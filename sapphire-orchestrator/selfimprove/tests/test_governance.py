import unittest
from selfimprove.governance import load_policy, may_auto_apply, trigger_count, freshness_days

class TestGovernance(unittest.TestCase):
    def test_default_is_tiered(self):
        self.assertEqual(load_policy()["level"], "tiered")

    def test_memory_auto_applies(self):
        self.assertTrue(may_auto_apply("memory"))

    def test_behavior_change_gated(self):
        for a in ["skills", "specs", "scenarios", "routes"]:
            self.assertFalse(may_auto_apply(a))

    def test_unknown_artifact_defaults_false(self):
        self.assertFalse(may_auto_apply("nuclear_codes"))

    def test_thresholds(self):
        self.assertEqual(trigger_count(), 3)
        self.assertEqual(freshness_days(), 90)

if __name__ == "__main__":
    unittest.main()
