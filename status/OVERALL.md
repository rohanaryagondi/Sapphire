# Sapphire — Overall Status

*One screen: where the build is. Updated 2026-06-28. Detail in the per-area docs; assignments in
[`WORKBOARD.md`](WORKBOARD.md).*

## ⏳ Current wave — live handoff (read FIRST if you're a fresh Head Claude)
*Updated 2026-06-28.* **WO-2 (front door) is COMPLETE.** The active push is the **"smarter orchestrator"
initiative** + proving/hardening the live tools.

- **✅ WO-2 front door — DONE & MERGED:** Phase A (#113, `run_live` whole: round2+spread+13 semantic
  agents+VETO gate+class), Phase B backend (#116, `POST /api/chat`→`run_live`, honest moat health), B-6
  console (#117, `frontend2` shareable `?mode=replay` + Gate-5 SSE drive). The front door serves the harnessed
  firm end-to-end with a live streamed trace + spread. **Suite 721 green.**
- **🎨 Front end = OURS (`frontend2`), decided.** We use our own console design, NOT a LOKA fork (user call,
  2026-06-28). The LOKA-adapter item is parked. Run it: `python frontend2/server.py --port 8100`.
- **🔄 In flight (background builders, being gated by Head Claude):**
  - **WO-5 moat rescue** — implement Loka's EXACT dual-rank union-filter method (+ heap-union fix +
    `supporting_genes`). User accepted Loka's genuine output (EP-distance rescue ≠ mechanistic for *compounds*:
    rapamycin is NOT in the EP data, verified twice — see [[wo5-moat-rescue-data-reality]]). Gate 5 = faithful
    Loka reproduction; the gene-rescue case (e.g. TSC2→MTOR) is meaningful.
  - **Smarter-orchestrator initiative** (in design): (1) **plan mode** — LLM-driven plan stage that selects
    tools + optional approval-gate; (2) **adaptive/evidence-driven tool deployment** — re-dispatch a tool when
    another agent surfaces a high-salience entity the initial data missed (e.g. EMET flags gene X → re-query
    the moat for X); (3) **model selection** — user picks the model per run (UI selector → `run_live` →
    dispatch); (4) **strict doc enforcement** — a mechanical gate requiring ledger/status/spec/WO updates.
  - **Q-Models GPU proof** — one real AWS GPU run to flip a `gpu-unproven` tool → `live` (cost-capped, ledgered, auto-teardown).
  - **Persistent BenchSci login** — a durable Chrome profile so EMET stays logged in (user logs in once).
- **Discovery caveat:** a pushed branch with NO PR is invisible to `gh pr list`. Always also run
  `git branch -r --no-merged origin/main` before concluding "nothing to do."
- **Worktree hygiene:** gate/build work happens in isolated worktrees (scratchpad / `/tmp`); the main working
  tree is never touched. `git worktree remove` stale ones. The `:8101` orchestrator_ui (branch
  `rohan/orchestrator-8101`, not on main) is an experimental demo asset, not the front door.

## Headline
The two-bucket firm runs end-to-end and **the front door now serves it live** (`POST /api/chat` /
`GET /api/run` → in-process `live_engine.run_live`, `via=engine-live`; `frontend2` streams the trace + spread).
Phases 1–6 + WO-2 are done. **721 tests green · 29 harnessed agents.** Fact sources are largely **live/real**
(EMET live · personas live · Q-Models real, some GPU tracks being proven · internal moat **real** ·
ASO-tox **real**). Active frontier: the **smarter orchestrator** (plan mode + adaptive tool deployment +
model selection) and proving the remaining tool tracks.

## At a glance
| Area | State | Live vs mock | Detail |
|---|---|---|---|
| Engine (orchestrator + live_engine) | ✅ runs end-to-end | canned path live; **`run_live` now serves the front door** (K1) | [engine.md](engine.md) |
| Runtime harness (29 agents) | ✅ done | guard-enforced, provenance-stamped, traced | [runtime-harness.md](runtime-harness.md) |
| Fact tools | ✅ mostly real | EMET live · personas live · Q-Models real (some GPU tracks being proven) · moat **real** · ASO-tox **real** | [tools.md](tools.md) |
| Dev/build harness | ✅ done | 3-contributor, PR-gated, local enforcement | [dev-harness.md](dev-harness.md) |
| Front door (serve.py `/api/run` + `/api/chat`) | ✅ **live firm** (WO-2 #116) | both → in-process `run_live` (`via=engine-live`); `?mode=claude`/`?mode=canned` = labeled fallbacks | [engine.md](engine.md) |
| **Front end (`frontend2/`) — OUR design** | ✅ **live (WO-2 #117)** | stdlib SSE console → in-process `run_live`; streams the full firm trace + two data planes + roundtable spread; profiles demo/simulate/live/replay + shareable `?mode=replay`. (`frontend/` Chainlit = supported fallback.) | [frontend-loka.md](frontend-loka.md) |

## Phases (done)
- **P1–P3:** control agents + Bucket-1 fact agents + Bucket-2 partners; orchestrator runs end-to-end (triage→
  plan→dossier→roundtable→synthesis); Console front face.
- **P4:** Q-Models toolset vendored; orchestrator can call any tool; two-speed routing (local-cpu sync /
  gpu-launch async); live AWS plumbing proven.
- **P5:** agent harness + live EMET + self-improvement loop + scenario suite.
- **P6:** ASO-tox tool integrated; **`run_live(..., sequences=...)`** feeds it real GBR tox facts (shipped
  2026-06-22, PR-gated).

## The end-to-end goal (realized)
End-to-end runs today: **query in `frontend2` → `live_engine.run_live` (the live harnessed firm) → Bucket-1
facts (EMET + moat + seams + corpora, corpus-first→search-the-gap) → Bucket-2 roundtable → synthesis →
streamed back to the console.** The front end is **our own `frontend2`** (decided 2026-06-28 — not a LOKA
fork). The next leap is making the orchestrator *smarter* (plan mode + adaptive tool deployment), not wiring a
new front end.

## Top open items (→ flow to the workboard when assigned)
1. **Smarter-orchestrator initiative** (in design → WOs incoming): plan mode · adaptive/evidence-driven tool
   re-dispatch · model selection · strict doc-enforcement gate. The active frontier. (engine.md, dev-harness.md)
2. **WO-5 moat rescue** (Loka's exact method) — building; gate when it lands. (tools.md, [[wo5-moat-rescue-data-reality]])
3. **Prove the GPU Q-Models tracks** — flip `gpu-unproven`→`live` with real AWS runs (one in flight). (tools.md)
4. **Persistent BenchSci login** — durable Chrome profile for EMET (building). (tools.md)
5. **Bucket-1 semantic corpora** (`semantic-corpora`, **hayes**) — remainder pending Hayes; each lights up at
   run time. (tools.md)
6. **Experiment Design tool** (`experiment-design`, **hayes**) — ED-1 merged (#28); ED-2 next. **ASO Design** →
   feed sequences into `aso-tox`. (tools.md)
7. **Broaden scenario coverage**; **retire/label mocks**; **chronic-tox** (roadmap); **quant-fact seams r2**
   (DepMap, AlphaMissense, Foldseek). (engine.md, tools.md)

*(✅ done: **WO-2 front door complete** (#113/#116/#117 — live firm served end-to-end via our `frontend2`);
quant-fact-seams (4 seams); FDA-memory dual-source corpus + method/gate; K1/K2; cross-platform test hardening.)*

## Top risks
- **Enforcement is local-only** (free repo, no branch protection/Actions) — relies on cooperating agents +
  `dev/audit-history.sh`. See `dev/CONVENTIONS.md` §1.
- **`/api/chat` and `/api/run` now both serve the live firm** (`via=engine-live`); `frontend2/` is the live
  SSE console. The legacy static Console (`site/`) still serves canned scenarios — acceptable for demo; don't
  overclaim "live" for the old Console until it's re-pointed.
- **The `:8101` orchestrator_ui console** (branch `rohan/orchestrator-8101`, not on `main`) is an experimental
  demo asset, not the production front door — keep it as a reference snapshot only.
- **Mock surfaces** must stay labeled; "SOTA on shit is still shit."
