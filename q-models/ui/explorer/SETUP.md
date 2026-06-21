# Quiver Capability Explorer — setup

This is the runbook: environment, dependencies, the run command, the two
environment variables, and the exact contract the AWS endpoint must satisfy when
you wire it live. Read [`CONTRACT.md`](CONTRACT.md) for the full build spec and
[`README.md`](README.md) for the overview and the track → best-model table.

## 1. Environment

Use the project's conda env (`mammal`, Python 3.11). The web layer is deliberately
light — the Explorer runs in **stub mode** with no model weights, no GPU, and no AWS,
so you do not need any of the heavy ML stack (`biomed-multi-alignment`, torch, RDKit)
just to run it.

```bash
conda activate mammal        # Python 3.11 — /opt/anaconda3/envs/mammal
```

If you prefer not to touch conda, any Python 3.11 with the three deps below works,
because nothing in stub mode imports the model libraries.

## 2. Dependencies

The Explorer's backend needs only:

```bash
pip install fastapi uvicorn pydantic    # pydantic v2
pip install markdown                     # renders /doc/*.md as styled HTML pages
```

For the tests, add pytest and the ASGI test transport:

```bash
pip install pytest httpx                 # httpx backs Starlette's TestClient
```

Everything else is the Python standard library (`json`, `os`, `urllib.request`,
`pathlib`, `threading`, `uuid`, `datetime`). No external JS/CSS/CDN on the frontend.

> Note: `USE_TF=0 USE_FLAX=0` (the macOS TensorFlow-import deadlock workaround used
> elsewhere in this repo) is **not** needed for the Explorer in stub mode — it never
> imports transformers. It only matters once you put a real model behind the AWS
> endpoint, and that runs on AWS, not on this host.

## 3. Run

From the **repo root** (`mammal-models-wt/`):

```bash
EXPLORER_HISTORY=/tmp/ex_hist.jsonl \
  /opt/anaconda3/envs/mammal/bin/uvicorn ui.explorer.backend.app:app --reload
```

Open <http://localhost:8000/> (Swagger at `/docs`). In stub mode the header shows a
**DEMO MODE** banner and every prediction returns the track's `stub_prediction`
shape flagged `stubbed: true`.

## 4. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXPLORER_HISTORY` | `ui/explorer/backend/_history.jsonl` (gitignored) | Path to the append-only JSONL run history. Server-side on purpose: survives restarts and is one source of truth a fresh session can read. Point it at a temp file in tests. |
| `EXPLORER_AWS_ENDPOINT` | *(unset)* | The model-inference URL (the `/predict` of the GPU server). **While unset, the Explorer is stubbed.** Setting it flips `is_stubbed()` to `False` and makes `run_inference()` POST to it. This is the one step to go live. |
| `EXPLORER_AWS_API_KEY` | *(unset)* | Optional. If set, sent as the `x-api-key` header on every endpoint call (use if you front the server with API Gateway / a proxy that checks a key). |
| `EXPLORER_AWS_TIMEOUT` | `600` | Per-request timeout (seconds). Default 600 because Boltz-2 co-folding (DTI / structure / selectivity) is minutes per pair even on a warm endpoint. |

`EXPLORER_AWS_ENDPOINT` / `_API_KEY` / `_TIMEOUT` are read by `backend/inference.py`
**at call time** (a running process can be flipped live without a reimport);
`EXPLORER_HISTORY` is read by `backend/history.py` at process start.

## 5. Going live — the AWS wiring

The wiring is **built and tested** (against a local mock of the endpoint contract);
the only thing not done is launching the GPU instance. Three pieces, all in `aws/`:

| File | Role |
|------|------|
| `aws/explorer_inference_server.py` | The GPU-side FastAPI model server. `POST /predict` receives `{track, model, inputs}` and dispatches on `model` (the track's `aws_model_key`) to the right model, returning the prediction body for that track's `score_kind`. Models load lazily + cached. `GET /health` reports CUDA + loaded models. |
| `aws/launch_explorer_endpoint.py` | Provisions ONE GPU instance running that server. **Dry-run by default** — prints the plan and the `run-instances` it would call, and launches *nothing* unless invoked with `--launch --yes`. |
| `aws/explorer_endpoint_userdata.sh` | Boot script: self-contained venv (torch cu121 + transformers + rdkit + sklearn), pulls the server + artifacts from S3, starts uvicorn on `:8080`, and self-terminates after `--max-minutes` (default 120) as a budget backstop. |

### Bring-up (when you're ready to spend ~$1/hr)

```bash
# 1. stage the server + helpers (+ any trained artifacts) to your bucket
aws s3 cp aws/explorer_inference_server.py s3://rohan-mammal-bootstrap-20260610-213029/explorer_endpoint/
aws s3 cp aws/boltz_runner.py              s3://rohan-mammal-bootstrap-20260610-213029/explorer_endpoint/
# (optional) aws s3 cp -r artifacts/  s3://.../explorer_endpoint/artifacts/   # chemberta probes, ref library

# 2. preview the launch (touches nothing), then actually launch
python aws/launch_explorer_endpoint.py                  # DRY RUN — prints the plan
python aws/launch_explorer_endpoint.py --launch --yes   # provisions g5.xlarge (costs $)

# 3. open :8080 to your IP in the SG (or SSH-tunnel it), then point the Explorer at it
export EXPLORER_AWS_ENDPOINT="http://<instance-public-dns>:8080/predict"
/opt/anaconda3/envs/mammal/bin/uvicorn ui.explorer.backend.app:app --reload
# terminate the instance when done:  aws ec2 terminate-instances --instance-ids <id>
```

No backend code changes — `inference.py` already contains the single, clearly-marked
AWS block, and `EXPLORER_AWS_ENDPOINT` is the only switch. Guardrails apply:
**$15/session hard cap**, instances tagged `Owner=RohanAryaGondi`, only touch your own
EBS (`vol-066389517f2740f19`) and instances you launch.

### What `run_inference()` sends

For each non-informational track, `run_inference(track_id, payload)` issues an HTTP
`POST` to `EXPLORER_AWS_ENDPOINT` with `Content-Type: application/json` (and `x-api-key`
if `EXPLORER_AWS_API_KEY` is set), timeout `EXPLORER_AWS_TIMEOUT` (default 600 s):

```json
{
  "track": "<track_id>",          // e.g. "dti", "bbbp", "family_clustering"
  "model": "<aws_model_key>",     // tracks.json aws_model_key, e.g. "boltz2", "esm2_650m"
  "inputs": { ...payload... }      // the validated track input fields the user submitted
}
```

`aws_model_key` per track (from `tracks.json`):

| Track | `aws_model_key` |
|-------|-----------------|
| family_clustering | `esm2_650m` |
| dti | `boltz2` |
| structure_binding | `boltz2` |
| bbbp | `molformer_xl` |
| toxicity | `chemberta2` |
| kg_hypothesis | `proton` |
| crossmodal | `null` — **never called** (informational track) |
| generative | `morgan_fp` |
| selectivity | `boltz2` |

The endpoint must dispatch on `model` (or `track`) to the right model.

### What the AWS endpoint must return

The endpoint must return a JSON object that **is the `prediction` body** for that
track — i.e. the same shape as the track's `stub_prediction` in `tracks.json`, minus
the `_stub`/`note` markers. The backend wraps it into the standard `PredictResponse`
(adding `track`, `label`, `model`, `license`, `verdict`, `performance`,
`inputs_echo`, and `stubbed: false`). The required field is `score_kind`, plus the
per-kind payload:

| Track(s) | `score_kind` | Required payload |
|----------|-------------|------------------|
| family_clustering | `embedding` | `nearest_family` (str), `family_scores` (obj name→0–1), `dim` (int) |
| dti | `affinity` | `value` (float, predicted pKd), `units` (str), `binder_call` (str) |
| structure_binding | `complex` | `confidence` (0–1), `affinity` (float pKd), `units` (str) |
| bbbp | `probability` | `value` (0–1), `call` (str), `providers` (list of `{name, value, call}`) |
| toxicity | `panel` | `endpoints` (list of `{name, value, call, model}`) |
| kg_hypothesis | `ranking` | `rank_percentile` (0–1), `shortlist` (list of `{drug, rank_pct, note?}`) |
| generative | `analogs` | `neighbors` (list of `{smiles, similarity, name?}`) |
| selectivity | `panel_ranking` | `ranking` (list of `{target, score, rank}`) |
| crossmodal | `none` | informational — **no model call ever** |

Example — a live DTI response body from the endpoint:

```json
{ "score_kind": "affinity", "value": 6.42, "units": "pKd (predicted)", "binder_call": "likely binder" }
```

Batch-enabled tracks (`bbbp`, `toxicity`) call the endpoint per row; the backend
ranks rows best-first by the prediction's primary score. Anything the endpoint
returns beyond the required fields is passed through to the UI unchanged.

## 6. Tests

```bash
/opt/anaconda3/envs/mammal/bin/python -m pytest ui/explorer/tests -q
```

The tests run in stub mode only (no `EXPLORER_AWS_ENDPOINT`), point `EXPLORER_HISTORY`
at a per-test temp file via the `conftest.py` fixture, and assert the stub-mode API
contract end to end.
