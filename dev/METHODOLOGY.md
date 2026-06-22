# Methodology — How We Build Sapphire

A self-contained, subagent-driven development (SDD) lifecycle. Owned in-repo; no external plugin required.

## The actors

| Role | Backed by | Model | Responsibility |
|---|---|---|---|
| **Controller** | the main Claude loop (or human lead) | — | Owns the engagement. Decomposes work, dispatches builder agents, holds the gates, keeps its own context lean. Does not hand-write feature code when it can delegate. |
| **Planner** | `.claude/agents/sapphire-dev-planner` | opus | Turns a goal into a sequenced plan of small, independently-verifiable tasks with explicit Definition of Done. |
| **Implementer** | `.claude/agents/sapphire-dev-implementer` | sonnet | Builds ONE task, test-first, and self-tests. Stays inside the brief — no scope creep. |
| **Reviewer** | `.claude/agents/sapphire-dev-reviewer` | sonnet | Independent spec-compliance + code-quality review of one task's diff. Never reviews its own work. |
| **Verifier** | `.claude/agents/sapphire-dev-verifier` | sonnet (controller overrides to opus for critical paths) | **Functional gate**: actually *runs* the change, adversarially, and asks "does this really work?" Surfaces fixes. |
| **Integrator** | `.claude/agents/sapphire-dev-integrator` | opus | Whole-branch review before a feature ships; resolves the ledger; performs the gated commit/push. |

Reviewer ≠ Implementer ≠ Verifier — separation of powers is mandatory. The controller may also run an **opus whole-branch review** directly for a feature-sized change.

## The lifecycle

```
0. FRAME      Controller states the goal + success criteria. Confirm scope with the human if it's a real fork.
1. PLAN       Planner → a task list (each task small enough to review in one diff) + per-task DoD.
2. BRIEF      Per task: a TASK-BRIEF (templates/task-brief.md) — what, why, constraints, DoD, files.
3. IMPLEMENT  Implementer builds the task test-first; runs the focused tests; writes a short report.
4. REVIEW     Reviewer reads ONLY that task's diff (review package) → spec + quality verdict.
5. FIX        Controller dispatches fixes for Important/Critical findings; re-review if needed.
6. VERIFY     Verifier RUNS the change end-to-end, tries to break it, confirms it does what it claims.
              Anything that doesn't actually work → back to FIX. (This gate is non-negotiable — see GATES.md.)
7. (repeat 2–6 per task)
8. BRANCH     When the feature is complete: WHOLE-BRANCH REVIEW (opus) over the full range.
9. PR         Open a PR `<handle>/<slug>` → `main`, filling the PR template with the Gate 1–5 evidence.
10. APPROVE   Rohan's Claude re-establishes the gates on the PR + runs Gate 6 (PR_REVIEW.md), then merges to
              `main`, deletes the branch, and appends the dev/LEDGER.md entry (Built-By + merged by rohan).
```

Contributors do steps 1–9 on their own branch; **only Rohan's Claude does step 10** (approve + merge). A
contributor never merges their own PR.

`pipeline` it when you can: a task can be in VERIFY while the next is still in IMPLEMENT. But **merges are
serialized** — Rohan's Claude merges one PR at a time (cloud/file-system git locks bite otherwise).

## Tiers (right-size the ceremony)

Not every change needs the full lifecycle. Pick the tier by blast radius:

- **Trivial** (typo, comment, doc line): controller edits directly → tests green → commit. No subagents.
- **Standard** (a function, a bugfix, a small module): BRIEF → IMPLEMENT → REVIEW → VERIFY → gates.
- **Feature** (a new subsystem, a tool integration, a wiring change): full lifecycle incl. PLAN + WHOLE-BRANCH REVIEW.

When unsure, go one tier heavier. The cost of a wasted review is small; the cost of a silent regression in a long-term build is not.

## Working with subagents (controller discipline)

- **Delegate heavy reads.** Hand a subagent the file/diff/zip; keep the conclusion, not the bytes.
- **Precise briefs.** Give exact paths, exact constraints, exact DoD, and the verbatim code to preserve when wrapping vendored logic. Vague briefs produce scope creep.
- **One committer at a time.** Launch reviewers/verifiers (read-only) in parallel freely; serialize anything that commits.
- **Trust nothing unverified.** A subagent's report is a claim. The Reviewer and Verifier exist to check claims, including the controller's.
- **Models:** sonnet for implement/review/verify; opus for plan, architecture, and whole-branch review. Omit a model override only when inheriting the session model is clearly right.

## Plans live in the repo

Feature plans go in `docs/superpowers/plans/<date>-<slug>.md` (existing convention) or `dev/plans/`. A plan is a contract: the Reviewer checks the diff against it. (Plans live in `docs/superpowers/plans/`; create the dir if it's a fresh repo.)
