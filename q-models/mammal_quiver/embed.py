"""Extract compound (or protein) embeddings from the base MAMMAL model.

Used for the Phase 2a hit-list expansion step: embed SMILES, find nearest
neighbors. Embedding = masked mean-pool of the encoder's last hidden state
(768-d), L2-normalized.
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
)
from mammal.model import Mammal

_REPO = os.path.dirname(os.path.dirname(__file__))
_LOCAL_BASE = os.path.join(_REPO, "models", "base_458m")
BASE_SOURCE = _LOCAL_BASE if os.path.isfile(os.path.join(_LOCAL_BASE, "model.safetensors")) \
    else "ibm/biomed.omics.bl.sm.ma-ted-458m"

_HID = "model.out.encoder_last_hidden_state"
_MASK = "data.encoder_input_attention_mask"


def pick_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_base_model(device: str | None = None):
    device = device or pick_device()
    model = Mammal.from_pretrained(BASE_SOURCE).to(device).eval()
    tok_path = os.path.join(BASE_SOURCE, "tokenizer") if os.path.isdir(BASE_SOURCE) else BASE_SOURCE
    tok = ModularTokenizerOp.from_pretrained(tok_path)
    return model, tok, device


def _prompt_smiles(smiles: str) -> str:
    return ("<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END><EOS>")


def _prompt_protein(seq: str) -> str:
    return ("<@TOKENIZER-TYPE=AA><MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
            f"<SEQUENCE_NATURAL_START>{seq}<SEQUENCE_NATURAL_END><EOS>")


@torch.no_grad()
def embed(model, tok, text: str, kind: str = "smiles") -> torch.Tensor:
    """Return an L2-normalized 768-d embedding (masked mean-pool of encoder hidden state)."""
    prompt = _prompt_smiles(text) if kind == "smiles" else _prompt_protein(text)
    sd = {ENCODER_INPUTS_STR: prompt, "data.sample_id": 0}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS]).to(model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK]).to(model.device)
    out = model.forward_encoder_only([sd])
    rec = out[0] if isinstance(out, list) else out
    h = rec[_HID]                       # (1, L, 768)
    m = rec[_MASK].to(h.dtype)          # (1, L)
    pooled = (h * m.unsqueeze(-1)).sum(1) / m.sum(1, keepdim=True).clamp(min=1)
    v = pooled.squeeze(0).float()
    return v / v.norm().clamp(min=1e-9)
