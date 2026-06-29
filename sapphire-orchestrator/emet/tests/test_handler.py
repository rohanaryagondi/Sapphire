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
    """EMET runs on its OWN capable model, DECOUPLED from the cheap-personas CLAUDE_MODEL lever."""

    def _run_capturing(self, env_var, env_val):
        captured = {}

        def _fake_run(cmd, **kw):
            captured["cmd"] = list(cmd)
            captured["timeout"] = kw.get("timeout")
            return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": ENV}), stderr="")

        keys = ("CLAUDE_MODEL", "SAPPHIRE_MODEL", "SAPPHIRE_EMET_MODEL",
                "SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE")
        prev = {k: os.environ.pop(k, None) for k in keys}
        # An authenticated source MUST be configured or _default_runner abstains before the
        # subprocess; set the CDP route so the live cmd is actually built + captured.
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        if env_var:
            os.environ[env_var] = env_val
        try:
            with mock.patch.object(H, "subprocess", SimpleNamespace(run=_fake_run)):
                H._default_runner({"candidate": "SCN11A", "question": "validate"})
        finally:
            for k in keys:
                os.environ.pop(k, None)
            for k, v in prev.items():
                if v is not None:
                    os.environ[k] = v
        self._captured = captured
        return captured["cmd"]

    def test_emet_uses_capable_default_ignoring_cheap_lever(self):
        # CLAUDE_MODEL=haiku (the cheap-personas lever) must NOT drive EMET — it stays on the
        # capable default (Gate-5: haiku tool-failed driving the agentic EMET UI).
        cmd = self._run_capturing("CLAUDE_MODEL", "claude-haiku-4-5")
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], H._EMET_MODEL_DEFAULT)
        self.assertNotIn("claude-haiku-4-5", cmd)

    def test_sapphire_emet_model_overrides(self):
        cmd = self._run_capturing("SAPPHIRE_EMET_MODEL", "claude-opus-4-8")
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-opus-4-8")

    def test_capable_default_when_unset(self):
        cmd = self._run_capturing(None, None)
        self.assertEqual(cmd[cmd.index("--model") + 1], H._EMET_MODEL_DEFAULT)

    def test_pins_strict_playwright_mcp_config(self):
        cmd = self._run_capturing(None, None)
        # The live cmd pins ONLY our authenticated Playwright MCP, strictly, with scoped tools.
        self.assertIn("--mcp-config", cmd)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("--allowedTools", cmd)
        tools = cmd[cmd.index("--allowedTools") + 1]
        self.assertIn("mcp__playwright__browser_navigate", tools)


class TestEmetAuthGating(unittest.TestCase):
    """Task-1 re-architecture gating: explicit CDP > auto-detected VISIBLE CDP > opt-in headless
    profile > honest-abstain. `probe` is injected so tests never hit the network."""

    _NO = staticmethod(lambda _ep: False)   # CDP probe that finds nothing reachable
    _YES = staticmethod(lambda _ep: True)    # CDP probe that finds a visible browser

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in
                       ("SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE", "SAPPHIRE_EMET_CDP_PORT",
                        "SAPPHIRE_EMET_ALLOW_HEADLESS")}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_no_auth_source_returns_none(self):
        # Nothing set + no reachable CDP browser → None → honest abstain (no invisible fallback).
        self.assertIsNone(H._emet_mcp_config(probe=self._NO))

    def test_no_auth_source_makes_agent_abstain(self):
        # End to end: a definitely-closed port → no CDP → cfg None → login_required → escalate.
        os.environ["SAPPHIRE_EMET_CDP_PORT"] = "59999"   # closed → autodetect fails fast
        self.assertEqual(H._default_runner({"candidate": "TSC2"}), {"login_required": True})
        with self.assertRaises(HarnessEscalation):
            emet_handler(C, {"candidate": "TSC2"})

    def test_explicit_cdp_builds_cdp_endpoint(self):
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        args = H._emet_mcp_config(probe=self._NO)["mcpServers"]["playwright"]["args"]
        self.assertIn("--cdp-endpoint", args)
        self.assertEqual(args[args.index("--cdp-endpoint") + 1], "http://localhost:9222")
        self.assertNotIn("--user-data-dir", args)

    def test_autodetected_visible_cdp_is_preferred(self):
        # No explicit CDP, but a visible browser is reachable on the default port → use it (watchable).
        args = H._emet_mcp_config(probe=self._YES)["mcpServers"]["playwright"]["args"]
        self.assertIn("--cdp-endpoint", args)
        self.assertEqual(args[args.index("--cdp-endpoint") + 1], "http://localhost:9222")

    def test_headless_profile_requires_opt_in(self):
        # Profile set but no reachable CDP and NO opt-in → abstain (don't silently go invisible).
        os.environ["SAPPHIRE_EMET_PROFILE"] = "/tmp/emet_profile"
        self.assertIsNone(H._emet_mcp_config(probe=self._NO))
        # With the explicit opt-in, the headless profile is used.
        os.environ["SAPPHIRE_EMET_ALLOW_HEADLESS"] = "1"
        args = H._emet_mcp_config(probe=self._NO)["mcpServers"]["playwright"]["args"]
        self.assertIn("--user-data-dir", args)
        self.assertEqual(args[args.index("--user-data-dir") + 1], "/tmp/emet_profile")

    def test_cdp_takes_precedence_over_headless_profile(self):
        os.environ["SAPPHIRE_EMET_CDP"] = "http://localhost:9222"
        os.environ["SAPPHIRE_EMET_PROFILE"] = "/tmp/emet_profile"
        os.environ["SAPPHIRE_EMET_ALLOW_HEADLESS"] = "1"
        args = H._emet_mcp_config(probe=self._NO)["mcpServers"]["playwright"]["args"]
        self.assertIn("--cdp-endpoint", args)
        self.assertNotIn("--user-data-dir", args)   # visible CDP wins over invisible profile


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
            captured["input"] = kw.get("input")         # prompt now flows via STDIN (Gate-5 fix)
            return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": ENV}), stderr="")

        with mock.patch.object(H, "subprocess", SimpleNamespace(run=_fake_run)):
            H._default_runner({"candidate": "TSC2", "question": "validate"})
        cmd = captured["cmd"]
        # The prompt must NOT be an argv token (a leading "---" would make `claude -p` exit 1) —
        # it is passed on stdin. `-p` is immediately followed by a flag, never the prompt.
        assert cmd[cmd.index("-p") + 1].startswith("--"), "prompt must not be an argv token"
        return cmd, captured["input"]                   # (cmd, prompt-from-stdin)

    def test_prompt_on_stdin_not_argv(self):
        # Gate-5 root cause: the prompt begins with the SKILL.md "---" frontmatter; as an argv token
        # `claude -p ---...` exits 1. It must go on STDIN; no argv token may start with "---".
        cmd, prompt = self._capture_cmd()
        self.assertTrue(prompt, "prompt must be passed (on stdin)")
        self.assertFalse(any(tok.startswith("---") for tok in cmd),
                         "no argv token may start with --- (claude -p would exit 1)")
        self.assertIn("EMET", prompt)                    # the skill content rode in on stdin

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
        self.assertEqual(H._emet_timeout_s(), 420)       # accommodates a real Thorough run

    def test_env_override(self):
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "90"
        self.assertEqual(H._emet_timeout_s(), 90)

    def test_floor_and_bad_value(self):
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "5"
        self.assertEqual(H._emet_timeout_s(), 30)        # floored
        os.environ["SAPPHIRE_EMET_TIMEOUT_S"] = "garbage"
        self.assertEqual(H._emet_timeout_s(), 420)       # bad → default


if __name__ == "__main__":
    unittest.main()
