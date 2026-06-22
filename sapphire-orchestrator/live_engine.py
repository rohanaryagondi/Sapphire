"""
live_engine.py — The live harnessed engine for Sapphire.

Every agent dispatch (Bucket 1 fact agents + Bucket 2 persona partners) runs through
harness.run(), ensuring input guards, output validation, provenance stamping, and trace
records fire for every call.  This is the production path; no canned scenario is loaded.

Usage:
    from live_engine import run_live
    result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
"""
from __future__ import annotations

import sys
import os

# Ensure the sapphire-orchestrator package root is on sys.path when called from tests CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from orchestrator import Orchestrator
from engagement import extract_entities, _eid
from moat.facts import moat_facts
from memory import recall
from harness import trace
import harness
from selfimprove.reflect import reflect

# ---------------------------------------------------------------------------
# Bucket-1 agent IDs — the representative span the spec requests.
# Agents are skipped if not present in the registry.
# ---------------------------------------------------------------------------
_BUCKET1_AGENTS = [
    "internal-science-lead",
    "emet-runner",
    "q-models-runner",
    "fda-institutional-memory",
    "patent-ip",
    "global-regulatory-divergence",
    "clinical-trial-registry",
    "post-market-safety",
    "payer",
    "financial",
]


def _known_agent_ids(registry) -> set:
    """Return the set of agent ids present in the registry dict."""
    if registry is None:
        from harness.contracts import load_registry
        registry = load_registry()
    return {a["id"] for a in registry.get("agents", [])}


def _build_moat_agent():
    """Return the real moat backend closure."""
    def _moat_agent(inputs: dict) -> dict:
        tgt = inputs.get("candidate") or inputs.get("target") or ""
        rows = moat_facts(tgt, k=4) if tgt else []
        facts = [
            {"value": r["value"], "source": r["source"], "tier": r["tier"]}
            for r in rows
        ]
        return {"candidate": tgt, "facts": facts, "provenance": "moat-real"}
    return _moat_agent


def run_live(
    query: str,
    *,
    ctx: dict | None = None,
    registry=None,
    engine: Orchestrator | None = None,
) -> dict:
    """
    Run a full Sapphire engagement with every agent dispatched through the harness.

    Parameters
    ----------
    query    : the free-text question / task.
    ctx      : optional harness context dict (inject mock backends for testing).
    registry : optional pre-loaded agents.json dict (default: harness.load_registry()).
    engine   : optional Orchestrator instance (default: new Orchestrator()).

    Returns
    -------
    A structured dict with keys:
        query, plan, priors, discover, consult, synthesize, engagement_id,
        reflection, _via.
    """
    # -----------------------------------------------------------------------
    # 0. Initialise engine + ctx
    # -----------------------------------------------------------------------
    engine = engine or Orchestrator()
    ctx = dict(ctx or {})

    # Load registry once (used for id-set lookups + harness.run).
    if registry is None:
        from harness.contracts import load_registry
        registry = load_registry()

    known_ids = _known_agent_ids(registry)

    # -----------------------------------------------------------------------
    # 1. Control — deterministic triage + plan
    # -----------------------------------------------------------------------
    tri = engine.triage(query)
    plan = engine.plan(query)
    panel = plan.get("panel", [])

    # -----------------------------------------------------------------------
    # 2. Entity extraction + engagement id + priors
    # -----------------------------------------------------------------------
    ents = extract_entities(query)
    target = ents["genes"][0] if ents["genes"] else ""
    eid = _eid(query)
    priors = recall(ents)

    # Open the engagement trace (plan dict minus internal _ keys).
    public_plan = {k: v for k, v in plan.items() if not k.startswith("_")}
    trace.open_engagement(eid, public_plan)

    # -----------------------------------------------------------------------
    # 3. Wire the REAL moat backend (only if caller didn't supply one already)
    # -----------------------------------------------------------------------
    ctx.setdefault("python_fns", {})
    if "internal-science-lead" not in ctx["python_fns"]:
        ctx["python_fns"]["internal-science-lead"] = _build_moat_agent()

    # -----------------------------------------------------------------------
    # 4. Bucket 1 — fact agents
    # -----------------------------------------------------------------------
    all_dossier_facts: list[dict] = []
    agent_statuses: list[dict] = []
    veto_flags: list[str] = []
    divergence_flags: list[str] = []
    abstained_agents: list[str] = []

    bucket1_inputs = {
        "candidate": target,
        "disease": tri.get("disease_label", ""),
        "query": query,
    }

    for agent_id in _BUCKET1_AGENTS:
        if agent_id not in known_ids:
            # Skip agents absent from the registry gracefully.
            continue

        res = harness.run(
            agent_id,
            bucket1_inputs,
            engagement_id=eid,
            ctx=ctx,
            registry=registry,
        )

        agent_statuses.append({
            "id": agent_id,
            "status": res.status,
            "provenance": res.provenance,
        })

        if res.ok and res.output:
            facts = res.output.get("facts", [])
            prov = res.output.get("provenance", res.provenance)
            for f in facts:
                enriched = dict(f)
                enriched.setdefault("provenance", prov)
                all_dossier_facts.append(enriched)
                flag = f.get("flag")
                if flag == "VETO":
                    veto_flags.append(f.get("value", ""))
                elif flag == "DIVERGENCE":
                    divergence_flags.append(f.get("value", ""))
        else:
            abstained_agents.append(agent_id)
            # A guardrail-violation or abstain is surfaced as a KNOWN_UNKNOWN.

    known_unknowns = [f"abstained: {aid}" for aid in abstained_agents]

    status = "complete" if not abstained_agents else "complete-with-known-unknowns"

    discover = {
        "dossier": all_dossier_facts,
        "flags": {
            "VETO": veto_flags,
            "DIVERGENCE": divergence_flags,
            "KNOWN_UNKNOWNS": known_unknowns,
        },
        "status": status,
        "agents": agent_statuses,
    }

    # -----------------------------------------------------------------------
    # 5. Bucket 2 — persona partners (one harness.run per seated persona)
    # -----------------------------------------------------------------------
    round1: list[dict] = []

    for p in panel:
        persona_name = p.get("persona", "")
        lens = p.get("lens", "")

        # Build a compact dossier field list for the partner to reference.
        dossier_fields = list({f.get("value", "")[:80] for f in all_dossier_facts})[
            :10
        ]

        if "company-partner" not in known_ids:
            continue

        res = harness.run(
            "company-partner",
            {
                "persona": persona_name,
                "lens": lens,
                "dossier_fields": dossier_fields,
            },
            engagement_id=eid,
            ctx={**ctx, "dossier_fields": dossier_fields},
            registry=registry,
        )

        if res.ok and res.output:
            verdict = dict(res.output)
            verdict.setdefault("provenance", res.provenance)
            verdict["status"] = res.status
            round1.append(verdict)
        else:
            round1.append({
                "persona": persona_name,
                "lens": lens,
                "stance": "hold",
                "conviction": 0,
                "rationale": f"abstained ({res.error or 'unknown'})",
                "fact_claims": [],
                "provenance": res.provenance,
                "status": res.status,
            })

    # -----------------------------------------------------------------------
    # 6. Synthesis — deterministic assembly
    # -----------------------------------------------------------------------
    stances = [v.get("stance", "hold") for v in round1 if isinstance(v, dict)]
    pass_count = stances.count("pass")
    no_go_count = stances.count("no_go")
    conditional_count = stances.count("conditional")

    if no_go_count > 0:
        recommendation = (
            f"Hold — {no_go_count} partner(s) returned no_go; "
            "resolve veto-class findings before advancing."
        )
        confidence = "low"
    elif pass_count > len(stances) // 2:
        recommendation = (
            f"Advance — majority consensus ({pass_count}/{len(stances)} pass). "
            f"Target: {target or 'unspecified'}."
        )
        confidence = "high"
    elif conditional_count > 0:
        recommendation = (
            f"Conditional advance — {conditional_count} conditional verdict(s). "
            "Address open items before IND filing."
        )
        confidence = "medium"
    else:
        recommendation = (
            "Insufficient evidence to recommend; commission proposed experiment."
        )
        confidence = "low"

    proposed_experiment = (
        f"Run orthogonal in vivo validation for {target} in disease-relevant model."
        if target
        else "Define experimental paradigm for primary target."
    )

    syn = {
        "recommendation": recommendation,
        "confidence": confidence,
        "proposed_experiment": proposed_experiment,
        "entities": ents,
    }

    # Close the trace and run the self-improvement reflection loop.
    trace.close_engagement(eid, syn)
    reflection = reflect(eid)

    # -----------------------------------------------------------------------
    # 7. Assemble and return
    # -----------------------------------------------------------------------
    return {
        "query": query,
        "plan": public_plan,
        "priors": priors,
        "discover": discover,
        "consult": {"round1": round1},
        "synthesize": syn,
        "engagement_id": eid,
        "reflection": reflection,
        "_via": "harness-live",
    }
