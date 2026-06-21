import json
import os
import tempfile
import unittest
from pathlib import Path
from selfimprove.authoring import propose, propose_from_routes

class TestAuthoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_PROPOSED_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_PROPOSED_DIR", None)

    def test_propose_writes_gated_artifact(self):
        p = propose("skills", "kcnt1-runner", "# draft skill", "needed for KCNT1 queries")
        self.assertFalse(p["auto_applied"])               # tiered: skills are gated
        files = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["rationale"], "needed for KCNT1 queries")

    def test_routes_at_threshold_proposed(self):
        out = propose_from_routes({"als_modality": 3, "rare_cns": 1})
        names = [p["name"] for p in out]
        self.assertIn("als_modality", names)              # 3 >= trigger_count
        self.assertNotIn("rare_cns", names)               # 1 < trigger_count

    def test_proposals_default_not_auto_applied(self):
        out = propose_from_routes({"als_modality": 5})
        self.assertTrue(all(p["auto_applied"] is False for p in out))

if __name__ == "__main__":
    unittest.main()
