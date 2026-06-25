# Task brief — live-run visibility (stream the firm convening, step-by-step)

*Owner: **rohan** (Rohan Claude builds; Head Claude reviews/gates/merges + verifies in the live UI). Tier: **Feature**.
Created 2026-06-25. Priority: HIGH — blocks a watchable live demo.*

## The problem (observed live)
A **Live (cheap · haiku)** run in `frontend/` shows only a single opaque **"Convening the firm…"** spinner for the
entire run (minutes), then dumps the whole result at once. During the run the user sees nothing — no indication that
the internal moat search ran, that EMET is querying, which agent is active, or the roundtable progressing. Confirmed:
the run IS doing real work (11 concurrent `claude -p` haiku subprocesses; trace shows internal-science-lead →
emet-runner → … → personas in the right order) — it's purely a **visibility gap**. Also, `run_live` only writes its
trace at `engagement_close`, so there's nothing to even tail mid-run.

Goal: **very high visibility** — the user watches the firm convene **step by step, in real time**: plan → each Bucket-1
fact agent (internal moat, EMET, Q-Models, seams, corpora, semantic agents) appearing as it starts/finishes with its
result + timing → flags → each Bucket-2 persona verdict streaming in → synthesis. No blind spinner.

## Work-item 1 — engine: emit live progress (additive)
- `live_engine.run_live(..., on_progress=None)`: invoke `on_progress(event)` at each milestone. Suggested event shape:
  `{"stage": "plan"|"bucket1"|"flags"|"roundtable"|"synthesis", "agent_id": str|None, "phase": "start"|"done",
    "status": str, "provenance": str, "n_facts": int, "round": int|None, "stance": str|None, "elapsed_s": float}`.
  Fire: plan ready; **each Bucket-1 agent start + done** (id, status, provenance, n_facts, elapsed); flags computed
  (VETO/DIVERGENCE counts); **each roundtable persona start + done** (round1 then round2, stance·conviction or
  abstained); synthesis start + done. Additive — `on_progress=None` ⇒ current behavior byte-identical.
- Also **flush the harness trace incrementally** (append each event as it happens, not only at close) so the run is
  observable by tailing `trace.jsonl` too.
- Keep engine **stdlib-only**; no contract change to the returned dict (progress is a side channel). Don't change agent
  outputs/guards/provenance.

## Work-item 2 — front end: render the live step tree
- Replace the single `cl.Step("Convening the firm…")` with a **streamed sequence** driven by `on_progress`:
  - **Plan** step first (deliverable/disease/modality/agents/panel) — appears immediately after triage.
  - **Bucket-1** parent step with a **child step per fact agent** that updates pending→running→done, each showing the
    real result: e.g. *"Internal moat — searching CNS_DFP… ✓ 8 EP-signatures (moat-real)"*, *"EMET (live) —
    querying BenchSci… ✓ 8 PMIDs (emet-live)"* or *"⚠ abstained (login_required)"*, *"Q-Models… ✓"*, each seam,
    each corpus, each semantic agent — with **per-agent elapsed time**.
  - **Flags** step (VETO ⛔ / DIVERGENCE ⚠) as computed.
  - **Roundtable** parent step with a **child step per persona**, round1 then round2, streaming the stance·conviction
    (or honest abstention) as each lands.
  - **Synthesis** step → the recommendation.
  Then render the final dossier/planes/roundtable/synthesis as today (keep the rich final view).
- **Sync→async bridge:** `run_live` is synchronous; Chainlit is async. Run `run_live` in a worker thread
  (`cl.make_async` / `asyncio.to_thread`); have `on_progress` push events onto a thread-safe queue that the async
  handler drains to create/update `cl.Step`s live (use `cl.run_sync` or a queue + `await` loop). Get this right —
  it's the crux. Steps must appear DURING the run, not after.
- Applies to **Live** and **Live (cheap · haiku)** profiles. **Demo (mock)** and **Replay** can reuse the same step
  rendering (they'll just complete instantly) — but the live profiles are the point.

## Definition of done (Head Claude verifies in the live UI)
- A **Live (cheap · haiku)** TSC2 run shows a **live, growing step tree** — plan, then each Bucket-1 agent appearing
  with status + result + timing (internal moat + EMET visibly first), then each persona verdict streaming in, then
  synthesis — NOT a single blind spinner. Verified by watching the actual browser run.
- Order is visible and correct (Bucket-1 facts → flags → roundtable → synthesis); abstentions shown honestly.
- `trace.jsonl` is observable mid-run (incremental flush).
- Suite green; engine stdlib; vendor untouched; agent outputs/guards/provenance unchanged; Demo/Replay unbroken.
- Gates 1–5 (Feature → also 6). Hand to Head Claude; don't self-merge.

## Constraints
- Additive `on_progress` (default None). No fabrication — a progress event reflects the real agent result (don't show
  "✓" for an agent that abstained). Honesty: an abstain shows as abstain, with the reason.
- Don't regress the rich final render or the replay path. Keep all-haiku as the cheap-live default.
