"""ESM-3-open (esm3_sm_open_v1, 1.4B) layer sweep on the 40-gene CRISPR-N panel — Track 1.

*** NON-COMMERCIAL RESEARCH USE ONLY. ESM-3 open weights are under a non-commercial
license. These results inform the science ceiling; nothing here may ship in a Quiver
product without a commercial agreement with EvolutionaryScale. ***

ESM-3 is a generative multi-track model (sequence + structure + function). The interesting
hypothesis for Track 1: because ESM-3 trained WITH a function track, its embeddings might
cluster the *function-not-fold* families (E3 ligases, mislabeled NRs) that every pure-sequence
model (ESM-2/C, MAMMAL, SaProt, ProstT5) fails on (e3 <= 0.5). If ESM-3 cracks e3_ligase,
that's a real, novel Track-1 signal.

The esm SDK returns embeddings but hidden_states=None, so we register forward-hooks on the
transformer blocks (auto-detected longest ModuleList) for a fair layer sweep, same approach as
experiments/mammal_layer_sweep.py. Same protocol: mean-pool ex BOS/EOS, cosine, LOO NN
same-family recall, raw + centered, 1022-aa truncation.

Run: <venv>/bin/python experiments/esm3_layer_sweep.py
Out: results/esm3_layer_sweep.json
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
import json
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
OUT = RESULTS / "esm3_layer_sweep.json"
MODEL = "esm3_sm_open_v1"
TRUNCATE_AA = 1022


def cms(E):
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


def per_family(sim, labels):
    by = {}
    for i in range(len(labels)):
        row = sim[i].copy(); row[i] = -np.inf
        nn = int(np.argmax(row))
        by.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {f: float(np.mean(v)) for f, v in by.items()}


def find_blocks(model):
    best = None
    for name, mod in model.named_modules():
        if type(mod).__name__ == "ModuleList" and len(mod) >= 4:
            if best is None or len(mod) > best[0]:
                best = (len(mod), name, mod)
    return best


def main():
    t0 = datetime.now()
    import torch
    from esm.models.esm3 import ESM3
    from esm.sdk.api import ESMProtein, LogitsConfig

    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text())
    seqs = [cache[p["accession"]][:TRUNCATE_AA] for p in proteins]
    print(f"panel: {len(proteins)} proteins", flush=True)

    model = ESM3.from_pretrained(MODEL, device=torch.device("cpu")).eval()
    n_blk, stack_name, blocks = find_blocks(model)
    print(f"transformer stack '{stack_name}': {n_blk} blocks (child={type(blocks[0]).__name__})", flush=True)

    captured = {}

    def mk(i):
        def hook(_m, _i, out):
            h = out[0] if isinstance(out, (tuple, list)) else out
            captured[i] = h.detach()
        return hook

    handles = [blocks[i].register_forward_hook(mk(i)) for i in range(n_blk)]

    per_layer = [[] for _ in range(n_blk)]
    final_emb = []
    cfg = LogitsConfig(sequence=True, return_embeddings=True)
    with torch.no_grad():
        for idx, seq in enumerate(seqs):
            captured.clear()
            enc = model.encode(ESMProtein(sequence=seq))
            out = model.logits(enc, cfg)
            for i in range(n_blk):
                h = captured[i]
                if h.dim() == 2:
                    h = h.unsqueeze(0)
                resid = h[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)
                per_layer[i].append(resid)
            e = out.embeddings[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)
            final_emb.append(e)
            del out, enc
            if (idx + 1) % 10 == 0:
                print(f"  {idx+1}/{len(seqs)} ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)
    for h in handles:
        h.remove()

    rows = []
    for i in range(n_blk):
        E = np.array(per_layer[i])
        raw = nn_recall(cms(E), labels)
        cen = nn_recall(cms(E - E.mean(0, keepdims=True)), labels)
        rows.append({"block": i, "nn_raw": float(raw), "nn_centered": float(cen),
                     "best": float(max(raw, cen))})
    Ef = np.array(final_emb)
    final_raw = nn_recall(cms(Ef), labels)
    final_cen = nn_recall(cms(Ef - Ef.mean(0, keepdims=True)), labels)

    best = max(rows, key=lambda r: r["best"]); bL = best["block"]
    Eb = np.array(per_layer[bL]); cenb = best["nn_centered"] >= best["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if cenb else Eb
    bfam = per_family(cms(Euse), labels)

    result = {
        "test": "esm3_sm_open_layer_sweep_crispr_n_panel", "timestamp": t0.isoformat(),
        "model": MODEL, "n_blocks": n_blk, "embedding_dim": int(Ef.shape[1]),
        "LICENSE": "NON-COMMERCIAL RESEARCH ONLY (ESM-3 open weights). Not shippable without a commercial deal.",
        "final_embeddings_nn": {"raw": float(final_raw), "centered": float(final_cen)},
        "per_block": rows,
        "best_block": {"block": bL, "nn_raw": best["nn_raw"], "nn_centered": best["nn_centered"],
                       "used": "centered" if cenb else "raw", "per_family_nn_recall": bfam},
        "references": {"esm2_650M_best": 0.875, "mammal_best": 0.850, "esmc_600M_best": 0.825,
                       "prostt5_best": 0.825, "e3_ligase_ceiling_seq_models": 0.5, "bar": 0.80},
        "hypothesis": "ESM-3's function track may crack the e3_ligase/NR families that pure-sequence models fail on",
    }
    OUT.write_text(json.dumps(result, indent=2))
    print("\n=== ESM-3-open layer sweep (NON-COMMERCIAL RESEARCH) ===", flush=True)
    print(f"  final embeddings: {final_raw:.3f}/{final_cen:.3f}", flush=True)
    print(f"  BEST block {bL}: {best['best']:.3f} ({result['best_block']['used']})", flush=True)
    print(f"  best-block per-family: {bfam}", flush=True)
    print(f"  e3_ligase = {bfam.get('e3_ligase')}  (seq-model ceiling 0.5 -- did the function track help?)", flush=True)
    print(f"  refs: ESM-2-650M 0.875, MAMMAL 0.850, ESM-C/ProstT5 0.825", flush=True)
    print(f"  Saved -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)


if __name__ == "__main__":
    main()
