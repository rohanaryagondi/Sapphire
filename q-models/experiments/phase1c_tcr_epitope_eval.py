"""Phase 1c — verify the TCR-epitope binding claim (paper AUROC 0.879, Weber benchmark).

Uses the published tcr_epitope_bind head on TDC's TCREpitopeBinding('weber') test
split. task_infer returns {pred, score=P(binding)}; we compute AUROC vs the label.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/phase1c_tcr_epitope_eval.py [n]
"""

from __future__ import annotations

import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
HEAD = str(REPO / "models" / "tcr_epitope_bind")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400


def auroc(yt, ys):
    pos = [s for s, t in zip(ys, yt) if t == 1]; neg = [s for s, t in zip(ys, yt) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from tdc.multi_pred import TCREpitopeBinding
    from mammal.examples.tcr_epitope_binding.main_infer import load_model, task_infer

    test = TCREpitopeBinding(name="weber").get_split()["test"]
    # prefer the full beta chain (matches the model's TCR_BETA_VDJ prompt) over CDR3
    tcr_col = "tcr_full" if "tcr_full" in test.columns else "tcr"
    epi_col = "epitope_aa" if "epitope_aa" in test.columns else next(c for c in test.columns if "epitope" in c.lower())
    lab_col = "label" if "label" in test.columns else "Y"
    print(f"columns={list(test.columns)}  using tcr={tcr_col} epitope={epi_col} label={lab_col}")
    df = test.dropna(subset=[tcr_col, epi_col, lab_col])
    step = max(1, len(df) // N)
    df = df.iloc[::step].head(N)
    print(f"test pairs total={len(test)}; scoring {len(df)} (pos rate {df[lab_col].mean():.2f})")

    model, tok = load_model(model_path=HEAD, tokenizer_path=f"{HEAD}/tokenizer", device="mps")
    y, s, err = [], [], 0
    for k, (_, r) in enumerate(df.iterrows()):
        try:
            res = task_infer(model=model, tokenizer_op=tok, tcr_beta_seq=str(r[tcr_col]), epitope_seq=str(r[epi_col]))
        except Exception:
            err += 1; continue
        y.append(int(r[lab_col])); s.append(res["score"])
        if (k + 1) % 100 == 0:
            print(f"  ...{k+1}/{len(df)}")
    roc = auroc(y, s)
    acc = sum(int((sc >= 0.5) == bool(t)) for sc, t in zip(s, y)) / len(y)
    summary = {"timestamp": ts, "task": "tcr_epitope_bind", "dataset": "TDC TCREpitopeBinding/weber",
               "n_scored": len(y), "errors": err, "auroc": round(roc, 4), "acc@0.5": round(acc, 4),
               "paper_auroc": 0.879}
    (REPO / "results" / f"phase1c_tcr_epitope_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\nTCR-epitope (Weber) AUROC={roc:.3f} acc@0.5={acc:.3f}  (paper 0.879)")


if __name__ == "__main__":
    main()
