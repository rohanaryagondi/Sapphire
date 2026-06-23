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
| `quant-fact-seams` | in-progress | Build 4 quantitative-fact Bucket-1 seams in the `aso-tox` pattern. **PR-A gnomAD ✅ merged (#6).** Remaining (one PR each): **GTEx (PR-B, next) → InterPro (PR-C) → g:Profiler (PR-D)**. | next: `hayes/gtex-expression` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md) |

> **Hayes — pilot merged, keep going:** the gnomAD pilot (#6) is in. The pattern is proven and in-repo —
> **use `sapphire-orchestrator/tools/gnomad_constraint_seam.py` as your template** for the rest. Next:
> **GTEx (PR-B)** on branch `hayes/gtex-expression`, one seam per PR, full Gates 1–5 each. Re-read the updated
> brief (it now has template + `syn_z`/`_SOURCE` notes). Blocked? `dev/HELP.md`.

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
| `crossplatform-test-hardening` | rohan/gavin | Fix 3 pre-existing cross-platform test failures Hayes flagged (HELP.md, resolved): moat clone-name test hardcodes `sapphire-capability-map`; `test_scenarios`/`test_trace_view` assume UTF-8 (fail on Windows cp1252). Low-risk: derive the moat suffix from the repo root; add `encoding="utf-8"` + guard the `✓` stdout write. | [dev-harness](dev-harness.md) |

## Recently merged
| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `quant-fact-seams` (PR-A gnomAD) | hayes | 2026-06-23 | PR #6 |
| `repo-streamline` | rohan | 2026-06-23 | PR #5 |
| `status-vision-hardening` | rohan | 2026-06-22 | PR #3 |
| `dev-strict-branch-rules` | rohan | 2026-06-22 | PR #2 |
| `dev-collab-harness` | rohan | 2026-06-22 | PR #1 |
| `aso-tox-sequence-wiring` | rohan | 2026-06-22 | see LEDGER |
