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


def _resolve_model(contract) -> str:
    """Resolve the --model flag for a claude dispatch call (3-tier priority).

    1. CLAUDE_MODEL or SAPPHIRE_MODEL env — operator override; wins unconditionally.
       Keeps backward-compat (existing tests that set CLAUDE_MODEL still pass; serve.py
       can force a single model for the whole run).
    2. contract.model (agents.json "model" field) — per-agent default. Mapping:
       - Bucket-2 roundtable/partner agents → claude-haiku-4-5  (cheap, fast deliberation)
       - Control + Bucket-1 fact agents + synthesis → claude-sonnet-4-6  (nuanced reasoning)
    3. Empty string → no --model flag (CLI default; backward-compatible fallback).
    """
    env_model = (os.environ.get("CLAUDE_MODEL") or os.environ.get("SAPPHIRE_MODEL") or "").strip()
    if env_model:
        return env_model
    if contract is not None:
        per_agent = getattr(contract, "model", None)
        if per_agent:
            return per_agent.strip()
    return ""


def dispatch_claude(contract, inputs, runner=None) -> dict:
    # simulate_exempt agents (the scientific-core reasoners whose output IS the deliverable, e.g.
    # rescue-mechanism) do REAL reasoning even under SAPPHIRE_SIMULATE_MODELS — so a fast demo can
    # stub the personas/semantic agents while the science still runs for real. In CI a mock runner
    # is injected via ctx, so an exempt agent never shells a live `claude -p`.
    if _simulate_models_on() and not getattr(contract, "simulate_exempt", False):
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
    model = _resolve_model(contract)
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
        # simulate_exempt agents still reason for real even in batch mode (consistency with
        # dispatch_claude). In practice the scientific-core reasoners are dispatched per-agent,
        # not batched, so this branch is belt-and-suspenders.
        return {c.id: (_simulate_claude(c, inp)
                       if not getattr(c, "simulate_exempt", False)
                       else dispatch_claude(c, inp, runner=runner))
                for c, inp in items}
    cmd = [
        CLAUDE_BIN, "-p", build_batch_prompt(items),
        "--output-format", "json",
        "--json-schema", json.dumps(_batch_schema(items)),
    ]
    # Batch model: env override wins (same priority as per-agent); fall back to the first
    # item's per-agent model (batch calls group same-bucket agents so they share a model).
    model = _resolve_model(items[0][0] if items else None)
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


def _select_qmodels_tool(inputs: dict, registry_tools: "dict | None" = None) -> tuple:
    """Select the most relevant Q-Models tool for the given inputs.

    Simple deterministic heuristic (no ML) — avoids fabrication:
      - SMILES present  → 'dti' (DTI/Binder Triage, live-local, headline tool)
      - Gene + variant  → 'variant_effect' (funNCion, endpoint/live)
      - Gene present    → 'kg_hypothesis' (PROTON, endpoint/live)
      - Fallback        → 'kg_hypothesis'

    Returns (tool_id, tool_label, input_used) — all public identifiers.
    tool_label is the human-readable name from the registry, or a default.
    """
    # Infer entity type from inputs — only public identifiers are examined.
    gene = (inputs.get("candidate") or "").strip()
    smiles = (inputs.get("smiles") or "").strip()
    variant = (inputs.get("variant") or "").strip()

    # Mapping from tool_id → (label, input_used)
    if smiles:
        chosen_id = "dti"
        chosen_input = smiles
    elif gene and variant:
        chosen_id = "variant_effect"
        chosen_input = f"{gene} {variant}"
    elif gene:
        chosen_id = "kg_hypothesis"
        chosen_input = gene
    else:
        chosen_id = "kg_hypothesis"
        chosen_input = inputs.get("query", "")[:80]

    # Look up the label from the registry (fall back to id if not found).
    tool_label = chosen_id
    if registry_tools:
        for t in registry_tools:
            if t.get("id") == chosen_id:
                tool_label = t.get("label") or t.get("name") or chosen_id
                break

    return chosen_id, tool_label, chosen_input


def dispatch_qmodels(contract, inputs, client=None) -> dict:
    if client is None:
        from qmodels.client import QModelsClient
        client = QModelsClient()

    # --- tool selection: pick a specific, relevant tool from the registry ---
    # If the caller explicitly pre-selected a tool_id via inputs["tool_id"], honour it.
    # Otherwise, use the deterministic entity-type heuristic.
    registry_tools = None
    try:
        registry_tools = list(client.tools())
    except Exception:
        pass

    if inputs.get("tool_id"):
        chosen_id = inputs["tool_id"]
        chosen_input = inputs.get("inputs", inputs).get("candidate", "") or ""
        # Look up label
        chosen_label = chosen_id
        if registry_tools:
            for t in registry_tools:
                if t.get("id") == chosen_id:
                    chosen_label = t.get("label") or t.get("name") or chosen_id
                    break
    else:
        chosen_id, chosen_label, chosen_input = _select_qmodels_tool(inputs, registry_tools)

    # Build the tool-specific payload from public inputs only.
    # Each tool declares its required inputs in the registry; we pass what we have
    # and let the client/seam handle missing fields gracefully (stub/unavailable).
    gene = (inputs.get("candidate") or "").strip()
    smiles = (inputs.get("smiles") or "").strip()
    variant = (inputs.get("variant") or "").strip()

    if chosen_id == "dti":
        payload = {"smiles": smiles or chosen_input}
        if gene:
            payload["uniprot_acc"] = gene  # best-effort; seam accepts partial
    elif chosen_id == "variant_effect":
        payload = {"gene": gene or chosen_input, "variant": variant or ""}
    elif chosen_id == "kg_hypothesis":
        payload = {"gene": gene or chosen_input, "known_drug": ""}
    else:
        payload = inputs.get("inputs", inputs)

    # WO-9 Phase 3: for local-cpu tools, check server reachability once up front — reused
    # both to route the call (avoids a second HTTP round-trip inside client.call) and to
    # stamp an honest at-a-glance health summary on the output (see _qmodels_health below),
    # so a user can tell the local Explorer endpoint is unreachable/stub-only WITHOUT having
    # to infer it from a single fact's "unavailable" note. GPU-tier tools are untouched —
    # this is scoped to the local-cpu investigation only. Guarded so callers whose fake
    # `client` has no `.health()` (unit tests) are unaffected — registry_tools stays None
    # and health is simply skipped.
    health = None
    if registry_tools:
        tool_meta = next((t for t in registry_tools if t.get("id") == chosen_id), None)
        if tool_meta and tool_meta.get("tier") == "local-cpu":
            try:
                health = client.health()
            except Exception:
                health = None

    if health is not None:
        raw = client.call(chosen_id, payload, live_tracks=health.get("live_tracks"))
    else:
        raw = client.call(chosen_id, payload)

    # If the client returned the raw {model, out, provenance} shape, wrap into findings.
    if "facts" not in raw:
        summary = str(raw.get("out", ""))
        # Honest: if the tool is unavailable/simulated, mark the fact explicitly.
        prov = raw.get("provenance", "qmodels")
        # not_called: tool selected but not executed (includes legacy gpu-async + new gpu-dry-run)
        not_called = prov in ("unavailable", "stub", "gpu-disabled", "gpu-async", "error", "unknown")
        # gpu-dry-run: tool selected, launch plan validated, AWS not touched; label clearly
        gpu_dry_run = prov == "gpu-dry-run"
        # gpu-stub: GPU tool unavailable / misconfigured (honest degradation)
        gpu_stub = prov == "gpu-stub"
        if gpu_dry_run:
            # Use the deterministic out string (already labeled "GPU tool … selected; would launch …")
            fact_value = summary
        elif not_called or gpu_stub:
            # Use the provenance string as the status descriptor, NOT the raw out string,
            # so the fact value is deterministic (the gpu-async out includes a random job id).
            fact_value = (
                f"(simulated / not called — {chosen_label} selected; "
                f"input: {chosen_input!r}; status: {prov})"
            )
        else:
            fact_value = summary if summary else f"({chosen_label} ran; no output)"
        raw = {
            "candidate": inputs.get("candidate", ""),
            "facts": [{"value": fact_value, "source": "Q-Models", "tier": "T2"}],
            "provenance": prov,
        }

    # Stamp the selected tool metadata on the output so the harness can surface it.
    # Prefix _ means internal-to-output; the Info panel reads these from res.meta.
    raw["_qmodels_tool_id"] = chosen_id
    raw["_qmodels_tool_label"] = chosen_label
    raw["_qmodels_input"] = chosen_input
    if health is not None:
        # Public-safe reachability summary only (bool + track-id list) — never internal scores.
        raw["_qmodels_health"] = {
            "reachable": bool(health.get("reachable")),
            "live_tracks": list(health.get("live_tracks") or []),
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
