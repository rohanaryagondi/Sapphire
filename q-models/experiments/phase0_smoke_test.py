"""Phase 0 — Instantiation smoke test.

Exit criterion (docs/exploration_plan.md):
  model loads, runs inference, returns embeddings without error.

We use the off-the-shelf DTI checkpoint for both checks (it IS a MAMMAL model)
so Phase 0 needs only one ~1.8 GB download, not two — disk is tight on this box.

  0a. Encode a known compound (aspirin) through the encoder; confirm we get a
      finite real-valued embedding tensor of sane shape.
  0b. Run the repo's own default DTI example pair; confirm a finite pKd. This is
      exactly the path Phase 1 relies on, so we verify it works first.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase0_smoke_test.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")  # transformers would deadlock importing TF on macOS
os.environ.setdefault("USE_FLAX", "0")

import sys
import time
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

from mammal_quiver.dti import DTI_MODEL_ID, load_dti_model, predict_pkd  # noqa: E402

ASPIRIN_SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"
# Repo dti example defaults — known-good inputs we reproduce as a check.
EXAMPLE_TARGET = "NLMKRCTRGFRKLGKCTTLEEEKCKTLYPRGQCTCSDSKMNTHSCDCKSC"
EXAMPLE_DRUG = "CC(=O)NCCC1=CNc2c1cc(OC)cc2"


def main():
    print("=" * 64)
    print(f"Phase 0 smoke test — {DTI_MODEL_ID}")
    print("=" * 64)

    t0 = time.time()
    model, tok, device = load_dti_model()
    print(f"[load] model + tokenizer in {time.time()-t0:.1f}s on device={device}")

    # 0a — encode aspirin, confirm a finite embedding tensor
    from mammal.keys import (
        ENCODER_INPUTS_ATTENTION_MASK,
        ENCODER_INPUTS_STR,
        ENCODER_INPUTS_TOKENS,
    )

    prompt = (
        "<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        f"<SEQUENCE_NATURAL_START>{ASPIRIN_SMILES}<SEQUENCE_NATURAL_END><EOS>"
    )
    sd = {ENCODER_INPUTS_STR: prompt}
    tok(
        sample_dict=sd,
        key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
    )
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS]).to(device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK]).to(device)
    n_tok = int(sd[ENCODER_INPUTS_TOKENS].numel())

    with torch.no_grad():
        out = model.forward_encoder_only([sd])

    rec = out[0] if isinstance(out, list) else out
    emb = None
    for k, v in rec.items():
        if torch.is_tensor(v) and v.dtype.is_floating_point and v.dim() >= 2:
            emb = v
            print(f"[0a] aspirin: {n_tok} tokens -> embedding key '{k}' shape={tuple(v.shape)} dtype={v.dtype}")
            break
    assert emb is not None, f"no float embedding tensor in encoder output (keys={list(rec)})"
    assert torch.isfinite(emb).all(), "embedding has non-finite values"
    print("[0a] PASS — finite real-valued embedding returned")

    # 0b — reproduce the repo's default DTI example pair
    t0 = time.time()
    pkd = predict_pkd(model, tok, EXAMPLE_TARGET, EXAMPLE_DRUG)
    print(f"[0b] example pair pKd={pkd:.3f}  (inference {time.time()-t0:.1f}s)")
    assert pkd == pkd and abs(pkd) < 100, "pKd NaN or absurd"
    print("[0b] PASS — finite pKd from the DTI head")

    print("\nPhase 0 exit criterion MET: model loads, runs inference, returns embeddings.")


if __name__ == "__main__":
    main()
