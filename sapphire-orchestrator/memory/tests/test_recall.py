import os
import tempfile
import unittest
from memory import write, recall, blank_entities

def rec(gene, **kw):
    ents = blank_entities(); ents["genes"] = [gene]
    base = {"type": "conclusion", "engagement_id": "e", "entities": ents,
            "payload": {"recommendation": f"about {gene}"}}
    base.update(kw)
    return base

class TestRecall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_recall_by_gene_filters(self):
        write(rec("SCN11A"))
        write(rec("KCNT1"))
        out = recall({"genes": ["SCN11A"]})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["entities"]["genes"], ["SCN11A"])

    def test_recall_accepts_flat_list(self):
        write(rec("SCN11A"))
        self.assertEqual(len(recall(["SCN11A"])), 1)

    def test_recall_ranks_by_overlap(self):
        ents = blank_entities(); ents["genes"] = ["SCN11A", "SCN10A"]
        write({"type": "conclusion", "entities": ents, "payload": {"recommendation": "two-gene"}})
        write(rec("SCN11A"))
        out = recall({"genes": ["SCN11A", "SCN10A"]})
        self.assertEqual(out[0]["payload"]["recommendation"], "two-gene")  # 2 overlaps ranks first

    def test_types_filter(self):
        write(rec("SCN11A", type="conclusion"))
        write(rec("SCN11A", type="fact", payload={"value": "x", "source": "PMID:1"}))
        self.assertTrue(all(r["type"] == "fact" for r in recall({"genes": ["SCN11A"]}, types=["fact"])))

    def test_no_match_empty(self):
        write(rec("SCN11A"))
        self.assertEqual(recall({"genes": ["TRPV1"]}), [])

if __name__ == "__main__":
    unittest.main()
