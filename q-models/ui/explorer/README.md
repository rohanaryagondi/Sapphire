# Quiver Capability Explorer

A web app organized **one tab per Quiver capability track**, where each track is
routed to **the best model we actually found for that task** (often *not* MAMMAL),
with that model's **empirical operating envelope** ("verdict") shown on every result.

This is a sibling to the original MAMMAL-head Explorer (`ui/backend` + `ui/frontend`),
which is organized by MAMMAL head. This one is organized by capability and surfaces
the best-of-breed model per track. The two are independent apps.

> **Single source of truth:** the build spec is [`CONTRACT.md`](CONTRACT.md) and the
> per-track data is [`tracks.json`](tracks.json). All track metadata — best model,
> license, metrics, verdict, inputs, example, stub prediction — comes from
> `tracks.json` (generated deterministically from `docs/models_tracks_scorecard.md`).
> Do not hand-edit track facts anywhere else.

## Build status: runnable today, one step from live

The Explorer is **frontend-complete and backend-wired, except the AWS model call.**
Everything works locally right now with **no AWS, no GPU, no model weights**:
routes, schemas, the track registry, history, the report page, the
reliability/operating-envelope verdicts, examples, and batch input parsing.

The **only** stubbed thing is the actual model inference, isolated to one function
(`run_inference()` in `backend/inference.py`). Until an AWS endpoint is configured it
returns each track's `stub_prediction` from `tracks.json`, flagged `stubbed: true`,
and the UI shows a clear "DEMO MODE — model call not wired" banner.

**To go live, set one environment variable** (see [SETUP.md](SETUP.md)):

```bash
export EXPLORER_AWS_ENDPOINT="https://<id>.execute-api.<region>.amazonaws.com/predict"
```

That flips `is_stubbed()` to `False` and makes `run_inference()` POST each request to
your endpoint. No other code changes are required.

## Track → best model

The nine tracks and the model each tab routes to (from `tracks.json`):

| # | Track | Best model | License | Headline performance | Verdict |
|---|-------|-----------|---------|----------------------|---------|
| 1 | 🧬 Protein Family Clustering | ESM-2-650M | MIT | NN-recall 0.875 (40-gene panel, best-layer) | ✅ Reliable — but layer selection is the real lever, not model choice |
| 2 | 🎯 DTI / Binder Triage | Boltz-2 | MIT | Nav1.8 AUROC 0.714 · mTOR AUROC 1.000 | ⚠️ Best available on Quiver targets — Nav1.8 still marginal |
| 3 | 🧲 Structure-Based Binding | Boltz-2 | MIT | Same model as Track 2 (Boltz-2) | ⚠️ Co-folding route for pockets BindingDB can't reach |
| 4 | 🧠 BBB Penetrance | MolFormer-XL | Apache-2.0 | AUROC 0.889 (vs MAMMAL 0.833) | ◑ MolFormer for the yes's, MAMMAL for the no's — ship both |
| 5 | ☠️ Toxicity / DILI / hERG | ChemBERTa-2 + ADMET-AI | MIT | hERG bal-acc 0.726 · DILI ext TPR 0.73 | ✅ Reliable de-risking gate — use hERG + DILI, never ClinTox |
| 6 | 🕸️ KG / Hypothesis Generation | PROTON (NeuroKG) | MIT + Harvard Dataverse | median 4.3% binder-rank percentile | ◑ Strongly asymmetric — ranking known drugs works; forward is hub noise |
| 7 | 🌉 Cross-Modal Bridge (V1-T) | None (build, don't buy) | n/a | FALSIFIED off-the-shelf (cross-modal cosine 0.08) | 🔨 This is the moat — build a contrastive head on Quiver's own pairs |
| 8 | ⚗️ Generative Chemistry | Morgan FP + Enamine REAL NN | n/a (RDKit + Enamine) | 0.96 similarity (vs MAMMAL 0.72) | ➖ Boring winner — but generation isn't a Quiver bottleneck |
| 9 | 🎯 Off-Target / Selectivity | Boltz-2 | MIT | Ranks Nav1.8 #1 (narrow margins) · ConPLex 0.437 blind | ⚠️ Right paralog order — margins too narrow to call selectivity |

Tracks 3 and 9 fold into Track 2's Boltz-2 endpoint (`aws_model_key: boltz2`).
Track 7 is **informational** — it never makes a model call (there is no public
voltage-trace modality; the value is the build plan, not a prediction).

### Badge legend

| Badge | Meaning |
|-------|---------|
| ✅ Reliable | Use the number; verdict is well-supported on Quiver substrate. |
| ⚠️ Use with caution | Best available, but marginal or directional — read the envelope. |
| ◑ Split verdict | Trust one direction only (e.g. yes vs no, or ranking vs prediction). |
| ➖ Low value | Works but not a Quiver bottleneck — deprioritized. |
| 🔨 Build, don't buy | Nothing public works (and nothing public can). This is the moat. |
| ⛔ Do not use | Worse than chance / wrong task — do not ship. |

## How to run (stub mode — no AWS)

From the repo root (`mammal-models-wt/`):

```bash
EXPLORER_HISTORY=/tmp/ex_hist.jsonl \
  /opt/anaconda3/envs/mammal/bin/uvicorn ui.explorer.backend.app:app --reload
```

Then open <http://localhost:8000/> (Swagger at `/docs`). The header shows a
**DEMO MODE** banner; every result is the track's illustrative `stub_prediction`
shape flagged `stubbed: true`. See [SETUP.md](SETUP.md) for the conda env, the exact
dependency list, the environment variables, and the AWS endpoint I/O contract.

### Two themes, same app

- **Default (`/`)** — the standard scheme (blue accent), `frontend/index.html` + `styles.css`.
- **Quiver-branded (`/quiver`)** — a separate re-skin in Quiver Bioscience brand colors
  (purple→magenta→red signature gradient, Poppins, deep-navy / pale-lavender surfaces),
  `frontend/quiver.html` + `quiver.css`. It reuses the **same** `app.js` and `/api/*`
  backend verbatim — only the stylesheet and font differ — and keeps its own light/dark
  preference (`qx-theme-quiver`). The default version is unaffected.

## API at a glance

All routes are same-origin (the FastAPI app serves the frontend) and live under `/api`,
except the read-only doc server at `/doc/{path}`.

| Route | Purpose |
|-------|---------|
| `GET /api/meta` | title/subtitle/banner/badges + whether inference is `stubbed` |
| `GET /api/tracks` | full track list (sans the heavy `stub_prediction`) |
| `GET /api/track/{track_id}` | one track object (inputs, example, verdict, performance) |
| `GET /api/report` | report-page rows — best model + verdict per track |
| `GET /api/examples/{track_id}` | the track's `example` + `example_note` |
| `POST /api/predict/{track_id}` | run one prediction → `PredictResponse` (stub in demo mode) |
| `POST /api/predict/{track_id}/batch` | ranked batch for batch-enabled tracks (bbbp, toxicity) |
| `GET /api/history?limit=&track=` | server-side JSONL run history |
| `DELETE /api/history` | clear history |
| `GET /doc/{path}` | serve `results/` + `docs/` markdown read-only (path-traversal-safe) |
| `GET /` | the single-page frontend |

The full request/response shapes and the stub boundary are specified in
[`CONTRACT.md`](CONTRACT.md) §"API contract".

## Layout

```
ui/explorer/
  tracks.json          # DATA CONTRACT (do not hand-edit track facts elsewhere)
  CONTRACT.md          # build spec
  backend/             # FastAPI app, registry, schemas, history, the inference stub boundary
  frontend/            # single-page dark-theme UI (vanilla JS, no CDN)
  README.md            # this file
  SETUP.md             # env + deps + the one AWS wiring step
  tests/               # stub-mode smoke tests (pytest + FastAPI TestClient)
```

## Tests

Stub-mode smoke tests live in `tests/`. From the repo root:

```bash
/opt/anaconda3/envs/mammal/bin/python -m pytest ui/explorer/tests -q
```

They run entirely in stub mode (no AWS, no GPU, no weights): they assert
`/api/meta` reports `stubbed: true`, all 9 tracks load, every `POST /api/predict/*`
returns 200 with a `stub`-flagged prediction whose `score_kind` matches `tracks.json`,
the crossmodal track returns `score_kind: "none"`, a BBBP batch ranks its rows,
history grows after a predict and clears on DELETE, and `/doc` serves a known
results markdown while rejecting path traversal.
