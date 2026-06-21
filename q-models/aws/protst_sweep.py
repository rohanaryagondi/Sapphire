"""ProtST-esm1b (mila-intel) Track-1 — function-aware protein embeddings on the 40-gene panel.
*** NON-COMMERCIAL? ProtST is MIT per its repo, but verify before shipping. ***
Hypothesis: ProtST's protein<->biomedical-text training cracks the e3_ligase/NR families that
pure-sequence models fail on (e3 <= 0.5). Loads via trust_remote_code; defensively finds the
protein encoder. Reads compare_esm2_650m.json + _uniprot_cache.json. Out: /opt/protst_result.json"""
import os, json, traceback
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from datetime import datetime
import numpy as np
TRUNC = 1022

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
    from transformers import AutoModel, AutoTokenizer
    proteins = json.load(open("/opt/compare_esm2_650m.json"))["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.load(open("/opt/_uniprot_cache.json"))
    seqs = [cache[p["accession"]][:TRUNC] for p in proteins]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # SECURITY: trust_remote_code runs arbitrary repo code -- scrub credentials from the env
    # first so the remote model code cannot read AWS/HF secrets. (mila-intel is reputable;
    # this is defense-in-depth. Ideally also pin revision="<sha>" after auditing the repo.)
    for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "HF_TOKEN"):
        os.environ.pop(_k, None)
    tok = AutoTokenizer.from_pretrained("mila-intel/ProtST-esm1b", trust_remote_code=True)
    model = AutoModel.from_pretrained("mila-intel/ProtST-esm1b", trust_remote_code=True).to(dev).eval()
    print("children:", [n for n, _ in model.named_children()], flush=True)
    # find the protein encoder submodule
    prot = None
    for attr in ["protein_model", "protein_encoder", "protein", "model"]:
        if hasattr(model, attr): prot = getattr(model, attr); print("using protein encoder:", attr, flush=True); break
    enc = prot if prot is not None else model

    def embed(seq):
        inp = tok(seq, return_tensors="pt", truncation=True, max_length=TRUNC)
        inp = {k: v.to(dev) for k, v in inp.items()}
        with torch.no_grad():
            out = enc(**inp)
        h = getattr(out, "last_hidden_state", None)
        if h is None and isinstance(out, (tuple, list)): h = out[0]
        if h is None and hasattr(out, "hidden_states") and out.hidden_states is not None: h = out.hidden_states[-1]
        return h[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)

    embs = []
    for i, s in enumerate(seqs):
        try:
            embs.append(embed(s))
        except Exception as e:
            print(f"protein {i} err: {str(e)[:160]}", flush=True)
            print(traceback.format_exc()[:500], flush=True); raise
        if (i + 1) % 10 == 0: print(f"  {i+1}/{len(seqs)}", flush=True)
    E = np.array(embs)
    raw = nn_recall(cms(E), labels); cen = nn_recall(cms(E - E.mean(0, keepdims=True)), labels)
    fam = per_family(cms(E - E.mean(0, keepdims=True) if cen >= raw else E), labels)
    res = {"test": "protst_esm1b_track1", "timestamp": t0.isoformat(), "model": "mila-intel/ProtST-esm1b",
           "note": "final-layer embedding (function-aware ESM-1b); NN-recall raw/centered",
           "final_nn": {"raw": float(raw), "cen": float(cen)}, "per_family": fam,
           "refs": {"esm2_650M": 0.875, "esm3_NR": 1.0, "e3_ceiling": 0.5, "mammal": 0.850}}
    json.dump(res, open("/opt/protst_result.json", "w"), indent=2)
    print(f"ProtST final NN raw {raw:.3f} cen {cen:.3f} | e3_ligase={fam.get('e3_ligase')} NR={fam.get('nuclear_receptor')}", flush=True)
    print(f"DONE {(datetime.now()-t0).total_seconds():.0f}s", flush=True)

if __name__ == "__main__":
    main()
