"""
geneset_enrichment_seam.py — stdlib-only Sapphire seam for g:Profiler enrichment.

Bucket-1 quantitative fact source (sibling of the gnomad/gtex/interpro seams). EMET
paraphrases what a gene set is "about"; this seam returns the actual functional
enrichment: the top over-represented GO / pathway / phenotype terms for the set,
with their term ids and p-values, computed by g:Profiler's g:GOSt. Cited,
provenance-stamped T2 facts (a computed enrichment statistic) that complement
EMET's narrative.

Boundary & honesty (dev/CONVENTIONS.md §2/§3):
  * Runtime stays stdlib-only — only ``json`` + ``urllib`` here.
  * Public identifiers only leave Quiver: we POST a list of public gene symbols to
    g:Profiler's public API. The harness ``data_boundary`` guardrail blocks internal
    ids before dispatch.
  * Degrade honestly, never fabricate: honest-empty (facts=[]) when there is no gene
    set or g:Profiler returns no significant term; an honest error envelope
    (facts=[] + ``error``) when the API call fails (incl. transport/TLS errors).
    Never raises into the engine; never invents a term.

Provenance label: ``gprofiler``.

API contract reference: ToolUniverse's g:Profiler tool (Apache-2.0) — reimplemented
as our own stdlib seam, not vendored. One POST to
https://biit.cs.ut.ee/gprofiler/api/gost/profile/ with {"organism":"hsapiens",
"query":[<symbols>]}; the response's ``result[]`` lists enriched terms (native id,
name, source, p_value, significant). Default secure TLS verification is used; the
host serves a valid HARICA chain (verifies on standard CA stores).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

_ENDPOINT = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"
_ORGANISM = "hsapiens"
_TIMEOUT = 30
_PROVENANCE = "gprofiler"
_SOURCE = "g:Profiler g:GOSt (hsapiens)"
_MAX_TERMS = 5   # cap the named top-terms in the fact text


def _fetch(genes: list) -> dict:
    """Single HTTP indirection so tests monkeypatch the network at the seam boundary.

    POSTs the gene set to g:GOSt and returns the parsed JSON dict. Raises on
    transport/decode error (incl. urllib.error.*) — the caller catches and degrades
    to an honest error envelope.
    """
    payload = json.dumps({"organism": _ORGANISM, "query": genes}).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "sapphire-gprofiler-seam/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_genes(inputs: dict) -> list:
    """The gene SET for enrichment: prefer the engine-threaded ``genes`` list, else
    fall back to the single ``candidate``/``target``. Returns stripped, de-duped,
    non-empty symbols (order preserved)."""
    raw = inputs.get("genes")
    if not raw:
        one = (inputs.get("candidate") or inputs.get("target") or "").strip()
        raw = [one] if one else []
    seen, out = set(), []
    for g in raw:
        s = str(g).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _build_fact(genes: list, raw: dict) -> dict | None:
    """Summarise g:GOSt output into one T2 fact: count of significant terms + the
    top few by p-value (name, term id, p). Returns None if nothing significant
    (→ honest-empty upstream)."""
    results = (raw or {}).get("result") or []
    sig = [t for t in results
           if t.get("significant") and isinstance(t.get("p_value"), (int, float))
           and not isinstance(t.get("p_value"), bool)]
    if not sig:
        return None
    top = sorted(sig, key=lambda t: t["p_value"])[:_MAX_TERMS]
    terms = []
    for t in top:
        name = t.get("name") or t.get("native") or "?"
        native = t.get("native") or "?"
        terms.append(f"{name} ({native}, p={t['p_value']:.1e})")
    gene_str = ", ".join(genes[:8]) + (f" +{len(genes) - 8} more" if len(genes) > 8 else "")
    value = (
        f"g:Profiler enrichment for {gene_str} (hsapiens): {len(sig)} significant terms; "
        f"top — " + "; ".join(terms)
    )
    return {"value": value, "source": _SOURCE, "tier": "T2"}


def findings(inputs: dict) -> dict:
    """Harness-compatible findings dict for the geneset-enrichment agent.

    Runs g:Profiler g:GOSt on the gene set (engine-threaded ``genes`` list, else the
    single ``candidate``) and returns one T2 enrichment fact. Honest-empty when there
    is no gene set or no significant term; honest error envelope if the API call
    fails. Never raises.
    """
    candidate = inputs.get("candidate", "")
    genes = _resolve_genes(inputs)
    if not genes:
        return {"candidate": candidate, "facts": [], "provenance": _PROVENANCE}

    try:
        raw = _fetch(genes)
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never raise into the engine
        return {"candidate": candidate, "facts": [], "error": str(exc), "provenance": _PROVENANCE}

    fact = _build_fact(genes, raw)
    facts = [fact] if fact is not None else []
    return {"candidate": candidate, "facts": facts, "provenance": _PROVENANCE}
