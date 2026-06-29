"""Tests for EMET persistent-session plumbing.

Tests session-detection and honest-abstain paths by mocking Playwright.
No live browser required — all tests must pass in CI.
"""
from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import emet.capture as C
from emet.login import DEFAULT_PROFILE, _is_authenticated_url, main, _launch_and_wait


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MISSING = object()


def _make_fake_playwright_module(page_url="https://emet.benchsci.com/"):
    """Build a fake playwright.sync_api module."""
    fake_page = MagicMock()
    fake_page.url = page_url
    fake_page.goto.return_value = None
    fake_page.wait_for_timeout.return_value = None

    fake_ctx = MagicMock()
    fake_ctx.pages = [fake_page]
    fake_ctx.close.return_value = None

    fake_pw = MagicMock()
    fake_pw.chromium.launch_persistent_context.return_value = fake_ctx

    fake_cm = MagicMock()
    fake_cm.__enter__ = lambda s: fake_pw
    fake_cm.__exit__ = MagicMock(return_value=False)

    fake_mod = types.ModuleType("playwright.sync_api")
    fake_mod.sync_playwright = lambda: fake_cm
    return fake_mod


# ---------------------------------------------------------------------------
# TestBenchSciProfileConstant
# ---------------------------------------------------------------------------

class TestBenchSciProfileConstant(unittest.TestCase):

    def test_default_profile_under_rohanonly(self):
        self.assertIn("RohanOnly", str(C.BENCHSCI_PROFILE))
        self.assertEqual(C.BENCHSCI_PROFILE.name, "benchsci_profile")

    def test_capture_and_login_agree_on_default(self):
        self.assertEqual(str(C.BENCHSCI_PROFILE), str(DEFAULT_PROFILE))


# ---------------------------------------------------------------------------
# TestProfileHasSession
# ---------------------------------------------------------------------------

class TestProfileHasSession(unittest.TestCase):
    """Tests `_profile_has_session` — a pure function, no mocks needed."""

    def test_none_returns_false(self):
        self.assertFalse(C._profile_has_session(None))

    def test_nonexistent_path_returns_false(self):
        self.assertFalse(C._profile_has_session("/tmp/does_not_exist_sapphire_test_xyz"))

    def test_empty_dir_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(C._profile_has_session(d))

    def test_cookies_file_returns_true(self):
        # The check gates on Default/Cookies — present only after a real authenticated session.
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Default").mkdir()
            (Path(d) / "Default" / "Cookies").write_bytes(b"")   # simulate a real session
            self.assertTrue(C._profile_has_session(d))

    def test_default_subdir_without_cookies_returns_false(self):
        # An interrupted login creates Default/ but NOT Default/Cookies → abstain, not attempt.
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Default").mkdir()
            self.assertFalse(C._profile_has_session(d))


# ---------------------------------------------------------------------------
# TestCaptureEmetAbstainNoSession
# ---------------------------------------------------------------------------

class TestCaptureEmetAbstainNoSession(unittest.TestCase):
    """Tests `capture_emet()` early-abort without launching a browser."""

    def _run_abstain(self, profile_path):
        """Run capture_emet with CDP stripped from env and a nonexistent/empty profile."""
        env_patch = {k: v for k, v in __import__("os").environ.items()
                     if k not in ("SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE")}
        with mock.patch.dict("os.environ", env_patch, clear=True):
            with mock.patch.object(C, "BENCHSCI_PROFILE", Path(profile_path)):
                return C.capture_emet("test query", "TSC2")

    def test_missing_profile_returns_login_required(self):
        result = self._run_abstain("/tmp/nonexistent_benchsci_profile_xyz")
        self.assertTrue(result.get("login_required"))

    def test_abstain_message_mentions_emet_login(self):
        result = self._run_abstain("/tmp/nonexistent_benchsci_profile_xyz")
        self.assertIn("python -m emet.login", result.get("reason", ""))

    def test_never_fabricates_evidence_on_abstain(self):
        result = self._run_abstain("/tmp/nonexistent_benchsci_profile_xyz")
        self.assertNotIn("evidence", result)
        self.assertNotIn("emet_workflow", result)

    def test_interrupted_login_dir_also_abstains(self):
        # A dir with Default/ but no Default/Cookies = interrupted login → abstain, not launch.
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Default").mkdir()   # skeleton written by launch_persistent_context
            # No Default/Cookies → session was never completed
            env_patch = {k: v for k, v in __import__("os").environ.items()
                         if k not in ("SAPPHIRE_EMET_CDP", "SAPPHIRE_EMET_PROFILE")}
            with mock.patch.dict("os.environ", env_patch, clear=True):
                with mock.patch.object(C, "BENCHSCI_PROFILE", Path(d)):
                    result = C.capture_emet("test query", "TSC2")
        self.assertTrue(result.get("login_required"))
        self.assertIn("python -m emet.login", result.get("reason", ""))


# ---------------------------------------------------------------------------
# TestLoginModuleInterface
# ---------------------------------------------------------------------------

class TestLoginModuleInterface(unittest.TestCase):
    """Tests the public interface of emet/login.py."""

    def test_is_authenticated_url_positive(self):
        self.assertTrue(_is_authenticated_url("https://emet.benchsci.com/"))
        self.assertTrue(_is_authenticated_url("https://emet.benchsci.com/chat/abc"))

    def test_is_authenticated_url_sso_negative(self):
        self.assertFalse(_is_authenticated_url("https://id.summit.benchsci.com/login"))
        self.assertFalse(_is_authenticated_url("https://accounts.google.com/oauth"))

    def test_default_profile_path(self):
        self.assertEqual(DEFAULT_PROFILE.name, "benchsci_profile")
        self.assertIn("RohanOnly", str(DEFAULT_PROFILE))

    def test_main_help_exits_0(self):
        """main() --help exits cleanly with code 0 (argparse contract)."""
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_playwright_not_imported_at_module_level(self):
        # Temporarily remove playwright from sys.modules to verify emet.login can be imported without it.
        pw_mods = {k: sys.modules.pop(k) for k in list(sys.modules) if "playwright" in k}
        try:
            import emet.login as lm
            importlib.reload(lm)   # re-import with playwright absent
        except ImportError as e:
            self.fail(f"emet.login imports playwright at module level: {e}")
        finally:
            sys.modules.update(pw_mods)


# ---------------------------------------------------------------------------
# TestLoginLaunchAbstain
# ---------------------------------------------------------------------------

class TestLoginLaunchAbstain(unittest.TestCase):
    """Tests `_launch_and_wait` with mocked playwright."""

    def _with_fake_playwright(self, page_url):
        return mock.patch.dict(
            "sys.modules",
            {"playwright.sync_api": _make_fake_playwright_module(page_url)},
        )

    def test_authenticated_url_returns_0(self):
        with tempfile.TemporaryDirectory() as d:
            with self._with_fake_playwright("https://emet.benchsci.com/"):
                rc = _launch_and_wait(Path(d), "https://emet.benchsci.com/")
        self.assertEqual(rc, 0)

    def test_missing_playwright_returns_3(self):
        # Set playwright.sync_api to None so 'from playwright.sync_api import ...' raises ImportError
        saved = sys.modules.get("playwright.sync_api", _MISSING)
        sys.modules["playwright.sync_api"] = None
        try:
            with tempfile.TemporaryDirectory() as d:
                rc = _launch_and_wait(Path(d), "https://emet.benchsci.com/")
            self.assertEqual(rc, 3)
        finally:
            if saved is _MISSING:
                sys.modules.pop("playwright.sync_api", None)
            else:
                sys.modules["playwright.sync_api"] = saved

    def test_profile_dir_created_on_launch(self):
        with self._with_fake_playwright("https://emet.benchsci.com/"):
            with tempfile.TemporaryDirectory() as parent:
                profile = Path(parent) / "new_profile"
                self.assertFalse(profile.exists())
                _launch_and_wait(profile, "https://emet.benchsci.com/")
                self.assertTrue(profile.exists())

    def test_browser_closed_before_auth_returns_2(self):
        """A page-op Exception while still on the SSO URL → rc=2, NOT a false 'persisted' message.

        This pins the contract for the 'browser closed during login' path: if the user
        closes the window while still on the SSO page, _launch_and_wait must return 2
        (not-persisted) and must NOT print 'Session persisted'."""
        fake_page = MagicMock()
        fake_page.url = "https://id.summit.benchsci.com/login"   # still on SSO, not authenticated
        fake_page.goto.return_value = None
        # Browser closed while polling: wait_for_timeout raises before auth URL is reached.
        fake_page.wait_for_timeout.side_effect = Exception("Target page closed")

        fake_ctx = MagicMock()
        fake_ctx.pages = [fake_page]
        fake_ctx.close.return_value = None

        fake_pw = MagicMock()
        fake_pw.chromium.launch_persistent_context.return_value = fake_ctx

        fake_cm = MagicMock()
        fake_cm.__enter__ = lambda s: fake_pw
        fake_cm.__exit__ = MagicMock(return_value=False)

        fake_mod = types.ModuleType("playwright.sync_api")
        fake_mod.sync_playwright = lambda: fake_cm

        with mock.patch.dict("sys.modules", {"playwright.sync_api": fake_mod}):
            with tempfile.TemporaryDirectory() as d:
                rc = _launch_and_wait(Path(d), "https://emet.benchsci.com/")
        self.assertEqual(rc, 2)

    def test_exception_during_cookie_flush_does_not_mislabel_success(self):
        """If the browser closes during the 2-second cookie-flush wait AFTER auth is detected,
        _launch_and_wait must still return 0 (authenticated flag was already set True)."""
        flush_calls = [0]

        def _wait_for_timeout(ms):
            # First call (flush): auth URL was already detected, now simulate close.
            flush_calls[0] += 1
            if flush_calls[0] == 1 and ms == 2000:
                raise Exception("Target page closed during flush")

        fake_page = MagicMock()
        fake_page.url = "https://emet.benchsci.com/"          # authenticated URL
        fake_page.goto.return_value = None
        fake_page.wait_for_timeout.side_effect = _wait_for_timeout

        fake_ctx = MagicMock()
        fake_ctx.pages = [fake_page]
        fake_ctx.close.return_value = None

        fake_pw = MagicMock()
        fake_pw.chromium.launch_persistent_context.return_value = fake_ctx

        fake_cm = MagicMock()
        fake_cm.__enter__ = lambda s: fake_pw
        fake_cm.__exit__ = MagicMock(return_value=False)

        fake_mod = types.ModuleType("playwright.sync_api")
        fake_mod.sync_playwright = lambda: fake_cm

        with mock.patch.dict("sys.modules", {"playwright.sync_api": fake_mod}):
            with tempfile.TemporaryDirectory() as d:
                rc = _launch_and_wait(Path(d), "https://emet.benchsci.com/")
        self.assertEqual(rc, 0, "authenticated before flush-exception → must return 0 not 2")


if __name__ == "__main__":
    unittest.main()
