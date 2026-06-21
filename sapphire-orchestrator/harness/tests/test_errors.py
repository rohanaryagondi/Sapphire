import unittest
from harness.errors import HARNESS_ERRORS, HarnessEscalation, abstain_envelope, escalate

class TestErrors(unittest.TestCase):
    def test_codes_present(self):
        for c in ["malformed-output", "guardrail-violation", "timeout",
                  "tool-failure", "login-required", "budget", "unknown-agent"]:
            self.assertIn(c, HARNESS_ERRORS)

    def test_abstain_envelope_shape(self):
        env = abstain_envelope("malformed-output", "a valid dossier row")
        self.assertTrue(env["abstained"])
        self.assertEqual(env["reason"], "malformed-output")
        self.assertEqual(env["would_need"], "a valid dossier row")

    def test_escalate_builds_exception(self):
        ex = escalate("login-required", "BenchSci login screen")
        self.assertIsInstance(ex, HarnessEscalation)
        self.assertEqual(ex.code, "login-required")
        self.assertIn("BenchSci", ex.detail)

if __name__ == "__main__":
    unittest.main()
