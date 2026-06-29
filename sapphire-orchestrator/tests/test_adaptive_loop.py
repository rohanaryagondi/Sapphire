"""
tests/test_adaptive_loop.py — Tests for the adaptive convergence loop (WOs 2.1–2.5).

All external backends mocked ($0, offline).  Real moat is used when available
(moat-specific assertions skip when DB is absent).

Run from sapphire-orchestrator/:
    python -m unittest tests.test_adaptive_loop -v

IMPORTANT NOTE on gene-symbol regex:
  _GENE_RE = re.compile(r"\b[A-Z]{2,6}[0-9]{1,3}[A-Z]?[0-9]?\b")
  Only tokens WITH a digit anchor match: TSC1, TSC2, SCN2A, FAK1A.
  Pure-letter symbols (MTOR, RHEB, SNCA) do NOT match — tests must use
  digit-anchored symbols.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from live_engine import (
    run_live,
    extract_salient_entities,
    REDISPATCH_TARGETS,
    _MAX_ADAPTIVE_ROUNDS,
    _MAX_ADAPTIVE_DISPATCHES,
    _ADAPTIVE_SALIENCE_THRESHOLD,
)
import harness


# ---------------------------------------------------------------------------
# Shared mock helpers (mirrored from test_live_engine.py)
# ---------------------------------------------------------------------------

def _fake_claude_runner(cmd):
    schema_str = ""
    for i, tok in enumerate(cmd):
        if tok == "--json-schema" and i + 1 < len(cmd):
            schema_str = cmd[i + 1]
            break
    if '"stance"' in schema_str:
        obj = {
            "persona": "Mock Persona",
            "stance": "conditional",
            "conviction": 3,
            "rationale": "Mock rationale.",
            "fact_claims": [{"claim": "TSC2 loss activates mTOR", "cite": "mock"}],
            "provenance": "semantic-web",
        }
    else:
        obj = {
            "candidate": "X",
            "facts": [{"value": "mock fact about TSC1 gene", "source": "PMID:1", "tier": "T2"}],
            "provenance": "semantic-web",
        }
    return types.SimpleNamespace(
        stdout=json.dumps({"structured_output": obj}),
        returncode=0, stderr=""
    )


def _fake_emet_handler(contract, inputs):
    return {
        "candidate": inputs.get("candidate", "X"),
        "facts": [{"value": "emet mock", "source": "PMID:9", "tier": "T2"}],
        "provenance": "emet-live",
    }


def _build_ctx():
    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "python_fns": {
            "gnomad-constraint": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gnomad"},
            "gtex-expression":   lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gtex"},
            "interpro-domains":  lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "interpro"},
            "geneset-enrichment": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gprofiler"},
        },
    }


# ---------------------------------------------------------------------------
# WO 2.1 — extract_salient_entities unit tests
# ---------------------------------------------------------------------------

class TestExtractSalientEntities(unittest.TestCase):

    # ── (1) empty facts → [] ────────────────────────────────────────────────
    def test_empty_facts_returns_empty(self):
        result = extract_salient_entities([], already_covered=set())
        self.assertEqual(result, [])

    # ── (2) all entities already covered → [] ───────────────────────────────
    def test_all_covered_returns_empty(self):
        facts = [
            {"value": "TSC2 loss activates mTOR pathway", "tier": "T1", "_source_agent": "moat"},
            {"value": "TSC1 mutations found in patients", "tier": "T2", "_source_agent": "emet"},
        ]
        result = extract_salient_entities(facts, already_covered={"TSC2", "TSC1"})
        self.assertEqual(result, [])

    # ── (3) T1/T2 fact about new gene → salience ≥ threshold ────────────────
    # Use TSC1 (digit-anchored) instead of MTOR (pure-letter, won't match regex)
    def test_t1_fact_new_gene_reaches_threshold(self):
        facts = [{"value": "TSC1 partner gene haploinsufficiency", "tier": "T1", "_source_agent": "moat"}]
        result = extract_salient_entities(facts, already_covered=set())
        # TSC1: +1 (base) +1 (T1) = 2 ≥ threshold (2)
        self.assertTrue(any(e["entity"] == "TSC1" for e in result), result)
        tsc1_entry = next(e for e in result if e["entity"] == "TSC1")
        self.assertGreaterEqual(tsc1_entry["salience"], _ADAPTIVE_SALIENCE_THRESHOLD)

    # ── (4) T3 fact with no flag → below threshold (salience=1) ─────────────
    def test_t3_no_flag_below_threshold(self):
        facts = [{"value": "TSC1 pathway involvement", "tier": "T3", "_source_agent": "moat"}]
        result = extract_salient_entities(facts, already_covered=set())
        # TSC1: +1 (base) only = 1 < threshold (2)
        self.assertEqual(result, [])

    # ── (5) VETO flag → high salience ───────────────────────────────────────
    # SCN2A has digit anchor (S-C-N-2-A), fits the regex
    def test_veto_flag_high_salience(self):
        facts = [{"value": "SCN2A amplification VETO finding", "tier": "T2", "flag": "VETO", "_source_agent": "fda"}]
        result = extract_salient_entities(facts, already_covered=set())
        # SCN2A: +1 (base) +1 (T2) +2 (VETO) = 4
        self.assertTrue(any(e["entity"] == "SCN2A" for e in result), result)
        scn2a_entry = next(e for e in result if e["entity"] == "SCN2A")
        self.assertEqual(scn2a_entry["salience"], 4)

    # ── (6) DIVERGENCE flag → same high-salience bonus as VETO ──────────────
    def test_divergence_flag_bonus(self):
        facts = [{"value": "TSC1 DIVERGENCE from internal data", "tier": "T3", "flag": "DIVERGENCE", "_source_agent": "emet"}]
        result = extract_salient_entities(facts, already_covered=set())
        # TSC1: +1 (base) +2 (DIVERGENCE) = 3
        tsc1 = next((e for e in result if e["entity"] == "TSC1"), None)
        self.assertIsNotNone(tsc1, f"expected TSC1 in result; got {result}")
        self.assertEqual(tsc1["salience"], 3)

    # ── (7) cross-agent bonus: ≥ 2 agents → +2 bonus ───────────────────────
    def test_cross_agent_bonus(self):
        facts = [
            {"value": "TSC1 haploinsufficiency confirmed", "tier": "T1", "_source_agent": "moat"},
            {"value": "TSC1 protein truncated", "tier": "T1", "_source_agent": "emet"},
        ]
        result = extract_salient_entities(facts, already_covered=set())
        # TSC1: (1+1) + (1+1) + 2 (cross-agent bonus) = 6
        tsc1 = next((e for e in result if e["entity"] == "TSC1"), None)
        self.assertIsNotNone(tsc1)
        self.assertEqual(tsc1["salience"], 6)

    # ── (8) no cross-agent bonus when same agent ─────────────────────────────
    def test_no_cross_agent_bonus_same_agent(self):
        facts = [
            {"value": "TSC1 haploinsufficiency confirmed", "tier": "T1", "_source_agent": "moat"},
            {"value": "TSC1 protein truncated by deletion", "tier": "T1", "_source_agent": "moat"},
        ]
        result = extract_salient_entities(facts, already_covered=set())
        # TSC1: (1+1) + (1+1) = 4; NO +2 (same agent)
        tsc1 = next((e for e in result if e["entity"] == "TSC1"), None)
        self.assertIsNotNone(tsc1)
        self.assertEqual(tsc1["salience"], 4)

    # ── (9) fact with no gene token matching _GENE_RE → [] ──────────────────
    def test_fact_with_no_gene_token(self):
        # "pathway activated; see protocol" — no digit-anchored gene symbol
        facts = [{"value": "pathway activated; see protocol", "tier": "T1", "_source_agent": "moat"}]
        result = extract_salient_entities(facts, already_covered=set())
        self.assertEqual(result, [])

    # ── (10) source_agent field is the first agent that mentioned the entity ─
    def test_source_agent_is_first_mentioner(self):
        facts = [
            {"value": "SCN2A gene expressed in CNS neurons", "tier": "T2", "_source_agent": "agent-A"},
            {"value": "SCN2A pathway involvement", "tier": "T1", "_source_agent": "agent-B"},
        ]
        result = extract_salient_entities(facts, already_covered=set())
        scn2a = next((e for e in result if e["entity"] == "SCN2A"), None)
        self.assertIsNotNone(scn2a)
        self.assertEqual(scn2a["source_agent"], "agent-A")  # first mentioner

    # ── (11) sorted descending by salience ──────────────────────────────────
    def test_sorted_descending(self):
        facts = [
            # TSC2: +1+1+2 (T1+VETO) = 4
            {"value": "TSC2 pathway activated by mutation", "tier": "T1", "flag": "VETO", "_source_agent": "moat"},
            # TSC1: +1+1 = 2 (T1 only)
            {"value": "TSC1 expressed in neurons", "tier": "T1", "_source_agent": "emet"},
        ]
        result = extract_salient_entities(facts, already_covered=set())
        if len(result) >= 2:
            self.assertGreaterEqual(result[0]["salience"], result[1]["salience"])

    # ── (12) gene tokens in already_covered are excluded ────────────────────
    def test_covered_gene_excluded(self):
        facts = [
            {"value": "TSC2 mutation found in patient cohort", "tier": "T1", "_source_agent": "moat"},
            {"value": "SCN2A is a sodium channel gene", "tier": "T1", "_source_agent": "moat"},
        ]
        result = extract_salient_entities(facts, already_covered={"TSC2"})
        entities = {e["entity"] for e in result}
        self.assertNotIn("TSC2", entities)
        self.assertIn("SCN2A", entities)


# ---------------------------------------------------------------------------
# WO 2.2 — REDISPATCH_TARGETS contract
# ---------------------------------------------------------------------------

class TestRedispatchTargets(unittest.TestCase):

    def test_redispatch_targets_non_empty(self):
        self.assertTrue(len(REDISPATCH_TARGETS) > 0)

    def test_internal_science_lead_in_targets(self):
        self.assertIn("internal-science-lead", REDISPATCH_TARGETS)

    def test_emet_not_in_targets(self):
        # EMET is paid/slow/login-gated; excluded from v1.
        self.assertNotIn("emet-runner", REDISPATCH_TARGETS)

    def test_gnomad_in_targets(self):
        self.assertIn("gnomad-constraint", REDISPATCH_TARGETS)


# ---------------------------------------------------------------------------
# WO 2.3 — Convergence loop controller
# ---------------------------------------------------------------------------

class TestConvergenceLoop(unittest.TestCase):

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run_adaptive(self, query="Is TSC2 a viable target in tuberous sclerosis?", **kw):
        return run_live(query, ctx=_build_ctx(), adaptive=True, **kw)

    def _run_default(self, query="Is TSC2 a viable target in tuberous sclerosis?", **kw):
        return run_live(query, ctx=_build_ctx(), **kw)

    # ── (1) adaptive=False is the default — same top-level keys ─────────────
    def test_adaptive_false_default_same_keys(self):
        """run_live with no adaptive kwarg and adaptive=False must return same top-level keys."""
        result_default = self._run_default()
        result_explicit = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
            adaptive=False,
        )
        self.assertEqual(set(result_default.keys()), set(result_explicit.keys()))

    # ── (2) adaptive=False — _via is still "harness-live" ───────────────────
    def test_adaptive_false_via_unchanged(self):
        result = self._run_default()
        self.assertEqual(result["_via"], "harness-live")

    # ── (3) adaptive=True — _via is still "harness-live" (no extra suffix) ──
    def test_adaptive_true_via_unchanged(self):
        result = self._run_adaptive()
        self.assertEqual(result["_via"], "harness-live")

    # ── (4) adaptive=True — run completes without raising ───────────────────
    def test_adaptive_true_completes(self):
        try:
            result = self._run_adaptive()
        except Exception as e:
            self.fail(f"run_live(adaptive=True) raised: {e}")
        self.assertIn("discover", result)

    # ── (5) adaptive=True — result has all required top-level keys ──────────
    def test_adaptive_true_result_structure(self):
        result = self._run_adaptive()
        for key in ("query", "plan", "priors", "discover", "consult",
                    "synthesize", "engagement_id", "reflection", "_via"):
            self.assertIn(key, result, f"Missing key: {key}")

    # ── (6) adaptive=True — moat is re-queried for a surfaced gene ───────────
    def test_adaptive_moat_requeried_for_surfaced_gene(self):
        """
        Gate-5 proof (WO 2.5): when a Bucket-1 agent returns a fact mentioning a
        GENE not in the original query (digit-anchored symbol), and adaptive=True,
        the internal-science-lead (moat) must be re-dispatched for that entity.

        Setup:
          - Original query: TSC2 (so ents["genes"] = ["TSC2"]).
          - gnomad-constraint returns a T1 fact mentioning "TSC1" (a NEW gene, not
            in the original query; TSC1 matches _GENE_RE because it has digit anchor).
          - TSC1 salience: +1 (base) +1 (T1) = 2 >= threshold.
          - After round 1, extract_salient_entities surfaces TSC1.
          - The moat (internal-science-lead) must then be called with candidate=TSC1.
        """
        moat_calls = []

        def _moat_fn(inputs):
            candidate = inputs.get("candidate", "")
            moat_calls.append(candidate)
            return {
                "candidate": candidate,
                "facts": [
                    {"value": f"moat fact for {candidate}", "source": "moat", "tier": "T1"}
                ],
                "provenance": "moat-real",
            }

        # gnomad returns a T1 fact mentioning TSC1 (new gene, not in original query)
        def _gnomad_fn(inputs):
            cand = inputs.get("candidate", "")
            return {
                "candidate": cand,
                "facts": [
                    {"value": "TSC1 is the obligate partner gene; haploinsufficiency documented",
                     "source": "gnomAD-v4", "tier": "T1"}
                ],
                "provenance": "gnomad",
            }

        ctx = _build_ctx()
        ctx["python_fns"]["gnomad-constraint"] = _gnomad_fn
        ctx["python_fns"]["internal-science-lead"] = _moat_fn

        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=ctx,
            adaptive=True,
        )

        dossier = result["discover"]["dossier"]

        # (a) The moat must have been called at least once for the original TSC2 query.
        self.assertIn("TSC2", moat_calls,
                      f"Expected moat called for TSC2; calls: {moat_calls}")

        # (b) Because gnomad returned a T1 fact mentioning TSC1 (salience >= 2),
        #     the moat must have been re-queried for TSC1.
        self.assertIn("TSC1", moat_calls,
                      f"Expected moat re-queried for TSC1 (surfaced gene); calls: {moat_calls}")

        # (c) The dossier must contain the moat fact for TSC1 (new fact landed).
        moat_tsc1_facts = [f for f in dossier
                           if "TSC1" in f.get("value", "") and f.get("provenance") == "moat-real"]
        self.assertTrue(
            len(moat_tsc1_facts) >= 1,
            f"Expected >=1 moat-real fact for TSC1 in dossier; dossier = {[(f.get('value','')[:60], f.get('provenance')) for f in dossier]}"
        )

    # ── (7) pathological many-genes input — must terminate ──────────────────
    def test_adaptive_terminates_on_many_new_genes(self):
        """
        A Bucket-1 agent that surfaces many new genes on every call must still
        terminate due to the dispatch budget cap (_MAX_ADAPTIVE_DISPATCHES=6).

        We mock internal-science-lead to always return facts mentioning new digit-
        anchored gene names: FAK1A, FAK2A, FAK3A etc. After budget=6 dispatches,
        the loop MUST stop.
        """
        call_counts: dict[str, int] = {"n": 0}
        # Gene names with digit anchors so they match _GENE_RE
        _gene_names = ["FAK1A", "FAK2A", "FAK3A", "FAK4A", "FAK5A", "FAK6A", "FAK7A", "FAK8A"]

        def _explosive_moat(inputs):
            call_counts["n"] += 1
            # Return facts mentioning new gene names each call — always 3 new genes.
            idx = call_counts["n"]
            genes_mentioned = _gene_names[idx % len(_gene_names):idx % len(_gene_names) + 3]
            val = "Pathway involves: " + " and ".join(genes_mentioned)
            return {
                "candidate": inputs.get("candidate", ""),
                "facts": [{"value": val, "source": "moat", "tier": "T1"}],
                "provenance": "moat-real",
            }

        ctx = _build_ctx()
        ctx["python_fns"]["internal-science-lead"] = _explosive_moat

        try:
            result = run_live(
                "Is TSC2 a viable target in tuberous sclerosis?",
                ctx=ctx,
                adaptive=True,
            )
        except Exception as e:
            self.fail(f"adaptive loop raised instead of terminating: {e}")

        # The loop must terminate; total moat calls <= 1 (initial) + _MAX_ADAPTIVE_DISPATCHES.
        # Each redispatch of internal-science-lead counts as 1 dispatch.
        self.assertLessEqual(
            call_counts["n"],
            1 + _MAX_ADAPTIVE_DISPATCHES,
            f"Moat called {call_counts['n']} times — budget cap not respected"
        )

    # ── (8) visited pair never dispatched twice ──────────────────────────────
    def test_adaptive_visited_pair_not_dispatched_twice(self):
        """
        The (entity, agent_id) visited set must prevent the same pair being
        dispatched more than once, even when multiple convergence rounds run.
        """
        call_log: list[tuple] = []

        def _tracking_moat(inputs):
            candidate = inputs.get("candidate", "")
            call_log.append(("internal-science-lead", candidate))
            return {
                "candidate": candidate,
                "facts": [{"value": f"TSC1 is related to {candidate}", "source": "moat", "tier": "T1"}],
                "provenance": "moat-real",
            }

        ctx = _build_ctx()
        ctx["python_fns"]["internal-science-lead"] = _tracking_moat

        run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=ctx,
            adaptive=True,
        )

        # For any (agent_id, entity) pair, it must appear AT MOST ONCE.
        seen_pairs: set[tuple] = set()
        for pair in call_log:
            self.assertNotIn(
                pair, seen_pairs,
                f"(entity={pair[1]}, agent={pair[0]}) dispatched more than once"
            )
            seen_pairs.add(pair)

    # ── (9) adaptive=False — no extra keys in result ─────────────────────────
    def test_adaptive_false_no_extra_top_level_keys(self):
        """run_live(adaptive=False) must not add any top-level keys beyond what
        the non-adaptive path produces."""
        expected_keys = {
            "query", "plan", "priors", "discover", "consult",
            "synthesize", "engagement_id", "reflection", "_via", "plan_source",
        }
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
            adaptive=False,
        )
        unexpected = set(result.keys()) - expected_keys
        self.assertEqual(unexpected, set(), f"Unexpected top-level keys: {unexpected}")


# ---------------------------------------------------------------------------
# WO 2.4 — Trace events
# ---------------------------------------------------------------------------

class TestRedispatchTraceEvents(unittest.TestCase):

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_redispatch_trace_events_written(self):
        """
        When adaptive=True and a new entity is surfaced, the trace.jsonl must
        contain at least one event with type=="redispatch" carrying the required
        fields: round, trigger_entity, source_agent, target_agents, reason.
        """
        def _gnomad_fn(inputs):
            return {
                "candidate": inputs.get("candidate", ""),
                "facts": [
                    {"value": "TSC1 haploinsufficiency documented in gnomAD constraint data",
                     "source": "gnomAD-v4", "tier": "T1"}
                ],
                "provenance": "gnomad",
            }

        ctx = _build_ctx()
        ctx["python_fns"]["gnomad-constraint"] = _gnomad_fn

        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=ctx,
            adaptive=True,
        )

        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_path), "trace file not found")

        redispatch_events = []
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        row = json.loads(line)
                        if row.get("type") == "redispatch":
                            redispatch_events.append(row)
                    except json.JSONDecodeError:
                        pass

        self.assertTrue(
            len(redispatch_events) >= 1,
            f"Expected >=1 redispatch trace event; found {len(redispatch_events)}"
        )
        ev = redispatch_events[0]
        for field in ("round", "trigger_entity", "source_agent", "target_agents", "reason"):
            self.assertIn(field, ev, f"redispatch event missing field '{field}': {ev}")

    def test_progress_events_redispatch_stage(self):
        """
        on_progress callbacks must emit events with stage=="redispatch" when
        adaptive=True and a new entity is surfaced.
        """
        def _gnomad_fn(inputs):
            return {
                "candidate": inputs.get("candidate", ""),
                "facts": [
                    {"value": "TSC1 referenced in gnomAD constraint data for tuberous sclerosis",
                     "source": "gnomAD-v4", "tier": "T1"}
                ],
                "provenance": "gnomad",
            }

        ctx = _build_ctx()
        ctx["python_fns"]["gnomad-constraint"] = _gnomad_fn

        progress_events = []
        run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=ctx,
            adaptive=True,
            on_progress=progress_events.append,
        )

        redispatch_stages = [e for e in progress_events if e.get("stage") == "redispatch"]
        self.assertTrue(
            len(redispatch_stages) >= 1,
            f"Expected >=1 progress event with stage=='redispatch'; "
            f"got stages: {[e.get('stage') for e in progress_events]}"
        )
        # Each redispatch progress event must carry phase (start or done), entity, target_agent.
        for ev in redispatch_stages:
            self.assertIn("phase", ev)
            self.assertIn(ev["phase"], ("start", "done"))
            self.assertIn("entity", ev)
            self.assertIn("target_agent", ev)


# ---------------------------------------------------------------------------
# WO 2.5 — Gate-5 regression (adaptive=False byte-for-byte proof)
# ---------------------------------------------------------------------------

class TestAdaptiveRegression(unittest.TestCase):

    def setUp(self):
        self._eng_dir_a = tempfile.mkdtemp()
        self._eng_dir_b = tempfile.mkdtemp()
        self._mem_dir_a = tempfile.mkdtemp()
        self._mem_dir_b = tempfile.mkdtemp()

    def test_adaptive_false_discover_dossier_identical_to_no_adaptive(self):
        """
        run_live(adaptive=False) must produce the same discover.dossier as
        run_live() (no adaptive param) with the same mocked backends.

        Moat is mocked to a fixed response so the comparison is deterministic.
        Use a suffix " A" on the query to generate the same eid for both runs —
        each run uses its own SAPPHIRE_ENGAGEMENTS_DIR.
        """
        QUERY = "Is TSC2 a viable target in tuberous sclerosis? A"
        MOAT_FACT = {"value": "TSC2 mutation causes mTOR hyperactivation", "source": "moat", "tier": "T1"}

        def _fixed_moat(inputs):
            return {"candidate": inputs.get("candidate", ""), "facts": [MOAT_FACT], "provenance": "moat-real"}

        def _build_fixed_ctx():
            ctx = _build_ctx()
            ctx["python_fns"]["internal-science-lead"] = _fixed_moat
            return ctx

        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir_a
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir_a
        result_no_adaptive = run_live(QUERY, ctx=_build_fixed_ctx())

        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir_b
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir_b
        result_adaptive_false = run_live(QUERY, ctx=_build_fixed_ctx(), adaptive=False)

        # Discover dossier must be identical.
        self.assertEqual(
            result_no_adaptive["discover"]["dossier"],
            result_adaptive_false["discover"]["dossier"],
            "discover.dossier differs between adaptive=False and no-adaptive-param runs"
        )
        # _via must be the same.
        self.assertEqual(result_no_adaptive["_via"], result_adaptive_false["_via"])
        # synthesize must be the same (recommendation/confidence are derived from same dossier).
        self.assertEqual(
            result_no_adaptive["synthesize"],
            result_adaptive_false["synthesize"],
            "synthesize differs between adaptive=False and no-adaptive-param runs"
        )
        # plan_source must be the same (both use deterministic plan).
        self.assertEqual(
            result_no_adaptive.get("plan_source"),
            result_adaptive_false.get("plan_source"),
            "plan_source differs between adaptive=False and no-adaptive-param runs"
        )

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)


if __name__ == "__main__":
    unittest.main()
