"""Head-to-head: ESM-2 650M vs MAMMAL 458M on the 40-gene CRISPR-N panel.

Question (asked 2026-06-07): Phase 5's MAMMAL-vs-ESM win was on a 25-protein/5-family
toy panel; the prior phase 6 ESM-650M comparison re-ran on the *same* 25-protein panel.
This script extends the head-to-head onto the **real 40-gene CRISPR-N panel** from
`experiments/phase5_crispr_gene_panel.py` (kinases, GPCRs, ion channels, nuclear
receptors, E3 ligases, and a few outliers).

If ESM-2-650M matches or beats MAMMAL on NN recall here, the Sapphire-embedding-layer
pitch loses its only remaining empirical win.

Protocol (matches phase5_crispr_gene_panel + phase6_esm650_comparison):
  - Same 40-gene panel (UniProt accessions hardcoded in phase5_crispr_gene_panel.py)
  - Sequences from UniProt (cached in results/_uniprot_cache.json)
  - Embedding recipe: mean-pool over residue positions (exclude CLS/EOS),
    L2-normalize, cosine similarity matrix.
    * MAMMAL: reuse cached numbers from results/phase5_crispr_panel_*.json
      (the canonical CRISPR-N MAMMAL run; do NOT reload MAMMAL — memory hygiene).
    * ESM-2 650M: facebook/esm2_t33_650M_UR50D, fresh embeddings here, CPU.
  - Metrics: leave-one-out NN same-family recall, intra/inter cosine gap, per-family
    NN recall. Also a centered-cosine anisotropy robustness check (standard ESM
    de-anisotropy fix) — same protocol as phase6_esm650_comparison.

Outputs: results/compare_esm2_650m.json (raw) + results/compare_esm2_650m.md (writeup).
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# Same memory hygiene as phase6_esm650: force CPU. MPS thrashes on this stack
# under memory pressure and we don't need a GPU for 40 short proteins.
FORCE_CPU = os.environ.get("COMPARE_FORCE_CPU", "1") == "1"

import gc
import glob
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

# Reuse the EXACT panel from phase5_crispr_gene_panel (import the constant)
from experiments.phase5_crispr_gene_panel import PANEL  # noqa: E402

torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4))))

RESULTS = REPO / "results"
OUT_JSON = RESULTS / "compare_esm2_650m.json"
OUT_MD = RESULTS / "compare_esm2_650m.md"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"

PRIMARY_MODEL = "facebook/esm2_t33_650M_UR50D"
FALLBACK_MODEL = "facebook/esm2_t30_150M_UR50D"


def _p(*a):
    print(*a, flush=True)


# ---------- sequence fetch (cached on disk so re-runs don't hit UniProt) ----------
def load_seq_cache() -> dict:
    if SEQ_CACHE.is_file():
        try:
            return json.loads(SEQ_CACHE.read_text())
        except Exception:
            return {}
    return {}


def fetch_seq(accession: str, cache: dict) -> str | None:
    if accession in cache and cache[accession]:
        return cache[accession]
    try:
        seq = fetch_uniprot_sequence(accession)
    except Exception as e:
        _p(f"    fetch error {accession}: {e}")
        return None
    if seq:
        cache[accession] = seq
        return seq
    return None


# ---------- metrics (identical to phase5_crispr_gene_panel) ----------
def cosine_sim_matrix(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    normed = embs / norms
    return normed @ normed.T


def nn_recall(sim: np.ndarray, labels: list[str]) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        if labels[nn] == labels[i]:
            correct += 1
    return correct / n


def intra_inter_gap(sim: np.ndarray, labels: list[str]) -> dict:
    n = len(labels)
    intra, inter = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (intra if labels[i] == labels[j] else inter).append(sim[i, j])
    return {
        "intra_mean": float(np.mean(intra)),
        "inter_mean": float(np.mean(inter)),
        "gap": float(np.mean(intra) - np.mean(inter)),
    }


def per_family_recall(sim: np.ndarray, labels: list[str]) -> dict:
    n = len(labels)
    by_fam: dict[str, list[int]] = {}
    for i in range(n):
        row = sim[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        by_fam.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {fam: float(np.mean(v)) for fam, v in by_fam.items()}


def knn_accuracy(sim: np.ndarray, labels: list[str], k: int = 3) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim[i].copy()
        row[i] = -np.inf
        top_k = np.argsort(row)[::-1][:k]
        votes = [labels[j] for j in top_k]
        pred = max(set(votes), key=votes.count)
        if pred == labels[i]:
            correct += 1
    return correct / n


# ---------- ESM-2 embeddings: mean-pool, exclude CLS/EOS ----------
def esm2_embeddings(model_name: str, sequences: list[str], device: str):
    from transformers import AutoModel, AutoTokenizer

    _p(f"Loading ESM-2 ({model_name}) on {device} ...")
    tok = AutoTokenizer.from_pretrained(model_name)
    # NOTE: do NOT use low_cpu_mem_usage=True; weights land on `meta` device, then
    # `.to("cpu")` fails with "Cannot copy out of meta tensor" (transformers+torch
    # gotcha on this stack, hit during phase6_esm650).
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
            hidden = out.last_hidden_state[0, 1:-1, :]  # [L, D], drop CLS + EOS
            e = hidden.mean(dim=0).cpu().numpy().astype(np.float64)
            embs.append(e)
            del out, hidden, inputs
            if (i + 1) % 5 == 0:
                _p(f"  ESM-2 {i + 1}/{len(sequences)}")
    dim = int(embs[0].shape[0])
    del model, tok
    gc.collect()
    return np.array(embs), dim


def run_esm(model_name: str, sequences: list[str], device: str):
    try:
        embs, dim = esm2_embeddings(model_name, sequences, device)
        return embs, dim, None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        _p(f"  ESM-2 {model_name} FAILED: {err}")
        _p(traceback.format_exc())
        return None, None, err


def load_cached_mammal_panel() -> dict | None:
    """Load the canonical Phase 5 CRISPR-N MAMMAL run (NN recall + sim matrix + labels)."""
    files = sorted(glob.glob(str(RESULTS / "phase5_crispr_panel_*.json")))
    if not files:
        return None
    return json.loads(Path(files[-1]).read_text()) | {"_file": Path(files[-1]).name}


def main():
    t0 = datetime.now()
    RESULTS.mkdir(exist_ok=True)
    device = "cpu" if FORCE_CPU else ("mps" if torch.backends.mps.is_available() else "cpu")
    _p(f"Device: {device}  (FORCE_CPU={FORCE_CPU})")

    # ---- the 40-gene panel (same UniProt accessions as phase5_crispr_gene_panel) ----
    panel = list(PANEL)  # [(acc, name, family), ...]
    _p(f"\nPanel: {len(panel)} genes (from phase5_crispr_gene_panel.PANEL)")

    # ---- fetch sequences (UniProt, cached) ----
    cache = load_seq_cache()
    proteins, sequences = [], []
    for acc, name, family in panel:
        seq = fetch_seq(acc, cache)
        if seq:
            proteins.append({"accession": acc, "name": name, "family": family})
            sequences.append(seq)
            _p(f"  {name:12} ({acc}): {len(seq)} aa")
        else:
            _p(f"  FAILED: {name} ({acc})")
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    labels = [p["family"] for p in proteins]
    names = [p["name"] for p in proteins]
    _p(f"\n{len(proteins)}/{len(panel)} sequences fetched")

    # ---- load cached MAMMAL CRISPR-N panel numbers (DO NOT reload MAMMAL) ----
    mammal_cached = load_cached_mammal_panel()
    if mammal_cached is None:
        _p("FATAL: no cached results/phase5_crispr_panel_*.json found; cannot reuse "
           "MAMMAL CRISPR-N numbers. Run experiments/phase5_crispr_gene_panel.py first.")
        sys.exit(2)
    _p(f"\nReusing MAMMAL CRISPR-N numbers from {mammal_cached['_file']}")
    _p(f"  MAMMAL prior: NN recall={mammal_cached['nn_recall']:.3f}  "
       f"intra={mammal_cached['intra_family_cosine_mean']:.3f}  "
       f"inter={mammal_cached['inter_family_cosine_mean']:.3f}  "
       f"gap={mammal_cached['gap']:.3f}")

    # sanity: panel identical to the cached MAMMAL run?
    mammal_names = mammal_cached.get("names", [])
    panel_identical = (mammal_names == names)
    _p(f"Panel identical to cached MAMMAL run: {panel_identical} "
       f"({len(names)} vs {len(mammal_names)})")

    # ---- ESM-2 650M (primary), 150M fallback. one attempt each, no retry loop ----
    attempts = []
    chosen_model, esm_embs, esm_dim = None, None, None

    embs, dim, err = run_esm(PRIMARY_MODEL, sequences, device)
    attempts.append({"model": PRIMARY_MODEL, "ok": embs is not None, "error": err})
    if embs is not None:
        chosen_model, esm_embs, esm_dim = PRIMARY_MODEL, embs, dim
    else:
        _p(f"\nFalling back to {FALLBACK_MODEL} ...")
        gc.collect()
        embs2, dim2, err2 = run_esm(FALLBACK_MODEL, sequences, device)
        attempts.append({"model": FALLBACK_MODEL, "ok": embs2 is not None, "error": err2})
        if embs2 is not None:
            chosen_model, esm_embs, esm_dim = FALLBACK_MODEL, embs2, dim2

    # ---- also pull the 25-protein phase6 numbers for context in the table ----
    p6_path = RESULTS / "phase6_esm650_comparison.json"
    p6_context = None
    if p6_path.is_file():
        try:
            p6 = json.loads(p6_path.read_text())
            p6_context = {
                "n_proteins": p6.get("n_proteins"),
                "MAMMAL_458M": p6.get("mammal_458M"),
                "ESM2_8M": p6.get("esm2_8M"),
                "ESM2_large": {
                    "model": p6.get("esm2_large", {}).get("model"),
                    "nn_recall": p6.get("esm2_large", {}).get("nn_recall"),
                    "gap": p6.get("esm2_large", {}).get("gap"),
                },
            }
        except Exception:
            p6_context = None

    result = {
        "test": "esm2_650M_vs_mammal_crispr_n_panel",
        "purpose": ("Extend the MAMMAL-vs-ESM-650M head-to-head from the 25-protein/5-family "
                    "toy panel onto the 40-gene CRISPR-N panel. Same recipe (mean-pool + cosine), "
                    "MAMMAL numbers reused from results/phase5_crispr_panel_*.json."),
        "timestamp": t0.isoformat(),
        "device": device,
        "n_proteins": len(proteins),
        "panel_source": "experiments/phase5_crispr_gene_panel.PANEL",
        "panel_identical_to_cached_mammal_run": panel_identical,
        "mammal_panel_source_file": mammal_cached["_file"],
        "phase6_25_protein_context": p6_context,
        "proteins": proteins,
        "esm_load_attempts": attempts,
        "mammal_458M": {
            "nn_recall": float(mammal_cached["nn_recall"]),
            "intra_mean": float(mammal_cached["intra_family_cosine_mean"]),
            "inter_mean": float(mammal_cached["inter_family_cosine_mean"]),
            "gap": float(mammal_cached["gap"]),
            "knn_k3_accuracy": float(mammal_cached.get("knn_k3_accuracy", float("nan"))),
            "embedding_dim": 768,
            "source": f"reused from {mammal_cached['_file']}",
        },
    }

    if esm_embs is None:
        result["esm2_large"] = {"model": None, "status": "load_failed", "attempts": attempts}
        result["verdict"] = ("INCONCLUSIVE — could not load ESM-2 650M or the 150M fallback "
                             "(see esm_load_attempts). MAMMAL-vs-ESM-650M on CRISPR-N unresolved.")
        OUT_JSON.write_text(json.dumps(result, indent=2))
        _p(f"\nSaved -> {OUT_JSON}")
        return

    # ---- ESM metrics ----
    esm_sim = cosine_sim_matrix(esm_embs)
    esm_recall = nn_recall(esm_sim, labels)
    esm_gap = intra_inter_gap(esm_sim, labels)
    esm_knn3 = knn_accuracy(esm_sim, labels, k=3)
    esm_fam_recall = per_family_recall(esm_sim, labels)

    # Anisotropy robustness check (mean-center then cosine — standard ESM fix).
    esm_centered = esm_embs - esm_embs.mean(axis=0, keepdims=True)
    esm_sim_c = cosine_sim_matrix(esm_centered)
    esm_recall_centered = nn_recall(esm_sim_c, labels)
    esm_gap_centered = intra_inter_gap(esm_sim_c, labels)
    esm_fam_recall_centered = per_family_recall(esm_sim_c, labels)

    is_650 = (chosen_model == PRIMARY_MODEL)
    label = "650M" if is_650 else "150M(fallback)"

    # per-protein NN detail (for the writeup's miss breakdown)
    nn_detail = []
    for i in range(len(proteins)):
        row = esm_sim[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        nn_detail.append({
            "protein": names[i], "family": labels[i],
            "nn": names[nn], "nn_family": labels[nn],
            "match": bool(labels[nn] == labels[i]),
            "sim": float(esm_sim[i, nn]),
        })

    result["esm2_large"] = {
        "model": chosen_model,
        "is_650M": is_650,
        "is_fallback_150M": (not is_650),
        "nn_recall": float(esm_recall),
        "knn_k3_accuracy": float(esm_knn3),
        **esm_gap,
        "embedding_dim": int(esm_dim),
        "per_family_nn_recall": esm_fam_recall,
        "nn_detail": nn_detail,
        "centered_anisotropy_check": {
            "nn_recall": float(esm_recall_centered),
            "per_family_nn_recall": esm_fam_recall_centered,
            **{f"centered_{k}": v for k, v in esm_gap_centered.items()},
            "note": ("Mean-centered embeddings before cosine (standard ESM anisotropy fix). "
                     "If centered NN recall is still < MAMMAL, the MAMMAL win is not a "
                     "raw-cosine artifact."),
        },
        "embeddings_raw": [[float(x) for x in row] for row in esm_embs],
    }

    m_recall = float(mammal_cached["nn_recall"])
    m_gap = float(mammal_cached["gap"])
    if abs(m_recall - esm_recall) < 1e-9:
        recall_call = f"TIE on NN recall ({m_recall:.3f})"
    elif m_recall > esm_recall:
        recall_call = f"MAMMAL wins NN recall ({m_recall:.3f} vs ESM-{label} {esm_recall:.3f})"
    else:
        recall_call = f"ESM-{label} wins NN recall ({esm_recall:.3f} vs MAMMAL {m_recall:.3f})"

    result["head_to_head"] = {
        "metric_table": {
            "MAMMAL_458M": {"nn_recall": m_recall, "gap": m_gap, "dim": 768},
            f"ESM2_{label}": {"nn_recall": float(esm_recall), "gap": float(esm_gap["gap"]),
                              "dim": int(esm_dim)},
        },
        "recall_call": recall_call,
        "note_on_gap": ("Cosine gap is NOT comparable across architectures — ESM raw-cosine "
                        "bands sit very high (anisotropy), so its gap looks tiny even when NN "
                        "recall is decent. NN recall is the decision metric; gap is context."),
    }

    OUT_JSON.write_text(json.dumps(result, indent=2))

    # ---- console summary ----
    _p("\n=== MAMMAL 458M vs ESM-2 (650M / fallback) on 40-gene CRISPR-N panel ===")
    _p(f"  {'Model':<22} {'NN recall':>10} {'knn3':>7} {'intra':>8} {'inter':>8} {'gap':>8} {'dim':>6}")
    _p(f"  {'MAMMAL 458M':<22} {m_recall:>10.3f} "
       f"{mammal_cached.get('knn_k3_accuracy', float('nan')):>7.3f} "
       f"{mammal_cached['intra_family_cosine_mean']:>8.3f} "
       f"{mammal_cached['inter_family_cosine_mean']:>8.3f} {m_gap:>8.3f} {768:>6}")
    _p(f"  {'ESM-2 ' + label:<22} {esm_recall:>10.3f} {esm_knn3:>7.3f} "
       f"{esm_gap['intra_mean']:>8.3f} {esm_gap['inter_mean']:>8.3f} {esm_gap['gap']:>8.3f} "
       f"{esm_dim:>6}")
    _p(f"\n  VERDICT: {recall_call}")
    _p(f"  Centered ESM NN recall: {esm_recall_centered:.3f}  "
       f"(centered gap {esm_gap_centered['gap']:.3f})")
    _p(f"  ESM per-family NN recall: {esm_fam_recall}")
    _p(f"\n  ESM-{label} misses (NN in wrong family):")
    for d in nn_detail:
        if not d["match"]:
            _p(f"    {d['protein']:12} ({d['family']}) -> {d['nn']:12} ({d['nn_family']})  "
               f"sim={d['sim']:.3f}")
    _p(f"\nSaved -> {OUT_JSON}")
    _p(f"Elapsed: {(datetime.now() - t0).total_seconds():.1f}s")

    # ---- write the markdown writeup ----
    write_markdown(result, mammal_cached, p6_context)
    _p(f"Wrote -> {OUT_MD}")


def write_markdown(result: dict, mammal_cached: dict, p6_context: dict | None):
    m = result["mammal_458M"]
    e = result["esm2_large"]
    label = "650M" if e.get("is_650M") else "150M(fallback)"

    # phase 5 ESM-8M number (25-protein panel — only ESM-8M baseline we have)
    p5_files = sorted(glob.glob(str(RESULTS / "phase5_esm_comparison_*.json")))
    esm8m_25 = None
    if p5_files:
        try:
            p5 = json.loads(Path(p5_files[-1]).read_text())
            esm8m_25 = p5.get("esm2", {})
        except Exception:
            pass

    lines = []
    A = lines.append
    A("# ESM-2 650M vs MAMMAL 458M on the 40-gene CRISPR-N panel\n")
    A("**Question.** Phase 5 / phase 6 showed MAMMAL beats ESM-2 (8M, 650M) on a "
      "25-protein/5-family toy panel. Does that hold on the **40-gene CRISPR-N panel** "
      "(`experiments/phase5_crispr_gene_panel.py`) — i.e. on a real, heterogeneous "
      "panel that includes E3 ligases and outlier TFs, not just clean structural families? "
      "If ESM-2-650M matches or beats MAMMAL here, the Sapphire-embedding-layer pitch "
      "loses its only remaining empirical win.\n")
    A("---\n")

    A("## Setup\n")
    A(f"- **Panel**: {result['n_proteins']} proteins (kinases 10 + a duplicate-family "
      "MAPK3 + 2 outliers, GPCRs 8, ion channels 8, nuclear receptors 6, "
      "E3-ligases-labeled 4, lipid kinase 1, phosphatase 1). Same accessions as "
      "`phase5_crispr_gene_panel.PANEL`.\n"
      "- **Sequences**: UniProt REST, cached in `results/_uniprot_cache.json`.\n"
      "- **Embedding recipe (identical to phase 6's ESM-650M study)**: mean-pool over "
      "residue positions (exclude CLS / EOS for ESM; masked mean-pool of encoder last "
      "hidden state for MAMMAL via `mammal_quiver/embed.py`), then L2-normalize and "
      "cosine.\n"
      f"- **MAMMAL 458M** numbers reused from `{mammal_cached['_file']}` "
      "(no reload — one model in RAM at a time, same protocol as phase 6).\n"
      f"- **ESM-2** model loaded here: `{e['model']}` ({label}), "
      f"dim={e['embedding_dim']}, CPU.\n")

    A("## Head-to-head (the deliverable)\n")
    A("| Model | Params | NN recall ↑ | k-NN (k=3) | intra cos | inter cos | gap | dim |")
    A("|---|---|---|---|---|---|---|---|")
    A(f"| **MAMMAL** | 458M | **{m['nn_recall']:.3f}** | {m['knn_k3_accuracy']:.3f} | "
      f"{m['intra_mean']:.3f} | {m['inter_mean']:.3f} | **{m['gap']:.3f}** | {m['embedding_dim']} |")
    if esm8m_25 is not None:
        A(f"| ESM-2 8M (25-prot panel, context) | 8M | {esm8m_25.get('nn_recall', 0):.3f} | — | "
          f"{esm8m_25.get('intra_mean', 0):.3f} | {esm8m_25.get('inter_mean', 0):.3f} | "
          f"{esm8m_25.get('gap', 0):.3f} | {esm8m_25.get('embedding_dim', 320)} |")
    A(f"| **ESM-2 {label}** | 650M | **{e['nn_recall']:.3f}** | {e['knn_k3_accuracy']:.3f} | "
      f"{e['intra_mean']:.3f} | {e['inter_mean']:.3f} | {e['gap']:.3f} | {e['embedding_dim']} |")
    A("")
    A("**Anisotropy check** (mean-center, then cosine — standard ESM fix): "
      f"ESM-{label} centered NN recall = "
      f"**{e['centered_anisotropy_check']['nn_recall']:.3f}** "
      f"(raw {e['nn_recall']:.3f}; centered gap "
      f"{e['centered_anisotropy_check']['centered_gap']:.3f}). "
      "If centered is still below MAMMAL, the MAMMAL number is not a raw-cosine artifact.\n")

    # per-family table
    A("### Per-family NN recall\n")
    A("| Family | n | MAMMAL | ESM-2 " + label + " |")
    A("|---|---|---|---|")
    # MAMMAL per-family from cached sim matrix
    mammal_sim = np.array(mammal_cached["similarity_matrix"])
    mammal_labels = mammal_cached["labels"]
    mammal_per_fam = per_family_recall(mammal_sim, mammal_labels)
    for fam in sorted(set(mammal_labels)):
        n_fam = sum(1 for l in mammal_labels if l == fam)
        mv = mammal_per_fam.get(fam, float("nan"))
        ev = e["per_family_nn_recall"].get(fam, float("nan"))
        A(f"| {fam} | {n_fam} | {mv:.2f} | {ev:.2f} |")
    A("")

    # verdict
    A("## Verdict\n")
    m_recall = m["nn_recall"]
    e_recall = e["nn_recall"]
    diff = m_recall - e_recall
    if diff > 0.025:
        verdict = ("**MAMMAL still wins on the CRISPR-N panel.** "
                   f"NN recall {m_recall:.3f} vs ESM-2-{label} {e_recall:.3f} "
                   f"(Δ = +{diff:.3f}). The Sapphire-embedding pitch's lone empirical win — "
                   "MAMMAL clusters Quiver's CRISPR-N gene panel by family better than a "
                   "size-matched off-the-shelf ESM-2 — survives this test.")
    elif diff < -0.025:
        verdict = ("**ESM-2-650M beats MAMMAL on the CRISPR-N panel.** "
                   f"NN recall {e_recall:.3f} vs MAMMAL {m_recall:.3f} "
                   f"(Δ = {diff:.3f}). The Sapphire-embedding-layer pitch loses its only "
                   "remaining off-the-shelf empirical win on the real Quiver-relevant panel.")
    else:
        verdict = (f"**MAMMAL and ESM-2-{label} tie on the CRISPR-N panel** "
                   f"(NN recall {m_recall:.3f} vs {e_recall:.3f}, |Δ| ≤ 0.025). "
                   "With n=40 and per-flip ≈ 0.025 sensitivity, this is a wash — "
                   "the Sapphire pitch loses the *exclusivity* of its win (MAMMAL is no longer "
                   "demonstrably better than an open MIT model on this readout).")
    A(verdict + "\n")

    # 25-protein context
    if p6_context and p6_context.get("ESM2_large", {}).get("nn_recall") is not None:
        A("### Cross-panel context (25-protein toy panel from phase 6)\n")
        A(f"| Model | 25-prot panel NN | 40-gene CRISPR-N NN |")
        A(f"|---|---|---|")
        A(f"| MAMMAL 458M | {p6_context['MAMMAL_458M']['nn_recall']:.3f} | {m_recall:.3f} |")
        A(f"| ESM-2 8M | {p6_context['ESM2_8M']['nn_recall']:.3f} | (not run here) |")
        A(f"| ESM-2 650M | {p6_context['ESM2_large']['nn_recall']:.3f} | {e_recall:.3f} |")
        A("")
        A("Both models drop from the toy panel to the real CRISPR-N panel — expected, since "
          "the 40-gene panel includes functionally-labeled but structurally heterogeneous "
          "families (E3 ligases, TP53-as-NR), and duplicate-family stress tests (MAPK3 in "
          "kinase, RARA labeled as E3).\n")

    A("## Implication for the Sapphire embedding-layer pitch\n")

    if diff > 0.025:
        A("- **Off-the-shelf, mean-pool + cosine, on a 40-gene panel that includes "
          "Quiver-relevant kinase / GPCR / ion-channel families: MAMMAL > ESM-2-650M.** "
          "Phase 5 / phase 6 / this run all point the same way; the size-matched challenge "
          "did not close the gap on either panel.\n"
          "- **What that buys:** the CLAUDE.md caveat — \"benchmark vs ESM-2 650M before "
          "committing to Sapphire at scale\" — is cleared on the same readout (NN recall, "
          "off-the-shelf recipe). MAMMAL embeddings remain the empirically-best drop-in "
          "for CRISPR-N family clustering among the open models tested here.\n"
          "- **What it does NOT buy:** a coronation. n = 40 is small, mean-pool is the *worst* "
          "way to use ESM-2 (typical pipelines select an intermediate layer + whiten), and "
          "the gap shrinks markedly versus the toy panel. Re-test at the full 1,400-gene "
          "CRISPR-N panel with each model's best extraction (layer selection + whitening for "
          "ESM) before treating MAMMAL embeddings as load-bearing infrastructure rather "
          "than enrichment. ESM-2 3B remains untested (memory).\n"
          "- **Strategic frame stays the same** (CLAUDE.md spine): MAMMAL is commodity "
          "enrichment that holds its own on this one readout. The moat is V1-T + functional "
          "trace data, not the embedding layer.\n")
    elif diff < -0.025:
        A("- **The CLAUDE.md hedge — \"benchmark before committing\" — was right.** On the "
          "real 40-gene CRISPR-N panel, ESM-2-650M (open, MIT) clusters families at least as "
          "well as MAMMAL with the same off-the-shelf recipe. MAMMAL's last off-the-shelf "
          "empirical edge (family clustering) does not survive a size-matched open baseline "
          "on the real panel.\n"
          "- **For Sapphire:** there is no off-the-shelf reason to prefer MAMMAL embeddings "
          "over ESM-2-650M for the CRISPR-N gene-clustering / KG use case. ESM-2 wins on "
          "openness, licensing simplicity, and (now) parity on the task that mattered.\n"
          "- **For the broader MAMMAL story:** consistent with the project's spine — off-the-shelf "
          "MAMMAL is commodity enrichment, not infrastructure. The value, if any, is in "
          "per-target fine-tuning on Quiver-specific data, not embeddings.\n")
    else:
        A("- **Tie ≈ loss for the pitch.** The Phase 5 framing of MAMMAL's win as a "
          "*proprietary* advantage falls apart if an open MIT-licensed ESM-2-650M matches it "
          "on the real panel. \"Why ship MAMMAL embeddings when ESM-2-650M is free and "
          "comparable?\" becomes the operative question.\n"
          "- **For Sapphire:** treat MAMMAL embeddings and ESM-2-650M as interchangeable for "
          "the CRISPR-N gene-clustering / KG use case at this scale; pick on licensing / "
          "ops convenience, not signal.\n"
          "- **For the broader MAMMAL story:** the off-the-shelf value proposition continues "
          "to thin out. The remaining argued-real wins are per-target fine-tuned heads on "
          "Quiver data — not embeddings.\n")

    A("## Reproduce\n")
    A("```bash")
    A("USE_TF=0 USE_FLAX=0 COMPARE_FORCE_CPU=1 \\")
    A("  /opt/anaconda3/envs/mammal/bin/python experiments/compare_esm2_650m.py")
    A("```")
    A("Loads only ESM-2-650M (CPU); reuses MAMMAL CRISPR-N numbers from the latest cached "
      "`results/phase5_crispr_panel_*.json`. UniProt sequences are cached in "
      "`results/_uniprot_cache.json`.")
    A("")

    OUT_MD.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
