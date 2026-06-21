"""Exhaustive Track-1 ranking on the 167-gene / 12-family de-saturation panel.

Runs the top family-clustering contenders, each with a FULL layer sweep, to rank them with
real separating power (the 40-gene panel was saturated) and map each model's per-family
operating envelope. Same protocol throughout: mean-pool residues (ex special tokens),
L2-normalize, cosine, leave-one-out NN same-family recall; raw + mean-centered; per layer;
1022-aa truncation; per-family recall at the best layer.

Models (all loadable on a single g5.xlarge A10G):
  - ESM-2-650M       (transformers EsmModel)               [MIT, the 40-gene winner]
  - Ankh-large       (transformers T5EncoderModel)         [permissive]
  - ProstT5          (transformers T5EncoderModel, <AA2fold>) [permissive, struct-aware]
  - ESM-C 600M       (esm SDK, hidden_states)              [Cambrian]
  - ESM-3-open       (esm SDK, forward hooks)              [NON-COMMERCIAL research]
(MAMMAL needs the biomed-multi-alignment env -> run separately/local. SaProt needs 3Di
structure tokens -> needs Foldseek/AF2 preprocessing, out of scope here.)

Reads /opt/big_panel.json. Writes /opt/big_panel_result.json (after EACH model = partial-safe).
"""
from __future__ import annotations
import os, json, gc, re, time, traceback
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
from datetime import datetime
import numpy as np

TRUNC = 1022
PANEL = "/opt/big_panel.json" if os.path.exists("/opt/big_panel.json") else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "big_panel.json")
OUTDIR = "/opt" if os.path.isdir("/opt") and os.access("/opt", os.W_OK) else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
OUT = os.path.join(OUTDIR, "big_panel_result.json")


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
    return {f: round(float(np.mean(v)), 3) for f, v in by.items()}


def sweep_from_layers(per_layer, labels):
    rows = []
    for L, embs in enumerate(per_layer):
        E = np.array(embs)
        raw = nn_recall(cms(E), labels)
        cen = nn_recall(cms(E - E.mean(0, keepdims=True)), labels)
        rows.append({"idx": L, "raw": round(float(raw), 3), "cen": round(float(cen), 3),
                     "best": round(float(max(raw, cen)), 3)})
    best = max(rows, key=lambda r: r["best"])
    Eb = np.array(per_layer[best["idx"]]); cb = best["cen"] >= best["raw"]
    fam = per_family(cms(Eb - Eb.mean(0, keepdims=True) if cb else Eb), labels)
    return {"best_layer": best, "per_family": fam, "per_layer": rows}


def run_esm2(seqs, labels):
    import torch
    from transformers import AutoModel, AutoTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
    m = AutoModel.from_pretrained("facebook/esm2_t33_650M_UR50D", torch_dtype=torch.float32).to(dev).eval()
    per = None
    with torch.no_grad():
        for i, s in enumerate(seqs):
            inp = tok(s[:TRUNC], return_tensors="pt", add_special_tokens=True)
            inp = {k: v.to(dev) for k, v in inp.items()}
            hs = m(**inp, output_hidden_states=True).hidden_states
            if per is None: per = [[] for _ in range(len(hs))]
            for L in range(len(hs)):
                per[L].append(hs[L][0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64))
    del m; gc.collect()
    return per


def run_t5(repo, seqs, labels, prostt5=False):
    import torch
    from transformers import T5EncoderModel, AutoTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(repo, do_lower_case=False, use_fast=not prostt5)  # ProstT5 needs slow tokenizer
    m = T5EncoderModel.from_pretrained(repo, torch_dtype=torch.float32).to(dev).eval()
    per = None
    with torch.no_grad():
        for i, s in enumerate(seqs):
            s = s[:TRUNC]
            if prostt5:
                txt = "<AA2fold> " + " ".join(re.sub(r"[UZOB]", "X", s))
                enc = tok.batch_encode_plus([txt], add_special_tokens=True, return_tensors="pt")
            else:
                enc = tok.batch_encode_plus([list(s)], add_special_tokens=True, is_split_into_words=True, return_tensors="pt")
            enc = {k: v.to(dev) for k, v in enc.items()}
            hs = m(**enc, output_hidden_states=True).hidden_states
            if per is None: per = [[] for _ in range(len(hs))]
            for L in range(len(hs)):
                per[L].append(hs[L][0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64))
    del m; gc.collect()
    return per


def run_esmc(seqs, labels):
    import torch
    from esm.models.esmc import ESMC
    from esm.sdk.api import ESMProtein, LogitsConfig
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    cl = ESMC.from_pretrained("esmc_600m").to(dev).eval()
    cfg = LogitsConfig(sequence=True, return_embeddings=True, return_hidden_states=True)
    per = None
    with torch.no_grad():
        for s in seqs:
            out = cl.logits(cl.encode(ESMProtein(sequence=s[:TRUNC])), cfg)
            hs = out.hidden_states  # (n,1,L,D)
            if per is None: per = [[] for _ in range(hs.shape[0])]
            for L in range(hs.shape[0]):
                per[L].append(hs[L, 0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64))
    del cl; gc.collect()
    return per


def run_esm3(seqs, labels):
    import torch
    from esm.models.esm3 import ESM3
    from esm.sdk.api import ESMProtein, LogitsConfig
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(k, None)
    m = ESM3.from_pretrained("esm3_sm_open_v1", device=torch.device(dev)).eval()
    blocks = max((mod for _, mod in m.named_modules() if type(mod).__name__ == "ModuleList" and len(mod) >= 4),
                 key=len)
    cap = {}
    hdl = [blocks[i].register_forward_hook(lambda _m, _i, o, i=i: cap.__setitem__(i, (o[0] if isinstance(o, (tuple, list)) else o).detach()))
           for i in range(len(blocks))]
    per = [[] for _ in range(len(blocks))]
    cfg = LogitsConfig(sequence=True, return_embeddings=True)
    with torch.no_grad():
        for s in seqs:
            cap.clear()
            m.logits(m.encode(ESMProtein(sequence=s[:TRUNC])), cfg)
            for i in range(len(blocks)):
                h = cap[i]
                if h.dim() == 2: h = h.unsqueeze(0)
                per[i].append(h[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64))
    for h in hdl: h.remove()
    del m; gc.collect()
    return per


MODELS = [
    ("esm2_650M", run_esm2, "MIT"),
    ("ankh_large", lambda s, l: run_t5("ElnaggarLab/ankh-large", s, l), "permissive"),
    ("prostt5", lambda s, l: run_t5("Rostlab/ProstT5", s, l, prostt5=True), "permissive"),
    ("esmc_600m", run_esmc, "Cambrian"),
    ("esm3_open", run_esm3, "non-commercial"),
]


def main():
    t0 = datetime.now()
    panel = json.load(open(PANEL))
    seqs = [p["sequence"] for p in panel]; labels = [p["family"] for p in panel]
    from collections import Counter
    print(f"panel: {len(panel)} genes, families {dict(Counter(labels))}", flush=True)
    import torch
    print(f"cuda {torch.cuda.is_available()} {torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}", flush=True)
    # optional: run only a subset (comma-sep names) e.g. MODELS_FILTER=prostt5 for a local re-run
    flt = [x for x in os.environ.get("MODELS_FILTER", "").split(",") if x]
    res = {"test": "big_panel_track1_desaturated", "timestamp": t0.isoformat(),
           "n_genes": len(panel), "n_families": len(set(labels)),
           "families": dict(Counter(labels)), "results": {}}
    # merge into any existing result file (so a single-model re-run augments the AWS results)
    if os.path.exists(OUT):
        try: res["results"] = json.load(open(OUT)).get("results", {})
        except Exception: pass
    for name, fn, lic in MODELS:
        if flt and name not in flt:
            continue
        try:
            tm = time.time()
            per = fn(seqs, labels)
            r = sweep_from_layers(per, labels)
            r["license"] = lic; r["elapsed_s"] = round(time.time() - tm, 0)
            res["results"][name] = r
            print(f"  {name}: BEST {r['best_layer']['best']} (layer {r['best_layer']['idx']}) | {r['per_family']}", flush=True)
        except Exception as e:
            res["results"][name] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}"}
            print(f"  {name} FAILED: {str(e)[:200]}", flush=True); print(traceback.format_exc()[:800], flush=True)
        json.dump(res, open(OUT, "w"), indent=2)
        gc.collect()
    # ranking
    rank = sorted([(n, r["best_layer"]["best"]) for n, r in res["results"].items() if "best_layer" in r],
                  key=lambda x: -x[1])
    res["ranking"] = rank
    json.dump(res, open(OUT, "w"), indent=2)
    print("\n=== RANKING (best-layer NN-recall, de-saturated 167-gene panel) ===", flush=True)
    for n, s in rank: print(f"  {n:14} {s}", flush=True)
    print(f"DONE {(datetime.now()-t0).total_seconds():.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
