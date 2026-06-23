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
from unittest import mock

# ── ensure package root is on sys.path ──────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import harness
from live_engine import run_live
from tools import gnomad_constraint_seam


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


def _fake_gnomad_fn(inputs):
    """Offline stand-in for the gnomAD seam: honest-empty, no network. Keeps the
    shared offline ctx from making a live API call when a gene symbol is present.
    The TestGnomadConstraintWiring tests pop this to exercise the real seam with
    _fetch monkeypatched to a recorded fixture."""
    return {"candidate": inputs.get("candidate", ""), "facts": [], "provenance": "gnomad"}


def _build_ctx():
    """Build a ctx dict that mocks every backend except the real moat."""
    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "qmodels_client": _fake_qmodels_client(),
        # gnomad-constraint would hit a public network API via the real seam; mock it
        # (honest-empty) so the offline suite never touches the network.
        "python_fns": {"gnomad-constraint": _fake_gnomad_fn},
        # NOTE: do NOT pre-populate python_fns["internal-science-lead"]/["aso-tox"] so
        #       that run_live wires the REAL moat + aso-tox backends by default.
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
        """The harness trace file must have ≥ (bucket1 agents dispatched + personas) records."""
        result = self._run()
        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_path), "trace file not found")

        with open(trace_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]

        # Compute expected minimum: agents actually dispatched in Bucket 1 + personas in panel.
        bucket1_dispatched = len(result["discover"]["agents"])
        personas_dispatched = len(result["consult"]["round1"])
        # +2 for the engagement_open and engagement_close bracket records.
        min_expected = bucket1_dispatched + personas_dispatched + 2
        self.assertGreaterEqual(
            len(lines), min_expected,
            f"Expected ≥{min_expected} trace records (bucket1={bucket1_dispatched}, "
            f"personas={personas_dispatched}); got {len(lines)}"
        )

    # ── test 3: consult round1 non-empty + harness provenance ───────────────
    def test_consult_round1_non_empty_and_stamped(self):
        """round1 must be non-empty, every verdict must carry provenance, and
        after FIX 1 (dossier_fields wired into ctx) at least one verdict must
        have status=='ok' with a real stance (not 'hold'/abstained)."""
        result = self._run()
        round1 = result["consult"]["round1"]
        self.assertTrue(len(round1) > 0, "consult round1 is empty")
        for v in round1:
            self.assertIn(
                "provenance", v,
                f"verdict missing provenance: {v}"
            )
        # Proof that must_cite_dossier is now correctly wired: at least one
        # verdict must pass all guardrails and carry a real stance.
        real_stances = {"pass", "conditional", "no_go"}
        ok_verdicts = [
            v for v in round1
            if v.get("status") == "ok" and v.get("stance") in real_stances
        ]
        self.assertTrue(
            len(ok_verdicts) >= 1,
            f"Expected ≥1 verdict with status=='ok' and real stance; "
            f"got stances={[(v.get('status'), v.get('stance')) for v in round1]}"
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


class TestAsoSequenceWiring(unittest.TestCase):
    """
    Tests for the sequences channel in run_live and the _extract_aso_sequences helper.

    All backend LLM/EMET/AWS calls are mocked ($0, offline).
    The aso-tox seam calls the REAL GBR model via subprocess — if sklearn is absent,
    the tests that require real predictions skip cleanly.
    """

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    # ── helper: build a ctx that uses the REAL aso-tox seam ─────────────────
    def _ctx_with_real_seam(self):
        """
        Build a ctx that keeps the real aso-tox seam wired (run_live default behavior).
        All other backends are mocked ($0, offline).
        """
        ctx = _build_ctx()
        # Explicitly ensure ctx["python_fns"]["aso-tox"] is NOT pre-populated so that
        # run_live wires the real aso_tox_seam.predict_findings.  pop() (not setdefault)
        # so a future _build_ctx that wires aso-tox can't silently break these tests.
        ctx.setdefault("python_fns", {}).pop("aso-tox", None)
        return ctx

    # ── test 8: sequences param → aso-tox facts in dossier ──────────────────
    def test_sequences_param_produces_aso_tox_facts(self):
        """
        run_live(..., sequences=[...]) must yield ≥1 fact with provenance=='aso-tox'
        in discover['dossier'], with GBR/label content matching the seam's output shape.

        Numeric cross-check: the dossier fact value must embed the real GBR score
        (formatted to 3 decimal places) produced by calling the seam directly.  A
        stub that returns formatted strings but doesn't call the model would produce
        a different number and fail this assertion.

        Skips if sklearn is unavailable (aso-tox subprocess would fail).
        """
        from tools import aso_tox_seam

        # Probe the seam to check whether sklearn is functional in this env.
        probe = aso_tox_seam.predict(["GCACTTGAATTTCACGTTGT"])
        if probe.get("error"):
            reason = probe["error"]
            self.skipTest(f"aso-tox seam not functional (sklearn absent?): {reason}")

        # Pick a reference sequence and get the real GBR score directly from the seam.
        ref_seq = "GCACTTGAATTTCACGTTGT"
        ref_raw = aso_tox_seam.predict([ref_seq])
        self.assertFalse(
            ref_raw.get("error"),
            f"Reference seam call failed: {ref_raw.get('error')}"
        )
        ref_preds = ref_raw.get("predictions", [])
        self.assertTrue(len(ref_preds) >= 1, "Reference seam call returned no predictions")
        ref_gbr = ref_preds[0]["gbr_predict_toxscore"]
        ref_gbr_str = f"{ref_gbr:.3f}"  # the format used by predict_findings

        seqs = [ref_seq, "TTGCTCCACCTTGGCCTGGCA"]
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            sequences=seqs,
            ctx=self._ctx_with_real_seam(),
        )

        dossier = result["discover"]["dossier"]
        tox_facts = [f for f in dossier if f.get("provenance") == "aso-tox"]

        self.assertTrue(
            len(tox_facts) >= 1,
            f"Expected ≥1 aso-tox fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )

        # Numeric cross-check: the real GBR score must appear in at least one fact value.
        values = [f.get("value", "") for f in tox_facts]
        has_numeric_match = any(ref_gbr_str in v for v in values)
        self.assertTrue(
            has_numeric_match,
            f"Expected real GBR score {ref_gbr_str!r} in at least one aso-tox fact value; "
            f"got values: {values}"
        )

        # Verify fact values contain GBR and a tox label (the seam's output shape).
        for f in tox_facts:
            val = f.get("value", "")
            self.assertIn(
                "GBR", val,
                f"Expected 'GBR' in aso-tox fact value; got: {val}"
            )
            # Should match one of the known labels produced by the seam.
            has_label = any(lbl in val for lbl in ("Non-toxic", "Toxic", "Unknown"))
            self.assertTrue(
                has_label,
                f"Expected a tox label in aso-tox fact value; got: {val}"
            )

    # ── test 9: no sequences → aso-tox dispatches but returns facts=[] ───────
    def test_no_sequences_aso_tox_honest_empty(self):
        """
        A normal target query (no sequences supplied) must still dispatch aso-tox
        and contribute facts=[] with no error — the honest-empty behavior.
        """
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=self._ctx_with_real_seam(),
        )

        dossier = result["discover"]["dossier"]
        agents = result["discover"]["agents"]

        # aso-tox agent must appear in the dispatch list (status ok or known).
        aso_agent = next((a for a in agents if a["id"] == "aso-tox"), None)
        self.assertIsNotNone(aso_agent, "aso-tox not found in discover.agents")

        # Status must be 'ok' — the honest-empty output (facts=[], invalid_sequences=[])
        # must pass harness schema validation, NOT abstain. Distinguishes a genuine
        # honest-empty run from a schema-rejection that also yields 0 dossier facts.
        self.assertEqual(
            aso_agent["status"], "ok",
            f"Expected aso-tox status 'ok' for honest-empty path; got {aso_agent}"
        )

        # No aso-tox facts should be present (honest empty path).
        tox_facts = [f for f in dossier if f.get("provenance") == "aso-tox"]
        self.assertEqual(
            len(tox_facts), 0,
            f"Expected 0 aso-tox facts for a query with no sequences; got {tox_facts}"
        )

    # ── test 10: extractor — positive detection ──────────────────────────────
    def test_extractor_detects_sequences_in_query(self):
        """
        _extract_aso_sequences must find pure A/T/G/C tokens of length ≥ 15
        embedded in a query string.
        """
        from live_engine import _extract_aso_sequences

        query = (
            "Score these ASO candidates: GCACTTGAATTTCACGTTGT "
            "and TTGCTCCACCTTGGCCTGGCA for TSC2."
        )
        found = _extract_aso_sequences(query)
        self.assertIn("GCACTTGAATTTCACGTTGT", found)
        self.assertIn("TTGCTCCACCTTGGCCTGGCA", found)

        # Punctuation-adjacent: comma-separated and trailing-period forms must
        # still split cleanly (the \b word boundary fires around punctuation).
        punct_query = "Candidates GCACTTGAATTTCACGTTGT,TTGCTCCACCTTGGCCTGGCA."
        punct_found = _extract_aso_sequences(punct_query)
        self.assertIn("GCACTTGAATTTCACGTTGT", punct_found)
        self.assertIn("TTGCTCCACCTTGGCCTGGCA", punct_found)
        self.assertEqual(len(punct_found), 2, f"Expected 2 sequences; got {punct_found}")

    # ── test 11: extractor — negative: gene symbols not misread ─────────────
    def test_extractor_does_not_misread_gene_symbols(self):
        """
        Gene symbols (TSC2, SCN2A, NAV1_8) and ordinary words must NOT be
        extracted as ASO sequences — they contain digits or non-ATGC characters.
        """
        from live_engine import _extract_aso_sequences

        query = (
            "Evaluate TSC2 in tuberous sclerosis. "
            "Consider SCN2A, NAV1_8, and GRIN2B as comparators. "
            "Is this a reasonable target? mTOR pathway analysis included."
        )
        found = _extract_aso_sequences(query)
        self.assertEqual(
            found, [],
            f"Expected no sequences extracted from gene-symbol query; got: {found}"
        )

    # ── test 12: extractor — boundary: length < 15 not extracted ────────────
    def test_extractor_ignores_short_atgc_tokens(self):
        """
        Pure A/T/G/C tokens shorter than 15 characters must not be extracted.
        """
        from live_engine import _extract_aso_sequences

        # 14-char pure ATGC token — should be ignored.
        query = "Evaluate GCACTTGAATTTCA for target binding."
        found = _extract_aso_sequences(query)
        self.assertEqual(
            found, [],
            f"Expected no extraction for 14-char token; got: {found}"
        )

    # ── test 13: extractor — lowercase not extracted ─────────────────────────
    def test_extractor_ignores_lowercase(self):
        """
        Lowercase sequences must NOT be extracted (strict uppercase only).
        """
        from live_engine import _extract_aso_sequences

        query = "Check gcacttgaatttcacgttgt binding affinity."
        found = _extract_aso_sequences(query)
        self.assertEqual(
            found, [],
            f"Expected no extraction from lowercase text; got: {found}"
        )

    # ── test 14: explicit sequences param overrides extractor ────────────────
    def test_explicit_sequences_param_takes_precedence(self):
        """
        When sequences= is explicitly provided, it should be used — the extractor
        fallback should NOT be invoked (no sequences from query text are added).
        We verify by passing sequences=[] explicitly for a query that contains an
        extractable sequence — dossier must have 0 aso-tox facts.
        """
        from tools import aso_tox_seam

        # Probe the seam — if unavailable, skip.
        probe = aso_tox_seam.predict(["GCACTTGAATTTCACGTTGT"])
        if probe.get("error"):
            self.skipTest(f"aso-tox seam not functional: {probe['error']}")

        # Query contains an extractable sequence but we explicitly pass sequences=[].
        query = "Score GCACTTGAATTTCACGTTGT for TSC2 toxicity."
        result = run_live(
            query,
            sequences=[],  # explicit empty list — overrides the extractor
            ctx=self._ctx_with_real_seam(),
        )

        dossier = result["discover"]["dossier"]
        tox_facts = [f for f in dossier if f.get("provenance") == "aso-tox"]
        self.assertEqual(
            len(tox_facts), 0,
            f"Expected 0 aso-tox facts when sequences=[] explicitly; got {tox_facts}"
        )

    # ── test 15: all-garbage sequences → 0 facts, surfaced in invalid channel ─
    def test_all_garbage_sequences_not_scored(self):
        """
        Garbage sequences (non-ATGC characters) passed via the explicit sequences=
        param must NOT be scored.  The seam must:
          1. Return 0 fabricated aso-tox facts in the dossier.
          2. Surface the rejected sequences in the invalid_sequences field.
          3. Not crash the engine.
        This verifies CONVENTIONS §3 (never fabricate; degrade honestly).
        """
        from tools import aso_tox_seam

        garbage_seqs = ["GCACTTGXYZ123ABCD", "NOT_DNA_AT_ALL", "12345678901234567"]
        # No sklearn skip-guard needed here: all sequences are invalid, so
        # _validate_sequences rejects them and predict() short-circuits before
        # ever spawning the subprocess. This path is exercised even without sklearn.
        raw = aso_tox_seam.predict(garbage_seqs)
        self.assertEqual(
            len(raw.get("predictions", [])), 0,
            f"Expected 0 predictions for all-garbage sequences; got: {raw.get('predictions')}"
        )
        invalid = raw.get("invalid_sequences", [])
        self.assertEqual(
            len(invalid), len(garbage_seqs),
            f"Expected all {len(garbage_seqs)} sequences in invalid_sequences; got: {invalid}"
        )
        # None of the original garbage strings should have slipped through.
        for g in garbage_seqs:
            self.assertIn(
                g, invalid,
                f"Garbage sequence {g!r} not found in invalid_sequences: {invalid}"
            )

        # Engine-level: run_live must not crash and must produce 0 aso-tox facts.
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            sequences=garbage_seqs,
            ctx=self._ctx_with_real_seam(),
        )
        dossier = result["discover"]["dossier"]
        tox_facts = [f for f in dossier if f.get("provenance") == "aso-tox"]
        self.assertEqual(
            len(tox_facts), 0,
            f"Expected 0 aso-tox facts for all-garbage sequences; got {tox_facts}"
        )

    # ── test 16: mixed valid+garbage → exactly one valid fact, one rejected ───
    def test_mixed_sequences_one_valid_one_garbage(self):
        """
        A mixed list (one valid ATGC sequence + one garbage) must produce exactly
        one scored fact (for the valid sequence only) and surface the garbage
        sequence in invalid_sequences.  This is the non-vacuous mixed-case test.
        """
        from tools import aso_tox_seam

        valid_seq = "GCACTTGAATTTCACGTTGT"
        garbage_seq = "GCACTTGXYZ123ABCD"

        # Probe the seam — if unavailable, skip.
        probe = aso_tox_seam.predict([valid_seq])
        if probe.get("error"):
            self.skipTest(f"aso-tox seam not functional (sklearn absent?): {probe['error']}")

        # Direct seam call for mixed list.
        raw = aso_tox_seam.predict([valid_seq, garbage_seq])
        self.assertEqual(
            len(raw.get("predictions", [])), 1,
            f"Expected exactly 1 prediction for 1 valid + 1 garbage; got: {raw.get('predictions')}"
        )
        # The valid sequence must be the one scored.
        scored_seq = raw["predictions"][0]["sequence"]
        self.assertEqual(
            scored_seq, valid_seq,
            f"Expected {valid_seq!r} to be scored; got {scored_seq!r}"
        )
        # The garbage must be recorded in invalid_sequences.
        invalid = raw.get("invalid_sequences", [])
        self.assertIn(
            garbage_seq, invalid,
            f"Expected {garbage_seq!r} in invalid_sequences; got: {invalid}"
        )

        # predict_findings interface: one fact, invalid_sequences populated.
        findings = aso_tox_seam.predict_findings(
            {"candidate": "TSC2", "sequences": [valid_seq, garbage_seq]}
        )
        self.assertEqual(
            len(findings.get("facts", [])), 1,
            f"Expected 1 fact for 1 valid + 1 garbage; got: {findings.get('facts')}"
        )
        self.assertIn(
            garbage_seq, findings.get("invalid_sequences", []),
            f"Expected {garbage_seq!r} in findings.invalid_sequences; got: "
            f"{findings.get('invalid_sequences')}"
        )

        # End-to-end through run_live: the schema-validated harness path must
        # accept the aso-tox output WITH invalid_sequences present and still land
        # exactly the one valid fact in the dossier. (Regression guard: the
        # aso-tox output_schema must allow invalid_sequences — otherwise the
        # harness rejects the output and the valid fact is silently dropped.)
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            sequences=[valid_seq, garbage_seq],
            ctx=self._ctx_with_real_seam(),
        )
        dossier = result["discover"]["dossier"]
        tox_facts = [f for f in dossier if f.get("provenance") == "aso-tox"]
        self.assertEqual(
            len(tox_facts), 1,
            f"Expected exactly 1 aso-tox fact through run_live (mixed valid+garbage); "
            f"got {tox_facts}. If 0, the harness rejected the output for carrying "
            f"invalid_sequences — check aso-tox output_schema."
        )
        self.assertIn(
            valid_seq, tox_facts[0].get("value", ""),
            f"Expected the valid sequence {valid_seq!r} in the scored fact; got {tox_facts[0]}"
        )
        # The aso-tox agent must be status 'ok' (not abstained) in this mixed case.
        aso_agent = next((a for a in result["discover"]["agents"] if a["id"] == "aso-tox"), None)
        self.assertIsNotNone(aso_agent, "aso-tox not found in discover.agents")
        self.assertEqual(
            aso_agent["status"], "ok",
            f"Expected aso-tox status 'ok' for mixed valid+garbage; got {aso_agent}"
        )

    # ── test 17: seam accepts lowercase and normalises to uppercase ───────────
    def test_seam_accepts_lowercase_atgc(self):
        """
        Lowercase atgc sequences must be accepted and normalised to uppercase before
        scoring (CONVENTIONS §3: degrade honestly — not reject valid DNA just because
        of case).  The predict_findings result must match a direct uppercase call.
        """
        from tools import aso_tox_seam

        lower_seq = "gcacttgaatttcacgttgt"
        upper_seq = lower_seq.upper()

        probe = aso_tox_seam.predict([upper_seq])
        if probe.get("error"):
            self.skipTest(f"aso-tox seam not functional (sklearn absent?): {probe['error']}")

        lower_raw = aso_tox_seam.predict([lower_seq])
        upper_raw = aso_tox_seam.predict([upper_seq])

        # Both calls must succeed with one prediction each.
        self.assertEqual(
            len(lower_raw.get("predictions", [])), 1,
            f"Expected 1 prediction for lowercase sequence; got: {lower_raw}"
        )
        self.assertEqual(
            len(upper_raw.get("predictions", [])), 1,
            f"Expected 1 prediction for uppercase sequence; got: {upper_raw}"
        )
        # GBR scores must be identical (same normalised input to model).
        gbr_lower = lower_raw["predictions"][0]["gbr_predict_toxscore"]
        gbr_upper = upper_raw["predictions"][0]["gbr_predict_toxscore"]
        self.assertAlmostEqual(
            gbr_lower, gbr_upper, places=6,
            msg=f"GBR mismatch after case normalisation: lower={gbr_lower} upper={gbr_upper}"
        )
        # Nothing should land in invalid_sequences.
        self.assertEqual(
            lower_raw.get("invalid_sequences", []), [],
            f"lowercase valid ATGC should not appear in invalid_sequences"
        )


# ── gnomAD constraint seam fixture (recorded live TSC2 GraphQL payload) ──────
_GNOMAD_FIXTURE_TSC2 = {
    "data": {"gene": {"symbol": "TSC2", "gnomad_constraint": {
        "pli": 1, "oe_lof": 0.14340755511655665,
        "oe_lof_upper": 0.1955335916011317, "mis_z": -0.07814465472993333}}}
}


class TestGnomadConstraintWiring(unittest.TestCase):
    """The gnomad-constraint seam, wired into run_live, lands a real cited fact in
    the dossier — proving the harness schema-validation + provenance-stamping path
    end-to-end. Network is monkeypatched at the seam's _fetch boundary ($0, offline)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _ctx_with_real_gnomad(self):
        """Offline ctx, but pop the gnomad mock so run_live wires the REAL seam
        (gnomad_constraint_seam.findings)."""
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("gnomad-constraint", None)
        return ctx

    def test_gnomad_fact_lands_in_dossier(self):
        """run_live on a gene query lands ≥1 fact with provenance 'gnomad' in the
        dossier, and the gnomad-constraint agent reports status 'ok'."""
        with mock.patch.object(gnomad_constraint_seam, "_fetch",
                               lambda symbol: _GNOMAD_FIXTURE_TSC2):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_gnomad(),
            )
        dossier = result["discover"]["dossier"]
        gnomad_facts = [f for f in dossier if f.get("provenance") == "gnomad"]
        self.assertTrue(
            len(gnomad_facts) >= 1,
            f"expected ≥1 gnomad fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )
        # Non-vacuous: the measured numbers must appear in the landed fact value.
        val = gnomad_facts[0]["value"]
        self.assertIn("pLI 1.00", val, val)
        self.assertIn("LOEUF 0.20", val, val)
        self.assertEqual(gnomad_facts[0]["tier"], "T1")
        # The fact must be provenance-stamped by the harness, and the agent 'ok'.
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gnomad-constraint"), None)
        self.assertIsNotNone(agent, "gnomad-constraint not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok; got {agent}")

    def test_no_gene_query_honest_empty_no_network(self):
        """A query with no extractable gene → the seam must NOT call the network,
        gnomad-constraint dispatches honest-empty (status 'ok'), 0 gnomad facts."""
        with mock.patch.object(gnomad_constraint_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Outline a general CNS target-validation strategy.",
                ctx=self._ctx_with_real_gnomad(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gnomad-constraint"), None)
        self.assertIsNotNone(agent, "gnomad-constraint not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok (honest-empty); got {agent}")
        gnomad_facts = [f for f in result["discover"]["dossier"]
                        if f.get("provenance") == "gnomad"]
        self.assertEqual(len(gnomad_facts), 0, f"expected 0 gnomad facts; got {gnomad_facts}")

    def test_api_down_degrades_no_crash(self):
        """If gnomAD is unreachable the engine must not crash: gnomad contributes 0
        facts and the agent degrades honestly (status 'ok', empty facts)."""
        import urllib.error

        def _boom(symbol):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(gnomad_constraint_seam, "_fetch", _boom):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_gnomad(),
            )
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gnomad-constraint"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected honest 'ok' empty; got {agent}")
        gnomad_facts = [f for f in result["discover"]["dossier"]
                        if f.get("provenance") == "gnomad"]
        self.assertEqual(len(gnomad_facts), 0)

    def test_internal_id_in_query_blocks_gnomad(self):
        """data_boundary must block the gnomad seam when an internal id (QS\\d+) is in
        the query — the seam never fires (no network), the agent abstains."""
        with mock.patch.object(gnomad_constraint_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Assess QS00123 against TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_gnomad(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gnomad-constraint"), None)
        self.assertIsNotNone(agent)
        self.assertIn(agent["status"], ("abstained", "escalated"),
                      f"expected data_boundary to block gnomad; got {agent}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
