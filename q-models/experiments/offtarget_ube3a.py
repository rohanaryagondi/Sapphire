"""Off-target sanity check (NEXT_STEPS 1a) — does MAMMAL's DTI head encode ANY specificity?

Graham's question. The on-target signal is suzetrigine -> Nav1.8 (SCN10A) ~7.6, BUT
the head already showed NO binder-vs-decoy separation on Nav1.8 (decoys score ~7.6 too).
So: score these Nav1.8 drugs against an UNRELATED off-target (UBE3A, an E3 ubiquitin
ligase with no known affinity for these compounds). Decision rule:
  - UBE3A also ~7  -> head predicts "binds" for everything -> no specificity / useless.
  - UBE3A much lower (~2-4) -> "something in there" -> enriching, just not precise.

Cheapest test of whether the DTI head encodes ANY specificity.

Drugs:   suzetrigine, vixotrigine (Nav1.8 blockers) + metformin/caffeine/ibuprofen (background).
Targets: UBE3A (Q05086, ~875 aa -> FITS under the 1250-aa cap, NO truncation penalty),
         Nav1.8 (Q9Y5Y9, 1956 aa -> on-target baseline, truncated to 1250),
         TUBB tubulin beta (P07437, ~444 aa -> secondary off-target, fully visible).

Uses the CORRECT PEER DTI checkpoint + its norm constants (6.286 / 1.542).

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/offtarget_ube3a.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import functools
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence, DRUGS  # noqa: E402

PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_M, PEER_S = 6.286291085593906, 1.5422950906208512

# Targets: (display, accession, gene, note, len_cap_note)
TARGETS = {
    "UBE3A":  ("Q05086", "UBE3A",  "E3 ubiquitin ligase — primary OFF-target (~875 aa, FITS 1250 cap, no truncation)"),
    "Nav1.8": ("Q9Y5Y9", "SCN10A", "voltage-gated Na channel — ON-target baseline (1956 aa, truncated to 1250)"),
    "TUBB":   ("P07437", "TUBB",   "tubulin beta — secondary OFF-target (~444 aa, fully visible)"),
}

# Drugs: Nav1.8 blockers of interest + background small molecules.
NAV_DRUGS = ["suzetrigine", "vixotrigine"]
BACKGROUND = ["metformin", "caffeine", "ibuprofen"]


@functools.lru_cache(maxsize=256)
def pubchem_smiles(name):
    """PubChem name -> isomeric SMILES (helper copied from phase2b_quiver_targets.py)."""
    u = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
         f"{urllib.parse.quote(name)}/property/IsomericSMILES,CanonicalSMILES/JSON")
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return p.get("IsomericSMILES") or p.get("CanonicalSMILES") or p.get("SMILES")
    except Exception as e:
        print(f"  PubChem lookup FAILED for {name!r}: {e}")
        return None


def rdkit_formula(smiles):
    try:
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors, Descriptors
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return None, None
        return rdMolDescriptors.CalcMolFormula(m), round(Descriptors.MolWt(m), 1)
    except Exception as e:
        print(f"  rdkit parse failed: {e}")
        return None, None


def resolve_vixotrigine():
    """Fetch vixotrigine SMILES from PubChem (try its aliases), verify the formula.

    NOTE (verified 2026-06-07): all four aliases resolve to PubChem CID 16046068,
    formula C18H18FN2O2 -> C18H19FN2O2 (MW 314.4), IUPAC
    (2S,5R)-5-[4-[(2-fluorophenyl)methoxy]phenyl]pyrrolidine-2-carboxamide. This
    matches DrugBank / ChEMBL (CHEMBL2105708): vixotrigine = C18H19FN2O2, MW 314.36,
    ONE fluorine. The task spec's "C16H16F2N2O2, MW~322" (two F) is WRONG — it does
    not describe vixotrigine. We verify against the authoritative formula instead.
    If lookup fails or formula is wrong, STOP — don't score a wrong molecule.
    """
    EXPECTED = "C18H19FN2O2"   # vixotrigine, verified against PubChem CID 16046068 / ChEMBL
    for alias in ("vixotrigine", "BIIB074", "raxatrigine", "GSK1014802"):
        s = pubchem_smiles(alias)
        if s:
            formula, mw = rdkit_formula(s)
            print(f"  vixotrigine via {alias!r}: {s}")
            print(f"    rdkit formula={formula} MW={mw}  (expected {EXPECTED}, MW~314.4)")
            if formula == EXPECTED:
                return s, formula, mw
            else:
                print(f"    WARNING: formula mismatch for {alias!r}; trying next alias.")
    return None, None, None


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Resolve & verify vixotrigine SMILES BEFORE loading the model ---
    vix_smiles, vix_formula, vix_mw = resolve_vixotrigine()
    if vix_smiles is None:
        print("\nSTOP: could not get a vixotrigine SMILES with the expected formula "
              "(C16H16F2N2O2). Not scoring a wrong molecule. Aborting.")
        sys.exit(1)

    drug_smiles = {
        "suzetrigine": DRUGS["suzetrigine"],
        "vixotrigine": vix_smiles,
        "metformin":   DRUGS["metformin"],
        "caffeine":    DRUGS["caffeine"],
        "ibuprofen":   DRUGS["ibuprofen"],
    }
    all_drugs = NAV_DRUGS + BACKGROUND

    # --- Load model & target sequences ---
    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"\nPEER DTI on {dev}")

    seqs = {}
    for disp, (acc, gene, note) in TARGETS.items():
        s = fetch_uniprot_sequence(acc)
        seqs[disp] = s
        cap = " (>1250 -> TRUNCATED)" if len(s) > 1250 else " (<=1250, fully visible)"
        print(f"  {disp:7s} {acc} ({gene}) len={len(s)}{cap}")

    # --- Score the full drug x target matrix ---
    print("\nScoring pKd matrix (PEER norms 6.286 / 1.542)...")
    matrix = {}  # target -> {drug: pkd}
    for disp in TARGETS:
        matrix[disp] = {}
        for d in all_drugs:
            pk = predict_pkd(model, tok, seqs[disp], drug_smiles[d], PEER_M, PEER_S)
            matrix[disp][d] = round(pk, 3)
            print(f"  {disp:7s} x {d:12s} pKd = {pk:6.3f}")

    # --- Deltas: on-target (Nav1.8) - off-target (UBE3A) for the Nav drugs ---
    deltas = {}
    for d in NAV_DRUGS:
        on = matrix["Nav1.8"][d]
        off_ube3a = matrix["UBE3A"][d]
        off_tubb = matrix["TUBB"][d]
        deltas[d] = {
            "nav1.8_on": on,
            "ube3a_off": off_ube3a,
            "tubb_off": off_tubb,
            "delta_nav_minus_ube3a": round(on - off_ube3a, 3),
            "delta_nav_minus_tubb": round(on - off_tubb, 3),
        }

    print("\nOn-target vs off-target deltas (Nav1.8 - off):")
    for d, dd in deltas.items():
        print(f"  {d:12s} Nav1.8={dd['nav1.8_on']:.3f}  UBE3A={dd['ube3a_off']:.3f} "
              f"(d={dd['delta_nav_minus_ube3a']:+.3f})  TUBB={dd['tubb_off']:.3f} "
              f"(d={dd['delta_nav_minus_tubb']:+.3f})")

    # --- Spread summary: how wide is the whole pKd range? ---
    all_vals = [v for tgt in matrix.values() for v in tgt.values()]
    spread = {"min": round(min(all_vals), 3), "max": round(max(all_vals), 3),
              "range": round(max(all_vals) - min(all_vals), 3)}
    print(f"\nWhole-matrix pKd spread: min={spread['min']} max={spread['max']} range={spread['range']}")

    res = {
        "timestamp": ts,
        "checkpoint": "dti_bindingdb_pkd_peer",
        "norm_constants": [PEER_M, PEER_S],
        "device": dev,
        "vixotrigine_smiles": vix_smiles,
        "vixotrigine_formula": vix_formula,
        "vixotrigine_mw": vix_mw,
        "drug_smiles": drug_smiles,
        "targets": {disp: {"accession": acc, "gene": gene, "len": len(seqs[disp]),
                           "truncated": len(seqs[disp]) > 1250, "note": note}
                    for disp, (acc, gene, note) in TARGETS.items()},
        "pkd_matrix": matrix,
        "deltas": deltas,
        "pkd_spread": spread,
    }
    out = REPO / "results" / f"offtarget_ube3a_{ts}.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
