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
    queried_genes: list[str] | None = None,
) -> list[dict]:
    """
    Return dossier-shaped fact rows for `perturbation` from the internal moat.

    Args:
        perturbation: gene symbol or compound name (case-insensitive).
        client: a MoatClient instance.  If None, a default MoatClient() is used.
        k: max rows per category (similar genes, rescue genes, rescue compounds).
        queried_genes: optional list of specific gene symbols from the user query
            (e.g. ["BCL2", "FZD7", "CDK9"]).  When provided, a per-gene moat fact
            is emitted for EACH queried gene — its union_rank + cosine in the
            rescue (opposite) neighbor set, or an explicit "absent" note if the
            gene is not in Quiver's neighbor set for this perturbation.
            These per-gene facts are PREPENDED before the global top-N facts (so
            the dossier leads with the user's specific candidates).
            Data-boundary: these are internal-plane moat-real facts — same
            provenance as the global top-N rows; never forwarded to external agents.

    Returns:
        A list of dicts with keys {field, value, source, tier, provenance,
        supporting_genes}, in order: per-queried-gene rescue facts (if any) →
        similar-gene → rescue-gene → rescue-compound.
        Returns [] if the client is unavailable — never raises.
    """
    if client is None:
        client = MoatClient()

    if not client.available():
        return []

    facts: list[dict] = []

    # ---- per-queried-gene rescue lookup (prepended) -------------------------
    # When the user query names specific candidate genes, surface their Quiver
    # moat rescue rank explicitly — even if they fall outside the global top-N.
    # Data-boundary: internal-plane (moat-real), same as the global top-N rows;
    # never forwarded to EMET/web/Q-Models.
    if queried_genes:
        # Filter out the perturbation itself (no self-lookup) and blanks.
        ref_genes = [
            g for g in queried_genes
            if g and g.upper() != perturbation.upper()
        ]
        if ref_genes:
            # Count total refs in the neighbor set so absent genes can cite it.
            _total_refs: int | None = None
            try:
                con = client._connect()
                if con is not None:
                    try:
                        cur = con.execute(
                            "SELECT COUNT(*) FROM neighbors WHERE query=? AND effect=?",
                            (perturbation.upper(), "opposite"),
                        )
                        row = cur.fetchone()
                        _total_refs = int(row[0]) if row else None
                    except Exception:
                        pass
                    finally:
                        try:
                            con.close()
                        except Exception:
                            pass
            except Exception:
                pass

            per_gene_rows = client.ranks_for_refs(
                perturbation, ref_genes, effect="rescue"
            )
            for row in per_gene_rows:
                ref = row["ref"]
                if row["found"]:
                    ur = row["union_rank"]
                    cos = row["cosine"]
                    value = (
                        f"Queried rescue candidate: {ref} opposes {perturbation.upper()} KO "
                        f"EP-signature (union_rank {ur}, cos {cos}) [Quiver CNS_DFP]"
                    )
                else:
                    absent_note = (
                        f" (out of {_total_refs} refs)" if _total_refs is not None else ""
                    )
                    value = (
                        f"Queried rescue candidate: {ref} not in Quiver's "
                        f"{perturbation.upper()} rescue neighbor set{absent_note} [Quiver CNS_DFP]"
                    )
                facts.append({
                    "field":            "moat rescue (queried gene)",
                    "value":            value,
                    "source":           _SOURCE,
                    "tier":             _TIER,
                    "provenance":       _PROV,
                    "supporting_genes": 1,
                })

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
