# 04 — Front door: converge to one live path (build plan · step 2)

> Status: 🔵 PLANNED. Decisions baked in: **our consoles stay the surface** (D8); the one path is the
> **harnessed `run_live`** (D1, leaning→commit here). **Prerequisite folded in:** step 2 can't ship onto a
> half-built engine, so **Phase A makes the live firm whole first** (the old "step 1"), then Phase B converges.

## Goal
One live path behind one console: a user query in the UI → `live_engine.run_live(query)` (guard-enforced,
schema-validated, provenance-stamped, traced) → streamed trace + the full report. Retire / demote the other
two paths so *the firm you demo is the firm that runs*.

## Current state (three paths, diverged) 🟡
- `orchestrator.run(sid)` — canned scenarios, $0, deterministic (:8099 / `frontend2/`). 🟢 keep as **replay/demo mode**.
- `live_engine.run_live(query)` — the harnessed live firm. 🟡 **incomplete** (see Phase A).
- `claude -p` console — `orchestrator_ui/` (:8101). 🟡 **demote** to an experimental surface.
- `serve.py`: `GET /api/run` → `_run_engine_live` (good); **`POST /api/chat` still spawns the old subprocess**;
  health label hardcodes `"moat":"mock"`. `site/index.html` still renders canned data.

## Phase A — make `run_live` whole (prerequisite)
The live path is materially weaker than the canned demo. Close that first (all small, contract-supported):
1. **Round 2 + spread** — `live_engine.py` returns only `{round1}`; port the rebuttal loop + spread
   computation from the canned path (`orchestrator.py`) so the live firm produces the spread. (~`live_engine.py` ll. 640–703)
2. **The 6 missing semantic agents** — add `dea-scheduling`, `manufacturing-cmc`, `patient-advocacy`,
   `kol-social`, `policy-legislative`, `reputational` to `_BUCKET1_AGENTS` (~l. 39). They're already in
   `harness/agents.json` with specs.
3. **VETO as a gate** — between Bucket-1 completion and Bucket-2 dispatch, if `veto_flags` non-empty, open
   the roundtable with an explicit adjudication step (not just surfaced context).
4. **Capability-class field** — the engagement plan tags the ask's class (diligence/design/experiment) so
   control activates the right tools (sets up steps 3/4). Add `class` to the plan + the registry.

**Phase A DoD:** `run_live` output dict matches the canned path's shape (`{round1, round2, spread, flags…}`);
all 13 semantic agents dispatch; a VETO fact provably forces an adjudication step; suite green.

## Phase B — converge the front door
5. **Point `POST /api/chat` at `run_live`** (drop the old subprocess path). (~`serve.py` ll. 376–383)
6. **Re-point the console** (`site/index.html` / the active console) to the `run_live` SSE so it renders the
   real run, not canned data. Keep a `?mode=replay` that uses the canned path for $0 demos.
7. **Fix the health endpoint** — compute `moat` from `MoatClient.available()` instead of hardcoding `"mock"`. (~`serve.py` l. 330)
8. **Demote `orchestrator_ui/` (:8101)** — label it experimental in its README; it's not the front door.
9. **Update `CLAUDE.md`** — one live path; remove the stale "run_live not wired" + "278 tests" lines.

**Phase B DoD:** a query typed in the console runs the harnessed firm end-to-end with a live streamed trace;
the canned replay still works behind `?mode=replay`; `serve.py` health is honest; docs match reality.

## Gates (dev lifecycle)
Full suite green (1) · independent review (2) · provenance + no secrets (3) · stdlib-engine boundary (4) ·
**Gate 5 functional verification** — actually drive a query through the console and confirm the live trace +
the spread render (this is the whole point; don't skip it).

## Risks / notes
- The `claude -p` console (:8101) and the openable demo snapshots (on `rohan/orchestrator-8101`) are good
  demo assets — demote, don't delete.
- Don't break the canned replay path; the captured scenarios are the $0 demo + the test fixtures.
- Loka contributes nothing to this step (D8) beyond optional UI patterns — see `06_LOKA_ASSETS.md`.
