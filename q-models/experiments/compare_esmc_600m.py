"""Head-to-head: ESM-C 600M (EvolutionaryScale Cambrian) vs MAMMAL 458M and
ESM-2 650M on the 40-gene CRISPR-N panel — Track 1 (protein family clustering).

Question (Q3 punchlist, 2026-06-12): ESM-2-650M ties MAMMAL at NN-recall 0.750
on the 40-gene CRISPR-N panel (centered cosine). ESM-C 600M is EvolutionaryScale's
direct successor — same param class, claimed parity-or-better at smaller weights.
Does it clear the **0.80 NN-recall** bar that would make it the new Track-1 winner,
or does it tie/lose like ESM-2?

This is the apples-to-apples successor test: same panel, same ordering, same
embedding recipe (mean-pool over residues excluding BOS/EOS, L2-normalize, cosine),
same metrics, same anisotropy robustness check as `compare_esm2_650m.py`. Sequences
are truncated to 1022 aa to exactly match the ESM-2 protocol, so any difference is
the model, not the input.

ESM-C runs LOCALLY in an isolated venv (esmc-600m is *not* HF-gated, ~1.2 GB
weights, runs on CPU for 40 short proteins) — no AWS needed, a positive deviation
from the scorecard's planned $0.30 g5 run.

Panel + the MAMMAL/ESM-2 reference numbers are read from the committed JSONs:
  - results/compare_esm2_650m.json  (panel ordering + ESM-2 numbers + MAMMAL mirror)
  - results/phase5_crispr_panel_20260529_113901.json  (canonical MAMMAL CRISPR-N run)

Outputs: results/compare_esmc_600m.json (raw) + results/compare_esmc_600m.md (writeup).

Reproduce:
  /private/tmp/esmc-venv/bin/python experiments/compare_esmc_600m.py
(the isolated venv has: esm, torch, numpy, requests — NOT biomed-multi-alignment,
so this script must stay free of any mammal_quiver import.)
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import glob
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
OUT_JSON = RESULTS / "compare_esmc_600m.json"
OUT_MD = RESULTS / "compare_esmc_600m.md"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"

ESM2_JSON = RESULTS / "compare_esm2_650m.json"          # panel ordering + ESM-2 numbers
MAMMAL_GLOB = "phase5_crispr_panel_*.json"               # canonical MAMMAL CRISPR-N run

MODEL_NAME = "esmc_600m"        # EvolutionaryScale ESM-C 600M (Cambrian Open License)
TRUNCATE_AA = 1022              # match the ESM-2 protocol exactly (1024 ctx incl. BOS/EOS)


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


def fetch_uniprot_fasta(accession: str) -> str | None:
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return None
        lines = r.text.strip().split("\n")
        return "".join(lines[1:])
    except Exception as e:
        _p(f"    fetch error {accession}: {e}")
        return None


def fetch_seq(accession: str, cache: dict) -> str | None:
    if accession in cache and cache[accession]:
        return cache[accession]
    seq = fetch_uniprot_fasta(accession)
    if seq:
        cache[accession] = seq
    return seq


# ---------- metrics (identical to compare_esm2_650m.py / phase5_crispr_gene_panel) ----------
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


# ---------- ESM-C embeddings: mean-pool, exclude BOS/EOS ----------
def esmc_embeddings(sequences: list[str], device: str):
    import torch
    from esm.models.esmc import ESMC
    from esm.sdk.api import ESMProtein, LogitsConfig

    _p(f"Loading ESM-C ({MODEL_NAME}) on {device} ...")
    t0 = time.time()
    client = ESMC.from_pretrained(MODEL_NAME)
    client = client.to(device)
    client = client.eval()
    _p(f"  loaded in {time.time() - t0:.1f}s")

    cfg = LogitsConfig(sequence=True, return_embeddings=True)
    embs = []
    with torch.no_grad():
        for i, seq in enumerate(sequences):
            truncated = seq[:TRUNCATE_AA]
            protein = ESMProtein(sequence=truncated)
            pt = client.encode(protein)
            out = client.logits(pt, cfg)
            h = out.embeddings  # [1, L+2, D] : BOS ... residues ... EOS
            if hasattr(h, "detach"):
                h = h.detach().to("cpu").float().numpy()
            else:
                h = np.asarray(h, dtype=np.float64)
            # drop BOS (pos 0) and EOS (pos -1), mean-pool the residue positions
            resid = h[0, 1:-1, :]
            e = resid.mean(axis=0).astype(np.float64)
            embs.append(e)
            del out, pt, protein
            if (i + 1) % 5 == 0:
                _p(f"  ESM-C {i + 1}/{len(sequences)}")
    dim = int(embs[0].shape[0])
    return np.array(embs), dim


# ---------- load reference numbers from the committed JSONs ----------
def load_panel_and_esm2():
    """Panel ordering + ESM-2-650M numbers + the MAMMAL mirror, all from compare_esm2_650m.json."""
    d = json.loads(ESM2_JSON.read_text())
    proteins = d["proteins"]  # [{accession,name,family}, ...] in canonical order
    esm2 = d["esm2_large"]
    return proteins, esm2, d.get("mammal_458M", {})


def load_cached_mammal_panel() -> dict | None:
    files = sorted(glob.glob(str(RESULTS / MAMMAL_GLOB)))
    if not files:
        return None
    return json.loads(Path(files[-1]).read_text()) | {"_file": Path(files[-1]).name}


def main():
    t0 = datetime.now()
    RESULTS.mkdir(exist_ok=True)

    import torch
    # CPU matches the ESM-2-650M protocol (FORCE_CPU=1) and is plenty for 40 short proteins.
    device = os.environ.get("ESMC_DEVICE", "cpu")
    _p(f"Device: {device}")

    # ---- panel (identical ordering to the ESM-2 run) ----
    proteins, esm2, mammal_mirror = load_panel_and_esm2()
    labels = [p["family"] for p in proteins]
    names = [p["name"] for p in proteins]
    _p(f"Panel: {len(proteins)} genes (ordering from {ESM2_JSON.name})")

    # ---- sequences (UniProt, cached) ----
    cache = load_seq_cache()
    sequences, used = [], []
    n_fetched = 0
    for p in proteins:
        acc = p["accession"]
        was_cached = bool(cache.get(acc))
        seq = fetch_seq(acc, cache)
        if not seq:
            _p(f"  FATAL: could not get sequence for {p['name']} ({acc})")
            sys.exit(2)
        if not was_cached:
            n_fetched += 1
        sequences.append(seq)
        used.append({**p, "length_aa": len(seq), "truncated_to": min(len(seq), TRUNCATE_AA)})
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    _p(f"Sequences: {len(sequences)} ({n_fetched} freshly fetched from UniProt, rest cached)")

    # ---- ESM-C embeddings ----
    try:
        esmc_embs, esmc_dim = esmc_embeddings(sequences, device)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        _p(f"ESM-C FAILED: {err}")
        _p(traceback.format_exc())
        OUT_JSON.write_text(json.dumps({
            "test": "esmc_600m_vs_mammal_esm2_crispr_n_panel",
            "timestamp": t0.isoformat(),
            "status": "esmc_load_or_inference_failed",
            "error": err,
        }, indent=2))
        sys.exit(1)

    # ---- ESM-C metrics ----
    sim = cosine_sim_matrix(esmc_embs)
    recall = nn_recall(sim, labels)
    knn3 = knn_accuracy(sim, labels, k=3)
    gap = intra_inter_gap(sim, labels)
    fam_recall = per_family_recall(sim, labels)

    # Anisotropy robustness check (mean-center, then cosine — standard fix).
    centered = esmc_embs - esmc_embs.mean(axis=0, keepdims=True)
    sim_c = cosine_sim_matrix(centered)
    recall_c = nn_recall(sim_c, labels)
    knn3_c = knn_accuracy(sim_c, labels, k=3)
    gap_c = intra_inter_gap(sim_c, labels)
    fam_recall_c = per_family_recall(sim_c, labels)

    # per-protein NN detail (raw) — for the miss breakdown
    nn_detail = []
    for i in range(len(proteins)):
        row = sim[i].copy()
        row[i] = -np.inf
        j = int(np.argmax(row))
        nn_detail.append({
            "protein": names[i], "family": labels[i],
            "nn": names[j], "nn_family": labels[j],
            "match": bool(labels[j] == labels[i]),
            "sim": float(sim[i, j]),
        })

    mammal = load_cached_mammal_panel() or {}
    m_recall = float(mammal.get("nn_recall", mammal_mirror.get("nn_recall", float("nan"))))

    result = {
        "test": "esmc_600m_vs_mammal_esm2_crispr_n_panel",
        "purpose": ("Track-1 successor test: ESM-C 600M (EvolutionaryScale) vs ESM-2-650M "
                    "and MAMMAL 458M on the 40-gene CRISPR-N panel. Same panel/ordering, "
                    "same recipe (mean-pool ex-BOS/EOS + cosine), 1022-aa truncation to "
                    "match the ESM-2 protocol. Success = NN-recall >= 0.80."),
        "timestamp": t0.isoformat(),
        "device": device,
        "model": MODEL_NAME,
        "truncate_aa": TRUNCATE_AA,
        "n_proteins": len(proteins),
        "panel_source": "results/compare_esm2_650m.json:proteins",
        "mammal_panel_source_file": mammal.get("_file"),
        "proteins": used,
        "esmc_600m": {
            "model": MODEL_NAME,
            "embedding_dim": int(esmc_dim),
            "nn_recall": float(recall),
            "knn_k3_accuracy": float(knn3),
            **gap,
            "per_family_nn_recall": fam_recall,
            "nn_detail": nn_detail,
            "centered_anisotropy_check": {
                "nn_recall": float(recall_c),
                "knn_k3_accuracy": float(knn3_c),
                "per_family_nn_recall": fam_recall_c,
                **{f"centered_{k}": v for k, v in gap_c.items()},
                "note": ("Mean-centered embeddings before cosine (standard anisotropy fix). "
                         "ESM-2-650M's headline 0.750 was its *centered* number."),
            },
            "embeddings_raw": [[float(x) for x in row] for row in esmc_embs],
        },
        "reference": {
            "mammal_458M_nn_recall": m_recall,
            "mammal_458M_knn_k3": float(mammal.get("knn_k3_accuracy", float("nan"))),
            "mammal_458M_gap": float(mammal.get("gap", float("nan"))),
            "esm2_650M_nn_recall_raw": float(esm2["nn_recall"]),
            "esm2_650M_nn_recall_centered": float(esm2["centered_anisotropy_check"]["nn_recall"]),
            "esm2_650M_per_family": esm2["per_family_nn_recall"],
            "esm2_650M_per_family_centered": esm2["centered_anisotropy_check"]["per_family_nn_recall"],
        },
    }

    # verdict (use the better of raw/centered for ESM-C, as we did for ESM-2)
    best = max(recall, recall_c)
    best_kind = "centered" if recall_c >= recall else "raw"
    if best >= 0.80:
        verdict = (f"ESM-C 600M is the new Track-1 winner: NN-recall {best:.3f} ({best_kind}) "
                   f">= 0.80, beating the MAMMAL/ESM-2 tie at 0.750.")
    elif best > m_recall + 1e-9:
        verdict = (f"ESM-C 600M edges the field at NN-recall {best:.3f} ({best_kind}) but does "
                   f"NOT clear the 0.80 bar — better than the 0.750 tie, short of a coronation.")
    elif abs(best - m_recall) < 0.026:
        verdict = (f"ESM-C 600M ties the field at NN-recall {best:.3f} ({best_kind}) "
                   f"(MAMMAL/ESM-2 0.750). No reason to switch on this readout; "
                   f"the upgrade-path test comes up empty.")
    else:
        verdict = (f"ESM-C 600M LOSES at NN-recall {best:.3f} ({best_kind}) vs the 0.750 tie.")
    result["verdict"] = verdict

    OUT_JSON.write_text(json.dumps(result, indent=2))

    # ---- console summary ----
    _p("\n=== ESM-C 600M vs ESM-2 650M vs MAMMAL 458M — 40-gene CRISPR-N panel ===")
    _p(f"  {'Model':<22} {'NN(raw)':>9} {'NN(cent)':>9} {'kNN3':>7} {'gap':>8} {'dim':>6}")
    _p(f"  {'MAMMAL 458M':<22} {m_recall:>9.3f} {'—':>9} "
       f"{mammal.get('knn_k3_accuracy', float('nan')):>7.3f} "
       f"{mammal.get('gap', float('nan')):>8.3f} {768:>6}")
    _p(f"  {'ESM-2 650M':<22} {esm2['nn_recall']:>9.3f} "
       f"{esm2['centered_anisotropy_check']['nn_recall']:>9.3f} "
       f"{esm2.get('knn_k3_accuracy', float('nan')):>7.3f} "
       f"{esm2.get('gap', float('nan')):>8.3f} {esm2.get('embedding_dim', 1280):>6}")
    _p(f"  {'ESM-C 600M':<22} {recall:>9.3f} {recall_c:>9.3f} {knn3:>7.3f} "
       f"{gap['gap']:>8.3f} {esmc_dim:>6}")
    _p(f"\n  per-family NN recall (raw): {fam_recall}")
    _p(f"  per-family NN recall (centered): {fam_recall_c}")
    _p(f"\n  ESM-C misses (NN in wrong family, raw):")
    for d in nn_detail:
        if not d["match"]:
            _p(f"    {d['protein']:12} ({d['family']:<16}) -> {d['nn']:12} ({d['nn_family']})  sim={d['sim']:.3f}")
    _p(f"\n  VERDICT: {verdict}")
    _p(f"\nSaved -> {OUT_JSON}")
    _p(f"Elapsed: {(datetime.now() - t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
