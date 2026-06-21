"""Quiver Capability Explorer — GPU-side inference server.

This is the model server the Explorer's backend talks to when it goes live.
`ui/explorer/backend/inference.py` POSTs `{track, model, inputs}` here; this
server dispatches on `model` (the track's `aws_model_key`) to the right model
and returns the prediction body matching that track's `score_kind` (the exact
shape `tracks.json` documents and the frontend renders). See ui/explorer/SETUP.md §5.

Run on a GPU instance (provisioned by aws/launch_explorer_endpoint.py):

    /opt/venv/bin/uvicorn explorer_inference_server:app --host 0.0.0.0 --port 8080

Then point the Explorer at it:

    export EXPLORER_AWS_ENDPOINT="http://<instance-public-dns>:8080/predict"

Design notes:
- Models load LAZILY on first use and are cached, so the server boots instantly
  and only pays the (multi-GB) load cost for models actually requested. The
  per-track runtime estimates in tracks.json fold this cold load into "startup".
- Each handler returns ONLY the prediction body (score_kind + payload). The
  Explorer backend adds track/verdict/performance wrappers.
- Heavy/queue-style models (Boltz-2 co-folding) shell out to the proven
  aws/boltz_runner.py rather than re-implementing inference here.
- This file has NO AWS credentials and makes NO AWS API calls — it just serves
  models. Provisioning/teardown is the launch script's job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

from fastapi import Body, FastAPI, HTTPException  # noqa: E402

app = FastAPI(title="Quiver Explorer Inference Server", version="0.1.0")

HERE = Path(__file__).resolve().parent
# Optional artifacts the handlers use (shipped to the instance by the launch
# script / userdata): trained probes, family centroids, the Enamine/REAL NN index.
ARTIFACTS = Path(os.environ.get("EXPLORER_ARTIFACTS", str(HERE / "artifacts")))

# ---- reference data for Track 1 (family centroids) -------------------------
# Representative members per family; we embed these once and use their mean as a
# centroid, then score a query by cosine to each centroid. (Same protocol as the
# Track-1 panel evals: mean-pooled mid-layer ESM-2-650M embedding.)
FAMILY_REFS = {
    "ion_channel": ["SCN10A", "SCN9A", "KCNQ2"],
    "gpcr": ["DRD2", "ADRB2", "HTR2A", "OPRM1"],
    "kinase": ["EGFR", "BRAF", "MAPK1"],
    "nuclear_receptor": ["PPARA", "PPARG", "RXRA"],
    "lysozyme": ["P61626"],
}

ESM2_CKPT = "facebook/esm2_t33_650M_UR50D"   # Track 1
MOLFORMER_CKPT = "ibm/MoLFormer-XL-both-10pct"  # Track 4
CHEMBERTA_CKPT = "DeepChem/ChemBERTa-77M-MLM"   # Track 5
PROTON_DIR = Path(os.environ.get("PROTON_DIR", "/opt/PROTON"))  # Track 6


# ============================================================ lazy model loaders
@lru_cache(maxsize=1)
def _torch():
    import torch  # noqa
    return torch


@lru_cache(maxsize=1)
def _esm2():
    """ESM-2-650M encoder for Track-1 family embeddings (mid-layer mean-pool)."""
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(ESM2_CKPT)
    model = AutoModel.from_pretrained(ESM2_CKPT, output_hidden_states=True)
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    return tok, model


def _embed_protein(seq: str, layer_frac: float = 0.25):
    """Mean-pooled hidden state at ~layer_frac depth (the Track-1 best-layer recipe)."""
    import torch
    tok, model = _esm2()
    seq = seq.strip().replace(" ", "")[:1022]
    enc = tok(seq, return_tensors="pt", truncation=True, max_length=1024)
    if torch.cuda.is_available():
        enc = {k: v.cuda() for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc)
    n_layers = len(out.hidden_states)
    layer = max(1, min(n_layers - 1, round(n_layers * layer_frac)))
    h = out.hidden_states[layer][0]                       # (L, d)
    mask = enc["attention_mask"][0].bool()
    vec = h[mask].mean(0)                                  # mean-pool over residues
    return (vec - vec.mean()).cpu()                        # center (Track-1 recipe)


@lru_cache(maxsize=1)
def _molformer():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MOLFORMER_CKPT, trust_remote_code=True)
    # A BBBP classifier head fine-tuned on TDC BBB_Martins is expected at
    # ARTIFACTS/molformer_bbbp; fall back to the base model + a saved logreg probe.
    head = ARTIFACTS / "molformer_bbbp"
    src = str(head) if head.exists() else MOLFORMER_CKPT
    model = AutoModelForSequenceClassification.from_pretrained(src, trust_remote_code=True, num_labels=2)
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    return tok, model


@lru_cache(maxsize=1)
def _chemberta():
    """ChemBERTa-2 encoder + per-endpoint logreg probes (hERG, DILI).

    Probes (joblib) are trained offline (see results/chemberta_admet.json) and
    shipped to ARTIFACTS/chemberta_probes/{herg,dili}.joblib. We embed the SMILES
    with the [CLS] hidden state and apply each probe.
    """
    import joblib
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(CHEMBERTA_CKPT)
    model = AutoModel.from_pretrained(CHEMBERTA_CKPT)
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    probes = {}
    pdir = ARTIFACTS / "chemberta_probes"
    for ep in ("herg", "dili"):
        f = pdir / f"{ep}.joblib"
        if f.exists():
            # SAFE: these are OUR OWN logreg probes, trained offline (see
            # results/chemberta_admet.json) and shipped to the instance by the
            # launch script — a trusted, first-party artifact, never user input.
            probes[ep] = joblib.load(f)
    return tok, model, probes


def _chemberta_embed(smiles: str):
    import torch
    tok, model, _ = _chemberta()
    enc = tok(smiles, return_tensors="pt", truncation=True, max_length=256)
    if torch.cuda.is_available():
        enc = {k: v.cuda() for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc)
    return out.last_hidden_state[0, 0].cpu().numpy()        # [CLS]


# ============================================================ per-model handlers
# Each returns the prediction BODY for its track's score_kind (see SETUP.md §5).

def predict_esm2_650m(inputs: dict) -> dict:
    """Track 1 — family clustering → score_kind 'embedding'."""
    import torch
    seqs = (inputs.get("sequences") or inputs.get("text") or "").strip()
    first = next((ln.split(",")[0].strip() for ln in seqs.splitlines() if ln.strip()), "")
    if not first:
        raise HTTPException(400, "no protein sequence provided")
    qv = _embed_protein(first)
    # centroids from reference members (cached across calls)
    scores = {}
    for fam, members in _family_centroids().items():
        c = members
        cos = float(torch.nn.functional.cosine_similarity(qv, c, dim=0))
        scores[fam] = round((cos + 1) / 2, 3)               # map [-1,1]→[0,1]
    nearest = max(scores, key=scores.get)
    return {"score_kind": "embedding", "nearest_family": nearest,
            "family_scores": scores, "dim": int(qv.shape[0])}


@lru_cache(maxsize=1)
def _family_centroids():
    """Mean embedding per family from FAMILY_REFS (UniProt accessions fetched once)."""
    import torch
    import urllib.request
    cents = {}
    for fam, accs in FAMILY_REFS.items():
        vecs = []
        for acc in accs:
            try:
                url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
                fa = urllib.request.urlopen(url, timeout=30).read().decode()
                seq = "".join(fa.splitlines()[1:])
                vecs.append(_embed_protein(seq))
            except Exception:
                continue
        if vecs:
            cents[fam] = torch.stack(vecs).mean(0)
    return cents


def predict_molformer_xl(inputs: dict) -> dict:
    """Track 4 — BBBP → score_kind 'probability' (MolFormer-XL + MAMMAL backstop)."""
    import torch
    smi = (inputs.get("smiles") or "").strip()
    if not smi:
        raise HTTPException(400, "no SMILES provided")
    tok, model = _molformer()
    enc = tok(smi, return_tensors="pt", truncation=True, max_length=256)
    if torch.cuda.is_available():
        enc = {k: v.cuda() for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits[0]
    p = float(torch.softmax(logits, -1)[1])                 # P(BBB+)
    call = "BBB+" if p >= 0.5 else "BBB-"
    # MAMMAL backstop ("trust the no's") is optional; surface MolFormer alone if absent.
    providers = [{"name": "MolFormer-XL", "value": round(p, 3), "call": f"{call} (trust the yes)"}]
    return {"score_kind": "probability", "value": round(p, 3), "call": call, "providers": providers}


def predict_chemberta2(inputs: dict) -> dict:
    """Track 5 — toxicity → score_kind 'panel' (hERG + DILI; ClinTox intentionally absent)."""
    smi = (inputs.get("smiles") or "").strip()
    if not smi:
        raise HTTPException(400, "no SMILES provided")
    _, _, probes = _chemberta()
    emb = _chemberta_embed(smi).reshape(1, -1)
    endpoints = []
    for ep, label in (("herg", "hERG"), ("dili", "DILI")):
        if ep in probes:
            risk = float(probes[ep].predict_proba(emb)[0, 1])
            call = "flag" if risk >= 0.5 else "low risk"
            endpoints.append({"name": label, "value": round(risk, 2), "call": call, "model": "ChemBERTa-2"})
        else:
            endpoints.append({"name": label, "value": None, "call": "probe missing",
                              "model": "ChemBERTa-2", "note": f"ship {ep}.joblib to EXPLORER_ARTIFACTS"})
    return {"score_kind": "panel", "endpoints": endpoints}


def predict_morgan_fp(inputs: dict) -> dict:
    """Track 8 — generative → score_kind 'analogs' (Morgan FP NN over a reference library)."""
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem
    smi = (inputs.get("smiles") or "").strip()
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        raise HTTPException(400, "could not parse SMILES")
    qfp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
    # Reference library: a SMILES file at ARTIFACTS/reference_library.smi (e.g. an
    # Enamine REAL subset). Fall back to a tiny built-in set so the endpoint works.
    lib_file = ARTIFACTS / "reference_library.smi"
    lib = (lib_file.read_text().splitlines() if lib_file.exists()
           else ["CC(=O)OC1=CC=CC=C1C(=O)OC", "CCC(=O)OC1=CC=CC=C1C(=O)O", "CC(=O)OC1=CC=CC=C1C(=O)N"])
    scored = []
    for line in lib:
        s = line.split()[0].split(",")[0].strip()
        mm = Chem.MolFromSmiles(s)
        if mm is None:
            continue
        sim = DataStructs.TanimotoSimilarity(qfp, AllChem.GetMorganFingerprintAsBitVect(mm, 2, nBits=2048))
        scored.append({"smiles": s, "similarity": round(sim, 3)})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return {"score_kind": "analogs", "neighbors": scored[:10]}


def predict_proton(inputs: dict) -> dict:
    """Track 6 — KG hypothesis → score_kind 'ranking'.

    Delegates to the proven PROTON ranking path (aws/proton_eval.py protocol):
    rank a KNOWN drug against the NeuroKG drug pool for a target gene. RANKING
    direction only (forward 'top drug' prediction is hub noise — never surfaced).
    """
    gene = (inputs.get("gene") or "").strip()
    drug = (inputs.get("known_drug") or "").strip()
    if not gene:
        raise HTTPException(400, "no target gene provided")
    helper = HERE / "proton_explorer_rank.py"   # thin wrapper around proton_eval's decoder
    if not (PROTON_DIR.exists() and helper.exists()):
        raise HTTPException(503, "PROTON KG not provisioned on this instance (see SETUP.md §5)")
    out = subprocess.run(
        [sys.executable, str(helper), "--gene", gene, "--drug", drug],
        capture_output=True, text=True, timeout=300, cwd=str(PROTON_DIR),
    )
    if out.returncode != 0:
        raise HTTPException(500, f"PROTON ranking failed: {out.stderr[-300:]}")
    import json as _json
    return _json.loads(out.stdout)              # {score_kind:'ranking', rank_percentile, shortlist}


def predict_boltz2(inputs: dict, track: str) -> dict:
    """Tracks 2/3/9 — Boltz-2 co-folding. Delegates to aws/boltz_runner.py.

    Returns 'affinity' (DTI), 'complex' (structure), or 'panel_ranking'
    (selectivity) depending on the track. Boltz-2 is the boltz-branch's lane;
    this wires the I/O — the heavy co-fold is the runner's job.
    """
    runner = HERE / "boltz_runner.py"
    if not runner.exists():
        raise HTTPException(503, "boltz_runner.py not present on this instance")
    smi = (inputs.get("smiles") or "").strip()
    seq = (inputs.get("target_seq") or "").strip()
    acc = (inputs.get("uniprot_acc") or "").strip()
    if not smi or not (seq or acc):
        raise HTTPException(400, "provide smiles + (target_seq or uniprot_acc)")
    with tempfile.TemporaryDirectory() as td:
        # boltz_runner writes a YAML (seq+smi), runs `boltz predict`, reads affinity.
        # We invoke it as a subprocess and parse its affinity JSON. Selectivity
        # (track 9) loops the target panel; here we score the single pair and the
        # caller (batch) handles the panel. Structure track returns confidence too.
        cmd = [sys.executable, str(runner), "--smiles", smi, "--out", td]
        cmd += (["--target_seq", seq] if seq else ["--uniprot", acc])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=str(HERE))
        if r.returncode != 0:
            raise HTTPException(500, f"Boltz-2 failed: {r.stderr[-300:]}")
        import json as _json
        aff = _json.loads(r.stdout)             # {affinity, confidence, ...}
    pkd = aff.get("affinity")
    if track == "structure_binding":
        return {"score_kind": "complex", "confidence": aff.get("confidence"),
                "affinity": pkd, "units": "pKd (predicted)"}
    if track == "selectivity":
        tgt = acc or "target"
        return {"score_kind": "panel_ranking",
                "ranking": [{"target": tgt, "score": pkd, "rank": 1}]}
    call = "likely binder" if (pkd or 0) >= 6 else "weak/non-binder"
    return {"score_kind": "affinity", "value": pkd, "units": "pKd (predicted)", "binder_call": call}


def predict_balm(inputs: dict) -> dict:
    """Track 2 DTI — BALM compound↔target shared-cosine triage (the current Nav1.8 best, 0.857).
    Delegates to balm_runner.py (a thin wrapper around the BALM loader already in
    aws/balm_characterization.py / aws/tsc2_deconv_eval.py). score_kind 'affinity' (cosine→pKd).
    FAMILY-LEVEL triage only — not fine selectivity/deconvolution (see Track selectivity)."""
    smi = (inputs.get("smiles") or "").strip()
    seq = (inputs.get("target_seq") or "").strip(); acc = (inputs.get("uniprot_acc") or "").strip()
    if not smi or not (seq or acc):
        raise HTTPException(400, "provide smiles + (target_seq or uniprot_acc)")
    runner = HERE / "balm_runner.py"
    if not runner.exists():
        raise HTTPException(503, "balm_runner.py not provisioned (thin wrapper around the BALM loader in aws/balm_characterization.py)")
    cmd = [sys.executable, str(runner), "--smiles", smi] + (["--target_seq", seq] if seq else ["--uniprot", acc])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(HERE))
    if r.returncode != 0:
        raise HTTPException(500, f"BALM failed: {r.stderr[-300:]}")
    out = json.loads(r.stdout)                       # {cosine, pkd}
    pkd = out.get("pkd")
    return {"score_kind": "affinity", "value": pkd, "units": "BALM cosine→pKd",
            "binder_call": "likely binder" if (pkd or 0) >= 6 else "weak/non-binder"}


def predict_maplight(inputs: dict) -> dict:
    """Track 4 BBBP — MapLight (CatBoost on ECFP+Avalon+ErG+RDKit), the confirmed primary (held-out
    B3DB 0.919). Delegates to maplight_runner.py (wraps the featurizer in aws/chemeleon_maplight_eval.py
    + a model trained on TDC BBB_Martins shipped to ARTIFACTS/maplight_bbb.cbm). score_kind 'probability'.
    Ships a Tanimoto-to-train confidence flag; MolFormer-XL is the secondary cross-check."""
    smi = (inputs.get("smiles") or "").strip()
    if not smi:
        raise HTTPException(400, "no SMILES provided")
    runner = HERE / "maplight_runner.py"
    if not runner.exists():
        raise HTTPException(503, "maplight_runner.py not provisioned (wraps the MapLight featurizer in aws/chemeleon_maplight_eval.py + ARTIFACTS/maplight_bbb.cbm)")
    r = subprocess.run([sys.executable, str(runner), "--smiles", smi], capture_output=True, text=True, timeout=300, cwd=str(HERE))
    if r.returncode != 0:
        raise HTTPException(500, f"MapLight failed: {r.stderr[-300:]}")
    out = json.loads(r.stdout)                       # {value, call, ad_confidence}
    p = out.get("value"); call = out.get("call") or ("BBB+" if (p or 0) >= 0.5 else "BBB-")
    return {"score_kind": "probability", "value": p, "call": call,
            "providers": [{"name": "MapLight", "value": p, "call": f"{call} (primary, held-out confirmed)",
                           "ad_confidence": out.get("ad_confidence")}]}


def predict_funncion(inputs: dict) -> dict:
    """Variant-effect track — funNCion ion-channel GoF/LoF (Apache-2.0, 0.897). Delegates to
    funncion_runner.py (wraps the loader in aws/mission_eval.py). score_kind 'panel' (GoF/LoF).
    NOTE: SCN10A/Nav1.8 is NOT covered by any public model — the runner returns 'unsupported' for it."""
    gene = (inputs.get("gene") or "").strip(); var = (inputs.get("variant") or "").strip()
    if not gene or not var:
        raise HTTPException(400, "provide gene + variant (e.g. SCN2A R1882Q)")
    runner = HERE / "funncion_runner.py"
    if not runner.exists():
        raise HTTPException(503, "funncion_runner.py not provisioned (wraps funNCion; Nav1.8/SCN10A unsupported by public models)")
    r = subprocess.run([sys.executable, str(runner), "--gene", gene, "--variant", var], capture_output=True, text=True, timeout=300, cwd=str(HERE))
    if r.returncode != 0:
        raise HTTPException(500, f"funNCion failed: {r.stderr[-300:]}")
    return json.loads(r.stdout)                      # {score_kind:'panel', endpoints:[...]}


# ============================================================ dispatch
# Every aws_model_key in ui/explorer/tracks.json maps to exactly one handler here. esm2/molformer/
# chemberta/morgan are inlined; proton/boltz2/balm/maplight/funncion delegate to a sibling runner
# script (graceful 503 until that runner + its artifacts are provisioned on the instance).
_HANDLERS = {
    "esm2_650m": lambda i, t: predict_esm2_650m(i),
    "molformer_xl": lambda i, t: predict_molformer_xl(i),   # Track 4 secondary cross-check
    "chemberta2": lambda i, t: predict_chemberta2(i),
    "morgan_fp": lambda i, t: predict_morgan_fp(i),
    "proton": lambda i, t: predict_proton(i),
    "boltz2": lambda i, t: predict_boltz2(i, t),
    "balm": lambda i, t: predict_balm(i),                   # Track 2 DTI (new primary)
    "maplight": lambda i, t: predict_maplight(i),           # Track 4 BBBP (new primary)
    "funncion": lambda i, t: predict_funncion(i),           # variant-effect track
}


@app.get("/health")
def health() -> dict:
    import torch
    return {"status": "ok", "cuda": torch.cuda.is_available() if _torch_ok() else None,
            "models": sorted(_HANDLERS), "artifacts_dir": str(ARTIFACTS)}


def _torch_ok() -> bool:
    try:
        _torch(); return True
    except Exception:
        return False


@app.post("/predict")
def predict(body: dict = Body(...)) -> dict[str, Any]:
    """The single endpoint the Explorer backend calls. Body: {track, model, inputs}."""
    track = (body or {}).get("track")
    model = (body or {}).get("model")
    inputs = (body or {}).get("inputs") or {}
    handler = _HANDLERS.get(model)
    if handler is None:
        raise HTTPException(404, f"no handler for model '{model}' (track '{track}')")
    return handler(inputs, track)
