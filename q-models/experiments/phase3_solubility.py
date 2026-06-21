"""Phase 3 — test MAMMAL's protein_solubility head on its OWN benchmark (DeepSol test set).

This is the one public MAMMAL paper-benchmark head we hadn't tested. Assumes the published
checkpoint IS the model used for the paper's solubility benchmark, and reproduces the number.

Task: binary protein solubility (soluble=1 / insoluble=0) from AA sequence. Generative readout
(prompt <SOLUBILITY><SENTINEL_ID_0> -> generate -> P(<1>) at class position 1), exactly as
mammal.examples.protein_solubility. Benchmark: DeepSol (Khurana et al. 2018, Bioinformatics;
data Zenodo 1162886) test fold = 1999 proteins. We reuse the example's data loader + I/O verbatim.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_solubility.py [N]   # N=sample size, default all
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
from datetime import datetime
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.examples.protein_solubility.pl_data_module import load_datasets
from mammal.examples.protein_solubility.task import ProteinSolubilityTask
from mammal.keys import CLS_PRED, SCORES
from mammal.model import Mammal

SOL_DIR = str(REPO / "models" / "protein_solubility")


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


@torch.no_grad()
def predict(model, tok, seq):
    sd = ProteinSolubilityTask.data_preprocessing(
        sample_dict={"protein_seq": seq}, protein_sequence_key="protein_seq",
        tokenizer_op=tok, device=model.device)
    bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
    ans = ProteinSolubilityTask.process_model_output(
        tokenizer_op=tok, decoder_output=bd[CLS_PRED][0], decoder_output_scores=bd[SCORES][0])
    return ans  # dict(pred, not_normalized_scores, normalized_scores)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ds = load_datasets(str(REPO / "data" / "solubility"))["test"]
    idxs = list(range(len(ds)))
    if n:
        idxs = idxs[:: max(1, len(ds) // n)][:n]  # even stride subsample
    print(f"DeepSol test: scoring {len(idxs)} / {len(ds)} proteins")

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Mammal.from_pretrained(SOL_DIR).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(SOL_DIR, "tokenizer"))

    y, pred, score, n_err = [], [], [], 0
    for k, i in enumerate(idxs):
        s = ds[i]
        seq = s["data.protein"]; lab = int(s["data.label"])
        try:
            a = predict(model, tok, seq)
        except Exception:
            n_err += 1; continue
        if a is None:
            n_err += 1; continue
        y.append(lab); pred.append(a["pred"])
        score.append(float(a["normalized_scores"]))
        if (k + 1) % 200 == 0:
            print(f"  {k+1}/{len(idxs)}")

    acc = sum(int(p == t) for p, t in zip(pred, y)) / len(y)
    roc = auroc(y, score)
    pos_rate = sum(y) / len(y)
    summary = {"timestamp": ts, "benchmark": "DeepSol test (Khurana 2018, Zenodo 1162886)",
               "n_scored": len(y), "n_errors": n_err, "pos_rate": round(pos_rate, 3),
               "accuracy": round(acc, 4), "auroc": round(roc, 4),
               "paper_deepsol_acc": 0.77, "note": "DeepSol paper reports ~0.77 test accuracy"}
    (REPO / "results" / f"phase3_solubility_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\n===== protein_solubility on DeepSol test =====")
    print(f"  n={len(y)} (pos rate {pos_rate:.2f}) errors={n_err}")
    print(f"  accuracy = {acc:.4f}")
    print(f"  AUROC    = {roc:.4f}")
    print(f"  (DeepSol paper baseline ~0.77 acc; compare to MAMMAL paper's reported solubility number)")


if __name__ == "__main__":
    main()
