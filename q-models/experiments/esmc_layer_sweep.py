"""ESM-C 600M layer sweep on the 40-gene CRISPR-N panel — readout diligence.

The matched off-the-shelf recipe (last-layer mean-pool + cosine) gave ESM-C
NN-recall 0.625/0.650, BELOW ESM-2-650M (0.725/0.750) and MAMMAL (0.750). A
successor scoring below its predecessor + everything sitting at cosine 0.92-0.97
(anisotropy) is the classic signature of a *layer-choice* problem, not a true
capability gap — and the compare_esm2_650m writeup explicitly flags last-layer
mean-pool as the worst way to use these encoders.

So: extract ALL 36 transformer-block hidden states in one forward per protein,
mean-pool each (ex BOS/EOS), and compute NN-recall (raw + centered) per layer.
If the BEST layer still doesn't clear 0.75, the "ESM-C loses Track 1" verdict is
robust. If some intermediate layer clears 0.80, the story flips to "ESM-C needs
layer selection; last-layer mean-pool is a trap."

Run: /private/tmp/esmc-venv/bin/python experiments/esmc_layer_sweep.py
Out: results/esmc_layer_sweep.json
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
OUT_JSON = RESULTS / "esmc_layer_sweep.json"
MODEL_NAME = "esmc_600m"
TRUNCATE_AA = 1022


def _p(*a):
    print(*a, flush=True)


def cosine_sim_matrix(embs):
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    normed = embs / norms
    return normed @ normed.T


def nn_recall(sim, labels):
    n = len(labels); c = 0
    for i in range(n):
        row = sim[i].copy(); row[i] = -np.inf
        if labels[int(np.argmax(row))] == labels[i]:
            c += 1
    return c / n


def per_family_recall(sim, labels):
    by = {}
    for i in range(len(labels)):
        row = sim[i].copy(); row[i] = -np.inf
        nn = int(np.argmax(row))
        by.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {f: float(np.mean(v)) for f, v in by.items()}


def fetch_seq(acc, cache):
    if cache.get(acc):
        return cache[acc]
    r = requests.get(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta", timeout=20)
    if r.status_code == 200:
        seq = "".join(r.text.strip().split("\n")[1:])
        cache[acc] = seq
        return seq
    return None


def main():
    t0 = datetime.now()
    import torch
    from esm.models.esmc import ESMC
    from esm.sdk.api import ESMProtein, LogitsConfig

    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text()) if SEQ_CACHE.is_file() else {}
    seqs = [fetch_seq(p["accession"], cache)[:TRUNCATE_AA] for p in proteins]
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    _p(f"{len(seqs)} sequences ready")

    client = ESMC.from_pretrained(MODEL_NAME).to("cpu").eval()
    cfg = LogitsConfig(sequence=True, return_embeddings=True, return_hidden_states=True)

    # per_layer_embs[layer] = list of mean-pooled vectors (one per protein)
    n_layers = None
    per_layer = None
    final_embs = []
    with torch.no_grad():
        for i, seq in enumerate(seqs):
            out = client.logits(client.encode(ESMProtein(sequence=seq)), cfg)
            hs = out.hidden_states  # (n_layers, 1, L+2, D)
            if n_layers is None:
                n_layers = hs.shape[0]
                per_layer = [[] for _ in range(n_layers)]
                _p(f"n_layers = {n_layers}, D = {hs.shape[-1]}")
            for L in range(n_layers):
                resid = hs[L, 0, 1:-1, :].detach().to("cpu").float().numpy().astype(np.float64)
                per_layer[L].append(resid.mean(axis=0))
            fe = out.embeddings[0, 1:-1, :].detach().to("cpu").float().numpy().astype(np.float64)
            final_embs.append(fe.mean(axis=0))
            del out, hs
            if (i + 1) % 10 == 0:
                _p(f"  {i + 1}/{len(seqs)}  ({time.time()-t0.timestamp():.0f}s)")

    rows = []
    for L in range(n_layers):
        E = np.array(per_layer[L])
        sim = cosine_sim_matrix(E)
        raw = nn_recall(sim, labels)
        Ec = E - E.mean(axis=0, keepdims=True)
        cen = nn_recall(cosine_sim_matrix(Ec), labels)
        rows.append({"layer": L, "nn_raw": float(raw), "nn_centered": float(cen),
                     "best": float(max(raw, cen))})

    Ef = np.array(final_embs)
    final_raw = nn_recall(cosine_sim_matrix(Ef), labels)
    final_cen = nn_recall(cosine_sim_matrix(Ef - Ef.mean(0, keepdims=True)), labels)

    best_row = max(rows, key=lambda r: r["best"])
    bestL = best_row["layer"]
    Eb = np.array(per_layer[bestL])
    best_centered_better = best_row["nn_centered"] >= best_row["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if best_centered_better else Eb
    best_fam = per_family_recall(cosine_sim_matrix(Euse), labels)

    result = {
        "test": "esmc_600m_layer_sweep_crispr_n_panel",
        "timestamp": t0.isoformat(),
        "model": MODEL_NAME,
        "n_layers": n_layers,
        "n_proteins": len(seqs),
        "truncate_aa": TRUNCATE_AA,
        "final_embeddings_nn": {"raw": float(final_raw), "centered": float(final_cen)},
        "per_layer": rows,
        "best_layer": {
            "layer": bestL,
            "nn_raw": best_row["nn_raw"],
            "nn_centered": best_row["nn_centered"],
            "used": "centered" if best_centered_better else "raw",
            "per_family_nn_recall": best_fam,
        },
        "references": {"mammal_458M": 0.750, "esm2_650M_raw": 0.725,
                       "esm2_650M_centered": 0.750, "bar": 0.80},
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    _p("\n=== ESM-C 600M layer sweep (NN-recall by layer) ===")
    _p(f"  {'layer':>5} {'raw':>7} {'centered':>9} {'best':>7}")
    for r in rows:
        mark = "  <-- BEST" if r["layer"] == bestL else ""
        _p(f"  {r['layer']:>5} {r['nn_raw']:>7.3f} {r['nn_centered']:>9.3f} {r['best']:>7.3f}{mark}")
    _p(f"\n  final 'embeddings' output: raw {final_raw:.3f} / centered {final_cen:.3f} "
       f"(this is what compare_esmc_600m.py used)")
    _p(f"  BEST layer = {bestL}: {best_row['best']:.3f} ({result['best_layer']['used']})")
    _p(f"  best-layer per-family: {best_fam}")
    _p(f"  references: MAMMAL 0.750, ESM-2-650M 0.750 (centered), bar 0.80")
    if best_row["best"] >= 0.80:
        _p("  => ESM-C clears 0.80 with layer selection — last-layer mean-pool was a trap.")
    elif best_row["best"] > 0.750 + 1e-9:
        _p("  => best layer edges the tie but < 0.80.")
    elif abs(best_row["best"] - 0.750) < 1e-9:
        _p("  => best layer only TIES 0.750; no layer rescues ESM-C above the field.")
    else:
        _p("  => even the best layer LOSES to the 0.750 tie — verdict robust.")
    _p(f"\nSaved -> {OUT_JSON}")
    _p(f"Elapsed: {(datetime.now() - t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
