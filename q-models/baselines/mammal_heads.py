"""baselines.mammal_heads — MAMMAL's scores for the head-to-head, in one place.

The compare scripts need MAMMAL in two distinct configurations (see the plan's
"critical reframing"):
  * Tests 1-3 use MAMMAL's OFF-THE-SHELF DTI head (general protein+SMILES → pKd).
    We use the PEER checkpoint + its norm constants — MAMMAL's best DTI config
    (CLAUDE.md: Spearman 0.43; single-target triage ≈ chance). This is the
    apples-to-apples analog of ConPLex / Boltz-2.
  * Test 4 (WDR91 / PGK2) uses MAMMAL's per-target FINE-TUNED heads via the
    generative binder_prob readout. The challengers run zero-shot here, so this
    comparison is deliberately in MAMMAL's favour and is labelled as such.

Runs in the `mammal` conda env (imports mammal_quiver). Kept thin; reuses the
validated wrappers in mammal_quiver/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# PEER DTI checkpoint — MAMMAL's best generalizing DTI head (its own norm constants).
PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_M, PEER_S = 6.286291085593906, 1.5422950906208512


def load_dti_peer(device: str | None = None):
    from mammal_quiver.dti import load_dti_model
    return load_dti_model(device=device, source=PEER_SOURCE)


def dti_scores(model, tok, pairs, progress: str | None = None) -> list[float]:
    """Predicted pKd (PEER norms) for an ordered list of (protein_seq, smiles)."""
    from mammal_quiver.dti import predict_pkd
    out = []
    for i, (seq, smi) in enumerate(pairs):
        out.append(predict_pkd(model, tok, seq, smi, PEER_M, PEER_S))
        if progress and (i + 1) % 25 == 0:
            print(f"    [MAMMAL-DTI {progress}] {i+1}/{len(pairs)}")
    return out


def load_finetuned(target: str = "wdr91", device: str | None = None):
    """Load a per-target fine-tuned head. Returns (model, tok, task_token, device)."""
    from mammal_quiver.wdr91 import load_target_model
    return load_target_model(target, device=device)


def finetuned_scores(model, tok, task: str, smiles_list, progress: str | None = None) -> list[float]:
    """P(binder) = P(<1>) from the fine-tuned generative classifier, per SMILES."""
    from mammal_quiver.wdr91 import binder_prob
    out = []
    for i, smi in enumerate(smiles_list):
        out.append(binder_prob(model, tok, smi, task=task))
        if progress and (i + 1) % 50 == 0:
            print(f"    [MAMMAL-{progress}] {i+1}/{len(smiles_list)}")
    return out
