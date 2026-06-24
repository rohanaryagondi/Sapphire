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
> **Overnight shift (2026-06-23→24): ✅ COMPLETE** — all 3 worker tasks merged: H (#22), K1 (#24), K2 (#26).
> Backend is now end-to-end-capable: front door serves the live firm (K1) + agents read their corpora at run
> time (K2). Suite 368 green. (Auditor: auto-merged all-green; none held.)

| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `crossplatform-test-hardening` | ✅ merged (#22) | Fixed 3 cross-platform test fails (moat dir-name, cp1252). Suite 343 green. | — | [dev-harness](dev-harness.md) |
| `k1-run-live-service` | ✅ merged (#24) | **Keystone DONE.** `/api/run` now serves the harnessed `run_live` (`via=engine-live`); contract frozen + validated; canned = labeled fallback. Suite 356. | — | [frontend-loka](frontend-loka.md) |
| `k2-corpus-retrieval` | ✅ merged (#26) | **Keystone DONE.** Bucket-1 agents read `corpus/<id>/` at run time; corpus facts land in the dossier (traced, `provenance=corpus`), live path runs the gap. Veto rule intact. Suite 368. | — | [runtime-harness](runtime-harness.md) |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `quant-fact-seams` | ✅ **COMPLETE** | All 4 seams shipped: gnomAD (#6) · GTEx (#9) · InterPro (#11) · g:Profiler (#12). | — | [tools](tools.md) |
| `experiment-design` | **ED-1 in review (PR-E1)** | **Epic.** Port Matt's `design-form-agent` into Sapphire: meeting-notes → filled design sheet. **ED-1 (port + fidelity-lock) shipped** → `tools/experiment_design/` (domain prompt/`MENUS_REFERENCE`/schema verbatim from `vendor/`; `anthropic` in the tool subprocess, engine stays stdlib-only; golden-test vs `vendor/.../sample_extraction_jan6.json`). **Next = ED-2 (fill the design sheet) after ED-1 merges.** | `hayes/experiment-design-port` (PR-E1) | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) |
| `semantic-corpora` (6) | assigned (after experiment-design) | Build dual-source knowledge corpora for **patent-ip · post-market-safety · clinical-trial-registry · payer-market-access · manufacturing-cmc · dea-scheduling** — one PR per agent, per the **locked** method (FDA-memory is the worked example). Self-auth BenchSci for the EMET pass. **Ship your first, wait for review, then batch the rest.** | `hayes/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Hayes — run autonomously** (`dev/CONTRIBUTOR_RULES.md` §Autonomous operation): keep
> `bash dev/watch-assignments.sh hayes HayesStewart-QuiverBS` running (board + HELP + PR-review channels).
> **Status:** `quant-fact-seams` ✅ complete (all 4 seams merged). **Now active: the `experiment-design` epic —
> ED-1 is UNBLOCKED.** Matt's source is vendored at **`vendor/design-form-agent/`** (read its `VENDORED.md`).
> Start ED-1: port into `tools/experiment_design/` per the
> [brief](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) — domain prompt/`MENUS_REFERENCE`/schema
> **verbatim**, deps in the tool subprocess (engine stays stdlib-only), golden-test vs
> `vendor/design-form-agent/sample_extraction_jan6.json`. Don't edit anything under `vendor/`.
> **PR flow:** you now have a PAT → **open your own PRs** (`gh pr create --base main`) and the watcher's
> pr-review channel works. (If `gh` ever fails, the token-less push→approver-opens fallback remains sanctioned.)
> Always branch from the **latest `main`** (`git pull` first; merge `origin/main` if it moves). Blocked? `dev/HELP.md`.

## gavin  (`@GavinWongYF`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `semantic-corpora` (6) | assigned | Build dual-source knowledge corpora for **global-regulatory-divergence · financial-investor · kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional** — one PR per agent, per the **locked** method (FDA-memory is the worked example). Self-auth BenchSci for the EMET pass. **Ship your first, wait for review, then batch the rest.** | `gavin/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Gavin — first task, start here:** (1) `bash dev/setup-contributor.sh gavin` (installs the hooks). (2) Read
> `dev/CONTRIBUTOR_RULES.md` (esp. §Autonomous operation) + the
> [corpora brief](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) + study the worked
> example `sapphire-orchestrator/corpus/fda-institutional-memory/` and its `METHOD.md`. (3) Start the watcher:
> `bash dev/watch-assignments.sh gavin GavinWongYF`. (4) Build your **first** corpus (suggest
> `global-regulatory-divergence`), open the PR, and **wait for Rohan's review before batching the rest**.
> Self-authenticate `emet.benchsci.com` for the EMET pass. Blocked? post in `dev/HELP.md`.

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
| `quant-fact-seams` (PR-D g:Profiler — series ✅ COMPLETE) | hayes | 2026-06-23 | PR #12 |
| `quant-fact-seams` (PR-C InterPro) | hayes | 2026-06-23 | PR #11 |
| `autonomous-contributors` | rohan | 2026-06-23 | PR #10 |
| `quant-fact-seams` (PR-B GTEx) | hayes | 2026-06-23 | PR #9 |
| `quant-fact-seams` (PR-A gnomAD) | hayes | 2026-06-23 | PR #6 |
| `repo-streamline` | rohan | 2026-06-23 | PR #5 |
| `status-vision-hardening` | rohan | 2026-06-22 | PR #3 |
| `dev-strict-branch-rules` | rohan | 2026-06-22 | PR #2 |
| `dev-collab-harness` | rohan | 2026-06-22 | PR #1 |
| `aso-tox-sequence-wiring` | rohan | 2026-06-22 | see LEDGER |
