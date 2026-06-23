# Workboard

**Where each contributor's agent finds its pending work.** One section per person. If a task isn't here under
your handle, it isn't yours to start. This is the live assignment state; the *protocol* for claiming/assigning
is `dev/DELEGATION.md`, and the *lifecycle* for building is `dev/METHODOLOGY.md`.

**Status values:** `assigned` → `claimed` → `in-progress` → `in-review` (PR open) → `merged` / `blocked`.

> **For Hayes's and Gavin's agents:** you currently have **no assigned work** — do not start anything yet.
> First time in the repo, run `bash dev/setup-contributor.sh <handle>` and read `dev/CONTRIBUTOR_RULES.md`.
> When Rohan assigns you a task it will appear under your section below with a brief link. Wait for it.

---

## rohan  (`@rohanaryagondi`) — lead + approver
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| _none in progress_ | — | (approver: review Hayes's quant-fact-seams PRs) | — | — |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `quant-fact-seams` | in-progress | Build 4 quantitative-fact Bucket-1 seams in the `aso-tox` pattern. **gnomAD ✅ (#6) · GTEx ✅ (#9) · InterPro ✅ (PR-C) merged.** Remaining: **g:Profiler (PR-D, last)**. | next: `hayes/gprofiler-enrichment` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md) |
| `experiment-design` | queued (after seams) | **Epic.** Port Matt's `design-form-agent` into Sapphire as a standalone tool: meeting-notes → filled experiment-design sheet. Phase 1 = ED-1 (port + fidelity-lock) → ED-2 (fill the design sheet). Moat/firm wiring is a later epic. | `hayes/experiment-design-port` (ED-1) | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) |

> **Hayes — run autonomously** (`dev/CONTRIBUTOR_RULES.md` §Autonomous operation): `git pull origin main`
> first (the watcher `dev/watch-assignments.sh` now exists — launch it: `bash dev/watch-assignments.sh hayes
> HayesStewart-QuiverBS`; on your gh-less box it runs board-only, which is your main signal). **Queue:**
> (1) finish `quant-fact-seams` — gnomAD ✅ + GTEx ✅ + InterPro ✅ merged; **g:Profiler (PR-D, last)** on
> `hayes/gprofiler-enrichment`; template = any merged seam (gnomAD/gtex/interpro), full Gates 1–5.
> (2) **THEN** the `experiment-design` epic (ED-1 first) —
> [brief](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md).
> **Musts:** (a) branch from the **latest `main`** (`git pull` first; merge `origin/main` if it moves);
> (b) **token-less PR flow is sanctioned** — push the gated branch + put the PR body in your report; I open +
> merge (your `gh`-less machine can't `gh pr create`, that's expected). Blocked? post in `dev/HELP.md`; the
> answer (merged to main) wakes your board watcher.

## gavin  (`@GavinWongYF`) — contributor
_No work assigned yet._

---

## Shared backlog (unassigned — Rohan assigns from here)
Pulled from `status/OVERALL.md` open items. To assign: move a row into a person's section above, set status
`assigned`, and link a brief in `docs/superpowers/plans/`.

| Task id | Suggested owner | Goal | Area |
|---|---|---|---|
| `frontdoor-wire-run-live` | rohan | Wire `run_live` into `serve.py`/Console — replace the canned path (the keystone) | [engine](engine.md) |
| `aso-design-tool` | hayes | Build the ASO Design tool; feed designed sequences into the `aso-tox` `sequences=` channel | [tools](tools.md) |
| `scenario-coverage` | gavin | Broaden captured scenario coverage across the 10-axis variety matrix | [engine](engine.md) |
| `retire-mocks` | — | Audit + honestly label/retire remaining mock surfaces | [tools](tools.md) |
| `chronic-tox` | hayes | Scope + integrate the chronic-tox model (roadmap) | [tools](tools.md) |
| `crossplatform-test-hardening` | rohan/gavin | Fix 3 pre-existing cross-platform test failures Hayes flagged (HELP.md, resolved): moat clone-name test hardcodes `sapphire-capability-map`; `test_scenarios`/`test_trace_view` assume UTF-8 (fail on Windows cp1252). Low-risk: derive the moat suffix from the repo root; add `encoding="utf-8"` + guard the `✓` stdout write. | [dev-harness](dev-harness.md) |

## Recently merged
| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `quant-fact-seams` (PR-C InterPro) | hayes | 2026-06-23 | PR #11 |
| `autonomous-contributors` | rohan | 2026-06-23 | PR #10 |
| `quant-fact-seams` (PR-B GTEx) | hayes | 2026-06-23 | PR #9 |
| `quant-fact-seams` (PR-A gnomAD) | hayes | 2026-06-23 | PR #6 |
| `repo-streamline` | rohan | 2026-06-23 | PR #5 |
| `status-vision-hardening` | rohan | 2026-06-22 | PR #3 |
| `dev-strict-branch-rules` | rohan | 2026-06-22 | PR #2 |
| `dev-collab-harness` | rohan | 2026-06-22 | PR #1 |
| `aso-tox-sequence-wiring` | rohan | 2026-06-22 | see LEDGER |
