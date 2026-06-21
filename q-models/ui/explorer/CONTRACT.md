# Quiver Capability Explorer — build contract (v2, track-organized)

This is the **single source of truth** for the new Explorer build. Every agent reads
this file + `ui/explorer/tracks.json`. Do not invent track data — it all comes from
`tracks.json` (which was generated deterministically from the canonical scorecard).

## What we're building

A NEW Explorer (sibling to the old MAMMAL-head Explorer in `ui/backend` + `ui/frontend`).
The old one is organized by MAMMAL head; THIS one is organized by **Quiver capability track**:
one tab per track, each routed to **the best model we found for that task** (often NOT MAMMAL —
ESM-2-650M, Boltz-2, MolFormer-XL, ChemBERTa-2, PROTON, etc.), with that model's **empirical
operating envelope** ("verdict") shown on every result.

**Scope for this build: FRONTEND COMPLETE + BACKEND FULLY WIRED EXCEPT THE AWS MODEL CALL.**
The user wants it runnable "just by doing the final AWS connection." So:
- Everything works locally today: routes, schemas, the track registry, history, the report
  page, the reliability/operating-envelope verdicts, examples, batch input parsing.
- The ONLY stubbed thing is the actual model inference, isolated to ONE function in
  `inference.py`. Until an AWS endpoint is configured it returns the per-track `stub_prediction`
  from `tracks.json`, flagged `stubbed: true`, and the UI shows a clear "DEMO — model call not
  wired" banner. When `EXPLORER_AWS_ENDPOINT` env var is set, that one function POSTs to it.

## File layout (who owns what — DISJOINT, no overlaps)

```
ui/explorer/
  tracks.json          # DATA CONTRACT — already written, do not modify
  CONTRACT.md          # this file — do not modify
  backend/
    __init__.py        # (empty) — BACKEND agent
    app.py             # FastAPI app, all routes, serves frontend — BACKEND agent
    registry.py        # loads tracks.json, exposes track lookup + badge metadata — BACKEND agent
    inference.py       # THE STUB BOUNDARY: run_inference(track_id, payload) -> dict — BACKEND agent
    schemas.py         # pydantic request/response models — BACKEND agent
    history.py         # append-only JSONL history (port from ui/backend/history.py) — BACKEND agent
  frontend/
    index.html         # shell — FRONTEND agent
    styles.css         # dark theme (port the look from ui/frontend/index.html) — FRONTEND agent
    app.js             # SPA logic: tabs, forms, results, history, report — FRONTEND agent
  README.md            # what it is + how to run + how to wire AWS — DOCS agent
  SETUP.md             # env + dependencies + the single AWS wiring step — DOCS agent
  tests/
    conftest.py        # TestClient fixture, temp history path — DOCS agent
    test_smoke.py      # endpoint smoke tests (stub mode) — DOCS agent
```

## API contract (backend ↔ frontend agree on THIS)

Base: same-origin (frontend served by FastAPI at `/`). All API routes under `/api`.

- `GET /api/meta` → `{title, subtitle, banner, badges, stubbed: bool}` from `tracks.json._meta`
  plus whether inference is currently stubbed (no AWS endpoint configured).
- `GET /api/tracks` → `{tracks: [...]}` — the full track list from `tracks.json` (each track
  minus the heavy `stub_prediction`; include everything the UI needs to render a tab + report row).
- `GET /api/track/{track_id}` → one track object (incl. inputs, example, verdict, performance).
- `GET /api/report` → `{tracks: [...]}` — report-page data: per track `{n, label, emoji,
  best_model, license, performance.headline, badge, verdict.headline, source}`. May reuse /api/tracks.
- `GET /api/examples/{track_id}` → the track's `example` dict + `example_note`.
- `POST /api/predict/{track_id}` body = the track's input fields → `PredictResponse`:
  ```
  {
    track: str, label: str, model: str, license: str,
    stubbed: bool,                      # true until AWS wired
    prediction: { score_kind: str, ... },   # track-specific; in stub mode == tracks.json stub_prediction
    verdict: { badge, badge_label, badge_emoji, headline, why, recommended_use, source },
    performance: { headline, metrics:[{name,value}] },
    inputs_echo: {...}                  # original inputs, for history re-load
  }
  ```
  Informational tracks (crossmodal, `informational: true`) return `score_kind: "none"` and never
  attempt a model call even when AWS is wired.
- `POST /api/predict/{track_id}/batch` body = `{rows:[{...}]}` → `{track, rows:[{index, rank,
  inputs, prediction, error}], reliability/verdict}` for batch-enabled tracks (those with a
  `batch` key in tracks.json: bbbp, toxicity). Rank best-first by the prediction's primary score.
- `GET /api/history?limit=&track=` / `DELETE /api/history` → history (port semantics from
  `ui/backend/history.py`: JSONL, server-side, env-overridable path `EXPLORER_HISTORY`).
- `GET /doc/{path}` → serve `results/` + `docs/` markdown read-only (path-traversal-safe), so the
  `source:` citations in each verdict are clickable. Port from `ui/backend/app.py`.
- `GET /` → serve `frontend/index.html`; `/styles.css`, `/app.js` served as static.

### The stub boundary (inference.py) — the heart of "wire AWS later"

```python
# inference.py — the ONE place that talks to a model. Everything else is done.
import os, json, urllib.request
from .registry import get_track

AWS_ENDPOINT = os.environ.get("EXPLORER_AWS_ENDPOINT")  # e.g. https://<id>.execute-api.../predict

def is_stubbed() -> bool:
    return not AWS_ENDPOINT

def run_inference(track_id: str, payload: dict) -> dict:
    track = get_track(track_id)
    if track.get("informational"):
        return {**track["stub_prediction"]}            # never a model call
    if is_stubbed():
        pred = dict(track["stub_prediction"])
        pred["_stub"] = True
        return pred
    # --- AWS WIRING (the final step the user will do) ---
    req = urllib.request.Request(
        AWS_ENDPOINT,
        data=json.dumps({"track": track_id, "model": track["aws_model_key"], "inputs": payload}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)
```
Keep it exactly this shape: a single clearly-commented AWS block. The backend/frontend must work
fully in stub mode with NO AWS, NO GPU, NO model weights.

## Visual / UX spec (match the existing Explorer's feel, then make it nicer)

Port the dark theme from `ui/frontend/index.html` (`:root` CSS vars: `--bg:#0f1115`,
`--panel:#171a21`, `--panel2:#1e222b`, `--line:#2a2f3a`, `--text:#e6e9ef`, `--muted:#9aa3b2`,
`--accent:#5b9dff`). Badge colors: reliable `#1a7f37`, caution `#bf8700`, dont_use `#cf222e`,
low_value `#6e7781`, split `#137a7f`, build `#8957e5` (violet for moat). Use system font stack;
monospace (`ui-monospace,Menlo`) for sequences/SMILES.

Layout:
- **Header**: title + subtitle (from /api/meta).
- **Strategic banner** (amber, like the existing one): the `_meta.banner`.
- **Stub banner** (only when `stubbed`): a clear, dismissible-but-prominent strip:
  "⚙️ DEMO MODE — model calls are stubbed. Results below are illustrative shapes, not real
  predictions. Wire `EXPLORER_AWS_ENDPOINT` to go live." Use accent/violet, not alarming red.
- **Tabs**: one per track (emoji + short label, in track `n` order), then **History** (🕘) and
  **Report** (📊). Active tab styled like the existing `.tab.active`.
- **Track tab body**: a card with
  - track question + tagline,
  - a "Best model" chip row: `best_model` + license pill + `performance.headline`,
  - the **verdict panel** (reuse the existing `.rel` panel design: colored left-border by badge,
    badge pill, headline, why, "Recommended use", clickable evidence links to /doc/...),
  - the **input form** built from the track's `inputs` (text / textarea / optional),
    a "Run" button + "Load example" ghost button,
  - for `batch`-enabled tracks: a Single/Batch toggle (port the pattern; batch = textarea of
    rows → ranked table),
  - the **result panel**: render per `score_kind` (embedding → nearest family + scores;
    affinity/probability → big number + call; panel → per-endpoint rows; ranking → shortlist
    table; complex → confidence+affinity; analogs → neighbor table; panel_ranking → ranked
    targets; none → just the verdict/build-plan). Always re-show the verdict under the result.
  - informational track (crossmodal): no Run button — show the verdict + a "build plan" call-out.
- **History tab**: list of past runs (newest first) with track badge, summary, inputs preview,
  timestamp, and a "Load into tab" button that repopulates the form. Refresh + Clear buttons.
  Port from the existing history UI.
- **Report tab**: the centerpiece "which model per track + how it performs" page. A clean table:
  Track | Best model | License | Headline performance | Verdict (badge + one-liner) | Receipt link.
  Plus a short legend of the 6 badges. This renders from /api/report. Make it presentable — this
  is what gets shown to James.

Quality bar: responsive (works at laptop width), no external JS/CSS/CDN (vanilla JS, single
same-origin app — matches the existing one), accessible (labels tied to inputs, keyboard-usable
tabs), no console errors, graceful error rendering (show backend `detail` on non-200).

## Conventions
- Python 3.11, FastAPI + pydantic v2 (`model_dump`), stdlib only beyond fastapi/uvicorn/pydantic.
- No network calls in stub mode (UniProt fetch for DTI can be a TODO/optional; in stub mode the
  target sequence isn't needed). Keep imports light so `import ui.explorer.backend.app` is fast.
- Reuse, don't re-import, the old `ui/backend` — this is a self-contained new app under `ui/explorer`.
- Run command (document it): `EXPLORER_HISTORY=/tmp/ex_hist.jsonl /opt/anaconda3/envs/mammal/bin/uvicorn ui.explorer.backend.app:app --reload` from repo root.
