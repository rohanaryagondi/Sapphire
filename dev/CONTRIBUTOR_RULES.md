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
   stop and ask rohan; do not route around it.
6. **Never touch the approver's machinery**: `.github/CODEOWNERS`, `.githooks/`, `dev/PR_REVIEW.md`,
   `dev/run-tests.sh`, `dev/audit-history.sh`, `dev/setup-contributor.sh`. If a change there is needed,
   propose it in a PR and let rohan decide.
7. **Stay in your lane / the brief.** Find your assigned work on the **workboard** (`status/WORKBOARD.md`),
   write a brief, and build only that. Run the full local lifecycle (Gates 1–5, `dev/GATES.md`) before opening
   the PR; paste the evidence into the PR template. (The pre-push hook also runs the suite when you change
   Python — but don't rely on it; run the gates yourself.)
8. **Honor every other convention** in `dev/CONVENTIONS.md` (stdlib-only runtime, provenance labels, public
   identifiers only, no secrets/binaries, real non-vacuous tests). The data boundary is absolute.

## How you ship (the only path)
```
bash dev/setup-contributor.sh hayes         # once
git checkout main && git pull
git checkout -b hayes/<slug>
# ...build test-first, run Gates 1–5 locally...
git commit            # message must include  Built-By: hayes
git push -u origin hayes/<slug>             # hook allows this; blocks main + wrong prefixes
gh pr create --base main                    # fill the PR template with gate evidence
# then STOP. rohan's Claude reviews, approves, and merges. You do not merge.
```

## Why hard rules and not just "please"
Three agents editing one long-term codebase diverge fast without a single chokepoint. The chokepoint is: all
change lands on `main` only through a PR that one reviewer (rohan's Claude) has independently gated. Everything
here exists to keep that chokepoint intact. On the current GitHub plan the server can't *force* it, so the
hooks + your discipline are the enforcement. Treat them as if they were force.
