"""The EMET seam the harness's `emet-playwright` dispatch calls. Injectable runner so it is
tested offline; the live default drives Claude+Playwright. MCP-swappable: when the EMET-MCP
lands, only `_default_runner` changes."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from harness.errors import escalate
from .adapter import normalize_emet

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_SKILL = ".claude/skills/emet-runner/SKILL.md"


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


def _default_runner(inputs) -> dict:
    """LIVE path: ask Claude (with the emet-runner skill + Playwright) to drive EMET and return
    one envelope. Requires an interactive, logged-in BenchSci session. Injectable; not used in tests."""
    skill = (ROOT / _SKILL)
    prompt = (
        (skill.read_text(encoding="utf-8") if skill.exists() else "Drive EMET per emet_protocol.md.")
        + f"\n\n## QUERY INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Drive EMET via Playwright per the protocol. Public identifiers only. If a login screen "
        'appears, return exactly {"login_required": true}. Otherwise return ONLY the EMET envelope object.'
    )
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"emet runner (claude) exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body
