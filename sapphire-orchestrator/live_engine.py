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

import re
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
from tools import aso_tox_seam, gnomad_constraint_seam, gtex_expression_seam, interpro_domains_seam, geneset_enrichment_seam
from corpus.reader import read_corpus, has_corpus
from contracts.provenance import plane_for

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
    # ASO acute-tox screen — contributes facts only when sequences are present in inputs;
    # returns facts=[] (honest empty) for standard target-level queries with no ASO sequences.
    "aso-tox",
    # gnomAD gene constraint (pLI / LOEUF / missense Z) — quantitative fact source.
    # Fires when a target gene symbol is present in inputs; honest-empty otherwise.
    "gnomad-constraint",
    # GTEx tissue expression (median TPM + CNS selectivity) — quantitative fact source.
    # Fires when a target gene symbol is present in inputs; honest-empty otherwise.
    "gtex-expression",
    # InterPro protein domain/family annotations (IPR accessions) — structured fact source.
    # Fires when a target gene symbol is present in inputs; honest-empty otherwise.
    "interpro-domains",
    # g:Profiler functional enrichment (top GO / pathway terms) over the gene set —
    # quantitative fact source. Fires when a gene set / target is present; honest-empty otherwise.
    "geneset-enrichment",
]


# ---------------------------------------------------------------------------
# ASO sequence extraction helper
# ---------------------------------------------------------------------------

# Strict pattern: standalone token that is pure A/T/G/C (uppercase only), length ≥ 15.
# Gene symbols (e.g. TSC2, SCN2A) always contain digits or non-ATGC letters — they
# never match.  Lowercase text, mixed case, and ordinary words are excluded by design.
_ASO_RE = re.compile(r"\b[ATGC]{15,}\b")


def _extract_aso_sequences(query: str) -> list[str]:
    """
    Extract standalone ASO candidate sequences embedded in a query string.

    A token qualifies only when it:
      - consists entirely of uppercase A, T, G, C characters
      - is at least 15 characters long
      - appears as a word boundary token

    This is intentionally strict to avoid false-positives on gene symbols,
    accession numbers, ordinary words, or mixed-case text.

    Returns a deduplicated list preserving first-occurrence order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for m in _ASO_RE.finditer(query):
        seq = m.group(0)
        if seq not in seen:
            seen.add(seq)
            result.append(seq)
    return result


def _known_agent_ids(registry) -> set:
    """Return the set of agent ids present in the registry dict."""
    if registry is None:
        from harness.contracts import load_registry
        registry = load_registry()
    return {a["id"] for a in registry.get("agents", [])}


def _corpus_card_to_fact(agent_id: str, card: dict) -> dict:
    """Convert a corpus claim-card into a corpus-sourced dossier fact.

    Carries the card's own `source` / `tier` / `url` and stamps provenance="corpus"
    (+ from_corpus=True). Deliberately sets NO `flag`: a corpus card is a T2 lead, not a
    dispositive veto — a veto still requires its T1 primary.

    Also stamps `plane` = plane_for("corpus") = "external" (corpus is pre-ingested
    public literature — additive A3 field).
    """
    return {
        "value": card.get("claim") or card.get("value") or "",
        "source": card.get("source", "corpus"),
        "tier": card.get("tier", "T2"),
        "url": card.get("url", ""),
        "provenance": "corpus",
        "plane": plane_for("corpus"),   # "external" — additive A3 field
        "from_corpus": True,
        "field": agent_id,
    }


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
    sequences: list[str] | None = None,
    ctx: dict | None = None,
    registry=None,
    engine: Orchestrator | None = None,
) -> dict:
    """
    Run a full Sapphire engagement with every agent dispatched through the harness.

    Parameters
    ----------
    query     : the free-text question / task.
    sequences : optional list of ASO candidate sequences (e.g. ["GCACTTGAATTTCACGTTGT"]).
                When provided, sequences are threaded into every Bucket-1 agent's inputs
                so the aso-tox agent can score them.  If None (default), the function
                falls back to extracting pure A/T/G/C tokens of length ≥ 15 from the
                query text via _extract_aso_sequences().
                NOTE: this is the documented handoff point for the future ASO-Design tool —
                that tool will pass its designed sequences here after its own dispatch.
    ctx       : optional harness context dict (inject mock backends for testing).
    registry  : optional pre-loaded agents.json dict (default: harness.load_registry()).
    engine    : optional Orchestrator instance (default: new Orchestrator()).

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

    # Resolve the sequences channel.
    # Precedence: explicit param > query-text extractor.
    # The explicit param is always used when provided (even if empty list).
    # When None, fall back to the strict query extractor (_extract_aso_sequences).
    # This channel is the handoff point for the future ASO-Design tool.
    if sequences is None:
        resolved_sequences: list[str] = _extract_aso_sequences(query)
    else:
        resolved_sequences = list(sequences)

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
    # Wire the ASO acute-tox seam (stdlib-only orchestrator; sklearn lives in the subprocess).
    # Passes sequences through inputs — fires only when ASO sequences are present.
    if "aso-tox" not in ctx["python_fns"]:
        ctx["python_fns"]["aso-tox"] = aso_tox_seam.predict_findings
    # Wire the gnomAD constraint seam (stdlib-only orchestrator; urllib lives in the seam).
    # Fires when a target gene symbol is present in inputs — honest-empty otherwise.
    if "gnomad-constraint" not in ctx["python_fns"]:
        ctx["python_fns"]["gnomad-constraint"] = gnomad_constraint_seam.findings
    # Wire the GTEx expression seam (stdlib-only orchestrator; urllib lives in the seam).
    # Fires when a target gene symbol is present in inputs — honest-empty otherwise.
    if "gtex-expression" not in ctx["python_fns"]:
        ctx["python_fns"]["gtex-expression"] = gtex_expression_seam.findings
    # Wire the InterPro domains seam (stdlib-only orchestrator; urllib lives in the seam).
    # Fires when a target gene symbol is present in inputs — honest-empty otherwise.
    if "interpro-domains" not in ctx["python_fns"]:
        ctx["python_fns"]["interpro-domains"] = interpro_domains_seam.findings
    # Wire the g:Profiler enrichment seam (stdlib-only orchestrator; urllib lives in the seam).
    # Fires when a gene set (or target) is present in inputs — honest-empty otherwise.
    if "geneset-enrichment" not in ctx["python_fns"]:
        ctx["python_fns"]["geneset-enrichment"] = geneset_enrichment_seam.findings

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
        # genes: the full set of gene symbols extracted from the query (candidate is
        # genes[0]). Threaded for the geneset-enrichment agent, which operates on a SET;
        # a single-gene query yields a one-element set. Other agents ignore this key.
        "genes": ents["genes"],
        # sequences: ASO candidates threaded through to the aso-tox agent.
        # Populated from the explicit sequences= param (preferred) or the
        # query-text extractor.  Empty list when no sequences are present —
        # aso-tox will return facts=[] (honest empty) in that case.
        "sequences": resolved_sequences,
    }

    for agent_id in _BUCKET1_AGENTS:
        if agent_id not in known_ids:
            # Skip agents absent from the registry gracefully.
            continue

        # Corpus-first retrieval: pull the matching claim-cards from this agent's
        # pre-ingested local corpus (corpus/<agent_id>/index.jsonl), if any. These
        # answer the stable ~70% locally; they are also handed to the agent below as
        # `corpus_hits` so its live call can target only the uncovered gap.
        corpus_cards = (
            read_corpus(agent_id, query, ents) if has_corpus(agent_id) else []
        )
        agent_inputs = (
            {**bucket1_inputs, "corpus_hits": corpus_cards}
            if corpus_cards else bucket1_inputs
        )

        res = harness.run(
            agent_id,
            agent_inputs,
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
                # A3: stamp the data plane derived from the fact's provenance.
                # plane is additive (never replaces an existing key) and derived —
                # never asserted by the agent. Unknown provenances default to "external"
                # (conservative: an unknown source is treated as external for safety).
                fact_prov = enriched.get("provenance", prov)
                try:
                    enriched.setdefault("plane", plane_for(fact_prov))
                except KeyError:
                    enriched.setdefault("plane", "external")
                all_dossier_facts.append(enriched)
                flag = f.get("flag")
                if flag == "VETO":
                    veto_flags.append(f.get("value", ""))
                elif flag == "DIVERGENCE":
                    divergence_flags.append(f.get("value", ""))
        else:
            abstained_agents.append(agent_id)
            # A guardrail-violation or abstain is surfaced as a KNOWN_UNKNOWN.

        # Surface the corpus cards as corpus-sourced dossier facts — independent of
        # whether the live agent ran (the point of corpus-first: the stable knowledge
        # lands even when the live backend is down). Each fact carries the card's own
        # source/tier/url and provenance="corpus". A corpus card is a T2 LEAD, never a
        # dispositive veto: we deliberately do NOT set flag=VETO here (a veto still
        # requires its T1 primary, per the FDA-memory skill doc). Traced below.
        if corpus_cards:
            corpus_facts = [_corpus_card_to_fact(agent_id, c) for c in corpus_cards]
            all_dossier_facts.extend(corpus_facts)
            trace.record(eid, {
                "type": "corpus_retrieval",
                "agent_id": agent_id,
                "n_cards": len(corpus_facts),
                "facts": [f["value"][:120] for f in corpus_facts],
            })

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
