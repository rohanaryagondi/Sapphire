# Contributor Rules — for Hayes's and Gavin's agents (and any non-approver)

**Read this before you touch the repo.** These are hard rules, not guidance. They are enforced by
client-side git hooks, a GitHub Actions backstop, CODEOWNERS, and — above all — by you, the agent, obeying
them. The repo is `rohanaryagondi/Sapphire`. The sole approver/merger is **rohan**.

## First thing, once per clone
```
bash dev/setup-contributor.sh <handle>      # handle is hayes or gavin
```
This wires the hooks (`core.hooksPath=.githooks`) and records `sapphire.handle`. If you skip it, your pushes
are unguarded and you will violate the rules below — so don't skip it.

## The rules (non-negotiable)
1. **Never push to `main`.** Not directly, not force, not ever. `main` changes only through a PR that **rohan**
   merges. The pre-push hook blocks it locally, and `dev/audit-history.sh` catches it after the fact.
2. **Never merge a PR** — not yours, not anyone's. Only rohan's Claude approves and merges. You open the PR
   and stop.
3. **One branch shape only: `<handle>/<slug>`** cut from the latest `main` (e.g. `hayes/aso-design-tool`).
   No other branch names. You may only push branches with **your own** handle prefix.
4. **Every commit carries `Built-By: <handle>`** + the Claude `Co-Authored-By` trailer. The commit-msg hook
   rejects commits without it.
5. **Never use `--no-verify`** (or otherwise disable/edit the hooks). Bypassing a guardrail is the most
   serious violation here — it defeats the whole model. If a hook blocks something you believe is legitimate,
   stop and ask rohan; do not route around it. **The approver (rohan) no longer needs `--no-verify` for
   post-merge main bookkeeping** — the `pre-push` hook now includes an approver carve-out that lets rohan
   push to `main` directly (Gate 1 still runs when Python files are included), so `--no-verify` is
   genuinely forbidden for everyone, including rohan. That carve-out is **convenience, not enforcement**:
   it keys on a local, spoofable `git config` handle, so it does not actually stop a contributor from
   pushing to main — `dev/audit-history.sh` is the detective backstop that flags any non-PR commit on
   main (a spoofed direct push) after the fact.
6. **Never touch the approver's machinery**: `.github/CODEOWNERS`, `.githooks/`, `dev/PR_REVIEW.md`,
   `dev/run-tests.sh`, `dev/audit-history.sh`, `dev/setup-contributor.sh`. If a change there is needed,
   propose it in a PR and let rohan decide.
7. **Stay in your lane / the brief.** Find your assigned work on the **workboard** (`status/WORKBOARD.md`),
   write a brief, and build only that. Run the full local lifecycle (Gates 1–5, `dev/GATES.md`) before opening
   the PR; paste the evidence into the PR template. (The pre-push hook also runs the suite when you change
   Python — but don't rely on it; run the gates yourself.)
8. **Honor every other convention** in `dev/CONVENTIONS.md` (stdlib-only runtime, provenance labels, public
   identifiers only, no secrets/binaries, real non-vacuous tests). The data boundary is absolute.
9. **When blocked, ask — don't guess.** If the brief, `dev/CONVENTIONS.md`, `dev/GATES.md`, and the code don't
   answer it — especially anything touching a contract/schema, the harness, the data boundary, or a gate you
   can't explain — post a request in **`dev/HELP.md`** and signal it (PR comment, or have your operator relay
   to Rohan). Guessing on the harness/contracts is how silent regressions happen (see the aso-tox schema
   lesson). Keep working on anything not blocked while you wait.

## How you ship (the only path)
```
bash dev/setup-contributor.sh hayes         # once
git checkout main && git pull               # ALWAYS branch from the LATEST main
git checkout -b hayes/<slug>
# ...build test-first, run Gates 1–5 locally...
git commit            # message must include  Built-By: hayes
# if main moved while you worked:  git fetch origin && git merge origin/main  (resolve, re-test)
git push -u origin hayes/<slug>             # hook allows this; blocks main + wrong prefixes
gh pr create --base main                    # open the PR yourself IF you have gh/a token (see below)
# then wait for rohan's Claude to review. Address change-requests on the same branch + push.
# rohan's Claude approves and merges. You never merge.
```
Two musts that have slipped before: **(1) branch from the latest `main`** (and merge `origin/main` in if it
moves) — stale branches cause merge conflicts the approver has to clean up; **(2) get your branch in front of
the approver**:
- **If you have `gh`/a token:** open the PR yourself (`gh pr create --base main`) — don't just push and stop.
- **If your environment has no `gh`/token** (e.g. a sandboxed Windows box — see the resolved HELP entry): this
  is the **sanctioned token-less flow** — push the fully-gated `hayes/<slug>` branch and put the complete PR
  body in `dev/reports/hayes/<slug>-report.md`; the approver opens + reviews + merges. Your board watcher will
  see the merge (workboard bump) and cue your next task. This is not a workaround — it's a supported path.

## Autonomous operation — run without being prompted
Contributor agents are expected to **run continuously**, not one task at a time. After setup, start the
watcher and enter the loop:

```
bash dev/setup-contributor.sh <handle>                       # once per clone
# launch as a background Monitor (it emits an event when there's something to act on):
bash dev/watch-assignments.sh <handle> <github-username>
```

The watcher (`dev/watch-assignments.sh`) watches **two channels on `origin/main`** + **your open PRs**:
- **`status/WORKBOARD.md`** — a new/updated task under your handle, or (when the approver merges your PR) the
  cue to start the next one.
- **`dev/HELP.md`** — an **answer** to one of your HELP requests (the approver fills the request's *Answer*
  field and merges it to `main`). This is how you get unblocked automatically.
- **your open PRs** — a new review/comment from the approver (address change-requests, or proceed if approved).

**The loop (repeat forever, no human input):**
1. `git pull origin main`; read `status/WORKBOARD.md` (your section) + `dev/HELP.md` (answers to your requests).
2. If a HELP request of yours was answered → act on the answer (unblock).
3. If there's a pending task and nothing blocking → build it through the full lifecycle above (branch → gates →
   open PR), then keep watching.
4. If the approver reviewed your PR → address change-requests on the same branch + push; if approved, the
   approver merges and the workboard signal will cue your next task.
5. If you're blocked → post a HELP request (commit it), keep working on anything not blocked, and **wait for
   the watcher to signal the answer** — don't stop the session.
6. If there's no pending work → idle; the watcher will wake you when the approver assigns something.

You only ever truly stop if explicitly told to. Blocked ≠ stopped — you ask via HELP and keep watching.

## Why hard rules and not just "please"
Three agents editing one long-term codebase diverge fast without a single chokepoint. The chokepoint is: all
change lands on `main` only through a PR that one reviewer (rohan's Claude) has independently gated. Everything
here exists to keep that chokepoint intact. On the current GitHub plan the server can't *force* it, so the
hooks + your discipline are the enforcement. Treat them as if they were force.
