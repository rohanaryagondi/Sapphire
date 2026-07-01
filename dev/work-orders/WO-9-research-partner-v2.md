# WO-9 — Sapphire "Research Partner" v2 (the path to a working product)

**From:** Head Claude (rohan) · **To:** Rohan Claude (builder) · **Date:** 2026-06-30 (expanded)
**Baseline:** `main` (UI v1 @ `ui-v1-2026-06-30`; backup branch `rohan/backup-ui-v1-2026-06-30`).

## GOAL
A **working Sapphire research partner** (localhost is fine — no public hosting/auth in scope). For any hard
CNS question (the ~300 in `source/…` and harder) it convenes the *real* firm and gives you an answer you can
trust and interrogate:
- **Real cited facts** — EMET (live), Quiver data (live moat), the semantic agents (real Claude reasoning),
  and **Q-Models actually executed** — CPU tools locally AND **GPU tools on AWS**.
- **Real partner deliberation** — the roundtable is genuine Claude persona reasoning, not placeholders.
- **A synthesized, cited report** — reliable, streamed as it writes, honest (real-vs-simulated obvious).
- **Interrogable** — follow-ups answer from stored evidence AND, when needed, **the orchestrator re-invokes
  specific agents/tools on demand** (real execution, incl. AWS) and folds the new evidence in.

## OPERATING RULES (unchanged — read `dev/CONTRIBUTOR_RULES.md`, `dev/PR_REVIEW.md`, `CLAUDE.md` Hard rules)
Branch `rohan/<slug>` from `main`; **one PR per phase to Head Claude — you submit, you never merge/push main**;
rebase on main before each PR. `Built-By: rohan` + Claude co-author trailers; never `--no-verify`. Data
boundary (no internal Quiver scores to EMET/web/Q-Models; public IDs only). Honesty (never fabricate; mark
`simulated`/`unavailable`/`paper-claim` vs `proven`). No emojis in `web/src`. **Hermetic tests** —
`CLAUDE_BIN=/usr/bin/false bash dev/run-tests.sh` + `npm run build` + `npx vitest run` + emoji-lint green per
PR; keep `SAPPHIRE_NO_STEP_SUMMARY=1` + the 300s report timeout. No nested subagents; Sonnet builders;
token-lean. **AWS safety (Phase 4): NEVER launch a GPU box outside the proven safety envelope** — profile
`Rohan-Sapphire`, account-gate, create-only + append-only ledger, **teardown ONLY by ledgered id**, dry-run
default + explicit live opt-in, a spend guard. Use the `sapphire-aws-runner` agent for GPU runs.

## THE PATH — one PR per phase, in order

### ✅ Phase 1 — Follow-up chat over stored evidence — DONE (#158 + #159 hardening)
Main-chat follow-ups answer from the run's stored evidence, honesty-guarded, citation pills, robust parse.

### Phase 2 — Live run: real, reliable, streamed
- On **Live**, every fact agent + every partner runs REAL Claude — eliminate the "simulated model / real
  reasoning pending" placeholders in the roundtable and semantic agents. Genuine conviction-weighted verdicts.
- **Stream the report as it writes** (progressive render) — no 70–100s spinner. Trace already streams live.
- Real-vs-simulated unmistakable in the UI; keep the summarizer storm killed; reasonable wall-clock.
- Fix the **demo-profile footgun**: default new runs to Simulate (or hide/relabel `demo`) so a run always
  produces a real report.

### Phase 3 — Real LOCAL tool execution + inspectable outputs
- Semantic agents produce genuine reasoning on Live; **Q-Models local-cpu tools actually run** (e.g. DTI /
  Binder Triage) and return real predictions with provenance `live-local`.
- The Info "full detail" per agent is genuinely useful for drill-down + the follow-up chat.

### Phase 4 — AWS tool execution (GPU Q-Models) — the "spin up an AWS instance for tool calls" ask
- Wire the **already-proven async launcher** (`sapphire-orchestrator/qmodels/` + `RohanOnly/qmodels_run/`,
  live-verified) into `run_live`: when q-models selects a **GPU-tier tool** (Boltz-2 structure/binding/
  selectivity, ESM-2 family clustering, funNCion/PROTON), auto-launch a tagged `Name=Sapphire` GPU EC2 →
  attach the Sapphire EBS cache → run the `*_eval.py` → retrieve `result.json` → **teardown by ledgered id**.
  Delegate each GPU run to the **`sapphire-aws-runner`** agent.
- Provenance stamped (`gpu-live` vs stub); honest degradation to a labeled stub when AWS is off / dry-run.
- ALL AWS safety guards above. Dry-run is the DEFAULT; live GPU is an explicit per-run/session opt-in with a
  spend cap. This turns the trace's "not called — gpu-async stub" into a real executed tool result.

### Phase 5 — Targeted re-invocation (agentic follow-ups) — the "requery specific things" ask
- When a follow-up's `needs_new_data` is true (Phase 1 already detects this + names the agent/tool), let the
  orchestrator **actually invoke** that agent/tool: re-run EMET on a refined query, call a specific Q-Models
  tool (local or AWS via Phase 4), or re-scope/re-run the roundtable — then fold the new evidence into the
  answer AND the run's stored evidence (so the trace + dossier grow).
- UI: a **"run it" affordance** — the user confirms before an expensive/AWS call; show the new agent(s) in the
  trace live. Depends on Phases 3 + 4 (real execution to invoke into).

### Phase 6 — Robust planner for the full query range
- Handle the ~300 real CNS prompts: comparisons, rankings (→ tables), SMILES, ASO sequences, multi-gene, and
  non-gene queries. Scoping / entity-extraction must not break on varied input; route to the right agents/tools.

### Phase 7 — Workspace + daily-use polish
- Rename / organize / delete conversations, working search, **sidebar cleanup** (prune old test runs), export,
  and wire the streaming-report UX from Phase 2 through.

## PARALLELIZATION — 3 concurrent tracks (for speed)
Run the phases as THREE parallel tracks, one per contributor. Rule of the road: **own your track's files,
rebase on `main` before every PR, keep each change function-scoped in shared files, one PR per phase.** Head
Claude gates every PR (functional-verifies) and resolves any cross-track conflict at merge.

- **Track A — Real & Streamed — `rohan`:** Phase 2 (live real + stream the report) → Phase 3 (real local
  tools) → **Phase 5 (targeted re-invocation, starts once Track B's Phase 4 has merged)**. Owns:
  `sapphire-orchestrator/live_engine.py` (run/dispatch flow), `report.py`, `frontend2/server.py` (SSE +
  `/api/followup`), `harness/dispatch.py` (claude-agent path), `web/src/components/run/*`, `synthesis.tsx`.
- **Track B — AWS Tools — `hayes`:** Phase 4 (GPU Q-Models on AWS via the already-proven async launcher +
  the `sapphire-aws-runner` agent). Owns: `sapphire-orchestrator/qmodels/*` (client/launcher/adapters/
  registry), the q-models branch of `harness/dispatch.py`, `RohanOnly/qmodels_run/*` (ledger). ALL AWS safety
  guards (Rohan-Sapphire profile · account-gate · create-only + ledger · teardown-only-by-ledgered-id ·
  dry-run default + explicit live opt-in + spend cap). This is INTEGRATION of proven plumbing, not from-scratch.
- **Track C — Breadth & Polish — `gavin`:** Phase 6 (robust planner for the full query range) + Phase 7
  (workspace: rename/delete, working search, export, sidebar cleanup, demo-profile footgun fix). Owns: the
  planner/scoping + entity-extraction (extract a `planner.py` module if it aids isolation),
  `web/src/components/history-rail.tsx`, `web/src/lib/store.ts` (workspace slices), search/export.

**Only dependency:** Track A's Phase 5 waits for Track B's Phase 4 to merge (re-invocation needs real tool
execution to invoke). Everything else runs concurrently. Shared files (`live_engine.py`, `store.ts`,
`dispatch.py`) are split by function-level ownership above — touch only your functions and rebase often.

## OUT OF SCOPE (for now, per the user)
Public hosting, auth, and external front-door deployment. Localhost is fine — do NOT spend effort there yet.

## Definition of done (each phase)
Gates green (hermetic suite + web build + vitest + emoji-lint), data-boundary + honesty + AWS-safety respected,
no emojis, docs/ledger/workboard updated, PR to Head Claude. **Do not merge — Head Claude gates (functional-
verifies with a real run) and merges.** Blocked on something you shouldn't guess? Ask via `dev/HELP.md`.
