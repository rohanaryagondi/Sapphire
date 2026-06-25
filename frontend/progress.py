"""Pure formatting of `run_live` progress events → live step-tree descriptors.

Chainlit-free + stdlib-only so it is unit-tested without a session. `main.py` drives the actual
`cl.Step`s from these strings. Honesty rule (live-run-visibility): a `done` line reflects the REAL
agent result — an abstain shows as an abstain (⚠ + reason), never a "✓".
"""
from __future__ import annotations

# Friendly labels for the Bucket-1 agents (so the live tree reads like a firm convening, not ids).
_AGENT_LABELS = {
    "internal-science-lead": "Internal moat — Quiver CNS_DFP (internal plane)",
    "emet-runner": "EMET — live BenchSci (external plane)",
    "q-models-runner": "Q-Models — predictive launchpad",
    "fda-institutional-memory": "FDA institutional memory ⛔",
    "patent-ip": "Patent / IP ⛔",
    "global-regulatory-divergence": "Global regulatory divergence",
    "clinical-trial-registry": "Clinical-trial registry",
    "post-market-safety": "Post-market safety",
    "payer": "Payer / reimbursement",
    "financial": "Financial",
    "aso-tox": "ASO acute-tox screen",
    "gnomad-constraint": "gnomAD constraint",
    "gtex-expression": "GTEx expression",
    "interpro-domains": "InterPro domains",
    "geneset-enrichment": "g:Profiler enrichment",
    "robyn-scs": "robyn_scs connectivity (internal)",
}

_PARENT_NAMES = {
    "bucket1": "Bucket-1 — gathering the cited fact dossier",
    "roundtable": "Bucket-2 — the persona roundtable (the spread)",
}


def agent_label(agent_id: str) -> str:
    return _AGENT_LABELS.get(agent_id, agent_id or "agent")


def parent_stage(ev: dict):
    """The parent group a child step lives under (None = a top-level step)."""
    return ev.get("stage") if ev.get("stage") in ("bucket1", "roundtable") else None


def parent_name(stage: str) -> str:
    return _PARENT_NAMES.get(stage, stage)


def is_done(ev: dict) -> bool:
    return ev.get("phase") == "done"


def step_name(ev: dict) -> str:
    stage = ev.get("stage")
    if stage == "plan":
        return "Plan — scoping the engagement"
    if stage == "bucket1":
        return agent_label(ev.get("agent_id", ""))
    if stage == "flags":
        return "Flags — VETO / DIVERGENCE"
    if stage == "roundtable":
        return ev.get("agent_id") or "persona"
    if stage == "synthesis":
        return "Synthesis — the recommendation"
    return str(stage)


def step_output(ev: dict) -> str:
    """The result line for a `done` event — honest (abstain ⇒ ⚠, never ✓)."""
    stage = ev.get("stage")
    if stage == "plan":
        return (f"{ev.get('disease', '') or '—'} · {ev.get('modality', '') or '—'} · "
                f"{len(ev.get('agents', []))} fact agents · {len(ev.get('panel', []))} panel")
    if stage == "bucket1":
        status = ev.get("status")
        n = ev.get("n_facts", 0)
        prov = ev.get("provenance", "")
        el = ev.get("elapsed_s")
        if status == "ok":
            return f"✓ {n} fact(s) · {prov} · {el}s"
        err = f" — {ev.get('error')}" if ev.get("error") else ""
        return f"⚠ {status}{err} · {prov} · {el}s"          # abstain/escalate shown honestly
    if stage == "flags":
        return (f"⛔ {ev.get('n_veto', 0)} VETO · ⚠ {ev.get('n_divergence', 0)} DIVERGENCE · "
                f"{ev.get('n_known_unknowns', 0)} known-unknown(s)")
    if stage == "roundtable":
        status = ev.get("status")
        el = ev.get("elapsed_s")
        if status == "ok":
            conv = ev.get("conviction")
            cv = f" · conviction {conv}" if conv is not None else ""
            return f"{ev.get('stance', '?')}{cv} · {el}s"
        return f"⚠ abstained ({status}) · {el}s"            # honest abstention, not a verdict
    if stage == "synthesis":
        return f"{ev.get('recommendation', '')} (confidence: {ev.get('confidence', '')})"
    return ""
