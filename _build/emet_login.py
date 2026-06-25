"""Auto-login the dedicated EMET browser profile so front-end Live runs land REAL PMIDs.

Reads creds from the environment (sourced from the gitignored RohanOnly/emet_creds.env):
  SAPPHIRE_EMET_USER, SAPPHIRE_EMET_PASS, SAPPHIRE_EMET_PROFILE  (+ optional SAPPHIRE_EMET_HEADLESS).

SECURITY: the password is read from the env and typed into the form ONLY — it is NEVER printed,
logged, or written anywhere. On any failure the message contains no credential material.

Exit codes:  0 = authenticated session persisted in the profile · 2 = SSO/2FA/selector failure
(use the manual route: `bash _build/emet_login.sh --manual`) · 3 = missing env · 4 = playwright
not installed (run via _build/emet_login.sh, which bootstraps a venv).
"""
from __future__ import annotations

import os
import sys

_SSO_HOSTS = ("accounts.google.com", "login.microsoftonline", "okta", "duosecurity",
              "shibboleth", ".yale.edu", "auth0")
_MFA_HINTS = ("duosecurity", "2fa", "mfa", "/verify", "challenge")


def _authed(url: str) -> bool:
    return ("benchsci.com" in url and "login" not in url
            and "id.summit" not in url and "auth" not in url)


def main() -> int:
    user = (os.environ.get("SAPPHIRE_EMET_USER") or "").strip()
    pw = os.environ.get("SAPPHIRE_EMET_PASS") or ""          # never printed
    profile = (os.environ.get("SAPPHIRE_EMET_PROFILE") or "").strip()
    headless = (os.environ.get("SAPPHIRE_EMET_HEADLESS") or "1") not in ("0", "false", "False")
    if not (user and pw and profile):
        print("ERROR: set SAPPHIRE_EMET_USER / SAPPHIRE_EMET_PASS / SAPPHIRE_EMET_PROFILE "
              "(source RohanOnly/emet_creds.env).", file=sys.stderr)
        return 3
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed — run via _build/emet_login.sh (it bootstraps a venv).",
              file=sys.stderr)
        return 4

    os.makedirs(profile, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://emet.benchsci.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            if _authed(page.url):
                print("Already authenticated — profile holds a live session.")
                return 0
            if any(h in page.url for h in _SSO_HOSTS):
                print(f"SSO provider detected ({page.url.split('/')[2]}) — automated password login "
                      "isn't possible. Use the MANUAL route: bash _build/emet_login.sh --manual",
                      file=sys.stderr)
                return 2
            # Dismiss a cookie-consent overlay if present (it can block the submit click).
            for s in ("button:has-text('Allow All')", "button:has-text('Accept')",
                      "button:has-text('Accept All')"):
                b = page.query_selector(s)
                if b:
                    try:
                        b.click(timeout=2000)
                    except Exception:
                        pass
                    break
            email_sel = next((s for s in ("input[type=email]", "input[name=email]", "input#email",
                                          "input[name=username]") if page.query_selector(s)), None)
            if not email_sel:
                print("No email field (likely SSO/redirect). Use: bash _build/emet_login.sh --manual",
                      file=sys.stderr)
                return 2
            page.fill(email_sel, user)
            pw_sel = next((s for s in ("input[type=password]", "input[name=password]", "input#password")
                           if page.query_selector(s)), None)
            if pw_sel is None:
                # Multi-step form: click Continue/Next to reveal the password field, then re-find it.
                for s in ("button:has-text('Continue')", "button:has-text('Next')", "button[type=submit]"):
                    b = page.query_selector(s)
                    if b:
                        b.click()
                        page.wait_for_timeout(2500)
                        break
                pw_sel = next((s for s in ("input[type=password]", "input[name=password]",
                                           "input#password") if page.query_selector(s)), None)
            if pw_sel is None:
                print("No password field (SSO/2FA). Use: bash _build/emet_login.sh --manual",
                      file=sys.stderr)
                return 2
            page.fill(pw_sel, pw)                            # value never printed
            for s in ("button:has-text('Log In')", "button:has-text('Log in')",
                      "button:has-text('Sign in')", "button:has-text('Continue')", "button[type=submit]"):
                b = page.query_selector(s)
                if b:
                    b.click()
                    break
            page.wait_for_timeout(7000)
            # One-time Auth0 custom-prompt: a Terms & Conditions consent (terms_consent +
            # privacy_consent checkboxes → Continue). Accept it so the session can complete; it
            # won't reappear once the profile holds the granted session.
            if "custom-prompt" in page.url or page.query_selector("input[name=terms_consent]"):
                for name in ("terms_consent", "privacy_consent"):
                    box = page.query_selector(f"input[name={name}]")
                    if box and not box.is_checked():
                        try:
                            box.check(timeout=2000)
                        except Exception:
                            box.click(timeout=2000)
                for s in ("button:has-text('Continue')", "button[type=submit]"):
                    b = page.query_selector(s)
                    if b:
                        b.click()
                        break
                page.wait_for_timeout(7000)
            if any(h in page.url for h in _MFA_HINTS):
                print("2FA/MFA challenge — automated login can't complete. Use the manual route.",
                      file=sys.stderr)
                return 2
            if any(h in page.url for h in _MFA_HINTS):
                print("2FA/MFA challenge — automated login can't complete. Use the manual route.",
                      file=sys.stderr)
                return 2
            if _authed(page.url):
                print("Login OK — authenticated session persisted in the profile.")
                return 0
            print("Login did not reach the app (check creds / SSO). Use: bash _build/emet_login.sh --manual",
                  file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"ERROR during login: {type(exc).__name__} (no credential shown). "
                  "Use: bash _build/emet_login.sh --manual", file=sys.stderr)
            return 2
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
