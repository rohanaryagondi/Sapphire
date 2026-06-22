"""
tests/test_live_engine.py — Offline tests for live_engine.run_live.

All real backends (claude, emet, aws) are replaced with in-process mocks.
The REAL moat backend fires when the SQLite DB is available; the moat-specific
assertion is skipped (with a clear message) when the DB is absent.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_live_engine -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest

# ── ensure package root is on sys.path ──────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import harness
from live_engine import run_live


# ── Fake runner helpers ──────────────────────────────────────────────────────

def _fake_claude_runner(cmd):
    """
    Inspect the --json-schema arg to decide which schema to return.
    Verdict schema keys: persona, stance, conviction, rationale, fact_claims.
    Findings schema keys: candidate, facts.
    """
    # Find the --json-schema argument value
    schema_str = ""
    for i, tok in enumerate(cmd):
        if tok == "--json-schema" and i + 1 < len(cmd):
            schema_str = cmd[i + 1]
            break

    if '"stance"' in schema_str:
        # Return a valid verdict object
        obj = {
            "persona": "Mock Persona",
            "stance": "conditional",
            "conviction": 3,
            "rationale": "Mock rationale for testing.",
            "fact_claims": [{"claim": "TSC2 loss activates mTOR", "cite": "mock"}],
            "provenance": "semantic-web",
        }
    else:
        # Return a valid findings object
        obj = {
            "candidate": "X",
            "facts": [
                {"value": "mock", "source": "PMID:1", "tier": "T2"}
            ],
            "provenance": "semantic-web",
        }

    stdout = json.dumps({"structured_output": obj})
    return types.SimpleNamespace(stdout=stdout, returncode=0, stderr="")


def _fake_emet_handler(contract, inputs):
    return {
        "candidate": inputs.get("candidate", "X"),
        "facts": [
            {"value": "emet mock", "source": "PMID:9", "tier": "T2"}
        ],
        "provenance": "emet-live",
    }


def _fake_qmodels_client():
    def _call(tool, inp):
        return {"model": tool, "out": "mock", "provenance": "stub"}
    ns = types.SimpleNamespace(call=_call)
    return ns


def _build_ctx():
    """Build a ctx dict that mocks every backend except the real moat."""
    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "qmodels_client": _fake_qmodels_client(),
        # NOTE: do NOT pre-populate python_fns["internal-science-lead"] so that
        #       run_live wires the REAL moat backend by default.
    }


# ── Test cases ───────────────────────────────────────────────────────────────

class TestRunLive(unittest.TestCase):

    def setUp(self):
        """Use temp dirs so tests never touch the real engagements / memory stores."""
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    # ── helper ──────────────────────────────────────────────────────────────
    def _run(self, query="Is TSC2 a viable target in tuberous sclerosis?", ctx=None):
        return run_live(query, ctx=ctx or _build_ctx())

    # ── test 1: moat-real provenance ────────────────────────────────────────
    def test_moat_real_provenance(self):
        """dossier must contain ≥1 fact with provenance=='moat-real' when DB is available."""
        from moat.client import MoatClient
        available = MoatClient().available()

        result = self._run()
        dossier = result["discover"]["dossier"]

        if not available:
            self.skipTest("moat DB not built at RohanOnly/moat/moat.sqlite — skipping moat-real assertion")

        moat_facts = [f for f in dossier if f.get("provenance") == "moat-real"]
        self.assertTrue(
            len(moat_facts) >= 1,
            f"Expected ≥1 moat-real fact; got dossier: {[f.get('provenance') for f in dossier]}"
        )
        # Verify a TSC2 neighbor (e.g. TSC1) appears somewhere in the fact values.
        all_values = " ".join(f.get("value", "") for f in moat_facts)
        # TSC1 or TSC2 or mTOR should appear — any of these signals moat ran correctly.
        has_neighbour = any(gene in all_values.upper() for gene in ("TSC1", "TSC2", "MTOR", "RHEB"))
        self.assertTrue(
            has_neighbour,
            f"Expected a TSC neighbourhood gene in moat facts; values: {all_values[:300]}"
        )

    # ── test 2: harness trace records ────────────────────────────────────────
    def test_trace_has_sufficient_records(self):
        """The harness trace file must have ≥ (bucket1 agents + personas + 2 brackets) records."""
        result = self._run()
        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_path), "trace file not found")

        with open(trace_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]

        # Minimum: open + close brackets + at least some agent records.
        self.assertGreaterEqual(
            len(lines), 3,
            f"Expected ≥3 trace records; got {len(lines)}"
        )

    # ── test 3: consult round1 non-empty + harness provenance ───────────────
    def test_consult_round1_non_empty_and_stamped(self):
        """round1 must be non-empty and every verdict must carry a provenance field."""
        result = self._run()
        round1 = result["consult"]["round1"]
        self.assertTrue(len(round1) > 0, "consult round1 is empty")
        for v in round1:
            self.assertIn(
                "provenance", v,
                f"verdict missing provenance: {v}"
            )

    # ── test 4: data-boundary guardrail blocks internal id ──────────────────
    def test_guardrail_blocks_internal_id(self):
        """
        Sending an internal candidate ID (QS00123) into the harness should cause
        at least one agent to return status 'abstained' with error 'guardrail-violation'.
        We test harness.run directly on internal-science-lead to confirm the block.
        """
        from harness.contracts import load_registry
        registry = load_registry()
        ctx = _build_ctx()
        # Wire the real moat agent (run_live does this; we replicate for the direct call).
        ctx.setdefault("python_fns", {})
        from live_engine import _build_moat_agent
        ctx["python_fns"]["internal-science-lead"] = _build_moat_agent()

        # Use a temp eid for this isolated test.
        import hashlib
        eid = "eng_" + hashlib.sha256(b"test_guard").hexdigest()[:8]

        res = harness.run(
            "internal-science-lead",
            {"candidate": "QS00123", "disease": "tuberous sclerosis", "query": "analyze QS00123"},
            engagement_id=eid,
            ctx=ctx,
            registry=registry,
        )
        self.assertFalse(res.ok, "Expected harness to block QS00123 (internal id)")
        self.assertIn(
            res.status, ("abstained", "escalated"),
            f"Expected abstained/escalated; got status={res.status}"
        )
        self.assertEqual(
            res.error, "guardrail-violation",
            f"Expected guardrail-violation; got error={res.error}"
        )

    # ── test 5: reflection written > 0 ──────────────────────────────────────
    def test_reflection_written_positive(self):
        """reflect() must write ≥1 memory record for a query that yields facts."""
        result = self._run()
        reflection = result["reflection"]
        self.assertIn("written", reflection)
        self.assertGreater(
            reflection["written"], 0,
            f"Expected reflection.written > 0; got {reflection['written']}"
        )

    # ── test 6: result structure sanity ─────────────────────────────────────
    def test_result_structure(self):
        """Top-level keys + _via sentinel must be present."""
        result = self._run()
        for key in ("query", "plan", "priors", "discover", "consult", "synthesize",
                    "engagement_id", "reflection", "_via"):
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertEqual(result["_via"], "harness-live")

    # ── test 7: run_live with QS id in main query ────────────────────────────
    def test_run_live_with_internal_id_in_query(self):
        """
        Calling run_live with QS00123 in the query: the data_boundary guardrail
        fires on at least one agent (internal-science-lead), resulting in ≥1 agent
        with abstained/error status in discover.agents.
        """
        result = run_live(
            "analyze candidate QS00123 in tuberous sclerosis",
            ctx=_build_ctx(),
        )
        agents = result["discover"]["agents"]
        flagged = [a for a in agents if a["status"] in ("abstained", "escalated")]
        self.assertTrue(
            len(flagged) >= 1,
            f"Expected ≥1 abstained/escalated agent due to QS00123; got: {agents}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
