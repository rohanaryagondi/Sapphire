import json
import os
import tempfile
import unittest
from pathlib import Path
from harness import trace

class TestTrace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def _lines(self, eid):
        return [json.loads(l) for l in trace.trace_path(eid).read_text().splitlines()]

    def test_open_record_close_appends_in_order(self):
        eid = "eng_test1"
        trace.open_engagement(eid, {"query": "q"})
        trace.record(eid, {"agent_id": "a", "status": "ok"})
        trace.close_engagement(eid, {"recommendation": "advance"})
        rows = self._lines(eid)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["type"], "engagement_open")
        self.assertEqual(rows[1]["agent_id"], "a")
        self.assertEqual(rows[2]["type"], "engagement_close")

    def test_every_line_has_ts(self):
        eid = "eng_test2"
        trace.record(eid, {"agent_id": "a"})
        trace.record(eid, {"agent_id": "b"})
        for row in self._lines(eid):
            self.assertIn("ts", row)

    def test_append_only_never_truncates(self):
        eid = "eng_test3"
        trace.record(eid, {"n": 1})
        trace.record(eid, {"n": 2})
        self.assertEqual([r["n"] for r in self._lines(eid)], [1, 2])

if __name__ == "__main__":
    unittest.main()
