"""Target-specific binder scoring with IBM's fine-tuned per-target heads (WDR91 / PGK2).

`michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.{wdr91_asms,pgk2_del_cdd}` — MAMMAL
fine-tuned on a single target's experimental hit data (ASMS = affinity-selection MS;
DEL = DNA-encoded library) to classify candidate molecules as binders for that one target.
Undocumented (no card / no example), so the I/O was reverse-engineered + validated here.

CORRECT I/O (validated): these are **generative binary classifiers**, NOT scalar regressors.
The tokenizer carries dedicated task tokens new vs base — `<WDR91_ASMS>`, `<PGK2_ASMS>`,
`<PGK2_DEL>` — and the trained signal lives in the encoder + the generative decoder path
(the `scalars_prediction_head` is untrained/vestigial here, exactly as in the MoleculeNet
classifiers). Prompt the molecule with the task token + `<SENTINEL_ID_0>`, run `model.generate`,
and read P(`<1>`) at classification position 1 — the same readout `mammal.examples.molnet`
uses. Validated against the BBBP head (reproduces AUROC 0.996 at position 1, vs 0.13 at
position 0). Higher P(`<1>`) = more binder-like.

NOTE: the model carries a strong inactive-class prior (argmax is `<0>` for nearly all inputs);
use P(`<1>`) as a soft *ranking* score, not as a hard active/inactive call.
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import torch

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    SCORES,
)
from mammal.model import Mammal

_REPO = os.path.dirname(os.path.dirname(__file__))

# (local dir, HF id, task token) for each published per-target head.
TARGETS = {
    "wdr91": ("wdr91_asms", "michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.wdr91_asms", "WDR91_ASMS"),
    "pgk2_asms": ("pgk2_del_cdd", "michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.pgk2_del_cdd", "PGK2_ASMS"),
    "pgk2_del": ("pgk2_del_cdd", "michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.pgk2_del_cdd", "PGK2_DEL"),
}
_CLS_POS = 1  # validated classification position (molnet convention)


def pick_device(prefer: str | None = None) -> str:
    if prefer:
        return prefer
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_target_model(target: str = "wdr91", device: str | None = None):
    """Load a per-target binder classifier. Returns (model, tokenizer_op, task_token, device)."""
    local_name, hub_id, task = TARGETS[target]
    local = os.path.join(_REPO, "models", local_name)
    source = local if os.path.isfile(os.path.join(local, "model.safetensors")) else hub_id
    device = pick_device(device)
    model = Mammal.from_pretrained(source).to(device).eval()
    tok_path = os.path.join(source, "tokenizer") if os.path.isdir(source) else source
    tok = ModularTokenizerOp.from_pretrained(tok_path)
    return model, tok, task, device


# back-compat alias used by older experiment scripts
def load_wdr91_model(device: str | None = None, source: str | None = None):
    model, tok, _task, dev = load_target_model("wdr91", device=device)
    return model, tok, dev


def _prompt(smiles: str, task: str) -> str:
    return (f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<{task}><SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100>"
            f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def score_smiles(model, tok, smiles: str) -> float:
    """SUPERSEDED readout — the untrained scalar-prediction head at the <MASK> slot.

    Kept only so the early phase3 scripts (phase3_wdr91_finetune/diagnose) still import & run.
    This is the WRONG I/O for these models: their scalar head is untrained/vestigial, so this
    returns no binder signal (AUROC ~0.43). Use `binder_prob` (generative classifier) instead.
    """
    from mammal.keys import ENCODER_INPUTS_SCALARS, SCALARS_PREDICTION_HEAD_LOGITS
    sd = {ENCODER_INPUTS_STR: ("<@TOKENIZER-TYPE=AA><MASK><@TOKENIZER-TYPE=SMILES@MAX-LEN=256>"
                               "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
                               f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END><EOS>"),
          "data.sample_id": 0}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK, key_out_scalars=ENCODER_INPUTS_SCALARS)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.forward_encoder_only([sd])
    return float(out[SCALARS_PREDICTION_HEAD_LOGITS][0, 0].item())


@torch.no_grad()
def binder_prob(model, tok, smiles: str, task: str = "WDR91_ASMS") -> float:
    """P(binder) = P(<1>) at the classification position. Soft ranking score, higher = more binder-like."""
    pos1 = tok.get_token_id("<1>")
    sd = {ENCODER_INPUTS_STR: _prompt(smiles, task)}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
    return float(out[SCORES][0][_CLS_POS, pos1].item())
