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
            captured["timeout"] = kw.get("timeout")
            return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": ENV}), stderr="")

        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
        prev_cdp = os.environ.pop("SAPPHIRE_EMET_CDP", None)
        prev_prof = os.environ.pop("SAPPHIRE_EMET_PROFILE", None)
        # An authenticated source MUST be configured or _default_runner abstains before the
        # subprocess; set the CDP route so the live cmd is actually built + captured.
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        if env_var:
            os.environ[env_var] = env_val
        try:
            with mock.patch.object(H, "subprocess", SimpleNamespace(run=_fake_run)):
                H._default_runner({"candidate": "SCN11A", "question": "validate"})
        finally:
            for k in ("CLAUDE_MODEL", "SAPPHIRE_MODEL", "SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE"):
                os.environ.pop(k, None)
            for k, v in (("CLAUDE_MODEL", prev_c), ("SAPPHIRE_MODEL", prev_s),
                         ("SAPPHIRE_EMET_CDP", prev_cdp), ("SAPPHIRE_EMET_PROFILE", prev_prof)):
                if v is not None:
                    os.environ[k] = v
        self._captured = captured
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

    def test_pins_strict_playwright_mcp_config(self):
        cmd = self._run_capturing(None, None)
        # The live cmd pins ONLY our authenticated Playwright MCP, strictly, with scoped tools.
        self.assertIn("--mcp-config", cmd)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("--allowedTools", cmd)
        tools = cmd[cmd.index("--allowedTools") + 1]
        self.assertIn("mcp__playwright__browser_navigate", tools)


class TestEmetAuthGating(unittest.TestCase):
    """The dedicated-authenticated-browser gating: CDP > profile > honest-abstain."""

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None)
                       for k in ("SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE")}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_no_auth_source_returns_login_required(self):
        # Neither env set → honest abstain BEFORE any subprocess (no fresh-browser tool-failure).
        self.assertEqual(H._emet_mcp_config(), None)
        self.assertEqual(H._default_runner({"candidate": "TSC2"}), {"login_required": True})

    def test_no_auth_source_makes_agent_abstain(self):
        # End to end: cfg None → login_required → handler escalates → agent abstains honestly.
        with self.assertRaises(HarnessEscalation):
            emet_handler(C, {"candidate": "TSC2"})

    def test_cdp_route_builds_cdp_endpoint(self):
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        cfg = H._emet_mcp_config()
        args = cfg["mcpServers"]["playwright"]["args"]
        self.assertIn("--cdp-endpoint", args)
        self.assertEqual(args[args.index("--cdp-endpoint") + 1], "http://localhost:9222")
        self.assertNotIn("--user-data-dir", args)

    def test_profile_route_builds_user_data_dir(self):
        os.environ["SAPPHIRE_EMET_PROFILE"] = "/tmp/emet_profile"
        cfg = H._emet_mcp_config()
        args = cfg["mcpServers"]["playwright"]["args"]
        self.assertIn("--user-data-dir", args)
        self.assertEqual(args[args.index("--user-data-dir") + 1], "/tmp/emet_profile")

    def test_cdp_takes_precedence_over_profile(self):
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        os.environ["SAPPHIRE_EMET_PROFILE"] = "/tmp/emet_profile"
        args = H._emet_mcp_config()["mcpServers"]["playwright"]["args"]
        self.assertIn("--cdp-endpoint", args)
        self.assertNotIn("--user-data-dir", args)   # CDP wins → no profile-lock


class TestEmetAutoLogin(unittest.TestCase):
    """Auto-login is authorized only when dedicated-profile creds are available; the password is
    read by the runner agent from the gitignored file — never by this process / argv."""

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None)
                       for k in ("SAPPHIRE_EMET_USER", "SAPPHIRE_EMET_PASS",
                                 "SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE")}
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"   # so the live cmd is built

    def tearDown(self):
        for k in ("SAPPHIRE_EMET_USER", "SAPPHIRE_EMET_PASS", "SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE"):
            os.environ.pop(k, None)
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v

    def _capture_cmd(self):
        captured = {}

        def _fake_run(cmd, **kw):
            captured["cmd"] = list(cmd)
            return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": ENV}), stderr="")

        with mock.patch.object(H, "subprocess", SimpleNamespace(run=_fake_run)):
            H._default_runner({"candidate": "TSC2", "question": "validate"})
        cmd = captured["cmd"]
        return cmd, cmd[cmd.index("-p") + 1]            # (cmd, prompt)

    def test_creds_available_authorizes_autologin(self):
        os.environ["SAPPHIRE_EMET_USER"] = "tester@example.org"
        os.environ["SAPPHIRE_EMET_PASS"] = "Z9_distinctive_pw_sentinel_Q7"   # never echoed/argv'd
        self.assertTrue(H._emet_autologin_available())
        cmd, prompt = self._capture_cmd()
        self.assertIn("AUTO-LOGIN IS AUTHORIZED", prompt)
        tools = cmd[cmd.index("--allowedTools") + 1]
        self.assertIn("Read", tools)                     # agent may read the gitignored creds file
        # The password is read by the agent FROM THE FILE — it must never appear on argv.
        self.assertNotIn("Z9_distinctive_pw_sentinel_Q7", " ".join(cmd))

    def test_no_creds_keeps_honest_abstain_clause(self):
        # No env creds AND no creds file → never auto-login; honest login_required clause, no Read.
        with mock.patch.object(H, "_EMET_CREDS", H.Path("/nonexistent/emet_creds.env")):
            self.assertFalse(H._emet_autologin_available())
            cmd, prompt = self._capture_cmd()
        self.assertIn('{"login_required": true}', prompt)
        self.assertNotIn("AUTO-LOGIN", prompt)
        self.assertNotIn("Read", cmd[cmd.index("--allowedTools") + 1])


class TestEmetTimeout(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.pop("SAPPHIRE_EMET_TIMEOUT_S", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_EMET_TIMEOUT_S", None)
        if self._prev is not None:
            os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = self._prev

    def test_default_timeout(self):
        self.assertEqual(H._emet_timeout_s(), 240)

    def test_env_override(self):
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "90"
        self.assertEqual(H._emet_timeout_s(), 90)

    def test_floor_and_bad_value(self):
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "5"
        self.assertEqual(H._emet_timeout_s(), 30)        # floored
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "garbage"
        self.assertEqual(H._emet_timeout_s(), 240)       # bad → default


if __name__ == "__main__":
    unittest.main()
