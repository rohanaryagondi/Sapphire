# frontend2 — Sapphire's custom 3-pane console (stdlib-only)

A thin, **Python-standard-library-only** front end that realizes **Hayes's adopted console
design** (`docs/design/console-ui/sapphire_chat.html` on `hayes/console-ui-refine`) — the
**violet 3-pane** (agent wing · chat · Sources & Trace), the **per-subagent agent-wing cards**,
and the **attributed findings** — wired to the **real firm** via `live_engine.run_live`, with the
**live trace streamed** over Server-Sent Events.

The palette is Hayes's verbatim: violet canvas `#1a1722`, accent `--purple #a07cff`, neutral nav,
Inter. The live-data layers (the profile selector, the honesty markers, the data-plane grouping,
the VETO/DIVERGENCE callouts, the roundtable spread) extend that token system — no new look was
invented.

## Why this exists (and how it differs from `frontend/`)

The Chainlit `frontend/` is a fixed single-column React app. It can't render a true 3-pane
layout, real side panels, or an agent wing without forking Chainlit's React — a framework
ceiling. We own the design and the engine (`run_live` returns a structured dict **and** streams
per-agent events via `on_progress`), so `frontend2/` is a thin custom shell: full design
fidelity, no framework ceiling, **no new dependencies**.

**`frontend/` (Chainlit) remains the supported fallback.** `frontend2/` is additive — it reuses
`frontend/bridge.py` (the in-process `run_live` seam) so real moat / live EMET / Boltz / the
auto-loaded 14-PMID EMET envelope all come through exactly as in the Chainlit path. Nothing in
`frontend/` is touched.

## Run

```bash
python frontend2/server.py --port 8100      # then open http://127.0.0.1:8100
```

The engine is stdlib-only and so is this server (`http.server.ThreadingHTTPServer`). For a real
run, the engine reads its secrets/data from `RohanOnly/` at runtime (the Boltz key from
`RohanOnly/boltz_api.env`, the moat from `RohanOnly/moat/moat.sqlite`) — none are committed.

### Profiles (the selector, top-right)

| Profile | `bridge.run` kwargs | What's real |
|---|---|---|
| **Live · simulated models** | `mock=False, simulate=True` | REAL moat · REAL EMET PMIDs · REAL seams/Q-Models; roundtable + claude-fact reasoning is 🧪 **simulated** (clearly labeled, fast) |
| **Demo · mock backends** | `mock=True` | Offline mock ctx — deterministic, $0, no external calls (the verification + test path) |
| **Live · real models** | `mock=False` | Real backends; claude subagents shell out to the `claude` CLI (absent ⇒ they abstain honestly) |
| **Replay · captured TSC2 ($0)** | `bridge.replay(...)` | A frozen REAL capture (real moat + real EMET PMIDs + the spread), $0, no model/network — labeled **CAPTURED** |

## Layout — Hayes's 3-pane + toggleable side panels

- **LEFT — the Agent Wing.** Categorized, expandable **per-subagent cards** (Internal Science &
  Moat · Biomedical Evidence (EMET) · Quantitative Models · Genetics & Constraint · Quiver Tools ·
  the veto-class Regulatory Memory / Patent & IP · Semantic Web · Roundtable Partners). Each card
  shows its **live status** (queued → spinning → ✓ ok / ⚠ abstain, streamed from the run), what it
  did, and **its cited sources** (the dossier facts attributed to it). Toggle via **Agents**.
- **CENTER — the conversation.** Your question → the **synthesis** (recommendation · confidence ·
  proposed experiment) → an **attributed-findings** row (one finding per contributing agent;
  **click a finding → the responsible agent's card opens and highlights** in the wing, and the
  finding turns violet — Hayes's finding↔agent linkage) → **VETO / DIVERGENCE** callouts (surfaced,
  never reconciled) → the **roundtable SPREAD** (one card per persona verdict — *the spread is the
  product*, no forced consensus).
- **RIGHT — Sources & Trace.** Two sections: **Evidence** — every dossier fact as a source row
  grouped by **data plane** (🔒 internal moat · 🌐 external), with tier + provenance chips, each row
  click-through to its originating agent card; and **Live Trace** — the step-tree `plan → each
  Bucket-1 agent (status · provenance · timing) → flags → each persona → synthesis`, **streamed
  live** from the SSE `progress` events (a row spins while running, then flips to ✓ / ⚠). Toggle via
  **Sources**.

### Honesty markers (mandatory, never fabricated)

Every marker is **derived from the engine's verbatim provenance** — never relabeled:

- **● REAL** (teal) — `moat-real`, `emet-live`, `aso-tox`, `boltz`, `gnomad`, `gtex`, … seams.
- **🧪 simulated** (amber) — provenance `simulated` (the simulate profile's reasoning stand-in).
- **◆ CAPTURED** (violet) — a replayed frozen run.
- **tier + provenance + plane** chips on every fact; an **abstention shows as ⚠**, never a false ✓.

## Full backend access for Demo Claudes

This is the load-bearing requirement: **a Demo Claude consumes structured data, never a screenshot
of the UI.** It runs this server and reads three machine-readable surfaces:

1. **`POST /api/run` (SSE).** The live per-agent `progress` events **and**, in the `result` frame,
   the **COMPLETE `run_live` dict** — every dossier fact with **all** fields
   (`value`/`field`/`tier`/`provenance`/`source`/`plane`/`flag`), the flags
   (`VETO`/`DIVERGENCE`/`KNOWN_UNKNOWNS`), the **full roundtable spread** (every persona's
   `stance`/`conviction`/`rationale`/`fact_claims`), the `synthesize` block, the `plan`,
   `engagement_id`, and `_via`. **No truncation, no summarisation.**
2. **`GET /api/trace/<engagement_id>`.** The **raw append-only trace JSONL** for that run
   (`RohanOnly/engagements/<id>/trace.jsonl`) — every harness event: `inputs_hash`, `status`,
   `provenance`, `guardrails_run`, `repairs`, `output`, `elapsed_s`. `Content-Type:
   application/x-ndjson`; honest **404** if the engagement has no trace on disk.
3. **`GET /api/runs/<engagement_id>`.** The **last full result dict** for that engagement, from a
   bounded server-side cache (the exact dict the `result` frame carried). **404** if uncached.

A Demo Claude's loop:

```bash
python frontend2/server.py --port 8100 &
# 1. run the firm and capture the complete structured result (no screenshot):
curl -sN -X POST localhost:8100/api/run \
     -H 'content-type: application/json' \
     -d '{"query":"Is TSC2 a viable target in tuberous sclerosis?","profile":"simulate"}'
#    → SSE: event: progress … ; event: result {<the COMPLETE run_live dict>} ; event: done
# 2. pull the raw engagement trace for the audit surface:
curl -s localhost:8100/api/trace/<engagement_id>     # raw JSONL, one harness event per line
# 3. (optional) re-fetch the complete result dict by id:
curl -s localhost:8100/api/runs/<engagement_id>      # the full cached result dict
```

Path-traversal-safe: engagement ids are validated (`[A-Za-z0-9_-]+`) and the resolved trace path
must stay under the engagements dir. The dir honours `SAPPHIRE_ENGAGEMENTS_DIR` (the same override
the harness trace writer uses), else the repo's `RohanOnly/engagements/`.

## The SSE contract (`POST /api/run`)

Request body (JSON): `{ "query": str, "profile": "demo"|"simulate"|"live"|"replay", "structure"?: any }`.

The response is `text/event-stream`. The firm runs in the request-handler thread; `bridge.run`'s
`on_progress` callback (fired on that thread) pushes each milestone onto a thread-safe
`queue.Queue` that the writer drains to the socket, flushing after each frame so the browser
renders the trace **live**. The connection closes after `done` (no Content-Length; a keep-alive
socket would strand a blocking reader).

| `event:` | `data:` (JSON) | when |
|---|---|---|
| `open` | `{profile, query, via}` | first, before the run starts |
| `progress` | a `run_live` progress event — `{stage, phase, …}` | one per milestone (verbatim from the engine) |
| `result` | the **full `run_live` dict** (the documented contract + `_via`/`_mock`/`_elapsed_s`/`_emet_session`) | once, when the run returns |
| `error` | `{error, trace?}` | only on a hard failure the bridge couldn't absorb (last-resort net) |
| `done` | `{}` | always last; closes the stream |

### `progress` event shape (verbatim from `live_engine`)

- `stage` ∈ `plan` · `bucket1` · `flags` · `roundtable` · `synthesis`; `phase` ∈ `start` · `done`.
- `plan` (done): `disease`, `modality`, `agents[]`, `panel[]`.
- `bucket1` (start): `agent_id`. (done): `agent_id`, `status` (`ok`/`abstained`/`escalated`),
  `provenance`, `n_facts`, `elapsed_s`, `error?`.
- `flags` (done): `n_veto`, `n_divergence`, `n_known_unknowns`, `n_facts`.
- `roundtable` (start): `agent_id`, `round`. (done): `agent_id`, `status`, `stance`, `conviction`,
  `elapsed_s`.
- `synthesis` (done): `recommendation`, `confidence`.

### `result` event shape

The complete `run_live` output dict — see
`sapphire-orchestrator/contracts/run_live_schema.md` for the authoritative contract
(`query`, `plan`, `priors`, `discover` {`dossier[]`, `flags`, `status`, `agents[]`}, `consult`
{`round1[]`, `round2[]?`}, `synthesize`, `engagement_id`, `reflection`, `_via`). Each fact carries
`value` · `source` · `tier` · `provenance` · `plane`.

### Honest-degrade

`bridge.run` is contracted **not to raise** — a missing backend yields an honest *abstain*
envelope, not a crash. The `error` frame is the last-resort net for a failure even the bridge
couldn't absorb; the stream still returns 200 and always ends with `done`, so the UI shows an
abstain — never a 500 in the user's face.

## Other routes

- `GET /` → `static/index.html`.
- `GET /static/<path>` → a file under `static/` (path-traversal-safe).
- `GET /api/replays` → `{"replays": [...]}` — the available frozen replay scenarios.

## Files

| Path | What |
|---|---|
| `server.py` | The stdlib-only `ThreadingHTTPServer` + SSE streamer + the full-access endpoints (`/api/trace/<id>`, `/api/runs/<id>`). Reuses `frontend/bridge.py`. |
| `static/index.html` | The 3-pane shell (nav · left agent wing · center chat · right Sources & Trace). |
| `static/app.css` | Hayes's tokens (violet `#1a1722` canvas, `--purple #a07cff`, Inter) + the wing / Sources & Trace / chip / spread / finding styling. |
| `static/app.js` | Vanilla JS: POST `/api/run`, read the SSE stream, build the agent wing + trace live, attribute facts to agents, render the center (synthesis · attributed findings · spread). |
| `tests/test_server.py` | Offline (demo profile) tests: progress→result streaming, contract conformance, the **full-access surface** (complete result · `/api/trace` raw JSONL · `/api/runs` cache · 404s · traversal), honest-degrade, SSE encoding. |

## Tests

```bash
python -m unittest discover -s frontend2/tests -t frontend2   # offline, $0
# or the whole suite (includes a frontend2 block):
bash dev/run-tests.sh
```
