"""Validate the generative classification harness on a KNOWN-good model (BBBP, AUROC ~0.968).

Confirms which decoder position is the real classification readout (IBM's molnet_infer uses
classification_position=1) before we trust the wdr91 generative number. If P(<1>) at pos 1
reproduces a high BBBP AUROC, position 1 is the legit readout and the wdr91 ~0.63 stands;
if pos 0 is the one that reproduces it, we'd revisit.
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import csv
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.keys import (
    CLS_PRED,
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCORES,
)
from mammal.model import Mammal

BBBP_DIR = str(REPO / "models" / "moleculenet_bbbp")


def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def prompt(smiles, task="BBBP"):
    return (f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<{task}><SENTINEL_ID_0>"
            f"<@TOKENIZER-TYPE=SMILES@MAX-LEN=2100><SEQUENCE_NATURAL_START>{smiles}"
            f"<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def score(model, tok, smiles, pos_id):
    sd = {ENCODER_INPUTS_STR: prompt(smiles)}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
    sc = out[SCORES][0]
    return float(sc[0, pos_id].item()), float(sc[1, pos_id].item()) if sc.shape[0] > 1 else 0.0


def main():
    rows = list(csv.DictReader(open("/tmp/BBBP.csv")))
    # deterministic mixed sample: take 150 pos + 150 neg spread through the file
    pos = [r for r in rows if int(float(r["p_np"])) == 1]
    neg = [r for r in rows if int(float(r["p_np"])) == 0]
    sample = pos[::max(1, len(pos)//150)][:150] + neg[::max(1, len(neg)//150)][:150]
    print(f"BBBP sample: {len(sample)} mols ({sum(int(float(r['p_np'])) for r in sample)} pos)")

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Mammal.from_pretrained(BBBP_DIR).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(BBBP_DIR, "tokenizer"))
    pos1_id = tok.get_token_id("<1>")

    y, p0, p1, n_err = [], [], [], 0
    for i, r in enumerate(sample):
        try:
            a, b = score(model, tok, r["smiles"], pos1_id)
        except Exception:
            n_err += 1; continue
        y.append(int(float(r["p_np"]))); p0.append(a); p1.append(b)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(sample)}")
    print(f"\nP(<1>) @pos0 AUROC = {auroc(y,p0):.4f}")
    print(f"P(<1>) @pos1 AUROC = {auroc(y,p1):.4f}   <- molnet's classification_position (paper 0.957/our 0.968)")
    print(f"(n={len(y)}, errors={n_err}) -- the position that reproduces ~0.95 is the legit readout")


if __name__ == "__main__":
    main()
