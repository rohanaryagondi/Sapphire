# WO-7 Phase A — PR report (the live firm in `web/`)

**Branch:** `rohan/web-live-trace` · **Built-By:** rohan · **Tier:** Feature
**Spec:** `dev/work-orders/WO-7-web-live-firm.md` (Phase A) + the approved mockup `design/app-layout-mockup.html`
**Workboard:** `web-live-firm-A` (🔨 HIGHEST). **For:** Head Claude to gate + merge (I do not self-merge).

## Goal
The live-firm experience in `web/`: a chat-center + expandable right-side work panel (Trace + Dossier tabs)
where the **Trace streams the real `run_live` execution live over SSE**, live-by-default, Haiku default,
within a < 2 GB RAM budget.

## Key framing (what this actually was)
`web/` was **already a substantial Next.js 15 App Router app** (chat, a live trace panel, in-chat dossier,
history replay, model picker), and the **backend SSE already existed** (`frontend2/server.py` `_stream_run`
bridges `run_live`'s `on_progress` → SSE; `web/` proxies `/api/*` → `:8201`). So Phase A was a **frontend
reshape to the mockup + defaults flip + RAM discipline**, touching **only `web/`** (zero backend Python).

## What shipped (commits f6cc41e → 57ee7ef → 73e0ee8, + merge of main)
**Reshape (f6cc41e):**
- **Layout** flex → the mockup's **animating CSS-grid** (rail 236 | chat | panel), with state classes for
  rail-collapse, panel-hide, and the **⤢ widen (400↔600px)** — all driven by new `railOpen`/`panelOpen`/
  `panelWide` store state.
- **Right panel** Inspector tabs **Monitor/Investigate → Trace/Dossier** (Trace carries a live pulse dot);
  `AgentRow` converted to an **inline click-to-expand `.trow`** (folds detail in place, no routing); `⤢`/`›`
  controls + hintbar.
- **Defaults flipped** to **profile:"live"** + **model:"haiku"** (`store.ts`).
- **Dossier tab** (`dossier-tab.tsx`) — two planes (🔒 internal / 🌐 external) of fact cards (mocks dashed),
  reusing the existing dossier rendering + `ui/chips.tsx` badges.
- **TS types** extended for `redispatch` + round-2 `rebuttal_*`; out-of-order bucket-1 events placed by `agent_id`.
- **RAM discipline:** `@tanstack/react-virtual` (gated on list length), `buildTrace` memoized, `pushTrace` caps
  retained turns; kept the event-driven **fetch+ReadableStream SSE consumer** (NOT `EventSource` — it's GET-only
  and can't carry the POST query body; documented in `api.ts`). No polling.

**Gate-2 fixes (57ee7ef):** (1) wired the **chat→row deep-links** (`monitor.tsx` `useEffect` on `focusRowId` →
open + `scrollIntoView`; `chat-thread.tsx` `trace ↗`/`dossier ↗` refs + spread verdict clicks set the tab +
focus row); (2) fixed the **round-2 rebuttal "spins forever"** bug (`trace-model.ts` now marks a row done on
`rebuttal_done`; `TracePhase` extended); (3) added **SSE abort** (`AbortController` per run in the store, aborts
on new-query and on unmount via `page.tsx` cleanup). Nits: merged `pushTrace`'s double `set()`; virtualizer now
uses the outer panel scroll container (no nested scrollbar).

**Crash fix (73e0ee8):** Gate-5 caught a **React error #310 (Rules of Hooks)** — the new deep-link hooks block
sat above the `if (!turn) return` early-return while the existing `useMemo` sat below it, so the hook count
changed between renders and the UI crashed on every query submit. Fixed by moving `useMemo` (+ `verdicts`/
`roundtable`/`rtDone`) above the early return (null-safe `buildTrace(turn?.trace ?? [])`); audited `AgentRow`/
`AgentList`/`TurnSwitcher` — no other violations.

**Merge:** merged latest `origin/main` (Phase 0 #140 + Gate-3.6 hook #141 + #143) — clean, no conflicts.

## Gate evidence
- **Gate 1 — full suite GREEN: 858 tests** (`bash dev/run-tests.sh`, with the local moat DB built).
- **Gate 2 — independent review: Approved-with-nits** (different agent). Confirmed honesty (zero canned rows in
  live mode, badges from `chips.tsx`, mocks dashed), no polling/external calls, engine untouched, RAM cap sound,
  always-mounted-panel is fine (only the active tab's component mounts). Its 3 Important findings (deep-links,
  rebuttal, SSE abort) + 2 nits were all fixed (57ee7ef).
- **Gate 5 — independent functional verification: PASS** (different agent, clean isolated env). Built prod, ran
  the stack on fresh ports, **Playwright-drove a real query submit** and verified every DoD item:
  - No crash (0 console errors); **Trace rows populate live** from streamed events (23/23 Bucket-1, 5/5
    roundtable partners settling to done — rebuttal fix confirmed in UI).
  - Inline expand (maxHeight 0→520px); **⤢ widen** (grid `400px`→`600px`); rail toggle (236→0→236); Dossier
    two-plane; **all 3 deep-link paths** (trace↗/dossier↗/spread verdict → tab switch + auto-expand + scroll);
    **history replay** instant ($0, static render); **abort** (two overlapping queries → no leak/crash).
  - **Peak RAM 0.108 GB** (backend + next-server), far under the 2 GB ceiling.
  - Honesty: simulate facts carry `provenance:"simulated"`, `tier:"T3"`, "🧪 simulated model" text; `_mock:false`.

## Honesty notes (read these)
- **Gate-5 attempt #1 was contaminated, not a code failure.** The first verify reported "trace never populates"
  — but its Next proxy was hitting a **stale server from a different session squatting port :8201** (the env has
  several orphaned servers on :8201/:8002/:3000). I aborted that run and **independently debunked the implied
  proxy-buffering bug**: in a clean env the Next rewrite proxy **streams SSE correctly** (response is
  `Transfer-Encoding: chunked`, no `Content-Length`, `X-Accel-Buffering: no` preserved; frames arrive
  incrementally). The clean re-verify used isolated ports + `SAPPHIRE_API` override to avoid the squatter.
- **The hooks crash was `tsc`-invisible.** `npm run build` passed despite the runtime crash, because TypeScript
  doesn't enforce Rules of Hooks and **the repo has no React component test harness** (no Jest/Vitest/RTL). Only
  the Gate-5 Playwright run caught it. **Recommended follow-up:** add a minimal Vitest+RTL (or Playwright) smoke
  that mounts `Monitor` with `turn=undefined` then a real turn — this class of bug is currently invisible to all
  automated gates.
- **`run_live` real-Haiku run is Head's authoritative Gate-5.** I verified the full UI + streaming + RAM on the
  cheap `profile=simulate` path (which streams the real `on_progress` event sequence — same code path, just
  simulated model outputs, $0). The workboard reserves the authoritative **real-Haiku live run + RAM
  measurement** for Head's gate; this PR proves everything up to that.
- Data boundary intact (internal moat scores render only in the internal plane, in-app; no new external call).

## Files changed (web/ only)
`web/package.json` (+`@tanstack/react-virtual`), `web/src/app/page.tsx`, `web/src/lib/{store,api,types}.ts`,
`web/src/components/topbar.tsx`, `web/src/components/chat-thread.tsx`,
`web/src/components/inspector/{index,monitor,trace-model}.tsx`, `web/src/components/inspector/dossier-tab.tsx`
(new). Engine + backend Python untouched.

## DoD checklist
- [x] New query streams the Trace live, event-by-event (verified on simulate; real-Haiku = Head's gate)
- [x] Rows expand inline · panel widens (⤢ 400↔600) · rail toggles · Dossier two-plane · deep-links
- [x] History replay renders the saved trace instantly ($0)
- [x] Model picker switches the live model; defaults are live + haiku
- [x] Honesty: real streamed events only, mocks badged; data boundary intact
- [x] Full suite green (858); **peak RAM 0.108 GB < 2 GB**
- [x] Gate 2 Approved (fixes applied) · Gate 5 PASS (clean env, Playwright)
- [ ] Authoritative real-Haiku live run + RAM — **Head Claude's Gate-5**
