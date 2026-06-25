"""The EMET seam the harness's `emet-playwright` dispatch calls. Injectable runner so it is
tested offline; the live default drives Claude+Playwright. MCP-swappable: when the EMET-MCP
lands, only `_default_runner` changes.

Live front-end EMET (real PMIDs)
--------------------------------
A detached `claude -p` would otherwise drive a FRESH, unauthenticated Playwright browser that
cannot reach the user's BenchSci session → tool-failure, never real PMIDs. The fix: pin the
subprocess's Playwright MCP to a DEDICATED authenticated browser via env (see `_emet_mcp_config`):

  • $SAPPHIRE_EMET_CDP     — CDP endpoint of an already-running authenticated browser
                             (the `_build/emet_login.sh` Chrome). Preferred — no profile-lock.
  • $SAPPHIRE_EMET_PROFILE — a dedicated persistent Chrome profile authenticated once
                             (the login browser must be CLOSED first; Chrome locks a user-data-dir).

When NEITHER is set (or the session has expired → login screen) the runner returns
`{"login_required": True}` → the handler escalates → the EMET agent abstains HONESTLY. Real PMIDs
only ever come from a genuinely reachable authenticated session; nothing is fabricated. The
credential-at-rest (the profile on disk) is an internal-only artifact, gitignored under RohanOnly/.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from harness.errors import escalate
from .adapter import normalize_emet

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_SKILL = ".claude/skills/emet-runner/SKILL.md"
# EMET driving (agentic BenchSci Thorough research via playwright-mcp) is hard — it needs a capable
# model and must NOT inherit the cheap-personas haiku lever. Default sonnet; $SAPPHIRE_EMET_MODEL overrides.
_EMET_MODEL_DEFAULT = "claude-sonnet-4-6"
# Gitignored, internal-only EMET tester credentials (SAPPHIRE_EMET_USER / _PASS / _PROFILE).
_EMET_CREDS = ROOT / "RohanOnly" / "emet_creds.env"

# The Playwright MCP tools the EMET runner is allowed to use (server name "playwright" in the
# generated config → mcp__playwright__<tool>). Scoped to what the emet-runner skill drives.
_PLAYWRIGHT_TOOLS = ",".join(
    "mcp__playwright__" + t for t in (
        "browser_navigate", "browser_click", "browser_type", "browser_snapshot",
        "browser_wait_for", "browser_tabs", "browser_press_key", "browser_evaluate",
        "browser_take_screenshot",
    )
)


def emet_handler(contract, inputs, *, runner=None) -> dict:
    run = runner or _default_runner
    raw = run(inputs)
    if isinstance(raw, dict) and raw.get("login_required"):
        raise escalate("login-required", "BenchSci login screen — please re-authenticate, then retry")
    return normalize_emet(raw)


def make_emet_handler(runner=None):
    """Return a 2-arg (contract, inputs) handler for ctx['emet_handler']."""
    def _handler(contract, inputs):
        return emet_handler(contract, inputs, runner=runner)
    return _handler


def _cdp_reachable(endpoint: str, timeout: float = 1.5) -> bool:
    """True if a CDP browser answers at `endpoint` (GET /json/version). stdlib urllib only."""
    try:
        import urllib.request
        url = endpoint.rstrip("/") + "/json/version"
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (localhost)
            return getattr(r, "status", r.getcode()) == 200
    except Exception:
        return False


def _resolve_emet_cdp(probe=_cdp_reachable) -> str | None:
    """The CDP endpoint of a VISIBLE authenticated browser to drive EMET in, or None.

    Order: explicit `$SAPPHIRE_EMET_CDP`, else AUTO-DETECT a reachable browser on the default
    local debug port (`$SAPPHIRE_EMET_CDP_PORT` or 9222 — i.e. `_build/emet_login.sh --manual`).
    Auto-detect is why a Live run "just works" + stays WATCHABLE: the EMET call opens a visible
    tab in the already-open authenticated browser, instead of a separate invisible headless one.
    """
    cdp = (os.environ.get("SAPPHIRE_EMET_CDP") or "").strip()
    if cdp:
        return cdp
    port = (os.environ.get("SAPPHIRE_EMET_CDP_PORT") or "9222").strip()
    cand = f"http://localhost:{port}"
    return cand if probe(cand) else None


def _headless_profile_opt_in() -> bool:
    """The headless `--user-data-dir` browser is INVISIBLE (you can't watch the EMET run) and was
    the silent failure mode in Gate-5 — so it is now strictly OPT-IN via $SAPPHIRE_EMET_ALLOW_HEADLESS."""
    return (os.environ.get("SAPPHIRE_EMET_ALLOW_HEADLESS") or "").strip().lower() in ("1", "true", "yes")


def _emet_mcp_config(probe=_cdp_reachable) -> dict | None:
    """Build a Playwright-MCP config pinned to an authenticated browser, or None → honest abstain.

    Preference (Task-1 re-architecture): drive the **shared VISIBLE authenticated browser via CDP**
    so the EMET call is watchable in a second tab and reuses the live session →
      1. explicit `$SAPPHIRE_EMET_CDP`, or auto-detected CDP on the default port (visible browser);
      2. ONLY if `$SAPPHIRE_EMET_ALLOW_HEADLESS` is set: a dedicated persistent `$SAPPHIRE_EMET_PROFILE`
         (a SEPARATE, INVISIBLE headless browser — opt-in, never the silent default);
      3. else None → the EMET agent abstains honestly (run `_build/emet_login.sh --manual` first).
    """
    args = ["-y", "@playwright/mcp@latest", "--browser", "chromium"]
    cdp = _resolve_emet_cdp(probe)
    profile = (os.environ.get("SAPPHIRE_EMET_PROFILE") or "").strip()
    if cdp:
        args += ["--cdp-endpoint", cdp]                       # VISIBLE shared browser — watchable
    elif profile and _headless_profile_opt_in():
        args += ["--user-data-dir", profile]                  # opt-in INVISIBLE headless fallback
    else:
        return None
    return {"mcpServers": {"playwright": {"command": "npx", "args": args}}}


def _emet_autologin_available() -> bool:
    """True when dedicated-profile auto-login creds are present (the gitignored
    RohanOnly/emet_creds.env, or SAPPHIRE_EMET_USER+_PASS in env). When available the runner is
    AUTHORIZED to sign into BenchSci for THIS dedicated tester profile (relaxing the skill's
    never-auto-login rule for this profile only, per the task brief). The password is read by the
    runner agent from the gitignored file at login time — never by this process, never logged."""
    if _EMET_CREDS.exists():
        return True
    return bool((os.environ.get("SAPPHIRE_EMET_USER") or "").strip()
                and (os.environ.get("SAPPHIRE_EMET_PASS") or "").strip())


def _emet_timeout_s() -> int:
    """Bounded per-run EMET timeout (seconds). $SAPPHIRE_EMET_TIMEOUT_S overrides; default 420,
    floor 30 — a real EMET *Thorough* run (agentic multi-stage research) takes minutes, so the
    default must accommodate it (Gate-5: a 240s cap timed out a working run). Still bounded so a
    genuinely stuck run abstains visibly instead of blocking the firm indefinitely."""
    try:
        return max(30, int(os.environ.get("SAPPHIRE_EMET_TIMEOUT_S", "420")))
    except (ValueError, TypeError):
        return 420


def _default_runner(inputs) -> dict:
    """LIVE path: drive EMET via a `claude -p` subprocess whose Playwright MCP is pinned to a
    DEDICATED authenticated browser (CDP or persistent profile — see `_emet_mcp_config`). Returns
    one EMET envelope, or `{"login_required": True}` when no authenticated source is configured
    or the session has expired (→ honest abstain). Injectable; not used in tests."""
    cfg = _emet_mcp_config()
    if cfg is None:
        # No dedicated authenticated browser configured → honest abstain (NOT a fresh-browser
        # tool-failure). Run `_build/emet_login.sh` once, then set $SAPPHIRE_EMET_CDP/_PROFILE.
        return {"login_required": True}

    autologin = _emet_autologin_available()
    # Login behaviour: with creds available, AUTO-LOGIN is authorized for this dedicated tester
    # profile — the agent reads the password itself from the gitignored creds file and signs in
    # (the password never touches this process / argv / logs). Without creds → honest abstain.
    login_clause = (
        "If a BenchSci login screen appears, AUTO-LOGIN IS AUTHORIZED for this dedicated tester "
        "profile: read the credentials from RohanOnly/emet_creds.env (keys SAPPHIRE_EMET_USER and "
        "SAPPHIRE_EMET_PASS), sign in, then continue the query. Never echo the password anywhere. "
        'If login still fails, return exactly {"login_required": true}.'
        if autologin else
        'If a login screen appears, return exactly {"login_required": true}.'
    )
    skill = (ROOT / _SKILL)
    prompt = (
        (skill.read_text(encoding="utf-8") if skill.exists() else "Drive EMET per emet_protocol.md.")
        + f"\n\n## QUERY INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Drive EMET via Playwright per the protocol. Public identifiers only. "
        + login_clause +
        " Otherwise return ONLY the EMET envelope object."
    )
    # The agent needs Read to load the gitignored creds file for the authorized auto-login.
    allowed_tools = _PLAYWRIGHT_TOOLS + (",Read" if autologin else "")
    # Write the MCP config to a temp file for --mcp-config (env-var paths already resolved).
    fd, cfg_path = tempfile.mkstemp(suffix=".json", prefix="emet_mcp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        # CRITICAL (Gate-5 root cause): the prompt begins with the emet-runner SKILL.md YAML
        # frontmatter ("---"), and `claude -p <prompt>` parses a leading "---" as an unknown CLI
        # option → exits 1 → EMET never runs. So pass the prompt on STDIN, NOT as an argv token.
        cmd = [
            CLAUDE_BIN, "-p", "--output-format", "json",
            # Pin the subprocess to ONLY our authenticated Playwright MCP (no other MCP servers).
            "--mcp-config", cfg_path, "--strict-mcp-config",
            "--allowedTools", allowed_tools,
        ]
        # EMET runs on its OWN capable model, DECOUPLED from the cheap-personas CLAUDE_MODEL lever
        # (Gate-5: driving BenchSci's agentic Thorough UI via playwright-mcp is hard — haiku
        # tool-failed at it, even though the cheap-live profile runs personas on haiku). Default to
        # a capable model; $SAPPHIRE_EMET_MODEL overrides. We deliberately do NOT read CLAUDE_MODEL.
        model = (os.environ.get("SAPPHIRE_EMET_MODEL") or _EMET_MODEL_DEFAULT).strip()
        if model:
            cmd += ["--model", model]
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=_emet_timeout_s(), cwd=str(ROOT))
    finally:
        try:
            os.unlink(cfg_path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(f"emet runner (claude) exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body
