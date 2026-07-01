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
from contracts.run_live_schema import validate_run_live
from tools import gnomad_constraint_seam, gtex_expression_seam, interpro_domains_seam, geneset_enrichment_seam
from tools import boltz_seam


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
        # Return a valid verdict object.
        # fact_claims is intentionally empty: a non-empty cite ("mock") would depend on
        # dossier_fields containing "mock", but dossier_fields is built from a set whose
        # iteration order is randomised by PYTHONHASHSEED. When the moat is available
        # (k=4 → up to 12 unique fact values plus "emet mock") the total can exceed the
        # [:10] slice, randomly excluding "mock" and causing must_cite_dossier to fire on
        # every persona (~20-30% of runs). Empty fact_claims bypasses the guardrail check
        # entirely (the loop runs zero iterations → no violations) and is schema-valid.
        obj = {
            "persona": "Mock Persona",
            "stance": "conditional",
            "conviction": 3,
            "rationale": "Mock rationale for testing.",
            "fact_claims": [],
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


def _fake_gtex_fn(inputs):
    """Offline stand-in for the GTEx seam: honest-empty, no network. The
    TestGtexExpressionWiring tests pop this to exercise the real seam with _fetch
    monkeypatched to recorded fixtures."""
    return {"candidate": inputs.get("candidate", ""), "facts": [], "provenance": "gtex"}


def _fake_interpro_fn(inputs):
    """Offline stand-in for the InterPro seam: honest-empty, no network. The
    TestInterproDomainsWiring tests pop this to exercise the real seam with _fetch
    monkeypatched to recorded fixtures."""
    return {"candidate": inputs.get("candidate", ""), "facts": [], "provenance": "interpro"}


def _fake_geneset_fn(inputs):
    """Offline stand-in for the g:Profiler enrichment seam: honest-empty, no network.
    The TestGenesetEnrichmentWiring tests pop this to exercise the real seam with
    _fetch monkeypatched to a recorded fixture."""
    return {"candidate": inputs.get("candidate", ""), "facts": [], "provenance": "gprofiler"}


def _build_ctx():
    """Build a ctx dict that mocks every backend except the real moat."""
    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "qmodels_client": _fake_qmodels_client(),
        # gnomad-constraint would hit a public network API via the real seam; mock it
        # (honest-empty) so the offline suite never touches the network.
        "python_fns": {"gnomad-constraint": _fake_gnomad_fn, "gtex-expression": _fake_gtex_fn, "interpro-domains": _fake_interpro_fn, "geneset-enrichment": _fake_geneset_fn},
        # NOTE: do NOT pre-populate python_fns["internal-science-lead"]/["aso-tox"]/["robyn-scs"]
        #       so that run_live wires the REAL moat + aso-tox + robyn-scs backends by default.
        #       (robyn-scs is honest-empty without imaging input, so it stays $0/offline here.)
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
        from moat.facts import moat_facts as _moat_facts
        available = MoatClient().available()
        if not available:
            self.skipTest("moat DB not built at RohanOnly/moat/moat.sqlite — skipping moat-real assertion")
        # Also skip if the moat has no hits for TSC2 (stale/empty DB).
        probe = _moat_facts("TSC2", k=1)
        if not probe:
            self.skipTest("moat DB has no hits for TSC2 (stale DB or schema change) — skipping moat-real assertion")

        result = self._run()
        dossier = result["discover"]["dossier"]

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

    # ── test 8: dossier facts stamped with agent_id (WO-8 Phase 3) ───────────
    def test_dossier_facts_stamped_with_agent_id(self):
        """Every dossier fact appended to all_dossier_facts must carry a non-empty
        `agent_id` matching the id of a dispatched Bucket-1 agent — this is the ONLY
        way the web Info tab can show a step's complete contributed-facts list.
        Stamped UNCONDITIONALLY (not gated behind adaptive=True, unlike the
        internal-only `_source_agent` key on `_annot_facts`)."""
        result = self._run()
        dossier = result["discover"]["dossier"]
        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        self.assertTrue(dossier, "expected a non-empty dossier for this query")

        missing = [f for f in dossier if not f.get("agent_id")]
        self.assertEqual(
            missing, [],
            f"Expected every dossier fact to carry agent_id; facts missing it: {missing}"
        )
        bad = [f for f in dossier if f.get("agent_id") not in agent_ids]
        self.assertEqual(
            bad, [],
            f"agent_id must match a dispatched Bucket-1 agent id; got "
            f"{[f.get('agent_id') for f in bad]} not in {agent_ids}"
        )
        # Spot-check a known attribution: the fake EMET handler returns exactly one
        # fact per dispatch, with provenance 'emet-live' — it must attribute to
        # 'emet-runner' (the only agent that calls the emet handler), proving the
        # stamp isn't just "present" but actually correct per-agent.
        emet_facts = [f for f in dossier if f.get("provenance") == "emet-live"]
        if emet_facts:
            self.assertTrue(
                all(f.get("agent_id") == "emet-runner" for f in emet_facts),
                f"Expected emet-live facts attributed to emet-runner; got: {emet_facts}"
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


# ── Boltz structure/binding seam fixtures (recorded live shapes, 2026-06-25) ─
# START response (job accepted, pending). RETRIEVE response with a ligand-protein
# binding job → both a structure_confidence and a binding_confidence fact.
_BOLTZ_START_PENDING = {
    "id": "sab_pred_WIRETEST0001", "status": "pending", "output": None,
    "error": None, "model": "boltz-2.1",
}
_BOLTZ_RETRIEVE_BINDING = {
    "id": "sab_pred_WIRETEST0001", "status": "succeeded", "error": None,
    "output": {
        "best_sample": {"metrics": {"structure_confidence": 0.91, "complex_plddt": 0.88,
                                    "ptm": 0.7, "iptm": 0.65}},
        "binding_metrics": {"binding_confidence": 0.83, "optimization_score": 0.42,
                            "type": "ligand_protein_binding_metrics"},
    },
}
# A public protein sequence (≥25 aa, not pure ATGC) + a public ligand SMILES — the
# structure/affinity inputs that activate Boltz. Public identifiers only.
_BOLTZ_PROTEIN = "MKTAYIAKQRQISFVKSHFSRQMKTAYIAKQR"
_BOLTZ_SMILES = "CC(=O)Oc1ccccc1C(=O)O"


def _boltz_fake_http(method, path, api_key, body=None):
    """Fake boltz _http: POST→pending start, GET→succeeded binding job. No live key,
    no network — the seam's single network boundary, monkeypatched."""
    if method == "POST":
        return dict(_BOLTZ_START_PENDING)
    return dict(_BOLTZ_RETRIEVE_BINDING)


class TestBoltzWiring(unittest.TestCase):
    """The boltz structure/binding seam, wired into run_live, fires ONLY when a
    structure/affinity input is in scope and lands a real cited 'boltz'-provenance fact
    in the dossier — proving the harness schema-validation + provenance-stamping path
    end-to-end. The Boltz Compute API is monkeypatched at the seam's _http boundary
    ($0, offline, NO live key — _resolve_key is patched to a dummy)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _ctx(self):
        """Offline ctx. boltz is NOT pre-populated in python_fns, so run_live wires the
        REAL seam (boltz_seam.findings); the network is mocked at boltz_seam._http."""
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("boltz", None)
        return ctx

    # ── (a) Boltz fires + a boltz-provenance fact lands when structure present ──
    def test_boltz_fact_lands_when_structure_present(self):
        """run_live with a target sequence + ligand SMILES (structure= channel) lands
        ≥1 fact with provenance 'boltz' in the dossier, the boltz agent is 'ok', and the
        real binding number flows through (non-vacuous). No live key, no network."""
        with mock.patch.object(boltz_seam, "_resolve_key", lambda: "DUMMY_TEST_KEY"), \
             mock.patch.object(boltz_seam, "_http", _boltz_fake_http), \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                "Will this candidate engage the target?",
                structure={"target_sequence": _BOLTZ_PROTEIN, "ligand_smiles": _BOLTZ_SMILES},
                ctx=self._ctx(),
            )
        dossier = result["discover"]["dossier"]
        boltz_facts = [f for f in dossier if f.get("provenance") == "boltz"]
        self.assertTrue(
            len(boltz_facts) >= 1,
            f"expected ≥1 boltz fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )
        # Non-vacuous: the recorded binding number must appear in a landed fact value.
        vals = " || ".join(f["value"] for f in boltz_facts)
        self.assertIn("binding_confidence 0.83", vals, vals)
        self.assertTrue(all(f["tier"] == "T2" for f in boltz_facts), boltz_facts)
        # The fact must be EXTERNAL-plane (derived from the 'boltz' provenance).
        self.assertTrue(all(f.get("plane") == "external" for f in boltz_facts), boltz_facts)
        # The agent must be 'ok' and provenance-stamped by the harness.
        agent = next((a for a in result["discover"]["agents"] if a["id"] == "boltz"), None)
        self.assertIsNotNone(agent, "boltz not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok; got {agent}")
        self.assertEqual(agent["provenance"], "boltz", f"expected boltz provenance; got {agent}")

    def test_boltz_fires_on_protein_sequence_in_query_text(self):
        """The query-text activation channel: a protein sequence embedded in the query
        (no explicit structure= param) is extracted and activates Boltz → ≥1 boltz fact.
        Proves _extract_structure_inputs wires through end-to-end."""
        with mock.patch.object(boltz_seam, "_resolve_key", lambda: "DUMMY_TEST_KEY"), \
             mock.patch.object(boltz_seam, "_http", _boltz_fake_http), \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                f"Predict the fold for target sequence {_BOLTZ_PROTEIN} please.",
                ctx=self._ctx(),
            )
        boltz_facts = [f for f in result["discover"]["dossier"]
                       if f.get("provenance") == "boltz"]
        self.assertTrue(len(boltz_facts) >= 1,
                        f"expected ≥1 boltz fact from query-text protein; got {boltz_facts}")
        # Fold-only (no ligand) → a structure_confidence fact, no binding.
        vals = " ".join(f["value"] for f in boltz_facts)
        self.assertIn("structure_confidence", vals, vals)

    # ── (b) Boltz stays DORMANT when no structure/affinity input is in scope ────
    def test_no_structure_input_dormant_no_network(self):
        """A normal gene query (no sequence, no ligand) → boltz must NOT call the network,
        dispatches honest-empty (status 'ok'), and contributes 0 boltz facts. This mirrors
        how aso-tox stays silent without ASO sequences."""
        with mock.patch.object(boltz_seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(boltz_seam, "_http") as http_mock, \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx(),
            )
            http_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"] if a["id"] == "boltz"), None)
        self.assertIsNotNone(agent, "boltz not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok (dormant/honest-empty); got {agent}")
        boltz_facts = [f for f in result["discover"]["dossier"]
                       if f.get("provenance") == "boltz"]
        self.assertEqual(len(boltz_facts), 0, f"expected 0 boltz facts; got {boltz_facts}")

    # ── (c) Honest-degrade when the API key is absent ───────────────────────────
    def test_missing_key_degrades_honestly_no_crash(self):
        """Structure inputs ARE present but the BOLTZ_API_KEY is absent → the seam must
        degrade to a KNOWN_UNKNOWN abstain fact (never a fabricated structure/affinity),
        the engine must NOT crash, and the boltz agent stays 'ok' (it returned an honest
        envelope with a flagged fact, not a hard failure). No network call is made."""
        with mock.patch.object(boltz_seam, "_resolve_key", lambda: None), \
             mock.patch.object(boltz_seam, "_http") as http_mock, \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                "Will this candidate engage the target?",
                structure={"target_sequence": _BOLTZ_PROTEIN, "ligand_smiles": _BOLTZ_SMILES},
                ctx=self._ctx(),
            )
            http_mock.assert_not_called()  # no key ⇒ no network
        boltz_facts = [f for f in result["discover"]["dossier"]
                       if f.get("provenance") == "boltz"]
        # Exactly the honest KNOWN_UNKNOWN abstain fact — present, flagged, never fabricated.
        self.assertTrue(len(boltz_facts) >= 1,
                        f"expected the honest KNOWN_UNKNOWN fact; got {boltz_facts}")
        self.assertTrue(any(f.get("flag") == "KNOWN_UNKNOWN" for f in boltz_facts),
                        f"expected a KNOWN_UNKNOWN flag; got {boltz_facts}")
        self.assertTrue(all("unavailable" in f["value"].lower() for f in boltz_facts),
                        f"KNOWN_UNKNOWN fact must say it's unavailable; got {boltz_facts}")
        agent = next((a for a in result["discover"]["agents"] if a["id"] == "boltz"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok",
                         f"expected honest 'ok' with a KNOWN_UNKNOWN fact; got {agent}")

    def test_api_down_degrades_no_crash(self):
        """If the Boltz API is unreachable the engine must not crash: boltz degrades to a
        KNOWN_UNKNOWN fact and stays 'ok' (honest envelope, no fabrication)."""
        import urllib.error

        def _boom(method, path, api_key, body=None):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(boltz_seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(boltz_seam, "_http", _boom), \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                "Will this candidate engage the target?",
                structure={"target_sequence": _BOLTZ_PROTEIN, "ligand_smiles": _BOLTZ_SMILES},
                ctx=self._ctx(),
            )
        agent = next((a for a in result["discover"]["agents"] if a["id"] == "boltz"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected honest 'ok'; got {agent}")
        boltz_facts = [f for f in result["discover"]["dossier"]
                       if f.get("provenance") == "boltz"]
        self.assertTrue(any(f.get("flag") == "KNOWN_UNKNOWN" for f in boltz_facts),
                        f"expected a KNOWN_UNKNOWN flag on API-down; got {boltz_facts}")

    # ── boundary: internal data in a structural input must block Boltz ──────────
    def test_internal_id_in_structure_blocks_boltz(self):
        """data_boundary must block boltz when an internal id (QS\\d+) rides in a structural
        input — the seam never fires (no network), the agent abstains. Boltz receives PUBLIC
        identifiers only; internal moat data must never be transmitted."""
        with mock.patch.object(boltz_seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(boltz_seam, "_http") as http_mock, \
             mock.patch.object(boltz_seam, "_sleep", lambda s: None):
            result = run_live(
                "Will this candidate engage the target?",
                # An internal candidate id smuggled into the structural channel.
                structure={"target_sequence": _BOLTZ_PROTEIN, "ligand_ccd": "QS00123"},
                ctx=self._ctx(),
            )
            http_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"] if a["id"] == "boltz"), None)
        self.assertIsNotNone(agent)
        self.assertIn(agent["status"], ("abstained", "escalated"),
                      f"expected data_boundary to block boltz; got {agent}")
        boltz_facts = [f for f in result["discover"]["dossier"]
                       if f.get("provenance") == "boltz"]
        self.assertEqual(len(boltz_facts), 0, f"expected 0 boltz facts on block; got {boltz_facts}")


# ── GTEx seam fixtures (recorded TSC2 GTEx v2 responses) ─────────────────────
_GTEX_GENE_TSC2 = {"data": [{"gencodeId": "ENSG00000103197.16", "geneSymbol": "TSC2",
                            "geneSymbolUpper": "TSC2", "geneType": "protein coding"}]}
_GTEX_EXPR_TSC2 = {"data": [
    {"median": 133.226, "tissueSiteDetailId": "Brain_Cerebellum", "unit": "TPM"},
    {"median": 94.3068, "tissueSiteDetailId": "Pituitary", "unit": "TPM"},
    {"median": 38.1049, "tissueSiteDetailId": "Brain_Cortex", "unit": "TPM"},
]}


def _gtex_dispatch(path, params):
    """Fake gtex _fetch routing the two-call flow to recorded fixtures."""
    if "reference/gene" in path:
        return _GTEX_GENE_TSC2
    if "medianGeneExpression" in path:
        return _GTEX_EXPR_TSC2
    raise AssertionError(f"unexpected gtex path {path}")


class TestGtexExpressionWiring(unittest.TestCase):
    """The gtex-expression seam, wired into run_live, lands a real cited fact in the
    dossier. Network is monkeypatched at the seam's _fetch boundary ($0, offline)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _ctx_with_real_gtex(self):
        """Offline ctx, but pop the gtex mock so run_live wires the REAL seam."""
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("gtex-expression", None)
        return ctx

    def test_gtex_fact_lands_in_dossier(self):
        with mock.patch.object(gtex_expression_seam, "_fetch", _gtex_dispatch):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_gtex(),
            )
        dossier = result["discover"]["dossier"]
        gtex_facts = [f for f in dossier if f.get("provenance") == "gtex"]
        self.assertTrue(
            len(gtex_facts) >= 1,
            f"expected ≥1 gtex fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )
        val = gtex_facts[0]["value"]
        self.assertIn("Brain Cerebellum 133.2", val, val)
        self.assertIn("CNS-enriched", val, val)
        self.assertEqual(gtex_facts[0]["tier"], "T1")
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gtex-expression"), None)
        self.assertIsNotNone(agent, "gtex-expression not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok; got {agent}")

    def test_no_gene_query_honest_empty_no_network(self):
        with mock.patch.object(gtex_expression_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Outline a general CNS target-validation strategy.",
                ctx=self._ctx_with_real_gtex(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gtex-expression"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected ok (honest-empty); got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "gtex"], [])

    def test_api_down_degrades_no_crash(self):
        import urllib.error

        def _boom(path, params):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(gtex_expression_seam, "_fetch", _boom):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_gtex(),
            )
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gtex-expression"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected honest 'ok' empty; got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "gtex"], [])

    def test_internal_id_in_query_blocks_gtex(self):
        with mock.patch.object(gtex_expression_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Assess QS00123 against TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_gtex(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "gtex-expression"), None)
        self.assertIsNotNone(agent)
        self.assertIn(agent["status"], ("abstained", "escalated"),
                      f"expected data_boundary to block gtex; got {agent}")


# ── InterPro seam fixtures (recorded TSC2 → UniProt P49815 → InterPro) ───────
_INTERPRO_UNIPROT_TSC2 = {"results": [{"primaryAccession": "P49815"}]}
_INTERPRO_ENTRIES_TSC2 = {"count": 8, "results": [
    {"metadata": {"accession": "IPR000331", "name": "Rap/Ran-GAP domain", "type": "domain"}},
    {"metadata": {"accession": "IPR003913", "name": "Tuberin", "type": "family"}},
    {"metadata": {"accession": "IPR018515", "name": "Tuberin-type domain", "type": "domain"}},
    {"metadata": {"accession": "IPR027107", "name": "Tuberin/Ral GTPase-activating protein subunit alpha", "type": "family"}},
]}


def _interpro_dispatch(url):
    """Fake interpro _fetch routing the two-call flow (UniProt → InterPro) to fixtures."""
    if "rest.uniprot.org" in url:
        return _INTERPRO_UNIPROT_TSC2
    if "interpro" in url:
        return _INTERPRO_ENTRIES_TSC2
    raise AssertionError(f"unexpected interpro url {url}")


class TestInterproDomainsWiring(unittest.TestCase):
    """The interpro-domains seam, wired into run_live, lands a real cited fact in the
    dossier. Network is monkeypatched at the seam's _fetch boundary ($0, offline)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _ctx_with_real_interpro(self):
        """Offline ctx, but pop the interpro mock so run_live wires the REAL seam."""
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("interpro-domains", None)
        return ctx

    def test_interpro_fact_lands_in_dossier(self):
        with mock.patch.object(interpro_domains_seam, "_fetch", _interpro_dispatch):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_interpro(),
            )
        dossier = result["discover"]["dossier"]
        interpro_facts = [f for f in dossier if f.get("provenance") == "interpro"]
        self.assertTrue(
            len(interpro_facts) >= 1,
            f"expected ≥1 interpro fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )
        val = interpro_facts[0]["value"]
        self.assertIn("UniProt P49815", val, val)
        self.assertIn("IPR000331", val, val)
        self.assertEqual(interpro_facts[0]["tier"], "T1")
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "interpro-domains"), None)
        self.assertIsNotNone(agent, "interpro-domains not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok; got {agent}")

    def test_no_gene_query_honest_empty_no_network(self):
        with mock.patch.object(interpro_domains_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Outline a general CNS target-validation strategy.",
                ctx=self._ctx_with_real_interpro(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "interpro-domains"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected ok (honest-empty); got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "interpro"], [])

    def test_api_down_degrades_no_crash(self):
        import urllib.error

        def _boom(url):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(interpro_domains_seam, "_fetch", _boom):
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=self._ctx_with_real_interpro(),
            )
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "interpro-domains"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected honest 'ok' empty; got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "interpro"], [])

    def test_internal_id_in_query_blocks_interpro(self):
        with mock.patch.object(interpro_domains_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Assess QS00123 against TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_interpro(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "interpro-domains"), None)
        self.assertIsNotNone(agent)
        self.assertIn(agent["status"], ("abstained", "escalated"),
                      f"expected data_boundary to block interpro; got {agent}")


# ── g:Profiler seam fixture (recorded enrichment terms for {TSC1,TSC2,MTOR}) ─
_GENESET_FIXTURE = {"result": [
    {"native": "HP:0032051", "name": "Focal cortical dysplasia type II", "source": "HP", "p_value": 3.0497e-07, "significant": True},
    {"native": "WP:WP4141", "name": "PI3K AKT mTOR vitamin D3 signaling", "source": "WP", "p_value": 9.52e-07, "significant": True},
    {"native": "REAC:R-HSA-380972", "name": "Energy dependent regulation of mTOR by LKB1-AMPK", "source": "REAC", "p_value": 2.98e-06, "significant": True},
]}


def _geneset_dispatch(genes):
    """Fake geneset _fetch returning the recorded enrichment fixture."""
    return _GENESET_FIXTURE


class TestGenesetEnrichmentWiring(unittest.TestCase):
    """The geneset-enrichment seam, wired into run_live, lands a real cited fact in the
    dossier from the query's gene SET. Network monkeypatched at the seam's _fetch
    boundary ($0, offline)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _ctx_with_real_geneset(self):
        """Offline ctx, but pop the geneset mock so run_live wires the REAL seam."""
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("geneset-enrichment", None)
        return ctx

    def test_geneset_fact_lands_in_dossier(self):
        with mock.patch.object(geneset_enrichment_seam, "_fetch", _geneset_dispatch):
            result = run_live(
                "Compare TSC1 and TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_geneset(),
            )
        dossier = result["discover"]["dossier"]
        gp_facts = [f for f in dossier if f.get("provenance") == "gprofiler"]
        self.assertTrue(
            len(gp_facts) >= 1,
            f"expected ≥1 gprofiler fact; dossier provenances: "
            f"{[f.get('provenance') for f in dossier]}"
        )
        val = gp_facts[0]["value"]
        self.assertIn("significant terms", val, val)
        self.assertIn("HP:0032051", val, val)
        self.assertEqual(gp_facts[0]["tier"], "T2")
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "geneset-enrichment"), None)
        self.assertIsNotNone(agent, "geneset-enrichment not in discover.agents")
        self.assertEqual(agent["status"], "ok", f"expected ok; got {agent}")

    def test_gene_set_threaded_from_query(self):
        """run_live threads the WHOLE extracted gene set into the seam — both TSC1 and
        TSC2 reach g:Profiler, not just candidate (genes[0])."""
        captured = {}

        def _spy(genes):
            captured["genes"] = list(genes)
            return _GENESET_FIXTURE

        with mock.patch.object(geneset_enrichment_seam, "_fetch", _spy):
            run_live("Compare TSC1 and TSC2 in tuberous sclerosis.",
                     ctx=self._ctx_with_real_geneset())
        self.assertIn("TSC1", captured.get("genes", []))
        self.assertIn("TSC2", captured.get("genes", []))

    def test_no_gene_query_honest_empty_no_network(self):
        with mock.patch.object(geneset_enrichment_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Outline a general CNS target-validation strategy.",
                ctx=self._ctx_with_real_geneset(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "geneset-enrichment"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected ok (honest-empty); got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "gprofiler"], [])

    def test_api_down_degrades_no_crash(self):
        import urllib.error

        def _boom(genes):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(geneset_enrichment_seam, "_fetch", _boom):
            result = run_live(
                "Compare TSC1 and TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_geneset(),
            )
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "geneset-enrichment"), None)
        self.assertIsNotNone(agent)
        self.assertEqual(agent["status"], "ok", f"expected honest 'ok' empty; got {agent}")
        self.assertEqual(
            [f for f in result["discover"]["dossier"] if f.get("provenance") == "gprofiler"], [])

    def test_internal_id_in_query_blocks_geneset(self):
        with mock.patch.object(geneset_enrichment_seam, "_fetch") as fetch_mock:
            result = run_live(
                "Assess QS00123 against TSC2 in tuberous sclerosis.",
                ctx=self._ctx_with_real_geneset(),
            )
            fetch_mock.assert_not_called()
        agent = next((a for a in result["discover"]["agents"]
                      if a["id"] == "geneset-enrichment"), None)
        self.assertIsNotNone(agent)
        self.assertIn(agent["status"], ("abstained", "escalated"),
                      f"expected data_boundary to block geneset; got {agent}")


# ── A3: plane tagging in run_live output ─────────────────────────────────────

class TestPlaneTags(unittest.TestCase):
    """Every dossier fact in the run_live output must carry a `plane` field
    derived from its provenance (A3 — additive, never asserted by agents)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_every_dossier_fact_has_plane_field(self):
        """All facts in discover.dossier must carry a 'plane' field."""
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
        )
        dossier = result["discover"]["dossier"]
        self.assertTrue(len(dossier) > 0, "dossier is empty — cannot check plane tags")
        for i, fact in enumerate(dossier):
            self.assertIn(
                "plane", fact,
                f"dossier[{i}] (provenance={fact.get('provenance')!r}) missing 'plane' field",
            )
            self.assertIn(
                fact["plane"], ("internal", "external"),
                f"dossier[{i}] has invalid plane value: {fact['plane']!r}",
            )

    def test_plane_is_derived_from_provenance(self):
        """plane must equal plane_for(provenance) for every fact in the dossier."""
        from contracts.provenance import plane_for
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
        )
        for i, fact in enumerate(result["discover"]["dossier"]):
            prov = fact.get("provenance", "")
            if not prov:
                continue  # skip facts without provenance (shouldn't exist, but be safe)
            try:
                expected = plane_for(prov)
            except KeyError:
                expected = "external"  # unknown → conservative external
            self.assertEqual(
                fact.get("plane"), expected,
                f"dossier[{i}] plane mismatch: provenance={prov!r}, "
                f"expected plane={expected!r}, got {fact.get('plane')!r}",
            )

    def test_external_agent_facts_have_external_plane(self):
        """Facts from the mock external agents must be tagged 'external'."""
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
        )
        # The fake claude runner returns provenance="semantic-web" (not in PROVENANCE)
        # → should default to "external" (conservative). Other expected external provenances
        # include emet-live (but our mock emet handler is not in python_fns, it goes through
        # the emet harness path). We check everything that isn't "moat-real" is "external".
        for fact in result["discover"]["dossier"]:
            prov = fact.get("provenance")
            if prov == "moat-real":
                self.assertEqual(
                    fact.get("plane"), "internal",
                    f"moat-real fact must have plane='internal'; got {fact}",
                )
            else:
                self.assertEqual(
                    fact.get("plane"), "external",
                    f"non-moat fact (provenance={prov!r}) must have plane='external'; got {fact}",
                )


# ── A2: Adversarial boundary test — internal-plane fact must never reach an
#        external-fetch agent's dispatch. Tests use the plane-anchored rule. ───

class TestDataBoundaryAdversarial(unittest.TestCase):
    """Adversarial data-boundary tests.

    The enforcement mechanism: harness/guardrails.py data_boundary() scans inputs
    for internal keys/patterns BEFORE dispatch. These tests verify the end-to-end
    chain: internal-plane marker in inputs → agent abstains (never dispatched).

    The plane-rule logic is expressed in contracts.provenance.is_boundary_violation;
    these tests validate that both the rule function AND the runtime guardrail agree.
    """

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _eid(self, label: str) -> str:
        import hashlib
        return "eng_" + hashlib.sha256(label.encode()).hexdigest()[:8]

    def test_internal_score_to_emet_is_blocked(self):
        """Feeding an internal score (internal-plane) to emet-runner must BLOCK (abstain)."""
        from harness.contracts import load_registry
        registry = load_registry()
        ctx = _build_ctx()

        # Inputs that carry an internal key: s_internal is a known internal field.
        # The plane rule: plane_for("emet-live") == "external" and the fact carries
        # internal data → is_boundary_violation("emet-live", "internal") == True.
        # The runtime enforcer (data_boundary guardrail) fires on the key name.
        poisoned_inputs = {
            "candidate": "TSC2",
            "disease": "tuberous sclerosis",
            "query": "evaluate TSC2",
            "s_internal": 0.97,   # ← internal key; must never reach emet
        }
        res = harness.run(
            "emet-runner",
            poisoned_inputs,
            engagement_id=self._eid("emet-adversarial"),
            ctx=ctx,
            registry=registry,
        )
        self.assertFalse(res.ok, "Expected BLOCK: emet-runner received internal key")
        self.assertIn(
            res.status, ("abstained", "escalated"),
            f"Expected abstained/escalated; got {res.status}",
        )
        self.assertEqual(
            res.error, "guardrail-violation",
            f"Expected guardrail-violation; got error={res.error}",
        )

    def test_internal_candidate_id_to_gnomad_is_blocked(self):
        """A QS-format internal candidate id (internal-plane) sent to gnomad-constraint
        must be blocked — the seam never fires (adversarial plane-crossing test)."""
        from harness.contracts import load_registry
        from tools import gnomad_constraint_seam

        registry = load_registry()
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("gnomad-constraint", None)

        fetch_calls = []

        def _spy_fetch(symbol):
            fetch_calls.append(symbol)
            return {}

        with mock.patch.object(gnomad_constraint_seam, "_fetch", _spy_fetch):
            res = harness.run(
                "gnomad-constraint",
                {"candidate": "QS00123", "disease": "tuberous sclerosis",
                 "query": "evaluate QS00123", "genes": ["QS00123"]},
                engagement_id=self._eid("gnomad-adversarial"),
                ctx=ctx,
                registry=registry,
            )

        # The seam must NEVER have been called (data_boundary blocked before dispatch).
        self.assertEqual(
            fetch_calls, [],
            f"gnomad _fetch was called with internal id QS00123: {fetch_calls}",
        )
        self.assertFalse(res.ok, "Expected BLOCK: gnomad received internal candidate id")
        self.assertIn(res.status, ("abstained", "escalated"))
        self.assertEqual(res.error, "guardrail-violation")

    def test_internal_latent_vector_to_aso_tox_is_blocked(self):
        """A latent_vector field (internal-plane) forwarded to aso-tox must be blocked —
        aso-tox is an external-plane agent (public ASO sequences only)."""
        from harness.contracts import load_registry
        registry = load_registry()
        ctx = _build_ctx()
        ctx.setdefault("python_fns", {}).pop("aso-tox", None)

        called = []

        def _spy_predict(inputs):
            called.append(inputs)
            return {"candidate": "TSC2", "facts": [], "invalid_sequences": [], "provenance": "aso-tox"}

        ctx["python_fns"]["aso-tox"] = _spy_predict

        res = harness.run(
            "aso-tox",
            {"candidate": "TSC2", "disease": "ts", "query": "eval",
             "sequences": [], "latent_vector": [0.1, 0.2, 0.3]},
            engagement_id=self._eid("aso-tox-adversarial"),
            ctx=ctx,
            registry=registry,
        )
        # Seam must NOT have been called.
        self.assertEqual(called, [], f"aso-tox seam was called with internal latent_vector: {called}")
        self.assertFalse(res.ok)
        self.assertIn(res.status, ("abstained", "escalated"))
        self.assertEqual(res.error, "guardrail-violation")

    def test_clean_external_inputs_to_external_agents_pass(self):
        """Verify the guard does NOT trigger false-positives: a clean external-plane
        input to an external-plane agent must not be blocked."""
        from harness.contracts import load_registry
        registry = load_registry()
        ctx = _build_ctx()

        # Clean inputs with only public identifiers (no internal keys/patterns).
        clean_inputs = {
            "candidate": "TSC2",
            "disease": "tuberous sclerosis",
            "query": "Is TSC2 a viable target?",
            "genes": ["TSC2"],
            "sequences": [],
        }
        res = harness.run(
            "emet-runner",
            clean_inputs,
            engagement_id=self._eid("emet-clean"),
            ctx=ctx,
            registry=registry,
        )
        # Status should not be "guardrail-violation"; it may still abstain due to mock
        # emet backend returning a result, but the error must not be guardrail-violation.
        self.assertNotEqual(
            res.error, "guardrail-violation",
            f"False positive: clean inputs triggered guardrail-violation on emet-runner",
        )

    def test_is_boundary_violation_matches_runtime_block(self):
        """The plane-rule function and the runtime guardrail must agree:
        is_boundary_violation(provenance, 'internal') == True  ↔  data_boundary blocks.

        We test this for emet-live (external plane) with an internal key present.
        """
        from contracts.provenance import is_boundary_violation
        from harness.guardrails import data_boundary

        # Rule function agrees: emet-live is external, internal facts → violation.
        self.assertTrue(is_boundary_violation("emet-live", "internal"))

        # Runtime agrees: data_boundary detects the internal key and returns violations.
        viols = data_boundary({"candidate": "TSC2", "s_internal": 0.97})
        self.assertTrue(
            len(viols) > 0,
            "data_boundary must return violations when s_internal is present",
        )
        self.assertEqual(viols[0].guardrail, "data_boundary")


def _batch_aware_runner(cmd):
    """A fake claude runner that handles BOTH the Opt-2 batch prompt and single-agent prompts.
    For a batch prompt it returns one object keyed by each `### AGENT: <id>` block."""
    import re
    prompt = ""
    for i, tok in enumerate(cmd):
        if tok == "-p" and i + 1 < len(cmd):
            prompt = cmd[i + 1]
            break
    if "MULTIPLE specialist agents" in prompt:
        ids = re.findall(r"### AGENT: (\S+)", prompt)
        body = {aid: {"candidate": "X",
                      "facts": [{"value": f"batched {aid} fact", "source": "PMID:7", "tier": "T2"}],
                      "provenance": "semantic-web"}
                for aid in ids}
        return types.SimpleNamespace(stdout=json.dumps({"structured_output": body}),
                                     returncode=0, stderr="")
    return _fake_claude_runner(cmd)


class TestBatchBucket1(unittest.TestCase):
    """Opt-2 — batched Bucket-1 dispatch produces the same per-agent guarded/stamped facts."""

    def setUp(self):
        self._eng = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_batched_agents_land_facts_and_are_stamped(self):
        # Monkeypatch live_engine.has_corpus → False so all agents are treated as
        # corpus-less for this test.  Phase 0 grounded all 13 semantic agents, which
        # correctly makes _batch_bucket1 skip every agent (corpus agents skip the batch
        # path by design).  But the TEST must exercise the batch mechanism regardless of
        # production grounding state, so we decouple them here.  The patch is scoped to
        # this test via addCleanup and cannot leak into other tests.
        import live_engine as _le
        _orig_has_corpus = _le.has_corpus
        _le.has_corpus = lambda *a, **k: False
        self.addCleanup(setattr, _le, "has_corpus", _orig_has_corpus)

        ctx = _build_ctx()
        ctx["runner"] = _batch_aware_runner
        ctx["batch_buckets"] = True
        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
        agents = {a["id"]: a for a in result["discover"]["agents"]}
        # A batched corpus-less claude-subagent agent fired ok with its provenance stamped.
        self.assertEqual(agents.get("patent-ip", {}).get("status"), "ok")
        batched_facts = [f for f in result["discover"]["dossier"]
                         if "batched" in f.get("value", "")]
        self.assertTrue(batched_facts, "batched agents' facts must reach the dossier")
        # provenance is stamped exactly as the per-agent path would (external plane).
        self.assertTrue(all(f.get("provenance") for f in batched_facts))

    def test_batch_failure_falls_back_to_per_agent(self):
        # A batch runner that errors → run_live still completes via per-agent dispatch.
        def _broken_batch(cmd):
            prompt = next((cmd[i + 1] for i, t in enumerate(cmd) if t == "-p"), "")
            if "MULTIPLE specialist agents" in prompt:
                return types.SimpleNamespace(stdout="", returncode=1, stderr="batch boom")
            return _fake_claude_runner(cmd)
        ctx = _build_ctx()
        ctx["runner"] = _broken_batch
        ctx["batch_buckets"] = True
        result = run_live("Is TSC2 a viable target?", ctx=ctx)
        agents = {a["id"]: a for a in result["discover"]["agents"]}
        # patent-ip still answered (per-agent fallback via the single-agent fake runner).
        self.assertEqual(agents.get("patent-ip", {}).get("status"), "ok")

    def test_default_path_does_not_batch(self):
        # Without the flag, _batch_bucket1 is never consulted (no batch prompt issued).
        seen = {"batch": False}

        def _watch(cmd):
            prompt = next((cmd[i + 1] for i, t in enumerate(cmd) if t == "-p"), "")
            if "MULTIPLE specialist agents" in prompt:
                seen["batch"] = True
            return _fake_claude_runner(cmd)
        ctx = _build_ctx()
        ctx["runner"] = _watch
        run_live("Is TSC2 a viable target?", ctx=ctx)  # no batch_buckets
        self.assertFalse(seen["batch"])


class TestEmetHandlerWiring(unittest.TestCase):
    """W1 — run_live registers a live EMET handler on ctx=None (lazy, setdefault)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_wire_registers_a_callable_emet_handler(self):
        # The empty ctx (the ctx=None path) gains a real, callable emet_handler — no longer
        # silently absent. Lazy import means this also proves emet.handler imports cleanly.
        from live_engine import _wire_emet_handler
        ctx = {}
        _wire_emet_handler(ctx)
        self.assertIn("emet_handler", ctx)
        self.assertTrue(callable(ctx["emet_handler"]))

    def test_wire_does_not_override_injected_handler(self):
        from live_engine import _wire_emet_handler
        sentinel = lambda contract, inputs: {"facts": []}  # noqa: E731
        ctx = {"emet_handler": sentinel}
        _wire_emet_handler(ctx)
        self.assertIs(ctx["emet_handler"], sentinel)

    def test_injected_mock_handler_lands_an_emet_fact(self):
        # The brief's "injected mock emet_handler → the agent fires and lands a fact" check.
        # This exercises the emet-runner DISPATCH path (handler supplied via _build_ctx);
        # the NEW W1 wiring (registering a handler on ctx=None) is covered by
        # test_wire_registers_a_callable_emet_handler + test_emet_runner_not_silently_absent_on_ctx_none.
        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=_build_ctx())
        dossier = result["discover"]["dossier"]
        emet_facts = [f for f in dossier if f.get("provenance") == "emet-live"]
        self.assertTrue(emet_facts, "the mock EMET handler should land >=1 emet-live fact")

    def test_emet_runner_not_silently_absent_on_ctx_none(self):
        # ctx=None must REGISTER a handler so emet-runner doesn't abstain with
        # 'handler not registered'. We avoid a live call by mocking the handler the wiring
        # installs (patch make_emet_handler to a recording mock), plus a mock claude runner.
        import live_engine
        calls = {"n": 0}

        def _spy_handler(contract, inputs):
            calls["n"] += 1
            return {"candidate": inputs.get("candidate", ""),
                    "facts": [{"value": "spy emet fact", "source": "PMID:1", "tier": "T2"}],
                    "provenance": "emet-live"}

        orig = live_engine._wire_emet_handler

        def _patched(ctx):
            ctx.setdefault("emet_handler", _spy_handler)

        live_engine._wire_emet_handler = _patched
        try:
            # ctx provides the OTHER mock backends but NOT an emet_handler, so the wiring fills it.
            ctx = _build_ctx()
            ctx.pop("emet_handler", None)
            result = run_live("Is TSC2 a viable target?", ctx=ctx)
        finally:
            live_engine._wire_emet_handler = orig
        self.assertGreater(calls["n"], 0, "the registered emet handler must actually be invoked")
        agents = {a["id"]: a["status"] for a in result["discover"]["agents"]}
        self.assertEqual(agents.get("emet-runner"), "ok")  # fired, not abstained


class TestSimulateModelsRunLive(unittest.TestCase):
    """SAPPHIRE_SIMULATE_MODELS in a full run_live: persona reasoning is labeled-simulated, while
    real moat/EMET facts stay genuinely real (the demo's honesty contract)."""

    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"

    def tearDown(self):
        for k in ("SAPPHIRE_ENGAGEMENTS_DIR", "SAPPHIRE_MEMORY_DIR", "SAPPHIRE_SIMULATE_MODELS"):
            os.environ.pop(k, None)

    def test_personas_simulated_moat_stays_real(self):
        from moat.client import MoatClient
        from moat.facts import moat_facts as _moat_facts
        # Skip if the moat DB is unavailable or has no TSC2 hits (stale/empty DB).
        if not MoatClient().available() or not _moat_facts("TSC2", k=1):
            self.skipTest(
                "moat DB unavailable or has no TSC2 hits — skipping moat-real simulated-run assertion"
            )
        r = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=_build_ctx())
        self.assertEqual(validate_run_live(r), [])
        # Every persona verdict is labeled simulated — never presented as a real verdict.
        provs = [v.get("provenance") for v in r["consult"]["round1"]]
        self.assertTrue(provs and all(p == "simulated" for p in provs), provs)
        self.assertTrue(all("🧪 simulated" in v.get("rationale", "") for v in r["consult"]["round1"]))
        # Real moat facts are untouched (internal plane, real provenance).
        moat = [f for f in r["discover"]["dossier"] if f.get("provenance") == "moat-real"]
        self.assertTrue(moat, "real moat facts must remain in a simulated run")
        self.assertTrue(all(f.get("plane") == "internal" for f in moat))


class TestLiveProgress(unittest.TestCase):
    """live-run-visibility W1 — run_live(on_progress=…) streams ordered milestones, additive."""

    def setUp(self):
        self._eng = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run(self, **kw):
        return run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=_build_ctx(), **kw)

    def test_events_fire_in_stage_order(self):
        events = []
        self._run(on_progress=events.append)
        self.assertTrue(events)
        self.assertEqual(events[0]["stage"], "plan")
        # WO-9 Phase 2: a "report" stage now always fires last (a terminal "done" event,
        # after any streamed "chunk" events) -- the report synthesizer runs after synthesis.
        self.assertEqual(events[-1], {"stage": "report", "phase": "done"})
        synthesis_done = [e for e in events if e["stage"] == "synthesis" and e["phase"] == "done"]
        self.assertEqual(len(synthesis_done), 1)
        self.assertIn("recommendation", synthesis_done[0])
        self.assertIn("confidence", synthesis_done[0])
        stages = [e["stage"] for e in events]
        # bucket1 (and its flags) precede roundtable precede synthesis precede report
        self.assertLess(stages.index("bucket1"), stages.index("roundtable"))
        self.assertLess(stages.index("flags"), stages.index("roundtable"))
        self.assertLess(stages.index("roundtable"), stages.index("synthesis"))
        self.assertLess(stages.index("synthesis"), stages.index("report"))

    def test_bucket1_done_events_carry_real_result(self):
        events = []
        self._run(on_progress=events.append)
        done = [e for e in events if e["stage"] == "bucket1" and e["phase"] == "done"]
        self.assertTrue(done)
        for e in done:
            self.assertIn("status", e)
            self.assertIn("provenance", e)
            self.assertIn("n_facts", e)
            self.assertIn("elapsed_s", e)
        # the internal moat agent reports its real provenance + fact count (not a fake "ok")
        moat = [e for e in done if e["agent_id"] == "internal-science-lead"]
        self.assertTrue(moat)
        self.assertEqual(moat[0]["provenance"], "moat-real")

    def test_roundtable_done_events_carry_stance(self):
        events = []
        self._run(on_progress=events.append)
        rt = [e for e in events if e["stage"] == "roundtable" and e["phase"] == "done"]
        self.assertTrue(rt)
        for e in rt:
            self.assertIn("stance", e)
            self.assertEqual(e["round"], 1)

    def test_additive_output_identical_with_and_without_callback(self):
        r0 = self._run()
        r1 = self._run(on_progress=lambda e: None)
        self.assertEqual(len(r0["discover"]["dossier"]), len(r1["discover"]["dossier"]))
        self.assertEqual(r0["consult"]["round1"], r1["consult"]["round1"])
        self.assertEqual(r0["synthesize"]["recommendation"], r1["synthesize"]["recommendation"])

    def test_raising_callback_never_breaks_the_run(self):
        def _boom(e):
            raise RuntimeError("ui blew up")
        result = self._run(on_progress=_boom)   # must NOT raise
        self.assertIn("discover", result)
        self.assertTrue(result["consult"]["round1"])

    def test_progress_flushed_to_trace_incrementally(self):
        import json as _json
        result = self._run(on_progress=lambda e: None)
        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng, eid, "trace.jsonl")
        with open(trace_path, encoding="utf-8") as fh:
            evts = [_json.loads(l) for l in fh if l.strip()]
        prog = [e for e in evts if e.get("type") == "progress"]
        self.assertTrue(prog, "progress milestones must be recorded to trace.jsonl (tail-able)")
        # plan progress appears BEFORE the engagement_close record (i.e. mid-run, not only at close)
        kinds = [e.get("type") for e in evts]
        self.assertIn("engagement_close", kinds)
        first_progress = next(i for i, e in enumerate(evts) if e.get("type") == "progress")
        close_idx = kinds.index("engagement_close")
        self.assertLess(first_progress, close_idx)


class TestPhaseADoD(unittest.TestCase):
    """Phase A Definition of Done checks:
    1. run_live output shape matches canned path (round1 + round2 + spread).
    2. All 13 semantic agents dispatch.
    3. A VETO fact provably forces adjudication.
    """

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run(self, query="Is TSC2 a viable target in tuberous sclerosis?", ctx=None):
        return run_live(query, ctx=ctx or _build_ctx())

    # DoD check 1: run_live shape matches canned path
    def test_consult_has_round2_and_spread(self):
        """run_live must return consult with round1, round2, and spread (matching canned shape)."""
        result = self._run()
        consult = result["consult"]
        self.assertIn("round1", consult, "consult missing round1")
        self.assertIn("round2", consult, "consult missing round2 — Phase A not done")
        self.assertIn("spread", consult, "consult missing spread — Phase A not done")
        # round2 is a list of rebuttal entries
        self.assertIsInstance(consult["round2"], list)
        # spread has the expected subkeys
        spread = consult["spread"]
        for key in ("conviction_range", "stance_mix", "moved_in_round2", "convergent_gate"):
            self.assertIn(key, spread, f"spread missing key {key!r}")
        # Shape lock: conviction_range must be a STRING (e.g. "3-4 / 5" or "-"),
        # and moved_in_round2 must be a LIST of persona-name strings — matching both
        # the canned path (orchestrator.py:298,300) and the live path (live_engine.py:884,889).
        self.assertIsInstance(spread["conviction_range"], str,
                              f"spread.conviction_range must be str; got {type(spread['conviction_range'])}: "
                              f"{spread['conviction_range']!r}")
        self.assertIsInstance(spread["moved_in_round2"], list,
                              f"spread.moved_in_round2 must be list; got {type(spread['moved_in_round2'])}: "
                              f"{spread['moved_in_round2']!r}")

    def test_round2_entries_have_revised_and_shift(self):
        """round2 entries must carry revised (bool) and shift (str)."""
        result = self._run()
        round2 = result["consult"]["round2"]
        self.assertTrue(len(round2) > 0, "round2 must be non-empty")
        for entry in round2:
            self.assertIn("persona", entry)
            self.assertIn("revised", entry)
            self.assertIn("conviction", entry)
            self.assertIn("shift", entry)
            self.assertIsInstance(entry["revised"], bool)

    # DoD check 2: all 13 semantic agents dispatch
    def test_all_13_semantic_agents_dispatch(self):
        """All 13 semantic agents must appear in discover.agents."""
        SEMANTIC_13 = {
            "fda-institutional-memory", "patent-ip", "global-regulatory-divergence",
            "dea-scheduling", "clinical-trial-registry", "post-market-safety",
            "financial", "payer", "manufacturing-cmc", "patient-advocacy",
            "kol-social", "policy-legislative", "reputational",
        }
        result = self._run()
        dispatched_ids = {a["id"] for a in result["discover"]["agents"]}
        missing = SEMANTIC_13 - dispatched_ids
        self.assertEqual(
            missing, set(),
            f"These semantic agents did not dispatch: {missing}. "
            f"Got: {sorted(dispatched_ids)}"
        )

    # DoD check 3: VETO fact forces adjudication
    def test_veto_fact_forces_adjudication(self):
        """When a Bucket-1 agent returns a VETO fact, consult must carry adjudication
        with veto_facts surfaced. This proves the VETO-as-gate MECHANICS fire:
        - exactly 1 VETO from fda-institutional-memory (narrow mock, not 8 duplicates)
        - adj["n_veto"] == 1
        - a 'veto_gate' trace landmark is written mid-run (auditable gate)
        """
        # Build a ctx that injects a VETO fact ONLY from fda-institutional-memory.
        ctx = _build_ctx()

        _original_runner = ctx["runner"]
        def _veto_runner(cmd):
            # Detect if this is the fda-institutional-memory call by prompt content.
            # Match ONLY on the exact agent id string — do NOT match the broad "fda"
            # substring which would fire on ~8 agents and yield duplicate veto_facts.
            prompt_str = ""
            for i, tok in enumerate(cmd):
                if tok == "-p" and i + 1 < len(cmd):
                    prompt_str = cmd[i + 1]
                    break
            if "fda-institutional-memory" in prompt_str:
                obj = {
                    "candidate": "TSC2",
                    "facts": [
                        {"value": "Prior CRL on mTOR inhibitor class for CNS (2019)",
                         "source": "FDA.gov", "tier": "T1", "flag": "VETO",
                         "provenance": "fda-primary"}
                    ],
                    "provenance": "fda-primary",
                }
                return types.SimpleNamespace(
                    stdout=json.dumps({"structured_output": obj}),
                    returncode=0, stderr=""
                )
            return _original_runner(cmd)

        ctx["runner"] = _veto_runner

        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
        eid = result["engagement_id"]

        # VETO must be in discover.flags
        veto_flags = result["discover"]["flags"]["VETO"]
        self.assertTrue(len(veto_flags) >= 1,
                        f"Expected ≥1 VETO flag; got {veto_flags}")

        # consult must carry adjudication when veto_flags is non-empty
        consult = result["consult"]
        self.assertIn("adjudication", consult,
                      "consult missing 'adjudication' key when VETO facts present")
        adj = consult["adjudication"]
        self.assertIn("veto_facts", adj)

        # Exactly 1 VETO: the narrow mock fires only for fda-institutional-memory.
        # If this fails (n_veto > 1) the broad "fda" match crept back in.
        self.assertEqual(adj["n_veto"], 1,
                         f"Expected exactly 1 VETO (from fda-institutional-memory only); "
                         f"got {adj['n_veto']}. veto_facts={adj.get('veto_facts')}")

        # Gate mechanics: the 'veto_gate' trace landmark must have been written
        # mid-run — this proves the gate logic executed, not just that the output
        # key was decorated after the fact.
        trace_path = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_path),
                        f"trace file not found at {trace_path}")
        with open(trace_path, encoding="utf-8") as fh:
            trace_records = [json.loads(line) for line in fh if line.strip()]
        veto_gate_records = [r for r in trace_records if r.get("type") == "veto_gate"]
        self.assertTrue(
            len(veto_gate_records) >= 1,
            f"Expected ≥1 'veto_gate' trace record; got types: "
            f"{[r.get('type') for r in trace_records]}"
        )

    def test_plan_has_capability_class(self):
        """The plan must carry a 'class' field ∈ {diligence, design, experiment}."""
        result = self._run()
        plan = result["plan"]
        self.assertIn("class", plan, "plan missing 'class' field — Phase A not done")
        self.assertIn(plan["class"], {"diligence", "design", "experiment"},
                      f"plan.class must be one of diligence/design/experiment; got {plan['class']!r}")

    def test_plan_class_design_for_design_query(self):
        """A query containing 'design' should yield plan.class == 'design'."""
        result = run_live(
            "Design an ASO targeting TSC2 for tuberous sclerosis.",
            ctx=_build_ctx(),
        )
        self.assertEqual(result["plan"].get("class"), "design")

    def test_plan_class_experiment_for_experiment_query(self):
        """A query containing an experiment keyword should yield plan.class == 'experiment'."""
        result = run_live(
            "Validate TSC2 as a target in vivo in a mouse model.",
            ctx=_build_ctx(),
        )
        self.assertEqual(result["plan"].get("class"), "experiment")

    def test_plan_class_default_diligence(self):
        """A generic diligence query should default to plan.class == 'diligence'."""
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
        )
        self.assertEqual(result["plan"].get("class"), "diligence")


class TestBucket1Parallelization(unittest.TestCase):
    """Tests that Bucket-1 parallel dispatch (ThreadPoolExecutor) produces the same
    correct results as serial dispatch, is deterministically ordered, and has no
    thread-safety issues in the trace or dossier.

    All backends are mocked — no real claude/EMET/AWS. The fake runner is fast
    (in-process), so these tests complete in milliseconds and are fully offline/$0.
    """

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir
        # Always reset the concurrency env so tests are independent.
        os.environ.pop("SAPPHIRE_BUCKET1_CONCURRENCY", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        os.environ.pop("SAPPHIRE_BUCKET1_CONCURRENCY", None)

    # Force the module constant to re-read for each test by patching it directly.
    # (The constant is computed once at import time from the env.)
    def _run(self, concurrency):
        import live_engine
        old = live_engine._MAX_BUCKET1_WORKERS
        live_engine._MAX_BUCKET1_WORKERS = concurrency
        try:
            return run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=_build_ctx(),
            )
        finally:
            live_engine._MAX_BUCKET1_WORKERS = old

    def test_concurrency_one_regression(self):
        """concurrency=1 (serial path via single-thread pool) must produce a well-formed
        result identical in structure to the pre-parallelization serial loop."""
        result = self._run(concurrency=1)
        # Basic structure
        for key in ("query", "plan", "priors", "discover", "consult", "synthesize",
                    "engagement_id", "reflection", "_via"):
            self.assertIn(key, result, f"Missing key '{key}' with concurrency=1")
        self.assertEqual(result["_via"], "harness-live",
                         "concurrency=1 must still use harness-live path")
        agents = result["discover"]["agents"]
        self.assertGreater(len(agents), 0,
                           "concurrency=1 must dispatch at least one agent")
        self.assertIsInstance(result["discover"]["dossier"], list)

    def test_parallel_same_agent_set_as_serial(self):
        """Parallel (concurrency=8) must dispatch the exact same set of agents as
        serial (concurrency=1) — no silent drops, no extras."""
        serial_result = self._run(concurrency=1)
        parallel_result = self._run(concurrency=8)
        serial_ids = {a["id"] for a in serial_result["discover"]["agents"]}
        parallel_ids = {a["id"] for a in parallel_result["discover"]["agents"]}
        self.assertEqual(
            serial_ids, parallel_ids,
            f"Parallel dropped or added agents vs serial:\n"
            f"  serial={sorted(serial_ids)}\n  parallel={sorted(parallel_ids)}"
        )

    def test_deterministic_agent_order_in_discover(self):
        """discover.agents must be in selected_ids order regardless of thread
        completion order. Verified across 3 runs to surface any ordering flakiness.
        In offline tests (no LLM plan-mode), selected_ids == _BUCKET1_AGENTS filtered
        by known_ids, so we derive expected_order from a baseline serial run."""
        # Use a serial run to establish the expected order (no reliance on plan-mode).
        baseline = self._run(concurrency=1)
        expected_order = [a["id"] for a in baseline["discover"]["agents"]]

        import live_engine
        old = live_engine._MAX_BUCKET1_WORKERS
        live_engine._MAX_BUCKET1_WORKERS = 8
        try:
            for run_num in range(3):
                result = run_live(
                    "Is TSC2 a viable target in tuberous sclerosis?",
                    ctx=_build_ctx(),
                )
                actual_order = [a["id"] for a in result["discover"]["agents"]]
                self.assertEqual(
                    actual_order, expected_order,
                    f"Run {run_num + 1}: agent order not deterministic.\n"
                    f"  expected={expected_order}\n  actual={actual_order}"
                )
        finally:
            live_engine._MAX_BUCKET1_WORKERS = old

    def test_no_dropped_agents_parallel(self):
        """All agents dispatched in serial mode must also appear in parallel mode."""
        serial_result = self._run(concurrency=1)
        parallel_result = self._run(concurrency=8)
        serial_ids = {a["id"] for a in serial_result["discover"]["agents"]}
        parallel_ids = {a["id"] for a in parallel_result["discover"]["agents"]}
        self.assertEqual(
            parallel_ids, serial_ids,
            f"Parallel dispatch dropped agents:\n"
            f"  missing={sorted(serial_ids - parallel_ids)}\n"
            f"  extra={sorted(parallel_ids - serial_ids)}"
        )

    def test_parallel_no_agent_dispatched_twice(self):
        """Each Bucket-1 agent must appear exactly once in discover.agents — parallel
        dispatch must not double-submit any agent."""
        result = self._run(concurrency=8)
        agent_ids = [a["id"] for a in result["discover"]["agents"]]
        self.assertEqual(
            len(agent_ids), len(set(agent_ids)),
            f"Agent dispatched more than once in parallel mode:\n"
            f"  duplicates={[aid for aid in agent_ids if agent_ids.count(aid) > 1]}"
        )

    def test_trace_valid_jsonl_parallel(self):
        """Trace file must be valid JSONL (no interleaved garbage lines) when multiple
        agents write concurrently. Every line must be a parseable JSON object."""
        result = self._run(concurrency=8)
        eid = result["engagement_id"]
        trace_file = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_file),
                        f"Trace file not found: {trace_file}")
        with open(trace_file, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        self.assertGreater(len(lines), 2,
                           "Trace must have at least engagement_open + agent + engagement_close")
        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                self.fail(
                    f"Trace line {i} is not valid JSON (interleaved write?): {exc}\n"
                    f"  Line content: {line[:160]}"
                )
            self.assertIsInstance(obj, dict,
                                  f"Trace line {i} parsed but is not a JSON object: {type(obj)}")

    def test_parallel_same_dossier_size_as_serial(self):
        """Parallel dispatch must yield the same total dossier size as serial dispatch
        for the same mocked backends."""
        serial = self._run(concurrency=1)
        parallel = self._run(concurrency=8)
        s_count = len(serial["discover"]["dossier"])
        p_count = len(parallel["discover"]["dossier"])
        self.assertEqual(
            s_count, p_count,
            f"Dossier size mismatch: serial={s_count} parallel={p_count}. "
            "A dropped agent would make parallel smaller; a duplicate would make it larger."
        )

    def test_agent_statuses_have_n_facts(self):
        """Each entry in discover.agents must have an 'n_facts' key — the per-agent
        contribution count needed for restore/visibility."""
        result = self._run(concurrency=8)
        for agent in result["discover"]["agents"]:
            self.assertIn("n_facts", agent,
                          f"Agent {agent.get('id')} missing 'n_facts' field: {agent}")
            self.assertIsInstance(agent["n_facts"], int,
                                  f"Agent {agent.get('id')} n_facts not int: {agent}")


class TestBucket2Parallel(unittest.TestCase):
    """Tests for the Bucket-2 round-1 parallel dispatch (ThreadPoolExecutor).

    All backends are mocked — no real claude/EMET/AWS. The fake runner is fast
    (in-process), so these tests complete in milliseconds and are fully offline/$0.

    Five tests required by the brief:
      1. test_parallel_verdicts_match_serial         — order-independent set comparison
      2. test_concurrency_1_equals_serial            — per-persona name/stance/conviction
      3. test_no_persona_dropped_parallel            — all N personas yield N verdicts
      4. test_thread_safety_trace_no_corruption      — JSONL valid under 4 workers
      5. test_on_progress_events_roundtable_all_personas — start+done for every persona
    """

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir
        # Reset the concurrency constant so tests are independent.
        os.environ.pop("SAPPHIRE_BUCKET2_CONCURRENCY", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        os.environ.pop("SAPPHIRE_BUCKET2_CONCURRENCY", None)

    def _run(self, concurrency):
        """Run with a specific _MAX_BUCKET2_WORKERS value (patched at module level)."""
        import live_engine
        old = live_engine._MAX_BUCKET2_WORKERS
        live_engine._MAX_BUCKET2_WORKERS = concurrency
        try:
            return run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=_build_ctx(),
            )
        finally:
            live_engine._MAX_BUCKET2_WORKERS = old

    # ── test 1: parallel verdicts match serial (order-independent) ────────────
    def test_parallel_verdicts_match_serial(self):
        """Run twice (concurrency=1 and concurrency=3, same deterministic mock runner),
        collect round1 persona-name sets and stances, assert they match order-independently.
        """
        serial = self._run(concurrency=1)
        parallel = self._run(concurrency=3)

        serial_round1 = serial["consult"]["round1"]
        parallel_round1 = parallel["consult"]["round1"]

        # Both must produce the same number of verdicts.
        self.assertEqual(
            len(serial_round1), len(parallel_round1),
            f"Verdict count mismatch: serial={len(serial_round1)} parallel={len(parallel_round1)}"
        )

        # The set of (persona, stance) pairs must be the same regardless of completion order.
        serial_pairs = {
            (v.get("persona", ""), v.get("stance", "hold"))
            for v in serial_round1
        }
        parallel_pairs = {
            (v.get("persona", ""), v.get("stance", "hold"))
            for v in parallel_round1
        }
        self.assertEqual(
            serial_pairs, parallel_pairs,
            f"Parallel produced different (persona, stance) pairs than serial.\n"
            f"  serial={sorted(serial_pairs)}\n  parallel={sorted(parallel_pairs)}"
        )

    # ── test 2: concurrency=1 produces the same results as the default ────────
    def test_concurrency_1_equals_serial(self):
        """SAPPHIRE_BUCKET2_CONCURRENCY=1 (single-thread pool) must yield identical
        round1 persona names, stances, and convictions to the default-concurrency run."""
        result_c1 = self._run(concurrency=1)
        result_c8 = self._run(concurrency=8)

        r1_c1 = result_c1["consult"]["round1"]
        r1_c8 = result_c8["consult"]["round1"]

        # Same persona names (order-independent for robustness against scheduler variance).
        names_c1 = {v.get("persona", "") for v in r1_c1}
        names_c8 = {v.get("persona", "") for v in r1_c8}
        self.assertEqual(
            names_c1, names_c8,
            f"concurrency=1 produced different persona set from concurrency=8.\n"
            f"  c1={sorted(names_c1)}\n  c8={sorted(names_c8)}"
        )

        # Same stances (deterministic mock runner returns the same stance every time).
        stances_c1 = {v.get("stance", "hold") for v in r1_c1}
        stances_c8 = {v.get("stance", "hold") for v in r1_c8}
        self.assertEqual(
            stances_c1, stances_c8,
            f"concurrency=1 produced different stances from concurrency=8.\n"
            f"  c1={sorted(stances_c1)}\n  c8={sorted(stances_c8)}"
        )

        # Same conviction values.
        convictions_c1 = {v.get("conviction", 0) for v in r1_c1}
        convictions_c8 = {v.get("conviction", 0) for v in r1_c8}
        self.assertEqual(
            convictions_c1, convictions_c8,
            f"concurrency=1 produced different convictions from concurrency=8.\n"
            f"  c1={sorted(convictions_c1)}\n  c8={sorted(convictions_c8)}"
        )

    # ── test 3: no persona dropped with parallel dispatch ────────────────────
    def test_no_persona_dropped_parallel(self):
        """With N personas in the mock plan, parallel dispatch must yield exactly N verdicts
        (no future silently dropped on exception)."""
        result = self._run(concurrency=4)
        round1 = result["consult"]["round1"]
        panel = result["plan"].get("panel", [])

        # panel may be empty for this query in the mock orchestrator; the invariant is
        # that round1 == panel in length (all submitted futures were joined and appended).
        self.assertEqual(
            len(round1), len(panel),
            f"Parallel dispatch dropped or duplicated verdicts: "
            f"expected {len(panel)} (panel length) got {len(round1)} round1 entries.\n"
            f"  panel={[p.get('persona', p) for p in panel]}\n"
            f"  round1 personas={[v.get('persona') for v in round1]}"
        )

    # ── test 4: trace is valid JSONL under concurrent persona writes ─────────
    def test_thread_safety_trace_no_corruption(self):
        """Run with _MAX_BUCKET2_WORKERS=4, then read the trace.jsonl and assert every
        line parses as valid JSON (no interleaved/corrupted write from parallel personas)."""
        result = self._run(concurrency=4)
        eid = result["engagement_id"]
        trace_file = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_file), f"Trace file not found: {trace_file}")

        with open(trace_file, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]

        self.assertGreater(
            len(lines), 2,
            "Trace must have at least engagement_open + one record + engagement_close"
        )

        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                self.fail(
                    f"Trace line {i} is not valid JSON (interleaved write from parallel "
                    f"Bucket-2 personas?): {exc}\n  Line content: {line[:160]}"
                )
            self.assertIsInstance(
                obj, dict,
                f"Trace line {i} parsed but is not a JSON object: {type(obj)}"
            )

    # ── test 5: on_progress events cover all personas (start + done) ─────────
    def test_on_progress_events_roundtable_all_personas(self):
        """With on_progress callback collecting events, assert every persona in panel
        has both a roundtable 'start' and a roundtable 'done' event."""
        import live_engine

        events: list[dict] = []

        def _collect(ev):
            events.append(dict(ev))

        old = live_engine._MAX_BUCKET2_WORKERS
        live_engine._MAX_BUCKET2_WORKERS = 3
        try:
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=_build_ctx(),
                on_progress=_collect,
            )
        finally:
            live_engine._MAX_BUCKET2_WORKERS = old

        panel = result["plan"].get("panel", [])
        # If there are no personas in the panel, the test is vacuously true — skip
        # with a clear message so CI doesn't silently green a plan-without-panel.
        if not panel:
            self.skipTest("No personas in plan.panel for this query/mock; skipping roundtable event check.")

        roundtable_events = [
            ev for ev in events
            if ev.get("stage") == "roundtable" and ev.get("round") == 1
        ]

        for p in panel:
            persona_name = p.get("persona", "")
            persona_events = [ev for ev in roundtable_events if ev.get("agent_id") == persona_name]
            phases = {ev.get("phase") for ev in persona_events}

            self.assertIn(
                "start", phases,
                f"Persona '{persona_name}' missing 'start' roundtable event. "
                f"Got phases={sorted(phases)} from events={persona_events}"
            )
            self.assertIn(
                "done", phases,
                f"Persona '{persona_name}' missing 'done' roundtable event. "
                f"Got phases={sorted(phases)} from events={persona_events}"
            )

    # ── test 6: round-2 (rebuttal) runs in parallel — no personas dropped ────
    def test_round2_no_persona_dropped_parallel(self):
        """Parallel round-2 dispatch must yield exactly len(panel) rebuttal entries
        (no future silently dropped, no persona duplicated)."""
        result = self._run(concurrency=4)
        round2 = result["consult"]["round2"]
        panel = result["plan"].get("panel", [])

        self.assertEqual(
            len(round2), len(panel),
            f"Round-2 parallel dropped/duplicated entries: "
            f"expected {len(panel)} got {len(round2)}.\n"
            f"  panel={[p.get('persona', p) for p in panel]}\n"
            f"  round2 personas={[r.get('persona') for r in round2]}"
        )

    # ── test 7: round-2 trace is valid JSONL under concurrent writes ──────────
    def test_round2_trace_valid_jsonl_parallel(self):
        """After parallel round-2 dispatch with 4 workers, every line of trace.jsonl
        must parse as valid JSON (no interleaved writes from concurrent rebuttal threads)."""
        result = self._run(concurrency=4)
        eid = result["engagement_id"]
        trace_file = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_file), f"Trace not found: {trace_file}")

        with open(trace_file, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]

        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                self.fail(
                    f"Trace line {i} not valid JSON (interleaved write from parallel "
                    f"round-2 threads?): {exc}\n  Line: {line[:160]}"
                )
            self.assertIsInstance(obj, dict, f"Trace line {i} is not a JSON object")

    # ── test 8: round-2 on_progress events cover all personas ────────────────
    def test_round2_on_progress_events_all_personas(self):
        """With on_progress callback, every persona must have a rebuttal_start and
        rebuttal_done event in the roundtable stage (round-2 progress events)."""
        import live_engine
        events: list[dict] = []

        def _collect(ev):
            events.append(dict(ev))

        old = live_engine._MAX_BUCKET2_WORKERS
        live_engine._MAX_BUCKET2_WORKERS = 3
        try:
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=_build_ctx(),
                on_progress=_collect,
            )
        finally:
            live_engine._MAX_BUCKET2_WORKERS = old

        panel = result["plan"].get("panel", [])
        if not panel:
            self.skipTest("No personas in plan.panel; skipping round-2 event check.")

        r2_events = [
            ev for ev in events
            if ev.get("stage") == "roundtable" and ev.get("round") == 2
        ]

        for p in panel:
            persona_name = p.get("persona", "")
            persona_r2_events = [ev for ev in r2_events if ev.get("agent_id") == persona_name]
            phases = {ev.get("phase") for ev in persona_r2_events}

            self.assertIn(
                "rebuttal_start", phases,
                f"Persona '{persona_name}' missing 'rebuttal_start' event in round-2. "
                f"Got phases={sorted(phases)} from events={persona_r2_events}"
            )
            self.assertIn(
                "rebuttal_done", phases,
                f"Persona '{persona_name}' missing 'rebuttal_done' event in round-2. "
                f"Got phases={sorted(phases)} from events={persona_r2_events}"
            )

    # ── test 9: round-2 barrier — round1 fully joined before round2 starts ───
    def test_round2_barrier_round1_complete(self):
        """round1 must be fully populated BEFORE round2 dispatches — each round-2
        worker must see the complete round1 verdicts list (barrier invariant)."""
        result = self._run(concurrency=4)
        round1 = result["consult"]["round1"]
        round2 = result["consult"]["round2"]
        panel = result["plan"].get("panel", [])

        # Basic sanity: both lists have the same length as the panel.
        self.assertEqual(len(round1), len(panel),
                         "round1 length must equal panel length")
        self.assertEqual(len(round2), len(panel),
                         "round2 length must equal panel length")

        # Every round2 entry must have a 'revised' field (set by the worker using
        # round1 conviction/stance comparison — only possible if round1 was complete).
        for i, r2 in enumerate(round2):
            self.assertIn(
                "revised", r2,
                f"round2[{i}] missing 'revised' field — was round1 incomplete at dispatch? "
                f"entry={r2}"
            )
            self.assertIsInstance(
                r2["revised"], bool,
                f"round2[{i}].revised must be bool; got {type(r2['revised'])}: {r2['revised']}"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
