# Sapphire Phase 5 — Completion Report

**Date:** 2026-06-21 · **Branch:** `Rohan` (not pushed to main) · **Method:** subagent-driven development (every task: implement → spec+quality review → fix-loop → whole-branch review).

**Bottom line:** Five workstreams shipped behind shared contracts — the agent harness, live EMET via Playwright, the self-improvement loop, the science scenario suite, and the integration that runs the loop on the real engine. **~137 stdlib-only tests green. The legacy demo engine is untouched and still runs.** Nothing pushed to main.

---

## What shipped

### P0 — Shared contracts (`sapphire-orchestrator/contracts/`)
Stdlib JSON-Schema validator, the canonical provenance vocabulary, and the EMET-envelope + memory-record schemas every workstream imports. 22 tests.

### D — Agent harness (`sapphire-orchestrator/harness/`)
The single runtime every agent runs through: **declare → dispatch → validate → guard → stamp → trace**.
- `harness.run(agent_id, inputs, *, engagement_id, ctx) -> AgentResult`; registry `agents.json`; dispatch by kind (`claude-subagent` / `qmodels-delegate` / `python` / `emet-playwright`), all injectable → tested offline.
- **Mechanical guardrails** (the CLAUDE.md hard rules): `data_boundary`/`public_identifiers_only` BLOCK (never strip), personas get empty tools + `must_cite_dossier`, `veto_is_gate`, `stamp_provenance`.
- **Fail-safe:** bounded repair → typed abstain/escalate; **never fabricates**.
- Append-only trace at `RohanOnly/engagements/<id>/trace.jsonl` — the audit surface AND the loop's input. 51 tests.

### A — Live EMET (`sapphire-orchestrator/emet/` + `.claude/skills/emet-runner/SKILL.md`)
EMET (BenchSci) as a harness-callable agent: a Playwright skill wrapping `emet_protocol.md`, behind an **MCP-swappable** `make_emet_handler()` seam (when the EMET-MCP lands, only the runner changes). Manual auth — login screen → `HarnessEscalation("login-required")`, never auto-login. Adapter normalizes the EMET envelope → cited **T2** dossier facts; **EMET never emits a formal VETO** (that is the veto-class agents' T1 job). 18 tests.

### C — Self-improvement loop (`sapphire-orchestrator/memory/` + `selfimprove/`)
- **Memory** — append-only, **public-identifiers-only** (every write runs the harness data-boundary and refuses internal Quiver data), schema-valid. `write` / `recall` (entity-overlap + recency) / `record_outcome` / `rebuild_index`.
- **Active-learning spine** — a proposed experiment + `record_outcome`; a **refuted** outcome opens a `moat_blindspot` linked to both the proposal and the outcome (verified live; recall by gene finds the chain).
- **Reflect** — post-engagement: reads the harness trace → writes conclusions/proposals/facts/divergences to memory.
- **Governance** (`governance.json`) — **tiered**: memory auto-applies; skills/specs/scenarios/routes are gated to `proposed/` for human approval. The path to fully-autonomous is flipping flags — no code change.
- **Metrics** (`selfimprove/REPORT.md`) — prediction accuracy, blind spots, recall — so "gets better" is a tracked number. 34 tests.

### B + Integration (`engagement.py`, `selfimprove/cli.py`, `scenarios/manifest.json`, `capture.py`)
- **`run_engagement()`** wraps the existing `Orchestrator` **additively** (`orchestrator.py` untouched): recall priors in → harness trace → reflect memory out. The loop now runs end-to-end on real engagements (verified: `run_engagement('nav1_8')` wrote 10 schema-valid memory records, recallable by gene).
- **`python -m selfimprove record-outcome <proposal_id> <result>`** — the active-learning feedback path for wet-lab/real outcomes.
- **Scenario suite** — `scenarios/manifest.json` is the 10-axis variety matrix (go/no-go · selectivity · mechanism · modality · ADMET/BBB · biomarker · abstain · divergence · payer · IP-veto). `nav1_8` + `tsc2` are `captured`; the other 8 are honest `stub`s, captured live via `_build/capture_scenario.py` — **never fabricated**. 19 tests.

---

## What the reviews caught (and we fixed)
The two-stage review per task earned its cost:
- A **data-boundary value-side leak** — internal scores embedded as string *values* slipped the key-only check; hardened so every internal term is also a value-side pattern.
- The harness **error-code path** was string-parsed and fragile → made unambiguous (schema vs guard errors tracked separately).
- EMET **sparse-envelope** cases (null claim / empty chat_url) would have escalated a human → degrade gracefully now.
- The big one in C: reflected conclusions would have been **unrecallable by gene** (real `synthesize` omits `entities`) → `reflect` now falls back to the engagement's candidates.
- Integration discovered the live engine emits an invalid `tier="-"` → tier-normalized before memory (load-bearing, verified).

## Safety posture
- Memory and EMET are **public-identifiers-only**, enforced mechanically (the boundary BLOCKS, before any write/dispatch).
- The self-improvement loop is **tiered**: it writes memory automatically but **cannot change its own behavior** (skills/specs/routes) without a human approving the `proposed/` draft.
- Nothing fabricates: failures abstain/escalate; stub scenarios are marked, not invented.

## Open items (Phase 6)
1. Rewire each orchestrator agent-seam through `harness.run` (the legacy engine still serves canned evidence; the harness is proven and callable, but the per-seam swap is a separate, careful step).
2. Capture the 8 stub scenarios live (needs a BenchSci session): `python _build/capture_scenario.py "<query>"` → curate the draft → move into `scenarios/`.
3. Wire `qmodels_fn` into the live capture wrapper; wire remaining Q-Models `stub`/`eval` tracks.
4. Swap the mock internal moat for the real Quiver latent space (a confirmed `moat_blindspot` is the labeled example that updates it).
5. Upgrade the `site/` Console to surface priors + the metrics report.

## Run it
- Tests: `cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove; do python -m unittest discover -s $s/tests; done && python -m unittest discover -s tests`
- Loop on the real engine: `python -c "import engagement; print(engagement.run_engagement('nav1_8')['reflection'])"`
- Record an outcome: `python -m selfimprove record-outcome <proposal_id> confirmed --data "..." --source wetlab`
- Metrics: `python -m selfimprove report`
