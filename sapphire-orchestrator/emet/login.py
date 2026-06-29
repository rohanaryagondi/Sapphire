"""One-time BenchSci login helper — run once headed to persist a Playwright profile.

Usage:
    python -m emet.login [--profile PATH] [--url URL]

The profile directory is gitignored under RohanOnly/ (see .gitignore).
Playwright is imported LAZILY inside `_launch_and_wait` so importing this module
never pulls in Playwright — it remains a standalone CLI tool only.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root

# Default persistent Chromium profile for BenchSci (gitignored under RohanOnly/).
DEFAULT_PROFILE = ROOT / "RohanOnly" / "benchsci_profile"

_DEFAULT_URL = "https://emet.benchsci.com/"

# URL fragments that indicate an SSO/login gate rather than the authenticated app.
_LOGIN_FRAGMENTS = (
    "id.summit.benchsci.com",
    "accounts.google.com",
    "login.microsoftonline",
    "okta",
    "duosecurity",
)


def _is_authenticated_url(url: str) -> bool:
    """True when `url` looks like an authenticated BenchSci page (not a login/SSO redirect).

    An authenticated URL contains 'benchsci.com' and does NOT contain any known SSO
    host fragment.  Returns False for empty or non-BenchSci URLs.
    """
    if not url or "benchsci.com" not in url:
        return False
    return not any(frag in url for frag in _LOGIN_FRAGMENTS)


def _launch_and_wait(profile: Path, url: str) -> int:
    """Open a headed Playwright browser at `profile`, navigate to `url`, and poll until the
    user has authenticated.  Returns an exit code:
        0 — session persisted successfully
        2 — interrupted before auth (KeyboardInterrupt or browser closed)
        3 — playwright not installed
    """
    try:
        from playwright.sync_api import sync_playwright  # lazy import
    except ImportError:
        print(
            "playwright is not installed.\n"
            "Install it with:\n"
            "    pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 3

    profile.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(profile),
                headless=False,
            )
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(url)

                # Poll until authenticated.
                while True:
                    current_url = page.url
                    if _is_authenticated_url(current_url):
                        print(f"Session persisted to: {profile}")
                        # Sleep briefly to ensure cookies flush before closing.
                        page.wait_for_timeout(2000)
                        ctx.close()
                        return 0
                    print("Waiting for BenchSci login...", flush=True)
                    page.wait_for_timeout(1500)
            except Exception:
                # Browser was closed by the user before auth completed.
                ctx.close()
                print(
                    "Browser closed before authentication was detected. "
                    "Session NOT persisted.",
                    file=sys.stderr,
                )
                return 2
    except KeyboardInterrupt:
        print(
            "\nInterrupted before authentication. Session NOT persisted.",
            file=sys.stderr,
        )
        return 2


def main(argv=None) -> int:
    """CLI entry point: ``python -m emet.login``."""
    ap = argparse.ArgumentParser(
        prog="python -m emet.login",
        description=(
            "One-time BenchSci login — opens a headed browser so you can log in. "
            "The session is persisted to the profile directory and reused on future runs."
        ),
    )
    ap.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE),
        help=f"Persistent Chromium profile directory (default: {DEFAULT_PROFILE})",
    )
    ap.add_argument(
        "--url",
        default=_DEFAULT_URL,
        help=f"BenchSci URL to navigate to (default: {_DEFAULT_URL})",
    )
    args = ap.parse_args(argv)
    return _launch_and_wait(Path(args.profile), args.url)


if __name__ == "__main__":
    raise SystemExit(main())
