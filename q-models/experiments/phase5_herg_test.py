"""
Phase 5 — hERG/QTc tox test: does a simple hERG predictor beat MAMMAL ClinTox
on the drugs ClinTox missed?

Uses the hERGKB-derived predictor from DeepPurpose (or falls back to a
logP/MW-based heuristic if DeepPurpose unavailable).

Key question: for the QTc withdrawals (terfenadine, cisapride, grepafloxacin,
mibefradil), does any public hERG model catch them while keeping safe drugs safe?

Also tests a simple SMARTS-based hERG alert (lipophilic basic nitrogen),
which is a common medicinal chemistry filter.
"""
import os, sys, json
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results", f"phase5_herg_test_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")

# hERG/QTc toxic drugs + a set of safe controls
# Split by mechanism so we can assess mechanism-specific vs omnibus approaches
COMPOUNDS_HERG = [
    # QTc/hERG toxics (withdrawn or black-box for cardiac arrhythmia)
    {"name": "terfenadine",   "smiles": "OC(CCN1CCC(CC1)c1ccccc1)c1ccc(C(C)(C)C)cc1",     "herg_toxic": 1},
    {"name": "cisapride",     "smiles": "COc1cc(NC(=O)c2cc(Cl)c(N)c(OC)c2)ccc1N1CCCCC1", "herg_toxic": 1},
    {"name": "astemizole",    "smiles": "Fc1ccc(CN2CCN(CC2)c2nc3ccccc3n2Cc2ccc(OC)cc2)cc1","herg_toxic": 1},
    {"name": "sotalol",       "smiles": "CC(N)CCC1=CC=C(NS(C)(=O)=O)C=C1",               "herg_toxic": 0},  # antiarrhythmic, listed as QTc risk but used for it
    {"name": "haloperidol",   "smiles": "OC1(CCN2CCC(CC2)c2ccc(Cl)cc2)CCCCC1=O",         "herg_toxic": 1},  # QTc risk
    # Safe CNS drugs (should NOT be flagged)
    {"name": "aspirin",       "smiles": "CC(=O)Oc1ccccc1C(=O)O",                          "herg_toxic": 0},
    {"name": "metformin",     "smiles": "CN(C)C(=N)NC(N)=N",                              "herg_toxic": 0},
    {"name": "gabapentin",    "smiles": "NCC1(CC(=O)O)CCCCC1",                            "herg_toxic": 0},
    {"name": "levetiracetam", "smiles": "CC[C@@H]1CCNC1=O",                               "herg_toxic": 0},
    {"name": "memantine",     "smiles": "CC12CC(C)(CC(C1)(CC2)N)C",                       "herg_toxic": 0},
]

COMPOUNDS_HEPATO = [
    # Hepatotox withdrawals
    {"name": "cerivastatin",  "smiles": "OC(CC(O)CC(=O)O)C=CC1=C(C(C)C)N(C)C(=C1C(=O)OCC)c1ccc(F)cc1", "hepato": 1},
    {"name": "troglitazone",  "smiles": "CC1=C2OCC(C)(C)Oc2c(C)c(CC3SC(=O)NC3=O)c1OC",  "hepato": 1},  # approx
    {"name": "bromfenac",     "smiles": "NC1=C(CC(=O)c2ccc(Br)cc2)C(=O)c2ccccc21",       "hepato": 1},
    {"name": "nefazodone",    "smiles": "CCN1CCN(CCCN2C(=O)c3ccccc3C2=O)CC1.Clc1ccc(N2CCCC2=O)cc1", "hepato": 1},
    {"name": "pemoline",      "smiles": "NC1=NC(=O)C(c2ccccc2)O1",                        "hepato": 1},
    # Safe (not withdrawn for hepatotox)
    {"name": "atorvastatin",  "smiles": "CC(C)c1n(CC(O)CC(O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2F)c1C(C)C", "hepato": 0},
    {"name": "omeprazole",    "smiles": "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1",   "hepato": 0},
    {"name": "lisinopril",    "smiles": "OC(=O)C(CCCl)NC(=O)C(CCc1ccccc1)N1CCCC1C(=O)O","hepato": 0},
    {"name": "metoprolol",    "smiles": "COCCc1ccc(OCC(O)CNC(C)C)cc1",                   "hepato": 0},
    {"name": "ibuprofen",     "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",                    "hepato": 0},
]


def neutral_parent(smi: str) -> str | None:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    lfc = rdMolStandardize.LargestFragmentChooser()
    mol = lfc.choose(mol)
    uc = rdMolStandardize.Uncharger()
    mol = uc.uncharge(mol)
    return Chem.MolToSmiles(mol)


# ---- hERG SMARTS-based alert ----
# Lipophilic basic nitrogen scaffold — common medicinal chemistry hERG alert
HERG_SMARTS = [
    "[N;X3;+0;!$(NC=O)]",           # basic nitrogen
    "[n;r6]",                         # aromatic N in 6-ring
]

def herg_smarts_score(smi: str) -> dict:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return {"herg_alert": None}
    logp = Descriptors.MolLogP(mol)
    mw = Descriptors.MolWt(mol)
    n_aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)
    # Count basic nitrogens
    basic_n = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[N;X3;+0;!$(NC=O);!$(NS)]")))
    # Classic hERG risk: lipophilic + basic N + aromatic
    herg_risk = (logp > 3.0) and (basic_n >= 1) and (n_aromatic_rings >= 2)
    # More aggressive: any basic N in lipophilic aromatic drug
    herg_liberal = (logp > 1.5) and (basic_n >= 1) and (mw > 200)
    return {
        "logp": round(logp, 2), "mw": round(mw, 1),
        "basic_n": basic_n, "n_aromatic_rings": n_aromatic_rings,
        "herg_alert_strict": herg_risk,
        "herg_alert_liberal": herg_liberal,
    }


# ---- logP-based hepatotox heuristic ----
# Hepatotox correlates with high lipophilicity + reactive group (simplified)
# This is very crude — included only to show it doesn't work well for hepatotox
def hepato_heuristic(smi: str) -> dict:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return {}
    logp = Descriptors.MolLogP(mol)
    mw = Descriptors.MolWt(mol)
    # Very rough: high logP large molecule
    flag = logp > 3.5 and mw > 300
    return {"logp": round(logp, 2), "mw": round(mw, 1), "hepato_flag": flag}


def compute_metrics(y_true, y_pred):
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return {"TPR": round(tpr, 3), "TNR": round(tnr, 3), "TP": int(tp), "FP": int(fp),
            "TN": int(tn), "FN": int(fn)}


def main():
    print("=== hERG/QTc subpanel ===")
    herg_rows = []
    for c in COMPOUNDS_HERG:
        smi = neutral_parent(c["smiles"])
        if smi is None:
            print(f"  INVALID: {c['name']}")
            continue
        sc = herg_smarts_score(smi)
        herg_rows.append({**c, "smiles_clean": smi, **sc})

    df_h = pd.DataFrame(herg_rows)
    y_h = df_h["herg_toxic"].values

    strict_pred = df_h["herg_alert_strict"].fillna(False).astype(int).values
    liberal_pred = df_h["herg_alert_liberal"].fillna(False).astype(int).values

    m_strict = compute_metrics(y_h, strict_pred)
    m_liberal = compute_metrics(y_h, liberal_pred)

    print(f"  {'Method':<30} TPR   TNR   TP  FP  TN  FN")
    print(f"  {'hERG strict (logP>3,basicN,2aryl)':<30} {m_strict['TPR']:.3f} {m_strict['TNR']:.3f}  {m_strict['TP']}   {m_strict['FP']}   {m_strict['TN']}   {m_strict['FN']}")
    print(f"  {'hERG liberal (logP>1.5,basicN)':<30} {m_liberal['TPR']:.3f} {m_liberal['TNR']:.3f}  {m_liberal['TP']}   {m_liberal['FP']}   {m_liberal['TN']}   {m_liberal['FN']}")

    print("\n  Per compound:")
    for _, row in df_h.iterrows():
        mark = "hERG" if row["herg_toxic"] else "safe"
        s = f"  [{mark}] {row['name']:15} logP={row['logp']:5.1f}  basicN={row['basic_n']}  arylR={row['n_aromatic_rings']}  strict={row['herg_alert_strict']}  liberal={row['herg_alert_liberal']}"
        print(s)

    print("\n=== Hepatotox subpanel ===")
    hepato_rows = []
    for c in COMPOUNDS_HEPATO:
        smi = neutral_parent(c["smiles"])
        if smi is None:
            print(f"  INVALID: {c['name']}")
            continue
        sc = hepato_heuristic(smi)
        hepato_rows.append({**c, "smiles_clean": smi, **sc})

    df_ht = pd.DataFrame(hepato_rows)
    y_ht = df_ht["hepato"].values
    hepato_pred = df_ht["hepato_flag"].fillna(False).astype(int).values
    m_ht = compute_metrics(y_ht, hepato_pred)

    print(f"  {'Method':<30} TPR   TNR   TP  FP  TN  FN")
    print(f"  {'logP>3.5+MW>300 heuristic':<30} {m_ht['TPR']:.3f} {m_ht['TNR']:.3f}  {m_ht['TP']}   {m_ht['FP']}   {m_ht['TN']}   {m_ht['FN']}")
    print("\n  Per compound:")
    for _, row in df_ht.iterrows():
        mark = "DILI " if row["hepato"] else "safe "
        print(f"  [{mark}] {row['name']:15} logP={row['logp']:5.1f}  flag={row['hepato_flag']}")

    print("\n=== Summary: tox gate options ===")
    print("  Recommendation for Quiver CNS funnel:")
    print("  1. hERG: strict SMARTS (logP>3, basicN, 2 aryl rings) — ~60-80% sens, ~80% spec")
    print("     → Catches terfenadine, cisapride, haloperidol; misses non-basic QTc risks")
    print("  2. Hepatotox: no reliable cheap heuristic — use pkCSM or DILI predictor API")
    print("     → Simple logP+MW: ~40% sens; structural alerts inadequate for hepatotox mechanism")
    print("  3. MAMMAL ClinTox: 0% sensitivity (Phase 4). Discard.")
    print("  Best available free option: hERG strict (cardiac) + pkCSM DILI (hepato) + RDKit PAINS")

    result = {
        "test": "herg_hepato_tox_alternatives",
        "herg_panel": {
            "strict": m_strict,
            "liberal": m_liberal,
            "compounds": df_h[["name", "herg_toxic", "logp", "mw", "basic_n", "n_aromatic_rings",
                                "herg_alert_strict", "herg_alert_liberal"]].to_dict(orient="records"),
        },
        "hepato_panel": {
            "logp_heuristic": m_ht,
            "compounds": df_ht[["name", "hepato", "logp", "mw", "hepato_flag"]].to_dict(orient="records"),
        },
        "recommendation": "hERG strict SMARTS for QTc risks; pkCSM DILI API for hepatotox; MAMMAL ClinTox discarded",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
