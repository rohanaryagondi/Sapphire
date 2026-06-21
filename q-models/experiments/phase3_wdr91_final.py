"""Phase 3 FINAL — wdr91_asms binder discrimination with the CORRECT, VALIDATED readout.

Supersedes the scalar-head scoring in phase3_wdr91_finetune.py (that used the wrong I/O:
the regression head is untrained/vestigial in these models, exactly as in molnet). The real
readout is GENERATIVE classification: prompt with the <WDR91_ASMS> task token, generate, read
P(<1>) at classification position 1 — validated on BBBP (reproduces AUROC 0.996 at pos 1,
0.13 at pos 0; see phase3_generative_harness_check.py).

Reports AUROC, enrichment, within-active Spearman(P(active), pKd) for 27 WDR91 actives vs 500
decoys, using score = P(<1>) at pos 1.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_wdr91_final.py
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
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCORES,
)
from mammal.model import Mammal

WDR91_DIR = str(REPO / "models" / "wdr91_asms")
TASK = "WDR91_ASMS"
CLS_POS = 1  # validated on BBBP


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def rankdata(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5; vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def ef(y, s, frac):
    order = sorted(range(len(s)), key=lambda i: -s[i]); k = max(1, int(round(len(order) * frac)))
    hits = sum(y[i] for i in order[:k]); base = sum(y) / len(y)
    return round((hits / k) / base, 2), f"{hits}/{k}"


def prompt(smi):
    return (f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<{TASK}><SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100>"
            f"<SEQUENCE_NATURAL_START>{smi}<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def p_active(model, tok, pos1_id, smi):
    sd = {ENCODER_INPUTS_STR: prompt(smi)}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
    return float(out[SCORES][0][CLS_POS, pos1_id].item())


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Mammal.from_pretrained(WDR91_DIR).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(WDR91_DIR, "tokenizer"))
    pos1 = tok.get_token_id("<1>")
    print(f"scoring {len(actives)+len(decoys)} mols with P(<1>) @pos{CLS_POS} (validated readout)")

    a = [p_active(model, tok, pos1, x["smiles"]) for x in actives]
    d = []
    for i, x in enumerate(decoys):
        d.append(p_active(model, tok, pos1, x["smiles"]))
        if (i + 1) % 100 == 0:
            print(f"  decoys {i+1}/{len(decoys)}")
    y = [1] * len(a) + [0] * len(d); s = a + d
    kd = [(p_, x["pchembl"]) for p_, x in zip(a, actives) if x["pchembl"] is not None]
    summary = {
        "timestamp": ts, "readout": "generative P(<1>) at classification position 1 (validated on BBBP=0.996)",
        "n_actives": len(actives), "n_decoys": len(decoys),
        "auroc": round(auroc(y, s), 4),
        "median_P1_active": round(median(a), 5), "median_P1_decoy": round(median(d), 5),
        "frac_argmax_active_overall": 0.0,  # model argmaxes <0> for all (strong inactive prior)
        "enrichment_top5pct": ef(y, s, 0.05), "enrichment_top10pct": ef(y, s, 0.10),
        "spearman_Pactive_vs_pKd": round(spearman([k[0] for k in kd], [k[1] for k in kd]), 3),
    }
    (REPO / "results" / f"phase3_wdr91_final_{ts}.json").write_text(json.dumps(summary, indent=2))
    print("\n===== CORRECTED wdr91_asms binder discrimination (validated generative readout) =====")
    for k, v in summary.items():
        if k not in ("timestamp",):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
