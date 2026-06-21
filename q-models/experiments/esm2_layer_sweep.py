"""ESM-2-650M layer sweep on the 40-gene CRISPR-N panel — fairness companion to
experiments/esmc_layer_sweep.py.

ESM-C's best intermediate layer hit NN-recall 0.825 vs the 0.625 last-layer trap.
To compare best-vs-best (not ESM-C's best layer vs ESM-2's arbitrary last layer),
run the IDENTICAL sweep on ESM-2-650M: all 33 transformer layers, mean-pool
(ex CLS/EOS), NN-recall raw + centered per layer, find the best.

Same panel/ordering (from compare_esm2_650m.json), same 1022-aa truncation, same
metrics. ESM-2-650M weights are already in the HF cache.

Run: /private/tmp/esmc-venv/bin/python experiments/esm2_layer_sweep.py
Out: results/esm2_layer_sweep.json
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
OUT_JSON = RESULTS / "esm2_layer_sweep.json"
MODEL = "facebook/esm2_t33_650M_UR50D"
TRUNCATE_AA = 1022


def _p(*a):
    print(*a, flush=True)


def cosine_sim_matrix(E):
    n = np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
    Z = E / n
    return Z @ Z.T


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
    from transformers import AutoModel, AutoTokenizer

    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text()) if SEQ_CACHE.is_file() else {}
    seqs = [fetch_seq(p["accession"], cache)[:TRUNCATE_AA] for p in proteins]
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    _p(f"{len(seqs)} sequences ready")

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL, torch_dtype=torch.float32).eval()

    per_layer = None
    n_hs = None
    with torch.no_grad():
        for i, seq in enumerate(seqs):
            inp = tok(seq, return_tensors="pt", add_special_tokens=True)
            out = model(**inp, output_hidden_states=True)
            hs = out.hidden_states  # tuple len = n_layers+1 (embeddings + each layer)
            if n_hs is None:
                n_hs = len(hs)
                per_layer = [[] for _ in range(n_hs)]
                _p(f"n_hidden_states = {n_hs} (embeddings + 33 layers), D = {hs[0].shape[-1]}")
            for L in range(n_hs):
                resid = hs[L][0, 1:-1, :].cpu().float().numpy().astype(np.float64)
                per_layer[L].append(resid.mean(axis=0))
            del out, hs, inp
            if (i + 1) % 10 == 0:
                _p(f"  {i + 1}/{len(seqs)}")

    rows = []
    for L in range(n_hs):
        E = np.array(per_layer[L])
        raw = nn_recall(cosine_sim_matrix(E), labels)
        Ec = E - E.mean(axis=0, keepdims=True)
        cen = nn_recall(cosine_sim_matrix(Ec), labels)
        rows.append({"hidden_state_index": L, "nn_raw": float(raw),
                     "nn_centered": float(cen), "best": float(max(raw, cen))})

    best_row = max(rows, key=lambda r: r["best"])
    bL = best_row["hidden_state_index"]
    Eb = np.array(per_layer[bL])
    cen_better = best_row["nn_centered"] >= best_row["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if cen_better else Eb
    best_fam = per_family_recall(cosine_sim_matrix(Euse), labels)

    result = {
        "test": "esm2_650m_layer_sweep_crispr_n_panel",
        "timestamp": t0.isoformat(),
        "model": MODEL,
        "n_hidden_states": n_hs,
        "n_proteins": len(seqs),
        "truncate_aa": TRUNCATE_AA,
        "last_layer_nn": {"raw": rows[-1]["nn_raw"], "centered": rows[-1]["nn_centered"]},
        "per_layer": rows,
        "best_layer": {"hidden_state_index": bL, "nn_raw": best_row["nn_raw"],
                       "nn_centered": best_row["nn_centered"],
                       "used": "centered" if cen_better else "raw",
                       "per_family_nn_recall": best_fam},
        "references": {"esmc_600m_best_layer5": 0.825, "mammal_458M": 0.750, "bar": 0.80},
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    _p("\n=== ESM-2-650M layer sweep (NN-recall by hidden-state index) ===")
    _p(f"  {'idx':>4} {'raw':>7} {'centered':>9} {'best':>7}")
    for r in rows:
        mark = "  <-- BEST" if r["hidden_state_index"] == bL else ""
        _p(f"  {r['hidden_state_index']:>4} {r['nn_raw']:>7.3f} {r['nn_centered']:>9.3f} {r['best']:>7.3f}{mark}")
    _p(f"\n  last layer (idx {n_hs-1}): raw {rows[-1]['nn_raw']:.3f} / centered {rows[-1]['nn_centered']:.3f}  "
       "(this is the canonical 0.725/0.750)")
    _p(f"  BEST hidden-state idx {bL}: {best_row['best']:.3f} ({result['best_layer']['used']})")
    _p(f"  best-layer per-family: {best_fam}")
    _p(f"  ESM-C best layer was 0.825; MAMMAL 0.750; bar 0.80")
    _p(f"\nSaved -> {OUT_JSON}")
    _p(f"Elapsed: {(datetime.now() - t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
