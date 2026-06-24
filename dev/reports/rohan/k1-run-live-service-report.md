# Task K1 — `run_live` as a clean service boundary + the real front door — report

**Branch:** `rohan/k1-run-live-service`
**Built-By:** rohan
**Tier:** Feature

## Goal
Make the harnessed live firm (`live_engine.run_live`) reachable behind a stable, documented
contract — the integration point LOKA will call — and make `serve.py` serve the **real**
harnessed firm by default (keeping the canned scenarios as an explicit, labeled `$0` fallback).

## What shipped

### 1. Frozen + documented contract (single source of truth)
- **`contracts/run_live_schema.md`** — prose contract for the `run_live()` output dict: the entry
  point, every top-level key, the `discover` / `consult` sub-shapes, provenance honesty, and the
  **additive-only** stability rule. This dict **is** the API the front end / LOKA consume.
- **`contracts/run_live_schema.py`** — the machine-readable `RUN_LIVE_SCHEMA` + a
  `validate_run_live(result) -> list[str]` helper (stdlib `jsonschema_min`). The schema is
  **additive-friendly** (no `additionalProperties: false` on objects), so callers may stamp extra
  keys (`via`, `live`) without breaking validation. Required keys are exactly the ones `run_live`
  always emits; `written` is correctly typed as `integer` (a record count, not a bool — verified
  against a real run).

### 2. `serve.py` serves the harnessed firm
- New `_run_engine_live(query, ctx=None)` calls `live_engine.run_live` and stamps the HTTP envelope
  `via="engine-live"`, `live=True`. `run_live` is designed never to raise (the harness abstains
  honestly for a down backend); a defensive `try/except` still guarantees the endpoint can never
  crash — on a programming error it returns an honest plan-only envelope (`via="plan"`).
- New `_run_canned(query)` keeps the pre-captured scenarios reachable as an explicit, labeled `$0`
  offline fallback (`via="canned"`); honest note when no scenario matches.
- New `route_api_run(query, mode)` — a **pure, testable routing function**:
  `live` (default) → engine-live · `canned` → scenario · `claude` → headless-Claude reconstruction
  (`via="claude-subscription"`).
- `GET /api/run?q=` now defaults to **engine-live**; `?mode=canned` / `?mode=claude` select the
  fallbacks. The Console (which uses `/api/chat`, not `/api/run`) is unaffected.
- Honest `via` vocabulary: **`engine-live` | `canned` | `claude-subscription`** (+ `plan` for the
  defensive degrade).

### Stdlib-only preserved
`serve.py` stays on `http.server`; `run_live_schema.py` uses only `contracts.jsonschema_min`.
No third-party import entered the runtime (Gate 4 grep clean).

## Gate evidence

- **Gate 1 — full suite:** `bash dev/run-tests.sh` → **355 GREEN** (contracts 29 · harness 68 ·
  emet 18 · memory 14 · selfimprove 20 · moat 68 · tests 138). Baseline 343; +12 new
  (6 schema-validator + 6 serve-routing/conformance).
- **Gate 3 — provenance/secrets:** no secrets, no binaries. No new provenance labels (the `via`
  markers are HTTP envelope stamps, not fact-provenance labels — fact provenance stays in the
  allowed set). Public-identifiers-only intact.
- **Gate 4 — stdlib runtime:** grep of `serve.py` / `live_engine.py` / `run_live_schema.py` for
  pandas/numpy/sklearn/scipy/pyarrow/requests/torch/joblib → **none**.
- **Gate 5 — functional verification (RAN it over real HTTP):** started `serve.py` and curled
  `/api/run`:
  - **Default `GET /api/run?q="is TSC2 a viable CNS target?"`** → `via=engine-live`, `live=True`,
    `_via=harness-live`, a real `engagement_id`, **5 dossier facts from REAL backends** (q-models,
    aso-tox, gnomad, gtex, interpro, gprofiler all `ok` with real provenance), claude-subagents
    `abstained`/emet `escalated` **honestly** (claude CLI deliberately made unreachable for the
    test → the documented degraded path), 5 persona verdicts. **NOT a canned scenario.**
  - **Live HTTP response validated against the contract** → `validate_run_live` returned `[]`
    (0 errors) on the real `engine-live` response.
  - **Adversarial:** empty `q` → HTTP 400; `?mode=canned` → `via=canned, live=False`;
    `?mode=claude` with claude down → honest `via=plan` degrade (no crash).

Server runtime artifacts produced during Gate-5 (engagement traces, memory appends) were reverted —
not part of the diff. Offline tests use temp `SAPPHIRE_ENGAGEMENTS_DIR`/`SAPPHIRE_MEMORY_DIR`, so
the suite never pollutes the repo stores.

## Out of scope (per brief)
The LOKA adapter itself (LOKA code isn't in the repo yet) — K1 delivers the **boundary** LOKA calls.
Rewiring the Console to the `run_live` shape is a separate follow-up (the Console uses `/api/chat`).

## Files
- `sapphire-orchestrator/contracts/run_live_schema.md` (new)
- `sapphire-orchestrator/contracts/run_live_schema.py` (new)
- `sapphire-orchestrator/contracts/tests/test_run_live_schema.py` (new)
- `sapphire-orchestrator/tests/test_serve_run_live.py` (new)
- `sapphire-orchestrator/serve.py` (modified — routing + helpers + docstring)
