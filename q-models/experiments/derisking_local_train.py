#!/usr/bin/env python3
"""Live local de-risking models (BBBP / hERG / DILI) — MapLight-class fingerprint+GBT, CPU,
served in the Explorer. Local, $0, no AWS.

MapLight (the campaign's Track-4/5 winner) is a fingerprint+gradient-boosting model — so, like the
per-target DTI fine-tunes, it can run LIVE inside the Explorer. This trains a MapLight-style model
per endpoint (Morgan ECFP4 2048 + MACCS 167 + RDKit 2D descriptors -> HistGradientBoosting), on the
TDC benchmark each endpoint uses, with a Murcko scaffold split, and saves a deployable joblib
(+ train-active fingerprints for a Tanimoto-to-train confidence flag).

Endpoints: BBB_Martins (BBBP, Track 4), hERG_Karim (hERG, Track 5), DILI (Track 5).
Reference (full MapLight on AWS): BBBP 0.905-0.919, hERG 0.89, DILI ~0.83.
"""
import json, os, warnings
import numpy as np
warnings.filterwarnings("ignore")
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, DataStructs, MACCSkeys, Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
import joblib
RDLogger.DisableLog("rdApp.*")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "models", "derisking_local")
os.makedirs(OUT, exist_ok=True)

# (track, joblib name, TDC group, TDC name, reference AUROC)
ENDPOINTS = [
    ("bbbp", "BBB_Martins", "ADME", "BBB_Martins", 0.91),
    ("herg", "hERG_Karim", "Tox", "hERG_Karim", 0.89),
    ("dili", "DILI", "Tox", "DILI", 0.83),
]
_DESC_NAMES = [d[0] for d in Descriptors._descList][:80]   # first 80 RDKit 2D descriptors
_CALC = MoleculeDescriptors.MolecularDescriptorCalculator(_DESC_NAMES)


def featurize(smiles):
    """MapLight-style: Morgan(2048) + MACCS(167) + RDKit 2D descriptors. Returns (vec, morgan_bv)."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None, None
    mbv = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
    morgan = np.zeros((2048,), dtype=np.float32); DataStructs.ConvertToNumpyArray(mbv, morgan)
    maccs = np.zeros((167,), dtype=np.float32)
    DataStructs.ConvertToNumpyArray(MACCSkeys.GenMACCSKeys(m), maccs)
    try:
        desc = np.array(_CALC.CalcDescriptors(m), dtype=np.float32)
        desc = np.nan_to_num(desc, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception:
        desc = np.zeros((len(_DESC_NAMES),), dtype=np.float32)
    return np.concatenate([morgan, maccs, desc]), mbv


def scaf(s):
    m = Chem.MolFromSmiles(s)
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) or s
    except Exception:
        return s


def load_tdc(group, name):
    if group == "ADME":
        from tdc.single_pred import ADME as G
    else:
        from tdc.single_pred import Tox as G
    d = G(name=name)
    sp = d.get_split(method="scaffold")
    return sp


def build(df):
    X, y, bvs = [], [], []
    for smi, lab in zip(df["Drug"], df["Y"]):
        v, bv = featurize(smi)
        if v is not None:
            X.append(v); y.append(int(lab)); bvs.append(bv)
    return np.array(X), np.array(y), bvs


def main():
    summary = {"recipe": "Morgan2048+MACCS167+RDKit2D -> HistGradientBoosting; TDC scaffold split",
               "endpoints": {}}
    for track, jname, group, tname, ref in ENDPOINTS:
        print(f"=== {jname} ({group}/{tname}) ===")
        try:
            sp = load_tdc(group, tname)
        except Exception as e:
            print(f"[skip] {jname}: TDC load failed: {e}")
            summary["endpoints"][jname] = {"status": "tdc_failed", "error": str(e)[:120]}
            continue
        Xtr, ytr, bvtr = build(sp["train"])
        Xva, yva, _ = build(sp["valid"])
        Xte, yte, _ = build(sp["test"])
        clf = HistGradientBoostingClassifier(random_state=0, max_iter=300)
        clf.fit(np.vstack([Xtr, Xva]), np.concatenate([ytr, yva]))
        te_auroc = round(float(roc_auc_score(yte, clf.predict_proba(Xte)[:, 1])), 4) \
            if len(set(yte)) > 1 else None
        # store a sample of ALL train Morgan bvs for a proper applicability-domain (Tanimoto-to-
        # train) flag — for de-risking we care about similarity to ANY training compound (both
        # classes), not just actives (else a benign cpd far from blockers looks "OOD").
        import random as _r; _r.seed(0)
        all_bvs = list(bvtr); _r.shuffle(all_bvs)
        bundle = {"clf": clf, "track": track, "endpoint": jname, "fp_radius": 2, "fp_bits": 2048,
                  "desc_names": _DESC_NAMES, "train_all_fps": all_bvs[:2500],
                  "test_scaffold_auroc": te_auroc, "n_train": int(len(ytr) + len(yva)),
                  "reference_maplight_auroc": ref}
        joblib.dump(bundle, os.path.join(OUT, f"{jname}.joblib"))
        summary["endpoints"][jname] = {"status": "trained", "track": track,
                                       "test_scaffold_auroc": te_auroc, "n_train": int(len(ytr) + len(yva)),
                                       "reference_maplight_auroc": ref,
                                       "model": f"models/derisking_local/{jname}.joblib"}
        print(f"[train] {jname}: scaffold-test AUROC={te_auroc} (MapLight ref {ref}); saved")
    json.dump(summary, open(os.path.join(REPO, "results", "derisking_local_result.json"), "w"), indent=2)
    print("\nwrote results/derisking_local_result.json + models/derisking_local/*.joblib")


if __name__ == "__main__":
    main()
