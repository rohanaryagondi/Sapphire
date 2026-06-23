"""
interpro_domains_seam.py — stdlib-only Sapphire seam for InterPro protein domains.

Bucket-1 quantitative/structured fact source (sibling of gnomad/gtex seams — same
pattern). EMET paraphrases what's written about a protein's structure; this seam
returns the curated InterPro annotation: the protein's domain and family entries
(with their IPR accessions). Cited, provenance-stamped T1 facts that complement
EMET's narrative.

Boundary & honesty (dev/CONVENTIONS.md §2/§3):
  * Runtime stays stdlib-only — only ``json`` + ``urllib`` here.
  * Public identifiers only leave Quiver: we send a public gene symbol to UniProt
    (→ its public reviewed-human accession), then that accession to InterPro. The
    harness ``data_boundary`` guardrail blocks internal ids before dispatch.
  * Degrade honestly, never fabricate: honest-empty (facts=[]) when there is no
    target gene, when UniProt has no reviewed human protein for it, or when
    InterPro has no entries (200-empty or 404); an honest error envelope
    (facts=[] + ``error``) when an API call otherwise fails. Never raises into the
    engine; never invents a domain.

Provenance label: ``interpro``.

API contract reference: ToolUniverse's InterPro tool (Apache-2.0) — reimplemented
as our own stdlib seam, not vendored. Two GET calls:
  1. UniProt  https://rest.uniprot.org/uniprotkb/search   (symbol → reviewed human accession)
  2. InterPro https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot/<acc>/
The InterPro API returns the current release; the source label is therefore
version-agnostic (the release is not pinnable on this endpoint).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
_INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot/"
_TIMEOUT = 30
_PROVENANCE = "interpro"
_SOURCE = "InterPro (EBI)"
_MAX_PER_TYPE = 5   # cap names shown per entry-type; overflow summarised as "+N more"


def _fetch(url: str) -> dict:
    """Single HTTP indirection so tests monkeypatch the network at the seam boundary.

    GETs the full ``url`` and returns the parsed JSON dict. Raises on
    transport/decode error (incl. urllib.error.HTTPError) — the caller handles
    404 as honest-empty and other failures as an honest error envelope.
    """
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "sapphire-interpro-seam/1.0"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_accession(symbol: str) -> str | None:
    """Resolve a public gene symbol to its reviewed (Swiss-Prot) human UniProt
    accession. Returns None if there is no reviewed human protein (→ honest-empty)."""
    query = urllib.parse.urlencode({
        "query": f"gene_exact:{symbol} AND organism_id:9606 AND reviewed:true",
        "format": "json",
        "fields": "accession",
        "size": "1",
    })
    raw = _fetch(_UNIPROT_SEARCH + "?" + query)
    results = (raw or {}).get("results") or []
    return results[0].get("primaryAccession") if results and results[0].get("primaryAccession") else None


def _entries_of_type(results: list, type_name: str) -> list:
    """Return [(name, IPR-accession), ...] for InterPro entries of the given type."""
    out = []
    for r in results:
        m = r.get("metadata") or {}
        if m.get("type") == type_name and m.get("name") and m.get("accession"):
            out.append((m["name"], m["accession"]))
    return out


def _fmt(entries: list) -> str:
    shown = entries[:_MAX_PER_TYPE]
    s = ", ".join(f"{name} ({acc})" for name, acc in shown)
    if len(entries) > _MAX_PER_TYPE:
        s += f", +{len(entries) - _MAX_PER_TYPE} more"
    return s


def _build_fact(symbol: str, acc: str, raw: dict) -> dict | None:
    """Summarise InterPro entries into one T1 fact: domain + family annotations with
    IPR accessions, plus the total entry count. Returns None if no entries (→
    honest-empty upstream). The count is the API's true total; the shown names are
    a capped sample of the first page (no silent drift — count reflects the whole)."""
    results = (raw or {}).get("results") or []
    if not results:
        return None
    count = raw.get("count")
    if not isinstance(count, int):
        count = len(results)

    domains = _entries_of_type(results, "domain")
    families = _entries_of_type(results, "family")
    parts = []
    if domains:
        parts.append("domains: " + _fmt(domains))
    if families:
        parts.append("families: " + _fmt(families))
    if not parts:
        # Entries exist but none are domain/family (e.g. only homologous superfamilies).
        types = sorted({(r.get("metadata") or {}).get("type") for r in results
                        if (r.get("metadata") or {}).get("type")})
        parts.append("entry types: " + ", ".join(types))

    value = f"{symbol} (UniProt {acc}) InterPro: {count} entries — " + "; ".join(parts)
    return {"value": value, "source": _SOURCE, "tier": "T1"}


def findings(inputs: dict) -> dict:
    """Harness-compatible findings dict for the interpro-domains agent.

    Reads the target gene symbol from ``candidate`` (or ``target``), resolves it to
    a reviewed human UniProt accession, and returns one T1 domain/family-annotation
    fact. Honest-empty when no target / no reviewed protein / no InterPro entries;
    honest error envelope if an API call otherwise fails. Never raises.
    """
    target = (inputs.get("candidate") or inputs.get("target") or "").strip()
    if not target:
        return {"candidate": target, "facts": [], "provenance": _PROVENANCE}

    try:
        acc = _resolve_accession(target)
        if not acc:
            # No reviewed human protein for this symbol — a known-unknown.
            return {"candidate": target, "facts": [], "provenance": _PROVENANCE}
        raw = _fetch(_INTERPRO_BASE + urllib.parse.quote(acc) + "/")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # InterPro has no entries for this protein — honest-empty, not a failure.
            return {"candidate": target, "facts": [], "provenance": _PROVENANCE}
        return {"candidate": target, "facts": [], "error": f"HTTP {exc.code}", "provenance": _PROVENANCE}
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never raise into the engine
        return {"candidate": target, "facts": [], "error": str(exc), "provenance": _PROVENANCE}

    fact = _build_fact(target, acc, raw)
    facts = [fact] if fact is not None else []
    return {"candidate": target, "facts": facts, "provenance": _PROVENANCE}
