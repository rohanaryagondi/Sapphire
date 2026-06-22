"""Tests for the full agent roster added in P1a."""
import unittest
from harness.contracts import resolve, Contract

SEMANTIC_IDS = [
    "patent-ip",
    "global-regulatory-divergence",
    "dea-scheduling",
    "clinical-trial-registry",
    "post-market-safety",
    "financial",
    "payer",
    "manufacturing-cmc",
    "patient-advocacy",
    "kol-social",
    "policy-legislative",
    "reputational",
    "fda-institutional-memory",
]

INSTITUTIONAL_IDS = [
    "ex-fda-regulator",
    "adversarial-red-team",
    "payer-partner",
    "kol-partner",
]

ALL_NEW_IDS = SEMANTIC_IDS + INSTITUTIONAL_IDS + ["internal-science-lead"]


class TestRoster(unittest.TestCase):

    def test_all_new_ids_resolve(self):
        for agent_id in ALL_NEW_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertIsInstance(c, Contract)

    def test_all_new_ids_have_expected_kind(self):
        for agent_id in SEMANTIC_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertEqual(c.kind, "claude-subagent")
        for agent_id in INSTITUTIONAL_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertEqual(c.kind, "claude-subagent")
        self.assertEqual(resolve("internal-science-lead").kind, "python")

    def test_all_new_ids_have_non_none_output_schema(self):
        for agent_id in ALL_NEW_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertIsNotNone(c.output_schema)

    def test_no_ref_left_in_output_schema(self):
        for agent_id in ALL_NEW_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertNotIn("$ref", c.output_schema)

    def test_semantic_guardrails(self):
        expected = {"data_boundary", "facts_only_cited", "stamp_provenance"}
        for agent_id in SEMANTIC_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                for g in expected:
                    self.assertIn(g, c.guardrails)

    def test_institutional_guardrails(self):
        expected = {"must_cite_dossier", "veto_is_gate", "stamp_provenance"}
        for agent_id in INSTITUTIONAL_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                for g in expected:
                    self.assertIn(g, c.guardrails)

    def test_veto_class_agents(self):
        self.assertTrue(resolve("patent-ip").veto_class)
        self.assertTrue(resolve("fda-institutional-memory").veto_class)

    def test_non_veto_semantic_agents_not_veto_class(self):
        non_veto = [a for a in SEMANTIC_IDS if a not in ("patent-ip", "fda-institutional-memory")]
        for agent_id in non_veto:
            with self.subTest(agent_id=agent_id):
                self.assertFalse(resolve(agent_id).veto_class)

    def test_veto_is_gate_in_veto_class_guardrails(self):
        self.assertIn("veto_is_gate", resolve("patent-ip").guardrails)
        self.assertIn("veto_is_gate", resolve("fda-institutional-memory").guardrails)

    def test_institutional_agents_no_tools(self):
        for agent_id in INSTITUTIONAL_IDS:
            with self.subTest(agent_id=agent_id):
                self.assertEqual(resolve(agent_id).tools_allowed, [])

    def test_internal_science_lead_provenance_label(self):
        self.assertEqual(resolve("internal-science-lead").provenance_label, "moat-real")

    def test_semantic_agents_provenance_label(self):
        # fda-institutional-memory pre-existed with provenance_label "fda-primary"; all new semantic
        # agents use "semantic-web".
        new_semantic = [a for a in SEMANTIC_IDS if a != "fda-institutional-memory"]
        for agent_id in new_semantic:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertEqual(c.provenance_label, "semantic-web")

    def test_institutional_agents_output_schema_is_verdict(self):
        verdict_required = {"persona", "stance", "conviction", "rationale", "fact_claims"}
        for agent_id in INSTITUTIONAL_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertIsNotNone(c.output_schema)
                props = set(c.output_schema.get("required", []))
                self.assertTrue(verdict_required.issubset(props))

    def test_semantic_agents_output_schema_is_findings(self):
        findings_required = {"candidate", "facts"}
        for agent_id in SEMANTIC_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertIsNotNone(c.output_schema)
                props = set(c.output_schema.get("required", []))
                self.assertTrue(findings_required.issubset(props))

    def test_internal_science_lead_output_schema_is_findings(self):
        c = resolve("internal-science-lead")
        self.assertIsNotNone(c.output_schema)
        self.assertIn("candidate", c.output_schema.get("required", []))
        self.assertIn("facts", c.output_schema.get("required", []))

    def test_retry_fields_set_for_new_agents(self):
        for agent_id in ALL_NEW_IDS:
            with self.subTest(agent_id=agent_id):
                c = resolve(agent_id)
                self.assertIsInstance(c.max_repair, int)
                self.assertIn(c.on_hard_fail, ("abstain", "escalate"))


if __name__ == "__main__":
    unittest.main()
