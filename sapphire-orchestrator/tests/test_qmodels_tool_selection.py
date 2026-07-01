"""
tests/test_qmodels_tool_selection.py — hermetic tests for:

1. dispatch_qmodels records tool_id + input for a gene query (WO-8 q-models-runner task)
2. The per-agent `detail` is present in the run result and is public-safe (no _ keys)
3. scoped_chat.answer_scoped accepts a fuller `detail` context

All offline ($0); no real claude/EMET/AWS calls.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_qmodels_tool_selection -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)


# ── helpers ──────────────────────────────────────────────────────────────────

def _fake_runner(cmd):
    """Offline claude runner — returns a minimal valid findings dict."""
    schema_str = ""
    for i, tok in enumerate(cmd):
        if tok == "--json-schema" and i + 1 < len(cmd):
            schema_str = cmd[i + 1]
            break
    if '"stance"' in schema_str:
        obj = {
            "persona": "Mock",
            "stance": "conditional",
            "conviction": 3,
            "rationale": "Mock.",
            "fact_claims": [],
            "provenance": "semantic-web",
        }
    else:
        obj = {
            "candidate": "TSC2",
            "facts": [{"value": "mock fact", "source": "PMID:1", "tier": "T2"}],
            "provenance": "semantic-web",
        }
    return types.SimpleNamespace(stdout=json.dumps({"structured_output": obj}), returncode=0, stderr="")


def _fake_emet(contract, inputs):
    return {
        "candidate": inputs.get("candidate", ""),
        "facts": [{"value": "emet mock", "source": "PMID:9", "tier": "T2"}],
        "provenance": "emet-live",
    }


class _MockQModelsClient:
    """Mock QModelsClient: records the tool_id + payload it was called with."""
    def __init__(self):
        self.calls = []
        # Simulate a registry with a few tools.
        self._tools_list = [
            {"id": "kg_hypothesis", "label": "KG / Hypothesis Generation", "status": "live", "tier": "endpoint"},
            {"id": "variant_effect", "label": "Variant Effect (Channelopathy)", "status": "live", "tier": "endpoint"},
            {"id": "dti", "label": "DTI / Binder Triage", "status": "live-local", "tier": "local-cpu"},
        ]

    def tools(self):
        return self._tools_list

    def call(self, tool_id, payload):
        self.calls.append({"tool_id": tool_id, "payload": payload})
        # Return a stub-unavailable result so the caller wraps it honestly.
        return {
            "ok": False,
            "tool_id": tool_id,
            "provenance": "stub",
            "model": "KG / Hypothesis Generation",
            "note": "stub for testing",
            "out": f"(stub — {tool_id} selected)",
        }


def _build_ctx(qmodels_client=None):
    return {
        "runner": _fake_runner,
        "emet_handler": _fake_emet,
        "qmodels_client": qmodels_client or _MockQModelsClient(),
        "python_fns": {
            "internal-science-lead": lambda inp: {
                "candidate": inp.get("candidate", ""),
                "facts": [],
                "provenance": "moat-real",
            },
            "aso-tox": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "aso-tox"},
            "gnomad-constraint": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gnomad"},
            "gtex-expression": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gtex"},
            "interpro-domains": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "interpro"},
            "geneset-enrichment": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "gprofiler"},
            "boltz": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "boltz"},
            "robyn-scs": lambda inp: {"candidate": inp.get("candidate", ""), "facts": [], "provenance": "robyn-scs"},
        },
    }


# ── Test 1: _select_qmodels_tool heuristic ────────────────────────────────────

class TestSelectQmodelsTool(unittest.TestCase):
    """Unit-test the deterministic tool-selection heuristic."""

    def setUp(self):
        from harness.dispatch import _select_qmodels_tool
        self._select = _select_qmodels_tool
        self._registry = [
            {"id": "kg_hypothesis", "label": "KG / Hypothesis Generation"},
            {"id": "variant_effect", "label": "Variant Effect (Channelopathy)"},
            {"id": "dti", "label": "DTI / Binder Triage"},
        ]

    def test_gene_maps_to_kg_hypothesis(self):
        tid, label, inp = self._select({"candidate": "TSC2", "disease": "tuberous sclerosis"}, self._registry)
        self.assertEqual(tid, "kg_hypothesis")
        self.assertEqual(inp, "TSC2")
        self.assertIn("KG", label)

    def test_smiles_maps_to_dti(self):
        tid, label, inp = self._select({"smiles": "CC(=O)O", "candidate": "TSC2"}, self._registry)
        self.assertEqual(tid, "dti")
        self.assertEqual(inp, "CC(=O)O")
        self.assertIn("DTI", label)

    def test_gene_plus_variant_maps_to_variant_effect(self):
        tid, label, inp = self._select({"candidate": "SCN2A", "variant": "p.Arg853Gln"}, self._registry)
        self.assertEqual(tid, "variant_effect")
        self.assertIn("SCN2A", inp)
        self.assertIn("Variant", label)

    def test_empty_inputs_fallback(self):
        tid, label, inp = self._select({}, self._registry)
        self.assertEqual(tid, "kg_hypothesis")

    def test_label_fallback_when_no_registry(self):
        tid, label, inp = self._select({"candidate": "TSC2"}, None)
        # Without registry, label falls back to the tool_id string
        self.assertEqual(tid, "kg_hypothesis")
        self.assertEqual(label, "kg_hypothesis")


# ── Test 2: dispatch_qmodels records tool_id + input ─────────────────────────

class TestDispatchQmodelsMeta(unittest.TestCase):
    """dispatch_qmodels must stamp _qmodels_tool_id, _qmodels_tool_label, _qmodels_input
    on its return value, and the harness must promote these into res.meta."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_dispatch_qmodels_stamps_tool_meta(self):
        """dispatch_qmodels should stamp _qmodels_tool_id and _qmodels_input on the output."""
        from harness.dispatch import dispatch_qmodels
        from harness.contracts import resolve, load_registry
        registry = load_registry()
        contract = resolve("q-models-runner", registry)
        mock_client = _MockQModelsClient()
        inputs = {"candidate": "TSC2", "disease": "tuberous sclerosis", "query": "Is TSC2 a viable target?"}
        out = dispatch_qmodels(contract, inputs, client=mock_client)
        self.assertIn("_qmodels_tool_id", out, "dispatch_qmodels must stamp _qmodels_tool_id")
        self.assertIn("_qmodels_tool_label", out, "dispatch_qmodels must stamp _qmodels_tool_label")
        self.assertIn("_qmodels_input", out, "dispatch_qmodels must stamp _qmodels_input")
        # For a gene query (no SMILES, no variant), expect kg_hypothesis
        self.assertEqual(out["_qmodels_tool_id"], "kg_hypothesis")
        # The input used should be the gene symbol
        self.assertEqual(out["_qmodels_input"], "TSC2")
        # The fact must exist (even if stub/simulated)
        self.assertIn("facts", out)
        self.assertTrue(len(out["facts"]) > 0, "must produce at least one fact (honest stub)")

    def test_harness_promotes_qmodels_meta_into_res_meta(self):
        """harness.run for q-models-runner must put qmodels_tool_id + qmodels_input in res.meta."""
        import harness
        from harness.contracts import load_registry
        registry = load_registry()
        mock_client = _MockQModelsClient()
        ctx = {"qmodels_client": mock_client}
        res = harness.run(
            "q-models-runner",
            {"candidate": "TSC2", "disease": "tuberous sclerosis", "query": "Is TSC2 a viable target?"},
            engagement_id="test_qmodels_meta",
            ctx=ctx,
            registry=registry,
        )
        self.assertTrue(res.ok, f"harness.run should succeed; got error: {res.error}")
        self.assertIsNotNone(res.meta, "res.meta must be set")
        self.assertIn("qmodels_tool_id", res.meta, "res.meta must carry qmodels_tool_id")
        self.assertIn("qmodels_input", res.meta, "res.meta must carry qmodels_input")
        # model in meta should be the specific tool label, not the generic fallback
        self.assertNotEqual(res.meta.get("model"), "Q-Models launchpad",
                            "model should be the specific tool label, not the generic fallback")

    def test_fact_is_honest_when_tool_unavailable(self):
        """When tool is unavailable/stub, the fact value must say 'simulated / not called'."""
        from harness.dispatch import dispatch_qmodels
        from harness.contracts import resolve, load_registry
        registry = load_registry()
        contract = resolve("q-models-runner", registry)
        mock_client = _MockQModelsClient()
        inputs = {"candidate": "TSC2", "disease": "tuberous sclerosis"}
        out = dispatch_qmodels(contract, inputs, client=mock_client)
        fact_value = out["facts"][0]["value"]
        # Must explicitly say the tool was not called (honesty requirement)
        self.assertIn("simulated / not called", fact_value,
                      f"Fact must be honest about not calling the tool; got: {fact_value!r}")
        # Must mention the selected tool (by label or id)
        self.assertTrue(
            "KG" in fact_value or "kg_hypothesis" in fact_value or "Hypothesis" in fact_value,
            f"Fact must mention the selected tool; got: {fact_value!r}",
        )


# ── Test 3: per-agent detail in the run result ────────────────────────────────

class TestPerAgentDetail(unittest.TestCase):
    """The run result's discover.agents[] must include a `detail` field (public-safe)."""

    def setUp(self):
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run(self):
        from live_engine import run_live
        return run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=_build_ctx(),
        )

    def test_agent_status_has_detail_field(self):
        """Every agent status entry must have a 'detail' key (None is allowed for abstained)."""
        result = self._run()
        agents = result["discover"]["agents"]
        self.assertTrue(len(agents) > 0, "must have at least one agent status entry")
        for agent in agents:
            self.assertIn("detail", agent,
                          f"agent {agent.get('id')} missing 'detail' key")

    def test_detail_is_public_safe_no_internal_keys(self):
        """detail dict must not contain any key starting with '_' (internal keys are stripped)."""
        result = self._run()
        for agent in result["discover"]["agents"]:
            detail = agent.get("detail")
            if detail is None:
                continue  # abstained agent — ok
            for key in detail:
                self.assertFalse(key.startswith("_"),
                                 f"detail for {agent.get('id')} has internal key {key!r}")

    def test_qmodels_runner_has_specific_model_and_query(self):
        """q-models-runner's agent status must show a specific tool label (not generic) and input."""
        result = self._run()
        agents = result["discover"]["agents"]
        qmodels_agent = next((a for a in agents if a["id"] == "q-models-runner"), None)
        if qmodels_agent is None:
            self.skipTest("q-models-runner not in registry or not dispatched")
        # model should be the specific tool label
        self.assertIsNotNone(qmodels_agent.get("model"), "model must be set for q-models-runner")
        self.assertNotEqual(qmodels_agent.get("model"), "Q-Models launchpad",
                            "model should be specific tool label (e.g. KG / Hypothesis Generation)")
        # agent_query should be the gene symbol (or SMILES), not the full original query
        aq = qmodels_agent.get("agent_query", "")
        self.assertTrue(
            aq == "TSC2" or aq.startswith("TSC2"),
            f"agent_query should be the gene symbol 'TSC2'; got {aq!r}",
        )


# ── Test 4: scoped_chat accepts detail ────────────────────────────────────────

class TestScopedChatDetail(unittest.TestCase):
    """answer_scoped must accept and include a `detail` dict in the prompt."""

    def test_answer_scoped_passes_detail_to_prompt(self):
        """When detail is provided, the prompt sent to claude should contain the detail content."""
        from scoped_chat import answer_scoped
        captured = []

        def _runner(cmd):
            captured.append(" ".join(cmd))
            return types.SimpleNamespace(stdout="mocked answer", returncode=0, stderr="")

        facts = [{"value": "TSC2 suppresses mTORC1.", "source": "PMID:1", "tier": "T2", "provenance": "emet-live"}]
        detail = {"candidate": "TSC2", "provenance": "qmodels", "tool_label": "KG / Hypothesis Generation"}
        answer_scoped("What tool was used?", facts, runner=_runner, detail=detail)

        self.assertTrue(len(captured) > 0, "runner must be called")
        prompt_arg = captured[0]
        # The prompt is passed as a single CLI argument; check the runner was called
        # (the actual prompt is inside the cmd list, not in the joined string trivially).
        # Instead verify via the cmd list that the runner received.

    def test_answer_scoped_detail_content_in_cmd(self):
        """The command list passed to runner must contain detail content when detail provided."""
        from scoped_chat import answer_scoped
        captured_cmd = []

        def _runner(cmd):
            captured_cmd.extend(cmd)
            return types.SimpleNamespace(stdout="mocked answer", returncode=0, stderr="")

        facts = [{"value": "TSC2 fact.", "source": "src", "tier": "T2", "provenance": "emet-live"}]
        detail = {"tool_label": "KG / Hypothesis Generation", "provenance": "stub"}
        answer_scoped("What was selected?", facts, runner=_runner, detail=detail)

        full_prompt = " ".join(captured_cmd)
        self.assertIn("KG / Hypothesis Generation", full_prompt,
                      "detail content must appear in the prompt passed to the model")

    def test_answer_scoped_strips_internal_keys_from_detail(self):
        """Internal keys (starting with _) in detail must be stripped before use in prompt."""
        from scoped_chat import answer_scoped
        captured_cmd = []

        def _runner(cmd):
            captured_cmd.extend(cmd)
            return types.SimpleNamespace(stdout="answer", returncode=0, stderr="")

        facts = [{"value": "fact", "source": "src", "tier": "T2", "provenance": "p"}]
        detail = {
            "_internal_secret": "NEVER_SURFACE",
            "public_tool": "ESM-2",
        }
        answer_scoped("question", facts, runner=_runner, detail=detail)

        full_prompt = " ".join(captured_cmd)
        self.assertNotIn("NEVER_SURFACE", full_prompt,
                         "internal detail keys must NOT appear in the prompt")
        self.assertIn("ESM-2", full_prompt,
                      "public detail keys must appear in the prompt")

    def test_answer_scoped_no_detail_backward_compat(self):
        """answer_scoped with no detail arg must work as before (backward compat)."""
        from scoped_chat import answer_scoped

        def _runner(cmd):
            return types.SimpleNamespace(stdout="compat answer", returncode=0, stderr="")

        facts = [{"value": "TSC2 fact.", "source": "PMID:1", "tier": "T2", "provenance": "emet"}]
        result = answer_scoped("question", facts, runner=_runner)
        self.assertEqual(result, "compat answer")

    def test_answer_scoped_empty_facts_no_detail(self):
        """No evidence + no detail → returns the NO_EVIDENCE sentinel."""
        from scoped_chat import answer_scoped, _NO_EVIDENCE
        result = answer_scoped("question", [])
        self.assertEqual(result, _NO_EVIDENCE)


if __name__ == "__main__":
    unittest.main()
