"""Phase 1 — in-distribution control: does the DTI head work on its OWN benchmark?

This is the control that distinguishes "broken model/pipeline" from "doesn't
transfer to our pairs". We sample real pairs from TDC's BindingDB_Kd test split
(the exact benchmark MAMMAL's dti_bindingdb_pkd head was finetuned on) and check
whether predicted pKd ranks with experimental pKd.

If this correlates (it does: Spearman ~0.6) but our Quiver-relevant pairs do not,
the failure is domain transfer, not a bug.

TDC Y is Kd in nM -> pKd = 9 - log10(Kd_nM).

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1_indistribution_check.py [n_samples]
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import math
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

from mammal_quiver.dti import DTI_MODEL_ID, load_dti_model, predict_pkd  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20


def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x) ** 0.5
    vy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for rk, i in enumerate(o):
            r[i] = rk
        return r
    return pearson(rank(x), rank(y))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from tdc.multi_pred import DTI

    test = DTI(name="BindingDB_Kd").get_split()["test"]
    df = test.dropna(subset=["Y"]).copy()
    df = df[df["Y"] > 0]
    df["pkd"] = 9.0 - df["Y"].apply(math.log10)
    df = df.sort_values("pkd")
    idx = list(range(0, len(df), max(1, len(df) // N)))[:N]
    sample = df.iloc[idx]
    print(f"BindingDB_Kd test pairs={len(df)}; sampling {len(sample)} across "
          f"pKd [{df.pkd.min():.2f},{df.pkd.max():.2f}]")

    model, tok, dev = load_dti_model()
    rows, exp, pred = [], [], []
    for _, r in sample.iterrows():
        try:
            p = predict_pkd(model, tok, r["Target"], r["Drug"])
        except Exception as e:
            print(f"  skip: {e}"); continue
        exp.append(r["pkd"]); pred.append(p)
        rows.append({"exp_pkd": round(r["pkd"], 3), "pred_pkd": round(p, 3)})
        print(f"  exp={r['pkd']:.2f}  pred={p:.2f}")

    rho, rp = spearman(exp, pred), pearson(exp, pred)
    summary = {"timestamp": ts, "model": DTI_MODEL_ID, "device": dev, "n": len(exp),
               "spearman": round(rho, 4), "pearson": round(rp, 4),
               "pred_range": [round(min(pred), 3), round(max(pred), 3)],
               "exp_range": [round(min(exp), 3), round(max(exp), 3)], "rows": rows}
    out = REPO / "results" / f"phase1_indistribution_{ts}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nIN-DISTRIBUTION: n={len(exp)} Spearman={rho:.3f} Pearson={rp:.3f}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
