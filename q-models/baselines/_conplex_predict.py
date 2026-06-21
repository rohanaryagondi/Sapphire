"""Standalone ConPLex predict driver — runs INSIDE the `conplex` conda env.

ConPLex's own CLI (`conplex-dti predict`) routes through conplex_dti.cli.__init__,
which eagerly imports cli.train → tdc (PyTDC) + wandb + pytorch_lightning. Those
training-only deps are heavy and pin-conflicting, so we deliberately did NOT install
them. This driver reproduces the ~20 lines of cli/predict.py's `main`, importing
ONLY the clean predict-path modules (featurizer / model / utils) — no cli, no train,
no tdc/wandb. Input/output formats match the original exactly.

Usage (called by baselines/conplex.py via subprocess):
  python _conplex_predict.py --data-file pairs.tsv --model-path X.pt --outfile preds.tsv \
                             --data-cache-dir <dir> --device cpu
Input TSV  (no header): proteinID  moleculeID  proteinSequence  moleculeSmiles
Output TSV (no header): moleculeID  proteinID  Prediction
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from conplex_dti.featurizer import MorganFeaturizer, ProtBertFeaturizer
from conplex_dti.model.architectures import SimpleCoembeddingNoSigmoid
from conplex_dti.utils import set_random_seed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-file", required=True)
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--outfile", required=True)
    ap.add_argument("--data-cache-dir", default=".")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--random-seed", type=int, default=61998)
    args = ap.parse_args()

    set_random_seed(args.random_seed)
    device = torch.device("cpu") if args.device == "cpu" else torch.device(
        f"cuda:{args.device}" if torch.cuda.is_available() else "cpu")

    df = pd.read_csv(args.data_file, sep="\t",
                     names=["proteinID", "moleculeID", "proteinSequence", "moleculeSmiles"])

    target_feat = ProtBertFeaturizer(save_dir=args.data_cache_dir, per_tok=False).to(device)
    drug_feat = MorganFeaturizer(save_dir=args.data_cache_dir).to(device)
    drug_feat.preload(df["moleculeSmiles"].unique())
    target_feat.preload(df["proteinSequence"].unique())

    model = SimpleCoembeddingNoSigmoid(drug_feat.shape, target_feat.shape, 1024)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model = model.eval().to(device)

    pairs = [(drug_feat(r["moleculeSmiles"]), target_feat(r["proteinSequence"]))
             for _, r in df.iterrows()]
    loader = DataLoader(pairs, batch_size=args.batch_size, shuffle=False)

    preds = []
    with torch.set_grad_enabled(False):
        for b in loader:
            preds.append(model(b[0], b[1]).detach().cpu().numpy())
    preds = np.concatenate(preds)

    out = pd.DataFrame(df[["moleculeID", "proteinID"]])
    out["Prediction"] = preds
    out.to_csv(args.outfile, sep="\t", index=False, header=False)


if __name__ == "__main__":
    main()
