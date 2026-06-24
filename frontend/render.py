"""Pure mapping: a `run_live` result dict → render *specs* (plain stdlib data).

This module is deliberately **chainlit-free and stdlib-only** so it is unit-testable in
Gate-1 without a Chainlit runtime. Each function returns a plain spec dict/list describing
*what* to render; `elements.py` (chainlit + pandas, imported only by the running app)
turns these specs into `cl.Dataframe` / `cl.Text` / `cl.Step` elements at launch.

Honesty rules baked in (CONTRACT.md §3, §7):
- tier / provenance / plane strings are rendered **verbatim** — never relabel a T2 as T1,
  never upgrade a `stub`/`mock` chip.
- render **only fields that exist** — there is NO per-agent timing field; we never fabricate one.
- the two data planes (internal / external) render as **separate, clearly-labelled sections**.
- the roundtable is the **spread** — one card per persona, no forced consensus.
- abstained/escalated agents and KNOWN_UNKNOWNS are **shown, not hidden**.
"""
from __future__ import annotations

# Dossier table columns, in order (CONTRACT.md §3). `plane` is the SECTION, not a column.
DOSSIER_COLUMNS = ["value", "field", "tier", "provenance", "source", "flag"]
AGENT_COLUMNS = ["id", "status", "provenance"]


def _s(v) -> str:
    """Verbatim string-coerce; missing/None → '' (blank cell, never a fabricated value)."""
    return "" if v is None else str(v)


# ---------------------------------------------------------------------------
# header / plan / footer
# ---------------------------------------------------------------------------

def render_header(query: str) -> dict:
    return {"kind": "header", "query": _s(query)}


def render_plan(plan: dict) -> dict:
    """Collapsed 'how the firm scoped this' step."""
    plan = plan or {}
    return {
        "kind": "plan",
        "deliverable": _s(plan.get("deliverable")),
        "disease": _s(plan.get("disease")),
        "modality": _s(plan.get("modality")),
        "agents": [_s(a.get("name", a)) if isinstance(a, dict) else _s(a)
                   for a in plan.get("agents", [])],
        "panel": [_s(p.get("persona", p)) if isinstance(p, dict) else _s(p)
                  for p in plan.get("panel", [])],
    }


def render_footer(engagement_id: str) -> dict:
    return {"kind": "footer", "engagement_id": _s(engagement_id)}


# ---------------------------------------------------------------------------
# discover: agent roster, dossier (two planes), flags
# ---------------------------------------------------------------------------

def render_agents(agents: list) -> dict:
    """The firm roster: id · status · provenance. Abstained/escalated shown explicitly.

    No timing column — `discover.agents[]` carries no timing field; we never invent one.
    """
    rows = [
        {"id": _s(a.get("id")), "status": _s(a.get("status")),
         "provenance": _s(a.get("provenance"))}
        for a in (agents or [])
    ]
    # Count anything that is not "ok" as not-fully-answered. A valid harness status is
    # "ok"|"abstained"|"escalated"; a missing/blank status (only from a malformed envelope)
    # is also counted here rather than silently treated as ok — don't undercount.
    n_abstained = sum(1 for r in rows if r["status"] != "ok")
    return {
        "kind": "agents",
        "name": "Firm roster (Bucket-1 fact agents)",
        "columns": list(AGENT_COLUMNS),
        "rows": rows,
        "n_total": len(rows),
        "n_abstained": n_abstained,
    }


def _fact_row(fact: dict) -> dict:
    return {
        "value": _s(fact.get("value")),
        "field": _s(fact.get("field")),
        "tier": _s(fact.get("tier")),
        "provenance": _s(fact.get("provenance")),
        "source": _s(fact.get("source")),
        "flag": _s(fact.get("flag")),
    }


def render_dossier(discover: dict) -> list:
    """The cited fact dossier, split into TWO distinct plane sections.

    Returns a list of table specs — one per non-empty plane, in a fixed order
    (internal first, then external), then a catch-all for any unlabelled plane.
    A plane with no facts renders nothing (empty section omitted).
    """
    discover = discover or {}
    dossier = discover.get("dossier", []) or []

    sections = [
        ("internal", "Internal plane — Quiver moat (private CNS_DFP)"),
        ("external", "External plane — public evidence"),
    ]
    out = []
    for plane_key, title in sections:
        facts = [f for f in dossier if f.get("plane") == plane_key]
        if not facts:
            continue
        out.append({
            "kind": "dossier",
            "plane": plane_key,
            "name": title,
            "columns": list(DOSSIER_COLUMNS),
            "rows": [_fact_row(f) for f in facts],
        })
    # Any fact with a plane outside {internal, external} (or missing) — surface it honestly
    # under an explicit "unclassified plane" section rather than dropping it.
    leftover = [f for f in dossier if f.get("plane") not in ("internal", "external")]
    if leftover:
        out.append({
            "kind": "dossier",
            "plane": "unclassified",
            "name": "Unclassified plane",
            "columns": list(DOSSIER_COLUMNS),
            "rows": [_fact_row(f) for f in leftover],
        })
    return out


def render_flags(flags: dict) -> list:
    """VETO / DIVERGENCE / KNOWN_UNKNOWNS callouts. Empty lists render nothing."""
    flags = flags or {}
    out = []
    veto = flags.get("VETO", []) or []
    if veto:
        out.append({"kind": "flag", "level": "VETO", "icon": "⛔",
                    "title": "VETO — gates the roundtable adjudicates (not silent kills)",
                    "items": [_s(x) for x in veto]})
    diverge = flags.get("DIVERGENCE", []) or []
    if diverge:
        out.append({"kind": "flag", "level": "DIVERGENCE", "icon": "⚠",
                    "title": "DIVERGENCE — internal vs external, surfaced not reconciled (often the alpha)",
                    "items": [_s(x) for x in diverge]})
    unknowns = flags.get("KNOWN_UNKNOWNS", []) or []
    if unknowns:
        out.append({"kind": "flag", "level": "KNOWN_UNKNOWNS", "icon": "…",
                    "title": "Still open (known unknowns)",
                    "items": [_s(x) for x in unknowns]})
    return out


# ---------------------------------------------------------------------------
# consult: the roundtable spread + synthesis
# ---------------------------------------------------------------------------

def _verdict_card(v: dict, round_label: str) -> dict:
    return {
        "round": round_label,
        "persona": _s(v.get("persona")),
        "lens": _s(v.get("lens")),
        "stance": _s(v.get("stance")),
        "conviction": v.get("conviction"),  # int or None — render only if present
        "status": _s(v.get("status")),
        "rationale": _s(v.get("rationale")),
        "fact_claims": list(v.get("fact_claims", []) or []),
    }


def render_roundtable(consult: dict) -> dict:
    """Bucket-2 spread: one card per persona verdict. NO forced consensus.

    round2 (rebuttal) rendered only when present; absent → round1 alone (not fabricated).
    """
    consult = consult or {}
    round1 = consult.get("round1", []) or []
    round2 = consult.get("round2", []) or []
    return {
        "kind": "roundtable",
        "round1": [_verdict_card(v, "round1") for v in round1],
        "round2": [_verdict_card(v, "round2") for v in round2],
        "has_round2": bool(round2),
        "n_personas": len(round1),
    }


def render_synthesis(synthesize: dict) -> dict:
    """The synthesis — 'the facts + how each player reacted', not a single verdict."""
    synthesize = synthesize or {}
    ents = synthesize.get("entities", {}) or {}
    return {
        "kind": "synthesis",
        "recommendation": _s(synthesize.get("recommendation")),
        "confidence": _s(synthesize.get("confidence")),
        "proposed_experiment": _s(synthesize.get("proposed_experiment")),
        "entities": ents,
    }


def render_status(discover: dict) -> dict | None:
    """A run-completeness banner from `discover.status` (contract: `complete` |
    `complete-with-known-unknowns`). Returns None for a fully-complete run (no banner);
    a "⚠ Partial run" spec when status is anything else or known-unknowns are present —
    so a degraded run is never read as a clean one.
    """
    discover = discover or {}
    status = _s(discover.get("status"))
    n_unknown = len((discover.get("flags", {}) or {}).get("KNOWN_UNKNOWNS", []) or [])
    if status in ("", "complete") and n_unknown == 0:
        return None
    note = f"{n_unknown} known-unknown(s)" if n_unknown else "see below"
    return {"kind": "status", "status": status or "incomplete",
            "title": f"⚠ Partial run — status: {status or 'incomplete'} ({note})"}


# ---------------------------------------------------------------------------
# top-level assembly
# ---------------------------------------------------------------------------

def render_run(result: dict) -> list:
    """Assemble the FULL transparency view, in display order, from a run_live result.

    plan → agent roster → dossier (two planes) → flags → roundtable spread → synthesis,
    bracketed by a header (query) and footer (engagement_id). Returns a flat list of
    specs; `elements.py` converts each to a Chainlit element.
    """
    result = result or {}
    specs = [render_header(result.get("query", ""))]
    specs.append(render_plan(result.get("plan", {})))

    discover = result.get("discover", {}) or {}
    status_spec = render_status(discover)
    if status_spec:
        specs.append(status_spec)
    specs.append(render_agents(discover.get("agents", [])))
    specs.extend(render_dossier(discover))
    specs.extend(render_flags(discover.get("flags", {})))

    specs.append(render_roundtable(result.get("consult", {})))
    specs.append(render_synthesis(result.get("synthesize", {})))
    specs.append(render_footer(result.get("engagement_id", "")))
    return specs
