# Workboard

**Where each contributor's agent finds its pending work.** One section per person. If a task isn't here under
your handle, it isn't yours to start. This is the live assignment state; the *protocol* for claiming/assigning
is `dev/DELEGATION.md`, and the *lifecycle* for building is `dev/METHODOLOGY.md`.

**Status values:** `assigned` → `claimed` → `in-progress` → `in-review` (PR open) → `merged` / `blocked`.

> **For Hayes's and Gavin's agents:** you currently have **no assigned work** — do not start anything yet.
> First time in the repo, run `bash dev/setup-contributor.sh <handle>` and read `dev/CONTRIBUTOR_RULES.md`.
> When Rohan assigns you a task it will appear under your section below with a brief link. Wait for it.

---

## rohan  (`@rohanaryagondi`) — lead + approver
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| _none in progress_ | — | (approver: review Hayes's quant-fact-seams PRs) | — | — |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `quant-fact-seams` | assigned | Build 4 quantitative-fact Bucket-1 seams — **gnomAD constraint, GTEx expression, InterPro domains, g:Profiler enrichment** (clean public APIs, no keys) — in the `aso-tox` seam pattern. **Pilot-gate: ship gnomAD first (PR-A), wait for merge, then one PR per remaining seam.** | `hayes/gnomad-constraint` (PR-A) | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md) |

> **Hayes — start here:** (1) `bash dev/setup-contributor.sh hayes`  (2) read `dev/CONTRIBUTOR_RULES.md` +
> the [brief](../docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md) in full  (3) build **only**
> `gnomad-constraint` first, open PR-A to `main`, stop and wait for Rohan's review. Stuck on the harness or a
> contract? Post in `dev/HELP.md` — don't guess.

## gavin  (`@GavinWongYF`) — contributor
_No work assigned yet._

---

## Shared backlog (unassigned — Rohan assigns from here)
Pulled from `status/OVERALL.md` open items. To assign: move a row into a person's section above, set status
`assigned`, and link a brief in `docs/superpowers/plans/`.

| Task id | Suggested owner | Goal | Area |
|---|---|---|---|
| `frontdoor-wire-run-live` | rohan | Wire `run_live` into `serve.py`/Console — replace the canned path (the keystone) | [engine](engine.md) |
| `aso-design-tool` | hayes | Build the ASO Design tool; feed designed sequences into the `aso-tox` `sequences=` channel | [tools](tools.md) |
| `scenario-coverage` | gavin | Broaden captured scenario coverage across the 10-axis variety matrix | [engine](engine.md) |
| `retire-mocks` | — | Audit + honestly label/retire remaining mock surfaces | [tools](tools.md) |
| `chronic-tox` | hayes | Scope + integrate the chronic-tox model (roadmap) | [tools](tools.md) |

## Recently merged
| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `status-vision-hardening` | rohan | 2026-06-22 | PR #3 |
| `dev-strict-branch-rules` | rohan | 2026-06-22 | PR #2 |
| `dev-collab-harness` | rohan | 2026-06-22 | PR #1 |
| `aso-tox-sequence-wiring` | rohan | 2026-06-22 | see LEDGER |
