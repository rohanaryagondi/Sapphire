import json
import os
import tempfile
import unittest
from pathlib import Path
from capture import draft_scenario, write_draft

def fake_plan(query):
    return {"id": "scn2a_epilepsy", "title": "SCN2A epilepsy", "query": query,
            "headline": "SCN2A", "disease": "epilepsy", "modality": "small molecule"}

def fake_emet(query):
    return {"candidate": "SCN2A", "facts": [
        {"value": "GoF early-onset; LoF later-onset", "source": "PMID:111 [PMID:111]", "tier": "T2"}]}

def fake_qmodels(query):
    return [{"model": "Boltz-2", "out": "pKd 7.1", "provenance": "stub"}]

class TestCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.drafts_dir = os.path.join(self.tmp, "drafts")
        os.environ["SAPPHIRE_DRAFTS_DIR"] = self.drafts_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_DRAFTS_DIR", None)

    def test_draft_assembles_from_parts(self):
        d = draft_scenario("Is SCN2A druggable?", plan_fn=fake_plan, emet_fn=fake_emet, qmodels_fn=fake_qmodels)
        self.assertEqual(d["id"], "scn2a_epilepsy")
        self.assertEqual(d["query"], "Is SCN2A druggable?")
        self.assertTrue(d["discover"]["dossier"])          # EMET facts present
        self.assertTrue(d["validate"]["runs"])             # Q-Models runs present
        self.assertEqual(d["_status"], "draft")            # clearly marked unfinished

    def test_draft_without_optional_sources(self):
        d = draft_scenario("q", plan_fn=fake_plan)         # no emet/qmodels
        self.assertEqual(d["discover"]["dossier"], [])
        self.assertEqual(d["validate"]["runs"], [])

    def test_write_draft_to_drafts_dir(self):
        d = draft_scenario("q", plan_fn=fake_plan)
        p = write_draft(d)
        self.assertTrue(p.exists())
        self.assertEqual(json.loads(p.read_text())["id"], "scn2a_epilepsy")
        self.assertIn("drafts", str(p))

if __name__ == "__main__":
    unittest.main()
