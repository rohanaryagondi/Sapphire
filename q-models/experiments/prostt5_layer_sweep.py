"""ProstT5 (Rostlab) layer sweep on the 40-gene CRISPR-N panel — Track 1.

Structure-aware seq<->3Di T5; cheaper alternative to SaProt. Does it match SaProt's
perfect GPCR clustering and the ~0.85-0.875 best-layer ceiling of the ESM/MAMMAL ladder?
Same protocol: mean-pool residues (ex <AA2fold> prefix + EOS), cosine, LOO NN same-family
recall, per hidden-state layer, raw + centered, 1000-aa truncation.

ProstT5 input convention: prefix "<AA2fold>", space-separated residues, rare AAs (U/Z/O/B)->X.
Runs in the existing esmc-venv (transformers + torch + sentencepiece). ~1.2B params, CPU.

Run: /private/tmp/esmc-venv/bin/python experiments/prostt5_layer_sweep.py
Out: results/prostt5_layer_sweep.json
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
import json, re
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
OUT = RESULTS / "prostt5_layer_sweep.json"
MODEL = "Rostlab/ProstT5"
TRUNCATE_AA = 1000


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
    import torch
    from transformers import T5EncoderModel, T5Tokenizer

    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text())
    seqs = [cache[p["accession"]][:TRUNCATE_AA] for p in proteins]
    print(f"panel: {len(proteins)} proteins", flush=True)

    tok = T5Tokenizer.from_pretrained(MODEL, do_lower_case=False)
    model = T5EncoderModel.from_pretrained(MODEL, torch_dtype=torch.float32).eval()
    print(f"loaded {MODEL}", flush=True)

    per_layer = None; n_hs = None
    with torch.no_grad():
        for i, seq in enumerate(seqs):
            s = "<AA2fold> " + " ".join(re.sub(r"[UZOB]", "X", seq))
            enc = tok.batch_encode_plus([s], add_special_tokens=True, return_tensors="pt")
            out = model(enc.input_ids, attention_mask=enc.attention_mask, output_hidden_states=True)
            hs = out.hidden_states  # tuple len n_layers+1, each [1,L,1024]
            if n_hs is None:
                n_hs = len(hs); per_layer = [[] for _ in range(n_hs)]
                print(f"n_hidden_states={n_hs}, D={hs[0].shape[-1]}", flush=True)
            for L in range(n_hs):
                resid = hs[L][0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)  # ex prefix + EOS
                per_layer[L].append(resid)
            del out, hs, enc
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(seqs)} ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)

    rows = []
    for L in range(n_hs):
        E = np.array(per_layer[L])
        raw = nn_recall(cms(E), labels)
        cen = nn_recall(cms(E - E.mean(0, keepdims=True)), labels)
        rows.append({"idx": L, "nn_raw": float(raw), "nn_centered": float(cen),
                     "best": float(max(raw, cen))})
    best = max(rows, key=lambda r: r["best"]); bL = best["idx"]
    Eb = np.array(per_layer[bL]); cenb = best["nn_centered"] >= best["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if cenb else Eb
    bfam = per_family(cms(Euse), labels)

    result = {
        "test": "prostt5_layer_sweep_crispr_n_panel", "timestamp": t0.isoformat(),
        "model": MODEL, "n_hidden_states": n_hs, "embedding_dim": int(np.array(per_layer[0]).shape[1]),
        "last_layer_nn": {"raw": rows[-1]["nn_raw"], "centered": rows[-1]["nn_centered"]},
        "best_layer": {"idx": bL, "nn_raw": best["nn_raw"], "nn_centered": best["nn_centered"],
                       "used": "centered" if cenb else "raw", "per_family_nn_recall": bfam},
        "per_layer": rows,
        "references": {"esm2_650M_best": 0.875, "mammal_best": 0.850, "esmc_600M_best": 0.825,
                       "saprot_gpcr": 1.0, "bar": 0.80},
    }
    OUT.write_text(json.dumps(result, indent=2))
    print("\n=== ProstT5 layer sweep ===", flush=True)
    print(f"  last-layer {rows[-1]['nn_raw']:.3f}/{rows[-1]['nn_centered']:.3f}  "
          f"BEST idx {bL} = {best['best']:.3f} ({result['best_layer']['used']})", flush=True)
    print(f"  best-layer per-family: {bfam}", flush=True)
    print(f"  refs: ESM-2-650M 0.875, MAMMAL 0.850, ESM-C 0.825, SaProt GPCR 1.0", flush=True)
    print(f"  Saved -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)", flush=True)


if __name__ == "__main__":
    main()
