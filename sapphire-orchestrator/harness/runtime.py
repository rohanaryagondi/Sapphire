"""The single entry point: resolve -> guard(inputs) -> dispatch -> validate+guard(output)
-> repair -> stamp -> trace -> AgentResult. Fail-safe; never fabricates (spec §A.3/§A.4)."""
from __future__ import annotations

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


def _validate_output(contract, out, ctx) -> list:
    errs = []
    if contract.output_schema:
        errs += validate(out, contract.output_schema, contract.output_schema)
    for gname in contract.guardrails:
        fn = _OUTPUT_GUARDS.get(gname)
        if fn:
            errs += [f"{v.guardrail}: {v.detail}" for v in fn(contract, out, ctx)]
    return errs


def _finish(contract, result, engagement_id, t0, repairs, guardrails_run, ihash, cache):
    result.meta = {"inputs_hash": ihash, "latency_ms": int((time.time() - t0) * 1000),
                   "repairs": repairs, "guardrails_run": guardrails_run}
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

    # 2. dispatch + validate + repair loop
    out, errs = None, []
    for attempt in range(contract.max_repair + 1):
        call_inputs = inputs if attempt == 0 else {**inputs, "_repair": repair_prompt(out, errs)}
        try:
            out = disp(contract, call_inputs, ctx)
        except HarnessEscalation as ex:
            res = AgentResult(contract.id, False, abstain_envelope(ex.code, ex.detail),
                              contract.provenance_label, "escalated", ex.code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)
        except Exception as ex:
            code = "timeout" if ex.__class__.__name__ == "TimeoutExpired" else "tool-failure"
            errs = [f"{code}: {ex}"]
            if attempt < contract.max_repair:
                out = None
                continue
            status = "escalated" if contract.on_hard_fail == "escalate" else "abstained"
            res = AgentResult(contract.id, False, abstain_envelope(code, "a working backend"),
                              contract.provenance_label, status, code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)

        errs = _validate_output(contract, out, ctx)
        if not errs:
            break
        if attempt >= contract.max_repair:
            code = "guardrail-violation" if any(":" in e and e.split(":")[0] in _OUTPUT_GUARDS for e in errs) else "malformed-output"
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
    return _finish(contract, res, engagement_id, t0, repairs, guardrails_run, ihash, cache)
