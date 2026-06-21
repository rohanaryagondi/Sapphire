"""Phase 6 — ESM-2 650M vs MAMMAL 458M on protein-family clustering.

THE gap FINDINGS.md (and HANDOFF §7, CLAUDE.md) flags before Sapphire commits to MAMMAL
embeddings: Phase 5 only compared MAMMAL against ESM-2 *8M* (MAMMAL won, NN recall 0.92 vs
0.88). But a 458M model beating an 8M model on family recovery is unsurprising; the honest
baseline is a *size-matched* ESM-2. FINDINGS flags that ESM-2 650M/3B "would likely win and
must be checked." This script checks it.

Re-runs the EXACT Phase 5 protein-family-clustering benchmark
(experiments/phase5_esm_comparison.py): the SAME 25-protein x 5-family panel, the SAME metrics
(leave-one-out same-family nearest-neighbor recall, cosine; intra- vs inter-family cosine gap),
the SAME embedding recipe (mean-pool over residue positions, exclude CLS/EOS, then cosine) —
but with facebook/esm2_t33_650M_UR50D (650M params, ~2.5 GB) instead of the 8M model.

MEMORY (18 GB machine, ~1 GB hard-free + ~5 GB reclaimable): loads ESM-650M ALONE. Does NOT
load MAMMAL in this process — the MAMMAL numbers are READ from the cached Phase 5 JSON
(results/phase5_esm_comparison_*.json), which used the identical panel/metric. Forces CPU
(MPS uses unified RAM and thrashes under memory pressure), float32, low_cpu_mem_usage, one
sequence at a time, no_grad, frees tensors as it goes.

FALLBACK: if ESM-650M fails to download or OOMs on load, the failure is recorded and we fall
back to facebook/esm2_t30_150M_UR50D (150M, ~0.6 GB) as an intermediate size point. We do NOT
hang or retry in a loop — one attempt per model, capture the error, write what we have, exit.

UniProt sequences are cached to results/_uniprot_cache.json so a re-run never refetches.

Run:  USE_TF=0 USE_FLAX=0 /opt/anaconda3/envs/mammal/bin/python experiments/phase6_esm650_comparison.py
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# This machine is under memory pressure; MPS uses unified RAM and thrashes. Pin to CPU.
FORCE_CPU = os.environ.get("PHASE6_FORCE_CPU", "1") == "1"

import json, sys, glob, traceback, gc
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch
torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4))))

RESULTS = REPO / "results"
OUT_JSON = RESULTS / "phase6_esm650_comparison.json"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"

# ---- The EXACT Phase 5 panel: 5 families x 5 proteins (UniProt accession + short name) ----
PANEL = {
    "kinase": [
        ("P00533", "EGFR"), ("P15056", "BRAF"), ("P24941", "CDK2"),
        ("P00519", "ABL1"), ("P28482", "MAPK1"),
    ],
    "gpcr": [
        ("P14416", "DRD2"), ("P07550", "ADRB2"), ("P28223", "HTR2A"),
        ("P21554", "CNR1"), ("P35372", "OPRM1"),
    ],
    "ion_channel": [
        ("Q15858", "Nav1.7"), ("Q9Y5Y9", "Nav1.8"), ("O43526", "KCNQ2"),
        ("O60353", "HCN1"), ("Q8NER1", "TRPV1"),
    ],
    "nuclear_receptor": [
        ("P37231", "PPARG"), ("P19793", "RXRA"), ("P11473", "VDR"),
        ("P03372", "ESR1"), ("P10275", "AR"),
    ],
    "serine_protease": [
        ("P00734", "THROMBIN"), ("P00750", "tPA"), ("P00747", "PLASMIN"),
        ("P07477", "TRYPSIN"), ("P29622", "KALLIKREIN"),
    ],
}
PROTEINS = [{"accession": acc, "name": name, "family": fam}
            for fam, members in PANEL.items() for acc, name in members]

PRIMARY_MODEL = "facebook/esm2_t33_650M_UR50D"
FALLBACK_MODEL = "facebook/esm2_t30_150M_UR50D"


def _p(*a):
    print(*a, flush=True)


# ---------- sequence fetch (cached) ----------
def load_seq_cache() -> dict:
    if SEQ_CACHE.is_file():
        try:
            return json.loads(SEQ_CACHE.read_text())
        except Exception:
            return {}
    return {}


def fetch_sequence(accession: str, cache: dict) -> str | None:
    if accession in cache and cache[accession]:
        return cache[accession]
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    try:
        r = requests.get(url, timeout=20)
    except Exception as e:
        _p(f"    fetch error {accession}: {e}")
        return None
    if r.status_code != 200:
        return None
    seq = "".join(r.text.strip().split("\n")[1:])
    cache[accession] = seq
    return seq


# ---------- metrics (identical to phase5) ----------
def cosine_sim_matrix(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    normed = embs / norms
    return normed @ normed.T


def same_family_nn_recall(sim_matrix: np.ndarray, labels: list[str]) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim_matrix[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        if labels[nn] == labels[i]:
            correct += 1
    return correct / n


def intra_inter_gap(sim_matrix: np.ndarray, labels: list[str]) -> dict:
    n = len(labels)
    intra, inter = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (intra if labels[i] == labels[j] else inter).append(sim_matrix[i, j])
    return {"intra_mean": float(np.mean(intra)), "inter_mean": float(np.mean(inter)),
            "gap": float(np.mean(intra) - np.mean(inter))}


def per_family_recall(sim_matrix: np.ndarray, labels: list[str]) -> dict:
    n = len(labels)
    by_fam: dict[str, list[int]] = {}
    for i in range(n):
        row = sim_matrix[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        by_fam.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {fam: float(np.mean(v)) for fam, v in by_fam.items()}


# ---------- ESM-2 embeddings (mean-pool, exclude CLS/EOS) — identical recipe to phase5 ----------
def esm2_embeddings(model_name: str, sequences: list[str], device: str):
    """Returns (embs[N,D], note). Raises on load failure so caller can fall back."""
    from transformers import AutoTokenizer, AutoModel
    _p(f"Loading ESM-2 ({model_name}) on {device} ...")
    tok = AutoTokenizer.from_pretrained(model_name)
    # NOTE: do NOT use low_cpu_mem_usage=True here. It loads weights onto the `meta`
    # device, and a subsequent `.to("cpu")` then fails with "Cannot copy out of meta
    # tensor" (transformers/torch gotcha on this stack). HF loads straight to CPU by
    # default, so we load plainly and only move if the target is a real accelerator.
    model = AutoModel.from_pretrained(model_name, torch_dtype=torch.float32)
    if device != "cpu":
        model = model.to(device)
    model = model.eval()
    embs = []
    with torch.no_grad():
        for i, seq in enumerate(sequences):
            truncated = seq[:1022]  # ESM-2 1024-token limit incl. CLS/EOS
            inputs = tok(truncated, return_tensors="pt", add_special_tokens=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            out = model(**inputs)
            hidden = out.last_hidden_state[0, 1:-1, :]   # [L, D], drop CLS + EOS
            e = hidden.mean(dim=0).cpu().numpy().astype(np.float64)
            embs.append(e)
            del out, hidden, inputs
            if (i + 1) % 5 == 0:
                _p(f"  ESM-2 {i + 1}/{len(sequences)}")
    dim = int(embs[0].shape[0])
    # free the model before we do anything else
    del model, tok
    gc.collect()
    return np.array(embs), f"loaded {model_name}; emb_dim={dim}"


def run_esm(model_name: str, sequences: list[str], device: str):
    """One attempt. Returns (result_dict_or_None, error_str_or_None). Never loops."""
    try:
        embs, note = esm2_embeddings(model_name, sequences, device)
        return embs, None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        _p(f"  ESM-2 {model_name} FAILED: {err}")
        _p(traceback.format_exc())
        return None, err


def main():
    t0 = datetime.now()
    RESULTS.mkdir(exist_ok=True)
    device = "cpu" if FORCE_CPU else ("mps" if torch.backends.mps.is_available() else "cpu")
    _p(f"Device: {device}  (FORCE_CPU={FORCE_CPU})")

    # ---- load cached MAMMAL numbers from Phase 5 (do NOT load MAMMAL here) ----
    p5_files = sorted(glob.glob(str(RESULTS / "phase5_esm_comparison_*.json")))
    if not p5_files:
        _p("FATAL: no cached Phase 5 result found; cannot reuse MAMMAL numbers.")
        sys.exit(2)
    p5 = json.loads(Path(p5_files[-1]).read_text())
    mammal_prior = p5["mammal"]
    esm8m_prior = p5["esm2"]
    p5_proteins = p5["proteins"]
    _p(f"Reusing MAMMAL + ESM-8M numbers from {Path(p5_files[-1]).name}")
    _p(f"  MAMMAL prior: NN={mammal_prior['nn_recall']} gap={mammal_prior['gap']:.3f}")
    _p(f"  ESM-8M prior: NN={esm8m_prior['nn_recall']} gap={esm8m_prior['gap']:.3f}")

    # ---- fetch the SAME 25 sequences (cached) ----
    _p("\nFetching sequences from UniProt (cached) ...")
    cache = load_seq_cache()
    sequences, valid = [], []
    for prot in PROTEINS:
        seq = fetch_sequence(prot["accession"], cache)
        if seq:
            sequences.append(seq)
            valid.append(prot)
            _p(f"  {prot['name']:12} ({prot['accession']}): {len(seq)} aa")
        else:
            _p(f"  FAILED: {prot['name']} ({prot['accession']})")
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    labels = [p["family"] for p in valid]
    names = [p["name"] for p in valid]
    _p(f"\n{len(valid)}/25 sequences fetched")

    # Sanity: confirm the panel matches Phase 5 exactly (apples-to-apples)
    p5_accs = [p["accession"] for p in p5_proteins]
    our_accs = [p["accession"] for p in valid]
    panel_matches_phase5 = (our_accs == p5_accs)
    _p(f"Panel identical to Phase 5: {panel_matches_phase5} "
       f"({len(our_accs)} vs {len(p5_accs)} proteins)")

    # ---- ESM-2 650M (primary), then 150M fallback. ONE attempt each, no loop. ----
    attempts = []
    chosen_model = None
    esm_embs = None

    embs, err = run_esm(PRIMARY_MODEL, sequences, device)
    attempts.append({"model": PRIMARY_MODEL, "ok": embs is not None, "error": err})
    if embs is not None:
        chosen_model, esm_embs = PRIMARY_MODEL, embs
    else:
        _p(f"\nFalling back to {FALLBACK_MODEL} ...")
        gc.collect()
        embs2, err2 = run_esm(FALLBACK_MODEL, sequences, device)
        attempts.append({"model": FALLBACK_MODEL, "ok": embs2 is not None, "error": err2})
        if embs2 is not None:
            chosen_model, esm_embs = FALLBACK_MODEL, embs2

    result = {
        "test": "esm2_650M_vs_mammal_protein_embeddings",
        "purpose": ("Size-matched ESM-2 baseline for the MAMMAL protein-embedding question "
                    "FINDINGS.md flagged (Phase 5 only had ESM-2 8M). Same 25-protein x 5-family "
                    "panel + same LOO NN-recall / intra-inter cosine-gap metric."),
        "timestamp": t0.isoformat(),
        "device": device,
        "n_proteins": len(valid),
        "panel_identical_to_phase5": panel_matches_phase5,
        "phase5_source": Path(p5_files[-1]).name,
        "proteins": [{"name": p["name"], "accession": p["accession"], "family": p["family"]}
                     for p in valid],
        "esm_load_attempts": attempts,
        "mammal_458M": {  # reused, not recomputed
            "nn_recall": mammal_prior["nn_recall"],
            "intra_mean": mammal_prior["intra_mean"],
            "inter_mean": mammal_prior["inter_mean"],
            "gap": mammal_prior["gap"],
            "embedding_dim": mammal_prior["embedding_dim"],
            "source": "reused from phase5",
        },
        "esm2_8M": {  # reused, not recomputed
            "model": esm8m_prior.get("model", "facebook/esm2_t6_8M_UR50D"),
            "nn_recall": esm8m_prior["nn_recall"],
            "intra_mean": esm8m_prior["intra_mean"],
            "inter_mean": esm8m_prior["inter_mean"],
            "gap": esm8m_prior["gap"],
            "embedding_dim": esm8m_prior["embedding_dim"],
            "source": "reused from phase5",
        },
    }

    if esm_embs is None:
        _p("\nBOTH ESM models failed to load — recording failure and exiting cleanly.")
        result["esm2_large"] = {"model": None, "status": "load_failed",
                                "attempts": attempts}
        result["verdict"] = ("INCONCLUSIVE — could not load ESM-2 650M or the 150M fallback "
                             "(see esm_load_attempts). MAMMAL-vs-ESM-650M unresolved.")
        OUT_JSON.write_text(json.dumps(result, indent=2))
        _p(f"Saved -> {OUT_JSON}")
        return

    # ---- metrics for the loaded ESM model ----
    esm_sim = cosine_sim_matrix(esm_embs)
    esm_recall = same_family_nn_recall(esm_sim, labels)
    esm_gap = intra_inter_gap(esm_sim, labels)
    esm_fam_recall = per_family_recall(esm_sim, labels)

    # Anisotropy robustness check: ESM mean-pooled embeddings are notoriously anisotropic
    # (all vectors in a narrow cone -> raw cosine is a weak NN discriminator). The standard
    # fix is to mean-center the embedding cloud before cosine. We report ESM NN recall both
    # raw (Phase-5-consistent) and centered, so the verdict can't be dismissed as "you just
    # used raw cosine on an anisotropic model." (MAMMAL's raw bands are already well-spread,
    # 0.71/0.25, so centering helps it little; recomputing MAMMAL centered would require
    # reloading MAMMAL -> deferred to respect the one-model-in-RAM constraint.)
    esm_centered = esm_embs - esm_embs.mean(axis=0, keepdims=True)
    esm_sim_c = cosine_sim_matrix(esm_centered)
    esm_recall_centered = same_family_nn_recall(esm_sim_c, labels)
    esm_gap_centered = intra_inter_gap(esm_sim_c, labels)
    esm_fam_recall_centered = per_family_recall(esm_sim_c, labels)
    _p(f"\n  Anisotropy check — ESM centered NN recall: {esm_recall_centered:.3f} "
       f"(raw {esm_recall:.3f}); centered gap {esm_gap_centered['gap']:.3f}")

    is_650 = (chosen_model == PRIMARY_MODEL)
    result["esm2_large"] = {
        "model": chosen_model,
        "is_650M": is_650,
        "is_fallback_150M": (not is_650),
        "nn_recall": float(esm_recall),
        **esm_gap,
        "embedding_dim": int(esm_embs.shape[1]),
        "per_family_nn_recall": esm_fam_recall,
        "centered_anisotropy_check": {
            "nn_recall": float(esm_recall_centered),
            "per_family_nn_recall": esm_fam_recall_centered,
            **{f"centered_{k}": v for k, v in esm_gap_centered.items()},
            "note": ("Mean-centered embeddings before cosine (standard ESM anisotropy fix). "
                     "If this is still < MAMMAL 0.92, the MAMMAL win is not a raw-cosine artifact."),
        },
        "embeddings_raw": [[float(x) for x in row] for row in esm_embs],  # persisted so no reload needed
    }

    # ---- nearest-neighbor detail for the loaded ESM model ----
    nn_detail = []
    for i in range(len(valid)):
        row = esm_sim[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        nn_detail.append({"protein": names[i], "family": labels[i],
                          "nn": names[nn], "nn_family": labels[nn],
                          "match": labels[nn] == labels[i],
                          "sim": float(esm_sim[i, nn])})
    result["esm2_large"]["nn_detail"] = nn_detail

    # ---- head-to-head verdict ----
    m_recall = float(mammal_prior["nn_recall"])
    m_gap = float(mammal_prior["gap"])
    mammal_wins_recall = m_recall >= esm_recall
    label_650 = "650M" if is_650 else "150M(fallback)"
    if abs(m_recall - esm_recall) < 1e-9:
        recall_call = f"TIE on NN recall ({m_recall:.2f})"
    elif mammal_wins_recall:
        recall_call = f"MAMMAL wins NN recall ({m_recall:.2f} vs ESM-{label_650} {esm_recall:.2f})"
    else:
        recall_call = f"ESM-{label_650} wins NN recall ({esm_recall:.2f} vs MAMMAL {m_recall:.2f})"

    result["head_to_head"] = {
        "metric_table": {
            "MAMMAL_458M": {"nn_recall": m_recall, "gap": m_gap,
                            "dim": mammal_prior["embedding_dim"]},
            "ESM2_8M": {"nn_recall": float(esm8m_prior["nn_recall"]),
                        "gap": float(esm8m_prior["gap"]),
                        "dim": esm8m_prior["embedding_dim"]},
            f"ESM2_{label_650}": {"nn_recall": float(esm_recall), "gap": float(esm_gap["gap"]),
                                  "dim": int(esm_embs.shape[1])},
        },
        "recall_call": recall_call,
        "note_on_gap": ("Cosine gap is NOT comparable across models — ESM raw-cosine bands sit "
                        "very high (anisotropy), so its gap looks small even when NN recall is "
                        "perfect. NN recall is the decision metric; gap is within-model context."),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    # ---- console summary ----
    _p("\n=== ESM-2 (650M / fallback) vs MAMMAL vs ESM-2 8M ===")
    _p(f"  {'Model':<22} {'NN recall':>10} {'intra':>8} {'inter':>8} {'gap':>8} {'dim':>6}")
    _p(f"  {'MAMMAL 458M':<22} {m_recall:>10.3f} {mammal_prior['intra_mean']:>8.3f} "
       f"{mammal_prior['inter_mean']:>8.3f} {m_gap:>8.3f} {mammal_prior['embedding_dim']:>6}")
    _p(f"  {'ESM-2 8M':<22} {esm8m_prior['nn_recall']:>10.3f} {esm8m_prior['intra_mean']:>8.3f} "
       f"{esm8m_prior['inter_mean']:>8.3f} {esm8m_prior['gap']:>8.3f} {esm8m_prior['embedding_dim']:>6}")
    _p(f"  {'ESM-2 ' + label_650:<22} {esm_recall:>10.3f} {esm_gap['intra_mean']:>8.3f} "
       f"{esm_gap['inter_mean']:>8.3f} {esm_gap['gap']:>8.3f} {int(esm_embs.shape[1]):>6}")
    _p(f"\n  VERDICT: {recall_call}")
    _p(f"  ESM per-family NN recall: {esm_fam_recall}")
    _p(f"\n  ESM-{label_650} misses (NN in wrong family):")
    for d in nn_detail:
        if not d["match"]:
            _p(f"    {d['protein']:12} ({d['family']}) -> {d['nn']:12} ({d['nn_family']}) sim={d['sim']:.3f}")
    _p(f"\nSaved -> {OUT_JSON}")
    _p(f"Elapsed: {(datetime.now() - t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
