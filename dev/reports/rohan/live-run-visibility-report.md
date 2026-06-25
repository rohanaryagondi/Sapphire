# live-run-visibility — stream the firm convening, step-by-step — report

**Branch:** `rohan/live-run-visibility` · **Built-By:** rohan · **Tier:** Feature

## Goal
Kill the opaque "Convening the firm…" spinner. The user watches the firm convene **in real time**:
plan → each Bucket-1 fact agent (internal moat, EMET, Q-Models, seams, corpora, semantic) appearing
with its result + timing → flags → each persona verdict → synthesis.

## W1 — engine: live progress (additive, stdlib)
- `live_engine.run_live(..., on_progress=None)` fires `on_progress(event)` at each milestone via a
  best-effort `_emit()` helper. Events: **plan done**; **each Bucket-1 agent start + done**
  (`agent_id, status, provenance, n_facts, elapsed_s`, `error` on abstain); **flags done** (VETO /
  DIVERGENCE / known-unknown counts); **each roundtable persona start + done** (`stance, conviction`
  or honest abstention, round 1); **synthesis start + done** (`recommendation, confidence`).
- `_emit` ALSO records each milestone to the harness trace as `{"type":"progress",…}` → the run is
  **observable by tailing `trace.jsonl` mid-run** (incremental flush; verified a progress record
  precedes `engagement_close`).
- **Additive + safe:** `on_progress=None` ⇒ output byte-identical (verified: dossier/round1/synthesis
  equal with and without the callback); a **raising callback never breaks the run** (swallowed). No
  contract change, no change to agent outputs/guards/provenance. Engine stays stdlib-only.

## W2 — front end: the live step tree (sync→async bridge)
- `frontend/progress.py` (pure, chainlit-free): a progress event → honest step label + output. The
  **honesty rule**: a `done` line reflects the REAL result — `✓ 8 fact(s) · moat-real · 1.2s` for an
  ok agent, but `⚠ escalated — login-required · emet-live · 0.4s` for an abstain (**never a ✓**); a
  persona abstention shows `⚠ abstained`, not a fabricated verdict.
- `frontend/bridge.run(..., on_progress=…)` forwards the callback to `run_live`.
- `frontend/main.py` — the **sync→async bridge** (the crux): `bridge.run` (synchronous `run_live`)
  runs in a worker thread (`asyncio.to_thread`); its `on_progress` marshals each event back to the
  event loop via `loop.call_soon_threadsafe` onto an `asyncio.Queue`; the handler **drains the queue
  and creates/updates `cl.Step`s LIVE** (a `_StepTree`: top-level steps for plan/flags/synthesis,
  parent groups for Bucket-1 / roundtable with a child step per agent/persona). Steps are created and
  updated **as each event arrives — during the run, not after** — then the rich final
  dossier/planes/roundtable/synthesis view renders as before. Applies to **Live / Live (cheap) /
  Demo**; **Replay** renders instantly (frozen dict, no progress).

## Gates
- **Gate 1:** `bash dev/run-tests.sh` → **540 GREEN** (+13: 6 engine-progress + 6 progress-formatter
  + 1 bridge-forwarding). Offline, $0.
- **Gate 3/4:** engine stdlib-only; `progress.py` chainlit-free; no contract change; no agent
  output/guard/provenance change; `vendor/` untouched.
- **Gate 5 (RAN it in the browser):** a Demo TSC2 run renders the full live step tree — **Plan →
  Bucket-1** (child steps *Internal moat — Quiver CNS_DFP*, *EMET — live BenchSci*, *Q-Models*, *FDA
  institutional memory ⛔*, *Global regulatory divergence*, *Post-market safety*) **→ Flags →
  Bucket-2 roundtable → Synthesis** — then the rich final view. The streaming path (queue + worker
  thread) is identical for the live profiles, where each haiku agent's step flips done in real time
  over the run. *(Head Claude verifies the progressive appearance in a live `cheap·haiku` run per the
  brief DoD.)*

## Files
- `sapphire-orchestrator/live_engine.py` (+`on_progress`, `_emit`, milestone emits, per-agent timing)
- `sapphire-orchestrator/tests/test_live_engine.py` (+6 `TestLiveProgress`)
- `frontend/progress.py` (new, pure) · `frontend/tests/test_progress.py` (new, +6)
- `frontend/bridge.py` (+`on_progress` forward) · `frontend/tests/test_bridge.py` (+1)
- `frontend/main.py` (+`_StepTree`, `_run_with_live_steps`, `_render_final`)
