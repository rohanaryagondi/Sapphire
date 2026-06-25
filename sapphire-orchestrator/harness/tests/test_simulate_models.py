"""SAPPHIRE_SIMULATE_MODELS — labeled simulated claude-subagent reasoning (real EMET/moat/seams
stay real). Covers the dispatch seam, schema-validity, and the provenance='simulated' stamp."""
import os
import unittest

from harness import dispatch as D
from harness import guardrails as G
from harness.contracts import load_registry, resolve
from contracts.jsonschema_min import validate as schema_errors

MARK = "🧪 simulated"


class _SimEnv(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)
        if self._prev is not None:
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = self._prev


class TestSimulateLever(_SimEnv):
    def test_off_by_default(self):
        self.assertFalse(D._simulate_models_on())

    def test_truthy_values_on(self):
        for v in ("1", "true", "yes", "on"):
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = v
            self.assertTrue(D._simulate_models_on(), v)

    def test_falsey_values_off(self):
        for v in ("", "0", "false", "False"):
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = v
            self.assertFalse(D._simulate_models_on(), v)


class TestSimulatedOutputsSchemaValid(_SimEnv):
    def setUp(self):
        super().setUp()
        self.reg = load_registry()

    def test_persona_shape_valid_and_labeled(self):
        cp = resolve("company-partner", self.reg)
        out = D._simulate_claude(cp, {"persona": "Denali CSO", "lens": "translational"})
        self.assertEqual(schema_errors(out, cp.output_schema), [])
        self.assertEqual(out["provenance"], "simulated")
        self.assertIn(MARK, out["rationale"])           # unmistakably labeled

    def test_fact_agent_shape_valid_and_labeled(self):
        fa = resolve("post-market-safety", self.reg)
        out = D._simulate_claude(fa, {"candidate": "TSC2"})
        self.assertEqual(schema_errors(out, fa.output_schema), [])
        self.assertEqual(out["provenance"], "simulated")
        self.assertIn(MARK, out["facts"][0]["value"])

    def test_dispatch_claude_short_circuits_to_simulation(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        cp = resolve("company-partner", self.reg)
        # No runner, no real claude — simulation must short-circuit before any subprocess.
        out = D.dispatch_claude(cp, {"persona": "X", "lens": "y"})
        self.assertIn(MARK, out["rationale"])

    def test_batch_short_circuits_to_simulation(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        items = [(resolve("post-market-safety", self.reg), {"candidate": "TSC2"}),
                 (resolve("financial", self.reg), {"candidate": "TSC2"})]
        out = D.dispatch_claude_batch(items)
        self.assertEqual(set(out), {"post-market-safety", "financial"})
        self.assertTrue(all(MARK in r["facts"][0]["value"] for r in out.values()))


class TestStampProvenanceSimulateAware(_SimEnv):
    def setUp(self):
        super().setUp()
        self.cp = resolve("company-partner", load_registry())

    def test_stamps_simulated_for_claude_subagent_when_on(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        out = G.stamp_provenance(self.cp, {"persona": "X", "stance": "hold", "conviction": 0,
                                           "rationale": "r", "fact_claims": []})
        self.assertEqual(out["provenance"], "simulated")

    def test_keeps_real_label_when_off(self):
        out = G.stamp_provenance(self.cp, {"persona": "X", "stance": "hold", "conviction": 0,
                                           "rationale": "r", "fact_claims": []})
        self.assertEqual(out["provenance"], self.cp.provenance_label)   # NOT simulated

    def test_non_claude_kind_keeps_real_label_even_when_on(self):
        # A python/seam agent is genuinely real — simulate mode must NOT relabel it.
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        moat = resolve("internal-science-lead", load_registry())
        out = G.stamp_provenance(moat, {"candidate": "TSC2", "facts": [
            {"value": "v", "source": "s", "tier": "T2"}]})
        self.assertNotEqual(out["provenance"], "simulated")
        self.assertEqual(out["provenance"], moat.provenance_label)


if __name__ == "__main__":
    unittest.main()
