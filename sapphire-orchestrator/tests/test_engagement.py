import os
import tempfile
import unittest
from engagement import extract_entities, run_engagement
from memory import recall

class FakeEngine:
    """Stand-in for Orchestrator.run — returns a crafted run with a gene + dossier + synthesis."""
    def run(self, sid):
        return {
            "id": sid, "title": "Nav1.9 pain", "query": "Is SCN11A a viable analgesic target?",
            "headline": "SCN11A / Nav1.9", "plan": {"disease": "neuropathic pain"},
            "discover": {"dossier": [
                {"field": "B1", "value": "GoF Mendelian", "source": "PMID:26243570", "tier": "T2"},
                {"field": "C3", "value": "moat-vs-lit gap", "source": "PMID:2", "tier": "T2", "flag": "DIVERGENCE"},
            ], "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}},
            "validate": {"runs": []},
            "consult": {"round1": [], "round2": [], "spread": {}},
            "synthesize": {"recommendation": "advance to de-risking", "confidence": "conditional",
                           "proposed_experiment": "resolve Nav1.9 persistent current"},
        }

class TestEngagement(unittest.TestCase):
    def setUp(self):
        self.eng = tempfile.mkdtemp(); self.mem = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.mem

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_extract_entities_finds_genes(self):
        e = extract_entities("SCN11A gain-of-function and KCNT1 in epilepsy")
        self.assertIn("SCN11A", e["genes"])
        self.assertIn("KCNT1", e["genes"])

    def test_run_engagement_writes_recallable_memory(self):
        run = run_engagement("nav1_8", engine=FakeEngine())
        self.assertIn("engagement_id", run)
        self.assertGreaterEqual(run["reflection"]["written"], 1)
        hits = recall({"genes": ["SCN11A"]})
        self.assertTrue(any(r["type"] == "conclusion" for r in hits))
        self.assertTrue(any(r["type"] == "divergence" for r in hits))   # the DIVERGENCE dossier row

    def test_second_engagement_recalls_prior(self):
        run_engagement("nav1_8", engine=FakeEngine())
        run2 = run_engagement("nav1_8", engine=FakeEngine())
        self.assertTrue(run2["priors"])     # priors surfaced from the first engagement

    def test_real_engine_smoke(self):
        # the real Orchestrator must run end-to-end through the wrapper without error
        run = run_engagement("nav1_8")
        self.assertIn("engagement_id", run)
        self.assertIn("synthesize", run)

    def test_extract_entities_handles_long_prefix_genes(self):
        e = extract_entities("CACNA1A and GRIN2A and ATP2A2 in ataxia; plus SCN11A")
        for g in ["CACNA1A", "GRIN2A", "ATP2A2", "SCN11A"]:
            self.assertIn(g, e["genes"])

if __name__ == "__main__":
    unittest.main()
