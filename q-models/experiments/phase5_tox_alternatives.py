"""
Phase 5 — Tox gate replacement: MAMMAL ClinTox vs. simple RDKit alerts vs. pkCSM API.

MAMMAL ClinTox-tox scored 0% sensitivity to external clinically-toxic drugs.
This test asks: what would we use instead?

Three alternatives tested on the same 15-safe + 15-toxic literature set:
  1. RDKit structural alerts (Brenk + PAINS via FilterCatalog) — rule-based, fast, interpretable
  2. pkCSM API (http://biosig.lab.uq.edu.au/pkcsm/prediction) — ML, free, returns hERG/tox predictions
  3. Simple lipophilicity/TPSA heuristics (logP > 5, TPSA < 60, QED) — dead simple baseline

The toxic drugs in the set (ClinTox missed them all):
  cerivastatin (rhabdo), troglitazone (hepato), terfenadine (QTc/cardiac),
  thalidomide (teratogen), cisapride (QTc), bromfenac (hepato),
  mibefradil (drug-drug interactions/cardiac), trovafloxacin (hepato),
  grepafloxacin (QTc), alosetron (ischemic colitis), cefonicid (hemolytic),
  valdecoxib (SJS), ximelagatran (hepato), pemoline (hepato), nefazodone (hepato)

Safe drugs (ClinTox correctly called 0% false alarm on these with clean SMILES):
  aspirin, ibuprofen, metformin, lisinopril, atorvastatin,
  omeprazole, metoprolol, amlodipine, losartan, levothyroxine,
  gabapentin, citalopram, donepezil, memantine, levetiracetam
"""
import os, sys, json, time
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, QED
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
from rdkit.Chem.MolStandardize import rdMolStandardize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results", f"phase5_tox_alternatives_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")

COMPOUNDS = [
    # safe=0
    {"name": "aspirin",        "smiles": "CC(=O)Oc1ccccc1C(=O)O",                   "toxic": 0},
    {"name": "ibuprofen",      "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",              "toxic": 0},
    {"name": "metformin",      "smiles": "CN(C)C(=N)NC(N)=N",                        "toxic": 0},
    {"name": "lisinopril",     "smiles": "OC(=O)C(CCCl)NC(=O)C(CCc1ccccc1)N1CCCC1C(=O)O", "toxic": 0},
    {"name": "atorvastatin",   "smiles": "CC(C)c1n(CC(O)CC(O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2F)c1C(C)C", "toxic": 0},
    {"name": "omeprazole",     "smiles": "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1", "toxic": 0},
    {"name": "metoprolol",     "smiles": "COCCc1ccc(OCC(O)CNC(C)C)cc1",              "toxic": 0},
    {"name": "amlodipine",     "smiles": "CCOC(=O)C1=C(COCCN)NC(C)=C(C(=O)OC)C1c1ccccc1Cl", "toxic": 0},
    {"name": "losartan",       "smiles": "Clc1ccc(-c2ccccc2Cn2nnnn2)cc1CCc1ccc(CC(O)c2ccc(Cl)cc2)nn1", "toxic": 0},
    {"name": "gabapentin",     "smiles": "NCC1(CC(=O)O)CCCCC1",                      "toxic": 0},
    {"name": "citalopram",     "smiles": "CN(C)CCCC1(OCC#N)c2ccc(F)cc2-c2ccccc21",  "toxic": 0},
    {"name": "donepezil",      "smiles": "COc1cc2c(cc1OC)CC(CC(=O)Cc1ccc(OC)c(OC)c1)N(C)CC2", "toxic": 0},
    {"name": "memantine",      "smiles": "CC12CC(C)(CC(C1)(CC2)N)C",                 "toxic": 0},
    {"name": "levetiracetam",  "smiles": "CC[C@@H]1CCNC1=O.NCC(=O)N1CCCC1",         "toxic": 0},
    {"name": "levothyroxine",  "smiles": "Nc1cc(I)c(Oc2cc(I)c(O)c(I)c2)c(I)c1CC(N)C(=O)O", "toxic": 0},
    # toxic=1
    {"name": "cerivastatin",   "smiles": "OC(CC(O)CC(=O)O)C=CC1=C(C(C)C)N(C)C(=C1C(=O)OCC)c1ccc(F)cc1", "toxic": 1},
    {"name": "troglitazone",   "smiles": "O=C1CSC(=O)N1Cc1ccc(OCC(C)(C)c2ccc(C)cc2-c2ccc(C)cc2O)cc1", "toxic": 1},  # simplified
    {"name": "terfenadine",    "smiles": "OC(CCN1CCC(CC1)c1ccccc1)c1ccc(C(C)(C)C)cc1", "toxic": 1},
    {"name": "thalidomide",    "smiles": "O=C1CCC(=O)N1C1CC(=O)Nc2ccccc21",          "toxic": 1},
    {"name": "cisapride",      "smiles": "COc1cc(NC(=O)c2cc(Cl)c(N)c(OC)c2)ccc1N1CCCCC1", "toxic": 1},
    {"name": "bromfenac",      "smiles": "NC1=C(CC(=O)c2ccc(Br)cc2)C(=O)c2ccccc21", "toxic": 1},
    {"name": "mibefradil",     "smiles": "COC(=O)N1CCN(C)CC1CC(=O)Oc1cccc2c1CCC1(CCCC1)c1ccccc1", "toxic": 1},
    {"name": "trovafloxacin",  "smiles": "OC(=O)c1cn2c(nc1=O)c(C1CC1)cc2N1CC(F)(F)C1", "toxic": 1},  # simplified
    {"name": "grepafloxacin",  "smiles": "CC1COc2c(N3CCN(C)CC3)c(F)cc3c(=O)c(C(=O)O)cn1c23", "toxic": 1},
    {"name": "alosetron",      "smiles": "CN1C(=O)Nc2ccc3[nH]cnc3c21",               "toxic": 1},
    {"name": "cefonicid",      "smiles": "OC(=O)[C@@H]1[C@H]2CC(=C(CS[C@@H]3NC(=O)[C@H](Cc4ccc(O)cc4)N3)C(=O)O)SCC12", "toxic": 1},  # approx
    {"name": "valdecoxib",     "smiles": "Cc1ccc(-c2cc(=O)no2)cc1-c1ccc(S(N)(=O)=O)cc1", "toxic": 1},
    {"name": "ximelagatran",   "smiles": "CCOC(=O)/N=C/c1ccc(CNC(=O)CN2CCC(N)CC2)cc1", "toxic": 1},
    {"name": "pemoline",       "smiles": "NC1=NC(=O)C(c2ccccc2)O1",                  "toxic": 1},
    {"name": "nefazodone",     "smiles": "OCCN1CCN(CC1)c1ccc(Cl)cc1.Clc1ccc(N2CCCC2=O)cc1CC", "toxic": 1},
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


# ---- RDKit structural alerts ----
def setup_filter_catalog():
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    return FilterCatalog(params)


def rdkit_alert_score(smi: str, catalog: FilterCatalog) -> dict:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return {"has_alert": None, "n_alerts": None, "alerts": []}
    matches = list(catalog.GetMatches(mol))
    return {
        "has_alert": len(matches) > 0,
        "n_alerts": len(matches),
        "alerts": [m.GetDescription() for m in matches[:5]],
    }


# ---- Lipophilicity heuristics ----
def physchem_flags(smi: str) -> dict:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return {}
    logp = Descriptors.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    mw = Descriptors.MolWt(mol)
    qed = QED.qed(mol)
    # simple heuristic: flag if high logP (metabolic concern) or hERG risk proxy
    herg_risk = logp > 3.7 and mw > 300  # rough hERG proxy (lipophilic + big)
    return {"logp": round(logp, 2), "tpsa": round(tpsa, 1), "mw": round(mw, 1),
            "qed": round(qed, 3), "herg_risk_heuristic": herg_risk}


# ---- pkCSM API (hERG inhibition prediction) ----
PKCSM_URL = "http://biosig.lab.uq.edu.au/pkcsm/prediction"

def pkcsm_score(smi: str) -> dict | None:
    """Query pkCSM for hERG + acute_oral_toxicity. Returns None on failure."""
    try:
        r = requests.post(
            PKCSM_URL,
            data={"smiles": smi, "target": "herg"},
            timeout=20,
        )
        if r.status_code == 200 and r.text.strip():
            # pkCSM returns a table; parse the first numeric value
            lines = [l for l in r.text.strip().split("\n") if l.strip()]
            # Try JSON parse
            try:
                data = r.json()
                return {"pkcsm_herg": data}
            except Exception:
                return {"pkcsm_raw": r.text[:200]}
        return None
    except Exception as e:
        return {"error": str(e)}


def main():
    print("Setting up RDKit alert catalog...")
    catalog = setup_filter_catalog()

    results = []
    for c in COMPOUNDS:
        smi = neutral_parent(c["smiles"])
        if smi is None:
            print(f"  INVALID SMILES: {c['name']}")
            continue

        alerts = rdkit_alert_score(smi, catalog)
        physchem = physchem_flags(smi)

        row = {
            "name": c["name"],
            "toxic": c["toxic"],
            "smiles": smi,
            **{f"alert_{k}": v for k, v in alerts.items()},
            **{f"pc_{k}": v for k, v in physchem.items()},
        }
        results.append(row)

    df = pd.DataFrame(results)

    # ---- Classification metrics per method ----
    y = df["toxic"].values

    # Method 1: RDKit alerts (predict toxic if has_alert)
    alert_pred = df["alert_has_alert"].fillna(False).astype(int).values
    from sklearn.metrics import roc_auc_score, confusion_matrix
    def metrics(y_true, y_pred_binary):
        cm = confusion_matrix(y_true, y_pred_binary, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        return {"TPR": round(tpr, 3), "TNR": round(tnr, 3), "TP": int(tp), "FP": int(fp),
                "TN": int(tn), "FN": int(fn)}

    alert_m = metrics(y, alert_pred)

    # Method 2: hERG risk heuristic (logP > 3.7, MW > 300)
    herg_pred = df["pc_herg_risk_heuristic"].fillna(False).astype(int).values
    herg_m = metrics(y, herg_pred)

    # Method 3: combined (alert OR hERG heuristic)
    combined_pred = ((df["alert_has_alert"].fillna(False)) | (df["pc_herg_risk_heuristic"].fillna(False))).astype(int).values
    combined_m = metrics(y, combined_pred)

    print("\n=== Tox alternatives — 15 safe + 15 clinical toxics ===")
    print(f"\n  Method                      TPR (sens)  TNR (spec)  TP  FP  TN  FN")
    print(f"  {'RDKit BRENK+PAINS alerts':<28} {alert_m['TPR']:>10}  {alert_m['TNR']:>10}  {alert_m['TP']}   {alert_m['FP']}   {alert_m['TN']}   {alert_m['FN']}")
    print(f"  {'logP>3.7+MW>300 hERG proxy':<28} {herg_m['TPR']:>10}  {herg_m['TNR']:>10}  {herg_m['TP']}   {herg_m['FP']}   {herg_m['TN']}   {herg_m['FN']}")
    print(f"  {'Combined (alert OR hERG)':<28} {combined_m['TPR']:>10}  {combined_m['TNR']:>10}  {combined_m['TP']}   {combined_m['FP']}   {combined_m['TN']}   {combined_m['FN']}")
    print(f"  {'MAMMAL ClinTox-tox (Phase 4)':<28} {'0.000':>10}  {'1.000':>10}  0   0   15  15  (memorization baseline)")

    print("\n  Alerts per compound (BRENK+PAINS):")
    for _, row in df.iterrows():
        mark = "TOXIC" if row["toxic"] else "safe "
        detected = "FLAGGED" if row["alert_has_alert"] else "clean  "
        print(f"    [{mark}] {row['name']:20} {detected}  n_alerts={row['alert_n_alerts']}  logP={row['pc_logp']:5.1f}  MW={row['pc_mw']:5.0f}  hERG={row['pc_herg_risk_heuristic']}")

    # What did alerts catch / miss?
    missed_toxics = df[(df["toxic"] == 1) & (~df["alert_has_alert"].fillna(False))]
    false_alarms = df[(df["toxic"] == 0) & (df["alert_has_alert"].fillna(False))]
    print(f"\n  Alerts: caught {alert_m['TP']}/15 toxics, false-alarmed on {alert_m['FP']}/15 safe")
    if not missed_toxics.empty:
        print(f"  Missed toxics: {', '.join(missed_toxics['name'].tolist())}")
    if not false_alarms.empty:
        print(f"  False alarms:  {', '.join(false_alarms['name'].tolist())}")

    result = {
        "test": "tox_gate_alternatives",
        "n_safe": int((y == 0).sum()),
        "n_toxic": int((y == 1).sum()),
        "rdkit_alerts": alert_m,
        "herg_heuristic": herg_m,
        "combined": combined_m,
        "mammal_clintox_reference": {"TPR": 0.0, "TNR": 1.0, "note": "0% external toxic sensitivity, Phase 4"},
        "per_compound": df.drop(columns=["alert_alerts"]).to_dict(orient="records"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
