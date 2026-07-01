"""
reinvoke.py — WO-9 Phase 5: targeted re-invocation of ONE specific agent/tool.

When a follow-up flags `needs_new_data=True` with a real `missing_agent` id
(followup.py's `answer_followup`, constrained to a validated id — see that
module's docstring), this module actually invokes that ONE agent/tool for
real — never the full 23-agent firm, never a roundtable re-deliberation
(explicitly out of scope for this phase; see `reinvoke_agent`'s docstring).

CONTRACT
--------
  reinvoke_agent(agent_id: str, source_result: dict, refined_query: str | None = None,
                 runner=None, dispatch_fn=None, registry=None, qmodels_client=None) -> dict

  Returns {"ok": bool, "new_facts": list[dict], "agent_id": str | None,
           "engagement_id": str | None, "error": str | None}. Never raises.

TWO INVOCATION PATHS
---------------------
  1. Bucket-1 / semantic agent (e.g. "post-market-safety", "emet-runner",
     "q-models-runner") — dispatched for real via `harness.run`, so it gets the
     exact same guardrails / schema-validation / provenance-stamping / trace
     every Bucket-1 agent gets inside a full `run_live()` pass. The minimal ctx
     it needs (moat + every python seam + the live EMET handler) is built via
     `live_engine._wire_bucket1_ctx` — the SAME helper `run_live` itself uses
     (extracted in this phase precisely so this module doesn't duplicate it).
  2. Q-Models tool (e.g. "dti", "variant_effect", "kg_hypothesis") — dispatched
     directly via `harness.dispatch.dispatch_qmodels` (mirrors the exact
     payload-building logic `dispatch_qmodels` already uses for gene/smiles/
     variant inputs — no duplication) OUTSIDE the harness (a raw Q-Models tool
     is not itself a registered Bucket-1 agent contract).

OUT OF SCOPE (deliberate — see WO-9-research-partner-v2.md Phase 5)
---------------------------------------------------------------------
  Re-scoping/re-running the Bucket-2 roundtable (persona re-deliberation) is
  NOT built here. It is a materially larger, more expensive operation
  (multi-persona, 2 rounds) that deserves its own scoped follow-up — this
  phase covers exactly the two invocation paths above.

HONESTY
-------
  New facts get the SAME public-safe stripping/enrichment `live_engine.py`
  already applies to every dossier fact: `plane` DERIVED via `plane_for`
  (never asserted), the contributing `agent_id` stamped. Never fabricates a
  "found it" result — any failure (agent not found, dispatch error, guardrail
  violation, honest-empty abstain) degrades to `{"ok": False, "new_facts": []}`.

STDLIB-ONLY
  Imports only sibling engine modules (harness, live_engine, engagement,
  contracts.provenance, qmodels.client) — no third-party deps.
"""
from __future__ import annotations

import uuid

from contracts.provenance import plane_for


def _bucket1_agent_ids(registry) -> set:
    """The real, invocable Bucket-1 agent ids — the SAME roster `live_engine.run_live()`
    dispatches (`_BUCKET1_AGENTS` intersected with the live registry). Deliberately
    excludes Bucket-2 personas (company-partner, ex-fda-regulator, ...) and the
    rescue-mechanism reasoner (a derived, query-shaped dispatch, not a standalone
    re-invocable fact agent) — never invented, always sourced from the same list
    `followup.py`'s `_bucket1_targets` constrains `missing_agent` to."""
    try:
        from live_engine import _BUCKET1_AGENTS, _known_agent_ids
    except ImportError:
        return set()
    try:
        known = _known_agent_ids(registry)
    except Exception:
        return set()
    return {aid for aid in _BUCKET1_AGENTS if aid in known}


def _qmodels_tool_ids(client=None) -> set:
    """The real Q-Models tool ids (dti, variant_effect, kg_hypothesis, ...)."""
    try:
        from qmodels.client import QModelsClient
    except ImportError:
        return set()
    try:
        tools = (client if client is not None else QModelsClient()).tools()
    except Exception:
        return set()
    return {t.get("id") for t in tools if t.get("id")}


def _enrich_fact(fact: dict, provenance: str, agent_id: str) -> dict:
    """Public-safe enrichment mirroring live_engine.py's per-fact stamping exactly:
    provenance defaulted, plane DERIVED (never asserted, conservative 'external' on
    an unrecognised label), and the contributing agent id stamped unconditionally."""
    enriched = dict(fact)
    enriched.setdefault("provenance", provenance)
    fact_prov = enriched.get("provenance", provenance)
    try:
        enriched["plane"] = plane_for(fact_prov)
    except KeyError:
        enriched["plane"] = "external"
    enriched["agent_id"] = agent_id
    return enriched


def _scoped_inputs(source_result: "dict | None", refined_query: "str | None") -> dict:
    """Build the minimal Bucket-1 `inputs` dict for a single agent — a `refined_query`
    (if given) scopes it more precisely than the original run's query; falls back to
    the original run's query/plan fields otherwise. Public identifiers only (gene
    symbols extracted via the same entity extractor `run_live` uses)."""
    from engagement import extract_entities

    source_result = source_result if isinstance(source_result, dict) else {}
    query = (refined_query or source_result.get("query") or "").strip()
    ents = extract_entities(query)
    candidate = ents["genes"][0] if ents["genes"] else ""
    plan = source_result.get("plan") or {}
    disease = plan.get("disease", "")
    return {
        "candidate": candidate,
        "disease": disease,
        "query": query,
        "genes": ents["genes"],
        "sequences": [],
    }


def _reinvoke_bucket1(agent_id: str, source_result, refined_query, runner, dispatch_fn, registry) -> dict:
    import harness
    from live_engine import _wire_bucket1_ctx

    inputs = _scoped_inputs(source_result, refined_query)

    ctx: dict = {}
    if runner is not None:
        ctx["runner"] = runner
    _wire_bucket1_ctx(ctx)

    eid = "eng_reinvoke_" + uuid.uuid4().hex[:12]
    res = harness.run(agent_id, inputs, engagement_id=eid, ctx=ctx, registry=registry, dispatch_fn=dispatch_fn)

    if not res.ok or not res.output:
        return {
            "ok": False, "new_facts": [], "agent_id": agent_id, "engagement_id": eid,
            "error": res.error or f"{agent_id} abstained (status={res.status})",
        }

    facts = res.output.get("facts", [])
    prov = res.output.get("provenance", res.provenance)
    new_facts = [_enrich_fact(f, prov, agent_id) for f in facts]
    if not new_facts:
        return {
            "ok": False, "new_facts": [], "agent_id": agent_id, "engagement_id": eid,
            "error": f"{agent_id} returned no facts (honest-empty)",
        }
    return {"ok": True, "new_facts": new_facts, "agent_id": agent_id, "engagement_id": eid, "error": None}


def _reinvoke_qmodels(tool_id: str, source_result, refined_query, client) -> dict:
    from harness.dispatch import dispatch_qmodels

    inputs = _scoped_inputs(source_result, refined_query)
    # dispatch_qmodels honours an explicit tool_id (bypasses its own heuristic
    # selection) and mirrors the exact gene/smiles/variant payload-building it
    # already does for the q-models-runner Bucket-1 agent — no duplication.
    inputs["tool_id"] = tool_id

    try:
        raw = dispatch_qmodels(None, inputs, client=client)
    except Exception as e:
        return {"ok": False, "new_facts": [], "agent_id": tool_id, "engagement_id": None,
                "error": f"{type(e).__name__}: {e}"}

    facts = raw.get("facts", [])
    prov = raw.get("provenance", "unavailable")
    new_facts = [_enrich_fact(f, prov, tool_id) for f in facts]
    # dispatch_qmodels always returns a (possibly "simulated/not called") placeholder
    # fact rather than an empty list — only a genuinely live/successful provenance
    # counts as new evidence; anything else is an honest non-result, never fabricated.
    ok = bool(new_facts) and prov not in (
        "unavailable", "error", "unknown", "gpu-disabled", "gpu-stub", "gpu-dry-run", "stub",
    )
    return {
        "ok": ok, "new_facts": new_facts if ok else [], "agent_id": tool_id, "engagement_id": None,
        "error": None if ok else f"{tool_id} returned no usable result (provenance={prov})",
    }


def reinvoke_agent(agent_id: str, source_result: "dict | None", refined_query: "str | None" = None,
                    runner=None, dispatch_fn=None, registry=None, qmodels_client=None) -> dict:
    """Actually invoke ONE specific Bucket-1 agent or Q-Models tool for real. Never raises.

    Parameters
    ----------
    agent_id      : a real, validated id (a Bucket-1 agent id or a Q-Models tool id) —
                     normally `followup.answer_followup`'s already-validated `missing_agent`.
    source_result : the run_live-shaped evidence dict the re-invocation is scoping
                     against (used for its `query`/`plan.disease` fields as a fallback
                     when `refined_query` is absent).
    refined_query : optional, more precisely scoped question/entity than the original
                     run's query (e.g. a narrower candidate/entity).
    runner        : optional callable injected into the Bucket-1 claude-subagent
                     dispatch path (tests only) — never used for the Q-Models path.
    dispatch_fn   : optional harness dispatch override (tests only).
    registry      : optional pre-loaded agents.json dict (tests only).
    qmodels_client: optional pre-built QModelsClient (tests only).

    Returns
    -------
    dict — {"ok": bool, "new_facts": list[dict], "agent_id": str | None,
    "engagement_id": str | None, "error": str | None}. Never raises; any failure
    (unknown id, dispatch error, guardrail violation, honest-empty abstain)
    degrades to an honest `{"ok": False, "new_facts": [], "error": "..."}`.
    """
    try:
        if not agent_id or not isinstance(agent_id, str):
            return {"ok": False, "new_facts": [], "agent_id": None, "engagement_id": None,
                    "error": "agent_id is required"}

        if registry is None:
            from harness.contracts import load_registry
            registry = load_registry()

        if agent_id in _bucket1_agent_ids(registry):
            return _reinvoke_bucket1(agent_id, source_result, refined_query, runner, dispatch_fn, registry)

        if agent_id in _qmodels_tool_ids(qmodels_client):
            return _reinvoke_qmodels(agent_id, source_result, refined_query, qmodels_client)

        return {
            "ok": False, "new_facts": [], "agent_id": agent_id, "engagement_id": None,
            "error": f"unknown agent_id {agent_id!r} — not a real Bucket-1 agent or Q-Models tool",
        }
    except Exception as e:
        return {"ok": False, "new_facts": [], "agent_id": agent_id, "engagement_id": None,
                "error": f"{type(e).__name__}: {e}"}


__all__ = ["reinvoke_agent"]
