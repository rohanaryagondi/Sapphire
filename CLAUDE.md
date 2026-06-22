# CLAUDE.md — Sapphire (Quiver Bioscience)

Orientation for a new session. Read this, then `sapphire-orchestrator/AGENTS.md`. Spend tokens on the
work, not re-deriving context.

> **Building Sapphire?** See `dev/README.md` (the dev harness) — distinct from the product runtime harness in `sapphire-orchestrator/harness/`.

## What we're building
**Sapphire** = an agentic CNS drug-discovery decision system. A user-facing **orchestrator** runs a
two-bucket "firm":
- **Bucket 1 — Facts (junior analysts):** gather a *cited fact dossier* from EMET (BenchSci, live),
  Q-Models (model launchpad), the Quiver internal moat, and 13 semantic web agents. Iterate until the
  dossier is complete (contradiction/gap/veto checks), not one-pass.
- **Bucket 2 — Deliberation (partners):** a roundtable of company + institutional persona agents debate
  the dossier (independent verdicts → moderated rebuttal). **No forced consensus** — the spread is the product.
- The orchestrator then writes a report: the facts + how each player reacted.

**Goal:** handle the ~300 hard CNS questions in
`source/Sapphire Prompt Work_Feb 2026/Sapphire Prompts and Queries_For ExpoAI.docx` — and harder.

## Start here (in order)
0. **[`docs/README.md`](docs/README.md)** — the documentation hub (index of every spec, plan, report, and
   subsystem) + **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — the consolidated end-to-end walkthrough.
1. `sapphire-orchestrator/AGENTS.md` — the operating model + full roster + the 7 operating rules.
2. `sapphire-orchestrator/dossier_schema.md` — the "done" definition for the fact bucket.
3. `HANDOFF.md` — full narrative: vision, decisions + rationale, status, next steps.

## Status
- **Phase 1 DONE** (this branch): 3 control agents (Engagement Lead, Research Manager, Roundtable
  Moderator) + 3 scientific-core fact agents (Internal Science Lead, EMET Analyst, Q-Models Runner) +
  4 institutional partners (ex-FDA Regulator, Adversarial Red-Team, Payer, KOL) + company-partner
  template + dossier schema.
- **Phase 2 DONE:** all **13 semantic (non-scientific) fact agents** built in `architecture/bucket1/semantic/`
  (2 veto-class: FDA Institutional Memory ⛔, Patent/IP ⛔; + global regulatory divergence, DEA scheduling,
  clinical-trial registry, post-market safety, financial, payer, manufacturing/CMC, patient advocacy,
  KOL/social, policy/legislative, reputational). Built from Hayes' draft
  (`SemanticAgents/SemanticAgentsHayes_Sapphire_6.16.docx` on `origin/main`) — source lists kept, framing
  adapted to Quiver CNS; DEA + reputational are project additions beyond Hayes' 11.
- **Phase 3 DONE:** the orchestrator runs end-to-end. `sapphire-orchestrator/orchestrator.py` is the
  engine (real triage→scope→plan, Bucket-1 dossier with Research-Manager completeness/contradiction/
  VETO/DIVERGENCE rules, Bucket-2 two-round roundtable + spread, synthesis); `run.py` is the CLI
  (`python run.py nav1_8` | `"free text"` | `--json`). The `site/` Console is the front face — real
  query intake + a JS planner mirror (PLAN stage for any query), dossier with tier/flag chips, and the
  round-1→round-2 rebuttal. `_build/build_orch_data.py` runs the engine to generate the Console data
  (one source of truth). The `/sapphire` skill drives a live query (planner → cascade/EMET → Q-Models →
  persona subagents → synthesis). EMET + personas live; **Q-Models real** (CPU live-local, GPU via launcher);
  internal moat still MOCK (labeled).
  The **front-facing site is Console-first** (`site/index.html`); the full-flow explainer moved to
  `site/explainer.html`. **`sapphire-orchestrator/serve.py` is the subscription bridge** — serves the site
  and runs novel queries through **Claude Code headless on the user's subscription** (no API key; one
  `claude -p --json-schema` call returns the structured run) via `/api/run`, with graceful fallback to the
  canned scenarios + engagement plan on static hosting. "Claude under the hood" = the engine is the harness
  that enforces the rules; Claude is the reasoning at each box.
- **Phase 4 — Q-Models integration DONE** (`Rohan` branch, overnight 2026-06-21): the **full Q-Models
  toolset is vendored into `q-models/`** (source repo retired) and the **orchestrator can call any of the
  24 tools** by id via `call_model(tool_id, inputs)`. Two-speed routing: **`local-cpu` → sync HTTP** (real
  predictions, `provenance: live-local`, $0) and **`gpu-launch`/`endpoint`/`batch` → async launcher**
  (auto-launch tagged self-terminating EC2 → run `*_eval.py` → retrieve → auto-teardown; dry-run by default,
  live opt-in behind every safety guard). Per-tool status is marked honestly in `qmodels/registry.json`
  (live-local / stub / gpu / deprecated). **Live AWS plumbing proven** by `qmodels/smoke_test.py` (one
  t3.micro, verified teardown, ~$0.0017; full report in `RohanOnly/qmodels_run/REPORT.md`). Safety: profile
  `Rohan-Sapphire`, account-gated, create-only + ledger, **teardown only by ledgered id**.
- **Phase 5 — harness + live EMET + self-improvement loop + scenario suite DONE** (`Rohan`, 2026-06-21;
  built subagent-driven, every task spec+quality reviewed; full report
  `docs/superpowers/PHASE5-REPORT.md`). Five workstreams behind shared contracts (`sapphire-orchestrator/contracts/`):
  - **Agent harness** (`harness/`) — one runtime every agent runs through: declare→dispatch→validate→guard→
    stamp→trace. `harness.run(agent_id, inputs)`; registry `agents.json`; dispatch by kind
    (claude/qmodels/python/emet); mechanical guardrails (data-boundary BLOCKS, personas no-tools+must-cite,
    veto-is-a-gate, provenance stamped); fail-safe abstain/escalate (never fabricates); append-only trace at
    `RohanOnly/engagements/<id>/trace.jsonl`.
  - **Live EMET** (`emet/` + `.claude/skills/emet-runner/`) — a Playwright skill behind an MCP-swappable
    `make_emet_handler()` seam; login→escalate; cited **T2** facts; never emits a formal VETO.
  - **Self-improvement loop** (`memory/` + `selfimprove/`) — append-only public-only memory; entity `recall`;
    active-learning spine (`record_outcome` refuted → `moat_blindspot`); **tiered governance** (`governance.json`:
    memory auto, behavior-change gated to `proposed/`; flip flags → autonomous); metrics → `selfimprove/REPORT.md`.
  - **Integration** (`engagement.py`) — `run_engagement()` wraps the engine ADDITIVELY (orchestrator.py
    untouched): recall priors in → harness trace → reflect memory out. `python -m selfimprove record-outcome …`.
  - **Scenario suite** (`scenarios/manifest.json` + `capture.py`) — 10-axis variety matrix; nav1_8+tsc2
    captured, the rest honest `stub` (capture live via `_build/capture_scenario.py`, never fabricated).
- **Phase 6 — ASO tox tool integrated** (`Rohan`, 2026-06-22): **`aso-tox` agent** added to the harness
  registry (22 agents total). `tools/aso_tox/` contains Hongkang's GBR model (notebook +
  `aso_tox_gbr_model.pkl` + `predict.py`); stdlib-only seam at `sapphire-orchestrator/tools/aso_tox_seam.py`
  (kind `python`, provenance `aso-tox`). Fires in `live_engine` Bucket-1 when ASO sequences are present,
  downstream of the future ASO Design tool. Requires scikit-learn==1.8.0 in the tool subprocess only;
  engine remains stdlib-only. Per the 2026-06-19 sprint deck: **Loka is the front-end/orchestrator scaffold**;
  Quiver tools (OPAL, ASO Design, ASO toxicity [this], chronic-tox roadmap, Experiment Design) plug into it.
- **Tests: 268, all green.**
- **Still TODO:** wire `run_live` to the front door (`serve.py`/Console still use the canned path); wire
  ASO Design tool to feed sequences into `aso-tox`; broaden captured scenario coverage.

## Hard rules (non-negotiable)
- **Data boundary:** Quiver internal EP/CRISPR data + scores NEVER leave to EMET / web / Q-Models. Public
  identifiers only (gene symbols, SMILES, disease terms).
- **Facts vs. judgment:** Bucket 1 = cited facts only; Bucket 2 = opinions that cite the dossier. Partners
  never invent facts (they file a fact-request instead).
- **Internal↔external contradictions = `DIVERGENCE` findings** — surface, do NOT auto-reconcile. Often the
  alpha (Quiver sees what the literature can't). Only external↔external conflicts trigger re-fetch.
- **Veto facts** (FDA-memory, IP) = gates the roundtable adjudicates, never silent kills.
- **Demo fidelity, label it:** EMET = live, personas = live, **Q-Models = REAL** (CPU tracks `live-local`;
  GPU tracks via the live-proven async launcher; remaining tracks marked `stub`/`eval` in the registry —
  never silently mocked), **internal moat = REAL** (reads from the Loka CNS_DFP data via
  `sapphire-orchestrator/moat/` — `MoatClient` + `moat_facts`; provenance `moat-real`; degrades honestly
  to `[]`/mock if `RohanOnly/moat/moat.sqlite` hasn't been built from the parquet). **ASO tox** = live
  GBR model (`tools/aso_tox/`) — real predictions when ASO sequences present, stubs otherwise.
- **Two execution paths (important):** (1) **Canned path** `orchestrator.run(sid)` — runs pre-captured
  scenario JSONs, $0, deterministic; used by `run.py`/`serve.py`/Console today. (2) **Live harnessed
  path** `live_engine.run_live(query)` — dispatches EVERY agent + persona through `harness.run`
  (guard-enforced, schema-validated, provenance-stamped, traced); verified OFFLINE with mock backends +
  REAL moat; **NOT yet wired to the front door** (the keystone remaining task).
- **Empirical culture:** *"SOTA on shit is still shit."* Mark `proven` vs `paper-claim`; never oversell a
  mock or a paper benchmark.

## Map
| Path | What |
|---|---|
| `architecture/` | **The agent specs**, organized as the firm: `orchestrator/` (control) · `bucket1/` (facts — `scientific/` + `semantic/`) · `bucket2/` (partners + `institutional/`). A README at every level + a top-level agent report. |
| `sapphire-orchestrator/` | **The engine.** `orchestrator.py` · `live_engine.py` (`run_live` — the live harnessed firm) · `run.py` · `engagement.py` (loop wrapper: recall→trace→reflect) · `serve.py` (subscription bridge) · `trace_view.py` (CLI transparency) · `contracts/` (shared P5 contracts: validator + provenance + schemas) · `harness/` (the agent harness — 22-agent registry, one runtime every agent runs through) · `emet/` (live EMET adapter+handler) · `tools/` (tool seams: `aso_tox_seam.py`) · `memory/` (durable memory store) · `selfimprove/` (governance · reflect · authoring · metrics · CLI) · `qmodels/` (**real launchpad**) · `moat/` (**real internal moat**: `MoatClient` + `moat_facts`; provenance `moat-real`; reads from Loka CNS_DFP SQLite) · `scenarios/` (+ `manifest.json`, `capture.py`) · `AGENTS.md` · `dossier_schema.md`. |
| `tools/` | **Quiver tool implementations** (separate from the engine). `aso_tox/` = Hongkang's GBR acute-tox model (notebook + `aso_tox_gbr_model.pkl` + `predict.py`). The engine seam is `sapphire-orchestrator/tools/aso_tox_seam.py`. |
| `q-models/` | **Vendored Q-Models toolset** (full code; source repo retired — see `q-models/VENDORED.md`). The 24 tools the orchestrator can call. |
| `RohanOnly/qmodels_run/` | Q-Models overnight run artifacts: AWS pre-existing snapshot, append-only ledger, smoke result, and `REPORT.md` (the integration report). |
| `sapphire-cascade/` | Runnable internal→gate→boost→abstain evidence pipeline; EMET live via Playwright. Skill: `sapphire-cascade`. |
| `personas/` | James' 59 company personas (md, by archetype). Wrapped by `company-partner-template.md`. |
| `capability_map.xlsx`, `model_landscape.md`, `integration_map.md`, `orchestration_brief_hayes.md`, `expert-agent/` | **Research foundation** — what to build, which models per capability, the 3-layer data vision, the CAP-15 expert-agent design (regulator partner reuses it). |
| `site/` | Interactive walkthrough + the orchestrator **Console** (demo surface). |
| `source/`, `meetings/`, `specs/` | James' raw Feb-2026 corpus (the ~300 prompts, 399 pipelines), the strategy-meeting transcript, design specs. |
| `_build/` | Re-runnable generators (personas→md, xlsx, site data). |

## Run
- Site: `cd site && python -m http.server 8077`. Regenerate data: `python _build/build_site_data.py` + `build_orch_data.py`.
- Empirical model verdicts: **Q-Mammal** repo (github.com/rohanaryagondi/Q-Mammal). Model launchpad: **Q-Models** (github.com/rohanaryagondi/Q-Models).

## Conventions
- Agent `.md` files follow one template (see end of `AGENTS.md`): Bucket/layer · One-liner · Activate-when
  · Inputs · Procedure · Output (contract) · Sources/tools or Persona-grounding · Rules · Hands-off-to.
- **`main` is the bedrock** (formerly the `Rohan` branch, promoted 2026-06-22; old `main` preserved at
  `main-backup-2026-06-22`). **Sapphire is now built by a 3-person team** (rohan · hayes · gavin), each
  driving their own Claude — see the **collaborative dev harness** in `dev/` (`CONTRIBUTORS.md`,
  `DELEGATION.md`, `PR_REVIEW.md`).
- **Work on a feature branch `<handle>/<slug>` cut from `main`; ship via a PR.** `main` is branch-protected —
  nobody pushes to it directly. **Only Rohan's Claude reviews, approves, and merges PRs** (`dev/PR_REVIEW.md`).
  Every commit carries `Built-By: <handle>` + the Claude `Co-Authored-By` trailer.
- Push with the user's PAT when asked; scrub the token from the git remote afterward.
