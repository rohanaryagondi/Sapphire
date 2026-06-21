"""ProTrek-650M (westlake-repl) Track-1 — function/text-aligned protein embeddings on the
40-gene CRISPR-N panel. Runs on a GPU instance.

HYPOTHESIS: ProTrek's tri-modal contrastive training (protein sequence <-> structure <->
biomedical TEXT) gives the protein representation a *function* axis that pure-sequence
encoders lack. The Track-1 ceiling for ESM-2 / MAMMAL is set by the FUNCTION-DEFINED
families (e3_ligase <= 0.5, nuclear_receptor ~0.5-0.83) where sequence similarity does NOT
track family. If text alignment helps, those two families are where it should show.

PROTOCOL (identical to the rest of the Track-1 ladder so numbers are best-vs-best comparable):
  embed each panel protein, L2-normalize, cosine sim, leave-one-out NN same-family recall;
  report RAW + MEAN-CENTERED (the repo's established finding: last-layer mean-pool undersells,
  best-layer + centering is the fair protocol). Headline = overall NN-recall + the e3_ligase
  and nuclear_receptor per-family numbers.

LAYER SWEEP — NOT AVAILABLE here, and that is the point:
  ProTrek's public API is model.get_protein_repr([seq]) -> a SINGLE final, projected,
  L2-normalized CLIP-style contrastive embedding ([N, repr_dim]). It does NOT expose the
  underlying ESM-2-650M intermediate transformer layers. The ESM-2-650M sub-encoder layer
  sweep is ALREADY covered by aws/esm2_big_layer_sweep.py (best-layer 0.875) and
  experiments/esm2_layer_sweep.py. So ProTrek is evaluated on its single function-aligned
  protein repr (raw + centered), and the JSON records layer_sweep_available=False with the
  reason. The interesting comparison is ProTrek's projected repr vs ESM-2's best raw layer:
  does the function alignment buy the e3/NR families anything?

OPTIONAL TEXT-ANCHORED ASSIGNMENT (secondary, not the headline):
  Embed each family's name/description via model.get_text_repr([...]) into the SAME shared
  space, then assign every protein to its nearest family-text anchor (cosine). Report the
  per-family accuracy of that text-anchored assignment — this is the unique thing a tri-modal
  model can do that a sequence-only encoder cannot, and it directly probes whether the text
  modality cracks the function-defined families. Primary metric stays protein-embedding
  NN-recall (matches every other Track-1 eval).

Reads compare_esm2_650m.json (panel: accession/name/family) + _uniprot_cache.json
(accession -> sequence) from /opt — the EXACT same panel + sequence cache the ESM/Ankh/ProtST
Track-1 evals use. Loads ProTrek via its own repo loader (PROTREK_DIR on sys.path) with the
HF-downloaded weights (PROTREK_WEIGHTS). Out: env OUT (default /opt/protrek_result.json).

Usage: OUT=/opt/protrek_result.json PROTREK_DIR=/opt/ProTrek \
       PROTREK_WEIGHTS=/opt/ProTrek/weights/ProTrek_650M python protrek_eval.py
"""
from __future__ import annotations
import os
# transformers auto-imports TensorFlow which deadlocks/bloats; force it off everywhere.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import json
import sys
import time
import traceback
from datetime import datetime

import numpy as np

# Where the panel + sequence cache live on-instance (userdata stages them here). Falls back to
# the repo's results/ dir so the script can be smoke-tested locally too.
BASE = "/opt" if os.path.exists("/opt/compare_esm2_650m.json") else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
OUT = os.environ.get("OUT", "/opt/protrek_result.json")
PROTREK_DIR = os.environ.get("PROTREK_DIR", "/opt/ProTrek")
PROTREK_WEIGHTS = os.environ.get("PROTREK_WEIGHTS",
                                 os.path.join(PROTREK_DIR, "weights", "ProTrek_650M"))
# ProTrek's ESM-2-650M sub-encoder caps at 1024 tokens; match the rest of the ladder.
TRUNC = int(os.environ.get("TRUNC_AA", "1022"))


def _p(*a):
    print(*a, flush=True)


# ---- metric (verbatim protocol from aws/esm2_big_layer_sweep.py / aws/ankh_sweep.py) ----
def cms(E):
    """Cosine-similarity matrix of L2-normalized rows."""
    n = np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
    Z = E / n
    return Z @ Z.T


def nn_recall(sim, labels):
    """Leave-one-out nearest-neighbour same-family recall."""
    c = 0
    for i in range(len(labels)):
        r = sim[i].copy()
        r[i] = -np.inf
        if labels[int(np.argmax(r))] == labels[i]:
            c += 1
    return c / len(labels)


def per_family_recall(sim, labels):
    by = {}
    for i in range(len(labels)):
        r = sim[i].copy()
        r[i] = -np.inf
        nn = int(np.argmax(r))
        by.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {f: float(np.mean(v)) for f, v in by.items()}


# ---- family text anchors for the OPTIONAL text-anchored assignment (secondary metric) ----
# Short biomedical-style descriptions of each panel family. ProTrek was trained on
# protein<->text pairs of roughly this shape (UniProt/Gene-Ontology function blurbs).
FAMILY_TEXTS = {
    "kinase": "Protein kinase enzyme that catalyzes the transfer of a phosphate group "
              "from ATP to a substrate protein.",
    "gpcr": "G protein-coupled receptor, a seven-transmembrane integral membrane receptor "
            "that transduces extracellular signals.",
    "ion_channel": "Voltage-gated ion channel, a transmembrane pore-forming protein that "
                   "conducts ions across the cell membrane.",
    "nuclear_receptor": "Ligand-activated nuclear hormone receptor transcription factor "
                        "that regulates gene expression.",
    "e3_ligase": "E3 ubiquitin-protein ligase that catalyzes the transfer of ubiquitin to "
                 "target proteins for degradation.",
    "lipid_kinase": "Lipid kinase that phosphorylates phosphatidylinositol lipids in "
                    "phosphoinositide signaling.",
    "phosphatase": "Protein phosphatase enzyme that removes phosphate groups from "
                   "phosphorylated substrate proteins.",
}


def _to_numpy(x):
    """ProTrek get_*_repr returns a torch.Tensor ([N, repr_dim], normalized). Coerce to
    float64 numpy regardless of device/dtype."""
    try:
        import torch
        if isinstance(x, torch.Tensor):
            return x.detach().float().cpu().numpy().astype(np.float64)
    except Exception:
        pass
    return np.asarray(x, dtype=np.float64)


def text_anchored_assignment(prot_E, fam_E, fam_order, labels):
    """Assign each protein to its nearest family-text anchor in the shared space; report
    overall + per-family accuracy. Both inputs are L2-normalized -> dot product = cosine."""
    Pn = prot_E / (np.linalg.norm(prot_E, axis=1, keepdims=True) + 1e-12)
    Fn = fam_E / (np.linalg.norm(fam_E, axis=1, keepdims=True) + 1e-12)
    sims = Pn @ Fn.T  # [n_prot, n_fam]
    preds = [fam_order[int(np.argmax(sims[i]))] for i in range(len(labels))]
    correct = [int(preds[i] == labels[i]) for i in range(len(labels))]
    by = {}
    for i in range(len(labels)):
        by.setdefault(labels[i], []).append(correct[i])
    return {
        "overall_accuracy": float(np.mean(correct)) if correct else float("nan"),
        "per_family_accuracy": {f: float(np.mean(v)) for f, v in by.items()},
        "predictions": preds,
    }


def main():
    t0 = datetime.utcnow()
    import torch

    _p(f"=== ProTrek-650M Track-1 eval  {t0.isoformat()}Z ===")
    _p(f"BASE={BASE}  OUT={OUT}")
    _p(f"PROTREK_DIR={PROTREK_DIR}  PROTREK_WEIGHTS={PROTREK_WEIGHTS}")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if torch.cuda.is_available():
        _p(f"CUDA: {torch.cuda.get_device_name(0)}  "
           f"{torch.cuda.get_device_properties(0).total_memory/1e9:.0f}GB")
    else:
        _p("WARNING: no CUDA — running on CPU (slow but functional)")

    # ---- panel + sequences (EXACT same files as the ESM/Ankh/ProtST Track-1 evals) ----
    proteins = json.load(open(f"{BASE}/compare_esm2_650m.json"))["proteins"]
    labels = [p["family"] for p in proteins]
    names = [p["name"] for p in proteins]
    cache = json.load(open(f"{BASE}/_uniprot_cache.json"))
    seqs = [cache[p["accession"]][:TRUNC] for p in proteins]
    _p(f"panel: {len(proteins)} proteins  "
       f"families={ {f: labels.count(f) for f in sorted(set(labels))} }")

    # ---- load ProTrek via its own repo loader ----
    if PROTREK_DIR not in sys.path:
        sys.path.insert(0, PROTREK_DIR)
    from model.ProTrek.protrek_trimodal_model import ProTrekTrimodalModel

    config = {
        "protein_config": os.path.join(PROTREK_WEIGHTS, "esm2_t33_650M_UR50D"),
        "text_config": os.path.join(PROTREK_WEIGHTS,
                                    "BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"),
        # The HF weights bundle the foldseek STRUCTURE-ENCODER weights as a subfolder; this is
        # NOT the Foldseek binary and no structures are folded — we only call get_protein_repr
        # (sequence) and get_text_repr (text). The structure encoder is constructed but unused.
        "structure_config": os.path.join(PROTREK_WEIGHTS, "foldseek_t30_150M"),
        "from_checkpoint": os.path.join(PROTREK_WEIGHTS, "ProTrek_650M.pt"),
    }
    _p("constructing ProTrekTrimodalModel ...")
    tload = time.time()
    model = ProTrekTrimodalModel(**config).eval().to(dev)
    _p(f"  loaded in {time.time()-tload:.0f}s")

    result = {
        "test": "protrek_650m_track1",
        "timestamp": t0.isoformat() + "Z",
        "model": "westlake-repl/ProTrek_650M",
        "device": dev,
        "n_proteins": len(proteins),
        "names": names,
        "labels": labels,
        "truncate_aa": TRUNC,
        "protocol": "model.get_protein_repr (final function-aligned contrastive repr), "
                    "L2-norm, cosine, LOO NN same-family recall, raw + mean-centered",
        "layer_sweep_available": False,
        "layer_sweep_note": (
            "ProTrek's public API (get_protein_repr) returns a SINGLE final projected/"
            "normalized contrastive embedding and does not expose intermediate ESM-2 "
            "transformer layers. The ESM-2-650M sub-encoder layer sweep is already covered "
            "by aws/esm2_big_layer_sweep.py (best-layer 0.875). ProTrek is evaluated on its "
            "single function-aligned protein repr."),
        "refs": {
            "esm2_650M_best_layer": 0.875,
            "esm2_650M_last_layer_centered": 0.750,
            "mammal_458M_last_layer": 0.750,
            "esm3_NR": 1.0,
            "saprot_gpcr": 1.0,
            "e3_ligase_ceiling": 0.5,
            "bar": 0.80,
        },
    }

    # ---- PRIMARY: protein-embedding NN-recall (raw + mean-centered) ----
    try:
        _p("embedding proteins via get_protein_repr ...")
        temb = time.time()
        with torch.no_grad():
            prot_repr = model.get_protein_repr(seqs)
        prot_E = _to_numpy(prot_repr)
        _p(f"  protein reprs: shape {prot_E.shape}  ({time.time()-temb:.0f}s)")

        raw = nn_recall(cms(prot_E), labels)
        Ec = prot_E - prot_E.mean(axis=0, keepdims=True)
        cen = nn_recall(cms(Ec), labels)
        cen_better = cen >= raw
        E_use = Ec if cen_better else prot_E
        fam = per_family_recall(cms(E_use), labels)

        result["embedding_dim"] = int(prot_E.shape[1])
        result["protein_nn_recall"] = {
            "raw": float(raw),
            "centered": float(cen),
            "best": float(max(raw, cen)),
            "used": "centered" if cen_better else "raw",
            "per_family_nn_recall": fam,
        }
        # Headline call-outs: the two function-defined families.
        result["headline"] = {
            "overall_nn_recall_best": float(max(raw, cen)),
            "used": "centered" if cen_better else "raw",
            "e3_ligase_nn_recall": fam.get("e3_ligase"),
            "nuclear_receptor_nn_recall": fam.get("nuclear_receptor"),
            "beats_esm2_best_layer_0875": bool(max(raw, cen) > 0.875),
        }
        _p(f"  PROTEIN NN-recall  raw {raw:.3f}  centered {cen:.3f}  "
           f"BEST {max(raw, cen):.3f} ({result['protein_nn_recall']['used']})")
        _p(f"  per-family: {fam}")
        _p(f"  HEADLINE  e3_ligase={fam.get('e3_ligase')}  "
           f"nuclear_receptor={fam.get('nuclear_receptor')}")
    except Exception as e:
        result["protein_nn_recall"] = {"status": "FAILED",
                                       "error": f"{type(e).__name__}: {e}",
                                       "trace": traceback.format_exc()}
        _p(f"  PROTEIN EMBED FAILED: {e}")
        _p(traceback.format_exc())
        # protein metric is the whole point; still try to write what we have.
        with open(OUT, "w") as f:
            json.dump(result, f, indent=2, default=str)
        _p(f"wrote (partial) -> {OUT}")
        return

    # ---- SECONDARY (optional): text-anchored family assignment in the shared space ----
    try:
        _p("\nembedding family-text anchors via get_text_repr ...")
        fam_order = list(FAMILY_TEXTS.keys())
        texts = [FAMILY_TEXTS[f] for f in fam_order]
        with torch.no_grad():
            text_repr = model.get_text_repr(texts)
        fam_E = _to_numpy(text_repr)
        _p(f"  family-text reprs: shape {fam_E.shape}")
        ta = text_anchored_assignment(prot_E, fam_E, fam_order, labels)
        result["text_anchored_assignment"] = {
            "family_anchor_texts": FAMILY_TEXTS,
            "overall_accuracy": ta["overall_accuracy"],
            "per_family_accuracy": ta["per_family_accuracy"],
            "note": "secondary metric: nearest family-text anchor in the shared ProTrek "
                    "space; unique to a tri-modal model. Primary metric is protein NN-recall.",
        }
        # Does the TEXT modality crack the function-defined families that NN-recall plateaus on?
        result["headline"]["text_anchored_overall_accuracy"] = ta["overall_accuracy"]
        result["headline"]["text_anchored_e3_ligase_accuracy"] = \
            ta["per_family_accuracy"].get("e3_ligase")
        result["headline"]["text_anchored_nuclear_receptor_accuracy"] = \
            ta["per_family_accuracy"].get("nuclear_receptor")
        _p(f"  TEXT-ANCHORED overall acc {ta['overall_accuracy']:.3f}")
        _p(f"  per-family: {ta['per_family_accuracy']}")
    except Exception as e:
        result["text_anchored_assignment"] = {"status": "FAILED",
                                              "error": f"{type(e).__name__}: {e}"}
        _p(f"  TEXT-ANCHORED step FAILED (secondary, non-fatal): {e}")

    result["elapsed_s"] = round((datetime.utcnow() - t0).total_seconds(), 1)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2, default=str)
    _p(f"\nDONE -> {OUT}  ({result['elapsed_s']}s)")
    h = result.get("headline", {})
    _p("=== SUMMARY ===")
    _p(f"  protein NN-recall (best)   = {h.get('overall_nn_recall_best')}  "
       f"(vs ESM-2 best-layer 0.875)")
    _p(f"  e3_ligase NN-recall        = {h.get('e3_ligase_nn_recall')}  (ceiling ~0.5)")
    _p(f"  nuclear_receptor NN-recall = {h.get('nuclear_receptor_nn_recall')}")
    _p(f"  text-anchored overall acc  = {h.get('text_anchored_overall_accuracy')}")


if __name__ == "__main__":
    main()
