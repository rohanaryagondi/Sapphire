import os
import tempfile
import unittest
from selfimprove.cli import main
from memory import write, read_all, blank_entities

class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _proposal(self):
        ents = blank_entities(); ents["genes"] = ["SCN11A"]
        return write({"type": "experiment_proposal", "entities": ents, "payload": {"experiment": "x"}})

    def test_record_outcome_writes(self):
        p = self._proposal()
        rc = main(["record-outcome", p["id"], "confirmed", "--data", "assay ok", "--source", "wetlab"])
        self.assertEqual(rc, 0)
        self.assertTrue(any(r["type"] == "experiment_outcome" for r in read_all()))

    def test_record_outcome_refuted_opens_blindspot(self):
        p = self._proposal()
        main(["record-outcome", p["id"], "refuted", "--data", "missed it"])
        self.assertTrue(any(r["type"] == "moat_blindspot" for r in read_all()))

    def test_report_command(self):
        self.assertEqual(main(["report"]), 0)

    def test_unknown_command_nonzero(self):
        self.assertNotEqual(main(["frobnicate"]), 0)

    def test_missing_args_nonzero(self):
        self.assertNotEqual(main(["record-outcome"]), 0)

if __name__ == "__main__":
    unittest.main()
