**Note:** See [`REPORT.md`](REPORT.md) for the living architecture document.

# Morning Report — Overnight of 2026-06-22

**Branch:** `Rohan` · **Repo:** `~/Desktop/Projects/Quiver/sapphire-capability-map` (local, off OneDrive)
**Goal:** make the firm actually run through the harness on any query — verified without burning money or tokens — plus terminal transparency, captured scenarios, and the self-improvement loop running live.

**TL;DR:** #1 (live harness wiring), #2 (transparency), #3 (scenarios), and #5 (active-learning loop) are **done, tested, and committed** — **252 tests green**, 9 commits (incl. a review-driven fix pass), a final opus review. Verified under the "run it without spending" doctrine: personas + EMET mocked, Q-Models GPU **dry-run** (AWS untouched), **real local moat live**. I also captured **3 brand-new scenarios from live EMET** (6 captured total).

---

## What shipped (commits on `Rohan`)
| # | Commit | What |
|---|--------|------|
| Plan | `e4a2bc8` | Overnight plan doc |
| P1-a | `14f868c` | Full agent roster in the harness registry (18 agents: internal-science-lead, 12 semantic, 4 institutional) |
| P1-b | `5f7086d` | **`live_engine.run_live` — the keystone**: dispatches every agent through `harness.run` |
| P2 | `4303ad7` | **`trace_view.py` — CLI transparency** |
| P4 | `bf53c49` | Loop+trace demo: harnessed trace sample, memory accumulation, outcome→blind-spot, metrics report |
| P3 | `4f54ae1` | Live-EMET scenarios: SCN2A (mechanism), GBA1 (biomarker) |
| P3-b | `9777ddd` | Live-EMET scenario: C9orf72 ALS (modality) |

## #1 — The firm now runs through the harness (`live_engine.run_live`)
For any query, `run_live` runs control (triage/scope/plan deterministically), then **dispatches every Bucket-1 agent and every seated persona through `harness.run`** — contract-resolved, input-guarded, output-schema-validated, provenance-stamped, and traced. The **Internal Science Lead is wired to the REAL moat** (`moat_facts`); every other backend is injectable via `ctx`, so the offline test runs the whole firm with mock LLM/EMET/Q-Models outputs and the real moat — **$0, no tokens, no AWS**. `test_live_engine` proves: a real `moat-real` fact in the dossier, one trace record per dispatched agent, a **data-boundary guardrail blocking an internal id**, a roundtable + synthesis, and `reflection.written>0`.

## #2 — Transparency (CLI trace viewer)
```
cd sapphire-orchestrator && python trace_view.py <engagement_id> [--full]
```
Renders the run as a timeline: each agent · kind · status (✓/⚠/⛔) · provenance · guardrails · output summary, plus recalled priors and the synthesis. A real harnessed run is rendered in **`docs/sample-trace.txt`** (engagement `eng_6444d0e8` — 10 Bucket-1 agents + 5 personas, real moat fired). Missing trace → a clean "no trace" line, no crash.

## #3 — Scenarios: capability + 6 captured
- **Capability:** `run_live(<any query>)` runs the full harnessed firm — the system can run any of the ~300 questions; we don't have to pre-author them.
- **Captured (6):** `nav1_8`, `tsc2`, `lrrk2_pd`, **`scn2a_epilepsy`** (9 facts/11 PMIDs), **`gba1_pd`** (10 facts/15 PMIDs), **`c9orf72_als`** (10 facts/22 PMIDs). The 3 new ones were captured **live from EMET (Thorough)** tonight — real PMIDs only; uncited claims flagged `KNOWN_UNKNOWN`; DIVERGENCE flagged where the literature is genuinely split. Run any: `python run.py scn2a_epilepsy`.

## #5 — Active-learning loop, live
The loop runs end-to-end (deterministic, $0): scenarios run through `run_engagement` → **memory accumulated 58 records** (conclusions/facts/divergences/proposals/outcomes), `recall(LRRK2)` surfaces 5 priors, a **refuted outcome opened a `moat_blindspot`**, and `selfimprove/REPORT.md` reports prediction accuracy + blind spots. See `_build/loop_and_trace_demo.py`.

## How to drive it
```
cd sapphire-orchestrator
python run.py gba1_pd                 # run a captured scenario (canned dossier)
python trace_view.py <eid>            # see exactly what every agent did
python3 ../_build/loop_and_trace_demo.py   # regenerate the loop+trace demo ($0)
# run_live(query, ctx=...) is the harnessed live path (live LLM/EMET need real backends in ctx)
```

## Tests
**252 total, all green** — contracts · harness · emet · memory · selfimprove · moat · tests (incl. hardened live-engine + trace-view tests from the fix pass). New: `test_live_engine` (7), `test_trace_view` (13), `test_loop_demo` (8), `test_roster` (16), scenario tests updated.

## Honest gaps (deliberately deferred / out of scope tonight)
- **Live LLM in `run_live`:** the persona/semantic/EMET backends were **mocked** for verification (your "no token burn" rule). Wiring the real Claude runner + live EMET into `run_live` for a true end-to-end paid run is a flip of `ctx` backends — proven to dispatch, not yet run for real.
- **#4 Q-Models GPU:** verified **dry-run only** (no AWS spend); one real GPU eval still never run. **#6 Loka asks** (their repo, 7-stage workflow doc, DisGeNET key, MoA model) untouched, as agreed.
- **Coverage:** 6 scenarios captured; the rest of the corpus remains stubs (one EMET capture each — the pipeline is proven).
- **Console UI:** transparency is terminal-only (as requested — "no fancy UI").
- **Minor:** `recall` keys on genes/entities; a disease-only recall (e.g. "Parkinson's") returns 0 because some scenarios plan as "general CNS" — gene recall works (LRRK2=5).

## EMET capture URLs (tonight, for reference)
SCN2A `…/chat/cbb64717-…` · GBA1 `…/chat/ad734624-…` · C9orf72 `…/chat/da99c861-…`

## Reviews & fixes
**Opus whole-branch review** (overnight): verified `run_live` routes every agent + persona through `harness.run` (not canned), the real moat DB is read live (TSC2 → Isorhamnetin/Momelotinib, `moat-real`), scenario PMIDs real with honest `KNOWN_UNKNOWN` flagging, stdlib-only, no secrets/binaries.

**Second pass — 2 sonnet reviewers (correctness + data honesty)** caught real issues the opus pass missed, all **fixed in `290530f`**:
- **(Critical) `must_cite_dossier` was miswired** — `dossier_fields` was passed in *inputs* but the guardrail reads it from *ctx*, so the citation allow-set was always empty and **every persona was force-abstained → the roundtable never produced a verdict**. (This corrects the opus note above: those abstentions were a bug, not the guardrail "working.") Fixed — and the hardened test proves personas now produce real verdicts when they cite the dossier: **0 → 5/5 ok**.
- **(Critical) Q-Models output silently dropped** — `q-models-runner` had no `output_schema` and returned no `facts`; it now returns findings-shaped output and contributes to the dossier.
- **(Important)** `trace_view` crash on non-dict output (guarded); two **vacuous tests** that masked the bug above (hardened to assert real verdicts + a computed trace-record count).
- **(Data)** `scn2a`/`gba1` `synthesize.entities` normalized to the canonical flat-dict shape; PMID `41850233` (a CSF-proteomics paper) removed from a tofersen-approval claim it didn't support.
- Data reviewer **verified 14 PMIDs against live PubMed** — all real and matching; no fabrication, no secrets/binaries.

**Result:** 252 tests green; roundtable produces real verdicts; honest citations intact.

## Push — done ✅
Pushed to `origin/Rohan` (`aed3803..8f5a839`, then this report). The full overnight build is on the remote.
