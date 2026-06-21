"""Phase 3 — test the wdr91_asms TRAINED weights from last.ckpt.

The published model.safetensors has a scalar-prediction head BIT-IDENTICAL to the base
foundation model (untrained), while its encoder did move from base — the signature of a
broken/partial safetensors export. The real trained head should live in last.ckpt.

This script:
  1. loads last.ckpt's state_dict, confirms whether its scalar head is genuinely trained
     (differs from base) — i.e. whether the safetensors was indeed a bad export,
  2. if so, loads the model from the .ckpt and re-runs the actives-vs-decoys evaluation
     (smiles-only AND protein+smiles, position-0 readout), to see if the FINE-TUNED head
     discriminates WDR91 binders after all.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_wdr91_ckpt.py
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
from safetensors.torch import load_file

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.examples.dti_bindingdb_kd.task import DtiBindingdbKdTask
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_SCALARS,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCALARS_PREDICTION_HEAD_LOGITS,
)
from mammal.model import Mammal

WDR91_DIR = REPO / "models" / "wdr91_asms"
CKPT = str(WDR91_DIR / "last.ckpt")
HEAD_KEY = "scalars_prediction_head.classifier.0.weight"
BIAS_KEY = "scalars_prediction_head.classifier.0.bias"


def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5; vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def inspect_ckpt_head():
    """Return (trained: bool, info: dict) — is the ckpt's scalar head different from base?"""
    pl = torch.load(CKPT, map_location="cpu", weights_only=False)
    sd = pl["state_dict"]
    pref = "_model."
    sd = {(k[len(pref):] if k.startswith(pref) else k): v for k, v in sd.items()}
    base = load_file(str(REPO / "models" / "base_458m" / "model.safetensors"))
    info = {"n_keys": len(sd), "has_head": HEAD_KEY in sd}
    if HEAD_KEY not in sd:
        # maybe a different prefix; show candidate head keys
        info["head_like_keys"] = [k for k in sd if "scalar" in k.lower()][:8]
        return False, info
    hk, bk = sd[HEAD_KEY].float(), base[HEAD_KEY].float()
    info["head_allclose_base"] = bool(torch.allclose(hk, bk))
    info["head_max_abs_diff_vs_base"] = float((hk - bk).abs().max())
    info["head_norm_ckpt"] = float(hk.norm()); info["head_norm_base"] = float(bk.norm())
    info["bias_ckpt"] = float(sd[BIAS_KEY]); info["bias_base"] = float(base[BIAS_KEY])
    # encoder movement of ckpt vs base
    enc = [k for k in sd if k.startswith("t5_model.encoder") and k in base]
    num = sum((sd[k].float() - base[k].float()).pow(2).sum() for k in enc)
    den = sum(base[k].float().pow(2).sum() for k in enc)
    info["encoder_relL2_vs_base"] = float((num.sqrt() / den.sqrt()))
    trained = not info["head_allclose_base"]
    return trained, info


def prompt_smiles_only(smi):
    return ("<@TOKENIZER-TYPE=AA><MASK>"
            "<@TOKENIZER-TYPE=SMILES@MAX-LEN=256>"
            "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<SEQUENCE_NATURAL_START>{smi}<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def score_smiles_only(model, tok, smi):
    sd = {ENCODER_INPUTS_STR: prompt_smiles_only(smi), "data.sample_id": 0}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK, key_out_scalars=ENCODER_INPUTS_SCALARS)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.forward_encoder_only([sd])
    return float(out[SCALARS_PREDICTION_HEAD_LOGITS][0, 0].item())


@torch.no_grad()
def score_protein_smiles(model, tok, seq, smi):
    sd = {"target_seq": seq, "drug_seq": smi, "data.sample_id": 0}
    sd = DtiBindingdbKdTask.data_preprocessing(
        sample_dict=sd, tokenizer_op=tok, target_sequence_key="target_seq",
        drug_sequence_key="drug_seq", norm_y_mean=None, norm_y_std=None, device=model.device)
    out = model.forward_encoder_only([sd])
    return float(out[SCALARS_PREDICTION_HEAD_LOGITS][0, 0].item())


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=== Step 1: is last.ckpt's scalar head genuinely trained? ===")
    trained, info = inspect_ckpt_head()
    for k, v in info.items():
        print(f"  {k}: {v}")
    print(f"  --> ckpt head trained (differs from base): {trained}")

    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    seq = json.load(open(REPO / "data" / "wdr91" / "wdr91_sequence.json"))["sequence"]

    print("\n=== Step 2: load model FROM last.ckpt and re-score ===")
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Mammal.from_pretrained(CKPT, strict=False).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(str(WDR91_DIR / "tokenizer"))
    # confirm the LOADED model's head matches the ckpt (not silently reset)
    live_head_norm = float(model.scalars_prediction_head.classifier[0].weight.float().norm())
    print(f"  loaded on {dev}; live scalar-head weight norm = {live_head_norm:.5f}")

    summary = {"timestamp": ts, "ckpt_head_trained": trained, "ckpt_info": info,
               "live_head_norm": round(live_head_norm, 5)}

    for scheme in ("smiles_only", "protein_smiles"):
        print(f"\n  scoring scheme={scheme} ...")
        act, dec, act_pkd = [], [], []
        for a in actives:
            s = (score_smiles_only(model, tok, a["smiles"]) if scheme == "smiles_only"
                 else score_protein_smiles(model, tok, seq, a["smiles"]))
            act.append(s); act_pkd.append(a["pchembl"])
        for i, d in enumerate(decoys):
            s = (score_smiles_only(model, tok, d["smiles"]) if scheme == "smiles_only"
                 else score_protein_smiles(model, tok, seq, d["smiles"]))
            dec.append(s)
            if (i + 1) % 100 == 0:
                print(f"    decoys {i+1}/{len(decoys)}")
        y = [1] * len(act) + [0] * len(dec)
        roc = auroc(y, act + dec)
        kd_idx = [i for i, a in enumerate(actives) if a["pchembl"] is not None]
        sp = spearman([act[i] for i in kd_idx], [act_pkd[i] for i in kd_idx])
        summary[scheme] = {
            "auroc": round(roc, 4), "auroc_flipped": round(1 - roc, 4),
            "median_active": round(median(act), 4), "median_decoy": round(median(dec), 4),
            "spearman_score_vs_pKd": round(sp, 3),
        }
        print(f"    AUROC={roc:.4f} (flip {1-roc:.4f}) | median act={median(act):+.4f} "
              f"dec={median(dec):+.4f} | Spearman(score,pKd)={sp:+.3f}")

    out = REPO / "results" / f"phase3_wdr91_ckpt_{ts}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
