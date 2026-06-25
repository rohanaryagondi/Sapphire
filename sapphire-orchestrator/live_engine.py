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
import time

# Ensure the sapphire-orchestrator package root is on sys.path when called from tests CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from orchestrator import Orchestrator
from engagement import extract_entities, _eid
from moat.facts import moat_facts, rescue_genes
from memory import recall
from harness import trace
import harness
from selfimprove.reflect import reflect
from tools import aso_tox_seam, gnomad_constraint_seam, gtex_expression_seam, interpro_domains_seam, geneset_enrichment_seam, robyn_scs_seam, boltz_seam
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
    # Boltz-2 structure + binding-affinity (hosted Boltz Compute API). Contributes facts only
    # when a target protein sequence and/or a candidate ligand (SMILES/CCD) is present in inputs
    # (the structure channel — fed by the upstream ASO Design / small-molecule tools); returns
    # facts=[] (honest empty) for standard target-level queries with no structure/affinity input.
    "boltz",
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
    # robyn_scs SCS/STA neuronal-connectivity (internal, imaging-derived). Fires only when
    # imaging data (a v17_traces plate dir) is present in inputs; honest-empty otherwise.
    "robyn-scs",
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


# ---------------------------------------------------------------------------
# Boltz structure/affinity input extraction helper
# ---------------------------------------------------------------------------
# A protein sequence token: standalone, ≥ 25 uppercase amino-acid letters, and
# containing AT LEAST ONE letter outside {A,T,G,C} so it can never collide with an
# ASO/DNA token (which _ASO_RE owns) — gene symbols always carry digits and so never
# match.  The amino-acid alphabet is the standard 20 one-letter codes.
_PROTEIN_RE = re.compile(r"\b[ACDEFGHIKLMNPQRSTVWY]{25,}\b")
_ATGC_ONLY_RE = re.compile(r"^[ATGC]+$")


def _extract_structure_inputs(query: str) -> dict:
    """
    Best-effort extraction of Boltz STRUCTURE/AFFINITY inputs from a query string.

    This is the query-text fallback for the Boltz activation channel, mirroring
    _extract_aso_sequences for the ASO channel.  The PRIMARY channel is the explicit
    ``structure=`` param to run_live (fed by the upstream ASO Design / small-molecule
    tools).  This extractor only fires on inputs unambiguous in free text:

      - target_sequence : the FIRST standalone protein token that is ≥ 25 uppercase
        amino-acid letters AND contains a non-ATGC residue (so a long pure-ATGC ASO/DNA
        token is never misread as a protein; gene symbols carry digits and never match).

    SMILES are deliberately NOT extracted from free text: a SMILES string overlaps with
    ordinary punctuation/words and a false positive would trigger a paid Boltz job.  A
    ligand is supplied only via the explicit ``structure=`` channel (ligand_smiles /
    ligand_ccd).  Returns {} when no structural input is detectable — Boltz then stays
    dormant (honest-empty), exactly like aso-tox with no sequences.
    """
    out: dict = {}
    for m in _PROTEIN_RE.finditer(query):
        tok = m.group(0)
        if not _ATGC_ONLY_RE.match(tok):  # exclude pure-ATGC (those are ASO/DNA tokens)
            out["target_sequence"] = tok
            break
    return out


_RESCUE_RE = re.compile(r"\brescue", re.I)


def _is_rescue_ranking_query(query: str) -> bool:
    """True for a "rank/identify GENES that RESCUE the <TARGET>-KO phenotype" question — the
    trigger for the ranked-rescue-gene deliverable (structured rescue_genes + mechanism reasoning
    + ranked synthesis).

    Conservative by design: requires "rescue" AND a gene/ranking cue AND a KO/phenotype/signature
    cue, so an ordinary viability question ("Is TSC2 a viable target?") does NOT match and keeps the
    existing IND-style synthesis untouched.
    """
    q = query or ""
    if not _RESCUE_RE.search(q):
        return False
    # Require an explicit GENE cue (the deliverable ranks GENES) — a bare "rank"/"identify" is too
    # loose. And exclude compound/drug/molecule ranking questions, which are a different deliverable
    # (the moat's rescue COMPOUNDS), so "rank the rescue compound candidates for TSC2 KO" does NOT
    # trigger the gene path. Conservative by design: a miss falls back to IND synthesis (no harm).
    has_gene_cue = re.search(r"\bgenes?\b", q, re.I) is not None
    is_compound_q = re.search(r"\bcompounds?\b|\bdrugs?\b|\bmolecules?\b|\bsmall[- ]molecules?\b",
                              q, re.I) is not None
    has_ko_cue = re.search(r"\bK/?O\b|knock-?out|knock-?down|phenotype|signature", q, re.I) is not None
    return has_gene_cue and has_ko_cue and not is_compound_q


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


def _wire_emet_handler(ctx: dict) -> None:
    """Register the live EMET handler on ctx if the caller didn't supply one (setdefault).

    LAZY import — `emet.handler` pulls in the Playwright/Claude-driving seam, which must NOT
    enter the engine's import graph at module-import time (the engine stays stdlib-only).
    Importing here, only when run_live actually wires backends, keeps that boundary.

    Session-reuse caveat (honest): the live runner drives EMET by shelling out to a SEPARATE
    `claude -p` subprocess (its own Playwright browser), so it does NOT inherit the interactive
    session's already-authenticated BenchSci browser/tabs, and contends on the Chrome
    profile lock. When it lands on the BenchSci login screen the runner returns
    `{"login_required": true}` → the handler escalates → the emet agent abstains HONESTLY
    (no fabricated facts). Reliable session sharing is an open design question — see
    `dev/HELP.md` (EMET-MCP vs shared persistent profile vs in-session orchestration).
    """
    if "emet_handler" not in ctx:
        from emet.handler import make_emet_handler
        ctx["emet_handler"] = make_emet_handler()


def _batch_bucket1(known_ids, bucket1_inputs, ctx, registry) -> dict:
    """Opt-2: batch the corpus-less claude-subagent Bucket-1 agents into ONE claude call
    (~6 boots → 1). Returns `{agent_id: output}`; `{}` on ANY failure → the caller falls back to
    per-agent dispatch (honest cold-fallback, never a guessed result). Corpus agents and
    python/qmodels/emet agents are intentionally excluded (their inputs/paths differ)."""
    from harness.contracts import resolve
    from harness.dispatch import dispatch_claude_batch
    items = []
    for aid in _BUCKET1_AGENTS:
        if aid not in known_ids or has_corpus(aid):
            continue
        try:
            contract = resolve(aid, registry)
        except KeyError:
            continue
        if contract.kind != "claude-subagent":
            continue
        items.append((contract, bucket1_inputs))
    if not items:
        return {}
    try:
        return dispatch_claude_batch(items, runner=ctx.get("runner"))
    except Exception:
        return {}


def _emit(on_progress, eid, event: dict) -> None:
    """Fire one live-progress milestone (live-run-visibility, additive side channel).

    Two effects, both best-effort so they can NEVER break the engagement:
      1. record a `{"type": "progress", ...}` event to the harness trace → the run is observable
         by tailing `trace.jsonl` mid-run (incremental flush);
      2. invoke the optional `on_progress(event)` callback (the front end's live step tree).

    A bad callback or a trace-write failure is swallowed — progress is a side channel, never a
    gate. `on_progress=None` ⇒ only the trace record (the trace was already written per agent;
    these add the staged milestones), and the returned dict is byte-identical either way.
    """
    ev = dict(event)
    try:
        trace.record(eid, {"type": "progress", **ev})
    except Exception:
        pass
    if on_progress is not None:
        try:
            on_progress(ev)
        except Exception:
            pass


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
    structure: dict | None = None,
    ctx: dict | None = None,
    registry=None,
    engine: Orchestrator | None = None,
    on_progress=None,
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
    structure : optional dict of Boltz STRUCTURE/AFFINITY inputs — public identifiers only:
                {"target_sequence"|"protein_sequence", "ligand_smiles"|"ligand_ccd"} (or a
                pre-built {"entities": [...], "binding": {...}}).  When provided, these are
                threaded into every Bucket-1 agent's inputs so the boltz agent folds/scores
                them (a protein + a ligand auto-requests a binding_confidence).  If None
                (default), the function falls back to extracting a target protein sequence
                from the query text via _extract_structure_inputs().  Boltz fires ONLY when
                a structure/affinity input is in scope — with neither a sequence nor a
                ligand it stays dormant (honest-empty), mirroring aso-tox.
                NOTE: this is the documented handoff point for the upstream ASO Design /
                small-molecule tools — they pass a target sequence + candidate ligand here.
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

    # Resolve the structure/affinity channel (Boltz).  Same precedence as sequences:
    # explicit structure= param > query-text extractor.  An explicit dict is used as-is
    # (even if empty → Boltz stays dormant); None falls back to _extract_structure_inputs.
    # This channel is the handoff point for the upstream ASO Design / small-molecule tools.
    if structure is None:
        resolved_structure: dict = _extract_structure_inputs(query)
    else:
        resolved_structure = dict(structure)

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

    # Live progress: the plan is ready (fires immediately after triage, before any agent runs).
    _emit(on_progress, eid, {
        "stage": "plan", "phase": "done",
        "deliverable": public_plan.get("deliverable", ""),
        "disease": public_plan.get("disease", ""),
        "modality": public_plan.get("modality", ""),
        "agents": [a.get("name", a) if isinstance(a, dict) else a
                   for a in public_plan.get("agents", [])],
        "panel": [p.get("persona", p) if isinstance(p, dict) else p
                  for p in public_plan.get("panel", [])],
    })

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
    # Wire the Boltz structure/binding seam (stdlib-only orchestrator; urllib lives in the seam;
    # the BOLTZ_API_KEY is read by the seam from RohanOnly/boltz_api.env at call time, never here).
    # Passes structural inputs through — fires only when a target sequence and/or ligand is present.
    if "boltz" not in ctx["python_fns"]:
        ctx["python_fns"]["boltz"] = boltz_seam.findings
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
    # Wire the robyn_scs connectivity seam (stdlib orchestrator; numpy/scipy/pandas in the
    # subprocess). Fires only when imaging data is present in inputs — honest-empty otherwise.
    if "robyn-scs" not in ctx["python_fns"]:
        ctx["python_fns"]["robyn-scs"] = robyn_scs_seam.findings

    # Wire the live EMET handler (external plane). Registered so emet-runner is no longer
    # silently absent on ctx=None — a logged-in BenchSci session can actually be used. See
    # _wire_emet_handler for the lazy import + the honest session-reuse caveat.
    _wire_emet_handler(ctx)

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

    # structure/affinity inputs threaded through to the boltz agent. Only the recognised
    # PUBLIC structural keys are forwarded (target_sequence/protein_sequence, ligand_smiles,
    # ligand_ccd, or a pre-built entities/binding) — never arbitrary caller keys, so no
    # internal field can sneak into the dossier inputs. Absent ⇒ boltz honest-empties (dormant),
    # mirroring how aso-tox stays silent without sequences. Populated from the explicit
    # structure= param (preferred) or the query-text extractor.
    _STRUCT_KEYS = ("target_sequence", "protein_sequence", "ligand_smiles", "ligand_ccd",
                    "entities", "binding")
    for _k in _STRUCT_KEYS:
        if resolved_structure.get(_k):
            bucket1_inputs[_k] = resolved_structure[_k]

    # Opt-2 (dispatch-optimization): optionally batch the corpus-less claude-subagent Bucket-1
    # agents into ONE claude call. Opt-in via ctx["batch_buckets"]; on ANY failure we fall back to
    # per-agent dispatch. Each batched output still flows through the FULL per-agent harness path
    # (validation + guardrails + provenance stamp + trace) via dispatch_fn below — only the
    # generation transport changes; guards/provenance/schemas are unaffected.
    batched_outputs: dict = (
        _batch_bucket1(known_ids, bucket1_inputs, ctx, registry)
        if ctx.get("batch_buckets") else {}
    )

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

        # If this agent was answered in the Opt-2 batch, feed its output through the SAME harness
        # path via dispatch_fn (validation/guards/provenance/trace run unchanged). Else dispatch
        # normally (the per-agent, per-kind backend).
        disp_fn = None
        if agent_id in batched_outputs:
            _o = batched_outputs[agent_id]
            # Const dispatch_fn: returns the batched output verbatim. It IGNORES the harness
            # repair prompt — so a batched output that fails schema/guard validation is retried
            # with the same value and (correctly) abstains after max_repair, never accepted. The
            # tradeoff: a batched agent cannot self-correct via prompt-repair the way a per-agent
            # claude call can; bad batched output → honest abstain, not a fix-up.
            disp_fn = lambda contract, inputs, ctx, _o=_o: _o  # noqa: E731

        # Live progress: this Bucket-1 agent is starting.
        _emit(on_progress, eid, {"stage": "bucket1", "agent_id": agent_id, "phase": "start"})
        _t0 = time.monotonic()

        res = harness.run(
            agent_id,
            agent_inputs,
            engagement_id=eid,
            ctx=ctx,
            registry=registry,
            dispatch_fn=disp_fn,
        )

        _elapsed = round(time.monotonic() - _t0, 2)
        # Live progress: this Bucket-1 agent is done — real status/provenance/fact-count + timing
        # (honest: an abstain reports its status, never a "✓"). The corpus facts surfaced below
        # are independent of the live agent, so they're folded into n_facts here.
        _n_facts = (len(res.output.get("facts", [])) if (res.ok and res.output) else 0) + len(corpus_cards)
        _emit(on_progress, eid, {
            "stage": "bucket1", "agent_id": agent_id, "phase": "done",
            "status": res.status, "provenance": res.provenance,
            "n_facts": _n_facts, "elapsed_s": _elapsed,
            "error": res.error if not res.ok else None,
        })

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
                # A3: stamp the data plane DERIVED from the fact's provenance.
                # Authoritative + unconditional — any `plane` the agent asserted is
                # overwritten by the derived value (the spec guarantee: plane is derived,
                # never asserted). Unknown provenances → "external" (conservative: an
                # unknown source is treated as external for safety).
                fact_prov = enriched.get("provenance", prov)
                try:
                    enriched["plane"] = plane_for(fact_prov)
                except KeyError:
                    enriched["plane"] = "external"
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

    # -----------------------------------------------------------------------
    # 4b. Scientific mechanism reasoning (rescue-ranking queries only)
    # -----------------------------------------------------------------------
    # For a "rank genes that rescue the <TARGET>-KO phenotype" question, run the scientific-core
    # reasoner over the moat's ranked rescue-gene candidates + the literature already gathered, to
    # produce a plausible, CITED mechanism per gene. The rescue-mechanism agent is simulate_exempt →
    # it does REAL reasoning even when the rest of the firm is stubbed (the science IS the
    # deliverable). DATA BOUNDARY: only PUBLIC identifiers cross to it — gene symbols + ORDINAL rank,
    # never the raw moat cosines (those stay here, for the ranked view). Non-rescue queries skip this
    # entirely (rescue_ranked/gene_mechanisms stay empty → the existing IND synthesis runs unchanged).
    rescue_ranked: list[dict] = []
    gene_mechanisms: list[dict] = []
    if _is_rescue_ranking_query(query) and target and "rescue-mechanism" in known_ids:
        rescue_ranked = rescue_genes(target, k=8)  # structured: rank/gene/cosine (cosine kept local)
        if rescue_ranked:
            # The cited public literature already in the dossier (EMET / corpus) is the grounding set.
            evidence = [
                {"claim": f.get("value", "")[:300],
                 "source": f.get("source", "") or f.get("url", "")}
                for f in all_dossier_facts
                if f.get("provenance") in ("emet-live", "emet-mcp", "corpus") and f.get("value")
            ][:12]
            mech_inputs = {
                "target": target,
                "disease": tri.get("disease_label", ""),
                # PUBLIC ONLY: gene symbol + ordinal rank — no cosine / no internal score crosses.
                "candidates": [{"gene": r["gene"], "rank": r["rank"]} for r in rescue_ranked],
                "evidence": evidence,
            }
            _emit(on_progress, eid, {"stage": "bucket1", "agent_id": "rescue-mechanism",
                                     "phase": "start"})
            _t0 = time.monotonic()
            mres = harness.run("rescue-mechanism", mech_inputs,
                               engagement_id=eid, ctx=ctx, registry=registry)
            _elapsed = round(time.monotonic() - _t0, 2)
            if mres.ok and mres.output:
                gene_mechanisms = mres.output.get("gene_mechanisms", []) or []
            # Enforce "cite or hedge" MECHANICALLY (defense in depth — the JSON schema cannot): an
            # uncited high/medium claim is downgraded to low, so a confident-but-unsupported mechanism
            # can never be presented as well-grounded. The agent is instructed to do this; this makes
            # it a guarantee regardless of what the model returns.
            for gm in gene_mechanisms:
                if gm.get("confidence") in ("high", "medium") and not (gm.get("citations") or []):
                    gm["confidence"] = "low"
            # Surface each cited mechanism as a dossier fact (provenance scientific-reasoning).
            for gm in gene_mechanisms:
                cites = ", ".join(gm.get("citations", []) or [])
                val = f"Rescue mechanism — {gm.get('gene', '')}: {gm.get('mechanism', '')}"
                if cites:
                    val += f" [{cites}]"
                all_dossier_facts.append({
                    "value": val,
                    "source": "Sapphire scientific reasoning (cites EMET/corpus literature)",
                    "tier": "T3",
                    "provenance": "scientific-reasoning",
                    "plane": plane_for("scientific-reasoning"),
                    "field": "rescue mechanism",
                })
            agent_statuses.append({
                "id": "rescue-mechanism", "status": mres.status, "provenance": mres.provenance,
            })
            if not mres.ok:
                abstained_agents.append("rescue-mechanism")
            _emit(on_progress, eid, {
                "stage": "bucket1", "agent_id": "rescue-mechanism", "phase": "done",
                "status": mres.status, "provenance": mres.provenance,
                "n_facts": len(gene_mechanisms), "elapsed_s": _elapsed,
                "error": mres.error if not mres.ok else None,
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

    # Live progress: Bucket-1 flags computed (VETO ⛔ / DIVERGENCE ⚠ / known-unknowns).
    _emit(on_progress, eid, {
        "stage": "flags", "phase": "done",
        "n_veto": len(veto_flags), "n_divergence": len(divergence_flags),
        "n_known_unknowns": len(known_unknowns), "n_facts": len(all_dossier_facts),
    })

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

        # Live progress: this persona is deliberating (round 1).
        _emit(on_progress, eid, {"stage": "roundtable", "agent_id": persona_name,
                                 "phase": "start", "round": 1})
        _t0 = time.monotonic()

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

        _elapsed = round(time.monotonic() - _t0, 2)
        if res.ok and res.output:
            verdict = dict(res.output)
            verdict.setdefault("provenance", res.provenance)
            verdict["status"] = res.status
            round1.append(verdict)
        else:
            verdict = {
                "persona": persona_name,
                "lens": lens,
                "stance": "hold",
                "conviction": 0,
                "rationale": f"abstained ({res.error or 'unknown'})",
                "fact_claims": [],
                "provenance": res.provenance,
                "status": res.status,
            }
            round1.append(verdict)

        # Live progress: this persona's verdict landed — stance·conviction, or honest abstention.
        _emit(on_progress, eid, {
            "stage": "roundtable", "agent_id": persona_name, "phase": "done", "round": 1,
            "status": verdict.get("status", res.status),
            "stance": verdict.get("stance"), "conviction": verdict.get("conviction"),
            "elapsed_s": _elapsed,
        })

    # -----------------------------------------------------------------------
    # 6. Synthesis — deterministic assembly
    # -----------------------------------------------------------------------
    _emit(on_progress, eid, {"stage": "synthesis", "phase": "start"})
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

    # Rescue-ranking deliverable: when the query asked to RANK genes that rescue the KO, the
    # synthesis IS a ranked gene table — merge the moat rank/cosine (internal, shown as the
    # evidence basis) with each gene's cited mechanism. This OVERRIDES the IND-style recommendation
    # computed above. Empty rescue_ranked (any non-rescue query) ⇒ this block is skipped entirely.
    ranked_genes: list[dict] = []
    if rescue_ranked:
        mech_by_gene = {gm.get("gene", "").upper(): gm for gm in gene_mechanisms}
        for r in rescue_ranked:
            gm = mech_by_gene.get(r["gene"].upper(), {})
            ranked_genes.append({
                "rank": r["rank"],
                "gene": r["gene"],
                "cosine": r["cosine"],            # Quiver EP-signature reversal strength (internal)
                "mechanism": gm.get("mechanism", ""),
                "citations": gm.get("citations", []) or [],
                "confidence": gm.get("confidence", "low"),
                "source": r.get("source", ""),
            })
        grounded = [g for g in ranked_genes if g["citations"]]
        top = ranked_genes[:5]
        top_str = "; ".join(f"{g['rank']}. {g['gene']}" for g in top)
        recommendation = (
            f"Top rescue-gene candidates for {target}-KO, ranked by Quiver EP-signature reversal "
            f"with literature-grounded mechanism: {top_str}."
        )
        confidence = "high" if len(grounded) >= 3 else ("medium" if grounded else "low")
        proposed_experiment = (
            f"Validate the top rescue-gene candidate(s) ({', '.join(g['gene'] for g in top[:3])}) "
            f"against the {target}-KO phenotype in a disease-relevant CNS model."
        )

    syn = {
        "recommendation": recommendation,
        "confidence": confidence,
        "proposed_experiment": proposed_experiment,
        "entities": ents,
    }
    if ranked_genes:
        syn["ranked_genes"] = ranked_genes

    # Live progress: synthesis done — the recommendation + confidence.
    _emit(on_progress, eid, {
        "stage": "synthesis", "phase": "done",
        "recommendation": recommendation, "confidence": confidence,
    })

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
