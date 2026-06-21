"""Per-kind dispatch backends (spec §A.3). All backends are injectable so the
harness is tested offline (no live claude, no AWS). dispatch_claude mirrors
serve.py:_run_live's `claude -p --json-schema` invocation + parsing."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .errors import HarnessEscalation  # noqa: F401  (re-exported for handlers)

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def _read_spec(spec) -> str:
    if not spec:
        return ""
    p = ROOT / spec
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(contract, inputs) -> str:
    return (
        f"{_read_spec(contract.spec)}\n\n"
        f"## INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Return ONLY the structured object (the JSON schema is enforced). Do not add commentary."
    )


def dispatch_claude(contract, inputs, runner=None) -> dict:
    cmd = [
        CLAUDE_BIN, "-p", build_prompt(contract, inputs),
        "--output-format", "json",
        "--json-schema", json.dumps(contract.output_schema or {}),
        "--allowedTools", ",".join(contract.tools_allowed),
    ]
    if runner is None:
        def runner(cmd):
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=contract.timeout_s, cwd=str(ROOT))
    proc = runner(cmd)
    if getattr(proc, "returncode", 0) != 0:
        raise RuntimeError(f"claude exited {getattr(proc, 'returncode', '?')}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body


def dispatch_qmodels(contract, inputs, client=None) -> dict:
    if client is None:
        from qmodels.client import QModelsClient
        client = QModelsClient()
    tool_id = inputs.get("tool_id", contract.id)
    payload = inputs.get("inputs", inputs)
    return client.call(tool_id, payload)


def dispatch_python(contract, inputs, fn) -> dict:
    if fn is None:
        raise RuntimeError(f"no python fn registered for {contract.id}")
    return fn(inputs)


def dispatch_emet(contract, inputs, handler) -> dict:
    if handler is None:
        raise RuntimeError("emet handler not registered (workstream A wires emet-runner)")
    return handler(contract, inputs)


def dispatch(contract, inputs, ctx=None) -> dict:
    ctx = ctx or {}
    kind = contract.kind
    if kind == "claude-subagent":
        return dispatch_claude(contract, inputs, runner=ctx.get("runner"))
    if kind == "qmodels-delegate":
        return dispatch_qmodels(contract, inputs, client=ctx.get("qmodels_client"))
    if kind == "python":
        fn = (ctx.get("python_fns") or {}).get(contract.id) or ctx.get("python_fn")
        return dispatch_python(contract, inputs, fn)
    if kind == "emet-playwright":
        return dispatch_emet(contract, inputs, ctx.get("emet_handler"))
    raise RuntimeError(f"unknown dispatch kind {kind!r}")
