# WO-9 — Sapphire "Research Partner" v2

**From:** Head Claude (rohan) · **To:** Rohan Claude (builder) · **Date:** 2026-06-30
**Baseline:** `main` (= UI v1 @ `ui-v1-2026-06-30`; backup branch `rohan/backup-ui-v1-2026-06-30`).
**Goal:** turn Sapphire from "a report generator" into "a research partner you can interrogate," per the
prioritized roadmap the user approved.

## Operating rules (NON-NEGOTIABLE — read before starting)
Read `dev/CONTRIBUTOR_RULES.md`, `dev/PR_REVIEW.md`, `CLAUDE.md` (Hard rules), `sapphire-orchestrator/AGENTS.md`.
- **Branch + PR flow:** work on `rohan/<slug>` cut fresh from `main`; **one PR per phase**; Head Claude reviews,
  approves, and merges — you only submit PRs. Rebase on `main` before each PR (Gate 3.6 base-freshness).
- **Every commit:** `Built-By: rohan` + `Co-Authored-By: Claude <...>` trailers. **Never `--no-verify`. Never
  push to `main`.** Push with the user's PAT only when asked; scrub the token from the remote after.
- **Data boundary:** Quiver internal EP/CRISPR scores NEVER leave to EMET / web / Q-Models. Public identifiers
  only (gene symbols, SMILES, disease terms). Storing public-safe evidence in the run for the UI is fine.
- **Facts vs judgment:** Bucket 1 = cited facts; Bucket 2 = opinions citing the dossier. Personas never invent
  facts. Internal↔external conflicts = `DIVERGENCE` (surface, don't reconcile). Veto facts = gates.
- **Honesty:** never fabricate; mark `simulated`/`unavailable`/`paper-claim` vs `proven`; never oversell a mock.
- **No emojis anywhere in `web/src`** (lint enforces). lucide icons + colored dots only.
- **Hermetic tests / no CPU storm:** run the suite as `CLAUDE_BIN=/usr/bin/false bash dev/run-tests.sh`
  (the per-step summarizer + report + scoped-chat shell out to real `claude` — running the suite with real
  claude floods the machine; keep `SAPPHIRE_NO_STEP_SUMMARY=1` behavior intact). Also `cd web && npm run build`
  + `npx vitest run` + emoji-lint green before every PR.
- **No nested subagents:** if you delegate to a subagent, tell it explicitly to do ALL work inline and NOT use
  the Agent tool; use **Sonnet** for build subagents. Be token-lean.
- **Keep the report reliable:** `report.py` timeout is 300s; don't reintroduce the 120s fallback.

## The work — one PR per phase, in order

### Phase 1 (P0, keystone) — Main-chat follow-up over stored evidence
When the user asks a follow-up **in an existing conversation**, answer from the STORED run — do NOT re-convene
the 23 agents. The run already persists the full per-agent evidence (`discover.agents[].detail`, the dossier,
verdicts, and the report).
- **Backend:** add `POST /api/followup` (in `frontend2/server.py`) → `{conversation_id, question}` → load the
  stored run → a Claude call that answers grounded ONLY in that run's evidence (reuse the `report.py` honesty +
  `[[source]]` citation conventions; mirror `scoped_chat`'s never-fabricate guard but over the WHOLE run). If
  the question genuinely needs new data, it must SAY which agent/tool it would run rather than invent an answer
  (offer a "run it" affordance; do not silently re-run). Stream if feasible. Hermetic-testable (CLAUDE_BIN seam,
  deterministic fallback, never raises — mirror `report.py`/`summarizer.py`).
- **Frontend:** the main composer, inside an existing conversation, routes follow-ups to `/api/followup` and
  renders the answer as a new turn with citation pills. Clearly distinguish "follow-up (from this run's
  evidence)" from "new run (full firm)" — auto-detect or a small toggle. New (empty) conversations still do a
  full `/api/run`.

### Phase 2 (P0) — Harden the LIVE run (real content, watchable)
- Verify a real `profile=live` run end-to-end produces GENUINE partner reasoning + real tool outputs (not
  placeholders). Keep the summarizer storm killed. Parallelism already lands ~6 min — keep it reasonable.
- **Stream the report as it writes** (progressive render) so the user isn't staring at a 70–100s spinner.
- Make real-vs-simulated obvious at a glance in the UI.

### Phase 3 (P1) — Genuine, inspectable source outputs
- Build on the Q-Models tool-selection work (`dispatch_qmodels` now selects DTI / kg_hypothesis /
  variant_effect and records tool_id + input). Make each source return real, inspectable evidence; the Info
  panel's "full detail" should be genuinely useful for drill-down + the new follow-up chat.

### Phase 4 (P1) — Robust planner for varied queries
- Handle the real CNS prompt range (`source/Sapphire Prompt Work_Feb 2026/…`): comparisons, rankings (→ tables),
  SMILES, ASO sequences, multi-gene — beyond the gene+disease TSC2 path. Scoping must not break on varied input.

### Phase 5 (P2) — Workspace for daily use
- Rename / organize / delete conversations, working search, export (Markdown now; PDF nice-to-have), and the
  streaming-report UX from Phase 2 wired through.

## Definition of done (each phase)
Gates green (hermetic suite + web build + vitest + emoji-lint), data-boundary + honesty respected, no emojis,
docs/ledger/workboard updated, PR opened to Head Claude with a clear description. **Do not merge — Head Claude
gates and merges.** If blocked on something you shouldn't guess, ask via `dev/HELP.md`.
