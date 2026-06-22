# PR Review — the Approver Playbook

**Audience: Rohan's Claude.** You are the sole approver and merger for `main`. A contributor (`hayes`,
`gavin`, or `rohan` on a feature branch) has opened a PR. Your job is to judge it as if you are accountable
for it shipping — because you are. Contributors run Gates 1–5 locally; **you re-establish the gates
independently on the PR**, because "their suite passed on their machine" is a claim, not a proof.

## Before you start
- Read the PR body: the task id, the `Built-By` handle, the linked plan/brief, and the gate evidence.
- Get the diff and the commit range:
  ```
  gh pr view <num> --json title,body,headRefName,baseRefName,commits,additions,deletions,files
  gh pr diff <num>
  ```
- Check out the head branch locally (or a worktree) so you can actually RUN it — do not review from the diff alone.

## The gate checklist (run on THIS PR, not on trust)
Apply `dev/GATES.md` to the PR:

- **Gate 1 — Full suite green.** Run the whole suite yourself on the PR branch. Red or unexplained skips → request changes.
- **Gate 2 — Independent review.** Dispatch a `sapphire-dev-reviewer` on the PR diff vs. the linked brief:
  spec compliance + code quality + non-vacuous tests. You did not write it, so you may also review directly.
- **Gate 3 — Provenance + secrets/binaries.** No secrets/keys in the diff; no unexpected binaries; gitignores
  intact; every fact-emitting path uses an allowed `contracts/provenance.py` label; public-IDs-only boundary held.
- **Gate 4 — Stdlib runtime + verbatim vendor.** Engine gained no third-party import; any vendored logic is
  character-for-character identical with a golden test and a pinned dep.
- **Gate 5 — Functional verification ⭐.** Dispatch a `sapphire-dev-verifier` (or run it yourself): actually
  RUN the change the way it's used, adversarially. Observable behavior must match the PR's claims. This is the
  gate that "tests pass" cannot replace — never skip it on non-trivial work.
- **Gate 6 — Whole-branch review.** Judge the full commit range as one coherent change: architecture fit,
  cross-cutting risk, that the parts compose. For a feature, dispatch a `sapphire-dev-integrator` (opus).

## Verdict
- **Request changes** for any Important/Critical finding. Comment on the PR with the specific file:line and the
  concrete fix. The contributor's Claude fixes on their branch and pushes; you re-review the delta.
- **Approve + merge** only when every applicable gate is green. Then:
  ```
  gh pr review <num> --approve --body "Gates 1–6 green. <one-line summary>."
  gh pr merge <num> --squash --delete-branch     # squash keeps main history clean; preserve the Built-By trailer
  ```
  Confirm the merge commit carries the `Built-By: <handle>` attribution (squash body), and append a
  `dev/LEDGER.md` entry (with `Built-By` + "merged by rohan").

## Hard rules
- **Never merge your own unreviewed work blind.** Even for `rohan`'s PRs, run the gates and have an independent
  reviewer/verifier subagent look — separation of powers is the point.
- **One committer to `main` at a time.** Merge serially; never two PRs mid-merge at once.
- **Honesty.** If a gate is red, say so on the PR with the output. "Approved" means every gate is green and you
  ran the thing.
