import unittest
from harness.repair import repair_prompt

class TestRepair(unittest.TestCase):
    def test_includes_errors_and_prior(self):
        p = repair_prompt({"facts": []}, ["$.candidate: required field missing"])
        self.assertIn("$.candidate: required field missing", p)
        self.assertIn("facts", p)
        self.assertIn("corrected", p.lower())

    def test_handles_no_prior(self):
        p = repair_prompt(None, ["tool-failure: web fetch 500"])
        self.assertIn("tool-failure: web fetch 500", p)

if __name__ == "__main__":
    unittest.main()
