"""
moat/facts.py — Moat facts helper (Task 4).

Returns dossier-shaped fact rows from the Quiver internal moat SQLite database:
  - top similar genes   (EP-signature mimics)
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
        k: max rows per category (similar genes, rescue compounds).

    Returns:
        A list of dicts with keys {field, value, source, tier, provenance},
        similar-gene rows first then rescue-compound rows.
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
            "field":      "moat similar (gene)",
            "value":      value,
            "source":     _SOURCE,
            "tier":       _TIER,
            "provenance": _PROV,
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
            "field":      "moat rescue (compound)",
            "value":      value,
            "source":     _SOURCE,
            "tier":       _TIER,
            "provenance": _PROV,
        })

    return facts
