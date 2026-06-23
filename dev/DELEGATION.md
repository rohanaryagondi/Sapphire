# Delegation — the assignment protocol

This file is the **protocol** for how work is assigned and claimed. The **live assignment state** (who has
what, per person) lives on the workboard: **[`status/WORKBOARD.md`](../status/WORKBOARD.md)**. Open items
originate in the area status docs (`status/*.md`) and flow to the workboard when Rohan assigns them.

**Status values:** `assigned` → `claimed` → `in-progress` → `in-review` (PR open) → `merged` / `blocked`.

## Who assigns
**Only Rohan assigns work** (moves an open item from a `status/*.md` doc onto the workboard under an owner).
Contributor agents do not self-assign — they build what's under their handle on `status/WORKBOARD.md`.

## Claim protocol (once a task is on the workboard under your handle)
1. Confirm the task row exists under your handle on [`status/WORKBOARD.md`](../status/WORKBOARD.md) with a
   short id (`<area>-<slug>`) and a goal. If it's not there, it's not yours — stop.
2. Write a task brief in `docs/superpowers/plans/<date>-<slug>.md` (use `dev/templates/task-brief.md`) for
   anything Standard-tier or larger.
3. Set the workboard status `claimed` → cut your branch `<handle>/<slug>` off the latest `main`
   (after `bash dev/setup-contributor.sh <handle>`).
4. Drive the lifecycle (`dev/METHODOLOGY.md`): implement → review → verify → Gates 1–5 locally.
5. Open a PR to `main` (status `in-review`). Fill the PR template, including the gate evidence.
6. Rohan's Claude reviews → approves → merges (status `merged`). Then delete your branch.

Don't take two `in-progress` tasks that touch the same files concurrently across contributors — coordinate on
the workboard first to avoid merge pain. When in doubt, smaller PRs, more often.

> The **live tables** (per-person assignments, shared backlog, recently merged) live on
> [`status/WORKBOARD.md`](../status/WORKBOARD.md) — this file is just the rules of the road.
