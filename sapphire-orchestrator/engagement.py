"""Run a Sapphire engagement on the live engine, bracketed by the harness trace and the
self-improvement loop (recall priors in, reflect memory out). Additive: wraps Orchestrator,
does not modify it. This is where the Phase-5 loop runs end-to-end on real engagements."""
from __future__ import annotations

import hashlib
import re

from harness import trace
from memory import recall
from selfimprove.reflect import reflect as _reflect

_GENE_RE = re.compile(r"\b[A-Z]{2,4}[0-9]{1,3}[A-Z]?\b")   # SCN11A, SCN2A, KCNT1, LRRK2, GBA1


def extract_entities(text: str) -> dict:
    genes = sorted(set(_GENE_RE.findall(text or "")))
    return {"genes": genes, "smiles": [], "diseases": [], "drugs": []}


def _eid(key: str) -> str:
    return "eng_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def run_engagement(sid_or_query: str, *, engine=None, do_reflect: bool = True) -> dict:
    if engine is None:
        from orchestrator import Orchestrator
        engine = Orchestrator()
    try:
        run = engine.run(sid_or_query)
    except ValueError:
        run = engine.run_query(sid_or_query)

    ents = extract_entities(f"{run.get('query','')} {run.get('headline','')} {run.get('title','')}")
    disease = (run.get("plan", {}) or {}).get("disease")
    if disease and disease != "general CNS":
        ents["diseases"] = [disease]

    eid = _eid(str(run.get("id") or sid_or_query))
    run["engagement_id"] = eid
    run["priors"] = recall(ents) if (ents["genes"] or ents["diseases"]) else []

    trace.open_engagement(eid, run.get("plan", {}) or {})
    facts = []
    valid_tiers = {"T1", "T2", "T3", "T4"}
    for row in (run.get("discover", {}) or {}).get("dossier", []) or []:
        tier = row.get("tier", "T3")
        # Normalize invalid tiers to T3
        if tier not in valid_tiers:
            tier = "T3"
        fact = {"value": row.get("value", ""), "source": row.get("source", ""), "tier": tier}
        if row.get("flag"):
            fact["flag"] = row["flag"]
        facts.append(fact)
    if facts:
        primary = ents["genes"][0] if ents["genes"] else ""
        trace.record(eid, {"agent_id": "dossier", "provenance": "synthesis",
                           "output": {"candidate": primary, "facts": facts}})
    syn = dict(run.get("synthesize", {}) or {})
    syn["entities"] = ents
    trace.close_engagement(eid, syn)

    run["reflection"] = _reflect(eid) if do_reflect else None
    return run
