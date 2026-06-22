# Sapphire — Architecture & Status Report

*Last updated: 2026-06-22 · branch `Rohan` · repo `~/Desktop/Projects/Quiver/sapphire-capability-map` (local).*
*This is the orientation document: what Sapphire is, how it's built, what works, and what's missing. For the overnight change log see [`MORNING-REPORT.md`](MORNING-REPORT.md); for agent specs see [`architecture/`](architecture/); for the engine see [`sapphire-orchestrator/`](sapphire-orchestrator/).*

---

## 1. What Sapphire is

Sapphire answers hard **CNS drug-discovery decision questions** ("is TSC2 a viable target?", "which modality for C9orf72 ALS?") the way a **firm** would — not as a single model call, but as a structured pipeline of specialist agents that gather **cited facts**, debate them from independent institutional viewpoints, and converge on a recommendation with an explicit confidence and a proposed next experiment. It is designed to be **honest** (every fact carries provenance; unknowns are flagged, never fabricated), **inspectable** (every agent's work is traced), and to **get better over time** (a cross-engagement memory + self-improvement loop).

The strategic moat is Quiver's proprietary **CNS perturbation data** (the Loka `CNS_DFP` embedding-distance dataset), wired in as a real evidence source.

---

## 2. The "firm" pipeline

Every question flows through the same four stages. The agent *specs* (org chart) live in [`architecture/`](architecture/); the *engine* that runs them lives in [`sapphire-orchestrator/`](sapphire-orchestrator/).

```
          ┌─────────────────────────────────────────────────────────────┐
  query → │  CONTROL    triage → scope → plan → seat the roundtable       │  (deterministic)
          └─────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────────────────────────────────────────┐
          │  BUCKET 1 — cited-fact DOSSIER                                │
          │   scientific core:  internal-science-lead (→ REAL moat)       │
          │                     emet-runner (→ EMET live)                 │
          │                     q-models-runner (→ Q-Models)              │
          │   13 semantic fact agents: fda-institutional-memory*,         │
          │     patent-ip*, global-regulatory-divergence, dea-scheduling, │
          │     clinical-trial-registry, post-market-safety, financial,   │
          │     payer, manufacturing-cmc, patient-advocacy, kol-social,   │
          │     policy-legislative, reputational      (* = veto class)     │
          │   Research-Manager rules: completeness · contradiction-by-    │
          │     tier · VETO · DIVERGENCE · KNOWN_UNKNOWN                   │
          └─────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────────────────────────────────────────┐
          │  BUCKET 2 — ROUNDTABLE (independent persona partners)         │
          │   company-partner (template) + institutional archetypes:      │
          │   ex-fda-regulator · adversarial-red-team · payer-partner ·   │
          │   kol-partner.   Round 1 verdicts → rebuttal → spread.        │
          │   Personas may ONLY cite the dossier (guardrail-enforced).     │
          └─────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────────────────────────────────────────┐
          │  SYNTHESIS  recommendation · consensus/dissent · convergent   │
          │             gate · proposed experiment · confidence           │
          └─────────────────────────────────────────────────────────────┘
```

### Two execution paths (important)
There are **two engines** that run this pipeline:

| | **Canned path** — `orchestrator.run(sid)` | **Live harnessed path** — `live_engine.run_live(query)` |
|---|---|---|
| Evidence | pre-captured scenario JSON (`scenarios/*.json`) | dispatched live: each agent via `harness.run` |
| Agents | logic only (facts are authored) | **every agent + persona actually dispatched** |
| Moat | the captured facts | **real moat DB, live** |
| Cost | $0, instant, deterministic | real backends cost tokens/time (mockable for $0 verification) |
| Used by | `run.py`, `serve.py`/Console, the loop demo | the new harnessed firm (verified offline) |

The canned path is what the Console/CLI run today; the live path (`run_live`) is the real firm and is **verified working offline** but **not yet wired to the front door** (see §6, gap 1).

---

## 3. Core subsystems

- **Agent harness** (`harness/`) — one runtime every agent goes through: `run(agent_id, inputs, *, engagement_id, ctx) → AgentResult`. Per call it: resolves the **contract** from `agents.json` (21 agents), runs **input guardrails**, **dispatches** by kind (`python` · `claude-subagent` · `qmodels-delegate` · `emet-playwright`), **validates output** against a JSON schema, runs **output guardrails**, **stamps provenance**, and **writes a trace record**. Fail-safe: on hard failure an agent **abstains/escalates** — it never fabricates. Guardrails enforced: `data_boundary` (no internal IDs leave Quiver), `facts_only_cited` / `must_cite_dossier`, `veto_is_gate`, `stamp_provenance`.
- **Internal moat** (`moat/`) — **REAL**. `MoatClient` + `moat_facts()` query a SQLite (`RohanOnly/moat/moat.sqlite`, gitignored) materialized from the 38.4M-row Loka `CNS_DFP` embedding-distance parquet via `_build/build_moat_db.py`. Direction-aware: `similar` (mimic) vs `opposite` (rescue), top-K per ref_type. Provenance `moat-real`; degrades honestly to `[]` if absent.
- **EMET** (`emet/`) — evidence from BenchSci's EMET (`emet.benchsci.com`), driven **live via Playwright** (Thorough mode, real cited PMIDs). MCP-swap ready (`emet-mcp` provenance reserved).
- **Q-Models** (`qmodels/`, top-level `q-models/`) — Quiver's predictive models on AWS Bedrock/GPU. CPU tracks run locally; GPU runs are **dry-run** by default (no AWS spend) and gated.
- **Memory + self-improvement** (`memory/`, `selfimprove/`) — append-only, **public-IDs-only** cross-engagement memory; `recall` surfaces priors at the start of a run; `record_outcome` feeds wet-lab results back and opens a `moat_blindspot` on a refuted prediction; `reflect` + `metrics` + tiered `governance` (advisory → autonomous). `engagement.run_engagement` brackets a run with recall→trace→reflect.
- **Transparency** (`trace_view.py`) — `python trace_view.py <engagement_id>` prints the run as an agent-by-agent timeline (kind · status ✓/⚠/⛔ · provenance · guardrails · output). Sample in `docs/sample-trace.txt`.
- **Front door** (`serve.py`, `site/`) — a stdlib bridge that serves the Console and runs queries on the user's **Claude subscription** (headless), with a provenance-honest UI.

### Provenance vocabulary (`contracts/provenance.py`)
`moat-real` · `emet-live` · `emet-mcp` · `qmodels:*` · `live-local` · `gpu-async` · `gpu-disabled` · `memory-recall` · `persona-judgment` · `synthesis` · `stub` · `mock` · `unavailable`. Every fact in a dossier carries one; the UI badges them so a reader always knows whether evidence is real, reconstructed, or mock.

---

## 4. Repository map

```
architecture/           Agent specs = the firm org chart (orchestrator/ control,
                        bucket1/scientific + bucket1/semantic, bucket2/institutional)
sapphire-orchestrator/  THE ENGINE
  orchestrator.py         canned deterministic pipeline + SCENARIOS registry
  live_engine.py          run_live() — the live harnessed firm
  harness/                runtime · dispatch · guardrails · contracts · agents.json · trace
  moat/                   MoatClient + moat_facts (REAL)
  emet/                   EMET seam
  qmodels/                Q-Models integration
  memory/ selfimprove/    cross-engagement memory + self-improvement loop
  engagement.py           run_engagement (recall→trace→reflect)
  trace_view.py           CLI transparency
  scenarios/              6 captured scenario dossiers + manifest
  serve.py · run.py       subscription bridge + CLI
  contracts/provenance.py provenance vocabulary
site/                   Console (chat UI + inspector)
_build/                 build tools (build_moat_db.py, loop_and_trace_demo.py — pyarrow OK here only)
docs/                   ARCHITECTURE.md, LOKA.md, plans/, sample-trace.txt
RohanOnly/              runtime artifacts: moat.sqlite (gitignored), engagements/ traces, memory/
sapphire-cascade/       the original re-ranking "Discover" engine (predecessor, still present)
CLAUDE.md · HANDOFF.md · MORNING-REPORT.md · REPORT.md (this file)
```

---

## 5. What's built and working ✅

| Area | Status |
|---|---|
| The firm runs end-to-end (canned) | ✅ triage→dossier→roundtable→synthesis; CLI + Console + subscription bridge |
| **Live harnessed engine** (`run_live`) | ✅ every agent + persona dispatched via `harness.run`; verified **offline, $0** |
| Agent harness + 21-agent registry | ✅ guard-enforced, schema-validated, provenance-stamped, traced |
| Guardrails (real, negative-path proven) | ✅ data-boundary blocks internal IDs; personas forced to abstain on uncited claims |
| **Internal moat — REAL** | ✅ CNS_DFP SQLite; direction-aware mimic/rescue; `moat-real` |
| **EMET — live** | ✅ Playwright on `emet.benchsci.com`; real cited captures |
| CLI transparency (`trace_view`) | ✅ agent-by-agent timeline |
| Self-improvement loop | ✅ memory accumulates, recall, outcome→blind-spot, metrics report |
| Captured scenarios (6) | ✅ `nav1_8, tsc2, lrrk2_pd, scn2a_epilepsy, gba1_pd, c9orf72_als` (3 new from live EMET, real PMIDs) |
| Tests | ✅ **252**, all green |
| Reviews | ✅ opus whole-branch + 2-reviewer pass; 2 Critical bugs found & fixed |

---

## 6. What's missing / incomplete ⛳ (honest, prioritized)

1. **The live path isn't wired to the front door.** `serve.py`/Console still use the canned engine (or a single Claude reconstruction) for novel queries — they don't yet call `run_live`. **This is the keystone remaining task**: route the Console/CLI through `run_live` so *any* user question runs the full harnessed firm. (Once done, the trace viewer shows it for free.)
2. **Real backends in `run_live` have never been run for real.** Personas (Claude), EMET, and Q-Models are **mocked** in verification (the "no token/$ burn" rule). Flipping `ctx` to the live Claude runner + a logged-in EMET session + the real Q-Models client is proven to *dispatch*, but no paid end-to-end run has executed.
3. **Institutional personas aren't individually dispatched.** `run_live` seats every Bucket-2 slot through the generic `company-partner` template; `ex-fda-regulator`, `adversarial-red-team`, `payer-partner`, `kol-partner` are registered but not invoked. Either wire them per-seat or formally adopt the template approach (and stop implying otherwise in tests).
4. **Q-Models depth.** CPU tracks + GPU **dry-run** only; **one real GPU eval has never been run**; some tracks are stubs.
5. **Moat scoring vs. Loka.** The real EP-distance substrate works, but Loka's higher-level rescue scoring (e.g. reproducing "rapamycin rescues TSC2") is **not** reproduced — gated on getting Loka's repo + 7-stage workflow doc (the external asks).
6. **Scenario coverage.** 6 of the ~300 target questions captured; 5 named stubs remain (`kcnt1_dee, novel_ad_target, moat_divergence, rare_cns_payer, competitor_ip_gate`). The capture pipeline is proven (one live-EMET pass each); the system can already *run* any query via `run_live`.
7. **The loop needs real outcomes.** It runs on seeded/demo outcomes; real wet-lab `record_outcome`s are needed for the blind-spot/calibration machinery to actually improve predictions, and to justify moving governance from advisory toward autonomous.
8. **Transparency is terminal-only.** No Console/web view of the trace yet (deliberately deferred — "no fancy UI").
9. **Smaller gaps.** `recall` keys on genes, so a disease-only query that plans as "general CNS" recalls 0 priors; EMET is Playwright (an EMET **MCP** would replace the browser seam); the moat DB must be rebuilt locally (`python3 _build/build_moat_db.py`) since it's gitignored.

### Suggested next step
Do **#1** (wire `run_live` into `serve.py`/Console with real backends, behind a flag) — it converts the proven-but-isolated live engine into the actual product, and #8 (web trace view) then falls out almost for free. #6 (coverage) and #7 (real outcomes) make it broad and self-improving; #4/#5 are depth/partnership items.

---

## 7. How to run it

```bash
cd ~/Desktop/Projects/Quiver/sapphire-capability-map/sapphire-orchestrator
python run.py tsc2                      # run a captured scenario (canned, $0)
python run.py "is GBA1 druggable in PD?"   # free-text → plan + routed scenario
python trace_view.py <engagement_id>    # see exactly what every agent did
python3 ../_build/loop_and_trace_demo.py   # regenerate the loop + trace demo ($0)
python3 ../_build/build_moat_db.py      # (re)build the real moat SQLite from the parquet
# run_live(query, ctx=...) is the harnessed live path; supply live backends in ctx for a real run
```
Full test surface: `cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove moat tests; do python -m unittest discover -s $s/tests; done`
