import unittest
from emet.handler import emet_handler, make_emet_handler
from harness.errors import HarnessEscalation
from harness.contracts import Contract

C = Contract(id="emet-runner", role="", kind="emet-playwright", provenance_label="emet-live")

ENV = {"candidate": "SCN11A", "emet_workflow": "Target Validation", "verdict": "pass",
       "evidence": [{"claim": "GoF analgesia", "source": "X 2016", "id_or_url": "PMID:1"}],
       "notes": "", "chat_url": "u", "captured_at": "t", "provenance": "emet-live"}

class TestHandler(unittest.TestCase):
    def test_handler_normalizes_runner_envelope(self):
        out = emet_handler(C, {"candidate": "SCN11A", "workflow": "Target Validation"},
                           runner=lambda inp: ENV)
        self.assertEqual(out["candidate"], "SCN11A")
        self.assertEqual(out["provenance"], "emet-live")
        self.assertTrue(out["facts"])

    def test_login_required_escalates(self):
        with self.assertRaises(HarnessEscalation) as cm:
            emet_handler(C, {"candidate": "X"}, runner=lambda inp: {"login_required": True})
        self.assertEqual(cm.exception.code, "login-required")

    def test_make_emet_handler_is_two_arg(self):
        h = make_emet_handler(runner=lambda inp: ENV)
        out = h(C, {"candidate": "SCN11A"})       # 2-arg, as the harness calls it
        self.assertEqual(out["candidate"], "SCN11A")

if __name__ == "__main__":
    unittest.main()
