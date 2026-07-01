"""The single entry point: resolve -> guard(inputs) -> dispatch -> validate+guard(output)
-> repair -> stamp -> trace -> AgentResult. Fail-safe; never fabricates (spec §A.3/§A.4)."""
from __future__ import annotations

import os
import time

from contracts.jsonschema_min import validate

from . import dispatch as _dispatch
from . import guardrails as G
from . import trace as T
from .contracts import AgentResult, inputs_hash, resolve
from .errors import HarnessEscalation, abstain_envelope
from .repair import repair_prompt

_INPUT_GUARDS = {"data_boundary": G.data_boundary, "public_identifiers_only": G.public_identifiers_only}
_OUTPUT_GUARDS = {
    "facts_only_cited": G.facts_only_cited,
    "must_cite_dossier": G.must_cite_dossier,
    "veto_is_gate": G.veto_is_gate,
    "emet_tab_discipline": G.emet_tab_discipline,
}


def _validate_output(contract, out, ctx) -> tuple:
    schema_errs = validate(out, contract.output_schema, contract.output_schema) if contract.output_schema else []
    guard_errs = []
    for gname in contract.guardrails:
        fn = _OUTPUT_GUARDS.get(gname)
        if fn:
            guard_errs += [f"{v.guardrail}: {v.detail}" for v in fn(contract, out, ctx)]
    return schema_errs, guard_errs


def _model_for_contract(contract, transport_meta: "dict | None" = None) -> str:
    """Return an honest backend/model string for the contract's kind.

    Recorded in meta["model"] so the UI can show what actually ran.
    Never fabricates — falls back to kind-based label.

    For qmodels-delegate, prefers the specific tool label from transport_meta
    (extracted by the harness from dispatch_qmodels output before schema validation)
    over the generic "Q-Models launchpad" fallback.
    """
    kind = contract.kind
    if kind == "emet-playwright":
        return "EMET / BenchSci"
    if kind == "python":
        return "Quiver data (CNS_DFP)"
    if kind == "qmodels-delegate":
        # Use the specific tool label if the dispatch recorded one.
        if transport_meta and transport_meta.get("_qmodels_tool_label"):
            return transport_meta["_qmodels_tool_label"]
        return "Q-Models launchpad"
    if kind == "claude-subagent":
        from . import dispatch as _d
        if _d._simulate_models_on():
            return "simulated"
        model = (os.environ.get("CLAUDE_MODEL") or os.environ.get("SAPPHIRE_MODEL") or "").strip()
        return model if model else "claude (default)"
    return kind


def _finish(contract, result, engagement_id, t0, repairs, guardrails_run, ihash, cache,
            transport_meta: "dict | None" = None):
    out = result.output if result.ok else None
    meta: dict = {
        "inputs_hash": ihash,
        "latency_ms": int((time.time() - t0) * 1000),
        "repairs": repairs,
        "guardrails_run": guardrails_run,
        "model": _model_for_contract(contract, transport_meta or {}),
    }
    # For q-models-delegate: surface the specific tool + input in meta so live_engine
    # can read them and set agent_query / model on the agent status entry.
    # transport_meta carries the _qmodels_* keys extracted before schema validation.
    if transport_meta and contract.kind == "qmodels-delegate":
        if transport_meta.get("_qmodels_tool_id"):
            meta["qmodels_tool_id"] = transport_meta["_qmodels_tool_id"]
        if transport_meta.get("_qmodels_tool_label"):
            meta["qmodels_tool_label"] = transport_meta["_qmodels_tool_label"]
        if transport_meta.get("_qmodels_input") is not None:
            meta["qmodels_input"] = transport_meta["_qmodels_input"]
    result.meta = meta
    T.record(engagement_id, {"agent_id": contract.id, "kind": contract.kind,
                             "inputs_hash": ihash, "status": result.status,
                             "provenance": result.provenance, "error": result.error,
                             "repairs": repairs, "guardrails_run": guardrails_run,
                             "output": result.output})
    cache[ihash] = result
    return result


def run(agent_id, inputs, *, engagement_id, ctx=None, registry=None, dispatch_fn=None) -> AgentResult:
    ctx = ctx if ctx is not None else {}
    t0 = time.time()
    try:
        contract = resolve(agent_id, registry)
    except KeyError:
        T.record(engagement_id, {"agent_id": agent_id, "kind": "unknown",
                                 "status": "escalated", "error": "unknown-agent"})
        return AgentResult(agent_id, False, abstain_envelope("unknown-agent", "a registered agent id"),
                           "synthesis", "escalated", "unknown-agent",
                           {"inputs_hash": None, "latency_ms": 0, "repairs": 0, "guardrails_run": []})

    ihash = inputs_hash(contract.id, inputs)
    cache = ctx.setdefault("_cache", {})
    if ihash in cache:
        return cache[ihash]

    guardrails_run = []

    # 1. input guards — BLOCK pre-dispatch
    for gname in contract.guardrails:
        gfn = _INPUT_GUARDS.get(gname)
        if gfn:
            guardrails_run.append(gname)
            if gfn(inputs):
                res = AgentResult(contract.id, False,
                                  abstain_envelope("guardrail-violation", f"{gname} clean inputs"),
                                  contract.provenance_label, "abstained", "guardrail-violation")
                return _finish(contract, res, engagement_id, t0, 0, guardrails_run, ihash, cache)

    disp = dispatch_fn or _dispatch.dispatch

    # Transport-only metadata extracted from dispatch output (before schema validation).
    # For qmodels-delegate: dispatch_qmodels stamps _qmodels_* on the output dict so the
    # harness can surface them in meta, but the schema rejects extra keys — so we extract
    # and strip them here, before _validate_output runs, and carry them forward in a local
    # dict that is folded into result.meta inside _finish. Cleared on each attempt.
    _transport_meta: dict = {}

    # 2. dispatch + validate + repair loop
    out, errs = None, []
    for attempt in range(contract.max_repair + 1):
        call_inputs = inputs if attempt == 0 else {**inputs, "_repair": repair_prompt(out, errs)}
        _transport_meta = {}  # reset each attempt
        try:
            out = disp(contract, call_inputs, ctx)
        except HarnessEscalation as ex:
            res = AgentResult(contract.id, False, abstain_envelope(ex.code, ex.detail),
                              contract.provenance_label, "escalated", ex.code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)
        except Exception as ex:
            code = "timeout" if ex.__class__.__name__ == "TimeoutExpired" else "tool-failure"
            errs = [f"{code}: {ex}"]
            # Timeouts are not retried — a same-cost retry would block for the full timeout again.
            # tool-failure may retry up to max_repair times (prompt-repair can fix malformed output).
            if attempt < contract.max_repair and code != "timeout":
                out = None
                continue
            status = "escalated" if contract.on_hard_fail == "escalate" else "abstained"
            res = AgentResult(contract.id, False, abstain_envelope(code, "a working backend"),
                              contract.provenance_label, status, code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)

        # Strip transport-only keys from the dispatch output before schema validation.
        # dispatch_qmodels stamps _qmodels_* keys on the output dict so the harness can
        # surface tool-selection details in meta; but "additionalProperties: false" in the
        # findings schema rejects them. We extract them here (into _transport_meta) and
        # strip them from the output BEFORE the schema check, so validation passes.
        if isinstance(out, dict):
            _TRANSPORT_KEYS = ("_qmodels_tool_id", "_qmodels_tool_label", "_qmodels_input")
            has_transport = any(k in out for k in _TRANSPORT_KEYS)
            if has_transport:
                for tk in _TRANSPORT_KEYS:
                    if tk in out:
                        _transport_meta[tk] = out[tk]
                # Shallow-copy minus transport keys so we don't mutate the dispatch return.
                out = {k: v for k, v in out.items() if k not in _TRANSPORT_KEYS}

        schema_errs, guard_errs = _validate_output(contract, out, ctx)
        errs = schema_errs + guard_errs
        if not errs:
            break
        if attempt >= contract.max_repair:
            code = "malformed-output" if schema_errs else "guardrail-violation"
            status = "escalated" if contract.on_hard_fail == "escalate" else "abstained"
            res = AgentResult(contract.id, False, abstain_envelope(code, "; ".join(errs[:3])),
                              contract.provenance_label, status, code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)

    repairs = attempt

    # 3. success — stamp provenance, record guardrails that ran
    for gname in contract.guardrails:
        if gname in _OUTPUT_GUARDS and gname not in guardrails_run:
            guardrails_run.append(gname)
    if "stamp_provenance" in contract.guardrails:
        out = G.stamp_provenance(contract, out)
        guardrails_run.append("stamp_provenance")
    provenance = out.get("provenance", contract.provenance_label)
    res = AgentResult(contract.id, True, out, provenance, "ok", None)
    return _finish(contract, res, engagement_id, t0, repairs, guardrails_run, ihash, cache,
                   transport_meta=_transport_meta)
