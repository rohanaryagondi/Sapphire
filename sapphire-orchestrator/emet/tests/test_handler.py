import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import emet.handler as H
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


class TestDefaultRunnerModel(unittest.TestCase):
    """The EMET subprocess honors the cheap-live model lever (CLAUDE_MODEL/SAPPHIRE_MODEL)."""

    def _run_capturing(self, env_var, env_val):
        captured = {}

        def _fake_run(cmd, **kw):
            captured["cmd"] = list(cmd)
            return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": ENV}), stderr="")

        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
        if env_var:
            os.environ[env_var] = env_val
        try:
            with mock.patch.object(H, "subprocess", SimpleNamespace(run=_fake_run)):
                H._default_runner({"candidate": "SCN11A", "question": "validate"})
        finally:
            os.environ.pop("CLAUDE_MODEL", None)
            os.environ.pop("SAPPHIRE_MODEL", None)
            if prev_c is not None:
                os.environ["CLAUDE_MODEL"] = prev_c
            if prev_s is not None:
                os.environ["SAPPHIRE_MODEL"] = prev_s
        return captured["cmd"]

    def test_model_added_when_claude_model_set(self):
        cmd = self._run_capturing("CLAUDE_MODEL", "claude-haiku-4-5")
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-haiku-4-5")

    def test_model_added_when_sapphire_model_set(self):
        cmd = self._run_capturing("SAPPHIRE_MODEL", "claude-haiku-4-5")
        self.assertIn("--model", cmd)

    def test_no_model_when_env_unset(self):
        cmd = self._run_capturing(None, None)
        self.assertNotIn("--model", cmd)


if __name__ == "__main__":
    unittest.main()
