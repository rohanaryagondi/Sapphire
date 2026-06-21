"""Uni-Mol2 (DPTech, 3D-conformer-aware) BBBP cross-check vs MolFormer-XL 0.889 — Track 4.
unimol_tools UniMolRepr embeddings + logreg probe on TDC BBB_Martins (also hERG/DILI for free).
Reads admet_traintest.json. Out: /opt/unimol2_result.json. (MIT-licensed; commercial-OK.)"""
import os, json
from datetime import datetime
import numpy as np

def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float); p = int((y==1).sum()); n = int((y==0).sum())
    if p == 0 or n == 0: return float("nan")
    o = np.argsort(s, kind="mergesort"); rk = np.empty(len(s)); rk[o] = np.arange(1, len(s)+1)
    u, inv, cnt = np.unique(s, return_inverse=True, return_counts=True); avg = {}; st = 0
    for k, c in enumerate(cnt): avg[k] = (st+1+st+c)/2; st += c
    rb = np.array([avg[i] for i in inv]); return float((rb[y==1].sum()-p*(p+1)/2)/(p*n))

def main():
    t0 = datetime.now()
    from unimol_tools import UniMolRepr
    from sklearn.linear_model import LogisticRegression
    BASE = "/opt" if os.path.exists("/opt/admet_traintest.json") else \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    OUTDIR = "/opt" if os.path.isdir("/opt") and os.access("/opt", os.W_OK) else BASE
    data = json.load(open(f"{BASE}/admet_traintest.json"))
    clf_model = UniMolRepr(data_type="molecule", remove_hs=False, model_name="unimolv2", model_size="84m")
    def emb(smis):
        r = clf_model.get_repr(smis, return_atomic_reprs=False)
        if isinstance(r, dict):
            arr = r.get("cls_repr", r.get("cls_token"))
        elif isinstance(r, list) and r and isinstance(r[0], dict):
            arr = [x.get("cls_repr", x.get("cls_token")) for x in r]
        else:
            arr = r
        arr = np.asarray(arr, dtype=np.float64)
        if arr.ndim == 3:
            arr = arr.reshape(arr.shape[0], -1)
        return arr
    res = {"test": "unimol2_admet", "timestamp": t0.isoformat(), "model": "unimolv2-84m",
           "in_distribution": {}, "refs": {"BBB_MolFormer": 0.889, "BBB_ChemBERTa": 0.873,
                                            "hERG_ChemBERTa_balacc": 0.726, "DILI_ChemBERTa_ext": 0.773}}
    for task in ["BBB_Martins", "DILI"]:  # BBBP is the Track-4 question; DILI small bonus. (hERG_Karim 9.4k too slow on CPU 3D)
        d = data[task]
        Xtr = emb([r["smiles"] for r in d["train"]]); ytr = np.array([r["y"] for r in d["train"]])
        Xte = emb([r["smiles"] for r in d["test"]]); yte = np.array([r["y"] for r in d["test"]])
        clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
        s = clf.predict_proba(Xte)[:, 1]
        res["in_distribution"][task] = {"auroc": auroc(yte, s), "n": len(yte)}
        print(f"  {task}: AUROC {res['in_distribution'][task]['auroc']:.3f}", flush=True)
        json.dump(res, open(f"{OUTDIR}/unimol2_result.json", "w"), indent=2)
    print(f"DONE {(datetime.now()-t0).total_seconds():.0f}s", flush=True)

if __name__ == "__main__":
    main()
