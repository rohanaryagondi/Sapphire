"""Fetch protein sequences (UniProt) and provide reference SMILES for Phase 1.

Sequences are fetched live from UniProt so we never hand-transcribe a 1960-aa
protein. SMILES for the small set of reference drugs are pinned here with their
source so the calibration set is reproducible and auditable.
"""

from __future__ import annotations

import functools
import urllib.request


@functools.lru_cache(maxsize=64)
def fetch_uniprot_sequence(accession: str) -> str:
    """Return the amino-acid sequence for a UniProt accession (no header, no newlines)."""
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    with urllib.request.urlopen(url, timeout=30) as r:
        fasta = r.read().decode()
    lines = fasta.strip().splitlines()
    return "".join(l.strip() for l in lines if not l.startswith(">"))


# --- Reference targets (UniProt accession, gene, note) ---
TARGETS = {
    "Nav1.8": ("Q9Y5Y9", "SCN10A", "voltage-gated sodium channel, the suzetrigine target"),
    # Negative-control proteins: unrelated families, no known suzetrigine binding.
    "CA2": ("P00918", "CA2", "carbonic anhydrase II — soluble enzyme, unrelated"),
    "DHFR": ("P00374", "DHFR", "dihydrofolate reductase — unrelated"),
    "ACHE": ("P22303", "ACHE", "acetylcholinesterase — unrelated to Nav1.8 pharmacology"),
}

# --- Reference drug SMILES (isomeric, from PubChem) ---
DRUGS = {
    # Jernabix == Journavx == suzetrigine == VX-548. CID via name 'suzetrigine'.
    "suzetrigine": "C[C@H]1[C@H]([C@@H](O[C@@]1(C)C(F)(F)F)C(=O)NC2=CC(=NC=C2)C(=O)N)C3=C(C(=C(C=C3)F)F)OC",
    # Negative-control drugs: no known potent Nav1.8 activity.
    "metformin": "CN(C)C(=N)N=C(N)N",
    "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
}


if __name__ == "__main__":
    for name, (acc, gene, note) in TARGETS.items():
        seq = fetch_uniprot_sequence(acc)
        print(f"{name:8s} {acc} ({gene}) len={len(seq)}  {seq[:40]}...")
