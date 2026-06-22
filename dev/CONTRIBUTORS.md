# Contributors

The people building Sapphire and the Claude each one drives. This is the source of truth for **handles**,
**attribution**, and **who owns what**. Every commit and PR is attributable to exactly one builder.

## Roster

| Handle | Person | GitHub | Drives | Role |
|---|---|---|---|---|
| `rohan` | Rohan Aryagondi | `@rohanaryagondi` | this Claude | **Lead + sole approver/merger** |
| `hayes` | Hayes | `@TBD` *(confirm)* | their Claude | Contributor |
| `gavin` | Gavin | `@TBD` *(confirm)* | their Claude | Contributor |

> GitHub usernames for Hayes and Gavin are placeholders until confirmed. They must be added as repo
> collaborators (write access) before they can push feature branches / open PRs.

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
