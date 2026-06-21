"""Quiver MAMMAL Explorer — FastAPI backend.

Every /predict/* response carries the model output AND Quiver's empirical
reliability verdict (the point of this UI). Run:

    cd <repo root>
    /opt/anaconda3/envs/mammal/bin/uvicorn ui.backend.app:app --reload

then open http://localhost:8000/ (Swagger at /docs). Models lazy-load per task on
first request (~1.8 GB from local disk; seconds on MPS/CPU).
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mammal_quiver import sequences  # noqa: E402  (lightweight: urllib only)

from . import history  # noqa: E402
from . import mammal_runner  # noqa: E402
from . import reliability as rel  # noqa: E402
from ._smiles import neutral_parent  # noqa: E402
from .models import (  # noqa: E402
    BatchRequest,
    BatchResponse,
    BbbpRequest,
    DtiRequest,
    EmbedRequest,
    GenerateRequest,
    PpiRequest,
    PredictResponse,
    SmilesRequest,
    SolubilityRequest,
    TcrRequest,
)

FRONTEND = REPO / "ui" / "frontend"

# Most rows we'll score in one batch (internal MPS tool, single user). Over this,
# extra rows are dropped and the count reported — never silently truncated.
MAX_BATCH_ROWS = int(os.environ.get("MAMMAL_UI_MAX_BATCH", "256"))

app = FastAPI(
    title="Quiver MAMMAL Explorer",
    description="IBM MAMMAL public heads + Quiver's empirical reliability verdict on every prediction.",
    version="0.1.0",
)

# SMILES tabs whose input we standardize (neutralize/strip salts) before scoring.
_SMILES_TASKS = {"dti", "bbbp", "clintox_tox", "clintox_fda"}

# Per-task request schema — used to validate each batch row the same way the
# single-prediction routes validate their body. Tasks absent here (generation,
# embeddings) are not batchable.
_REQUEST_MODEL = {
    "dti": DtiRequest,
    "ppi": PpiRequest,
    "bbbp": BbbpRequest,
    "clintox_tox": SmilesRequest,
    "clintox_fda": SmilesRequest,
    "solubility": SolubilityRequest,
    "tcr": TcrRequest,
}

# ---- Load-example prefills (sequences from mammal_quiver + the base model card) ----
# Calmodulin / calcineurin are the PPI sanity pair from models/base_458m/README.md.
_CALMODULIN = ("MADQLTEEQIAEFKEAFSLFDKDGDGTITTKELGTVMRSLGQNPTEAELQDMISELDQDGFIDKEDLHDG"
               "DGKISFEEFLNLVNKEMTADVDGDGQVNYEEFVTMMTSK")
_CALCINEURIN = ("MSSKLLLAGLDIERVLAEKNFYKEWDTWIIEAMNVGDEEVDRIKEFKEDEIFEEAKTLGTAEMQEYKKQKL"
                "EEAIEGAFDIFDKDGNGYISAAELRHVMTNLGEKLTDEEVDEMIRQMWDQNGDWDRIKELKFGEIKKLSAK"
                "DTRGTIFIKVFENLGTGVDSEYEDVSKYMLKHQ")
# TCR defaults from mammal/examples/tcr_epitope_binding/main_infer.py (known binder).
_TCR_BETA = ("GAVVSQHPSWVICKSGTSVKIECRSLDFQATTMFWYRQFPKQSLMLMATSNEGSKATYEQGVEKDKFLINH"
             "ASLTLSTLTVTSAHPEDSSFYICSASEGTSSYEQYFGPGTRLTVT")
_EPITOPE = "FLKEKGGL"

EXAMPLES: dict[str, dict] = {
    "dti": {"smiles": sequences.DRUGS["suzetrigine"], "uniprot_acc": "Q9Y5Y9",
            "_note": "suzetrigine → Nav1.8 (SCN10A). The named test the off-the-shelf head fails."},
    "ppi": {"seq_a": _CALMODULIN, "seq_b": _CALCINEURIN,
            "_note": "calmodulin–calcineurin (the base model card's PPI sanity pair, P≈0.95)."},
    "bbbp": {"smiles": sequences.DRUGS["caffeine"], "_note": "caffeine — CNS-penetrant."},
    "clintox_tox": {"smiles": sequences.DRUGS["caffeine"], "_note": "caffeine — benign reference."},
    "clintox_fda": {"smiles": sequences.DRUGS["ibuprofen"], "_note": "ibuprofen — FDA-approved."},
    "solubility": {"protein_seq": _CALMODULIN, "_note": "calmodulin — small soluble protein."},
    "tcr": {"tcr_beta_seq": _TCR_BETA, "epitope_seq": _EPITOPE,
            "_note": "Weber-benchmark known binder."},
    "generation": {"prompt": sequences.DRUGS["caffeine"], "kind": "smiles",
                   "_note": "caffeine SMILES — the middle third is masked and infilled (span-infill demo)."},
    "embeddings": {"text": "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSR", "kind": "protein",
                   "_note": "lysozyme C fragment — should land on the lysozyme reference family (clustering works)."},
}


# ----------------------------- meta endpoints -----------------------------

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "tasks": list(mammal_runner.TASKS.keys()),
        "reliability_tasks": list(rel.RELIABILITY.keys()),
        "device": mammal_runner.pick_device(),
    }


@app.get("/reliability")
def all_reliability() -> dict:
    return {
        "banner": rel.STRATEGIC_BANNER,
        "verdicts": {k: v.to_dict() for k, v in rel.RELIABILITY.items()},
    }


@app.get("/reliability/{task}")
def reliability_for(task: str) -> dict:
    r = rel.get_reliability(task)
    if r is None:
        raise HTTPException(404, f"unknown task '{task}'")
    return r.to_dict()


@app.get("/examples/{task}")
def example_for(task: str) -> dict:
    ex = EXAMPLES.get(task)
    if ex is None:
        raise HTTPException(404, f"no example for task '{task}'")
    return ex


@app.get("/history")
def get_history(limit: int = 100, task: str | None = None) -> dict:
    return {"count": history.count(), "records": history.recent(limit=limit, task=task)}


@app.delete("/history")
def clear_history() -> dict:
    history.clear()
    return {"status": "cleared"}


# ----------------------------- prediction core -----------------------------

def _predict(task: str, payload: dict) -> PredictResponse:
    original = {k: v for k, v in payload.items()}  # pre-standardization snapshot, for History re-run
    standardized = None
    if task in _SMILES_TASKS:
        std = neutral_parent(payload["smiles"])
        if std is None:
            raise HTTPException(400, "could not parse SMILES")
        standardized = std
        payload["smiles"] = std
    if task == "dti" and not payload.get("target_seq"):
        try:
            payload["target_seq"] = sequences.fetch_uniprot_sequence(payload["uniprot_acc"])
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"could not fetch UniProt {payload.get('uniprot_acc')}: {e}")
    try:
        providers = mammal_runner.run_task(task, payload)
    except KeyError:
        raise HTTPException(404, f"unknown task '{task}'")
    r = rel.get_reliability(task)
    history.append(task, original, providers[0]["prediction"], r.badge, providers[0]["provider_name"])
    return PredictResponse(
        task=task,
        prediction=providers[0]["prediction"],
        reliability=r.to_dict(),
        providers=providers,
        standardized_smiles=standardized,
    )


# ----------------------------- batch triage -----------------------------
# Quiver's real use is ranking MANY compounds (DEL/DFP screens), not one at a
# time. Each row is validated + standardized + (for DTI) UniProt-resolved, then
# all rows run under a single inference-lock hold. A bad row becomes an error row;
# successful rows are ranked best-score-first. The verdict travels with the batch.

def _preprocess_row(task: str, payload: dict, uniprot_cache: dict) -> tuple[dict, str | None]:
    """Standardize SMILES + resolve a DTI target (cached per accession).

    Returns (clean_payload_to_score, standardized_smiles_or_None). Raises
    ValueError on a bad SMILES or an unresolvable/absent target.
    """
    clean = dict(payload)
    standardized = None
    if task in _SMILES_TASKS:
        std = neutral_parent(clean.get("smiles") or "")
        if std is None:
            raise ValueError("could not parse SMILES")
        standardized = std
        clean["smiles"] = std
    if task == "dti" and not clean.get("target_seq"):
        acc = clean.get("uniprot_acc")
        if not acc:
            raise ValueError("provide target_seq or uniprot_acc")
        if acc in uniprot_cache:
            clean["target_seq"] = uniprot_cache[acc]
        else:
            seq = sequences.fetch_uniprot_sequence(acc)  # network; may raise
            uniprot_cache[acc] = seq
            clean["target_seq"] = seq
    return clean, standardized


def _rank_value(prediction: dict | None) -> float | None:
    """Score used to rank a row (higher = better for every batchable head)."""
    if not prediction:
        return None
    if prediction.get("score_kind") in ("pkd", "normalized_p1", "raw_p1"):
        return prediction.get("value")
    return None


@app.post("/predict/{task}/batch", response_model=BatchResponse)
def predict_batch(task: str, req: BatchRequest) -> BatchResponse:
    model_cls = _REQUEST_MODEL.get(task)
    if model_cls is None:
        raise HTTPException(404, f"task '{task}' is not batchable")
    r = rel.get_reliability(task)

    requested = len(req.rows)
    rows_in = req.rows[:MAX_BATCH_ROWS]
    dropped = requested - len(rows_in)

    # Phase 1 — validate + preprocess every row (no model yet). Network UniProt
    # fetches happen here, OUTSIDE the inference lock, cached per accession.
    uniprot_cache: dict[str, str] = {}
    prepared: list[dict] = []          # rows that will be scored, with back-refs
    error_rows: list[dict] = []        # rows that failed before scoring
    for i, row in enumerate(rows_in):
        try:
            validated = model_cls(**row).model_dump()
            clean, std = _preprocess_row(task, validated, uniprot_cache)
            prepared.append({"index": i, "inputs": row, "clean": clean, "standardized_smiles": std})
        except (ValidationError, ValueError) as e:
            error_rows.append({"index": i, "inputs": row, "error": str(e).splitlines()[0]})
        except Exception as e:  # noqa: BLE001  (e.g. UniProt fetch failure for one row)
            error_rows.append({"index": i, "inputs": row, "error": f"{type(e).__name__}: {e}"})

    # Phase 2 — score the prepared rows under one inference-lock hold.
    results = mammal_runner.run_task_batch(task, [p["clean"] for p in prepared])

    scored: list[dict] = []
    for p, res in zip(prepared, results):
        if res["error"] is not None:
            error_rows.append({"index": p["index"], "inputs": p["inputs"], "error": res["error"]})
            continue
        providers = res["providers"]
        scored.append({
            "index": p["index"],
            "inputs": p["inputs"],
            "standardized_smiles": p["standardized_smiles"],
            "prediction": providers[0]["prediction"],
            "providers": providers,
        })

    # Rank successful rows best-first; errored rows follow, unranked.
    scored.sort(key=lambda s: (_rank_value(s["prediction"]) is not None,
                               _rank_value(s["prediction"]) or 0.0), reverse=True)
    out_rows = []
    for rank, s in enumerate(scored, start=1):
        out_rows.append({**s, "rank": rank, "error": None})
    for e in sorted(error_rows, key=lambda x: x["index"]):
        out_rows.append({"index": e["index"], "rank": None, "inputs": e["inputs"],
                         "standardized_smiles": None, "prediction": None, "providers": None,
                         "error": e["error"]})

    # One compact history entry per batch (top result), so batch runs are visible
    # without spamming the log with N rows.
    if scored:
        top = scored[0]
        history.append(task, {"_batch": f"{len(scored)} scored / {requested} submitted"},
                       top["prediction"], r.badge, f"batch · {len(scored)} rows")

    return BatchResponse(
        task=task,
        reliability=r.to_dict(),
        requested=requested,
        processed=len(rows_in),
        dropped=dropped,
        rows=out_rows,
    )


# ----------------------------- predict endpoints -----------------------------

@app.post("/predict/dti", response_model=PredictResponse)
def predict_dti(req: DtiRequest) -> PredictResponse:
    return _predict("dti", req.model_dump())


@app.post("/predict/ppi", response_model=PredictResponse)
def predict_ppi(req: PpiRequest) -> PredictResponse:
    return _predict("ppi", req.model_dump())


@app.post("/predict/bbbp", response_model=PredictResponse)
def predict_bbbp(req: BbbpRequest) -> PredictResponse:
    return _predict("bbbp", req.model_dump())


@app.post("/predict/clintox_tox", response_model=PredictResponse)
def predict_clintox_tox(req: SmilesRequest) -> PredictResponse:
    return _predict("clintox_tox", req.model_dump())


@app.post("/predict/clintox_fda", response_model=PredictResponse)
def predict_clintox_fda(req: SmilesRequest) -> PredictResponse:
    return _predict("clintox_fda", req.model_dump())


@app.post("/predict/solubility", response_model=PredictResponse)
def predict_solubility(req: SolubilityRequest) -> PredictResponse:
    return _predict("solubility", req.model_dump())


@app.post("/predict/tcr", response_model=PredictResponse)
def predict_tcr(req: TcrRequest) -> PredictResponse:
    return _predict("tcr", req.model_dump())


def _wrap_base(task: str, provider_name: str, prediction: dict, inputs: dict) -> PredictResponse:
    """Wrap a single base-model output (generation/embeddings) in the standard response + log it."""
    r = rel.get_reliability(task)
    history.append(task, inputs, prediction, r.badge, provider_name)
    return PredictResponse(
        task=task,
        prediction=prediction,
        reliability=r.to_dict(),
        providers=[{"provider_name": provider_name, "provider_kind": "ibm_public", "prediction": prediction}],
    )


@app.post("/predict/generation", response_model=PredictResponse)
def predict_generation(req: GenerateRequest) -> PredictResponse:
    pred = mammal_runner.run_generate(req.prompt, req.kind)
    return _wrap_base("generation", "IBM base (span-infill)", pred, req.model_dump())


@app.post("/predict/embeddings", response_model=PredictResponse)
def predict_embeddings(req: EmbedRequest) -> PredictResponse:
    pred = mammal_runner.run_embed(req.text, req.kind)
    return _wrap_base("embeddings", "IBM base (mean-pool embedding)", pred, req.model_dump())


# Spec-named aliases (ui_spec §3 lists optional /generate, /embed).
@app.post("/generate", response_model=PredictResponse)
def generate_alias(req: GenerateRequest) -> PredictResponse:
    return predict_generation(req)


@app.post("/embed", response_model=PredictResponse)
def embed_alias(req: EmbedRequest) -> PredictResponse:
    return predict_embeddings(req)


# ----------------------------- evidence docs (read-only) -----------------------------
# Make the reliability "evidence:" citations clickable: serve the actual writeups,
# read-only, but ONLY from results/ and docs/ (path-traversal-safe). This is the
# trust layer — let the user open the receipt behind any verdict.

_DOC_ROOTS = [(REPO / "results").resolve(), (REPO / "docs").resolve()]


@app.get("/doc/{path:path}", response_class=PlainTextResponse)
def get_doc(path: str) -> PlainTextResponse:
    target = (REPO / path).resolve()
    if not any(target == root or root in target.parents for root in _DOC_ROOTS):
        raise HTTPException(403, "only results/ and docs/ are served")
    if not target.is_file():
        raise HTTPException(404, f"no such doc: {path}")
    return PlainTextResponse(target.read_text(), media_type="text/markdown; charset=utf-8")


# ----------------------------- frontend (same-origin → no CORS) -----------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(FRONTEND / "index.html"))
