# WO-2 — Front door: one live path (make the live firm whole, then converge)

**For:** Rohan Claude (worker) · **Branch:** `rohan/front-door` cut from `main` · **Plan:** [`docs/plan/04_FRONT_DOOR.md`](../../docs/plan/04_FRONT_DOOR.md)
**Lifecycle:** use `/sapphire-build` (plan→implement→review→verify→ship). **Blocked? →** append to `dev/HELP.md`.
**Priority: P0 — this is the keystone; WO-3 and WO-4 depend on Phase A.**

## Goal
Collapse the three live paths to **one harnessed path** (`live_engine.run_live`) behind **our console**, after
first making that engine produce a complete firm run. Decisions: D1 (one path = `run_live`), D8 (our consoles,
not Loka).

## Phase A — make `run_live` whole (do this first; it's the prerequisite)
1. **Round 2 + spread.** `live_engine.py` returns only `{round1}`. Port the rebuttal loop + spread computation
   from the canned path (`orchestrator.py`) so the live path returns `{round1, round2, spread, flags…}`
   matching the canned shape. (~`live_engine.py` ll. 640–703.)
2. **6 missing semantic agents.** Add `dea-scheduling, manufacturing-cmc, patient-advocacy, kol-social,
   policy-legislative, reputational` to `_BUCKET1_AGENTS` (~l. 39). They're already in `harness/agents.json`.
3. **VETO as a gate.** Between Bucket-1 completion and Bucket-2 dispatch: if `veto_flags` non-empty, open the
   roundtable with an explicit adjudication step (not just surfaced context). AGENTS.md describes this; the
   code doesn't enforce it.
4. **Capability-class on the plan.** The engagement plan tags the ask `class ∈ {diligence, design, experiment}`
   (sets up WO-3/WO-4). Add a `class` field to the plan + registry; default `diligence`.

**Phase A DoD:** `run_live` dict shape == canned path; all 13 semantic agents dispatch; a VETO fact provably
forces an adjudication step (test it); suite green.

## Phase B — converge the front door
5. **`POST /api/chat` → `run_live`** (drop the old `claude -p` subprocess). (~`serve.py` ll. 376–383.)
6. **Console → the live SSE.** Re-point the active console (`site/index.html` / `frontend2`) to `run_live`;
   keep `?mode=replay` using the canned path for $0 demos.
7. **Honest health.** `serve.py` health: compute `moat` from `MoatClient.available()`, not hardcoded `"mock"`. (~l. 330.)
8. **Demote :8101.** Label `orchestrator_ui/` experimental in its README (good demo asset, not the front door).
9. **Update `CLAUDE.md`** — one live path; remove stale "run_live not wired" + "278 tests" lines.

**Phase B DoD:** a query typed in the console runs the harnessed firm end-to-end with a live streamed trace +
the spread; canned replay still works behind `?mode=replay`; health honest; docs match.

## Gates
Full suite green · independent review (different agent) · provenance + no secrets · stdlib-engine boundary ·
**Gate 5: actually drive a query through the console and confirm the live trace + spread render.** Do not skip Gate 5.

## Notes
- Don't break the canned replay (it's the $0 demo + test fixtures).
- The openable snapshots on `rohan/orchestrator-8101` are demo assets — keep.
