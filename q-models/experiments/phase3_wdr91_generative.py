"""Phase 3 (CORRECTED I/O) — wdr91_asms is a GENERATIVE classification task, not regression.

The tokenizer carries task tokens new vs base: <WDR91_ASMS>, <PGK2_ASMS>, <PGK2_DEL>,
plus <ACTIVE>/<ISACTIVE>/<BINDING>/<BINDING_AFFINITY_CLASS>/<REGRESSION>. And the weight
profile (encoder body moved ~0.02, all readout heads ~base) matches the WORKING molnet/TCR
classifiers, which read out via model.generate() (decoder path), NOT the scalar head.

So the correct readout is molnet-style: prompt the small molecule with the <WDR91_ASMS> task
token + <SENTINEL_ID_0>, generate, and read the probability of the "active/positive" answer
token at the classification position. This script (1) dumps what tokens the model actually
emits for a few actives/decoys, and (2) scores all 27 actives + 500 decoys under each plausible
answer token and reports AUROC.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_wdr91_generative.py
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
    CLS_PRED,
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCORES,
)
from mammal.model import Mammal

WDR91_DIR = str(REPO / "models" / "wdr91_asms")
TASK = "WDR91_ASMS"
# candidate "this molecule is a binder" answer tokens to probe
CAND = ["<1>", "<0>", "<ACTIVE>", "<ISACTIVE>", "<BINDING>"]


def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def prompt(smiles):
    # molnet-style, with the per-target task token
    return (f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<{TASK}><SENTINEL_ID_0>"
            f"<@TOKENIZER-TYPE=SMILES@MAX-LEN=2100><SEQUENCE_NATURAL_START>{smiles}"
            f"<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def generate_scores(model, tok, smiles):
    sd = {ENCODER_INPUTS_STR: prompt(smiles)}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
    return out[CLS_PRED][0], out[SCORES][0]  # token ids (gen_len,), softmax scores (gen_len, vocab)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Mammal.from_pretrained(WDR91_DIR).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(WDR91_DIR, "tokenizer"))

    cand_ids = {}
    for t in CAND:
        try:
            cand_ids[t] = tok.get_token_id(t)
        except Exception:
            pass
    print("candidate answer token ids:", cand_ids)

    # inverse map for displaying emitted tokens (candidates + common structural tokens)
    id2tok = {v: k for k, v in cand_ids.items()}
    for t in ["<SENTINEL_ID_0>", "<EOS>", "<PAD>", "<SEQUENCE_NATURAL_START>",
              "<SEQUENCE_NATURAL_END>", "<REGRESSION>", "<BINDING_AFFINITY_CLASS>",
              "<GENERAL_AFFINITY_CLASS>", "<CLS>", "<MASK>"]:
        try:
            id2tok[tok.get_token_id(t)] = t
        except Exception:
            pass

    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))

    # 1) exploration: what does it actually emit?
    print("\n--- generated tokens (pos 0..3 argmax) for 3 actives then 3 decoys ---")
    for label, mol in ([("ACT", a) for a in actives[:3]] + [("DEC", d) for d in decoys[:3]]):
        cls, sc = generate_scores(model, tok, mol["smiles"])
        toks = [id2tok.get(int(cls[i]), f"id{int(cls[i])}") if i < len(cls) else "-" for i in range(min(4, len(cls)))]
        probs = {t: round(float(sc[1, i].item()), 4) for t, i in cand_ids.items()}  # pos 1
        print(f"  {label} {mol['molecule_chembl_id']:14s} emit={toks}  P@pos1={probs}")

    # 2) full scoring under each candidate token at classification positions 0 and 1
    print("\n--- scoring all actives + decoys ---")
    rows = {f"{t}@{pos}": {"act": [], "dec": []} for t in cand_ids for pos in (0, 1)}
    for grp, mols in (("act", actives), ("dec", decoys)):
        for i, m in enumerate(mols):
            _, sc = generate_scores(model, tok, m["smiles"])
            for t, tid in cand_ids.items():
                for pos in (0, 1):
                    rows[f"{t}@{pos}"][grp].append(float(sc[pos, tid].item()) if pos < sc.shape[0] else 0.0)
            if grp == "dec" and (i + 1) % 100 == 0:
                print(f"  decoys {i+1}/{len(decoys)}")

    print("\n===== AUROC by candidate answer token / position =====")
    results = {}
    for key, d in rows.items():
        y = [1] * len(d["act"]) + [0] * len(d["dec"])
        roc = auroc(y, d["act"] + d["dec"])
        results[key] = round(roc, 4)
        print(f"  P({key:14s}) : AUROC {roc:.4f}  (flip {1-roc:.4f})")

    best = max(results.items(), key=lambda kv: max(kv[1], 1 - kv[1]))
    print(f"\nbest: {best[0]} AUROC={best[1]} (flip {round(1-best[1],4)})")
    out = REPO / "results" / f"phase3_wdr91_generative_{ts}.json"
    out.write_text(json.dumps({"timestamp": ts, "task_token": TASK,
                               "candidate_ids": cand_ids, "auroc": results,
                               "best": {"readout": best[0], "auroc": best[1]}}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
