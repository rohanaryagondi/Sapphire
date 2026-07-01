"""EMET FILE-BRIDGE handler — live EMET without Playwright / auto-login.

The detached-`claude -p` runner (`handler._default_runner`) drives its OWN Playwright browser,
so it cannot reach the user's authenticated BenchSci session and fights the Chrome profile lock.
This handler takes a different path: a **separate Claude-in-Chrome session** (run by the user in
their already-authenticated browser) answers EMET requests through a shared file queue. Sapphire
writes a request line; that session appends a response line; the handler polls for it.

Protocol (shared dir ``RohanOnly/emet_bridge/`` — gitignored under RohanOnly/)
----------------------------------------------------------------------------
- ``requests.jsonl``  — Sapphire APPENDS one JSON per line::

      {"id": <uuid>, "query": <str>, "gene": <str|null>, "genes": [<str>, ...], "ts": <iso8601>}

  - ``query``  — a COMPREHENSIVE multi-source prompt (see ``build_emet_query`` below).
  - ``gene``   — the primary public candidate identifier (or null for multi-gene requests).
  - ``genes``  — list of all gene symbols in scope (populated for multi-gene batches; single-gene
                 requests carry a one-element list matching ``gene``).

- ``responses.jsonl`` — the EMET (Claude-in-Chrome) session APPENDS one JSON per line::

      {"id": <uuid>, "status": "ok"|"empty"|"error",
       "evidence": <markdown str>, "citations": [<str>, ...], "ts": <iso8601>}

  A request is answered once its ``id`` appears in ``responses.jsonl``.

Multi-gene batching
-------------------
When a query involves multiple gene symbols (e.g. a ranking / comparison), the orchestrator MUST
send ONE batched request covering all genes — NOT one request per gene. The bridge handler checks
the ``genes`` field on inputs (threaded from ``live_engine`` via ``bucket1_inputs["genes"]``) and
builds a single comprehensive prompt asking the EMET worker to survey all genes in one pass.

Comprehensive multi-source prompts
-----------------------------------
The ``query`` field on every request is built by ``build_emet_query`` (public identifiers only).
It instructs the EMET worker to use ANY source it judges useful — NOT just BenchSci literature:

  - BenchSci LITERATURE evidence (the primary EMET channel)
  - Expression atlases: GTEx (tissue-level mRNA), Human Protein Atlas (HPA protein)
  - Variant/constraint DBs: gnomAD (pLI/LOEUF/missense Z), ClinVar (pathogenic variants)
  - Pathway + interaction DBs: Reactome, STRING, KEGG
  - Clinical-trial registries: ClinicalTrials.gov
  - Model-organism / phenotype data: Mouse Genome Informatics (MGI / IMPC)
  - Any other public DB the worker judges biologically relevant to the question

The prompt asks for evidence FOR and AGAINST (mechanism, phenotype, clinical) and requires a
source attribution per claim. Public identifiers only (gene symbols, disease terms, SMILES) —
never Quiver internal EP/CRISPR data.

Timeout + scaling
-----------------
Default ``$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S`` = **900 s** (15 min). When multiple requests are
pending (unanswered in the queue), the effective timeout scales up to give the EMET worker time
to finish earlier requests before the new one ages out:

    effective_timeout = min(base + per_pending × (unanswered_count − 1), cap)

where:
  - ``base``        = _timeout_s()           (default 900 s, ``$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S``)
  - ``per_pending`` = _PER_PENDING_S         (default 120 s per additional unanswered request)
  - cap             = _TIMEOUT_CAP_S         (default 3600 s / 1 h)
  - ``unanswered_count`` = number of request ids in requests.jsonl with no matching response yet

If there is only one pending request (the one just written), ``unanswered_count`` = 1 and the
formula collapses to the base timeout (× 0 extra): ``min(base + 0, cap) = base``.

Honesty / data boundary
-----------------------
- Only PUBLIC identifiers cross to EMET (gene symbol, disease/target term) — the same rule the
  Playwright runner obeys. The ``query`` and ``gene``/``genes`` are built from the run's public
  inputs only.
- On ``status == "ok"`` the handler returns ONLY what the response actually holds — the evidence
  markdown as one cited **T2** fact and each supplied citation as its own cited T2 fact. It never
  invents a fact or a citation.
- On timeout / ``status == "error"`` / ``status == "empty"`` (or a missing/blank evidence body) the
  handler returns an HONEST ABSTAIN: a schema-valid findings envelope with an EMPTY ``facts`` list
  and provenance ``emet-live-bridge``. No fabricated facts, and it NEVER raises — an EMET hiccup
  must not crash the firm; the orchestrator slots a zero-fact EMET result as an honest no-result.

The provenance label on every emitted fact is ``emet-live-bridge`` (external plane) so a bridge
fact is always distinguishable from a Playwright-driven ``emet-live`` fact in the trace.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# RohanOnly/emet_bridge/ — resolve relative to the repo root (two levels up from this package).
_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = "emet-live-bridge"

# Timeout + scaling constants.  All overridable via env for tests and operator tuning.
_DEFAULT_TIMEOUT_S = 900       # 15 min base — generous for a real multi-source EMET sweep
_DEFAULT_POLL_S = 2.0
_TIMEOUT_FLOOR_S = 5
_PER_PENDING_S = 120           # add 120 s per additional unanswered request in the queue
_TIMEOUT_CAP_S = 3600          # hard cap: 1 hour (never block the firm indefinitely)


def bridge_dir() -> Path:
    """The shared bridge directory. ``$SAPPHIRE_EMET_BRIDGE_DIR`` overrides (used by tests)."""
    override = (os.environ.get("SAPPHIRE_EMET_BRIDGE_DIR") or "").strip()
    return Path(override) if override else (_ROOT / "RohanOnly" / "emet_bridge")


def _timeout_s() -> int:
    """Base poll timeout in seconds. ``$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S`` overrides; default 900, floor 5.

    A bad/blank value falls back to the default so a typo can't disable the timeout entirely.
    """
    raw = os.environ.get("SAPPHIRE_EMET_BRIDGE_TIMEOUT_S")
    try:
        return max(_TIMEOUT_FLOOR_S, int(raw))
    except (ValueError, TypeError):
        return _DEFAULT_TIMEOUT_S


def _poll_s() -> float:
    """Poll interval in seconds. ``$SAPPHIRE_EMET_BRIDGE_POLL_S`` overrides; default ~2s, floor 0.05.

    Exposed mainly so tests (which pre-write the response) can poll fast without a real wait.
    """
    raw = os.environ.get("SAPPHIRE_EMET_BRIDGE_POLL_S")
    try:
        return max(0.05, float(raw))
    except (ValueError, TypeError):
        return _DEFAULT_POLL_S


def _count_unanswered(requests_path: Path, responses_path: Path) -> int:
    """Count request ids in requests.jsonl that have no matching entry in responses.jsonl.

    Returns 1 on any read error (conservative: assume at least the current request is pending).
    Used to scale the effective timeout when multiple requests are queued.
    """
    try:
        req_ids: set[str] = set()
        if requests_path.exists():
            for line in requests_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rid = str(obj.get("id") or "")
                    if rid:
                        req_ids.add(rid)
                except (ValueError, TypeError):
                    pass

        answered: set[str] = set()
        if responses_path.exists():
            for line in responses_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rid = str(obj.get("id") or "")
                    if rid:
                        answered.add(rid)
                except (ValueError, TypeError):
                    pass

        unanswered = req_ids - answered
        return max(1, len(unanswered))
    except Exception:
        return 1


def _scaled_timeout_s(requests_path: Path, responses_path: Path) -> int:
    """Effective poll timeout, scaled by the number of unanswered requests in the queue.

    Formula:  effective = min(base + per_pending × (unanswered_count - 1), cap)

    With a single pending request this collapses to the base timeout.  Each additional
    unanswered request adds _PER_PENDING_S seconds, capped at _TIMEOUT_CAP_S.
    """
    base = _timeout_s()
    unanswered = _count_unanswered(requests_path, responses_path)
    extra = _PER_PENDING_S * max(0, unanswered - 1)
    return min(base + extra, _TIMEOUT_CAP_S)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate(inputs: dict) -> str:
    """The primary public candidate identifier for the run (candidate | target | gene). Public only."""
    d = inputs or {}
    return str(d.get("candidate") or d.get("target") or d.get("gene") or "").strip()


def _gene_list(inputs: dict) -> list[str]:
    """The full set of public gene symbols in scope for this request.

    Prefers inputs["genes"] (threaded from live_engine bucket1_inputs["genes"]), falls back
    to a one-element list with the primary candidate.  Deduplicates while preserving order.
    """
    d = inputs or {}
    raw = d.get("genes") or []
    if isinstance(raw, (list, tuple)):
        seen: set[str] = set()
        out: list[str] = []
        for g in raw:
            g = str(g or "").strip()
            if g and g not in seen:
                seen.add(g)
                out.append(g)
        if out:
            return out
    # Fallback to the primary candidate.
    cand = _candidate(d)
    return [cand] if cand else []


def build_emet_query(inputs: dict) -> str:
    """Build a COMPREHENSIVE multi-source EMET prompt from PUBLIC inputs only.

    The prompt instructs the EMET (Claude-in-Chrome) worker to consult ANY source it judges
    relevant to the biological question — not just BenchSci LITERATURE.  Sources it should
    consider (use as appropriate to the question):

      - BenchSci LITERATURE: primary EMET channel — assay/study evidence for the target
      - Expression atlases: GTEx (tissue mRNA), Human Protein Atlas (HPA protein/RNA)
      - Variant/constraint DBs: gnomAD (pLI, LOEUF, missense Z), ClinVar (pathogenic variants)
      - Pathway + interaction DBs: Reactome, STRING, KEGG
      - Clinical-trial registries: ClinicalTrials.gov (active/completed trials)
      - Model-organism/phenotype DBs: Mouse Genome Informatics (MGI / IMPC)
      - Any other public database the worker judges biologically relevant

    The worker is asked to supply:
      - Evidence FOR (supporting biology: mechanism, expression, variant burden, trials)
      - Evidence AGAINST (negative data, safety signals, known liabilities)
      - Mechanistic context (pathway membership, interactors, phenotype)
      - A source attribution per claim (PMID / DOI / URL / DB accession)

    DATA BOUNDARY (enforced here): only public identifiers are included — gene symbols,
    disease/target terms, SMILES.  Quiver internal EP/CRISPR data never enters the query.
    """
    d = inputs or {}
    genes = _gene_list(d)
    question = str(d.get("question") or d.get("query") or d.get("workflow") or "").strip()
    disease = str(d.get("disease") or "").strip()

    if not genes and not question:
        return ""

    # Build the gene/target header.
    if len(genes) > 1:
        gene_header = f"Genes/targets: {', '.join(genes)}"
        gene_note = (
            f"This is a MULTI-GENE request covering {len(genes)} targets "
            f"({', '.join(genes)}). Survey all of them in a single pass — do NOT limit "
            "to one gene only."
        )
    else:
        gene_header = f"Gene/target: {genes[0]}" if genes else ""
        gene_note = ""

    disease_line = f"Disease/indication: {disease}" if disease else ""
    question_line = f"Biological question: {question}" if question else ""

    context_lines = [x for x in [gene_header, disease_line, question_line] if x]
    context_block = "\n".join(context_lines)

    sources_block = (
        "Use ANY of the following sources that are relevant to the question "
        "(you are NOT limited to BenchSci literature alone):\n"
        "  - BenchSci LITERATURE: assay/study evidence from the scientific literature\n"
        "  - Expression atlases: GTEx (tissue mRNA), Human Protein Atlas (HPA protein)\n"
        "  - Variant/constraint DBs: gnomAD (pLI / LOEUF / missense Z), ClinVar (pathogenic variants)\n"
        "  - Pathway + interaction DBs: Reactome, STRING, KEGG\n"
        "  - Clinical-trial registries: ClinicalTrials.gov (active/completed trials)\n"
        "  - Model-organism / phenotype DBs: Mouse Genome Informatics (MGI / IMPC knockout phenotypes)\n"
        "  - Any other public database you judge biologically relevant"
    )

    deliverables_block = (
        "For each source consulted, provide:\n"
        "  1. Evidence FOR (supporting biology: mechanism, expression pattern, variant burden, "
        "preclinical/clinical evidence)\n"
        "  2. Evidence AGAINST (negative data, safety signals, known liabilities)\n"
        "  3. Mechanistic context (pathway membership, key interactors, disease-relevant phenotype)\n"
        "  4. A source attribution per claim: PMID / DOI / URL / DB accession — "
        "do NOT omit citations."
    )

    boundary_note = (
        "DATA BOUNDARY: use public identifiers only (gene symbols, disease terms, SMILES). "
        "Do not include any proprietary or internal data."
    )

    parts = [context_block, ""]
    if gene_note:
        parts.append(gene_note)
        parts.append("")
    parts.extend([sources_block, "", deliverables_block, "", boundary_note])
    return "\n".join(parts).strip()


def _abstain(candidate: str) -> dict:
    """An HONEST, schema-valid EMET findings envelope with NO facts (timeout/error/empty).

    Zero facts = no evidence found via the bridge; the orchestrator treats it as an honest
    no-result, never a fabricated fact. Never raises."""
    return {"candidate": candidate, "facts": [], "provenance": PROVENANCE}


def _read_response(responses_path: Path, req_id: str) -> dict | None:
    """Return the FIRST response line whose ``id`` matches ``req_id``, or None if not present.

    Malformed lines are skipped silently — a bad line from the peer session must never crash the
    poll (never fabricate, never raise). Missing file → None (not yet answered)."""
    try:
        text = responses_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue  # skip a malformed response line
        if isinstance(obj, dict) and str(obj.get("id") or "") == req_id:
            return obj
    return None


def _normalize_response(resp: dict, candidate: str) -> dict:
    """Map a bridge response → a findings envelope. Only what the response HOLDS; never fabricate.

    ``status == "ok"`` with a non-empty evidence body → the evidence markdown as one cited T2 fact
    plus each supplied citation as its own cited T2 fact. Anything else (error / empty / blank
    evidence) → honest abstain (empty facts)."""
    status = str(resp.get("status") or "").strip().lower()
    evidence = str(resp.get("evidence") or "").strip()
    if status != "ok" or not evidence:
        return _abstain(candidate)

    facts = [{"value": evidence, "source": "EMET (Claude-in-Chrome bridge)",
              "tier": "T2", "provenance": PROVENANCE}]
    citations = resp.get("citations") or []
    if isinstance(citations, (list, tuple)):
        for c in citations:
            c = str(c or "").strip()
            if c:
                facts.append({"value": f"Cited source: {c}", "source": c,
                              "tier": "T2", "provenance": PROVENANCE})
    return {"candidate": candidate, "facts": facts, "provenance": PROVENANCE}


def _append_request(requests_path: Path, req: dict) -> None:
    """Append one request line (JSON + newline). Creates the file if absent."""
    with requests_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(req, ensure_ascii=False) + "\n")


def make_emet_bridge_handler(*, sleep=time.sleep, clock=time.monotonic):
    """Return a 2-arg ``(contract, inputs)`` EMET handler backed by the file bridge.

    Signature matches the seam the harness's ``emet-playwright`` dispatch calls (same as
    ``emet.make_emet_handler``). ``sleep`` / ``clock`` are injectable so tests never wait on a
    real clock. The handler NEVER raises: any failure degrades to an honest zero-fact abstain.

    Timeout scaling: ``effective_timeout = min(base + _PER_PENDING_S × (unanswered−1), _TIMEOUT_CAP_S)``
    so a queue with several pending requests gives the EMET worker proportionally more time.
    """
    def _handler(contract, inputs):
        candidate = _candidate(inputs)
        try:
            d = bridge_dir()
            d.mkdir(parents=True, exist_ok=True)
            requests_path = d / "requests.jsonl"
            responses_path = d / "responses.jsonl"

            req_id = str(uuid.uuid4())
            genes = _gene_list(inputs)
            req = {
                "id": req_id,
                "query": build_emet_query(inputs),
                "gene": (candidate or None),
                "genes": genes,
                "ts": _now_iso(),
            }
            _append_request(requests_path, req)

            # Scale timeout by the number of unanswered requests (this one just landed in the queue).
            timeout = _scaled_timeout_s(requests_path, responses_path)
            poll = _poll_s()
            deadline = clock() + timeout
            # Poll for the matching response id until it lands or we time out.
            while True:
                resp = _read_response(responses_path, req_id)
                if resp is not None:
                    return _normalize_response(resp, candidate)
                if clock() >= deadline:
                    return _abstain(candidate)     # timeout → honest abstain
                sleep(poll)
        except Exception:
            # Defensive: an unexpected I/O / filesystem error must NEVER crash the firm. Abstain
            # honestly (no fabricated facts) instead of propagating.
            return _abstain(candidate)

    return _handler
