# Sapphire — Overall Status

*One screen: where the build is. Updated 2026-06-24. Detail in the per-area docs; assignments in
[`WORKBOARD.md`](WORKBOARD.md).*

## ⏳ Current wave — live handoff (read FIRST if you're a fresh Head Claude)
*Updated 2026-06-28.* Next-build wave specced in [`dev/work-orders/`](../dev/work-orders/README.md)
(WO-2..WO-5) toward the blueprint in [`docs/plan/`](../docs/plan/README.md). **In flight right now:**

- **WO-2 Phase A — BUILT, AWAITING GATE → PR #113** (branch `rohan/front-door`). `run_live` made whole
  (round-2 + spread + the 6 missing semantic agents + VETO gate + capability-class); suite **714 green**.
  Gate it the normal way (isolated worktree, independent review + Gate-5) and merge if clean. It was built by
  a Head-Claude subagent before the builder/approver role split — treat it as a normal contributor PR.
- **Open decision for the human:** gate+merge PR #113 now (recommended — done + green) **vs** clean-slate and
  let a Rohan Claude *builder* redo WO-2. After Phase A: Phase B (front-door wiring) + WO-3/WO-4/WO-5.
- **Only ONE live feature branch: `rohan/front-door` (PR #113).** The ~25 other un-merged `rohan/*` branches
  (`book-*`, `assign-*`, `help-*`, demo branches) are HISTORICAL — ignore them.
- **Discovery caveat:** a pushed branch with NO PR is invisible to `gh pr list`. Always also run
  `git branch -r --no-merged origin/main` before concluding "nothing to do."
- **Leftover local worktrees** (`/tmp/demo-polish`, `/tmp/design-fold`, `/tmp/orch-8101`, `/tmp/wo2-frontdoor`)
  are this session's; `git worktree remove` them when not needed. The :8101 demo + openable snapshots live on
  `rohan/orchestrator-8101` (pushed) — keep as demo assets.
- **Does NOT transfer to a fresh session:** any armed Monitors / `/loop` heartbeat from the prior session —
  re-arm your own sweep if you want autonomous watching.
- **Recent harness merges:** #110 (harness hardening), #111 (docs/plan blueprint + work orders), #112
  (session prompts in `dev/CONTRIBUTORS.md`). Decisions D5/D7/D8 resolved (see `docs/plan/03`).

## Headline
The two-bucket firm runs end-to-end. Phases 1–6 are done. **381 tests green.** Fact sources are largely
**live/real** (EMET, personas, Q-Models, internal moat, ASO-tox). The **front door now serves the live
harnessed firm** (`run_live` via `serve.py /api/run`, K1) and **Bucket-1 agents read their corpora at run
time** (corpus-first → search-the-gap, K2). Remaining front-end piece: the LOKA adapter against the frozen
`run_live` contract.

## At a glance
| Area | State | Live vs mock | Detail |
|---|---|---|---|
| Engine (orchestrator + live_engine) | ✅ runs end-to-end | canned path live; **`run_live` now serves the front door** (K1) | [engine.md](engine.md) |
| Runtime harness (22 agents) | ✅ done | guard-enforced, provenance-stamped, traced | [runtime-harness.md](runtime-harness.md) |
| Fact tools | ✅ mostly real | EMET live · personas live · Q-Models real · moat **real** · ASO-tox **real** | [tools.md](tools.md) |
| Dev/build harness | ✅ done | 3-contributor, PR-gated, local enforcement | [dev-harness.md](dev-harness.md) |
| Front door (serve.py `/api/run`) | ✅ live firm (K1) | `run_live` default (`via=engine-live`); graceful canned fallback on static hosting | [engine.md](engine.md) |
| **Transparent front end (`frontend/`)** | ✅ **live (PR #41)** | LOKA-fork Chainlit UI → in-process `run_live`; renders the full firm process + two distinct data planes; Demo + Live profiles | [frontend-loka.md](frontend-loka.md) |

## Phases (done)
- **P1–P3:** control agents + Bucket-1 fact agents + Bucket-2 partners; orchestrator runs end-to-end (triage→
  plan→dossier→roundtable→synthesis); Console front face.
- **P4:** Q-Models toolset vendored; orchestrator can call any tool; two-speed routing (local-cpu sync /
  gpu-launch async); live AWS plumbing proven.
- **P5:** agent harness + live EMET + self-improvement loop + scenario suite.
- **P6:** ASO-tox tool integrated; **`run_live(..., sequences=...)`** feeds it real GBR tox facts (shipped
  2026-06-22, PR-gated).

## The end-to-end goal (LOKA arriving 2026-06-24)
LOKA is Quiver's **front end** (per `docs/LOKA.md`); Sapphire is the agentic reasoning layer; Quiver tools are
the predictive capability. End-to-end = **LOKA query → `live_engine.run_live` (the live harnessed firm) →
Bucket-1 facts (EMET + moat + seams + corpora, corpus-first→search-the-gap) → Bucket-2 roundtable → synthesis
→ back to LOKA.** Readiness plan: `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md`. Front-end /
LOKA integration tracked in [frontend-loka.md](frontend-loka.md).

## Top open items (→ flow to the workboard when assigned)
1. **LOKA adapter** — when the LOKA code lands, wire LOKA ↔ the frozen `run_live` contract (K1). The front
   door + contract are ready; this is the remaining front-end piece. (frontend-loka.md)
2. **Bucket-1 semantic corpora** (`semantic-corpora`) — Hayes 6 / Gavin 6, dual-source, method locked. In
   motion; each lights up at run time automatically now that K2 has landed. (tools.md)
3. **Experiment Design tool** (`experiment-design`, **hayes**) — ED-1 done (port merged, #28); ED-2 (fill the design sheet) next. (tools.md)
4. **ASO Design tool** → feed sequences into the `aso-tox` channel. (tools.md)
5. **Broaden scenario coverage**; **retire/label mocks**; **chronic-tox** (roadmap). (engine.md, tools.md)
6. **Quant-fact seams round 2** (deferred): DepMap, AlphaMissense, Foldseek (bulk-data). (tools.md)

*(✅ done: quant-fact-seams (4 seams); FDA-memory dual-source corpus + method/gate; **K1 — front door now serves
the live firm**; **K2 — Bucket-1 agents read their corpora at run time**; cross-platform test hardening. The
backend is now end-to-end-capable on its own.)*

## Top risks
- **Enforcement is local-only** (free repo, no branch protection/Actions) — relies on cooperating agents +
  `dev/audit-history.sh`. See `dev/CONVENTIONS.md` §1.
- **Console UI still renders the canned data file** — `/api/run` serves the live path, but the static Console
  page hasn't been re-pointed; don't overclaim "live" for the Console demo until that lands.
- **Mock surfaces** must stay labeled; "SOTA on shit is still shit."
