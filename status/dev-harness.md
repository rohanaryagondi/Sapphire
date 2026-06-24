# Status — Dev / Build Harness

*The system we use to build Sapphire (not part of the product). Updated 2026-06-22.* Code: `dev/`,
`.githooks/`, `.github/`, build agents `.claude/agents/sapphire-dev-*`, skill `sapphire-build`.

## State
- ✅ **3-contributor, PR-gated harness.** rohan (lead + sole approver) · hayes · gavin, each driving their own
  Claude. Branch off `main` as `<handle>/<slug>`; ship via PR; **only Rohan's Claude reviews + merges.**
- ✅ **Git-native attribution:** branch prefix + `Built-By` trailer + `dev/CONTRIBUTORS.md`.
- ✅ **Local enforcement** (repo stays free — no branch protection, no Actions):
  - `.githooks/pre-commit` — secret scanner.
  - `.githooks/commit-msg` — requires `Built-By` matching the clone's handle (parsed via `git
    interpret-trailers`).
  - `.githooks/pre-push` — blocks main/wrong-branch pushes; **runs the full suite when Python changes** (Gate
    1) and blocks on red.
  - `dev/setup-contributor.sh <handle>` arms all of the above; `dev/run-tests.sh` is the Gate-1 runner;
    `dev/audit-history.sh` is the detective backup (`Built-By` coverage + secret scan over history).
  - `.github/CODEOWNERS` routes review; `dev/CONTRIBUTOR_RULES.md` binds the contributor agents.
- ✅ Lifecycle + gates: `dev/METHODOLOGY.md`, `dev/GATES.md`, `dev/PR_REVIEW.md`, `dev/LEDGER.md`,
  `dev/templates/`.
- ✅ Work tracking: `status/WORKBOARD.md` (assignments) ↔ `dev/DELEGATION.md` (protocol).

## Open items
- None. Enforcement is **local-and-permanent by decision** (no GitHub Pro): hooks + CODEOWNERS + audit are the
  complete model — there is no server-side branch-protection layer coming. Don't reintroduce "pending Pro" language.

## Watch-outs
- Hooks are **per-clone** — a contributor who skips `setup-contributor.sh` or uses `--no-verify` bypasses
  everything. Mitigations: `CONTRIBUTOR_RULES.md` (hard rule) + run `dev/audit-history.sh` before trusting
  `main`. This is the accepted residual risk of a free repo.
- Keep the **product vs. build** distinction clean: a "reviewer" here judges code; a "reviewer" persona in the
  runtime judges a drug program.
