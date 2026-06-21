import os
import tempfile
import unittest
from memory import write, read_all, record_outcome, blank_entities

def proposal(gene="SCN11A"):
    ents = blank_entities(); ents["genes"] = [gene]
    return write({"type": "experiment_proposal", "engagement_id": "e", "entities": ents,
                  "payload": {"experiment": "resolve Nav1.9 persistent current"}})

class TestOutcome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_confirmed_outcome_links_no_blindspot(self):
        p = proposal()
        o = record_outcome(p["id"], {"result": "confirmed", "data": "assay resolved it", "source": "wetlab"})
        self.assertEqual(o["type"], "experiment_outcome")
        self.assertIn(p["id"], o["links"])
        self.assertEqual(o["entities"]["genes"], ["SCN11A"])    # inherited from proposal
        self.assertEqual([r["type"] for r in read_all()].count("moat_blindspot"), 0)

    def test_refuted_outcome_opens_blindspot(self):
        p = proposal()
        record_outcome(p["id"], {"result": "refuted", "data": "moat missed the persistent current", "source": "wetlab"})
        types = [r["type"] for r in read_all()]
        self.assertIn("moat_blindspot", types)
        bs = next(r for r in read_all() if r["type"] == "moat_blindspot")
        self.assertIn(p["id"], bs["links"])
        self.assertEqual(bs["entities"]["genes"], ["SCN11A"])

if __name__ == "__main__":
    unittest.main()
