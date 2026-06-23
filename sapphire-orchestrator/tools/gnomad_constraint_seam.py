"""
gnomad_constraint_seam.py — stdlib-only Sapphire seam for gnomAD gene constraint.

Bucket-1 quantitative fact source. EMET tells us what the literature *says* about a
gene; this seam returns the actual measured population-genetics numbers: the gnomAD
loss-of-function constraint metrics (pLI, LOEUF, missense Z). These are cited,
provenance-stamped T1 facts that complement EMET's narrative and let the Research
Manager flag number-vs-narrative DIVERGENCE.

Boundary & honesty (dev/CONVENTIONS.md §2/§3):
  * Runtime is stdlib-only — this module imports only ``json`` + ``urllib``. No
    third-party deps enter the engine path.
  * Public identifiers only leave Quiver: we send a public gene symbol to gnomAD's
    public GraphQL API. (The harness ``data_boundary`` guardrail blocks internal
    ids before dispatch; this seam additionally never echoes inputs outward beyond
    the symbol.)
  * Degrade honestly, never fabricate: honest-empty (facts=[]) when there is no
    target gene, when the gene is not found, or when gnomAD has no constraint
    record; an honest error envelope (facts=[] + ``error``) when the API is
    unreachable. It NEVER raises into the engine and never invents a number.

Provenance label: ``gnomad``.

API contract reference: ToolUniverse's gnomAD tool (Apache-2.0) — reimplemented as
our own stdlib seam, not vendored. Endpoint: POST GraphQL to
https://gnomad.broadinstitute.org/api. LOEUF is the ``oe_lof_upper`` field (the
upper bound of the observed/expected LoF 90% CI).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

_ENDPOINT = "https://gnomad.broadinstitute.org/api"
_TIMEOUT = 30
_PROVENANCE = "gnomad"
_REFERENCE_GENOME = "GRCh38"
_SOURCE = "gnomAD v4 constraint (GraphQL)"

# Constraint thresholds (gnomAD/MacArthur-lab conventions, also stated in the brief):
#   pLI >= 0.90  OR  LOEUF < 0.35  -> loss-of-function intolerant.
_PLI_INTOLERANT = 0.90
_LOEUF_INTOLERANT = 0.35

# GraphQL query — gene symbol + reference genome are passed as variables (no string
# interpolation of the symbol into the query, so the symbol cannot alter the query).
_QUERY = (
    "query GeneConstraint($symbol: String!, $genome: ReferenceGenomeId!) {"
    "  gene(gene_symbol: $symbol, reference_genome: $genome) {"
    "    symbol gnomad_constraint { pli oe_lof oe_lof_upper mis_z }"
    "  }"
    "}"
)


def _fetch(symbol: str) -> dict:
    """Single HTTP indirection so tests monkeypatch the network at the seam boundary.

    POSTs the GraphQL query for ``symbol`` and returns the parsed JSON dict (the
    full ``{"data": ..., "errors": ...}`` envelope). Raises on transport/decode
    error — the caller (``findings``) catches and degrades to an error envelope.
    """
    payload = json.dumps({
        "query": _QUERY,
        "variables": {"symbol": symbol, "genome": _REFERENCE_GENOME},
    }).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "sapphire-gnomad-seam/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _num(x):
    """Return x if it is a real number (not bool/None/str), else None.

    Guards the formatting below against a null or unexpected type slipping in from
    the API — we only ever format genuine numbers, never fabricate one."""
    if isinstance(x, bool):
        return None
    return x if isinstance(x, (int, float)) else None


def _interpret(pli, loeuf) -> str:
    """Return a short interpretation, or '' to state the values plainly.

    Only the well-established LoF-intolerant call is made (pLI >= 0.90 or
    LOEUF < 0.35). Anything else is reported without an interpretive claim — we do
    not over-claim 'tolerant' from a single metric."""
    if (pli is not None and pli >= _PLI_INTOLERANT) or (
        loeuf is not None and loeuf < _LOEUF_INTOLERANT
    ):
        return "loss-of-function intolerant"
    return ""


def _build_fact(symbol: str, constraint: dict) -> dict | None:
    """Build a single T1 fact dict from a gnomad_constraint record, or None if no
    metric is populated (→ honest-empty upstream)."""
    pli = _num(constraint.get("pli"))
    loeuf = _num(constraint.get("oe_lof_upper"))
    mis_z = _num(constraint.get("mis_z"))

    parts = []
    if pli is not None:
        parts.append(f"pLI {pli:.2f}")
    if loeuf is not None:
        parts.append(f"LOEUF {loeuf:.2f}")
    if mis_z is not None:
        parts.append(f"missense Z {mis_z:.2f}")
    if not parts:
        return None

    value = f"{symbol} gnomAD constraint: " + ", ".join(parts)
    interp = _interpret(pli, loeuf)
    if interp:
        value += f" ({interp})"
    return {"value": value, "source": _SOURCE, "tier": "T1"}


def findings(inputs: dict) -> dict:
    """Harness-compatible findings dict for the gnomad-constraint agent.

    Reads the target gene symbol from ``candidate`` (or ``target``). Returns one
    T1 constraint fact when gnomAD has a record; honest-empty otherwise; an honest
    error envelope if the API call fails. Never raises.
    """
    target = (inputs.get("candidate") or inputs.get("target") or "").strip()
    if not target:
        return {"candidate": target, "facts": [], "provenance": _PROVENANCE}

    try:
        raw = _fetch(target)
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never raise into the engine
        return {"candidate": target, "facts": [], "error": str(exc), "provenance": _PROVENANCE}

    if not isinstance(raw, dict) or "data" not in raw or raw["data"] is None:
        # No data payload at all — surface the GraphQL/transport problem honestly
        # (distinct from a gene that simply isn't in gnomAD).
        errs = (raw or {}).get("errors") or [] if isinstance(raw, dict) else []
        msg = "; ".join(e.get("message", "") for e in errs) or "no data in gnomAD response"
        return {"candidate": target, "facts": [], "error": msg, "provenance": _PROVENANCE}

    gene = raw["data"].get("gene")
    if not isinstance(gene, dict):
        # data.gene == null → gene not found. A known-unknown, not a failure.
        return {"candidate": target, "facts": [], "provenance": _PROVENANCE}

    constraint = gene.get("gnomad_constraint")
    if not isinstance(constraint, dict):
        # Gene exists but has no constraint record.
        return {"candidate": target, "facts": [], "provenance": _PROVENANCE}

    fact = _build_fact(target, constraint)
    facts = [fact] if fact is not None else []
    return {"candidate": target, "facts": facts, "provenance": _PROVENANCE}
