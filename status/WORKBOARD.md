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
| `frontend-and-data-planes` (B: front end) | **🔨 next** | **Feature, work-stream B.** Fork LOKA's Chainlit UI into `frontend/` (real LOKA repo untouched) as our **transparent front end** wired to `live_engine.run_live`: show the actual tools/agents + full firm process (plan→Bucket-1 per-agent→dossier→roundtable spread→synthesis) so we can see what's doing well and what isn't; render the two planes distinctly. Retires `site/`. | `rohan/frontend-loka-fork` (next) | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-24-sapphire-frontend-and-data-planes.md) |
| `frontend-and-data-planes` (A: data planes) | **✅ reviewed+verified, shipping** | **Work-stream A DONE.** Two enforced data planes: `plane_for()` maps every provenance → internal (moat) / external (EMET·web·Q-Models·seams·corpus) with a bidirectional import-time totality guard; `is_boundary_violation()` (fail-safe) + honest 2-layer docs (runtime `data_boundary()` key/pattern enforcer, shared w/ public-only memory; plane map = classification layer); every dossier fact carries a derived `plane` (additive in `run_live_schema`). Gate 2 ✅ (fix-looped) · Gate 5 ✅ (core) · suite 434. | `rohan/frontend-data-planes` | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-24-sapphire-frontend-and-data-planes.md) |
| `loka-integration-plan` | ✅ merged (#34) | Analyzed LOKA source (read-only), wrote plan + `/api/run` wire contract + open questions; data-boundary ruled (separate planes). | — | [frontend-loka](frontend-loka.md) |
| `crossplatform-test-hardening` | ✅ merged (#22) | Fixed 3 cross-platform test fails (moat dir-name, cp1252). Suite 343 green. | — | [dev-harness](dev-harness.md) |
| `k1-run-live-service` | ✅ merged (#24) | **Keystone DONE.** `/api/run` now serves the harnessed `run_live` (`via=engine-live`); contract frozen + validated; canned = labeled fallback. Suite 356. | — | [frontend-loka](frontend-loka.md) |
| `k2-corpus-retrieval` | ✅ merged (#26) | **Keystone DONE.** Bucket-1 agents read `corpus/<id>/` at run time; corpus facts land in the dossier (traced, `provenance=corpus`), live path runs the gap. Veto rule intact. Suite 368. | — | [runtime-harness](runtime-harness.md) |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `quant-fact-seams` | ✅ **COMPLETE** | All 4 seams shipped: gnomAD (#6) · GTEx (#9) · InterPro (#11) · g:Profiler (#12). | — | [tools](tools.md) |
| `experiment-design` | **ED-1 ✅ merged (#28); ED-2 in review (PR-E2)** | **Epic.** Port Matt's `design-form-agent` → filled design sheet. **ED-1 done** (`tools/experiment_design/`, domain content verbatim from `vendor/`, golden-locked, engine stdlib-only). **ED-2 built (PR-E2): `fill.py` → filled design sheet** — form-ready JSON + design-doc MD (per-field provenance) + **menu validation** (off-menu dropdown values flagged vs `MENUS_REFERENCE`, never silently written); pure local transform, stdlib-only, suite 404. Real `.xlsx` writer = documented pending seam (HELP: `experiment-design-ed2-xlsx-template`). Then your 6 semantic corpora. | `hayes/experiment-design-ed2` (PR-E2) | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) |
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
| `semantic-corpora` (6) | **1/6 ✅ merged (#30); 5 to go** | ~~global-regulatory-divergence ✅~~ · **financial-investor · kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional** — one PR per agent, per the **locked** method. First corpus reviewed + merged (gate CLEAN, suite 381) — **method proven; batch the remaining 5.** Self-auth BenchSci for the EMET pass. | `gavin/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Gavin — first corpus ✅ merged (#30); now batch the remaining 5.** The method is proven end-to-end (your
> dual-source build passed the gate + content audit clean). Keep the watcher running
> (`bash dev/watch-assignments.sh gavin GavinWongYF`). For each of the remaining 5
> (financial-investor · kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional):
> branch from the **latest `main`** (`git pull` first), build per the locked
> [METHOD](../sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md), run
> `bash dev/validate-corpus.sh sapphire-orchestrator/corpus/<agent>` + `bash dev/run-tests.sh` until both green,
> then open the PR. You can now run these in parallel (one PR each). Need a regulator/source added to the T1
> allowlist? `dev/HELP.md` (don't edit the gate). Self-auth `emet.benchsci.com` for the EMET pass.

---

## Shared backlog (unassigned — Rohan assigns from here)
Pulled from `status/OVERALL.md` open items. To assign: move a row into a person's section above, set status
`assigned`, and link a brief in `docs/superpowers/plans/`.

| Task id | Suggested owner | Goal | Area |
|---|---|---|---|
| ~~`frontdoor-wire-run-live`~~ | rohan | ✅ Folded into `frontend-and-data-planes` (active above) — the new `frontend/` connects directly to `run_live`; `serve.py /api/run` already serves it (K1). | [frontend-loka](frontend-loka.md) |
| `aso-design-tool` | hayes | Build the ASO Design tool; feed designed sequences into the `aso-tox` `sequences=` channel | [tools](tools.md) |
| `scenario-coverage` | gavin | Broaden captured scenario coverage across the 10-axis variety matrix | [engine](engine.md) |
| `retire-mocks` | — | Audit + honestly label/retire remaining mock surfaces | [tools](tools.md) |
| `chronic-tox` | hayes | Scope + integrate the chronic-tox model (roadmap) | [tools](tools.md) |
| `crossplatform-test-hardening` | rohan/gavin | Fix 3 pre-existing cross-platform test failures Hayes flagged (HELP.md, resolved): moat clone-name test hardcodes `sapphire-capability-map`; `test_scenarios`/`test_trace_view` assume UTF-8 (fail on Windows cp1252). Low-risk: derive the moat suffix from the repo root; add `encoding="utf-8"` + guard the `✓` stdout write. | [dev-harness](dev-harness.md) |

## Recently merged
| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `semantic-corpora` (global-regulatory-divergence — Gavin's 1st corpus) | gavin | 2026-06-24 | PR #30 |
| `loka-integration-plan` · overnight auditor report | rohan | 2026-06-24 | PRs #33/#34 |
| `experiment-design` (ED-1 port) | hayes | 2026-06-24 | PR #28 |
| overnight: `crossplatform-test-hardening` (#22) · `k1-run-live-service` (#24) · `k2-corpus-retrieval` (#26) | rohan | 2026-06-24 | PRs #22/#24/#26 |
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
