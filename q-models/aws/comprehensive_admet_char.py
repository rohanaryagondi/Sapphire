"""Comprehensive (Boltz-level) characterization of the de-risking winners — Tracks 4 & 5.

Not just an accuracy number: for MolFormer-XL and ChemBERTa-2 on BBB_Martins / hERG_Karim / DILI,
map the OPERATING ENVELOPE — where each model is reliable vs not:
  1. random-split AUROC (the headline)
  2. scaffold-held-out AUROC (Murcko) — does it generalize across chemotypes, or memorize scaffolds?
  3. applicability domain — bin test compounds by max Tanimoto (Morgan FP) to train; AUROC per
     bin (near / mid / far/out-of-domain). The nuance: where does it silently degrade?
  4. calibration — Brier score + 3-bin reliability (are the probabilities trustworthy?)
  5. TPR/TNR asymmetry at 0.5 (trust-the-yes vs trust-the-no)

Reads /opt/admet_traintest.json. Writes /opt/comprehensive_admet_result.json (after each
model x endpoint = partial-safe). Deps: transformers, torch, rdkit, scikit-learn, numpy.
"""
from __future__ import annotations
import os, json, time, traceback
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from datetime import datetime
import numpy as np

DATA = "/opt/admet_traintest.json" if os.path.exists("/opt/admet_traintest.json") else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "admet_traintest.json")
OUTDIR = "/opt" if os.path.isdir("/opt") and os.access("/opt", os.W_OK) else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
OUT = os.path.join(OUTDIR, "comprehensive_admet_result.json")

MODELS = [("MolFormer-XL", "ibm/MoLFormer-XL-both-10pct"), ("ChemBERTa-2", "DeepChem/ChemBERTa-77M-MLM")]
ENDPOINTS = ["BBB_Martins", "hERG_Karim", "DILI"]


def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0: return float("nan")
    o = np.argsort(s, kind="mergesort"); rk = np.empty(len(s)); rk[o] = np.arange(1, len(s)+1)
    u, inv, cnt = np.unique(s, return_inverse=True, return_counts=True); avg = {}; st = 0
    for k, c in enumerate(cnt): avg[k] = (st+1+st+c)/2; st += c
    rb = np.array([avg[i] for i in inv]); return float((rb[y == 1].sum()-p*(p+1)/2)/(p*n))


def scaffold(smi):
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    try:
        m = Chem.MolFromSmiles(smi)
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) if m else None
    except Exception:
        return None


def morgan(smis):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit import DataStructs
    fps = []
    for s in smis:
        m = Chem.MolFromSmiles(s)
        fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None)
    return fps


def max_tanimoto(test_fps, train_fps):
    from rdkit import DataStructs
    tr = [f for f in train_fps if f is not None]
    out = []
    for f in test_fps:
        if f is None:
            out.append(0.0); continue
        sims = DataStructs.BulkTanimotoSimilarity(f, tr)
        out.append(max(sims) if sims else 0.0)
    return np.array(out)


def calibration(y, p, bins=3):
    y = np.asarray(y); p = np.asarray(p, float)
    brier = float(np.mean((p - y) ** 2))
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    rel = []
    for i in range(bins):
        m = (p >= edges[i]) & (p <= edges[i + 1])
        if m.sum() > 0:
            rel.append({"bin": i, "pred_mean": round(float(p[m].mean()), 3),
                        "obs_rate": round(float(y[m].mean()), 3), "n": int(m.sum())})
    return {"brier": round(brier, 3), "reliability": rel}


def main():
    t0 = datetime.now()
    import torch
    from transformers import AutoModel, AutoTokenizer
    from sklearn.linear_model import LogisticRegression
    data = json.load(open(DATA))
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device {dev}", flush=True)

    res = {"test": "comprehensive_admet_characterization", "timestamp": t0.isoformat(),
           "models": {}, "dims": ["random_auroc", "scaffold_auroc", "applicability_domain",
                                   "calibration", "tpr_tnr_asymmetry"]}

    for mname, repo in MODELS:
        tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
        model = AutoModel.from_pretrained(repo, trust_remote_code=True,
                                          **({"deterministic_eval": True} if "MoLFormer" in repo else {})).to(dev).eval()

        @torch.no_grad()
        def embed(smis, bs=64):
            out = []
            for i in range(0, len(smis), bs):
                inp = tok(smis[i:i+bs], padding=True, truncation=True, max_length=256, return_tensors="pt").to(dev)
                h = model(**inp).last_hidden_state
                m = inp["attention_mask"].unsqueeze(-1).float()
                out.append(((h*m).sum(1)/m.sum(1).clamp(min=1)).cpu().numpy().astype(np.float64))
            return np.concatenate(out, 0)

        res["models"][mname] = {}
        for ep in ENDPOINTS:
            try:
                tr, te = data[ep]["train"], data[ep]["test"]
                tr_s = [r["smiles"] for r in tr]; ytr = np.array([r["y"] for r in tr])
                te_s = [r["smiles"] for r in te]; yte = np.array([r["y"] for r in te])
                Xtr, Xte = embed(tr_s), embed(te_s)
                clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
                p = clf.predict_proba(Xte)[:, 1]
                # 1. random-split AUROC + asymmetry
                pred = (p >= 0.5).astype(int)
                tp = int(((pred==1)&(yte==1)).sum()); tn=int(((pred==0)&(yte==0)).sum())
                fp = int(((pred==1)&(yte==0)).sum()); fn=int(((pred==0)&(yte==1)).sum())
                tpr = tp/(tp+fn) if (tp+fn) else float("nan"); tnr = tn/(tn+fp) if (tn+fp) else float("nan")
                # 2. scaffold-held-out: refit on scaffolds disjoint from test scaffolds
                tr_sc = [scaffold(s) for s in tr_s]; te_sc = set(scaffold(s) for s in te_s)
                keep = [i for i, sc in enumerate(tr_sc) if sc not in te_sc]
                sc_auroc = float("nan")
                if len(set(ytr[keep])) == 2 and len(keep) > 30:
                    clf2 = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr[keep], ytr[keep])
                    sc_auroc = auroc(yte, clf2.predict_proba(Xte)[:, 1])
                # 3. applicability domain: AUROC by Tanimoto-to-train bin
                tr_fp = morgan(tr_s); te_fp = morgan(te_s)
                mt = max_tanimoto(te_fp, tr_fp)
                ad = []
                for lo, hi, lab in [(0.0, 0.3, "far/OOD"), (0.3, 0.5, "mid"), (0.5, 1.01, "near")]:
                    m = (mt >= lo) & (mt < hi)
                    if m.sum() >= 10 and len(set(yte[m])) == 2:
                        ad.append({"band": lab, "tanimoto": f"{lo}-{hi}", "n": int(m.sum()),
                                   "auroc": round(auroc(yte[m], p[m]), 3)})
                res["models"][mname][ep] = {
                    "n_test": len(yte), "pos": int(yte.sum()),
                    "random_auroc": round(auroc(yte, p), 3),
                    "scaffold_held_out_auroc": round(sc_auroc, 3) if sc_auroc == sc_auroc else None,
                    "TPR": round(tpr, 3), "TNR": round(tnr, 3),
                    "applicability_domain": ad,
                    "calibration": calibration(yte, p),
                }
                r = res["models"][mname][ep]
                print(f"  {mname}/{ep}: rand {r['random_auroc']} | scaffold {r['scaffold_held_out_auroc']} | "
                      f"AD {[(a['band'],a['auroc']) for a in ad]} | brier {r['calibration']['brier']}", flush=True)
            except Exception as e:
                res["models"][mname][ep] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}"}
                print(f"  {mname}/{ep} FAILED: {str(e)[:150]}", flush=True); print(traceback.format_exc()[:600], flush=True)
            json.dump(res, open(OUT, "w"), indent=2)
        del model, tok
        import gc; gc.collect(); torch.cuda.empty_cache()
    print(f"DONE {(datetime.now()-t0).total_seconds():.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
