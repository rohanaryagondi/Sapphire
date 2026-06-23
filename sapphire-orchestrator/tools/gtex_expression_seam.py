"""
gtex_expression_seam.py — stdlib-only Sapphire seam for GTEx tissue expression.

Bucket-1 quantitative fact source (sibling of gnomad_constraint_seam.py — same
pattern). EMET paraphrases what the literature says about where a gene is
expressed; this seam returns the actual measured numbers: GTEx median expression
(TPM) across tissues, summarised as the top CNS (brain) region and a CNS
selectivity ranking. Cited, provenance-stamped T1 facts that complement EMET's
narrative and let the Research Manager flag number-vs-narrative DIVERGENCE.

Boundary & honesty (dev/CONVENTIONS.md §2/§3):
  * Runtime stays stdlib-only — only ``json`` + ``urllib`` here.
  * Public identifiers only leave Quiver: we send a public gene symbol (→ its
    public Ensembl gencodeId) to GTEx's public REST API. The harness
    ``data_boundary`` guardrail blocks internal ids before dispatch.
  * Degrade honestly, never fabricate: honest-empty (facts=[]) when there is no
    target gene, when GTEx doesn't know the gene, or when it has no expression
    record; an honest error envelope (facts=[] + ``error``) when the API is
    unreachable. It NEVER raises into the engine and never invents a number.

Provenance label: ``gtex``.

API contract reference: ToolUniverse's GTEx tool (Apache-2.0) — reimplemented as
our own stdlib seam, not vendored. Two GET calls to https://gtexportal.org/api/v2 :
  1. /reference/gene?geneId=<symbol>            → resolve symbol → gencodeId
  2. /expression/medianGeneExpression?gencodeId=<id>&datasetId=gtex_v8
The dataset release (gtex_v8) is PINNED in the request, so the source label may
name it deliberately (per the brief's "version the source label" refinement).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_BASE = "https://gtexportal.org/api/v2"
_DATASET = "gtex_v8"            # pinned in the request → named in the source label
_TIMEOUT = 30
_PROVENANCE = "gtex"
_SOURCE = f"GTEx Portal v2 ({_DATASET} medianGeneExpression)"  # label derives from the pinned dataset


def _fetch(path: str, params: dict) -> dict:
    """Single HTTP indirection so tests monkeypatch the network at the seam boundary.

    GETs ``_BASE + path`` with ``params`` and returns the parsed JSON dict. Raises
    on transport/decode error — the caller (``findings``) catches and degrades to
    an honest error envelope.
    """
    url = _BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "sapphire-gtex-seam/1.0"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _num(x):
    """Return x if it is a real number (not bool/None/str), else None — guards the
    formatting below from a null/unexpected median."""
    if isinstance(x, bool):
        return None
    return x if isinstance(x, (int, float)) else None


def _resolve_gencode(symbol: str) -> str | None:
    """Resolve a public gene symbol to its GTEx gencodeId. Prefers an exact
    symbol match; falls back to the first result. Returns None if GTEx doesn't
    know the gene (→ honest-empty upstream)."""
    raw = _fetch("/reference/gene", {"geneId": symbol})
    data = (raw or {}).get("data") or []
    up = symbol.upper()
    for row in data:
        sym = (row.get("geneSymbolUpper") or (row.get("geneSymbol") or "").upper())
        if sym == up and row.get("gencodeId"):
            return row["gencodeId"]
    # Fallback: no exact symbol match (e.g. an alias query) — take the first hit.
    # The fact's value still names the *queried* symbol, so an alias could resolve
    # to a neighbouring gene; acceptable for V1 (we report what the API returns).
    return data[0].get("gencodeId") if data and data[0].get("gencodeId") else None


def _build_fact(symbol: str, rows: list) -> dict | None:
    """Summarise per-tissue medians into one T1 fact: the top CNS (brain) region
    and its median TPM, plus a CNS selectivity ranking derived from ALL tissues.
    Returns None if no usable median is present (→ honest-empty upstream).

    We summarise rather than dump all ~54 tissues, but the summary is derived from
    every fetched median (the rank is over the full set) — no silent field drift.
    """
    vals = [
        (r.get("tissueSiteDetailId") or "", _num(r.get("median")))
        for r in rows
    ]
    vals = [(t, v) for (t, v) in vals if t and v is not None]
    if not vals:
        return None

    n = len(vals)
    ranked = sorted(vals, key=lambda x: x[1], reverse=True)
    ranked_tissues = [t for (t, _) in ranked]

    brain = [(t, v) for (t, v) in vals if t.startswith("Brain")]
    if brain:
        brain_tissue, brain_val = max(brain, key=lambda x: x[1])
        rank = ranked_tissues.index(brain_tissue) + 1
        pretty = brain_tissue.replace("_", " ")
        if rank == 1:
            sel = f"highest-expressing of {n} tissues (CNS-enriched)"
        elif rank <= 5:
            sel = f"top brain region ranks #{rank} of {n} (high CNS expression)"
        else:
            sel = f"top brain region ranks #{rank} of {n} (broadly expressed)"
        value = (
            f"{symbol} GTEx tissue expression ({_DATASET}, median TPM): "
            f"top brain region {pretty} {brain_val:.1f}; {sel}"
        )
    else:
        top_tissue, top_val = ranked[0]
        value = (
            f"{symbol} GTEx tissue expression ({_DATASET}, median TPM): "
            f"highest tissue {top_tissue.replace('_', ' ')} {top_val:.1f} of {n}; no CNS tissue in dataset"
        )
    return {"value": value, "source": _SOURCE, "tier": "T1"}


def findings(inputs: dict) -> dict:
    """Harness-compatible findings dict for the gtex-expression agent.

    Reads the target gene symbol from ``candidate`` (or ``target``), resolves it
    to a GTEx gencodeId, and returns one T1 tissue-expression fact. Honest-empty
    when there's no target / GTEx doesn't know the gene / no expression record;
    honest error envelope if the API call fails. Never raises.
    """
    target = (inputs.get("candidate") or inputs.get("target") or "").strip()
    if not target:
        return {"candidate": target, "facts": [], "provenance": _PROVENANCE}

    try:
        gencode = _resolve_gencode(target)
        if not gencode:
            # GTEx doesn't know this gene — a known-unknown, not a failure.
            return {"candidate": target, "facts": [], "provenance": _PROVENANCE}
        raw = _fetch(
            "/expression/medianGeneExpression",
            {"gencodeId": gencode, "datasetId": _DATASET},
        )
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never raise into the engine
        return {"candidate": target, "facts": [], "error": str(exc), "provenance": _PROVENANCE}

    rows = (raw or {}).get("data") or []
    fact = _build_fact(target, rows)
    facts = [fact] if fact is not None else []
    return {"candidate": target, "facts": facts, "provenance": _PROVENANCE}
