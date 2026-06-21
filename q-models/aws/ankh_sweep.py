"""Ankh-large (ElnaggarLab) Track-1 layer sweep on the 40-gene CRISPR-N panel.
Commercial-OK (Ankh is CC-BY / permissive). Same protocol as the ESM ladder.
Reads compare_esm2_650m.json (panel) + _uniprot_cache.json (seqs). Out: /opt/ankh_result.json"""
import os, json
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from datetime import datetime
import numpy as np
TRUNC = 1000

def cms(E):
    n = np.linalg.norm(E, axis=1, keepdims=True) + 1e-12; Z = E / n; return Z @ Z.T
def nn_recall(sim, labels):
    c = 0
    for i in range(len(labels)):
        r = sim[i].copy(); r[i] = -np.inf
        if labels[int(np.argmax(r))] == labels[i]: c += 1
    return c / len(labels)
def per_family(sim, labels):
    by = {}
    for i in range(len(labels)):
        r = sim[i].copy(); r[i] = -np.inf; nn = int(np.argmax(r))
        by.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {f: float(np.mean(v)) for f, v in by.items()}

def main():
    t0 = datetime.now()
    import torch
    from transformers import T5EncoderModel, AutoTokenizer
    BASE = "/opt" if os.path.exists("/opt/compare_esm2_650m.json") else \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    OUTDIR = "/opt" if os.path.isdir("/opt") and os.access("/opt", os.W_OK) else BASE
    proteins = json.load(open(f"{BASE}/compare_esm2_650m.json"))["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.load(open(f"{BASE}/_uniprot_cache.json"))
    seqs = [cache[p["accession"]][:TRUNC] for p in proteins]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained("ElnaggarLab/ankh-large")
    model = T5EncoderModel.from_pretrained("ElnaggarLab/ankh-large").to(dev).eval()
    print("loaded ankh-large", flush=True)
    per_layer = None; n_hs = None
    with torch.no_grad():
        for i, s in enumerate(seqs):
            enc = tok.batch_encode_plus([list(s)], add_special_tokens=True, is_split_into_words=True,
                                        return_tensors="pt")
            enc = {k: v.to(dev) for k, v in enc.items()}
            out = model(**enc, output_hidden_states=True)
            hs = out.hidden_states
            if n_hs is None:
                n_hs = len(hs); per_layer = [[] for _ in range(n_hs)]
                print(f"n_hidden_states={n_hs} D={hs[0].shape[-1]}", flush=True)
            for L in range(n_hs):
                per_layer[L].append(hs[L][0, :-1, :].float().mean(0).cpu().numpy().astype(np.float64))  # drop EOS
            if (i + 1) % 10 == 0: print(f"  {i+1}/{len(seqs)}", flush=True)
    rows = []
    for L in range(n_hs):
        E = np.array(per_layer[L])
        rows.append({"idx": L, "raw": float(nn_recall(cms(E), labels)),
                     "cen": float(nn_recall(cms(E - E.mean(0, keepdims=True)), labels))})
    best = max(rows, key=lambda r: max(r["raw"], r["cen"]))
    Eb = np.array(per_layer[best["idx"]]); cb = best["cen"] >= best["raw"]
    fam = per_family(cms(Eb - Eb.mean(0, keepdims=True) if cb else Eb), labels)
    res = {"test": "ankh_large_track1", "timestamp": t0.isoformat(), "model": "ElnaggarLab/ankh-large",
           "best_layer": {"idx": best["idx"], "raw": best["raw"], "cen": best["cen"],
                          "best": max(best["raw"], best["cen"]), "per_family": fam},
           "per_layer": rows,
           "refs": {"esm2_650M": 0.875, "mammal": 0.850, "esm3": 0.875, "esmc600": 0.825, "prostt5": 0.825}}
    json.dump(res, open(f"{OUTDIR}/ankh_result.json", "w"), indent=2)
    print(f"BEST idx {best['idx']} = {max(best['raw'],best['cen']):.3f}  per-family {fam}", flush=True)
    print(f"DONE {(datetime.now()-t0).total_seconds():.0f}s", flush=True)

if __name__ == "__main__":
    main()
