"""Phase 3 probe — reverse-engineer the I/O of the UNDOCUMENTED wdr91_asms head.

`michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.wdr91_asms` is MAMMAL fine-tuned
on WDR91 affinity-selection-MS hit data to SCORE candidate molecules for that one
target. No model card, no example code. Its config.json is IDENTICAL to the DTI
head (scalars_prediction_head {layers:[], num_classes:1}, support_input_scalars True,
encoder_head_layers [2048,1024]) -> it's a single-scalar regression head like DTI,
but target-specific so the input should be SMILES-only (no protein).

This probe verifies, before we trust anything:
  1. the model loads,
  2. a SMILES-only DTI-style prompt runs through forward_encoder_only,
  3. the scalar head (model.out.scalars_prediction_logits[:, 0], the <MASK> slot)
     returns FINITE, VARYING scores across diverse molecules,
  4. an early sniff test: do a couple known WDR91 actives outscore trivial/random ones?

For RANKING (actives vs decoys) the unknown train-time norm constants are irrelevant:
score = raw[:,0]*std+mean is monotonic, so AUROC/Spearman are invariant. We use raw[:,0].
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_SCALARS,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCALARS_PREDICTION_HEAD_LOGITS,
)
from mammal.model import Mammal

WDR91_DIR = str(REPO / "models" / "wdr91_asms")


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def build_prompt(smiles: str, drug_max_len: int = 256) -> str:
    """SMILES-only analogue of DtiBindingdbKdTask.data_preprocessing's encoder string.

    DTI builds: <AA><MASK>  <AA MAX-LEN=1250>protein...  <SMILES MAX-LEN=256>drug...  <EOS>
    The leading <MASK> is the scalar-prediction slot (position 0) the scalar head reads.
    For a target-specific head the protein is baked into the weights, so we drop the
    protein block and keep <MASK> + the small-molecule block.
    """
    return (
        "<@TOKENIZER-TYPE=AA><MASK>"
        f"<@TOKENIZER-TYPE=SMILES@MAX-LEN={drug_max_len}>"
        "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END>"
        "<EOS>"
    )


@torch.no_grad()
def raw_scalar(model, tok, smiles: str, dump_positions: bool = False):
    sd = {ENCODER_INPUTS_STR: build_prompt(smiles), "data.sample_id": 0}
    tok(
        sample_dict=sd,
        key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
        key_out_scalars=ENCODER_INPUTS_SCALARS,
    )
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(
        sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device
    )
    out = model.forward_encoder_only([sd])
    scal = out[SCALARS_PREDICTION_HEAD_LOGITS]  # (1, L)
    pos0 = float(scal[0, 0].item())
    if dump_positions:
        v = scal[0].float()
        return pos0, dict(n_tokens=int(v.numel()), min=float(v.min()), max=float(v.max()),
                          mean=float(v.mean()))
    return pos0


# a couple strong WDR91 actives (oxetane / 4-Cl-phenyl benzamide series, pKd 5.22),
# plus trivial / random molecules that should NOT look like WDR91 binders.
PROBE = [
    ("WDR91 active CHEMBL5416881 pKd5.22", "O=C(NC1(c2ccc(Cl)cc2)COC1)c1ccc(N2CCC(O)CC2)cc1"),
    ("WDR91 active CHEMBL5423537 pKd5.22", "O=C(NC1(c2ccc(Cl)cc2)COC1)c1ccc(N2CCC(O)C2)cc1"),
    ("aspirin",   "CC(=O)Oc1ccccc1C(=O)O"),
    ("caffeine",  "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("ethanol",   "CCO"),
    ("benzene",   "c1ccccc1"),
]


def main():
    dev = pick_device()
    print(f"loading wdr91_asms from {WDR91_DIR} on {dev} ...")
    model = Mammal.from_pretrained(WDR91_DIR).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(WDR91_DIR, "tokenizer"))
    print("loaded. encoder_head:", model.encoder_head is not None,
          "| scalars_prediction_head:", model.scalars_prediction_head is not None,
          "| project_input_scalars:", model.project_input_scalars is not None)
    print()

    scores = []
    for i, (name, smi) in enumerate(PROBE):
        pos0, stats = raw_scalar(model, tok, smi, dump_positions=True)
        scores.append(pos0)
        print(f"  {name:38s} pos0={pos0:+.4f}   [L={stats['n_tokens']} "
              f"min={stats['min']:+.3f} max={stats['max']:+.3f} mean={stats['mean']:+.3f}]")

    finite = all(torch.isfinite(torch.tensor(scores)))
    varying = (max(scores) - min(scores)) > 1e-4
    print()
    print(f"finite: {finite} | varying: {varying} | range=[{min(scores):+.4f}, {max(scores):+.4f}]")
    act = scores[:2]
    other = scores[2:]
    print(f"mean(2 WDR91 actives)={sum(act)/len(act):+.4f}  vs  mean(4 non-binders)={sum(other)/len(other):+.4f}")
    if not (finite and varying):
        print("\nWARNING: output not finite/varying -> I/O reverse-engineering is wrong; "
              "do NOT proceed to scoring. Try: (a) reading a different scalar position, "
              "(b) including the WDR91 protein sequence in the prompt.")


if __name__ == "__main__":
    main()
