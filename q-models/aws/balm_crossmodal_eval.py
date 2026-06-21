"""BALM cross-modal (compound<->target shared-embedding) eval on Quiver panels.

The question: does BALM put a protein target and a compound in the SAME embedding
space with a meaningful cosine (unlike MAMMAL, whose protein<->ligand cosine was
0.08)? BALM = ESM-2 (protein) + ChemBERTa-2 (ligand) -> linear projection -> shared
space; cosine(protein_emb, drug_emb) IS the binding score (scaled to pKd).

We run it on the IDENTICAL Nav1.8 (n=11) + mTOR (n=7) binder/decoy panels that
Boltz-2 scored (0.714 / 1.000), so the comparison is apples-to-apples.

Per target we report:
  - per-compound cosine + pKd (+ the Boltz prob_binder already in the panel)
  - binder-vs-decoy AUROC on the cosine score (head-to-head vs Boltz / ConPLex)
  - mean cosine for binders vs decoys + their separation (the "is the shared space
    real?" geometry test that MAMMAL failed)
  - Spearman(BALM pKd, Boltz prob_binder) as a cross-oracle agreement check

CAVEAT recorded in the output: ESM-2 truncates at 1022 tokens; Nav1.8 (1956 aa) and
mTOR (2549 aa) both exceed it, so BALM sees only the N-terminal ~1022 residues — the
same truncation wall that sinks sequence DTI heads on big channels/kinases.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/balm_out/balm_crossmodal_result.json"))
BALM_DIR = Path(os.environ.get("BALM_DIR", "/opt/BALM"))
CHECKPOINT = os.environ.get("BALM_CKPT", "BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse")
CONFIG = os.environ.get("BALM_CONFIG", str(BALM_DIR / "default_configs" / "balm_peft.yaml"))


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    labels = list(labels)
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


def spearman(a, b):
    from scipy.stats import spearmanr
    a = [x for x in a]; b = [x for x in b]
    if len([x for x in b if x is not None]) < 3:
        return None
    pairs = [(x, y) for x, y in zip(a, b) if y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    r, _ = spearmanr(xs, ys)
    return None if np.isnan(r) else float(r)


def main() -> int:
    import torch

    sys.path.insert(0, str(BALM_DIR))
    from balm import common_utils
    from balm.configs import Configs
    from balm.models import BALM
    from balm.models.utils import load_trained_model, load_pretrained_pkd_bounds
    from transformers import AutoTokenizer

    print(f"[load] config={CONFIG} checkpoint={CHECKPOINT} device={DEVICE}", flush=True)
    configs = Configs(**common_utils.load_yaml(CONFIG))
    # Pin to the released BindingDB-cleaned cosine checkpoint (the documented one).
    try:
        configs.model_configs.checkpoint_path = CHECKPOINT
    except Exception as e:
        print(f"[warn] could not set checkpoint_path on config: {e}", flush=True)

    model = BALM(configs.model_configs)
    model = load_trained_model(model, configs.model_configs, is_training=False)
    model.to(DEVICE).eval()
    pkd_lo, pkd_hi = load_pretrained_pkd_bounds(configs.model_configs.checkpoint_path)
    print(f"[load] pkd bounds: [{pkd_lo}, {pkd_hi}]", flush=True)

    p_tok = AutoTokenizer.from_pretrained(configs.model_configs.protein_model_name_or_path)
    d_tok = AutoTokenizer.from_pretrained(configs.model_configs.drug_model_name_or_path)
    p_max = getattr(p_tok, "model_max_length", 1024)
    if p_max > 100000:  # some tokenizers report a sentinel; clamp to ESM-2's real cap
        p_max = 1024

    panels = json.loads(PANELS.read_text())
    results = {}

    for key, panel in panels.items():
        seq = panel["protein_seq"]
        seq_len = len(seq)
        truncated = seq_len > (p_max - 2)
        p_in = p_tok(seq, return_tensors="pt", truncation=True, max_length=p_max).to(DEVICE)

        rows = []
        for comp in panel["compounds"]:
            d_in = d_tok(comp["smiles"], return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
            inputs = {
                "protein_input_ids": p_in["input_ids"],
                "protein_attention_mask": p_in["attention_mask"],
                "drug_input_ids": d_in["input_ids"],
                "drug_attention_mask": d_in["attention_mask"],
            }
            with torch.no_grad():
                out = model(inputs)
            cos = float(out["cosine_similarity"].reshape(-1)[0])
            # manual cosine from the exposed embeddings (sanity: should ~equal `cos`)
            pe = out["protein_embedding"].reshape(-1)
            de = out["drug_embedding"].reshape(-1)
            man_cos = float(torch.nn.functional.cosine_similarity(pe, de, dim=0))
            pkd = float(model.cosine_similarity_to_pkd(out["cosine_similarity"],
                        pkd_upper_bound=pkd_hi, pkd_lower_bound=pkd_lo).reshape(-1)[0])
            rows.append({"drug": comp["drug"], "label": comp["label"], "cosine": round(cos, 4),
                         "cosine_from_emb": round(man_cos, 4), "pkd": round(pkd, 3),
                         "boltz_prob_binder": comp.get("boltz_prob_binder")})

        labels = [r["label"] for r in rows]
        cosines = [r["cosine"] for r in rows]
        pkds = [r["pkd"] for r in rows]
        bind = [r["cosine"] for r in rows if r["label"] == 1]
        decoy = [r["cosine"] for r in rows if r["label"] == 0]
        results[key] = {
            "target": panel["target"], "seq_len": seq_len,
            "esm2_truncated_to": p_max if truncated else None,
            "truncation_caveat": (f"sequence {seq_len} aa > ESM-2 {p_max}-token cap; "
                                  "model saw only the N-terminal window") if truncated else None,
            "n": len(rows), "n_binders": len(bind), "n_decoys": len(decoy),
            "auroc_cosine": auroc(labels, cosines),
            "mean_cosine_binders": round(float(np.mean(bind)), 4) if bind else None,
            "mean_cosine_decoys": round(float(np.mean(decoy)), 4) if decoy else None,
            "binder_decoy_separation": (round(float(np.mean(bind) - np.mean(decoy)), 4)
                                        if bind and decoy else None),
            "spearman_pkd_vs_boltz": spearman(pkds, [r["boltz_prob_binder"] for r in rows]),
            "compounds": sorted(rows, key=lambda r: r["cosine"], reverse=True),
        }
        print(f"[{key}] {panel['target']}: AUROC(cos)={results[key]['auroc_cosine']} "
              f"sep={results[key]['binder_decoy_separation']} trunc={truncated}", flush=True)

    payload = {
        "model": "BALM (ESM-2-150M + ChemBERTa-77M, cosine-MSE PEFT)",
        "checkpoint": CHECKPOINT,
        "question": "compound<->target shared embedding space with meaningful cosine?",
        "baselines_for_context": {
            "boltz2_nav18_auroc": 0.714, "boltz2_mtor_auroc": 1.000,
            "conplex_nav_auroc": 0.437, "mammal_crossmodal_cosine": 0.08,
        },
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps({k: {"auroc_cosine": v["auroc_cosine"],
                          "separation": v["binder_decoy_separation"]} for k, v in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
