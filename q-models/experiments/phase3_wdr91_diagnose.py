"""Phase 3 diagnostic — is the AUROC 0.43 failure REAL, or wrong I/O reverse-engineering?

The SMILES-only / position-0 readout gives AUROC 0.43 (worse than chance) for WDR91
actives vs decoys. Before concluding "fine-tuning doesn't transfer," rule out I/O error
(the project's recurring false-negative trap). We test several input/readout hypotheses
from the SAME molecules and report AUROC (and 1-AUROC, the sign-flipped reading) + the
within-active Spearman(score, pKd) for each:

  input schemes:
    smiles_only   : <MASK> + SMILES                 (target-specific assumption)
    protein_smiles: <MASK> + WDR91 protein + SMILES  (full DTI-style; head may still want target)
  scalar readouts (from model.out.scalars_prediction_logits, shape (1,L)):
    pos0   : the <MASK> slot (what DTI uses)
    eos    : last valid (non-pad) position
    mean   : masked mean over all positions
    max    : masked max over all positions

If NO (scheme, readout, sign) combination separates actives from decoys, the failure is
real. If one does, we found the correct I/O and re-run the full evaluation with it.
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
from mammal.examples.dti_bindingdb_kd.task import DtiBindingdbKdTask
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_SCALARS,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCALARS_PREDICTION_HEAD_LOGITS,
)
from mammal.model import Mammal

WDR91_DIR = str(REPO / "models" / "wdr91_asms")
N_DECOYS = 200  # subset for a fast but clear diagnostic


def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def smiles_only_prompt(smi):
    return ("<@TOKENIZER-TYPE=AA><MASK>"
            "<@TOKENIZER-TYPE=SMILES@MAX-LEN=256>"
            "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<SEQUENCE_NATURAL_START>{smi}<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def scalar_vec_smiles_only(model, tok, smi):
    sd = {ENCODER_INPUTS_STR: smiles_only_prompt(smi), "data.sample_id": 0}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK, key_out_scalars=ENCODER_INPUTS_SCALARS)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.forward_encoder_only([sd])
    scal = out[SCALARS_PREDICTION_HEAD_LOGITS][0].float()
    mask = sd[ENCODER_INPUTS_ATTENTION_MASK][0].float().to(scal.device)
    return scal, mask


@torch.no_grad()
def scalar_vec_protein_smiles(model, tok, seq, smi):
    sd = {"target_seq": seq, "drug_seq": smi, "data.sample_id": 0}
    sd = DtiBindingdbKdTask.data_preprocessing(
        sample_dict=sd, tokenizer_op=tok, target_sequence_key="target_seq",
        drug_sequence_key="drug_seq", norm_y_mean=None, norm_y_std=None, device=model.device)
    out = model.forward_encoder_only([sd])
    scal = out[SCALARS_PREDICTION_HEAD_LOGITS][0].float()
    mask = sd[ENCODER_INPUTS_ATTENTION_MASK][0].float().to(scal.device)
    return scal, mask


def readouts(scal, mask):
    valid = mask > 0
    n = int(valid.sum().item())
    return {
        "pos0": float(scal[0].item()),
        "eos": float(scal[n - 1].item()),
        "mean": float((scal * mask).sum().item() / max(n, 1)),
        "max": float(scal[valid].max().item()),
    }


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))[:N_DECOYS]
    seq = json.load(open(REPO / "data" / "wdr91" / "wdr91_sequence.json"))["sequence"]
    print(f"actives={len(actives)} decoys={len(decoys)} | WDR91 seq len={len(seq)}")

    model = Mammal.from_pretrained(WDR91_DIR).to(
        "mps" if torch.backends.mps.is_available() else "cpu").eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(WDR91_DIR, "tokenizer"))

    schemes = {"smiles_only": scalar_vec_smiles_only,
               "protein_smiles": lambda m, t, s: scalar_vec_protein_smiles(m, t, seq, s)}
    READOUTS = ["pos0", "eos", "mean", "max"]

    # collect readout values per scheme
    results = {}
    for sname, fn in schemes.items():
        print(f"\nscheme={sname} ... scoring {len(actives)+len(decoys)} molecules")
        act_vals = {r: [] for r in READOUTS}
        dec_vals = {r: [] for r in READOUTS}
        act_pkd = []
        for a in actives:
            scal, mask = fn(model, tok, a["smiles"])
            ro = readouts(scal, mask)
            for r in READOUTS:
                act_vals[r].append(ro[r])
            act_pkd.append(a["pchembl"])
        for i, d in enumerate(decoys):
            scal, mask = fn(model, tok, d["smiles"])
            ro = readouts(scal, mask)
            for r in READOUTS:
                dec_vals[r].append(ro[r])
            if (i + 1) % 100 == 0:
                print(f"  decoys {i+1}/{len(decoys)}")
        results[sname] = {"act": act_vals, "dec": dec_vals, "act_pkd": act_pkd}

    # report
    print("\n========== I/O hypothesis sweep (AUROC actives-vs-decoys) ==========")
    print(f"{'scheme':16s} {'readout':6s} {'AUROC':>7s} {'1-AUROC':>8s} {'Sp(pKd)':>8s}")
    table = []
    kd_idx = [i for i, a in enumerate(actives) if a["pchembl"] is not None]
    for sname in schemes:
        for r in READOUTS:
            a = results[sname]["act"][r]
            d = results[sname]["dec"][r]
            y = [1] * len(a) + [0] * len(d)
            roc = auroc(y, a + d)
            # within-active spearman vs pKd (measured subset)
            sp = spearman([a[i] for i in kd_idx],
                          [results[sname]["act_pkd"][i] for i in kd_idx])
            table.append((sname, r, round(roc, 3), round(1 - roc, 3), round(sp, 3)))
            print(f"{sname:16s} {r:6s} {roc:7.3f} {1-roc:8.3f} {sp:8.3f}")

    best = max(table, key=lambda t: max(t[2], t[3]))
    print(f"\nbest separation: scheme={best[0]} readout={best[1]} "
          f"AUROC={best[2]} (flip {best[3]})")
    out = REPO / "results" / f"phase3_wdr91_diagnose_{ts}.json"
    out.write_text(json.dumps(
        {"timestamp": ts, "n_actives": len(actives), "n_decoys": len(decoys),
         "table": [{"scheme": t[0], "readout": t[1], "auroc": t[2],
                    "auroc_flipped": t[3], "spearman_pKd": t[4]} for t in table],
         "best": {"scheme": best[0], "readout": best[1], "auroc": best[2], "flipped": best[3]}},
        indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
