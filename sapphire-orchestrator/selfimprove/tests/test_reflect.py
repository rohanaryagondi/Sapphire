import json
import os
import tempfile
import unittest
from pathlib import Path
from selfimprove.reflect import reflect
from memory import read_all, recall

class TestReflect(unittest.TestCase):
    def setUp(self):
        self.eng = tempfile.mkdtemp()
        self.mem = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.mem
        d = Path(self.eng) / "engX"
        d.mkdir(parents=True, exist_ok=True)
        rows = [
            {"type": "engagement_open", "engagement_id": "engX", "plan": {"query": "Nav1.9?"}},
            {"engagement_id": "engX", "agent_id": "emet-runner", "provenance": "emet-live",
             "output": {"candidate": "SCN11A",
                        "facts": [{"value": "GoF analgesia", "source": "PMID:1", "tier": "T2"},
                                  {"value": "moat-vs-lit gap", "source": "PMID:2", "tier": "T2", "flag": "DIVERGENCE"}]}},
            {"type": "engagement_close", "engagement_id": "engX",
             "synthesis": {"recommendation": "advance to de-risking", "confidence": "conditional",
                           "proposed_experiment": "resolve Nav1.9 persistent current",
                           "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["pain"], "drugs": []}}},
        ]
        (d / "trace.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_reflect_writes_conclusion_proposal_and_facts(self):
        summary = reflect("engX")
        self.assertGreaterEqual(summary["written"], 4)   # conclusion + proposal + 2 facts
        types = [r["type"] for r in read_all()]
        self.assertIn("conclusion", types)
        self.assertIn("experiment_proposal", types)
        self.assertIn("fact", types)
        self.assertIn("divergence", types)               # the DIVERGENCE-flagged fact

    def test_reflected_memory_is_recallable(self):
        reflect("engX")
        hits = recall({"genes": ["SCN11A"]})
        self.assertTrue(any(r["type"] == "conclusion" for r in hits))

    def test_missing_trace_is_empty_not_error(self):
        self.assertEqual(reflect("no_such_engagement")["written"], 0)

if __name__ == "__main__":
    unittest.main()
