# `run_live` output contract — the live-firm service boundary

**Single source of truth** for what `live_engine.run_live()` returns. This dict **is the API**
the front end (`serve.py` → `/api/run`) and the future **LOKA adapter** consume. The
machine-readable schema + validator live next to this file in
[`run_live_schema.py`](run_live_schema.py) (`validate_run_live(result) -> list[str]`).

## Entry point

```python
from live_engine import run_live
result = run_live(query, *, sequences=None, ctx=None, registry=None, engine=None) -> dict
```

- `query` — free-text question / task.
- `sequences` — optional ASO candidate sequences (threaded to the `aso-tox` agent). When `None`,
  pure A/T/G/C tokens of length ≥ 15 are extracted from `query`. This is the documented handoff
  point for the future ASO-Design tool.
- `ctx` — optional harness context dict; inject **mock backends** here for offline/test runs
  (`runner`, `emet_handler`, `qmodels_client`, `python_fns`). Omit for the real backends (real
  moat + real seams; `claude`-subagents shell out to the `claude` CLI; EMET abstains honestly if
  no handler is wired).
- `registry` / `engine` — optional overrides (default: `harness.load_registry()` / a new
  `Orchestrator`).

`run_live` **never raises** for a missing backend: the harness catches the failure and that agent
returns an honest abstain envelope. The result is therefore always well-formed — possibly degraded
(facts missing, agents `abstained`/`escalated`), never fabricated.

## Output shape

Top-level dict, keys (all required):

| key | type | meaning |
|---|---|---|
| `query` | str | echo of the input query |
| `plan` | object | the deterministic engagement plan (`deliverable`, `disease`, `modality`, `agents[]`, `panel[]`, …) |
| `priors` | array | memory records recalled for the query entities (`[]` if none) |
| `discover` | object | the Bucket-1 fact dossier (see below) |
| `consult` | object | `{round1: [verdict, …]}` — Bucket-2 partner verdicts (round 1) |
| `synthesize` | object | `recommendation`, `confidence`, `proposed_experiment`, `entities` |
| `engagement_id` | str | the engagement id (`eng_…`) — the trace key |
| `reflection` | object | `engagement_id`, `written` (int count of memory records), `records[]` |
| `_via` | str | the engine's own provenance marker — always `"harness-live"` |

### `discover` (the fact dossier)

```
discover = {
  "dossier": [ fact, … ],
  "flags":   { "VETO": [str], "DIVERGENCE": [str], "KNOWN_UNKNOWNS": [str] },
  "status":  "complete" | "complete-with-known-unknowns",
  "agents":  [ { "id": str, "status": str, "provenance": str }, … ],
}
```

Each **fact** always carries `value`, `source`, `tier`, `provenance`; it MAY carry `field`,
`confidence`, and a `flag` (`VETO` | `DIVERGENCE` | `KNOWN_UNKNOWN`). Provenance is one of the
allowed labels in [`provenance.py`](provenance.py) (e.g. `moat-real`, `emet-live`, `aso-tox`,
`gnomad`, …).

### `consult.round1` (partner verdicts)

Each verdict always carries `persona`, `stance`, `provenance`, `status`; success verdicts add
`conviction`, `rationale`, `fact_claims`; the abstain path adds `lens`. Personas cite the dossier —
they never invent facts.

## Stability rules

- **Additive-only.** Don't rename or drop a documented key. New top-level keys (e.g. the
  `via` / `live` stamps `serve.py` adds for the HTTP response) are allowed — the schema does **not**
  set `additionalProperties: false`, so additive fields validate cleanly.
- **Provenance honesty.** Every fact's `provenance` is from the allowed set; degraded runs surface
  abstained agents in `discover.agents` and `KNOWN_UNKNOWNS`, never a fake citation.
- A change to this contract updates **this file + `run_live_schema.py` together**, and the
  conformance tests (`contracts/tests/test_run_live_schema.py` +
  `tests/test_serve_run_live.py::TestRealRunLiveConformsToContract`) must stay green.

## `serve.py` HTTP wrapper (`/api/run`)

`serve.py` exposes this dict over HTTP and stamps two extra keys for the client:

- `via` — honest path marker: **`engine-live`** (the harnessed `run_live`, the default),
  `canned` (a pre-captured scenario, `?mode=canned`), or `claude-subscription`
  (headless-Claude reconstruction, `?mode=claude`).
- `live` — bool; `true` for `engine-live` / `claude-subscription`, `false` for `canned`.

`GET /api/run?q=<query>` returns the `engine-live` result by default. The canned scenarios remain
reachable as an explicit, clearly-labeled `$0` offline fallback via `?mode=canned`.
