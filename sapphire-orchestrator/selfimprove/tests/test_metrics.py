import os
import tempfile
import unittest
from pathlib import Path
from memory import write, record_outcome, blank_entities
from selfimprove.metrics import compute_metrics, write_report

def proposal():
    ents = blank_entities(); ents["genes"] = ["SCN11A"]
    return write({"type": "experiment_proposal", "entities": ents, "payload": {"experiment": "x"}})

class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_prediction_accuracy_and_blindspots(self):
        p1 = proposal(); p2 = proposal()
        record_outcome(p1["id"], {"result": "confirmed", "data": "", "source": "w"})
        record_outcome(p2["id"], {"result": "refuted", "data": "missed it", "source": "w"})
        m = compute_metrics()
        self.assertEqual(m["proposals"], 2)
        self.assertEqual(m["outcomes"], 2)
        self.assertAlmostEqual(m["prediction_accuracy"], 0.5)
        self.assertEqual(m["blindspots"], 1)               # the refuted one opened a blindspot

    def test_accuracy_none_when_no_outcomes(self):
        proposal()
        self.assertIsNone(compute_metrics()["prediction_accuracy"])

    def test_write_report_creates_markdown(self):
        proposal()
        write_report()
        self.assertTrue((Path(self.tmp) / "REPORT.md").exists())

if __name__ == "__main__":
    unittest.main()
