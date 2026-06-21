"""Model loading + the CORRECT readouts for every MAMMAL public head.

Getting the readout I/O wrong is how every prior eval broke, so this module
reuses the proven wrappers (`mammal_quiver/`) and example helpers rather than
re-implementing anything:

  - DTI .......... mammal_quiver.dti.predict_pkd with the PEER norm constants
  - BBBP/ClinTox . mammal.examples.molnet.molnet_infer prompt + generative P(<1>)
  - Solubility ... mammal.examples.protein_solubility.ProteinSolubilityTask
  - TCR .......... the tcr_epitope_binding prompt (special entity tokens)
  - PPI .......... base model + <BINDING_AFFINITY_CLASS> (models/base_458m/README.md)

All classifier heads use the GENERATIVE readout (prompt + <SENTINEL_ID_0>,
model.generate, read P(<1>) at class position 1) — NOT the vestigial scalar
head. Every classifier returns a NORMALIZED P(<1>)/(P(<1>)+P(<0>)) in [0,1] so
the numbers are comparable across tabs; DTI returns a pKd scalar.

Architecture: a `Provider` per (task, model-source); a task hosts a LIST of
providers so a Quiver fine-tuned head can later drop in beside the IBM head and
render side by side (ui_spec §5). Models lazy-load on first request and cache in
the provider instance. A single global inference lock serializes MPS generates
(internal single-user tool).
"""

from __future__ import annotations

# Disable the TF/Flax backends BEFORE any transformers/mammal import (macOS
# mutex deadlock), and skip the flaky Xet downloader. Must precede mammal import.
import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import torch

# Repo root on sys.path so `import mammal_quiver` works regardless of CWD
# (mirrors the experiments/ shim).
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
MODELS = REPO / "models"

_CLS_POS = 1  # validated classification position (molnet/carcinogenicity convention)

# PEER checkpoint de-normalization constants (NOT the cold-split defaults baked
# into mammal_quiver.dti). ui_spec §1.
DTI_PEER_NORM_MEAN = 6.286291085593906
DTI_PEER_NORM_STD = 1.5422950906208512

# The DTI head truncates the target protein to this many residues; anything past
# it (e.g. Nav1.8's C-terminal binding region) is invisible to the model. This is
# the mechanical reason the named suzetrigine→Nav1.8 test fails — surface it.
DTI_MAX_AA = 1250


def dti_truncation_info(seq: str) -> dict:
    """Pure: does this target exceed the DTI head's 1250-aa window? (No model load.)"""
    n = len(seq or "")
    return {"target_len": n, "target_truncated": n > DTI_MAX_AA}

# Serialize generates — MPS models don't like concurrent forward passes, and an
# internal tool has one user at a time. Lift to a queue if this ever goes multi-user.
_INFER_LOCK = threading.Lock()


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _local(name: str) -> str:
    """Absolute path to a local checkpoint dir (must exist; we ship them locally)."""
    return str(MODELS / name)


# Shared base-model cache (PPI, generation, and embeddings all use base_458m —
# load it once, not three times).
_base_cache = None
_base_lock = threading.Lock()


def get_base_model():
    global _base_cache
    if _base_cache is None:
        with _base_lock:
            if _base_cache is None:
                from mammal_quiver.embed import load_base_model

                m, tok, _dev = load_base_model(device=pick_device())
                _base_cache = (m, tok)
    return _base_cache


def _norm_p1(tok, cls_pred, scores) -> tuple[float, int]:
    """Normalized P(<1>) and argmax class from a generative-classifier output.

    cls_pred = batch_dict[CLS_PRED][0]   (token ids per decode step)
    scores   = batch_dict[SCORES][0]     (per-step score over vocab)
    Returns (P(<1>)/(P(<1>)+P(<0>)), predicted_class in {0,1,-1}) at class position 1.
    Identical formula to Carcinogenicity/ProteinSolubility process_model_output.
    """
    pos1 = tok.get_token_id("<1>")
    pos0 = tok.get_token_id("<0>")
    s1 = float(scores[_CLS_POS, pos1])
    s0 = float(scores[_CLS_POS, pos0])
    prob = s1 / (s1 + s0 + 1e-10)
    pred = {pos1: 1, pos0: 0}.get(int(cls_pred[_CLS_POS]), -1)
    return prob, pred


# ----------------------------- provider abstraction -----------------------------

class Provider(ABC):
    """One model serving one task. Subclasses wrap a verified readout."""

    name: str = "provider"
    provider_kind: str = "ibm_public"  # ibm_public | quiver_finetuned

    def __init__(self) -> None:
        self._loaded = None
        self._lock = threading.Lock()

    def _ensure(self):
        """Lazy-load + cache the model, thread-safe (double-checked locking)."""
        if self._loaded is None:
            with self._lock:
                if self._loaded is None:
                    self._loaded = self._load()
        return self._loaded

    @abstractmethod
    def _load(self):
        ...

    @abstractmethod
    def predict(self, inputs: dict) -> dict:
        """Run the readout. Returns a dict matching the Prediction schema."""
        ...


@dataclass
class TaskSpec:
    slug: str
    providers: list[Provider] = field(default_factory=list)


# ----------------------------- IBM public providers -----------------------------

class SolubilityIbmProvider(Provider):
    name = "IBM solubility head"

    def _load(self):
        from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
        from mammal.model import Mammal

        d = _local("protein_solubility")
        model = Mammal.from_pretrained(d).to(pick_device()).eval()
        tok = ModularTokenizerOp.from_pretrained(os.path.join(d, "tokenizer"))
        return model, tok

    @torch.no_grad()
    def predict(self, inputs: dict) -> dict:
        from mammal.examples.protein_solubility.task import ProteinSolubilityTask
        from mammal.keys import CLS_PRED, SCORES

        model, tok = self._ensure()
        sd = ProteinSolubilityTask.data_preprocessing(
            sample_dict={"protein_seq": inputs["protein_seq"]},
            protein_sequence_key="protein_seq",
            tokenizer_op=tok,
            device=model.device,
        )
        bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
        ans = ProteinSolubilityTask.process_model_output(
            tokenizer_op=tok, decoder_output=bd[CLS_PRED][0], decoder_output_scores=bd[SCORES][0]
        )
        return {
            "score_kind": "normalized_p1",
            "value": round(float(ans["normalized_scores"]), 4),
            "pred_class": int(ans["pred"]),
            "note": "1 = soluble, 0 = insoluble",
        }


class MolnetIbmProvider(Provider):
    """BBBP / ClinTox-tox / ClinTox-fda — reuse molnet's exact prompt, normalize P(<1>)."""

    def __init__(self, task_name: str, local_dir: str, display: str, positive_label: str):
        super().__init__()
        self.task_name = task_name      # "BBBP" | "TOXICITY" | "FDA_APPR"
        self.local_dir = local_dir
        self.name = display
        self.positive_label = positive_label

    def _load(self):
        from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
        from mammal.model import Mammal

        d = _local(self.local_dir)
        model = Mammal.from_pretrained(d).to(pick_device()).eval()
        tok = ModularTokenizerOp.from_pretrained(os.path.join(d, "tokenizer"))
        return model, tok

    @torch.no_grad()
    def predict(self, inputs: dict) -> dict:
        from mammal.examples.molnet import molnet_infer
        from mammal.keys import CLS_PRED, SCORES

        model, tok = self._ensure()
        sd = molnet_infer.create_sample_dict(self.task_name, inputs["smiles"], tok, model)
        bd = molnet_infer.get_predictions(model, sd)
        prob, pred = _norm_p1(tok, bd[CLS_PRED][0], bd[SCORES][0])
        return {
            "score_kind": "normalized_p1",
            "value": round(prob, 4),
            "pred_class": pred,
            "note": f"1 = {self.positive_label}",
        }


class DtiIbmProvider(Provider):
    name = "IBM PEER head"

    def _load(self):
        from mammal_quiver.dti import load_dti_model

        model, tok, _dev = load_dti_model(source=_local("dti_bindingdb_pkd_peer"), device=pick_device())
        return model, tok

    def predict(self, inputs: dict) -> dict:
        from mammal_quiver.dti import predict_pkd

        model, tok = self._ensure()
        pkd = predict_pkd(
            model, tok,
            target_seq=inputs["target_seq"],
            drug_smiles=inputs["smiles"],
            norm_y_mean=DTI_PEER_NORM_MEAN,
            norm_y_std=DTI_PEER_NORM_STD,
        )
        trunc = dti_truncation_info(inputs["target_seq"])
        return {
            "score_kind": "pkd",
            "value": round(float(pkd), 4),
            "units": "pKd",
            "note": "higher = stronger predicted binding; protein truncated to 1250 aa, SMILES to 256 tokens",
            "extra": trunc,
        }


class PpiIbmProvider(Provider):
    """Base model, <BINDING_AFFINITY_CLASS> readout (models/base_458m/README.md). No dedicated checkpoint."""

    name = "IBM base (BINDING_AFFINITY_CLASS)"

    def _load(self):
        return get_base_model()

    @torch.no_grad()
    def predict(self, inputs: dict) -> dict:
        from mammal.keys import (
            CLS_PRED,
            ENCODER_INPUTS_ATTENTION_MASK,
            ENCODER_INPUTS_STR,
            ENCODER_INPUTS_TOKENS,
            SCORES,
        )

        model, tok = self._ensure()
        a, b = inputs["seq_a"], inputs["seq_b"]
        prompt = (
            "<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0>"
            f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN><SEQUENCE_NATURAL_START>{a}<SEQUENCE_NATURAL_END>"
            f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN><SEQUENCE_NATURAL_START>{b}<SEQUENCE_NATURAL_END><EOS>"
        )
        sd = {ENCODER_INPUTS_STR: prompt}
        tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
            key_out_tokens_ids=ENCODER_INPUTS_TOKENS, key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
        sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
        sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
        bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
        prob, pred = _norm_p1(tok, bd[CLS_PRED][0], bd[SCORES][0])
        return {
            "score_kind": "normalized_p1",
            "value": round(prob, 4),
            "pred_class": pred,
            "note": "1 = predicted interaction (base-model readout, least-validated — see reliability)",
        }


class TcrIbmProvider(Provider):
    name = "IBM TCR-epitope head"

    def _load(self):
        from mammal.examples.tcr_epitope_binding.main_infer import load_model

        d = _local("tcr_epitope_bind")
        model, tok = load_model(device=pick_device(), model_path=d, tokenizer_path=os.path.join(d, "tokenizer"))
        return model, tok

    @torch.no_grad()
    def predict(self, inputs: dict) -> dict:
        from mammal.keys import (
            CLS_PRED,
            ENCODER_INPUTS_ATTENTION_MASK,
            ENCODER_INPUTS_STR,
            ENCODER_INPUTS_TOKENS,
            SCORES,
        )

        model, tok = self._ensure()
        tcr, epi = inputs["tcr_beta_seq"], inputs["epitope_seq"]
        # Exact tcr_epitope_binding prompt (special entity tokens), normalized for UI consistency.
        prompt = (
            "<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0><@TOKENIZER-TYPE=AA>"
            f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_TCR_BETA_VDJ><SEQUENCE_NATURAL_START>{tcr}<SEQUENCE_NATURAL_END>"
            f"<@TOKENIZER-TYPE=AA><MOLECULAR_ENTITY><MOLECULAR_ENTITY_EPITOPE><SEQUENCE_NATURAL_START>{epi}<SEQUENCE_NATURAL_END><EOS>"
        )
        sd = {ENCODER_INPUTS_STR: prompt}
        tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
            key_out_tokens_ids=ENCODER_INPUTS_TOKENS, key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
        sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
        sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
        bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
        prob, pred = _norm_p1(tok, bd[CLS_PRED][0], bd[SCORES][0])
        return {
            "score_kind": "normalized_p1",
            "value": round(prob, 4),
            "pred_class": pred,
            "note": "1 = predicted TCR–epitope binding",
        }


# ----------------------------- task registry -----------------------------
# Ordered providers per task. IBM head today; a Quiver fine-tuned head later is
# just `TASKS["dti"].providers.append(DtiQuiverNav18Provider())` — run_task,
# the API `providers[]`, and the frontend loop all already handle N providers.

TASKS: dict[str, TaskSpec] = {
    "dti": TaskSpec("dti", [DtiIbmProvider()]),
    "ppi": TaskSpec("ppi", [PpiIbmProvider()]),
    "bbbp": TaskSpec("bbbp", [MolnetIbmProvider("BBBP", "moleculenet_bbbp", "IBM BBBP head", "BBB-penetrant")]),
    "clintox_tox": TaskSpec("clintox_tox", [MolnetIbmProvider("TOXICITY", "moleculenet_clintox_tox", "IBM ClinTox-tox head", "clinical-trial toxic")]),
    "clintox_fda": TaskSpec("clintox_fda", [MolnetIbmProvider("FDA_APPR", "moleculenet_clintox_fda", "IBM FDA head", "FDA-approved")]),
    "solubility": TaskSpec("solubility", [SolubilityIbmProvider()]),
    "tcr": TaskSpec("tcr", [TcrIbmProvider()]),
}


def _run_providers(spec: "TaskSpec", inputs: dict) -> list[dict]:
    """Run every provider for one input (caller holds the inference lock)."""
    out = []
    for p in spec.providers:
        out.append({
            "provider_name": p.name,
            "provider_kind": p.provider_kind,
            "prediction": p.predict(inputs),
        })
    return out


def run_task(task: str, inputs: dict) -> list[dict]:
    """Run every provider for a task. Returns one record per provider."""
    spec = TASKS.get(task)
    if spec is None:
        raise KeyError(task)
    with _INFER_LOCK:
        return _run_providers(spec, inputs)


def run_task_batch(task: str, rows: list[dict]) -> list[dict]:
    """Run a task over many already-preprocessed input rows under ONE lock hold.

    Returns one record per row, in input order: either
    `{"providers": [...], "error": None}` or `{"providers": None, "error": "msg"}`.
    A single row that the model chokes on becomes that row's error — it never kills
    the batch (the whole point of triaging a screening library is fault tolerance).
    """
    spec = TASKS.get(task)
    if spec is None:
        raise KeyError(task)
    if not rows:
        return []
    out: list[dict] = []
    with _INFER_LOCK:
        for inputs in rows:
            try:
                out.append({"providers": _run_providers(spec, inputs), "error": None})
            except Exception as e:  # noqa: BLE001  (fault-isolate one bad row)
                out.append({"providers": None, "error": f"{type(e).__name__}: {e}"})
    return out


# ============================ Generation (base model span-infill) ============================
# Reuses the verified phase6_generation.py harness. Public base_458m is a T5 span-infiller:
# place <SENTINEL_ID_0> where a span is removed; the decoder emits the fill. NOT a de-novo
# design tool (verdict ❌) — this tab demonstrates exactly that limit honestly.

import re as _re

_SENTINEL_RE = _re.compile(r"<SENTINEL_ID_\d+>")
_SPECIAL_RE = _re.compile(r"<[^>]+>")


@torch.no_grad()
def _generate_decoded(model, tok, prompt: str, max_new_tokens: int = 48) -> str:
    from mammal.keys import (
        CLS_PRED,
        ENCODER_INPUTS_ATTENTION_MASK,
        ENCODER_INPUTS_STR,
        ENCODER_INPUTS_TOKENS,
    )

    sd = {ENCODER_INPUTS_STR: prompt}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS, key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], max_new_tokens=max_new_tokens)
    ids = out[CLS_PRED][0].tolist()
    pad_id = model.config.t5_config.pad_token_id
    ids = [i for i in ids if i != pad_id]
    return tok._tokenizer.decode(ids)


def _extract_fill(decoded: str):
    if "<SENTINEL_ID_0>" not in decoded:
        return False, None
    after = decoded.split("<SENTINEL_ID_0>", 1)[1]
    nxt = _SENTINEL_RE.search(after)
    fill_raw = after[: nxt.start()] if nxt else after
    return True, _SPECIAL_RE.sub("", fill_raw).strip()


def _canonical_smiles(s: str | None):
    if not s:
        return None
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m is not None else None


def run_generate(text: str, kind: str = "smiles") -> dict:
    """Span-infill demo: mask an interior span (or honor a user-placed <SENTINEL_ID_0>),
    generate the fill, splice it back, validate. Honest illustration of the ❌ verdict."""
    aa_alphabet = set("ACDEFGHIKLMNPQRSTVWY")
    with _INFER_LOCK:
        model, tok = get_base_model()
        # If the user placed a sentinel, split on it; else auto-mask the middle third.
        if "<SENTINEL_ID_0>" in text:
            prefix, suffix = text.split("<SENTINEL_ID_0>", 1)
            held = None
        else:
            L = len(text)
            span = max(2, L // 3)
            a = (L - span) // 2
            prefix, held, suffix = text[:a], text[a:a + span], text[a + span:]
        if kind == "smiles":
            prompt = ("<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
                      f"<SEQUENCE_NATURAL_START>{prefix}<SENTINEL_ID_0>{suffix}<SEQUENCE_NATURAL_END><EOS>")
        else:
            prompt = ("<@TOKENIZER-TYPE=AA><MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
                      f"<SEQUENCE_NATURAL_START>{prefix}<SENTINEL_ID_0>{suffix}<SEQUENCE_NATURAL_END><EOS>")
        decoded = _generate_decoded(model, tok, prompt, max_new_tokens=48)

    compliant, fill = _extract_fill(decoded)
    recon = (prefix + (fill or "") + suffix) if compliant else None
    extra = {
        "kind": kind,
        "masked_prefix": prefix,
        "held_out_span": held,
        "masked_suffix": suffix,
        "predicted_fill": fill,
        "format_compliant": compliant,
        "decoded_raw": decoded[:300],
    }
    if kind == "smiles":
        recon_canon = _canonical_smiles(recon)
        extra["reconstructed_valid"] = recon_canon is not None
        extra["exact_recovery"] = (held is not None and fill == held)
        result_text = [recon_canon] if recon_canon else ([recon] if recon else [])
    else:
        fill_aa = "".join(c for c in (fill or "") if c in aa_alphabet)
        extra["aa_valid_fraction"] = round(len(fill_aa) / len(fill), 3) if fill else 0.0
        extra["exact_recovery"] = (held is not None and fill == held)
        result_text = [recon] if recon else []
    return {"score_kind": "none", "text": result_text, "extra": extra,
            "note": "span-infill analog (base model is NOT a de-novo design tool — see reliability)"}


# ============================ Embeddings (family clustering) ============================
# Verified value: protein embeddings recover functional family (NN recall 0.92). Cross-modal
# (protein↔SMILES) retrieval is DEAD (cosine 0.08) — so for SMILES we return the vector with
# that caveat and no family match.

# Small illustrative reference panel (UniProt accessions), fetched + embedded lazily and cached.
_FAMILY_PANEL = {
    "kinase (CDK2)": "P24941",
    "GPCR (β2-adrenergic, ADRB2)": "P07550",
    "serine protease (trypsin-1)": "P07477",
    "nuclear receptor (ERα)": "P03372",
    "lysozyme C": "P00698",
}
_panel_cache = None
_panel_lock = threading.Lock()


def _get_family_panel() -> dict:
    """family label -> L2-normalized 768-d reference embedding (lazy, cached, network-tolerant)."""
    global _panel_cache
    if _panel_cache is None:
        with _panel_lock:
            if _panel_cache is None:
                from mammal_quiver import sequences
                from mammal_quiver.embed import embed as _embed

                model, tok = get_base_model()
                panel = {}
                for fam, acc in _FAMILY_PANEL.items():
                    try:
                        seq = sequences.fetch_uniprot_sequence(acc)
                        panel[fam] = _embed(model, tok, seq, kind="protein")
                    except Exception:
                        continue  # offline / fetch failure: skip this family
                _panel_cache = panel
    return _panel_cache


def run_embed(text: str, kind: str = "protein") -> dict:
    from mammal_quiver.embed import embed as _embed

    with _INFER_LOCK:
        model, tok = get_base_model()
        vec = _embed(model, tok, text, kind=kind)  # (768,) L2-normalized
        nearest_family = None
        family_scores = None
        if kind == "protein":
            panel = _get_family_panel()
            if panel:
                family_scores = {fam: round(float(torch.dot(vec, pv)), 3) for fam, pv in panel.items()}
                nearest_family = max(family_scores, key=family_scores.get)
    v = vec.tolist()
    note = ("nearest functional family from a small reference panel" if kind == "protein"
            else "SMILES embedding — cross-modal protein↔compound retrieval does NOT work (see reliability)")
    return {
        "score_kind": "none",
        "vector": v,
        "nearest_family": nearest_family,
        "family_scores": family_scores,
        "note": note,
        "extra": {"dim": len(v), "preview": [round(x, 4) for x in v[:8]]},
    }
