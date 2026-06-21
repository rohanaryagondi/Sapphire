"""Thin wrapper around MAMMAL's off-the-shelf drug-target binding (DTI) head.

Loads the published BindingDB-Kd finetuned checkpoint and predicts pKd for a
(protein sequence, drug SMILES) pair. No fine-tuning of our own — this is the
off-the-shelf model the 5/28 meeting asked us to sanity-check.

Checkpoint: ibm/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd
Output: pKd  (higher = stronger binding; pKd = -log10(Kd in molar))

API confirmed against mammal/examples/dti_bindingdb_kd/main_infer.py.
"""

from __future__ import annotations

import os

# MAMMAL inference is pure PyTorch. transformers will otherwise auto-import the
# installed TensorFlow, which deadlocks on import on macOS (mutex lock hang).
# Disable the TF/Flax backends BEFORE importing transformers/mammal.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import torch

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.examples.dti_bindingdb_kd.task import DtiBindingdbKdTask
from mammal.model import Mammal

DTI_MODEL_ID = "ibm/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd"

# Prefer a local copy if present (we download weights via curl to dodge the HF
# downloader's broken resume on this network). Falls back to the HF hub id.
_LOCAL_DTI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "dti_bindingdb_pkd")
DTI_SOURCE = _LOCAL_DTI if os.path.isfile(os.path.join(_LOCAL_DTI, "model.safetensors")) else DTI_MODEL_ID

# Normalization constants from the BindingDB-Kd finetune (predictions live in a
# normalized pKd space; these convert back to real pKd). Source: example defaults.
NORM_Y_MEAN = 5.79384684128215
NORM_Y_STD = 1.33808027428196

# Output key MAMMAL writes the regression scalar into.
_OUT_KEY = "model.out.dti_bindingdb_kd"


def pick_device(prefer: str | None = None) -> str:
    if prefer:
        return prefer
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_dti_model(device: str | None = None, source: str | None = None):
    """Load a finetuned DTI model + its tokenizer. Returns (model, tokenizer_op, device).

    source: HF id or local dir. Defaults to DTI_SOURCE (the cold-split checkpoint).
            Pass e.g. a local copy of the dti_bindingdb_pkd_peer checkpoint to use
            the PEER generalization variant (different norm constants — see below).
    """
    device = pick_device(device)
    source = source or DTI_SOURCE
    model = Mammal.from_pretrained(source)
    model = model.to(device=device)
    model.eval()
    # For a local dir the tokenizer wants the 'tokenizer/' subfolder directly
    # (it loads config.yaml from the path given); for a hub id it resolves that
    # subfolder itself. See ModularTokenizerOp.from_pretrained.
    tok_path = os.path.join(source, "tokenizer") if os.path.isdir(source) else source
    tokenizer_op = ModularTokenizerOp.from_pretrained(tok_path)
    return model, tokenizer_op, device


@torch.no_grad()
def predict_pkd(model, tokenizer_op, target_seq: str, drug_smiles: str,
                norm_y_mean: float = NORM_Y_MEAN, norm_y_std: float = NORM_Y_STD) -> float:
    """Predict pKd for one (protein sequence, drug SMILES) pair.

    norm_y_mean/std default to the cold-split checkpoint's constants. The PEER
    checkpoint uses 6.286291085593906 / 1.5422950906208512.
    """
    # "data.sample_id" is required only when the tokenizer truncates an
    # over-long input (e.g. proteins > 1250 aa): the truncation warning reads it.
    sample_dict = {"target_seq": target_seq, "drug_seq": drug_smiles, "data.sample_id": 0}
    sample_dict = DtiBindingdbKdTask.data_preprocessing(
        sample_dict=sample_dict,
        tokenizer_op=tokenizer_op,
        target_sequence_key="target_seq",
        drug_sequence_key="drug_seq",
        norm_y_mean=None,
        norm_y_std=None,
        device=model.device,
    )
    batch_dict = model.forward_encoder_only([sample_dict])
    batch_dict = DtiBindingdbKdTask.process_model_output(
        batch_dict,
        scalars_preds_processed_key=_OUT_KEY,
        norm_y_mean=norm_y_mean,
        norm_y_std=norm_y_std,
    )
    pred = batch_dict[_OUT_KEY]
    # process_model_output may return a list, tensor, or scalar depending on version.
    if hasattr(pred, "__len__"):
        pred = pred[0]
    if hasattr(pred, "item"):
        pred = pred.item()
    return float(pred)
