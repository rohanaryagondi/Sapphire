# CLAUDE.md — Sapphire (Quiver Bioscience)

Orientation for a new session. Read this, then `sapphire-orchestrator/AGENTS.md`. Spend tokens on the
work, not re-deriving context.

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
- **Phase 5 ideas (TODO):** wire the remaining `stub`/`eval` tracks live; swap the mock moat for the real
  Quiver latent space; capture more `scenarios/*.json`; add the cross-engagement memory / active-learning loop.
- **Then:** wire the orchestrator end-to-end; upgrade the `site/` Console to drive it.

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
  never silently mocked), **internal moat = MOCK** (user is wiring internal data — assume it lands).
- **Empirical culture:** *"SOTA on shit is still shit."* Mark `proven` vs `paper-claim`; never oversell a
  mock or a paper benchmark.

## Map
| Path | What |
|---|---|
| `architecture/` | **The agent specs**, organized as the firm: `orchestrator/` (control) · `bucket1/` (facts — `scientific/` + `semantic/`) · `bucket2/` (partners + `institutional/`). A README at every level + a top-level agent report. |
| `sapphire-orchestrator/` | **The engine.** `orchestrator.py` · `run.py` · `serve.py` (subscription bridge) · `qmodels/` (**real launchpad**: `registry.json` · `client.py` two-speed router · `launcher.py` safe async EC2 · `adapters.py` · `smoke_test.py`) · `scenarios/` · `AGENTS.md` · `dossier_schema.md`. |
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
- Work on the **`Rohan`** branch (the project bedrock). `main` also receives parallel pushes from other
  sessions — rebase on `origin/main` before pushing if it has moved.
- Push with the user's PAT when asked; scrub the token from the git remote afterward.
