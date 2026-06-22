# Delegation Board

The live assignment board for Sapphire. One row per active or queued task. Keep it current — a task that
isn't on the board isn't claimed. Newest tasks at the top of the table.

**Status values:** `todo` → `claimed` → `in-progress` → `in-review` (PR open) → `merged` / `blocked`.

## Claim protocol
1. Find or add the task here with a short id (`<area>-<slug>`), an owner handle, and a one-line goal.
2. Write a task brief in `docs/superpowers/plans/<date>-<slug>.md` (use `dev/templates/task-brief.md`) for
   anything Standard-tier or larger.
3. Set status `claimed` → cut your branch `<handle>/<slug>` off the latest `main`.
4. Drive the lifecycle (`dev/METHODOLOGY.md`): implement → review → verify → Gates 1–5 locally.
5. Open a PR to `main` (status `in-review`). Fill the PR template, including the gate evidence.
6. Rohan's Claude reviews → approves → merges (status `merged`). Then delete your branch.

Don't take two `in-progress` tasks that touch the same files concurrently across contributors — coordinate
here first to avoid merge pain. When in doubt, smaller PRs, more often.

## Active

| Task id | Owner | Status | Goal | Branch / PR | Plan |
|---|---|---|---|---|---|
| `dev-collab-harness` | `rohan` | in-review | Multi-contributor harness: attribution, delegation, PR-gated ship, branch protection | `rohan/collab-harness` | [plan](../docs/superpowers/plans/2026-06-22-collaborative-harness.md) |

## Backlog (proposed — claim to activate)

| Task id | Suggested owner | Goal |
|---|---|---|
| `aso-design-tool` | `hayes` | Build the ASO Design tool; feed its sequences into the `aso-tox` channel (`run_live(..., sequences=...)`). |
| `frontdoor-wire-run-live` | `rohan` | Wire `run_live` into `serve.py`/Console (the keystone: replace the canned path). |
| `scenario-coverage` | `gavin` | Broaden captured scenario coverage across the 10-axis variety matrix. |
| `chronic-tox-roadmap` | `hayes` | Scope the chronic-tox model integration (per the sprint deck roadmap). |

## Recently merged
*(moved here from Active on merge; trim periodically — `dev/LEDGER.md` is the permanent record.)*

| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `aso-tox-sequence-wiring` | `rohan` | 2026-06-22 | see LEDGER |
