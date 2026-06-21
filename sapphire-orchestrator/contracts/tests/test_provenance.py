import unittest
from contracts.provenance import PROVENANCE, is_valid_provenance

class TestProvenance(unittest.TestCase):
    def test_fixed_labels_present(self):
        for label in ["emet-live", "emet-mcp", "memory-recall", "persona-judgment",
                      "synthesis", "live-local", "gpu-async", "gpu-disabled",
                      "stub", "unavailable", "mock"]:
            self.assertIn(label, PROVENANCE)

    def test_fixed_label_valid(self):
        self.assertTrue(is_valid_provenance("emet-live"))

    def test_qmodels_prefixed_valid(self):
        self.assertTrue(is_valid_provenance("qmodels:boltz2"))

    def test_unknown_invalid(self):
        self.assertFalse(is_valid_provenance("made-up"))

    def test_non_string_invalid(self):
        self.assertFalse(is_valid_provenance(None))

    def test_moat_real_valid(self):
        self.assertTrue(is_valid_provenance("moat-real"))

if __name__ == "__main__":
    unittest.main()
