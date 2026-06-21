import unittest
from harness.contracts import load_registry, resolve, Contract

class TestRegistry(unittest.TestCase):
    def test_registry_loads(self):
        reg = load_registry()
        self.assertIn("agents", reg)
        self.assertIn("schemas", reg)

    def test_known_agents_present(self):
        ids = {a["id"] for a in load_registry()["agents"]}
        for needed in ["company-partner", "q-models-runner", "emet-runner", "fda-institutional-memory"]:
            self.assertIn(needed, ids)

    def test_resolve_returns_contract_with_retry_mapped(self):
        c = resolve("company-partner")
        self.assertIsInstance(c, Contract)
        self.assertEqual(c.kind, "claude-subagent")
        self.assertEqual(c.tools_allowed, [])           # personas get no tools
        self.assertIn("must_cite_dossier", c.guardrails)
        self.assertIsInstance(c.max_repair, int)

    def test_resolve_inlines_schema_ref(self):
        c = resolve("company-partner")
        # output_schema must be the concrete verdict schema dict, not a {"$ref": ...}
        self.assertNotIn("$ref", c.output_schema)
        self.assertEqual(c.output_schema.get("type"), "object")

    def test_unknown_agent_raises_keyerror(self):
        with self.assertRaises(KeyError):
            resolve("no-such-agent")

    def test_veto_class_flag(self):
        self.assertTrue(resolve("fda-institutional-memory").veto_class)

if __name__ == "__main__":
    unittest.main()
