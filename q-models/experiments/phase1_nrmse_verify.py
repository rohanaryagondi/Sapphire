"""Verify the paper's DTI 'SOTA' claim and our loading/querying are consistent.

Paper reports NRMSE 0.906 on the PEER BindingDB holdout. NRMSE = RMSE / std(y),
so the constant mean-predictor scores exactly 1.0; NRMSE 0.906 => R^2 ~ 0.18 =>
implied correlation ~ 0.42. We compute NRMSE + Pearson + Spearman on a real
BindingDB_Kd test sample (TDC) for BOTH checkpoints, to confirm:
  (a) our pipeline produces paper-consistent NRMSE (~0.8-0.9), i.e. loading/querying is right;
  (b) 'SOTA' here is a barely-better-than-mean regime, which matches our modest correlations.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1_nrmse_verify.py [n]
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 150

CHECKPOINTS = [
    ("cold_split", str(REPO / "models" / "dti_bindingdb_pkd"), 5.79384684128215, 1.33808027428196),
    ("PEER", str(REPO / "models" / "dti_bindingdb_pkd_peer"), 6.286291085593906, 1.5422950906208512),
]


def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x) ** 0.5
    vy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for k, i in enumerate(o): r[i] = k
        return r
    return pearson(rank(x), rank(y))


def std(v):
    n = len(v); m = sum(v) / n
    return (sum((a - m) ** 2 for a in v) / n) ** 0.5


def main():
    from tdc.multi_pred import DTI
    test = DTI(name="BindingDB_Kd").get_split()["test"]
    df = test.dropna(subset=["Y"]).copy()
    df = df[df["Y"] > 0]
    df["pkd"] = 9.0 - df["Y"].apply(math.log10)
    df = df.sort_values("pkd")
    idx = list(range(0, len(df), max(1, len(df) // N)))[:N]
    sample = df.iloc[idx]
    targets = [r["Target"] for _, r in sample.iterrows()]
    drugs = [r["Drug"] for _, r in sample.iterrows()]
    exp = [r["pkd"] for _, r in sample.iterrows()]
    sy = std(exp)
    print(f"BindingDB_Kd test sample n={len(exp)}  exp pKd std={sy:.3f}  "
          f"range [{min(exp):.2f},{max(exp):.2f}]")
    print("(constant mean-predictor => NRMSE=1.000 by definition)\n")

    for name, src, mean, sd in CHECKPOINTS:
        model, tok, dev = load_dti_model(source=src)
        preds = [predict_pkd(model, tok, t, d, norm_y_mean=mean, norm_y_std=sd)
                 for t, d in zip(targets, drugs)]
        rmse = (sum((p - e) ** 2 for p, e in zip(preds, exp)) / len(exp)) ** 0.5
        nrmse = rmse / sy
        r = pearson(exp, preds); rho = spearman(exp, preds)
        print(f"[{name:10s}] NRMSE={nrmse:.3f}  RMSE={rmse:.3f}  Pearson={r:.3f}  "
              f"Spearman={rho:.3f}  pred_range=[{min(preds):.2f},{max(preds):.2f}]")
        del model

    print("\nReference: paper PEER-holdout NRMSE=0.906 => R^2~0.18 => implied r~0.42.")


if __name__ == "__main__":
    main()
