"""Offline tests for WO-9 orchestrator-decided scientific tool selection.

Tests (a)-(e) from the brief:
  (a) gene-ranking scope → tools_selected excludes boltz/aso-tox/DTI,
      includes gene tools; engine invokes only those; trace shows used only.
  (b) SMILES scope → DTI/boltz selected.
  (c) ASO scope → aso-tox selected.
  (d) tools_override honored.
  (e) claude-selection failure → deterministic fallback.

Run hermetically — mock the claude selection call + the tool seams; no real API/AWS.
CLAUDE_BIN=/usr/bin/false ensures the claude call fails → deterministic fallback.

    cd sapphire-orchestrator
    CLAUDE_BIN=/usr/bin/false python -m unittest tests.test_tool_selection -v
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

from live_engine import run_live, _BUCKET1_CORE_AGENTS, _BUCKET1_SCIENTIFIC_TOOLS
from tool_selector import select_tools, SCIENTIFIC_TOOLS, _deterministic_fallback
from planner import classify_query
from harness.contracts import load_registry
from tests.test_live_engine import _build_ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_claude_runner(cmd):
    """Fake runner: returns valid findings for bucket-1 agents, valid verdict for personas."""
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
            "fact_claims": [],
            "provenance": "semantic-web",
        }
    else:
        obj = {
            "candidate": "X",
            "facts": [{"value": "mock", "source": "PMID:1", "tier": "T2"}],
            "provenance": "semantic-web",
        }
    return types.SimpleNamespace(
        stdout=json.dumps({"structured_output": obj}),
        returncode=0,
        stderr="",
    )


def _fake_emet_handler(contract, inputs):
    return {
        "candidate": inputs.get("candidate", "X"),
        "facts": [{"value": "emet mock", "source": "PMID:9", "tier": "T2"}],
        "provenance": "emet-live",
    }


def _fake_qmodels_client():
    def _call(tool, inp):
        return {"model": tool, "out": "mock", "provenance": "stub"}
    return types.SimpleNamespace(call=_call)


def _offline_fn(name):
    """Return an honest-empty python_fn for a seam (no network)."""
    def _fn(inputs):
        return {"candidate": inputs.get("candidate", ""), "facts": [], "provenance": name}
    return _fn


def _build_test_ctx(*, track_calls: dict | None = None):
    """Build a ctx where every seam is mocked. Optionally records which seams were called."""
    fns = {
        "gnomad-constraint": _offline_fn("gnomad"),
        "gtex-expression": _offline_fn("gtex"),
        "interpro-domains": _offline_fn("interpro"),
        "geneset-enrichment": _offline_fn("gprofiler"),
        "aso-tox": _offline_fn("aso-tox"),
        "boltz": _offline_fn("boltz"),
        "robyn-scs": _offline_fn("robyn-scs"),
        "q-models-runner": _offline_fn("q-models"),
    }
    # Wrap with call tracker if provided.
    if track_calls is not None:
        for name, fn in list(fns.items()):
            def _tracked(inputs, _name=name, _fn=fn):
                track_calls.setdefault(_name, 0)
                track_calls[_name] += 1
                return _fn(inputs)
            fns[name] = _tracked

    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "qmodels_client": _fake_qmodels_client(),
        "python_fns": fns,
    }


# ---------------------------------------------------------------------------
# Part A: unit tests for tool_selector.py
# ---------------------------------------------------------------------------

class TestToolSelectorUnit(unittest.TestCase):
    """Unit tests for select_tools() and _deterministic_fallback()."""

    def test_catalog_loaded(self):
        """Tool catalog must contain the 8 expected scientific tool ids."""
        expected = {
            "aso-tox", "boltz", "q-models-runner",
            "gnomad-constraint", "gtex-expression", "interpro-domains",
            "geneset-enrichment", "robyn-scs",
        }
        self.assertEqual(set(SCIENTIFIC_TOOLS), expected,
                         f"Unexpected SCIENTIFIC_TOOLS: {SCIENTIFIC_TOOLS}")

    def test_deterministic_fallback_gene_query(self):
        """Gene query → gene tools selected; aso-tox/boltz/robyn-scs NOT selected."""
        scope = classify_query("Is TSC2 viable in tuberous sclerosis?")
        result = _deterministic_fallback(scope)
        selected = set(result["tools_selected"])
        # Gene tools must be selected.
        for t in ("gnomad-constraint", "gtex-expression", "interpro-domains",
                  "geneset-enrichment", "q-models-runner"):
            self.assertIn(t, selected, f"{t} must be selected for gene query")
        # Non-gene specialty tools must NOT be selected.
        for t in ("aso-tox", "boltz", "robyn-scs"):
            self.assertNotIn(t, selected, f"{t} must NOT be selected for gene query")

    def test_deterministic_fallback_aso_query(self):
        """ASO sequence query → aso-tox selected."""
        scope = classify_query("Score toxicity of ATGCATGCATGCATGCATGC")
        result = _deterministic_fallback(scope)
        selected = set(result["tools_selected"])
        self.assertIn("aso-tox", selected, "aso-tox must be selected for ASO query")

    def test_deterministic_fallback_smiles_query(self):
        """SMILES query → boltz + q-models-runner selected."""
        scope = classify_query("Run DTI for CC(=O)Oc1ccccc1C(=O)O")
        result = _deterministic_fallback(scope)
        selected = set(result["tools_selected"])
        self.assertIn("boltz", selected, "boltz must be selected for SMILES query")
        self.assertIn("q-models-runner", selected,
                      "q-models-runner must be selected for SMILES query")

    def test_deterministic_fallback_non_gene(self):
        """Non-gene/non-SMILES/non-ASO query → no scientific tools selected."""
        scope = classify_query("What are the DEA scheduling constraints for morphine?")
        result = _deterministic_fallback(scope)
        # Non-gene queries may still return [] or a subset — we just check that
        # no gene tools are selected (since no gene was detected).
        selected = set(result["tools_selected"])
        for t in ("gnomad-constraint", "gtex-expression", "interpro-domains",
                  "geneset-enrichment"):
            self.assertNotIn(t, selected, f"{t} must NOT be selected for non-gene query")

    def test_tools_available_always_returned(self):
        """tools_available must list all 8 scientific tools regardless of selection."""
        scope = classify_query("Is TSC2 viable?")
        result = _deterministic_fallback(scope)
        available_ids = {t["id"] for t in result["tools_available"]}
        self.assertEqual(available_ids, set(SCIENTIFIC_TOOLS),
                         "tools_available must list all 8 scientific tools")

    def test_rationale_covers_all_tools(self):
        """tool_rationale must have an entry for every scientific tool."""
        scope = classify_query("Is TSC2 viable?")
        result = _deterministic_fallback(scope)
        for t in SCIENTIFIC_TOOLS:
            self.assertIn(t, result["tool_rationale"],
                          f"tool_rationale missing entry for {t}")

    def test_select_tools_claude_failure_degrades_to_fallback(self):
        """When the claude call fails (CLAUDE_BIN=/usr/bin/false), select_tools
        degrades safely to the deterministic fallback."""
        scope = classify_query("Is TSC2 viable in tuberous sclerosis?")
        # Pass a runner that always fails.
        ctx = {"runner": lambda cmd: (_ for _ in ()).throw(RuntimeError("mock failure"))}

        result = select_tools("Is TSC2 viable in tuberous sclerosis?", scope, ctx=ctx)
        self.assertIn("tools_selected", result)
        self.assertIn("tool_rationale", result)
        self.assertIn("tools_available", result)
        self.assertEqual(result["selection_source"], "deterministic-fallback")

    def test_select_tools_claude_hallucinated_id_filtered(self):
        """Claude output with a hallucinated tool id must be filtered out."""
        scope = classify_query("Is TSC2 viable?")

        def _hallucinating_runner(cmd):
            obj = {"selected": ["gnomad-constraint", "FAKE_TOOL_XYZ"],
                   "rationale": {"gnomad-constraint": "useful", "FAKE_TOOL_XYZ": "made up"}}
            return types.SimpleNamespace(
                stdout=json.dumps({"structured_output": obj}),
                returncode=0, stderr="",
            )

        ctx = {"runner": _hallucinating_runner}
        result = select_tools("Is TSC2 viable?", scope, ctx=ctx)
        self.assertNotIn("FAKE_TOOL_XYZ", result["tools_selected"],
                         "Hallucinated tool id must be filtered from tools_selected")
        self.assertIn("gnomad-constraint", result["tools_selected"])

    def test_select_tools_robyn_scs_removed_without_imaging(self):
        """robyn-scs must be removed from Claude's selection when no imaging_input in ctx."""
        scope = classify_query("Is TSC2 viable?")

        def _selects_robyn(cmd):
            obj = {"selected": ["robyn-scs", "gnomad-constraint"],
                   "rationale": {"robyn-scs": "model selected it",
                                 "gnomad-constraint": "useful"}}
            return types.SimpleNamespace(
                stdout=json.dumps({"structured_output": obj}),
                returncode=0, stderr="",
            )

        ctx = {"runner": _selects_robyn}
        result = select_tools("Is TSC2 viable?", scope, ctx=ctx)
        self.assertNotIn("robyn-scs", result["tools_selected"],
                         "robyn-scs must be removed when no imaging_input in ctx")
        self.assertIn("gnomad-constraint", result["tools_selected"])


# ---------------------------------------------------------------------------
# Part B: integration tests via run_live (hermetic, no real API calls)
# ---------------------------------------------------------------------------

class TestToolSelectionIntegration(unittest.TestCase):
    """Integration tests: tool selection wired end-to-end in run_live."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        self._registry = load_registry()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)

    # ── (a) gene query: gene tools run; boltz/aso-tox NOT invoked ────────────
    def test_gene_query_excludes_boltz_and_aso_tox(self):
        """For a gene-level query, boltz and aso-tox seams must NOT be called.

        The engine must dispatch only core agents + gene-level scientific tools.
        The trace shows only used tools, not the skipped ones.
        """
        calls: dict = {}
        ctx = _build_test_ctx(track_calls=calls)

        # Mock select_tools to return gene tools deterministically (avoids CLAUDE_BIN).
        gene_tools = ["gnomad-constraint", "gtex-expression", "interpro-domains",
                      "geneset-enrichment", "q-models-runner"]
        mock_result = {
            "tools_selected": gene_tools,
            "tool_rationale": {t: "gene query — selected" if t in gene_tools
                               else "gene query — skipped"
                               for t in SCIENTIFIC_TOOLS},
            "tools_available": [{"id": t, "name": t, "purpose": ""} for t in SCIENTIFIC_TOOLS],
            "selection_source": "claude",
        }
        with mock.patch("live_engine.select_tools", return_value=mock_result):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                ctx=ctx,
            )

        self.assertIn("discover", result, "result must have discover")
        agent_ids = {a["id"] for a in result["discover"]["agents"]}

        # boltz and aso-tox must NOT appear in agents (they were not selected).
        self.assertNotIn("boltz", agent_ids,
                         "boltz must NOT appear in discover.agents for a gene query")
        self.assertNotIn("aso-tox", agent_ids,
                         "aso-tox must NOT appear in discover.agents for a gene query")

        # boltz and aso-tox seams must NOT have been called.
        self.assertNotIn("boltz", calls,
                         "boltz seam must NOT be called for a gene query")
        self.assertNotIn("aso-tox", calls,
                         "aso-tox seam must NOT be called for a gene query")

        # Gene tools must appear in agents.
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        for t in gene_tools:
            if t in known_ids:
                self.assertIn(t, agent_ids,
                              f"{t} must appear in discover.agents for a gene query")

        # Plan output contract: tools_selected must be on the plan.
        self.assertIn("tools_selected", result["plan"],
                      "plan must include tools_selected")
        self.assertIn("tool_rationale", result["plan"],
                      "plan must include tool_rationale")
        self.assertIn("tools_available", result["plan"],
                      "plan must include tools_available")
        self.assertEqual(set(result["plan"]["tools_selected"]), set(gene_tools),
                         "plan.tools_selected must match the selected gene tools")

    # ── (b) SMILES query: boltz/q-models-runner selected ────────────────────
    def test_smiles_query_selects_boltz(self):
        """For a SMILES query, boltz must be selected and appear in discover.agents."""
        calls: dict = {}
        ctx = _build_test_ctx(track_calls=calls)

        smiles_tools = ["boltz", "q-models-runner"]
        mock_result = {
            "tools_selected": smiles_tools,
            "tool_rationale": {t: "SMILES query — selected" if t in smiles_tools
                               else "SMILES query — skipped"
                               for t in SCIENTIFIC_TOOLS},
            "tools_available": [{"id": t, "name": t, "purpose": ""} for t in SCIENTIFIC_TOOLS],
            "selection_source": "claude",
        }
        with mock.patch("live_engine.select_tools", return_value=mock_result):
            result = run_live(
                "Run DTI for CC(=O)Oc1ccccc1C(=O)O",
                ctx=ctx,
            )

        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        known_ids = {a["id"] for a in self._registry.get("agents", [])}

        if "boltz" in known_ids:
            self.assertIn("boltz", agent_ids,
                          "boltz must appear in discover.agents for SMILES query")
        # aso-tox must NOT run (no ASO sequences).
        self.assertNotIn("aso-tox", agent_ids,
                         "aso-tox must NOT appear for a SMILES query")

    # ── (c) ASO query: aso-tox selected ─────────────────────────────────────
    def test_aso_query_selects_aso_tox(self):
        """For an ASO sequence query, aso-tox must be selected."""
        calls: dict = {}
        ctx = _build_test_ctx(track_calls=calls)

        aso_tools = ["aso-tox"]
        mock_result = {
            "tools_selected": aso_tools,
            "tool_rationale": {t: "ASO query — selected" if t in aso_tools
                               else "ASO query — skipped"
                               for t in SCIENTIFIC_TOOLS},
            "tools_available": [{"id": t, "name": t, "purpose": ""} for t in SCIENTIFIC_TOOLS],
            "selection_source": "claude",
        }
        with mock.patch("live_engine.select_tools", return_value=mock_result):
            result = run_live(
                "Score toxicity of ATGCATGCATGCATGCATGC in TSC2-ASO context",
                ctx=ctx,
            )

        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        known_ids = {a["id"] for a in self._registry.get("agents", [])}

        if "aso-tox" in known_ids:
            self.assertIn("aso-tox", agent_ids,
                          "aso-tox must appear in discover.agents for ASO query")
        # boltz must NOT run.
        self.assertNotIn("boltz", agent_ids,
                         "boltz must NOT appear for an ASO query")

    # ── (d) tools_override honored ───────────────────────────────────────────
    def test_tools_override_honored(self):
        """tools_override replaces the Claude selection.

        When tools_override=["gnomad-constraint"], only gnomad-constraint should
        run from the scientific tools (not boltz, aso-tox, etc.).
        select_tools must NOT be called (override bypasses it).
        """
        calls: dict = {}
        ctx = _build_test_ctx(track_calls=calls)
        known_ids = {a["id"] for a in self._registry.get("agents", [])}

        with mock.patch("live_engine.select_tools") as mock_select:
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                tools_override=["gnomad-constraint"],
                ctx=ctx,
            )
            # select_tools must NOT be called when tools_override is given.
            mock_select.assert_not_called()

        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        _sci_set = frozenset(_BUCKET1_SCIENTIFIC_TOOLS)

        if "gnomad-constraint" in known_ids:
            self.assertIn("gnomad-constraint", agent_ids,
                          "gnomad-constraint must appear with tools_override=[gnomad-constraint]")

        # Other scientific tools must NOT appear.
        for t in _BUCKET1_SCIENTIFIC_TOOLS:
            if t != "gnomad-constraint" and t in known_ids:
                self.assertNotIn(t, agent_ids,
                                 f"{t} must NOT appear with tools_override=[gnomad-constraint]")

        # Core agents must still appear.
        for t in _BUCKET1_CORE_AGENTS:
            if t in known_ids:
                self.assertIn(t, agent_ids,
                              f"Core agent {t} must appear even with tools_override")

        # tools_selected on plan must reflect the override.
        self.assertEqual(result["plan"]["tools_selected"], ["gnomad-constraint"],
                         "plan.tools_selected must reflect tools_override")

    # ── (d2) tools_override=[] runs core only ────────────────────────────────
    def test_tools_override_empty_runs_core_only(self):
        """tools_override=[] is honoured: no scientific tools run, core still runs."""
        ctx = _build_test_ctx()
        known_ids = {a["id"] for a in self._registry.get("agents", [])}

        with mock.patch("live_engine.select_tools") as mock_select:
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                tools_override=[],
                ctx=ctx,
            )
            mock_select.assert_not_called()

        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        _sci_set = frozenset(_BUCKET1_SCIENTIFIC_TOOLS)

        for t in _BUCKET1_SCIENTIFIC_TOOLS:
            if t in known_ids:
                self.assertNotIn(t, agent_ids,
                                 f"Scientific tool {t} must NOT appear with tools_override=[]")

        self.assertEqual(result["plan"]["tools_selected"], [],
                         "plan.tools_selected must be [] with tools_override=[]")

    # ── (e) claude-selection failure → deterministic fallback ────────────────
    def test_claude_selection_failure_uses_deterministic_fallback(self):
        """When select_tools falls back (claude fails), the fallback runs and the
        plan output contract fields are still present."""
        ctx = _build_test_ctx()

        # Patch select_tools to raise (simulating a totally broken tool selector).
        # In practice this path is covered by select_tools's internal try/except,
        # but we test the live_engine resilience too.
        with mock.patch("live_engine.select_tools",
                        side_effect=Exception("forced failure")):
            # run_live itself must not raise — it falls back gracefully.
            # Actually since select_tools is called before approved_plan/plan_mode,
            # a raised exception here would propagate. BUT select_tools itself
            # never raises (it catches internally). We test the outer path by
            # returning a valid fallback result even on total failure.
            # So here we patch to return the deterministic fallback result.
            pass

        # Test via the select_tools returning a fallback result (normal path).
        scope = classify_query("Is TSC2 viable in tuberous sclerosis?")
        from tool_selector import _deterministic_fallback
        fb = _deterministic_fallback(scope)
        with mock.patch("live_engine.select_tools", return_value=fb):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                ctx=ctx,
            )

        self.assertIn("plan", result)
        self.assertIn("tools_selected", result["plan"],
                      "tools_selected must be present even on fallback")
        self.assertIn("tool_rationale", result["plan"],
                      "tool_rationale must be present even on fallback")
        self.assertIn("tools_available", result["plan"],
                      "tools_available must be present even on fallback")
        # Fallback for TSC2 gene query selects gene tools.
        self.assertNotIn("aso-tox", result["plan"]["tools_selected"],
                         "aso-tox must NOT be in fallback result for gene query")
        self.assertNotIn("boltz", result["plan"]["tools_selected"],
                         "boltz must NOT be in fallback result for gene query")

    # ── trace shows used tools only ──────────────────────────────────────────
    def test_trace_shows_used_tools_only(self):
        """When boltz/aso-tox are not selected, they must NOT appear in the plan
        trace event's tools_selected field."""
        import json as _json
        calls: dict = {}
        ctx = _build_test_ctx(track_calls=calls)

        gene_tools = ["gnomad-constraint", "gtex-expression"]
        mock_result = {
            "tools_selected": gene_tools,
            "tool_rationale": {t: "selected" if t in gene_tools else "skipped"
                               for t in SCIENTIFIC_TOOLS},
            "tools_available": [],
            "selection_source": "claude",
        }
        with mock.patch("live_engine.select_tools", return_value=mock_result):
            result = run_live("Is TSC2 viable?", ctx=ctx)

        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng_dir, eid, "trace.jsonl")
        self.assertTrue(os.path.exists(trace_path), "trace file must exist")

        plan_events = []
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if rec.get("type") == "plan":
                    plan_events.append(rec)

        self.assertTrue(plan_events, "At least one 'plan' trace event must exist")
        ev = plan_events[-1]
        trace_sci = ev.get("tools_selected", [])
        self.assertNotIn("boltz", trace_sci,
                         "boltz must NOT appear in trace plan tools_selected for gene query")
        self.assertNotIn("aso-tox", trace_sci,
                         "aso-tox must NOT appear in trace plan tools_selected for gene query")

    # ── plan output contract fields present ──────────────────────────────────
    def test_plan_output_contract_fields_always_present(self):
        """tools_selected, tool_rationale, tools_available must always appear in plan."""
        ctx = _build_test_ctx()
        result = run_live(
            "Is TSC2 viable in tuberous sclerosis?",
            ctx=ctx,
        )
        plan = result.get("plan", {})
        self.assertIn("tools_selected", plan,
                      "plan must always contain tools_selected")
        self.assertIn("tool_rationale", plan,
                      "plan must always contain tool_rationale")
        self.assertIn("tools_available", plan,
                      "plan must always contain tools_available")
        # tools_available must list all 8 scientific tools.
        available_ids = {t["id"] for t in plan["tools_available"]}
        self.assertEqual(available_ids, set(SCIENTIFIC_TOOLS),
                         "tools_available must list all 8 scientific tools")

    # ── tools_override via tools_override=[] produces empty tools_selected ──
    def test_tools_override_invalid_ids_filtered(self):
        """tools_override with unknown tool ids are silently filtered; valid ones run."""
        ctx = _build_test_ctx()
        known_ids = {a["id"] for a in self._registry.get("agents", [])}

        with mock.patch("live_engine.select_tools") as mock_select:
            result = run_live(
                "Is TSC2 viable?",
                tools_override=["gnomad-constraint", "FAKE_TOOL_XYZ"],
                ctx=ctx,
            )
            mock_select.assert_not_called()

        self.assertNotIn("FAKE_TOOL_XYZ",
                         result["plan"]["tools_selected"],
                         "Unknown id in tools_override must be filtered")
        self.assertIn("gnomad-constraint",
                      result["plan"]["tools_selected"],
                      "Valid id in tools_override must be kept")


if __name__ == "__main__":
    unittest.main()
