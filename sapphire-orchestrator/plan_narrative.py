"""plan_narrative.py — Deterministic narrative builder for Sapphire plan-mode.

Produces a structured ``narrative`` dict (framing + 5 canonical steps) from the
real plan fields + the selected agent roster. Stdlib-only — no LLM, no third-party
imports. Called by live_engine for the deterministic fallback path and by bridge.plan.

The 5 canonical steps (stable contract):
  1. moat        — internal-science-lead  (plane=internal, prov=moat-real)
  2. external    — all other Bucket-1 fact agents (plane=external, T1/T2 cited)
  3. veto        — fda-institutional-memory ⛔ + patent-ip ⛔ (gates)
  4. roundtable  — partner roundtable (conditional — present when panel is non-empty)
  5. synth       — synthesize + flag unknowns

Data boundary: only public identifiers (disease, modality, gene symbols, agent ids).
Internal moat scores NEVER appear here.
"""
from __future__ import annotations

# Veto agents — locked, non-deselectable
_VETO_AGENTS = frozenset(["fda-institutional-memory", "patent-ip"])

# Agents that are part of the "external dossier" step (everything except moat + veto)
_MOAT_AGENTS = frozenset(["internal-science-lead"])

# Human labels for agents (public identifiers only)
_AGENT_LABEL: dict[str, str] = {
    "internal-science-lead": "Internal moat (Quiver CNS_DFP)",
    "emet-runner": "EMET — live BenchSci",
    "q-models-runner": "Q-Models launchpad",
    "fda-institutional-memory": "FDA institutional memory",
    "patent-ip": "Patent / IP",
    "global-regulatory-divergence": "Global regulatory divergence",
    "dea-scheduling": "DEA scheduling",
    "clinical-trial-registry": "Clinical-trial registry",
    "post-market-safety": "Post-market safety",
    "payer": "Payer / reimbursement",
    "financial": "Financial",
    "manufacturing-cmc": "Manufacturing / CMC",
    "patient-advocacy": "Patient advocacy",
    "kol-social": "KOL / social signal",
    "policy-legislative": "Policy / legislative",
    "reputational": "Reputational",
    "aso-tox": "ASO acute-tox screen",
    "boltz": "Boltz structure / binding",
    "gnomad-constraint": "gnomAD constraint",
    "gtex-expression": "GTEx expression",
    "interpro-domains": "InterPro domains",
    "geneset-enrichment": "g:Profiler enrichment",
    "robyn-scs": "robyn_scs connectivity",
}


def _label(agent_id: str) -> str:
    return _AGENT_LABEL.get(agent_id, agent_id)


def build_deterministic_narrative(
    query: str,
    plan: dict,
    selected_agent_ids: list[str],
    panel: list | None = None,
) -> dict:
    """Build a deterministic narrative dict from real plan fields + selected agents.

    Parameters
    ----------
    query               : the user's engagement question (public identifiers only).
    plan                : the public_plan dict from live_engine (deliverable/disease/modality).
    selected_agent_ids  : the ordered list of Bucket-1 agent ids that will run.
    panel               : the Bucket-2 partner panel (list of persona strings/dicts);
                          None or empty → roundtable is skipped (step 4 is "skipped").

    Returns
    -------
    A ``narrative`` dict shaped as:
        {
          "framing": str,
          "steps": [
            {"key": str, "title": str, "plane"?: str, "badges"?: [str],
             "prose": str, "expect"?: str, "skipping"?: str, "sub"?: [str]}
          ]
        }
    """
    disease = plan.get("disease") or "the target indication"
    modality = plan.get("modality") or "the proposed modality"
    deliverable = plan.get("deliverable") or "diligence"
    panel = panel or []
    roundtable_on = bool(panel)

    # Partition selected agents by role.
    moat_selected = [a for a in selected_agent_ids if a in _MOAT_AGENTS]
    veto_selected = [a for a in selected_agent_ids if a in _VETO_AGENTS]
    external_selected = [
        a for a in selected_agent_ids
        if a not in _MOAT_AGENTS and a not in _VETO_AGENTS
    ]

    # Also compute the "skipped" external agents — ones that are NOT in external_selected
    # but ARE in the full canonical list for context (DEA, CMC, policy, reputational).
    _skip_candidates = [
        "dea-scheduling", "manufacturing-cmc", "policy-legislative", "reputational"
    ]
    skipped_external = [a for a in _skip_candidates if a not in external_selected]

    # ── framing ──────────────────────────────────────────────────────────────
    framing = (
        f"A {deliverable} question on {disease} ({modality}). "
        f"My strategy: lead with Quiver's proprietary signal, corroborate it with "
        f"the external evidence base, stress-test against the veto gates"
        f"{', then convene the partner roundtable' if roundtable_on else ''} "
        f"— flagging anything I cannot establish rather than guessing."
    )

    # ── step 1: Internal moat ─────────────────────────────────────────────────
    moat_prose = (
        f"Pull the Quiver CNS_DFP proprietary signal for {disease}. "
        f"This is the internal edge and frames everything that follows. "
        f"Only public gene symbols ever leave — internal scores stay inside the boundary."
    )
    moat_expect = "A ranked list of gene/target signals with public identifiers only."
    if not moat_selected:
        moat_prose = (
            f"The internal moat agent is not in the selected panel for this run; "
            f"the fact dossier will rely on external sources only."
        )
        moat_expect = None

    step_moat: dict = {
        "key": "moat",
        "title": "Establish the proprietary signal",
        "plane": "internal",
        "badges": ["internal", "moat-real"],
        "prose": moat_prose,
    }
    if moat_expect:
        step_moat["expect"] = moat_expect

    # ── step 2: External dossier ──────────────────────────────────────────────
    n_ext = len(external_selected)
    ext_labels = [_label(a) for a in external_selected]

    ext_prose = (
        f"{n_ext} agent{'s' if n_ext != 1 else ''} in parallel, corpus-first then search the gap. "
        f"The point: corroborate the internal signal with public, cited evidence on "
        f"mechanism, safety, regulatory precedent, and commercial landscape."
    ) if n_ext > 0 else (
        "No external fact agents were selected for this panel; "
        "the dossier will rely on internal signal and veto gates only."
    )

    ext_sub = [f"{_label(a)} — selected" for a in external_selected[:6]]

    step_ext: dict = {
        "key": "external",
        "title": "Gather & corroborate the external dossier",
        "plane": "external",
        "badges": ["external", "T1/T2 cited"],
        "prose": ext_prose,
    }
    if ext_sub:
        step_ext["sub"] = ext_sub
    if skipped_external:
        step_ext["skipping"] = (
            f"Skipping: {', '.join(_label(a) for a in skipped_external)} — "
            "not load-bearing for this query type."
        )

    # ── step 3: Veto gates ────────────────────────────────────────────────────
    veto_labels = [_label(a) for a in veto_selected] if veto_selected else [
        "FDA institutional memory", "Patent / IP"
    ]
    step_veto: dict = {
        "key": "veto",
        "title": "Run the veto gates",
        "badges": ["fda-memory ⛔", "patent-ip ⛔"],
        "prose": (
            f"{' + '.join(veto_labels)} run as gates, not filters. "
            f"I check for prior CRLs / program deaths on this MOA, and "
            f"freedom-to-operate on the top candidates. "
            f"If either fires, the roundtable adjudicates — I never kill a program silently."
        ),
    }

    # ── step 4: Partner roundtable (conditional) ──────────────────────────────
    if roundtable_on:
        n_partners = len(panel)
        panel_labels = []
        for p in panel[:4]:
            if isinstance(p, dict):
                panel_labels.append(p.get("persona", str(p)))
            else:
                panel_labels.append(str(p))
        partner_str = " · ".join(panel_labels) if panel_labels else f"{n_partners} partners"
        step_roundtable: dict = {
            "key": "roundtable",
            "title": "Convene the partner roundtable",
            "badges": [f"{n_partners} partner{'s' if n_partners != 1 else ''}"],
            "prose": (
                f"Independent verdicts → moderated rebuttal. "
                f"Panel: {partner_str}. "
                f"No forced consensus — the spread between partners is the signal."
            ),
        }
    else:
        step_roundtable = {
            "key": "roundtable",
            "title": "Roundtable — skipped",
            "prose": (
                "The partner roundtable is not included in this panel; "
                "the run returns the cited dossier without partner deliberation."
            ),
            "skipping": "Roundtable not selected for this run.",
        }

    # ── step 5: Synthesize & flag unknowns ────────────────────────────────────
    step_synth: dict = {
        "key": "synth",
        "title": "Synthesize & flag the unknowns",
        "prose": (
            f"Rank the candidates by internal signal, grounded in external mechanism"
            f"{' and partner reaction' if roundtable_on else ''}. "
            f"Propose the validating experiment. "
            f"What I cannot establish — e.g. the rescue mechanism itself — "
            f"I flag as a known-unknown, not fake."
        ),
    }

    return {
        "framing": framing,
        "steps": [step_moat, step_ext, step_veto, step_roundtable, step_synth],
        # source="deterministic" — the card shows an honesty label when this is not "llm".
        "source": "deterministic",
    }
