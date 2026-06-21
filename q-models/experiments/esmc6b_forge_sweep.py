"""ESM-C 6B (EvolutionaryScale) via the Forge/biohub API — Track 1, NON-COMMERCIAL RESEARCH.

*** NON-COMMERCIAL RESEARCH USE ONLY. ESM-C 6B is under a non-commercial license; runs on
EvolutionaryScale's cloud (biohub.ai). Not shippable without a commercial agreement. ***

ESM-C 6B is not transformers-loadable and not in the esm SDK local registry, so it's reached
via the Forge API. IMPORTANT CAVEAT: the API returns only the FINAL-layer embeddings (no
per-layer hidden states), so this is the "last-layer trap" readout — the same readout that
gave ESM-C 600M a misleadingly-low 0.625 vs its best-layer 0.825. So ESM-C 6B's number here
is a LOWER BOUND, not a fair best-layer comparison. It answers "does the 6B final embedding
clear the field" (a weak test), not "what's 6B's best-layer ceiling" (unanswerable via API).

Token via env FORGE_TOKEN. Endpoint biohub.ai. Same panel/protocol as the ESM ladder.
Run: FORGE_TOKEN=... <venv>/bin/python experiments/esmc6b_forge_sweep.py
Out: results/esmc6b_forge.json
"""
from __future__ import annotations
import os, json, time
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
OUT = RESULTS / "esmc6b_forge.json"
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


def main():
    t0 = datetime.now()
    tok = os.environ["FORGE_TOKEN"]
    from esm.sdk import client
    from esm.sdk.api import ESMProtein, LogitsConfig

    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text())
    seqs = [cache[p["accession"]][:TRUNCATE_AA] for p in proteins]
    print(f"panel: {len(proteins)} proteins", flush=True)

    m = client(model="esmc-6b-2024-12", url="https://biohub.ai", token=tok)
    cfg = LogitsConfig(sequence=True, return_embeddings=True)
    embs = []
    for i, seq in enumerate(seqs):
        for attempt in range(3):
            try:
                out = m.logits(m.encode(ESMProtein(sequence=seq)), cfg)
                v = out.embeddings[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)
                embs.append(v)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  protein {i} FAILED after 3 tries: {str(e)[:120]}", flush=True)
                    raise
                time.sleep(5 * (attempt + 1))
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(seqs)} ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)

    E = np.array(embs)
    raw = nn_recall(cms(E), labels)
    cen = nn_recall(cms(E - E.mean(0, keepdims=True)), labels)
    fam_raw = per_family(cms(E), labels)
    fam_cen = per_family(cms(E - E.mean(0, keepdims=True)), labels)

    result = {
        "test": "esmc_6b_forge_final_embedding_crispr_n_panel", "timestamp": t0.isoformat(),
        "model": "esmc-6b-2024-12 (Forge/biohub API)", "embedding_dim": int(E.shape[1]),
        "LICENSE": "NON-COMMERCIAL RESEARCH ONLY (ESM-C 6B). Runs on EvolutionaryScale cloud. Not shippable.",
        "READOUT_CAVEAT": ("FINAL-layer embedding only (API gives no hidden_states). This is the "
                           "last-layer 'trap' readout -- ESM-C 600M's final embedding was 0.625 vs "
                           "best-layer 0.825. So this is a LOWER BOUND, not a fair best-layer number."),
        "final_embedding_nn": {"raw": float(raw), "centered": float(cen)},
        "per_family_raw": fam_raw, "per_family_centered": fam_cen,
        "references": {"esm2_650M_best": 0.875, "esm3_best": 0.875, "mammal_best": 0.850,
                       "esmc_600M_best": 0.825, "esmc_600M_FINAL_trap": 0.625, "bar": 0.80},
    }
    OUT.write_text(json.dumps(result, indent=2))
    print("\n=== ESM-C 6B (Forge, FINAL-embedding only, NON-COMMERCIAL) ===", flush=True)
    print(f"  final-embedding NN-recall: raw {raw:.3f} / centered {cen:.3f}", flush=True)
    print(f"  per-family (centered): {fam_cen}", flush=True)
    print(f"  CAVEAT: final-layer trap readout (cf. 600M final 0.625 vs best 0.825); lower bound only.", flush=True)
    print(f"  Saved -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)


if __name__ == "__main__":
    main()
