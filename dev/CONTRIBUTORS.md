# Contributors

The people building Sapphire and the Claude each one drives. This is the source of truth for **handles**,
**attribution**, and **who owns what**. Every commit and PR is attributable to exactly one builder.

## Roster

| Handle | Person | GitHub | Drives | Role |
|---|---|---|---|---|
| `rohan` | Rohan Aryagondi | `@rohanaryagondi` | this Claude | **Lead + sole approver/merger** |
| `hayes` | Hayes Stewart | `@HayesStewart-QuiverBS` | their Claude | Contributor (write) |
| `gavin` | Gavin Wong | `@GavinWongYF` | their Claude | Contributor (write) |

> **Canonical repo:** `rohanaryagondi/Sapphire`. `@rohanaryagondi` is the approver/CODEOWNER.
> Hayes and Gavin are repo collaborators with **write** access. On a free GitHub plan there is no server-side
> branch protection, so write access *technically* allows a direct push to `main` — the discipline that keeps
> that from happening is: their agents run **`bash dev/setup-contributor.sh <handle>`** first (installs the
> hooks that block it), obey **`dev/CONTRIBUTOR_RULES.md`**, and never use `--no-verify`. See the enforcement
> model in `dev/CONVENTIONS.md` §1.

## Cold start — from nothing to ready (a contributor's Claude runs this once)

**Repo:** `https://github.com/rohanaryagondi/Sapphire` (private; default branch `main`). Hayes/Gavin are
collaborators with write access. Do this on the contributor's machine before any task:

1. **Auth git to GitHub** (the repo is private). Use the contributor's PAT or `gh auth login`:
   ```
   gh auth login            # OR: git config --global credential.helper + a PAT when prompted on clone
   gh auth status           # confirm authenticated as your @github-user
   ```
2. **Clone into the canonical directory name `sapphire-capability-map`** — NOT `Sapphire`. (A test pins this
   path; cloning into a differently-named dir fails `moat/tests/test_client.py`. Learned the hard way.)
   ```
   git clone https://github.com/rohanaryagondi/Sapphire.git sapphire-capability-map
   cd sapphire-capability-map
   ```
3. **Set your git identity** (so commits attribute correctly; the `Built-By` trailer is added per-commit and
   enforced by the hook):
   ```
   git config user.name  "<Your Name>"
   git config user.email "<your @quiverbioscience.com email>"
   ```
4. **Arm the harness** (installs the pre-commit/commit-msg/pre-push hooks + records your handle):
   ```
   bash dev/setup-contributor.sh <handle>      # <handle> = hayes | gavin
   ```
5. **Windows only:** export `PYTHONUTF8=1` (the codebase assumes UTF-8; without it two tests fail on cp1252).
6. **Tooling for the corpora task:** install the Playwright browser MCP for browser + EMET passes —
   `claude mcp add playwright npx '@playwright/mcp@latest'` then `npx playwright install chromium`. EMET (Pass B)
   needs a signed-in BenchSci session — the agent opens `https://emet.benchsci.com/` and asks its human to sign
   in (or sign up with a `.edu` email); the agent never logs in itself. (See the corpora brief Step 0.)
7. **Run autonomously:** start the watcher and work your queue — `bash dev/watch-assignments.sh <handle> <github-user>`
   (see `dev/CONTRIBUTOR_RULES.md` §Autonomous operation). Your tasks are under your name on `status/WORKBOARD.md`.

You are now ready. Read `dev/CONTRIBUTOR_RULES.md` + your workboard section, then build.

## Session starting prompts (copy-paste)

Two **rohan-driven** session types build Sapphire, separated by *function*. Both use the **hardened harness**
(PR #110): `--no-verify` is forbidden for everyone; the work queue is `dev/work-orders/`; the blueprint is
`docs/plan/`. Paste the matching block to start a fresh session. (`hayes`/`gavin` use the same BUILDER block
with their handle + the cold-start above.)

### Rohan Claude — the BUILDER (handle `rohan`)
Builds work orders on feature branches with subagents. Pushes + opens PRs; **never merges to `main`** — Head
Claude does.

```
You are Rohan Claude — a Sapphire BUILDER (handle: rohan). You build; you do NOT merge to main.
Repo: /Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map (github: rohanaryagondi/Sapphire).

Orient (read in order): CLAUDE.md → sapphire-orchestrator/AGENTS.md → dev/CONTRIBUTOR_RULES.md →
dev/work-orders/README.md (your queue) → docs/plan/README.md (the blueprint) → dev/GATES.md.

Pick a work order from dev/work-orders/ (suggested order is in its README; WO-2 Phase A is the keystone).
Build it on its named feature branch cut from main, via the /sapphire-build lifecycle
(plan→implement→review→verify→ship). Run it with subagents under SEPARATION OF POWERS: the implementer
subagent never reviews or verifies its own work — use a DIFFERENT subagent for the Gate-2 review and the
Gate-5 functional verification. Honesty: label real vs mock, never fabricate, respect the data boundary
(only public IDs leave to external tools; internal moat scores never do). Engine stays stdlib-only.

Ship: all gates green (dev/GATES.md) → push your gated feature branch (you CAN push rohan/* branches; you
must NOT push or merge main) → open a PR, or token-less leave the filled PR body in
dev/reports/rohan/<slug>-report.md for Head Claude to open. NEVER use --no-verify (forbidden for everyone).
Blocked on something you shouldn't guess about? Append to dev/HELP.md and keep working on anything unblocked.
Head Claude reviews + merges your PR.
```

### Head Claude — the APPROVER + lead (handle `rohan`)
Reviews, gates, and merges every PR (including a Rohan Claude builder's); keeps the plan/ledger/workboard
current. Does **not** build feature work.

```
You are Head Claude — the Sapphire APPROVER + lead (handle: rohan). You review/gate/merge; you do NOT build
feature work. Repo: /Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map.

Orient — read FIRST: status/OVERALL.md (the "⏳ Current wave — live handoff" section names the in-flight
PRs/branches, the open decisions, and which branches are stale). Then: CLAUDE.md → docs/plan/README.md
(living blueprint; open decisions in 03) → dev/work-orders/README.md (the active wave) → dev/PR_REVIEW.md +
dev/GATES.md → status/SAPPHIRE_GAPS.md.

For each open contributor PR (hayes/gavin or a Rohan Claude builder branch): gate it in an ISOLATED git
worktree (never disturb the main working tree — a builder may be working there). Run bash dev/run-tests.sh +
the relevant gate checks + an INDEPENDENT review + Gate-5 functional verification (via subagents), and check
provenance / secrets / binaries / the stdlib-engine boundary. Merge (squash, --delete-branch) ONLY if ALL
gates pass; else request changes with specifics and leave it open. Update dev/LEDGER.md + status/WORKBOARD.md
on merge (via a worktree off main, NOT the main tree).

Hardened-harness notes (PR #110): you (the approver) can push main bookkeeping WITHOUT --no-verify — the
pre-push carve-out runs Gate 1 on Python changes and otherwise allows the push; --no-verify stays forbidden
for everyone. The handle is a local git-config value (spoofable), so run `bash dev/audit-history.sh` to catch
any direct-to-main commit before trusting main. `dev/watch-assignments.sh` backs off 90s→600s when idle.

Sweep loop: git fetch; gh pr list --state open AND `git branch -r --no-merged origin/main` (a pushed branch
with NO PR is invisible to `gh pr list` — don't conclude "nothing to do" without this); gate new PRs; answer
new dev/HELP.md requests (+ merge so the asker's watcher unblocks). If nothing's open, do nothing and end
quietly. Wake the human only at a genuine blocker or a data-boundary call.
```

## Ownership (default areas — see `dev/DELEGATION.md` for live assignments)

| Subsystem | Primary | Notes |
|---|---|---|
| Orchestrator engine (`sapphire-orchestrator/`, harness, moat, live_engine) | `rohan` | bedrock; changes reviewed hardest |
| Quiver tools (`tools/`, q-models seams, ASO Design/tox) | `hayes` *(proposed)* | tool integrations via stdlib seams |
| Semantic agents + EMET + scenarios | `gavin` *(proposed)* | Bucket-1 breadth + capture |
| Dev harness (`dev/`), CI, releases | `rohan` | process owner |

Ownership is a default, not a fence — anyone may touch any area through the normal PR flow. The owner is the
expected reviewer-of-record and the person who keeps that area coherent.

## How attribution works (git-native — no in-file tags)

1. **Branch naming:** every working branch is `<handle>/<slug>` — e.g. `hayes/aso-design-tool`,
   `gavin/post-market-safety-capture`. The prefix names the builder at a glance.
2. **Commit trailer:** every commit ends with **both** a `Built-By` line (the human builder) and the
   `Co-Authored-By` line (the Claude that did the work):
   ```
   Built-By: hayes
   Co-Authored-By: Claude <model-used> <noreply@anthropic.com>
   ```
   Use the model id of the session that did the work (e.g. `Claude Opus 4.8`, `Claude Sonnet 4.6`); the stable
   identifier is the `noreply@anthropic.com` email, not the display name. `git log --grep=Built-By` / `git blame`
   then answer "who built this" natively, with no file churn.
3. **Ledger:** each `dev/LEDGER.md` entry records `Built-By: <handle>` and the merging approver.
4. **Reports:** per-contributor under `dev/reports/<handle>/`.

## The one rule that is non-negotiable
**Only `rohan`'s Claude reviews, approves, and merges to `main`.** Contributors run the full local lifecycle
(Gates 1–5) on their branch and **open a PR** — they never merge. See `dev/PR_REVIEW.md` and `dev/GATES.md`.
