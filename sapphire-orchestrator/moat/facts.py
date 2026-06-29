"""
moat/facts.py — Moat facts helper (Task 4).

Returns dossier-shaped fact rows from the Quiver internal moat SQLite database:
  - top similar genes   (EP-signature mimics)
  - top rescue genes    (genes whose EP-signature OPPOSES the perturbation KO)
  - top opposite compounds (rescue candidates)

Degrades honestly to [] if the client is unavailable (DB not built).
All stdlib — no third-party deps.
"""
from __future__ import annotations

from moat.client import MoatClient

_SOURCE = "Quiver moat (CNS_DFP, real)"
_TIER   = "T2"
_PROV   = "moat-real"


def moat_facts(
    perturbation: str,
    client: MoatClient | None = None,
    k: int = 5,
) -> list[dict]:
    """
    Return dossier-shaped fact rows for `perturbation` from the internal moat.

    Args:
        perturbation: gene symbol or compound name (case-insensitive).
        client: a MoatClient instance.  If None, a default MoatClient() is used.
        k: max rows per category (similar genes, rescue genes, rescue compounds).

    Returns:
        A list of dicts with keys {field, value, source, tier, provenance,
        supporting_genes}, in order: similar-gene → rescue-gene → rescue-compound.
        Returns [] if the client is unavailable — never raises.
    """
    if client is None:
        client = MoatClient()

    if not client.available():
        return []

    facts: list[dict] = []

    # ---- similar genes (EP-signature mimics) --------------------------------
    gene_rows = client.neighbors(perturbation, effect="similar", ref_type="gene", k=k)
    for row in gene_rows:
        cos = round(float(row["cosine"]), 3)
        ref = row["ref"]
        value = (
            f"EP-signature mimic: {ref} (gene) ~ {perturbation.upper()} KO (cos {cos})"
        )
        facts.append({
            "field":            "moat similar (gene)",
            "value":            value,
            "source":           _SOURCE,
            "tier":             _TIER,
            "provenance":       _PROV,
            "supporting_genes": 1,  # single-query EP match; multi-query COUNT(DISTINCT) aggregation deferred
        })

    # ---- rescue genes (opposite EP-signature genes) -------------------------
    # Genes whose EP-signature OPPOSES the perturbation KO — i.e. modulating them
    # reverses the KO phenotype. THESE are the answer to "rank genes that rescue the
    # <gene>-KO phenotype": ranked by EP-signature reversal (union_rank, ascending).
    rg_rows = client.neighbors(perturbation, effect="opposite", ref_type="gene", k=k)
    for row in rg_rows:
        ur  = row["union_rank"]
        cos = round(float(row["cosine"]), 3)
        ref = row["ref"]
        value = (
            f"Rescue gene: {ref} (gene) opposes {perturbation.upper()} KO "
            f"EP-signature (union_rank {ur}, cos {cos})"
        )
        facts.append({
            "field":            "moat rescue (gene)",
            "value":            value,
            "source":           _SOURCE,
            "tier":             _TIER,
            "provenance":       _PROV,
            "supporting_genes": 1,  # single-query EP match; multi-query COUNT(DISTINCT) aggregation deferred
        })

    # ---- rescue compounds (opposite EP-signature) ---------------------------
    cpd_rows = client.neighbors(perturbation, effect="opposite", ref_type="compound", k=k)
    for row in cpd_rows:
        cos = round(float(row["cosine"]), 3)
        ref = row["ref"]
        value = (
            f"Rescue candidate: {ref} (compound) opposes {perturbation.upper()} KO "
            f"EP-signature (cos {cos})"
        )
        facts.append({
            "field":            "moat rescue (compound)",
            "value":            value,
            "source":           _SOURCE,
            "tier":             _TIER,
            "provenance":       _PROV,
            "supporting_genes": 1,  # single-query EP match; multi-query COUNT(DISTINCT) aggregation deferred
        })

    return facts


def rescue_genes(
    perturbation: str,
    client: MoatClient | None = None,
    k: int = 10,
) -> list[dict]:
    """Ranked GENES that rescue the `perturbation` KO phenotype — structured rows.

    A "rescue gene" is one whose EP-signature is OPPOSITE to the perturbation KO
    (ranked by union_rank): modulating it reverses the KO phenotype. This is the
    structured feed the ranked-synthesis consumes (the dossier-text view is
    `moat_facts`' "moat rescue (gene)" rows). The connectivity-map logic —
    opposite signature = rescue — is the same one `moat_facts` uses for rescue
    compounds, applied to genes.

    Args:
        perturbation: gene symbol (case-insensitive), e.g. "TSC2".
        client: a MoatClient; if None a default MoatClient() is used.
        k: max rescue genes to return (ranked best-first by union_rank).

    Returns:
        A list of dicts, union_rank-ordered (best rescuer first), each:
            {rank, gene, cosine, euclidean, perturbation, source, tier, provenance}.
        rank = union_rank from the dual-rank schema.
        Returns [] if the client is unavailable or no opposite genes exist — never raises.
    """
    if client is None:
        client = MoatClient()
    if not client.available():
        return []

    rows = client.neighbors(perturbation, effect="opposite", ref_type="gene", k=k)
    out: list[dict] = []
    for row in rows:
        out.append({
            "rank":         row["union_rank"],
            "gene":         row["ref"],
            "cosine":       round(float(row["cosine"]), 3),
            "euclidean":    row["euclidean"],
            "perturbation": perturbation.upper(),
            "source":       _SOURCE,
            "tier":         _TIER,
            "provenance":   _PROV,
        })
    return out
