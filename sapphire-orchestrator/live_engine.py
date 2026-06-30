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
import concurrent.futures
import threading

# Ensure the sapphire-orchestrator package root is on sys.path when called from tests CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from orchestrator import Orchestrator
from engagement import extract_entities, _eid, _GENE_RE
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
    # DEA scheduling classification — controlled-substance regulatory constraint.
    "dea-scheduling",
    # Manufacturing / CMC readiness — supply chain and formulation feasibility.
    "manufacturing-cmc",
    # Patient advocacy landscape — patient community sentiment and unmet need.
    "patient-advocacy",
    # KOL / social signal — expert opinion and pre-publication intelligence.
    "kol-social",
    # Policy / legislative environment — congressional and regulatory policy trends.
    "policy-legislative",
    # Reputational risk screen — press, litigation, and ESG signal.
    "reputational",
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

# Fast membership test for approved_plan filtering (WO 1.2).
_BUCKET1_AGENTS_SET: frozenset = frozenset(_BUCKET1_AGENTS)

# ---------------------------------------------------------------------------
# Concurrency cap for Bucket-1 parallel dispatch.
# Threads are ideal for subprocess/I-O-bound agents (each `claude -p` call blocks
# on a subprocess, not the GIL). Default 8; override via the env at process start
# (the constant is read once at import; changing the env after import has no effect
# without patching `_MAX_BUCKET1_WORKERS` directly).
# Set to 1 to reproduce the former serial behavior exactly (regression path).
# ---------------------------------------------------------------------------
_MAX_BUCKET1_WORKERS: int = max(1, int(os.environ.get("SAPPHIRE_BUCKET1_CONCURRENCY", "8")))

# Lock protecting the `on_progress` callback invocation from concurrent Bucket-1 threads.
# The callback is user-supplied and may not be thread-safe (e.g. a list.append without a
# lock). Serialising through `_PROGRESS_LOCK` prevents interleaved calls while keeping
# the callback as a pure best-effort side channel (all exceptions are still swallowed).
_PROGRESS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Adaptive convergence loop (WOs 2.1–2.5) — OPT-IN (adaptive=False default)
# ---------------------------------------------------------------------------

# v1 redispatch targets: CHEAP, DETERMINISTIC, no paid external API.
# EMET is intentionally excluded (paid/slow/login-gated — a later flag).
# "internal-science-lead" → moat (real internal DB lookup, stdlib-only engine).
# The three public-API seams (gnomad/gtex/interpro) fire only when a gene is present;
# they honest-empty when the gene is not found — so a spurious entity is harmless.
REDISPATCH_TARGETS: list[str] = [
    "internal-science-lead",  # real moat (Quiver internal; python kind; stdlib seam)
    "gnomad-constraint",       # gnomAD pLI / LOEUF (public; stdlib urllib seam)
    "gtex-expression",         # GTEx TPM + CNS selectivity (public; stdlib urllib seam)
    "interpro-domains",        # InterPro domain annotations (public; stdlib urllib seam)
]

_MAX_ADAPTIVE_ROUNDS: int = 2     # max convergence rounds after the initial Bucket-1 pass
_MAX_ADAPTIVE_DISPATCHES: int = 6  # max total follow-up harness.run calls across all rounds
_ADAPTIVE_SALIENCE_THRESHOLD: int = 2  # minimum salience score to trigger re-dispatch


def extract_salient_entities(
    facts: list[dict],
    already_covered: set[str],
) -> list[dict]:
    """Scan returned facts[].value for gene-symbol tokens NOT in already_covered.

    Pure function — stdlib only, no I/O.

    Salience (deterministic, explainable):
      - Base: +1 per occurrence of the entity in any fact.
      - +1 if the containing fact has tier "T1" or "T2" (high-quality source).
      - +2 if the containing fact carries flag "DIVERGENCE" or "VETO" (high-signal).
      - +2 cross-agent bonus if the entity appears in facts from ≥ 2 distinct
        source agents (corroboration across independent sources). Each fact may
        carry a ``_source_agent`` key for this computation; facts without it are
        treated as from the same anonymous agent and do NOT contribute to the bonus.

    already_covered: entity symbols to exclude (original query genes + any entity
    already re-dispatched in a prior round).

    Returns:
        list of {entity: str, salience: int, source_agent: str} sorted descending
        by salience, filtered to salience >= _ADAPTIVE_SALIENCE_THRESHOLD.
        Returns [] if no new qualifying entities are found.
    """
    # entity → {salience: int, source_agent: str, agents: set[str]}
    scores: dict[str, dict] = {}

    for fact in facts:
        value = fact.get("value") or ""
        tier = fact.get("tier", "")
        flag = fact.get("flag", "")
        src = fact.get("_source_agent", "")  # optional internal annotation

        tokens = set(_GENE_RE.findall(value))
        for tok in tokens:
            if tok in already_covered:
                continue
            if tok not in scores:
                scores[tok] = {
                    "salience": 0,
                    "source_agent": src or "unknown",
                    "agents": set(),
                }
            entry = scores[tok]
            entry["salience"] += 1            # base: one occurrence
            if tier in ("T1", "T2"):
                entry["salience"] += 1        # quality tier bonus
            if flag in ("DIVERGENCE", "VETO"):
                entry["salience"] += 2        # high-signal flag bonus
            if src:
                entry["agents"].add(src)

    # Cross-agent bonus: entity appears in facts from ≥ 2 distinct agents.
    for entry in scores.values():
        if len(entry["agents"]) >= 2:
            entry["salience"] += 2

    # Filter to threshold, sort descending.
    result = [
        {
            "entity": tok,
            "salience": entry["salience"],
            "source_agent": entry["source_agent"],
        }
        for tok, entry in scores.items()
        if entry["salience"] >= _ADAPTIVE_SALIENCE_THRESHOLD
    ]
    result.sort(key=lambda x: x["salience"], reverse=True)
    return result


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
            with _PROGRESS_LOCK:
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


def _run_one_bucket1_agent(
    agent_id: str,
    known_ids: set,
    bucket1_inputs: dict,
    query: str,
    ents: dict,
    eid: str,
    ctx: dict,
    registry,
    batched_outputs: dict,
    on_progress,
    adaptive: bool,
):
    """Worker executed in a ThreadPoolExecutor thread for one Bucket-1 agent.

    Thread-safety contract
    ----------------------
    * ``ctx["_cache"]`` is isolated: each worker receives a shallow copy of ctx
      with its own ``_cache`` dict, so concurrent agents never see each other's
      cached ``AgentResult`` mid-run (each agent has a unique inputs_hash anyway,
      but the dict itself is not thread-safe for concurrent writes).
    * ``ctx["python_fns"]``, ``ctx["runner"]``, ``ctx["emet_handler"]`` etc. are
      read-only after ``run_live`` wires them — safe to share across threads.
    * ``trace._append`` is locked inside the trace module (``_APPEND_LOCK``), so
      concurrent corpus-retrieval and harness trace writes are safe.
    * ``on_progress`` is called inside ``_PROGRESS_LOCK`` via ``_emit()`` — safe
      for non-thread-safe callbacks like bare list.append.
    * No reference to ``all_dossier_facts``, ``agent_statuses``, etc. — those are
      collected by the CALLER from the returned tuple after the pool joins.

    Returns
    -------
    ``(agent_id, res, corpus_cards, _annot_facts_local)`` on success, or ``None``
    if the agent is not in the registry (caller skips it).
    ``_annot_facts_local`` is a list of annotated facts (only populated when
    ``adaptive=True``) — the caller merges into ``_annot_facts`` after join.
    """
    if agent_id not in known_ids:
        return None

    corpus_cards = (
        read_corpus(agent_id, query, ents) if has_corpus(agent_id) else []
    )
    agent_inputs = (
        {**bucket1_inputs, "corpus_hits": corpus_cards}
        if corpus_cards else bucket1_inputs
    )

    # Per-thread ctx: shallow copy + isolated _cache dict.
    # Shared read-only references (python_fns, runner, emet_handler, batch_buckets)
    # are intentionally kept as the SAME objects — copying callables is unnecessary
    # and would break identity checks inside the harness.
    thread_ctx = {**ctx, "_cache": dict(ctx.get("_cache", {}))}

    # Opt-2 batch: if this agent's output was pre-generated by the batch call,
    # use a const dispatch_fn so the output flows through the full harness path
    # (validation / guardrails / provenance stamp / trace) unchanged — only the
    # generation transport changes (same as today's serial behavior for batch mode).
    disp_fn = None
    if agent_id in batched_outputs:
        _o = batched_outputs[agent_id]
        disp_fn = lambda contract, inputs, _ctx, _o=_o: _o  # noqa: E731

    _emit(on_progress, eid, {"stage": "bucket1", "agent_id": agent_id, "phase": "start"})
    _t0 = time.monotonic()

    res = harness.run(
        agent_id,
        agent_inputs,
        engagement_id=eid,
        ctx=thread_ctx,
        registry=registry,
        dispatch_fn=disp_fn,
    )

    _elapsed = round(time.monotonic() - _t0, 2)
    _n_facts = (
        (len(res.output.get("facts", [])) if (res.ok and res.output) else 0)
        + len(corpus_cards)
    )
    _emit(on_progress, eid, {
        "stage": "bucket1", "agent_id": agent_id, "phase": "done",
        "status": res.status, "provenance": res.provenance,
        "n_facts": _n_facts, "elapsed_s": _elapsed,
        "error": res.error if not res.ok else None,
    })

    # Collect _annot_facts locally (only populated when adaptive=True).
    _annot_facts_local: list[dict] = []
    if adaptive and res.ok and res.output:
        for f in res.output.get("facts", []):
            enriched = dict(f)
            enriched.setdefault("provenance", res.output.get("provenance", res.provenance))
            _annot_facts_local.append({**enriched, "_source_agent": agent_id})

    return (agent_id, res, corpus_cards, _n_facts, _annot_facts_local)


def run_live(
    query: str,
    *,
    sequences: list[str] | None = None,
    structure: dict | None = None,
    ctx: dict | None = None,
    registry=None,
    engine: Orchestrator | None = None,
    on_progress=None,
    plan_mode: str = "off",
    approved_plan: list[str] | None = None,
    adaptive: bool = False,
) -> dict:
    """
    Run a full Sapphire engagement with every agent dispatched through the harness.

    Parameters
    ----------
    query         : the free-text question / task.
    sequences     : optional list of ASO candidate sequences (e.g. ["GCACTTGAATTTCACGTTGT"]).
                    When provided, sequences are threaded into every Bucket-1 agent's inputs
                    so the aso-tox agent can score them.  If None (default), the function
                    falls back to extracting pure A/T/G/C tokens of length ≥ 15 from the
                    query text via _extract_aso_sequences().
                    NOTE: this is the documented handoff point for the future ASO-Design tool —
                    that tool will pass its designed sequences here after its own dispatch.
    structure     : optional dict of Boltz STRUCTURE/AFFINITY inputs — public identifiers only:
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
    ctx           : optional harness context dict (inject mock backends for testing).
    registry      : optional pre-loaded agents.json dict (default: harness.load_registry()).
    engine        : optional Orchestrator instance (default: new Orchestrator()).
    plan_mode     : controls Bucket-1 agent selection strategy:
                    "off" (default) — run all _BUCKET1_AGENTS (deterministic; backward-compat).
                    "llm"           — call smart_plan to select a relevant subset; fall back to
                                      deterministic on any smart_plan failure.
                    "llm+approve"   — call smart_plan and return immediately with
                                      plan_pending_approval=True without running any agents.
                                      The caller (front-door / LOKA) must approve and then
                                      re-call with approved_plan=<ids>.
    approved_plan : when not None, run ONLY these agent ids (filtered to known registry ids
                    and _BUCKET1_AGENTS); overrides plan_mode (smart_plan is skipped).
    adaptive      : when True, enable the adaptive convergence loop (WOs 2.1–2.5).
                    After the initial Bucket-1 pass, scan returned facts for new
                    high-salience gene-symbol entities not covered by the original
                    query; re-dispatch the REDISPATCH_TARGETS agents for each surfaced
                    entity; fold new facts into the dossier; repeat up to
                    _MAX_ADAPTIVE_ROUNDS rounds or _MAX_ADAPTIVE_DISPATCHES total
                    follow-up calls.  Default False (OPT-IN, Gate-5 validated).
                    MUST reproduce today's output byte-for-byte when False.

    Returns
    -------
    A structured dict with keys:
        query, plan, priors, discover, consult, synthesize, engagement_id,
        reflection, _via, plan_source.

    For plan_mode="llm+approve" returns early with:
        query, plan, plan_pending_approval, smart_plan (or absent on fallback),
        plan_source, engagement_id, _via="harness-live-plan".
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

    # Bucket-1 selection defaults — overridden below by plan_mode or approved_plan.
    selected_ids: list[str] = list(_BUCKET1_AGENTS)  # default: full deterministic list
    plan_source: str = "deterministic"
    smart_plan_rationale: dict | None = None

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
    # 2b. Plan-mode routing — approved_plan overrides plan_mode; smart_plan is
    #     called lazily only for plan_mode in ("llm", "llm+approve").
    # -----------------------------------------------------------------------
    if approved_plan is not None:
        # Explicit approved_plan takes full precedence over plan_mode.
        # Filter to agents that exist in the registry AND are Bucket-1 agents
        # (silently drop unknown or out-of-bucket ids — never crash).
        selected_ids = [i for i in approved_plan
                        if i in known_ids and i in _BUCKET1_AGENTS_SET]
        if not selected_ids:
            # All client-supplied ids were unknown/out-of-bucket — running zero
            # fact agents silently yields a fact-free dossier. Mirror the llm
            # empty-selection guard: fall back to the full deterministic list.
            trace.record(eid, {"type": "plan_fallback",
                               "reason": "approved_plan all-filtered (no valid bucket-1 ids)"})
            selected_ids = list(_BUCKET1_AGENTS)
            plan_source = "deterministic"
        else:
            plan_source = "approved"
    elif plan_mode.lower() == "llm+approve":
        # Compute the LLM plan, then return immediately WITHOUT running any agents.
        # The caller (front-door / LOKA) approves and re-calls with approved_plan.
        # We close the engagement trace before every early return so that
        # trace_view / reflect() see a clean open→close pair, not a "crashed run".
        try:
            from smart_plan import smart_plan as _sp
            _sp_result = _sp(query, plan, registry, ctx)
            # Build the narrative — prefer the LLM-produced one (it's query-specific);
            # fall back to the deterministic builder when absent/malformed or when
            # the data-boundary scrub fires (defense-in-depth: the prompt says
            # "public identifiers only" but we also check mechanically).
            from plan_narrative import (build_deterministic_narrative as _build_narr,
                                        FORBIDDEN_NARRATIVE_TERMS as _FORBIDDEN,
                                        _scrub_narrative_text as _scrub_text)
            _raw_narrative = _sp_result.get("narrative") or None
            _narrative_is_llm = (
                isinstance(_raw_narrative, dict)
                and bool(_raw_narrative.get("framing"))
                and isinstance(_raw_narrative.get("steps"), list)
                and len(_raw_narrative["steps"]) > 0
                # Data-boundary scrub: reject any narrative that contains a forbidden
                # internal-score term (case-insensitive scan of all text fields).
                and not _scrub_text(_raw_narrative)
            )
            if _narrative_is_llm:
                # Stamp source="llm" so the card knows this prose is LLM-authored.
                _llm_narrative = dict(_raw_narrative)
                _llm_narrative["source"] = "llm"
            else:
                # LLM did not produce a narrative (or it was scrubbed) — synthesise
                # deterministically. builder already stamps source="deterministic".
                _selected_ids_for_narr = [
                    a["id"] for a in _sp_result.get("selected_agents", []) if a.get("id")
                ] or list(_BUCKET1_AGENTS)
                _llm_narrative = _build_narr(query, public_plan, _selected_ids_for_narr,
                                             panel=panel)
            trace.close_engagement(eid, {"note": "plan_pending_approval", "plan_source": "llm"})
            return {
                "query": query,
                "plan": public_plan,
                "plan_pending_approval": True,
                "smart_plan": _sp_result,
                "narrative": _llm_narrative,
                "plan_source": "llm",
                "engagement_id": eid,
                "_via": "harness-live-plan",
            }
        except Exception as _e:
            trace.record(eid, {"type": "plan_fallback", "reason": str(_e)})
            # Fall back to a deterministic plan-only envelope (no agents ran).
            from plan_narrative import build_deterministic_narrative as _build_narr
            _det_narrative = _build_narr(query, public_plan, list(_BUCKET1_AGENTS), panel=panel)
            trace.close_engagement(eid, {"note": "plan_pending_approval", "plan_source": "deterministic"})
            return {
                "query": query,
                "plan": public_plan,
                "plan_pending_approval": True,
                "narrative": _det_narrative,
                "plan_source": "deterministic",
                "engagement_id": eid,
                "_via": "harness-live-plan",
            }
    elif plan_mode.lower() == "llm":
        # Let the LLM prune the Bucket-1 panel; fall back to the full deterministic
        # list on any smart_plan failure (never raises to the caller).
        try:
            from smart_plan import smart_plan as _sp
            _sp_result = _sp(query, plan, registry, ctx)
            selected_ids = [a["id"] for a in _sp_result.get("selected_agents", [])]
            if not selected_ids:
                # An empty LLM selection is not an exception, but running zero
                # Bucket-1 agents yields no facts — fall back to deterministic.
                trace.record(eid, {"type": "plan_fallback",
                                   "reason": "smart_plan returned empty selection"})
                selected_ids = list(_BUCKET1_AGENTS)
                plan_source = "deterministic"
            else:
                plan_source = "llm"
                smart_plan_rationale = _sp_result
        except Exception as _e:
            trace.record(eid, {"type": "plan_fallback", "reason": str(_e)})
            # selected_ids and plan_source stay at their deterministic defaults.
    # else: plan_mode "off" or any unrecognised value — keep deterministic defaults.

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

    # Annotated facts list: parallel to all_dossier_facts, each entry carries
    # "_source_agent" key for the adaptive salience computation. Only populated
    # when adaptive=True; always empty (and unused) when adaptive=False.
    _annot_facts: list[dict] = []

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

    # Emit a plan trace event so the run is auditable: which plan_source drove
    # Bucket-1 and what the LLM rationale was (None for deterministic/approved).
    trace.record(eid, {
        "type": "plan",
        "plan_source": plan_source,
        "selected_ids": selected_ids,
        "rationale": smart_plan_rationale,
    })

    # ── Parallel Bucket-1 dispatch ───────────────────────────────────────────
    # Submit all selected Bucket-1 agents concurrently. Each agent is I/O-bound
    # (shells out to `claude -p` or a seam subprocess), so threads are ideal here;
    # the GIL is released for the duration of each subprocess.run() call.
    #
    # Concurrency cap: SAPPHIRE_BUCKET1_CONCURRENCY (default 8, module constant
    # _MAX_BUCKET1_WORKERS). Set to 1 to reproduce today's serial behaviour exactly.
    #
    # Thread-safety:
    #   • trace writes   → _APPEND_LOCK inside harness/trace.py
    #   • ctx["_cache"]  → each worker gets its own shallow-copied cache dict
    #   • on_progress    → serialised through _PROGRESS_LOCK in _emit()
    #   • dossier lists  → workers DO NOT write to shared lists; results are
    #     collected from futures AFTER the pool joins, in selected_ids order.
    _num_scheduled = sum(1 for aid in selected_ids if aid in known_ids)
    _n_workers = min(_MAX_BUCKET1_WORKERS, max(1, _num_scheduled))

    # Map agent_id → Future result (submitted in selected_ids order so the
    # dict preserves insertion order; results are also merged in that order below).
    _futures: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=_n_workers) as _pool:
        for agent_id in selected_ids:
            if agent_id not in known_ids:
                continue
            fut = _pool.submit(
                _run_one_bucket1_agent,
                agent_id, known_ids, bucket1_inputs,
                query, ents, eid, ctx, registry,
                batched_outputs, on_progress, adaptive,
            )
            _futures[agent_id] = fut
    # Pool __exit__ blocks until all futures complete — the merge below is safe.

    # Merge results in the ORIGINAL selected_ids order so discover.agents and
    # the dossier ordering are deterministic regardless of thread completion order.
    for agent_id in selected_ids:
        if agent_id not in _futures:
            continue
        result_tuple = _futures[agent_id].result()  # re-raises any worker exception
        if result_tuple is None:
            continue  # agent was absent from registry (skipped inside worker)
        _, res, corpus_cards, _n_facts, _annot_facts_local = result_tuple

        agent_statuses.append({
            "id": agent_id,
            "status": res.status,
            "provenance": res.provenance,
            # Persist the per-agent fact count so a restored run (which has no live
            # trace) can show each agent's REAL contribution instead of mis-attributing
            # by shared provenance. Mirrors the n_facts in the live progress event above.
            "n_facts": _n_facts,
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

        # Merge adaptive annotated facts (worker collected them; merge here after join).
        if adaptive:
            _annot_facts.extend(_annot_facts_local)
            # Also annotate corpus facts for adaptive.
            for _cf in ([_corpus_card_to_fact(agent_id, c) for c in corpus_cards] if corpus_cards else []):
                _annot_facts.append({**_cf, "_source_agent": agent_id})

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
        # Top-K rescuers. K=6 bounds the real claude mechanism call (~35s/gene observed) under the
        # agent timeout while still giving a substantive ranked list. cosine is kept LOCAL (the view),
        # never sent to the agent.
        rescue_ranked = rescue_genes(target, k=6)
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
                if adaptive:
                    _annot_facts.append({
                        "value": val,
                        "source": "Sapphire scientific reasoning (cites EMET/corpus literature)",
                        "tier": "T3",
                        "provenance": "scientific-reasoning",
                        "plane": plane_for("scientific-reasoning"),
                        "field": "rescue mechanism",
                        "_source_agent": "rescue-mechanism",
                    })
            agent_statuses.append({
                "id": "rescue-mechanism", "status": mres.status, "provenance": mres.provenance,
                "n_facts": len(gene_mechanisms),
            })
            if not mres.ok:
                abstained_agents.append("rescue-mechanism")
            _emit(on_progress, eid, {
                "stage": "bucket1", "agent_id": "rescue-mechanism", "phase": "done",
                "status": mres.status, "provenance": mres.provenance,
                "n_facts": len(gene_mechanisms), "elapsed_s": _elapsed,
                "error": mres.error if not mres.ok else None,
            })

    # -----------------------------------------------------------------------
    # 4c. Adaptive convergence loop (WOs 2.1–2.5) — OPT-IN (adaptive=False skips)
    #
    # After the initial Bucket-1 pass (4 + 4b), scan returned facts for new
    # high-salience gene-symbol entities not in the original query.  For each,
    # re-dispatch the CHEAP DETERMINISTIC REDISPATCH_TARGETS agents through harness.run
    # (guards/provenance/trace fire identically to the main loop).  Fold any new
    # facts back into all_dossier_facts and _annot_facts.  Repeat for up to
    # _MAX_ADAPTIVE_ROUNDS rounds or _MAX_ADAPTIVE_DISPATCHES total dispatches.
    #
    # Termination is GUARANTEED by three independent caps:
    #   1. _MAX_ADAPTIVE_ROUNDS (2): loop exits after at most 2 convergence passes.
    #   2. _MAX_ADAPTIVE_DISPATCHES (6): total dispatch_budget counter.
    #   3. already_covered_adaptive: entities re-dispatched in prior rounds are
    #      added here, so extract_salient_entities never re-surfaces them.
    # A "pathological all-genes" input terminates as soon as budget=0.
    # -----------------------------------------------------------------------
    if adaptive:
        already_covered_adaptive: set[str] = set(ents.get("genes", []))
        visited: set[tuple[str, str]] = set()   # (entity, agent_id) pairs dispatched
        dispatch_budget: int = _MAX_ADAPTIVE_DISPATCHES

        for _rnd in range(1, _MAX_ADAPTIVE_ROUNDS + 1):
            if dispatch_budget <= 0:
                break

            salient = extract_salient_entities(_annot_facts, already_covered_adaptive)
            if not salient:
                break  # no new entities above threshold — dossier converged

            _any_dispatched_this_round = False

            for _ent_rec in salient:
                if dispatch_budget <= 0:
                    break

                _entity = _ent_rec["entity"]
                _source_agent = _ent_rec["source_agent"]
                _target_agents_fired: list[str] = []

                for _target_id in REDISPATCH_TARGETS:
                    if dispatch_budget <= 0:
                        break
                    if (_entity, _target_id) in visited:
                        continue  # never dispatch a (entity, agent) pair twice
                    if _target_id not in known_ids:
                        continue  # skip agents absent from the registry

                    visited.add((_entity, _target_id))

                    # Build redispatch inputs: ONLY the public gene SYMBOL crosses.
                    # Sequences and structure inputs are excluded (gene-level re-query
                    # doesn't need ASO/structure data).
                    _rd_inputs: dict = {
                        "candidate": _entity,           # public gene symbol ONLY
                        "genes": [_entity],             # one-element gene set
                        "disease": bucket1_inputs.get("disease", ""),
                        "query": bucket1_inputs.get("query", ""),
                        "sequences": [],                # no ASO sequences in re-query
                    }

                    # WO 2.4 — progress: redispatch start milestone
                    _emit(on_progress, eid, {
                        "stage": "redispatch", "phase": "start",
                        "round": _rnd, "entity": _entity,
                        "target_agent": _target_id,
                    })
                    _t0_rd = time.monotonic()

                    _rd_res = harness.run(
                        _target_id,
                        _rd_inputs,
                        engagement_id=eid,
                        ctx=ctx,
                        registry=registry,
                    )

                    _elapsed_rd = round(time.monotonic() - _t0_rd, 2)
                    dispatch_budget -= 1
                    _target_agents_fired.append(_target_id)
                    _any_dispatched_this_round = True

                    # Fix #1 (auditability): append this redispatch to agent_statuses
                    # so re-dispatched agents appear in discover["agents"].  The
                    # "phase"/"redispatch_round"/"trigger_entity" keys distinguish these
                    # entries from the initial Bucket-1 pass for monitoring consumers.
                    agent_statuses.append({
                        "id": _target_id,
                        "status": _rd_res.status,
                        "provenance": _rd_res.provenance,
                        "n_facts": (
                            len(_rd_res.output.get("facts", []))
                            if (_rd_res.ok and _rd_res.output) else 0
                        ),
                        "phase": "redispatch",
                        "redispatch_round": _rnd,
                        "trigger_entity": _entity,
                    })

                    # Fold new facts into all_dossier_facts (+ _annot_facts for
                    # further convergence rounds).  Stamp provenance + plane
                    # exactly like the main Bucket-1 loop.
                    if _rd_res.ok and _rd_res.output:
                        _rd_facts = _rd_res.output.get("facts", [])
                        _rd_prov = _rd_res.output.get("provenance", _rd_res.provenance)
                        for _f in _rd_facts:
                            _enriched = dict(_f)
                            _enriched.setdefault("provenance", _rd_prov)
                            _f_prov = _enriched.get("provenance", _rd_prov)
                            try:
                                _enriched["plane"] = plane_for(_f_prov)
                            except KeyError:
                                _enriched["plane"] = "external"
                            all_dossier_facts.append(_enriched)
                            _annot_facts.append({**_enriched, "_source_agent": _target_id})
                            _f_flag = _f.get("flag")
                            if _f_flag == "VETO":
                                veto_flags.append(_f.get("value", ""))
                            elif _f_flag == "DIVERGENCE":
                                divergence_flags.append(_f.get("value", ""))

                    # WO 2.4 — progress: redispatch done milestone
                    _emit(on_progress, eid, {
                        "stage": "redispatch", "phase": "done",
                        "round": _rnd, "entity": _entity,
                        "target_agent": _target_id,
                        "status": _rd_res.status,
                        "n_new_facts": (
                            len(_rd_res.output.get("facts", []))
                            if (_rd_res.ok and _rd_res.output) else 0
                        ),
                        "elapsed_s": _elapsed_rd,
                    })

                # WO 2.4 — trace: ONE redispatch event per entity per round.
                # Best-effort: a trace failure never breaks the run.
                if _target_agents_fired:
                    try:
                        trace.record(eid, {
                            "type": "redispatch",
                            "round": _rnd,
                            "trigger_entity": _entity,
                            "source_agent": _source_agent,
                            "target_agents": _target_agents_fired,
                            "reason": f"salience={_ent_rec['salience']}",
                        })
                    except Exception:
                        pass

                # Mark entity as covered so it is not re-surfaced in later rounds.
                # Intentional trade-off: the entity is marked covered even when budget
                # depleted mid-dispatch (e.g. 2 of 4 targets fired before budget hit 0).
                # The remaining (entity, target_id) pairs become unreachable — they are
                # not in visited (so no guard fires) but budget=0 prevents any dispatch.
                # This is by design: once budget is exhausted, further coverage of that
                # entity is deferred to a future engagement (the spec allows this).
                already_covered_adaptive.add(_entity)

            if not _any_dispatched_this_round:
                break  # nothing new dispatched this round — converged

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
    # VETO gate: when VETO facts are present, surface them as first-class
    # adjudication input into every persona's round-1 dispatch, and record a
    # trace landmark so the gate is auditable mid-run.
    veto_is_active = bool(veto_flags)
    if veto_is_active:
        trace.record(eid, {
            "type": "veto_gate",
            "veto_facts": veto_flags,
            "n_veto": len(veto_flags),
        })

    round1: list[dict] = []

    for p in panel:
        persona_name = p.get("persona", "")
        lens = p.get("lens", "")

        # Build a compact dossier field list for the partner to reference.
        dossier_fields = list({f.get("value", "")[:80] for f in all_dossier_facts})[:10]

        # VETO gate: when active, prepend VETO-adjudication markers so the
        # persona receives the gate condition as first-class input (capped to 12).
        if veto_is_active:
            veto_markers = ["[VETO ADJUDICATION] " + v[:80] for v in veto_flags]
            dossier_fields = (veto_markers + dossier_fields)[:12]

        if "company-partner" not in known_ids:
            continue

        # Live progress: this persona is deliberating (round 1).
        _emit(on_progress, eid, {"stage": "roundtable", "agent_id": persona_name,
                                 "phase": "start", "round": 1})
        _t0 = time.monotonic()

        persona_inputs: dict = {
            "persona": persona_name,
            "lens": lens,
            "dossier_fields": dossier_fields,
        }
        if veto_is_active:
            persona_inputs["veto_adjudication"] = veto_flags

        res = harness.run(
            "company-partner",
            persona_inputs,
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
    # 5b. Bucket 2 — Round 2 (rebuttal) + spread
    # -----------------------------------------------------------------------
    # Compact round-1 summary threaded into each persona's round-2 prompt so
    # they can revise or reaffirm in light of their peers' initial verdicts.
    round1_verdicts = [
        {
            "persona": v.get("persona", ""),
            "stance": v.get("stance", "conditional"),
            "conviction": v.get("conviction", 0),
            "rationale": (v.get("rationale") or "")[:150],
        }
        for v in round1
        if isinstance(v, dict)
    ]

    round2: list[dict] = []

    for p in panel:
        persona_name = p.get("persona", "")
        lens = p.get("lens", "")

        dossier_fields_r2 = list({f.get("value", "")[:80] for f in all_dossier_facts})[:10]

        if "company-partner" not in known_ids:
            continue

        # Locate this persona's round-1 entry for comparison (revised detection).
        r1_verdict = next(
            (v for v in round1 if v.get("persona") == persona_name), {}
        )
        r1_stance = r1_verdict.get("stance", "hold")
        r1_conviction = r1_verdict.get("conviction", 0)

        # Live progress: round-2 rebuttal starting (distinct phase name — must not
        # collide with "start"/"done" so the existing stage-order test keeps passing).
        _emit(on_progress, eid, {
            "stage": "roundtable", "agent_id": persona_name,
            "phase": "rebuttal_start", "round": 2,
        })
        _t0 = time.monotonic()

        res = harness.run(
            "company-partner",
            {
                "persona": persona_name,
                "lens": lens,
                "dossier_fields": dossier_fields_r2,
                "round1_verdicts": round1_verdicts,
            },
            engagement_id=eid,
            ctx={**ctx, "dossier_fields": dossier_fields_r2},
            registry=registry,
        )

        _elapsed = round(time.monotonic() - _t0, 2)

        if res.ok and res.output:
            r2_stance = res.output.get("stance", "conditional")
            r2_conviction = res.output.get("conviction", 0)
            r2_rationale = res.output.get("rationale", "")
        else:
            r2_stance = r1_stance
            r2_conviction = r1_conviction
            r2_rationale = f"abstained ({res.error or 'unknown'})"

        revised = (r2_conviction != r1_conviction or r2_stance != r1_stance)
        shift = r2_rationale[:200]

        rebuttal_entry: dict = {
            "persona": persona_name,
            "revised": revised,
            "conviction": r2_conviction,
            "shift": shift,
        }
        round2.append(rebuttal_entry)

        # Live progress: rebuttal landed (distinct phase so stage-order filters are unaffected).
        _emit(on_progress, eid, {
            "stage": "roundtable", "agent_id": persona_name,
            "phase": "rebuttal_done", "round": 2,
            "revised": revised, "conviction": r2_conviction,
            "elapsed_s": _elapsed,
        })

    # Spread computation — based on round-1 convictions and stances.
    r1_convictions = [
        v.get("conviction", 0)
        for v in round1
        if isinstance(v, dict) and isinstance(v.get("conviction"), int)
    ]
    r1_stances = [v.get("stance", "hold") for v in round1 if isinstance(v, dict)]
    stance_mix = {s: r1_stances.count(s) for s in sorted(set(r1_stances))}
    moved_in_r2 = [r["persona"].split(",")[0] for r in round2 if r.get("revised")]

    _r1_no_go = r1_stances.count("no_go")
    _r1_pass = r1_stances.count("pass")
    _r1_conditional = r1_stances.count("conditional")
    if _r1_no_go > 0 and _r1_pass == 0:
        _consensus_label = "no_go"
        _dissent_label = ""
    elif _r1_pass > len(r1_stances) // 2:
        _consensus_label = "majority pass"
        _dissent_label = f"{_r1_conditional} conditional, {_r1_no_go} no_go"
    else:
        _consensus_label = ""
        _dissent_label = f"{_r1_conditional} conditional, {_r1_no_go} no_go"

    spread: dict = {
        "consensus": _consensus_label,
        "dissent": _dissent_label,
        "convergent_gate": "VETO" if veto_flags else "",
        "conviction_range": (
            f"{min(r1_convictions)}-{max(r1_convictions)} / 5"
            if r1_convictions else "-"
        ),
        "stance_mix": stance_mix,
        "moved_in_round2": moved_in_r2,
    }

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
    consult: dict = {"round1": round1, "round2": round2, "spread": spread}
    # VETO gate adjudication: surfaced in the consult output when active so the
    # front door / LOKA adapter can render the gate prominently.
    if veto_is_active:
        consult["adjudication"] = {
            "veto_facts": veto_flags,
            "n_veto": len(veto_flags),
            "mode": "active",
        }

    return {
        "query": query,
        "plan": public_plan,
        "priors": priors,
        "discover": discover,
        "consult": consult,
        "synthesize": syn,
        "engagement_id": eid,
        "reflection": reflection,
        "_via": "harness-live",
        "plan_source": plan_source,
    }
