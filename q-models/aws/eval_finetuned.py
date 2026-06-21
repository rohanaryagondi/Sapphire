#!/usr/bin/env python
"""Evaluate a fine-tuned MAMMAL head on its held-out set via the generative P(<1>) readout.

Usage: eval_finetuned.py {bbbp|pgk2} <finetune_output_dir> [ckpt_filename]
Robust for unattended runs: per-sample try/except, shape-safe score extraction,
saves raw per-sample predictions for post-hoc recompute. Reports AUROC + top-5/10% enrichment.
"""
import os, sys, json, time
os.environ["USE_TF"] = "0"; os.environ["USE_FLAX"] = "0"; os.environ["HF_HUB_DISABLE_XET"] = "1"
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score
from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.examples.carcinogenicity.task import CarcinogenicityTask
from mammal.keys import SCORES
from mammal.model import Mammal

DS = sys.argv[1]
FT_DIR = sys.argv[2]
CKPT = sys.argv[3] if len(sys.argv) > 3 else "best_epoch.ckpt"
if not os.path.isabs(CKPT):
    CKPT = os.path.join(FT_DIR, CKPT)
device = "cuda" if torch.cuda.is_available() else "cpu"
W = "/mnt/rohan/mammal_ft"


def eval_set():
    if DS == "bbbp":
        from tdc.single_pred import ADME
        df = ADME(name="BBB_Martins").get_split(method="scaffold")["test"]
        return df["Drug"].tolist(), df["Y"].astype(int).tolist()
    else:
        df = pd.read_csv(f"{W}/data/pgk2_binder_val.csv")
        return df["Drug"].tolist(), df["label"].astype(int).tolist()


def main():
    print(f"[eval {DS}] ckpt={CKPT} device={device}")
    tok = ModularTokenizerOp.from_pretrained(os.path.join(FT_DIR, "tokenizer"))
    model = Mammal.from_pretrained(pretrained_model_name_or_path=CKPT)
    model.eval().to(device)
    id1 = tok.get_token_id("<1>"); id0 = tok.get_token_id("<0>")

    smiles, labels = eval_set()
    probs, raw = [], []
    t0 = time.time()
    with torch.no_grad():
        for i, smi in enumerate(smiles):
            try:
                sd = CarcinogenicityTask.data_preprocessing(
                    sample_dict={"drug_seq": smi}, sequence_key="drug_seq",
                    tokenizer_op=tok, device=model.device,
                )
                bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=2)
                t = torch.as_tensor(bd[SCORES][0]).float()
                while t.dim() > 1:          # peel batch/step dims -> [vocab]
                    t = t[0]
                pr = t.softmax(-1)
                p = (pr[id1] / (pr[id1] + pr[id0] + 1e-9)).item()
            except Exception as e:
                if i < 3:
                    print(f"[warn] sample {i} failed: {type(e).__name__}: {e}")
                p = float("nan")
            probs.append(p)
            raw.append({"p1": p, "label": int(labels[i])})
            if i == 0:
                print(f"[debug] first sample P(<1>)={p} label={labels[0]}")
    dt = time.time() - t0

    json.dump(raw, open(f"{W}/eval_{DS}_raw.json", "w"))  # for post-hoc recompute
    probs = np.array(probs); labels = np.array(labels)
    mask = ~np.isnan(probs)
    p_ok, l_ok = probs[mask], labels[mask]
    auroc = roc_auc_score(l_ok, p_ok) if len(set(l_ok.tolist())) > 1 else float("nan")
    order = np.argsort(-p_ok); n = len(l_ok); base = l_ok.mean()
    def ef(frac):
        k = max(1, int(n * frac))
        return float(l_ok[order[:k]].mean() / base) if base > 0 else float("nan")
    out = {
        "dataset": DS, "ckpt": os.path.basename(CKPT), "n_total": int(len(probs)),
        "n_scored": int(n), "pos_rate": float(base), "AUROC": float(auroc),
        "enrichment_top5pct": ef(0.05), "enrichment_top10pct": ef(0.10),
        "sec_per_cpd": dt / max(1, len(probs)),
    }
    print("RESULT " + json.dumps(out))
    json.dump(out, open(f"{W}/eval_{DS}.json", "w"), indent=2)


if __name__ == "__main__":
    main()
