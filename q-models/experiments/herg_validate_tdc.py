"""Validate the phase5 hERG rule on TDC hERG_Karim (~13K compounds) — Track 5.

The rule (from experiments/phase5_herg_test.py, validated only on n=10):
    hERG-risk = (MolLogP > 3.0) AND (basic_N >= 1) AND (aromatic_rings >= 2)
where basic_N = SMARTS matches of [N;X3;+0;!$(NC=O);!$(NS)].

Promote it from anecdote to a validated gate: apply to TDC `hERG_Karim` (binary
blocker labels), report TPR/TNR/balanced-acc/MCC for the boolean rule + AUROC of
an ordinal 0-3 "conditions met" score. Target: TPR >= 0.70 AND TNR >= 0.70.

Run (mammal env): USE_TF=0 USE_FLAX=0 \
  /opt/anaconda3/envs/mammal/bin/python experiments/herg_validate_tdc.py
Out: results/herg_validate_tdc.json
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdMolDescriptors
RDLogger.DisableLog("rdApp.*")

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "herg_validate_tdc.json"
_BASIC_N = Chem.MolFromSmarts("[N;X3;+0;!$(NC=O);!$(NS)]")


def features(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    logp = Descriptors.MolLogP(mol)
    nar = rdMolDescriptors.CalcNumAromaticRings(mol)
    bn = len(mol.GetSubstructMatches(_BASIC_N))
    cond = [logp > 3.0, bn >= 1, nar >= 2]
    return {"logp": logp, "basic_n": bn, "aromatic_rings": nar,
            "rule": all(cond), "n_cond": int(sum(cond))}


def metrics(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    tpr = tp / (tp + fn) if (tp + fn) else float("nan")
    tnr = tn / (tn + fp) if (tn + fp) else float("nan")
    denom = np.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    mcc = ((tp*tn - fp*fn) / denom) if denom else float("nan")
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "TPR": tpr, "TNR": tnr,
            "balanced_acc": (tpr + tnr) / 2, "MCC": float(mcc)}


def auroc(y, score):
    y = np.asarray(y); s = np.asarray(score, float)
    pos = s[y == 1]; neg = s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Mann-Whitney U / rank AUROC
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # average ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt); avg = {}
    start = 0
    for k, c in enumerate(cnt):
        avg[k] = (start + 1 + start + c) / 2; start += c
    rank_by_val = np.array([avg[i] for i in inv])
    n_pos = int((y == 1).sum()); n_neg = int((y == 0).sum())
    sum_pos = rank_by_val[y == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def main():
    t0 = datetime.now()
    from tdc.single_pred import Tox
    print("loading TDC hERG_Karim ...", flush=True)
    df = Tox(name="hERG_Karim").get_data()
    print(f"  {len(df)} rows; label balance: {df['Y'].value_counts().to_dict()}", flush=True)

    rows = []
    for smi, y in zip(df["Drug"], df["Y"]):
        f = features(smi)
        if f is None:
            continue
        rows.append({**f, "y": int(y)})
    print(f"  {len(rows)} valid molecules", flush=True)

    y = [r["y"] for r in rows]
    pred = [1 if r["rule"] else 0 for r in rows]
    ncond = [r["n_cond"] for r in rows]
    logp = [r["logp"] for r in rows]

    # TDC hERG_Karim: Y=1 is a hERG BLOCKER (the "toxic"/positive class)
    m = metrics(y, pred)
    result = {
        "test": "herg_rule_validation_tdc_hERG_Karim",
        "timestamp": t0.isoformat(),
        "rule": "(MolLogP>3.0) AND (basic_N>=1) AND (aromatic_rings>=2)",
        "n_valid": len(rows),
        "label_note": "Y=1 = hERG blocker (positive). TPR = blocker sensitivity.",
        "boolean_rule": m,
        "auroc_ordinal_0to3_conditions": auroc(y, ncond),
        "auroc_logp_alone": auroc(y, logp),
        "target": "TPR>=0.70 AND TNR>=0.70",
        "verdict": ("PASS" if (m["TPR"] >= 0.70 and m["TNR"] >= 0.70)
                    else f"PARTIAL (TPR {m['TPR']:.2f}, TNR {m['TNR']:.2f})"),
    }
    OUT.write_text(json.dumps(result, indent=2))
    print("\n=== hERG rule on TDC hERG_Karim ===", flush=True)
    print(f"  n={len(rows)}  TPR={m['TPR']:.3f} TNR={m['TNR']:.3f} "
          f"bal_acc={m['balanced_acc']:.3f} MCC={m['MCC']:.3f}", flush=True)
    print(f"  AUROC(0-3 ordinal)={result['auroc_ordinal_0to3_conditions']:.3f}  "
          f"AUROC(logP)={result['auroc_logp_alone']:.3f}", flush=True)
    print(f"  VERDICT: {result['verdict']}", flush=True)
    print(f"  Saved -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)


if __name__ == "__main__":
    main()
