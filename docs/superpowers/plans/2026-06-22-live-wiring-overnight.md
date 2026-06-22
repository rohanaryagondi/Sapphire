# Overnight Plan — Live Harness Wiring + Transparency + Scenarios + Loop (2026-06-22)

**Deadline:** 08:00. **Ship:** commit per phase on `Rohan`, then push `origin/Rohan` (fall back to local commits + flag if auth fails). **Repo:** `~/Desktop/Projects/Quiver/sapphire-capability-map` (local; off OneDrive).

**Goal:** turn the proven-but-isolated Phase-5 components into the firm actually running through the harness on any query — verified WITHOUT burning money or tokens, plus terminal transparency, the 8 scenarios runnable, and the self-improvement loop running live.

## Verification doctrine (the "run it without spending" rule)
- **Personas / LLM agents:** dispatched through `harness.run` with their real contracts, but verified with **injected MOCK outputs** (no live Claude). We prove they *can* run and *have the inputs/contracts/guardrails* they need.
- **EMET:** the seam is wired; verified mocked. Live EMET (user logged in) is used only for **scenario capture (P3)**.
- **Q-Models:** CPU tracks live (free/local); **GPU = dry-run** (`launcher.submit_job(mode="dry-run")` — renders+validates, **never touches AWS**).
- **Internal moat:** **REAL** (local SQLite, free) — runs for real everywhere.
- **Token efficiency:** sonnet subagents for all code/review/extraction; main loop only for EMET driving + the final opus whole-branch review.

---

## P1 — Agent registry + live harnessed engine  (the keystone) [sonnet subagents]
Make the firm dispatch every agent through `harness.run`, additively (legacy `orchestrator.run(sid)` canned path stays intact).
- **`harness/agents.json`** — expand to the full roster with contracts (`kind`, input/output schema refs, `tools_allowed`, `guardrails`, `provenance_label`): `internal-science-lead` (kind=python → moat), `emet-runner` (exists), `q-models-runner` (exists), the **13 semantic agents** (claude-subagent; the 2 veto-class flagged), and the **personas** (`company-partner` exists; add the institutional archetypes: ex-FDA, red-team, payer, KOL). Control (triage/scope/plan) stays deterministic in the orchestrator.
- **`sapphire-orchestrator/live_engine.py`** — `run_live(query, *, ctx=None, registry=None, engine=None) -> dict`:
  1. control: `engine.triage/scope/seat_panel/plan` (deterministic, reused from orchestrator).
  2. recall priors (`memory.recall(entities)`), open harness trace.
  3. Bucket-1: for each activated agent, `harness.run(agent_id, inputs, engagement_id, ctx)`; Internal Science Lead's agent fn returns `moat_facts(target)` (REAL). Assemble dossier (reuse Research-Manager slotting/flags from `orchestrator`).
  4. Bucket-2: for each seated persona, `harness.run("company-partner", {persona, dossier_fields}, …)`.
  5. synthesize (reuse orchestrator); close trace; `reflect`.
  - `ctx` carries injectable backends (`python_fns`, `emet_handler`, `qmodels_client`, persona mock) → verification uses mocks; moat is real.
- **Tests** (`sapphire-orchestrator/tests/test_live_engine.py`): `run_live("…TSC2…", ctx=<mock dispatch + real moat>)` → asserts: a dossier containing **real `moat-real` facts**, one trace record per dispatched agent, guardrails enforced (data-boundary blocks an internal id; persona must-cite), a roundtable + synthesis, and `reflection.written>0`. **All offline, $0.** This is the "prove they work" deliverable.

## P2 — CLI transparency (the glass-box) [sonnet subagent]
- **`sapphire-orchestrator/trace_view.py`** + `python -m … trace <engagement_id>` (or `run.py --trace <eid>`): pretty-print `RohanOnly/engagements/<eid>/trace.jsonl` as a readable timeline — `engagement_open` (query/plan), one block per agent (agent · kind · provenance · status ok/abstained/escalated · guardrails_run · repairs · inputs_hash · output summary), recalled priors, `engagement_close` (synthesis). TDD against a synthetic trace. Token-free, terminal-only.

## P3 — Scenarios: capability + live-EMET capture [main loop drives EMET; sonnet subagents extract/assemble]
- **Capability:** all 10 registered + runnable through `run_live` — real moat facts + EMET facts where captured, `KNOWN_UNKNOWN` where pending. Verify each `run_live(<scenario query>)` completes.
- **Capture (best-effort, EMET live):** drive EMET (Thorough + the matching workflow) for the 8 stubs, prioritized: scn2a_epilepsy, kcnt1_dee, c9orf72_als, gba1_pd, novel_ad_target(abstain), moat_divergence, rare_cns_payer, competitor_ip_gate. Save screenshots → **sonnet subagent extracts cited facts** → assemble `scenarios/<id>.json` (real PMIDs + real moat) → register + manifest `captured`. Honest about how many land before 08:00.

## P4 — Active-learning loop, live [local, free]
- Run all scenarios through `run_live`/`run_engagement` so memory accumulates; assert recall surfaces priors across runs (e.g. a 2nd Parkinson's query recalls the LRRK2/GBA1 priors).
- Seed `record_outcome` for 1–2 proposed experiments (one `confirmed`, one `refuted` → `moat_blindspot`); generate `selfimprove/REPORT.md` (prediction accuracy, blind spots, recall). All deterministic/offline.

## P5 — Ship + morning report
- Full test surface green (contracts·harness·emet·memory·selfimprove·moat·tests + new live_engine·trace). Per-phase commits on `Rohan`. **Push `origin/Rohan`** (attempt; if HTTPS auth fails, leave committed locally + flag). Final **opus** whole-branch review.
- **`MORNING-REPORT.md`**: what's wired live (per agent), how to see the trace (the CLI), scenario-running capability + count captured, the loop demo (memory/recall/metrics), exact test counts, honest remaining gaps (#4 Q-Models GPU real run, #6 Loka asks, full 300-prompt coverage, Console UI).

## Sequencing
P1 → P2 (free, subagents, do first/most). P3 EMET capture interleaved (slow; best-effort). P4 after P1. P5 last. If EMET is slow/unavailable overnight, P1/P2/P4 + the scenario *capability* still ship; captures are the only at-risk item.
