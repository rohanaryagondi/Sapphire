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


def _agent_timeout(contract_timeout_s) -> int:
    """The per-agent subprocess timeout (seconds), with an optional operator CAP.

    Defaults to the contract's declared `timeout_s`, but `$SAPPHIRE_AGENT_TIMEOUT_S` caps it
    (min of the two) so a fleet of live `claude -p` agents can't each block for the full
    declared budget — a stuck agent hits the cap and abstains visibly. Floor 30s. Unset → the
    contract value unchanged (backward-compatible)."""
    base = contract_timeout_s if isinstance(contract_timeout_s, (int, float)) else 300
    cap_env = (os.environ.get("SAPPHIRE_AGENT_TIMEOUT_S") or "").strip()
    if cap_env:
        try:
            return max(30, min(int(base), int(cap_env)))
        except (ValueError, TypeError):
            pass
    return int(base)

# Opt-1 (dispatch-optimization): identical across every agent and FIRST in the prompt, so the
# 5-min prompt cache reuses this user-message prefix across the fan-out. Keep it short + STABLE
# (no per-call/per-agent text) — any drift busts the shared cache.
SHARED_PREAMBLE = (
    "You are one specialist agent in Sapphire's CNS drug-discovery firm. Answer ONLY from your "
    "spec + the INPUTS below; return ONLY the structured object the JSON schema enforces, with no "
    "commentary. Public identifiers only; never fabricate — abstain honestly if you cannot answer."
)


def _read_spec(spec) -> str:
    if not spec:
        return ""
    p = ROOT / spec
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(contract, inputs) -> str:
    return (
        f"{SHARED_PREAMBLE}\n\n"
        f"{_read_spec(contract.spec)}\n\n"
        f"## INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Return ONLY the structured object (the JSON schema is enforced). Do not add commentary."
    )


def _context_flags() -> list:
    """Opt-1 cache/cost flags for a sub-agent `claude -p` call (measured, see the report):

      --setting-sources user                  → do NOT load the project CLAUDE.md (~5k tok/agent;
                                                the agent's spec is already in its prompt).
      --exclude-dynamic-system-prompt-sections → move cwd/env/git/memory-paths out of the system
                                                prefix → STABLE prefix → warm cache_creation→0.

    Both keep the cacheable Claude Code preamble (unlike a full --system-prompt override, which
    measured cache_read→0). Opt out with SAPPHIRE_DISPATCH_FULL_CONTEXT=1 (restores the old
    full-context behavior) — escape hatch if an agent ever needs project memory/settings.
    """
    if os.environ.get("SAPPHIRE_DISPATCH_FULL_CONTEXT", "").strip() in ("1", "true", "yes"):
        return []
    return ["--setting-sources", "user", "--exclude-dynamic-system-prompt-sections"]


# Labeled simulated model reasoning (SAPPHIRE_SIMULATE_MODELS=1). The real `claude -p` calls are
# slow/can hang; for a fast, fully-working demo the claude-subagent reasoning (personas + claude
# fact agents) is replaced by a LABELED placeholder. HONESTY: every simulated field carries this
# marker + provenance 'simulated' so it can never be mistaken for a real verdict. Real EMET/moat/
# seam agents do NOT pass through dispatch_claude, so they stay genuinely REAL.
SIMULATE_MARKER = "🧪 simulated model — real reasoning pending"


def _simulate_models_on() -> bool:
    return (os.environ.get("SAPPHIRE_SIMULATE_MODELS") or "").strip() not in ("", "0", "false", "False")


def _simulate_claude(contract, inputs) -> dict:
    """A schema-valid, provenance='simulated', clearly-marked stand-in for one claude-subagent call.

    Detects the two shapes the firm uses (persona verdict / fact-agent dossier) and fills a generic
    fallback otherwise; only emits keys the schema allows (schemas are additionalProperties:false)."""
    sch = contract.output_schema or {}
    props = sch.get("properties") or {}
    required = set(sch.get("required") or [])
    cand = inputs.get("candidate") or inputs.get("target") or ""

    # Persona / roundtable verdict shape.
    if "stance" in props and "conviction" in props:
        out = {
            "persona": inputs.get("persona", "") or cand or "persona",
            "stance": "conditional",
            "conviction": 2,
            "rationale": f"{SIMULATE_MARKER} (no real model call was made; placeholder verdict).",
            "fact_claims": [],
            "provenance": "simulated",
        }
        return {k: v for k, v in out.items() if k in props or k in required}

    # Fact-agent shape: {candidate, facts:[{value, source, tier, ...}]}.
    if "facts" in props:
        fitems = ((props.get("facts") or {}).get("items") or {}).get("properties") or {}
        fact = {"value": f"{SIMULATE_MARKER} (agent {contract.id})",
                "source": "simulated", "tier": "T3", "flag": "KNOWN_UNKNOWN",
                "provenance": "simulated"}
        fact = {k: v for k, v in fact.items() if k in fitems}
        out = {"candidate": cand, "facts": [fact], "provenance": "simulated"}
        return {k: v for k, v in out.items() if k in props or k in required}

    # Generic fallback: required scalars → marker; arrays → []; objects → {}.
    out: dict = {}
    for key in required:
        t = (props.get(key) or {}).get("type")
        out[key] = {"array": [], "object": {}, "integer": 0, "number": 0,
                    "boolean": False}.get(t, SIMULATE_MARKER)
    if "provenance" in props:
        out["provenance"] = "simulated"
    return out


def dispatch_claude(contract, inputs, runner=None) -> dict:
    if _simulate_models_on():
        return _simulate_claude(contract, inputs)
    cmd = [
        CLAUDE_BIN, "-p", build_prompt(contract, inputs),
        "--output-format", "json",
        "--json-schema", json.dumps(contract.output_schema or {}),
    ]
    # Cost control: pin the agent's model (e.g. haiku for a cheap live run) when an operator
    # sets it. Reads CLAUDE_MODEL first (the bridge's lever) then SAPPHIRE_MODEL (serve.py's
    # lever) so EITHER env works on this path — serve.py:_run_live reads SAPPHIRE_MODEL into its
    # local `CLAUDE_MODEL`, so accepting both keeps the two paths consistent. Additive +
    # backward-compatible — neither set → the CLI default.
    model = (os.environ.get("CLAUDE_MODEL") or os.environ.get("SAPPHIRE_MODEL") or "").strip()
    if model:
        cmd += ["--model", model]
    cmd += _context_flags()  # Opt-1: drop CLAUDE.md + cache-stable prefix
    if contract.tools_allowed:
        cmd += ["--allowedTools", ",".join(contract.tools_allowed)]
    if runner is None:
        def runner(cmd):
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=_agent_timeout(contract.timeout_s), cwd=str(ROOT))
    proc = runner(cmd)
    if getattr(proc, "returncode", 0) != 0:
        raise RuntimeError(f"claude exited {getattr(proc, 'returncode', '?')}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body


def build_batch_prompt(items) -> str:
    """One prompt for N claude-subagent agents (Opt-2). SHARED_PREAMBLE first (cache), then a
    labeled block per agent. The model returns ONE object keyed by agent id."""
    parts = [
        SHARED_PREAMBLE,
        "You are answering as MULTIPLE specialist agents in a single pass. For EACH agent block "
        "below, produce that agent's structured object **from its own spec + INPUTS only** — do not "
        "let one agent's spec leak into another's answer. Return ONE JSON object whose keys are the "
        "agent ids and whose values are each agent's structured object; nothing else.",
    ]
    for contract, inputs in items:
        parts.append(
            f"### AGENT: {contract.id}\n{_read_spec(contract.spec)}\n"
            f"## INPUTS\n{json.dumps(inputs, indent=2)}"
        )
    return "\n\n".join(parts)


def _batch_schema(items) -> dict:
    """A combined object schema: each agent id → its own output_schema (per-agent enforcement)."""
    props = {c.id: (c.output_schema or {"type": "object"}) for c, _ in items}
    return {"type": "object", "properties": props, "required": [c.id for c, _ in items]}


def dispatch_claude_batch(items, runner=None) -> dict:
    """Opt-2: ONE `claude -p` call for a list of (contract, inputs) claude-subagent items →
    `{agent_id: structured_output}`. ~N boots → 1. Honors the same model + Opt-1 context flags.
    Raises on a non-zero exit, unparseable output, or any missing agent id — the CALLER then falls
    back to per-agent dispatch (honest fallback, never a guessed result). The per-agent guardrails,
    provenance stamping, validation, and trace are applied UNCHANGED downstream (the harness runs
    them on each returned output via a dispatch_fn), so only the generation transport changes."""
    items = list(items)
    if not items:
        return {}
    if _simulate_models_on():
        return {c.id: _simulate_claude(c, inp) for c, inp in items}
    cmd = [
        CLAUDE_BIN, "-p", build_batch_prompt(items),
        "--output-format", "json",
        "--json-schema", json.dumps(_batch_schema(items)),
    ]
    model = (os.environ.get("CLAUDE_MODEL") or os.environ.get("SAPPHIRE_MODEL") or "").strip()
    if model:
        cmd += ["--model", model]
    cmd += _context_flags()
    # Forward the UNION of the batched agents' allowed tools (each agent's per-call --allowedTools
    # would otherwise be dropped → batched agents run tool-blind, e.g. web-search agents lose
    # WebSearch/WebFetch). The union is a superset; each agent uses only what its spec needs, and
    # per-agent output is still validated/guarded downstream.
    tools = sorted({t for c, _ in items for t in (c.tools_allowed or [])})
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    if runner is None:
        timeout_s = _agent_timeout(max((c.timeout_s for c, _ in items), default=300))

        def runner(cmd):
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout_s, cwd=str(ROOT))
    proc = runner(cmd)
    if getattr(proc, "returncode", 0) != 0:
        raise RuntimeError(f"batch claude exited {getattr(proc, 'returncode', '?')}: "
                           f"{(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    missing = [c.id for c, _ in items if c.id not in body]
    if missing:
        raise RuntimeError(f"batch response missing agents: {missing}")
    return {c.id: body[c.id] for c, _ in items}


def dispatch_qmodels(contract, inputs, client=None) -> dict:
    if client is None:
        from qmodels.client import QModelsClient
        client = QModelsClient()
    tool_id = inputs.get("tool_id", contract.id)
    payload = inputs.get("inputs", inputs)
    raw = client.call(tool_id, payload)
    # If the client returned the raw {model, out, provenance} shape, wrap into findings.
    if "facts" not in raw:
        summary = str(raw.get("out", ""))
        raw = {
            "candidate": inputs.get("candidate", ""),
            "facts": [{"value": summary, "source": "Q-Models", "tier": "T2"}],
            "provenance": raw.get("provenance", "qmodels"),
        }
    return raw


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
