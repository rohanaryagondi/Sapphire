"""ChemBERTa-2 multi-endpoint ADMET probe — Tracks 4 (BBBP) + 5 (hERG/DILI/ClinTox).

Commercial-OK (ChemBERTa-2 is MIT/Apache, DeepChem). Fills the de-risking gap: the hERG
rule is weak (bal-acc 0.65) and ClinTox doesn't transfer for MAMMAL or MolFormer. Question:
does a single commercial-usable chem encoder + per-task probe give a deployable de-risking
layer across BBBP/hERG/DILI, and does it transfer to the external withdrawn-vs-safe panel?

Recipe (mirrors experiments/molformer_clintox.py): ChemBERTa-2 mean-pooled embeddings + a
balanced logistic-regression probe trained per TDC task, eval on the TDC test split
(in-distribution AUROC) + the external 30-drug panel (for DILI/ClinTox generalization).

Reads results/admet_traintest.json (TDC train/test for BBB_Martins/hERG_Karim/DILI/ClinTox)
and results/txgemma_panels.json (external_tox_30). Runs locally (small model).
Run: <venv>/bin/python experiments/chemberta_admet.py
Out: results/chemberta_admet.json
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import json
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "results" / "admet_traintest.json"
PANELS = REPO / "results" / "txgemma_panels.json"
OUT = REPO / "results" / "chemberta_admet.json"
MODEL = "DeepChem/ChemBERTa-77M-MLM"


def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort"); ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s)+1)
    uniq, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    avg = {}; st = 0
    for k, c in enumerate(cnt):
        avg[k] = (st + 1 + st + c) / 2; st += c
    rb = np.array([avg[i] for i in inv])
    return float((rb[y == 1].sum() - p*(p+1)/2) / (p*n))


def metrics(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    tp=int(((pred==1)&(y==1)).sum()); tn=int(((pred==0)&(y==0)).sum())
    fp=int(((pred==1)&(y==0)).sum()); fn=int(((pred==0)&(y==1)).sum())
    tpr=tp/(tp+fn) if (tp+fn) else float("nan"); tnr=tn/(tn+fp) if (tn+fp) else float("nan")
    return {"TPR":tpr,"TNR":tnr,"bal_acc":(tpr+tnr)/2,"n":len(y),"pos":int((y==1).sum())}


def main():
    t0 = datetime.now()
    import torch
    from transformers import AutoModel, AutoTokenizer
    from sklearn.linear_model import LogisticRegression

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL).eval()
    print(f"loaded {MODEL}", flush=True)

    @torch.no_grad()
    def embed(smis, bs=64):
        out = []
        for i in range(0, len(smis), bs):
            b = smis[i:i+bs]
            inp = tok(b, padding=True, truncation=True, max_length=256, return_tensors="pt")
            h = model(**inp).last_hidden_state
            m = inp["attention_mask"].unsqueeze(-1).float()
            out.append(((h*m).sum(1)/m.sum(1).clamp(min=1)).cpu().numpy().astype(np.float64))
        return np.concatenate(out, 0)

    data = json.loads(DATA.read_text())
    ext = json.loads(PANELS.read_text())["external_tox_30"]
    ext_smi = [r["smiles"] for r in ext]; ext_y = [r["toxic"] for r in ext]

    result = {"test": "chemberta2_admet_probe", "timestamp": t0.isoformat(), "model": MODEL,
              "approach": "ChemBERTa-2 mean-pool embeddings + balanced logreg probe per TDC task",
              "in_distribution": {}, "external_30drug": {},
              "baselines": {"BBB_Martins_MolFormer": 0.889, "DILI_ADMET_AI_TPR": 0.83,
                            "hERG_rule_balacc": 0.65, "ClinTox_MAMMAL_TPR": 0.08,
                            "ClinTox_MolFormer_external_auroc": 0.244}}

    for task, d in data.items():
        Xtr = embed([r["smiles"] for r in d["train"]]); ytr = np.array([r["y"] for r in d["train"]])
        Xte = embed([r["smiles"] for r in d["test"]]);  yte = np.array([r["y"] for r in d["test"]])
        clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
        s = clf.predict_proba(Xte)[:, 1]
        result["in_distribution"][task] = {"auroc": auroc(yte, s), **metrics(yte, (s>=0.5).astype(int))}
        print(f"  [in-dist] {task}: AUROC {result['in_distribution'][task]['auroc']:.3f} "
              f"bal_acc {result['in_distribution'][task]['bal_acc']:.3f}", flush=True)
        # external panel under DILI + ClinTox probes
        if task in ("DILI", "ClinTox"):
            se = clf.predict_proba(embed(ext_smi))[:, 1]
            result["external_30drug"][task] = {"auroc": auroc(ext_y, se), **metrics(ext_y, (se>=0.5).astype(int))}
            print(f"  [external] {task}: AUROC {result['external_30drug'][task]['auroc']:.3f} "
                  f"TPR {result['external_30drug'][task]['TPR']:.2f}", flush=True)
        OUT.write_text(json.dumps(result, indent=2))

    print(f"\nDONE -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)


if __name__ == "__main__":
    main()
