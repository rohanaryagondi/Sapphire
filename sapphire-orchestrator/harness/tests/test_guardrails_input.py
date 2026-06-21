import unittest
from harness.guardrails import Violation, data_boundary, public_identifiers_only

class TestInputGuards(unittest.TestCase):
    def test_clean_public_inputs_pass(self):
        clean = {"gene": "SCN11A", "smiles": "CC(=O)O", "disease": "neuropathic pain"}
        self.assertEqual(data_boundary(clean), [])
        self.assertEqual(public_identifiers_only(clean), [])

    def test_internal_score_key_blocked(self):
        v = data_boundary({"gene": "SCN11A", "s_internal": 0.89})
        self.assertTrue(v)
        self.assertEqual(v[0].guardrail, "data_boundary")

    def test_internal_candidate_id_pattern_blocked(self):
        v = data_boundary({"note": "candidate QS00123 ranked first"})
        self.assertTrue(v)

    def test_nested_internal_key_blocked(self):
        v = data_boundary({"payload": {"deep": {"latent_vector": [0.1, 0.2]}}})
        self.assertTrue(v)

    def test_public_identifiers_only_relabels(self):
        v = public_identifiers_only({"s_internal": 1})
        self.assertEqual(v[0].guardrail, "public_identifiers_only")

    def test_internal_term_as_string_value_blocked(self):
        # internal scoring identifiers embedded in a free-text VALUE must be caught
        self.assertTrue(data_boundary({"note": "filtering on crispr_score=0.94"}))
        self.assertTrue(data_boundary({"q": "run latent_vector extraction"}))
        self.assertTrue(data_boundary({"x": "internal_score was high"}))
        self.assertTrue(data_boundary({"x": "see candidate_id below"}))

    def test_clean_value_text_still_passes(self):
        # ordinary scientific text must NOT trip the guard (no false positives)
        self.assertEqual(data_boundary({"note": "SCN11A gain-of-function in neuropathic pain"}), [])

if __name__ == "__main__":
    unittest.main()
