import os
import tempfile
import unittest
from harness.runtime import run
from emet.handler import make_emet_handler

ENV = {"candidate": "SCN11A", "emet_workflow": "Target Validation", "verdict": "pass",
       "evidence": [{"claim": "GoF analgesia", "source": "X 2016", "id_or_url": "PMID:26243570"}],
       "notes": "", "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
       "captured_at": "2026-06-21T00:00:00Z", "provenance": "emet-live"}

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def test_emet_runner_through_harness_ok(self):
        ctx = {"emet_handler": make_emet_handler(runner=lambda inp: ENV)}
        r = run("emet-runner", {"candidate": "SCN11A", "workflow": "Target Validation"},
                engagement_id="eng_emet1", ctx=ctx)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.provenance, "emet-live")
        self.assertTrue(r.output["facts"])
        self.assertEqual(r.output["facts"][0]["tier"], "T2")

    def test_login_escalates_through_harness(self):
        ctx = {"emet_handler": make_emet_handler(runner=lambda inp: {"login_required": True})}
        r = run("emet-runner", {"candidate": "SCN11A"}, engagement_id="eng_emet2", ctx=ctx)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "escalated")
        self.assertEqual(r.error, "login-required")

    def test_internal_input_blocked_before_handler(self):
        called = {"n": 0}
        def runner(inp):
            called["n"] += 1
            return ENV
        ctx = {"emet_handler": make_emet_handler(runner=runner)}
        r = run("emet-runner", {"candidate": "SCN11A", "s_internal": 0.9},
                engagement_id="eng_emet3", ctx=ctx)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "guardrail-violation")
        self.assertEqual(called["n"], 0)    # data boundary blocked before EMET ran

if __name__ == "__main__":
    unittest.main()
