import os
import tempfile
import unittest
from memory import write, read_all, rebuild_index, MemoryRefusal

def rec(**kw):
    base = {"type": "conclusion", "engagement_id": "eng1",
            "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["neuropathic pain"], "drugs": []},
            "payload": {"recommendation": "advance to de-risking"}}
    base.update(kw)
    return base

class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_write_fills_id_ts_and_roundtrips(self):
        out = write(rec())
        self.assertTrue(out["id"].startswith("mem_"))
        self.assertIn("ts", out)
        allr = read_all()
        self.assertEqual(len(allr), 1)
        self.assertEqual(allr[0]["payload"]["recommendation"], "advance to de-risking")

    def test_append_only(self):
        write(rec(payload={"recommendation": "a"}))
        write(rec(payload={"recommendation": "b"}))
        self.assertEqual([r["payload"]["recommendation"] for r in read_all()], ["a", "b"])

    def test_bad_type_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(type="gossip"))

    def test_internal_data_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(payload={"s_internal": 0.9}))      # data boundary blocks internal scores

    def test_schema_invalid_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(tier="T9"))                          # tier not in T1..T4

    def test_rebuild_index_maps_entities(self):
        write(rec())
        idx = rebuild_index()
        self.assertIn("SCN11A", idx)
        self.assertEqual(len(idx["SCN11A"]), 1)

if __name__ == "__main__":
    unittest.main()
