---
name: sapphire-build
description: Run the Sapphire dev lifecycle for a build task — plan → implement → review → verify → ship, with the mandatory quality gates. Use when building/changing Sapphire itself (the engine, harness, tools, scenarios). This is the BUILD process, distinct from the product runtime skills (/sapphire, emet-runner).
---

# Building Sapphire — the dev lifecycle

You are the **controller** for a Sapphire build task. Drive it through the lifecycle in `dev/METHODOLOGY.md`, enforce the gates in `dev/GATES.md`, and obey `dev/CONVENTIONS.md`. Read those three files if you haven't this session.

This skill is for building **Sapphire the product**. It is NOT a product runtime skill — don't confuse the dev `reviewer/verifier` (judging code) with the runtime personas (judging drug programs).

## Steps

1. **Frame.** State the goal and observable success criteria. If there's a genuine fork (scope, approach, a missing input), ask the human before building — don't guess.

2. **Tier it** (`dev/METHODOLOGY.md`): Trivial → edit + Gate 1 + commit. Standard → brief → implement → review → verify → gates. Feature → add PLAN (`sapphire-dev-planner`) + whole-branch review (`sapphire-dev-integrator`). When unsure, go one tier heavier.

3. **Per task:**
   - Write a brief from `dev/templates/task-brief.md`.
   - Dispatch **`sapphire-dev-implementer`** (sonnet) to build it test-first.
   - Dispatch **`sapphire-dev-reviewer`** (sonnet, a *different* agent) with `dev/templates/review-prompt.md` → Gate 2. Fix Important/Critical findings; re-review.
   - Dispatch **`sapphire-dev-verifier`** with `dev/templates/verify-prompt.md` → **Gate 5**: it RUNS the change adversarially and proves it actually works. Anything that doesn't → fix loop → re-verify.

4. **Gates** (`dev/GATES.md`) before any commit/push: full suite green (1), independent review Approved (2), provenance + no secrets/binaries (3), stdlib-runtime + verbatim-vendor (4), functional verification (5). Feature tier adds whole-branch review (6).

5. **Ship.** Append a `dev/LEDGER.md` entry, make the conventional commit (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer), `git push origin Rohan`. For a feature, let **`sapphire-dev-integrator`** run the whole-branch review + gated ship.

## Controller discipline (`dev/CONVENTIONS.md` §7)
- Delegate heavy reads to subagents; keep your context lean.
- Run read-only reviewers/verifiers in parallel; **serialize anything that commits** (git locks).
- Separation of powers: the implementer never reviews or verifies its own work.
- Report faithfully — "done" means done AND verified.

## The non-negotiable
Gate 5 (functional verification) is never skipped on non-trivial work. "The tests pass" is not "it works." Run the real thing, try to break it, then ship.
