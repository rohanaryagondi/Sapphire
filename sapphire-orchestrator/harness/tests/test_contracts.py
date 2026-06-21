import unittest
from harness.contracts import Contract, AgentResult, canonical_json, inputs_hash

class TestContracts(unittest.TestCase):
    def test_contract_defaults(self):
        c = Contract(id="x", role="r", kind="python")
        self.assertEqual(c.tools_allowed, [])
        self.assertEqual(c.guardrails, [])
        self.assertEqual(c.max_repair, 2)
        self.assertEqual(c.on_hard_fail, "abstain")
        self.assertFalse(c.veto_class)

    def test_two_contracts_dont_share_mutable_defaults(self):
        a = Contract(id="a", role="", kind="python")
        b = Contract(id="b", role="", kind="python")
        a.tools_allowed.append("WebSearch")
        self.assertEqual(b.tools_allowed, [])  # no shared list

    def test_agent_result_shape(self):
        r = AgentResult(agent_id="x", ok=True, output={"a": 1}, provenance="synthesis", status="ok")
        self.assertIsNone(r.error)
        self.assertEqual(r.meta, {})

    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), canonical_json({"a": 2, "b": 1}))

    def test_inputs_hash_stable_and_prefixed(self):
        h1 = inputs_hash("agent", {"x": 1, "y": 2})
        h2 = inputs_hash("agent", {"y": 2, "x": 1})
        self.assertEqual(h1, h2)               # key order irrelevant
        self.assertTrue(h1.startswith("sha256:"))
        self.assertNotEqual(h1, inputs_hash("other", {"x": 1, "y": 2}))  # id participates

if __name__ == "__main__":
    unittest.main()
