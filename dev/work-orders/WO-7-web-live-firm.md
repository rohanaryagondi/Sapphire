# WO-7 — web/ : the live firm experience

**Owner:** Rohan Claude · **Approver:** Head Claude · **Target:** `web/` (the Linear/Vercel flagship, `localhost:3000`).
**Authored:** 2026-06-30, after a long design iteration with the user. The approved visual spec is the set of
mockups committed under `design/` (read them — they ARE the spec and use `web/`'s real tokens verbatim).

## What & why
Turn `web/` into the real-time face of the firm: **chat in the center**, an **expandable right-side work panel**
(Trace + Dossier), with the Trace **streaming the ACTUAL `run_live` execution live** — Claude-Desktop-style
(click a row to expand its detail, `⤢` to widen the panel, collapse to hide). The chat holds the readable answer;
the right panel holds the receipts (the live trace + the cited dossier).

## Decisions (locked by Rohan/the user, 2026-06-30 — do not re-litigate)
- **Live by default.** Every NEW query runs the REAL firm (`live_engine.run_live`, `via=engine-live`) and streams
  its trace. Past conversations (history) render their **saved** trace instantly — only new queries run live, so
  browsing stays fast. There is no canned "Demo answer" shortcut for a fresh query.
- **Haiku default.** Live runs default to `CLAUDE_MODEL=haiku` (~3–5 min, cheap); the existing per-run model
  picker overrides to Claude 4 when depth matters.
- **Incremental rollout.** Four phases (A→D), each one gated PR.

## Visual spec (approved mockups — committed to `design/` on main)
- **`design/app-layout-mockup.html`** — THE layout to build: chat-center + expandable work panel (Trace/Dossier
  tabs), per-row expand, panel-widen, deep-linked citations (chat → panel row). **Phase A builds this.**
- `design/plan-canvas-mockup.html` — the plan card (Claude-plan-mode prose: framing + numbered steps with
  `expect:`/`skipping:` boxes, internal/external plane, locked veto). **Phase B.**
- `design/sapphire-fullsite-mockup.html` + `design/fullsite-design-notes.md` — the full surface set + the
  provider-pattern rationale + the prioritized build order. Reference for B/C/D.
These match `web/`'s `globals.css` tokens and extend the existing components — they are an evolution of `web/`,
not a rewrite.

## Hard constraints (acceptance criteria for EVERY phase)
- **RAM < 2 GB at all times.** Serve production (`next build && next start`, **never** `next dev` — that's what
  spiked RAM before). Event-driven **SSE only — no polling intervals**. Render-on-demand: rows expand on click;
  **cap/virtualize long lists** (21+ facts, 13 agents, the trace). Close the SSE stream on completion. No large
  in-memory blobs. **Phase A must MEASURE and report the peak RAM during a real live run.**
- **Honesty intact.** Provenance/tier/plane/flag badges from `web/src/components/ui/chips.tsx`; the live trace
  shows **REAL streamed events only** — never a scripted/canned row in live mode. Unknowns flagged, not faked.
- **Data boundary.** Internal moat scores never leave; only public identifiers in any external-bound payload.
- Engine is the source of truth; all UI work is additive. The canned/replay path stays for history.

---

## Phase A (ASSIGN NOW) — live trace + work-panel layout · branch `rohan/web-live-trace`
The keystone. Chat-center + expandable right work panel, with the Trace streaming the real run.

**Backend** (the Python API `web/` proxies to — `serve.py` / the `:8201` server; reuse the `frontend2` SSE drive
from WO-2 B-6 as the pattern):
- Add an **SSE endpoint** that invokes `live_engine.run_live(query, on_progress=…, ctx=…)` and streams each
  `on_progress` event as it fires: `plan` (selected_ids, class) · per-agent `bucket1` start/done
  (`agent_id`, `status`, `provenance`, `n_facts`, `elapsed_s`, `plane`) · `flags` (VETO/DIVERGENCE/known-unknowns)
  · per-persona `roundtable` round1/round2 (persona, stance, conviction) · `synthesis`. The `on_progress` contract
  already exists in `run_live` (from the `live-run-visibility` work) — wire it to SSE, don't reinvent it.
- Default `CLAUDE_MODEL=haiku`; honor the model picker. **Persist** the run (trace.jsonl + result) keyed to the
  conversation so history replays the saved trace instantly (no re-run, $0).
- **Bucket-1 already parallelizes** (the ThreadPoolExecutor merge, PR #139) — events may complete out of order;
  stream them as they finish and let the client place them by `agent_id` in the canonical section order.

**Frontend** (`web/` — evolve `inspector/`, `topbar`, `chat-thread`):
- **Layout:** chat center; **right work panel** with **Trace** + **Dossier** tabs, a **widen** control (`⤢`,
  ~400↔600px) + collapse; left history rail collapsible (topbar toggles). The panel is today's inspector grown up.
- **Trace tab:** consume the SSE stream via **`EventSource`** → append/update rows live. Each Bucket-1 row: status
  dot (waiting → running(pulse) → done / ⛔gate), `agent_id`, short desc, plane+provenance badges, fact count;
  **click → expand** its contributed facts (mono provenance lines). Section headers: Plan ✓ · Bucket 1 · Flags ·
  Bucket 2 · Synthesis ✓. Partner rows expand to verdict + conviction. Auto-open the panel + auto-scroll the
  active row during a live run; settle to the resting state on completion. Match `design/app-layout-mockup.html`.
- **Chat center:** a live "Convening the firm…" status while streaming (the trace IS the wait-filler); the
  synthesis recommendation renders in the thread when the run completes.
- **Perf:** `EventSource` (no polling); virtualize/cap the trace + dossier lists; lazy-render the inactive tab.

**DoD (Phase A):** a NEW query runs the real firm on haiku and the right-panel Trace **fills live, event by
event** (demonstrate with a real run — show the trace populating, not a canned fill); rows expand; panel widens;
**history replay shows the saved trace instantly** ($0, no re-run); the model picker switches the live model;
**zero fabricated rows** (live = real events only); full suite green; **measured peak RAM < 2 GB during a real
live run (report the number)**; data-boundary + provenance intact. Head Claude gates with a REAL live run + a RAM
measurement as the Gate-5 functional verify.

---

## Phase B (queued) — plan card · branch `rohan/web-plan-card`
Refactor `web/src/components/plan-review.tsx` from today's flat checklist to the **narrative plan card** in
`design/plan-canvas-mockup.html` (prose framing + numbered steps + `expect:`/`skipping:` + plane badges + locked
veto). With **Plan-first** ON, the firm proposes the plan (no agents run) → user approves → the live run streams
(Phase A). Engine: the `run_live` plan-mode path returns a **narrated** plan (per-step prose + expected findings),
**LLM-generated per query** (a small planner call) with a **deterministic templated fallback**. Reuse the existing
`pendingPlan` / `approvePlan` store. **DoD:** Plan-first shows the prose plan; approve → live run; narration is real
(LLM) with a working fallback; suite green; RAM constraint holds.

## Phase C (queued) — spread + synthesis polish · branch `rohan/web-spread-synth`
`web/src/components/run/spread.tsx`: the round-1 → round-2 toggle, conviction bars, the **moderator rebuttal
note**, stance-bar verdict cards + the final spread tally — **no consensus meter; preserve the disagreement**
("the spread is the product"). Verify `run/synthesis.tsx` (gradient + glow + confidence tone + proposed experiment
+ known-unknowns "flagged, not faked"). Match the mockups. **DoD:** spread shows round evolution + moderator note;
synthesis renders with all parts; suite green.

## Phase D (queued) — dossier panel + ⌘K · branch `rohan/web-dossier-cmdk`
Dossier renders in the right-panel **Dossier** tab (two-plane internal/external, expandable fact cards, full
honesty badges, click → inspector). `web/src/components/command-palette.tsx`: wire ⌘K for surface navigation +
actions (Raycast-style). **DoD:** dossier in the panel, expandable, badge-complete; ⌘K navigates + dispatches;
suite green.

---

## Lifecycle
`/sapphire-build` per phase; blocked → ask via `dev/HELP.md` (the answer merges to main and wakes you). One branch
per phase (`rohan/web-<phase>`), one gated PR each; **Head Claude gates + merges** (Gate 1 suite green · Gate 2
independent review · Gate 5 functional verify — for Phase A the Gate-5 is a REAL live run showing the trace stream
+ a RAM measurement). Build from the **latest** `origin/main` (`git fetch origin` first — the local main tree runs
stale; the pre-push Gate 3.6 will warn if your base lags).
