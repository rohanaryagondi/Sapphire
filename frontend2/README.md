# frontend2 — Sapphire's custom 3-pane console (stdlib-only)

A thin, **Python-standard-library-only** front end that fully realizes the team's design —
**Gavin's chat-first 3-pane layout** (`docs/design/console-ui/sapphire_chat.html`) and
**Hayes's agent-wing + attributed-findings** — wired to the **real firm** via
`live_engine.run_live`, with the **live trace streamed** over Server-Sent Events.

## Why this exists (and how it differs from `frontend/`)

The Chainlit `frontend/` is a fixed single-column React app. It can't render a true 3-pane
layout, real side panels, or an agent wing without forking Chainlit's React — a framework
ceiling. We own the design and the engine (`run_live` returns a structured dict **and** streams
per-agent events via `on_progress`), so `frontend2/` is a thin custom shell: full design
fidelity, no framework ceiling, **no new dependencies**.

**`frontend/` (Chainlit) remains the supported fallback.** `frontend2/` is additive — it reuses
`frontend/bridge.py` (the in-process `run_live` seam) so real moat / live EMET / Boltz / the
auto-loaded EMET envelope all come through exactly as in the Chainlit path. Nothing in
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
| **Live (simulated models)** | `mock=False, simulate=True` | REAL moat · REAL EMET PMIDs · REAL seams/Q-Models; roundtable + claude-fact reasoning is 🧪 **simulated** (clearly labeled, fast) |
| **Demo (mock backends)** | `mock=True` | Offline mock ctx — deterministic, $0, no external calls (the verification + test path) |
| **Live (real models)** | `mock=False` | Real backends; claude subagents shell out to the `claude` CLI (absent ⇒ they abstain honestly) |
| **Replay (captured TSC2 · $0)** | `bridge.replay(...)` | A frozen REAL capture (real moat + real EMET PMIDs + the spread), $0, no model/network — labeled **CAPTURED** |

## Layout (3-pane + toggleable side panels)

- **LEFT — Agent Wing + attributed findings.** Agent output grouped by the two **data planes**
  (🔒 internal moat vs 🌐 external), each finding a click-to-expand card with **tier (T1/T2/T3) +
  provenance + plane** chips, plus the live **Roster** (every seated agent with its status +
  provenance). Toggle via the **Agents** button.
- **CENTER — the conversation.** Your question → the **synthesis** (recommendation · confidence ·
  proposed experiment) → the **roundtable SPREAD** (one card per persona verdict — *the spread is
  the product*, no forced consensus) → **DIVERGENCE / VETO** surfaced as callouts.
- **RIGHT — the live Trace step-tree.** `plan → each Bucket-1 agent (status · provenance ·
  timing) → flags → each persona → synthesis`, **streamed live** from the SSE `progress` events
  (a row spins while `running`, then flips to ✓ / ⚠). Toggle via the **Trace** button.

### Honesty markers (mandatory, never fabricated)

Every marker is **derived from the engine's verbatim provenance** — never relabeled:

- **● REAL** (green) — `moat-real`, `emet-live`, `aso-tox`, `boltz`, `gnomad`, `gtex`, … seams.
- **🧪 simulated** — provenance `simulated` (the simulate profile's reasoning stand-in).
- **◆ CAPTURED** — a replayed frozen run.
- **tier + provenance + plane** chips on every fact; an **abstention shows as ⚠**, never a false ✓.

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
| `server.py` | The stdlib-only `ThreadingHTTPServer` + SSE streamer. Reuses `frontend/bridge.py`. |
| `static/index.html` | The 3-pane shell (nav · left wing · center chat · right trace). |
| `static/app.css` | Gavin's tokens (sapphire-blue `#4d7cfe`, Inter) + the 3-pane / panel / chip / trace styling. |
| `static/app.js` | Vanilla JS: POST `/api/run`, read the SSE stream, render the trace live, populate the panes from the final dossier. |
| `tests/test_server.py` | Offline (demo profile) tests: progress→result streaming, contract conformance, honest-degrade, path-traversal, SSE encoding. |

## Tests

```bash
python -m unittest discover -s frontend2/tests -t frontend2   # offline, $0
# or the whole suite (includes a frontend2 block):
bash dev/run-tests.sh
```
