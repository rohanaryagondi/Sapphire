"""ESM-2 3B + 15B layer sweep on the 40-gene CRISPR-N panel — runs on a GPU instance.

Companion to experiments/esm2_layer_sweep.py (650M, local) and
experiments/esmc_layer_sweep.py. Same protocol exactly so results are
best-layer-vs-best-layer comparable across the whole ESM size ladder
(650M -> 3B -> 15B) and vs ESM-C 600M:

  mean-pool residues (ex CLS/EOS), L2-normalize, cosine, leave-one-out NN
  same-family recall; per hidden-state layer; raw + mean-centered; 1022-aa
  truncation. Reads panel_seqs.json (40 entries w/ sequences, no UniProt needed).

Big models loaded with device_map={"":0} + bfloat16 on a single L40S (48 GB).
output_hidden_states=True gives all layers in one forward; each layer is pooled
and offloaded to CPU immediately. Results written + uploaded after EACH model so
a 15B OOM cannot lose the 3B result.

Usage: python esm2_big_layer_sweep.py panel_seqs.json out_dir
"""
from __future__ import annotations
import os
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import gc
import json
import sys
import time
import traceback
from datetime import datetime

import numpy as np

MODELS = [
    ("esm2_3B", "facebook/esm2_t36_3B_UR50D"),
    ("esm2_15B", "facebook/esm2_t48_15B_UR50D"),
]
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


def sweep_one(short, repo, seqs, labels):
    import torch
    from transformers import AutoModel, AutoTokenizer

    _p(f"\n===== {short} ({repo}) =====")
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(repo)
    # device_map="auto" works for a single big GPU (all on cuda:0) AND a multi-GPU
    # box (sharded across GPUs) — keeps this script agnostic to which instance we land.
    model = AutoModel.from_pretrained(
        repo, torch_dtype=torch.bfloat16, device_map="auto", low_cpu_mem_usage=True
    ).eval()
    DEV0 = next(model.parameters()).device  # input-embedding device for sharded models
    _p(f"  loaded in {time.time()-t0:.0f}s; device map done; input device {DEV0}")

    per_layer = None
    n_hs = None
    D = None
    with torch.no_grad():
        for i, seq in enumerate(seqs):
            inp = tok(seq[:TRUNCATE_AA], return_tensors="pt", add_special_tokens=True)
            inp = {k: v.to(DEV0) for k, v in inp.items()}
            out = model(**inp, output_hidden_states=True)
            hs = out.hidden_states  # tuple len n_layers+1, each [1, L+2, D]
            if n_hs is None:
                n_hs = len(hs); D = hs[0].shape[-1]
                per_layer = [[] for _ in range(n_hs)]
                _p(f"  n_hidden_states={n_hs}, D={D}")
            for L in range(n_hs):
                resid = hs[L][0, 1:-1, :].float().mean(dim=0).cpu().numpy().astype(np.float64)
                per_layer[L].append(resid)
            del out, hs, inp
            if (i + 1) % 10 == 0:
                _p(f"  {short} {i+1}/{len(seqs)}  ({time.time()-t0:.0f}s)")

    rows = []
    for L in range(n_hs):
        E = np.array(per_layer[L])
        raw = nn_recall(cosine_sim_matrix(E), labels)
        Ec = E - E.mean(axis=0, keepdims=True)
        cen = nn_recall(cosine_sim_matrix(Ec), labels)
        rows.append({"idx": L, "nn_raw": float(raw), "nn_centered": float(cen),
                     "best": float(max(raw, cen))})
    best = max(rows, key=lambda r: r["best"])
    bL = best["idx"]
    Eb = np.array(per_layer[bL])
    cen_better = best["nn_centered"] >= best["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if cen_better else Eb
    best_fam = per_family_recall(cosine_sim_matrix(Euse), labels)

    res = {
        "model_short": short, "repo": repo, "embedding_dim": int(D),
        "n_hidden_states": n_hs, "truncate_aa": TRUNCATE_AA,
        "last_layer_nn": {"raw": rows[-1]["nn_raw"], "centered": rows[-1]["nn_centered"]},
        "best_layer": {"idx": bL, "nn_raw": best["nn_raw"], "nn_centered": best["nn_centered"],
                       "used": "centered" if cen_better else "raw",
                       "per_family_nn_recall": best_fam},
        "per_layer": rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    _p(f"  {short}: last-layer {rows[-1]['nn_raw']:.3f}/{rows[-1]['nn_centered']:.3f}  "
       f"BEST idx {bL} = {best['best']:.3f} ({res['best_layer']['used']})")
    _p(f"  {short} best-layer per-family: {best_fam}")

    del model, tok, per_layer
    gc.collect()
    torch.cuda.empty_cache()
    return res


def main():
    panel_path = sys.argv[1] if len(sys.argv) > 1 else "panel_seqs.json"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    panel = json.loads(open(panel_path).read())
    seqs = [p["sequence"] for p in panel]
    labels = [p["family"] for p in panel]
    names = [p["name"] for p in panel]
    _p(f"panel: {len(panel)} proteins")

    import torch
    _p(f"CUDA: {torch.cuda.is_available()}  device: "
       f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}  "
       f"mem: {torch.cuda.get_device_properties(0).total_memory/1e9:.0f}GB"
       if torch.cuda.is_available() else "NO CUDA")

    combined = {
        "test": "esm2_big_layer_sweep_crispr_n_panel",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "n_proteins": len(panel), "names": names, "labels": labels,
        "protocol": "mean-pool ex CLS/EOS, cosine, LOO NN same-family recall, "
                    "per hidden-state layer, raw+centered, 1022-aa truncation",
        "references_local": {
            "esm2_650M_last_layer": {"raw": 0.725, "centered": 0.750},
            "esm2_650M_best_layer": {"idx": 8, "best": 0.875},
            "esmc_600M_best_layer": {"idx": 5, "best": 0.825},
            "esmc_600M_default_embeddings": 0.625,
            "mammal_458M_last_layer": 0.750,
            "bar": 0.80,
        },
        "results": {},
    }
    out_path = os.path.join(out_dir, "esm2_big_layer_sweep.json")

    for short, repo in MODELS:
        try:
            combined["results"][short] = sweep_one(short, repo, seqs, labels)
        except Exception as e:
            combined["results"][short] = {"status": "FAILED",
                                          "error": f"{type(e).__name__}: {e}",
                                          "trace": traceback.format_exc()}
            _p(f"  {short} FAILED: {e}")
        # write after EACH model so a later OOM can't lose earlier results
        with open(out_path, "w") as f:
            json.dump(combined, f, indent=2)
        _p(f"  wrote partial -> {out_path}")

    _p("\n=== SUMMARY (best-layer NN-recall) ===")
    for short, _ in MODELS:
        r = combined["results"].get(short, {})
        if "best_layer" in r:
            _p(f"  {short:10} last {r['last_layer_nn']['raw']:.3f}/{r['last_layer_nn']['centered']:.3f}  "
               f"best idx {r['best_layer']['idx']:>2} = "
               f"{max(r['best_layer']['nn_raw'], r['best_layer']['nn_centered']):.3f}")
        else:
            _p(f"  {short:10} {r.get('status','?')}: {r.get('error','')[:80]}")
    _p(f"\nDONE -> {out_path}")


if __name__ == "__main__":
    main()
