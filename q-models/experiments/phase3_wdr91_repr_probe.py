"""Phase 3 — does the FINE-TUNED wdr91 ENCODER hold WDR91 signal the dead head can't read?

The published wdr91_asms regression head is bit-identical to base (untrained), so the
scalar readout is meaningless. But the encoder DID move from base (relL2 0.024). Question:
did that movement encode WDR91-discriminative structure that a *working* head would exploit?
If yes -> "fine-tuning works, only the saved head is broken (recoverable)". If the fine-tuned
encoder separates actives no better than the BASE encoder -> the public checkpoint added
nothing usable.

Method: embed actives+decoys with (a) wdr91 encoder, (b) base encoder, (c) Morgan FP
[the established phase2a baseline]. Metric = 5-fold stratified CV, nearest-active-centroid
by cosine (build centroid from train-fold actives, score held-out molecules), pooled AUROC.
The informative number is the wdr91 - base DELTA. Centroid scoring can't overfit 768 dims,
unlike a free logistic probe.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_wdr91_repr_probe.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver.embed import embed, load_base_model
from mammal_quiver.wdr91 import load_wdr91_model
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold


def morgan_matrix(smiles_list):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    rows = []
    for smi in smiles_list:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            rows.append(np.zeros(2048)); continue
        fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
        arr = np.zeros((2048,), dtype=np.float32)
        from rdkit.DataStructs import ConvertToNumpyArray
        ConvertToNumpyArray(fp, arr)
        rows.append(arr)
    return np.vstack(rows)


def embed_matrix(model, tok, smiles_list, tag):
    vecs = []
    for i, smi in enumerate(smiles_list):
        v = embed(model, tok, smi, kind="smiles").cpu().numpy()
        vecs.append(v)
        if (i + 1) % 100 == 0:
            print(f"    {tag} embedded {i+1}/{len(smiles_list)}")
    return np.vstack(vecs)


def cv_centroid_auroc(X, y, seed=0):
    """5-fold stratified CV; score = cosine to train-fold active centroid; pooled AUROC."""
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    y = np.asarray(y)
    oof = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    for tr, te in skf.split(Xn, y):
        centroid = Xn[tr][y[tr] == 1].mean(axis=0)
        centroid /= (np.linalg.norm(centroid) + 1e-9)
        oof[te] = Xn[te] @ centroid
    return roc_auc_score(y, oof)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    smiles = [a["smiles"] for a in actives] + [d["smiles"] for d in decoys]
    y = [1] * len(actives) + [0] * len(decoys)
    print(f"actives={len(actives)} decoys={len(decoys)}")

    print("  embedding with BASE encoder ...")
    bm, bt, _ = load_base_model()
    Xb = embed_matrix(bm, bt, smiles, "base")
    del bm
    print("  embedding with WDR91 encoder ...")
    wm, wt, _ = load_wdr91_model()
    Xw = embed_matrix(wm, wt, smiles, "wdr91")
    del wm
    print("  building Morgan fingerprints ...")
    Xm = morgan_matrix(smiles)

    reps = {"base_encoder": Xb, "wdr91_encoder": Xw, "morgan_fp": Xm}
    # average over a few seeds for stable AUROC
    out = {}
    for name, X in reps.items():
        aucs = [cv_centroid_auroc(X, y, seed=s) for s in range(5)]
        out[name] = {"cv_auroc_mean": round(float(np.mean(aucs)), 4),
                     "cv_auroc_std": round(float(np.std(aucs)), 4)}
    delta = out["wdr91_encoder"]["cv_auroc_mean"] - out["base_encoder"]["cv_auroc_mean"]

    print("\n===== WDR91 actives-vs-decoys separability by representation =====")
    print("(5-fold CV, nearest-active-centroid cosine, mean over 5 seeds)")
    for name in ("base_encoder", "wdr91_encoder", "morgan_fp"):
        print(f"  {name:14s}: AUROC {out[name]['cv_auroc_mean']:.4f} ± {out[name]['cv_auroc_std']:.4f}")
    print(f"\n  DELTA (wdr91 - base) = {delta:+.4f}  "
          f"({'fine-tune improved repr' if delta > 0.03 else 'no meaningful improvement from fine-tuning'})")

    summary = {"timestamp": ts, "n_actives": len(actives), "n_decoys": len(decoys),
               "method": "5fold CV nearest-active-centroid cosine, mean of 5 seeds",
               "representations": out, "delta_wdr91_minus_base": round(delta, 4)}
    p = REPO / "results" / f"phase3_wdr91_repr_probe_{ts}.json"
    p.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
