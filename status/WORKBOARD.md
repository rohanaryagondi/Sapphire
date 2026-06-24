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
| `frontend-and-data-planes` | ✅ **COMPLETE (A #37 + B #41)** | **Feature DONE.** A: two enforced data planes (`plane_for`, fail-safe boundary rule, derived `plane` on every fact). B: **transparent front end** — `frontend/` forks LOKA's Chainlit app (real repo untouched), re-points to in-process `live_engine.run_live`, renders the full firm process (plan→per-agent→dossier split by **two distinct planes**→roundtable **spread**→synthesis→partial-run banner); Demo + Live profiles; engine stays stdlib. Gate 2 ✅ + Gate 5 ✅ (PASS — bridge hits real engine, planes zero cross-contamination, app launches). Suite **463**. `site/` superseded. | — | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-24-sapphire-frontend-and-data-planes.md) |
| `loka-integration-plan` | ✅ merged (#34) | Analyzed LOKA source (read-only), wrote plan + `/api/run` wire contract + open questions; data-boundary ruled (separate planes). | — | [frontend-loka](frontend-loka.md) |
| `crossplatform-test-hardening` | ✅ merged (#22) | Fixed 3 cross-platform test fails (moat dir-name, cp1252). Suite 343 green. | — | [dev-harness](dev-harness.md) |
| `k1-run-live-service` | ✅ merged (#24) | **Keystone DONE.** `/api/run` now serves the harnessed `run_live` (`via=engine-live`); contract frozen + validated; canned = labeled fallback. Suite 356. | — | [frontend-loka](frontend-loka.md) |
| `k2-corpus-retrieval` | ✅ merged (#26) | **Keystone DONE.** Bucket-1 agents read `corpus/<id>/` at run time; corpus facts land in the dossier (traced, `provenance=corpus`), live path runs the gap. Veto rule intact. Suite 368. | — | [runtime-harness](runtime-harness.md) |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `robyn-scs-endpoint-wiring` | **🔨 assigned (DO THIS NEXT)** | **Standard.** Wire up callable endpoints for the vendored `robyn_scs` SCS/STA pipeline (`vendor/robyn_scs/`, Robyn gave full permission). Build `tools/robyn_scs/` (endpoints.py + README + wiring test) that exposes the ~8 operations by calling the vendored `utils/` code correctly — **don't modify `vendor/`, don't run the full pipeline** (verify by import + `inspect.signature`, optional cheap synthetic call). Engine stays stdlib-only (heavy deps stay in the tool). | `hayes/robyn-scs-endpoints` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-24-robyn-scs-endpoint-wiring.md) |
| `quant-fact-seams` | ✅ **COMPLETE** | All 4 seams shipped: gnomAD (#6) · GTEx (#9) · InterPro (#11) · g:Profiler (#12). | — | [tools](tools.md) |
| `experiment-design` | ✅ **ED-1 (#28) + ED-2 (#36) merged** | **Epic done.** Port Matt's `design-form-agent` → filled design sheet. `tools/experiment_design/` (extract.py + fill.py), vendor-verbatim, golden-locked, stdlib-only. Follow-up nit (next ED push): add `scan_direction`/`addition_protocol` to `_MENU_FIELDS` validation. | — | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) |
| `semantic-corpora` (6) | assigned (after robyn-scs) | Build dual-source knowledge corpora for **patent-ip · post-market-safety · clinical-trial-registry · payer-market-access · manufacturing-cmc · dea-scheduling** — one PR per agent, per the **locked** method (FDA-memory is the worked example). Self-auth BenchSci for the EMET pass. **Ship your first, wait for review, then batch the rest.** | `hayes/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Hayes — run autonomously** (`dev/CONTRIBUTOR_RULES.md` §Autonomous operation): keep
> `bash dev/watch-assignments.sh hayes HayesStewart-QuiverBS` running (board + HELP + PR-review channels).
> **Status:** `quant-fact-seams` ✅ + `experiment-design` (ED-1 #28, ED-2 #36) ✅ — both complete.
> **🔨 NOW: `robyn-scs-endpoint-wiring`** (read the [brief](../docs/superpowers/plans/2026-06-24-robyn-scs-endpoint-wiring.md)).
> The pipeline is **already vendored** for you at **`vendor/robyn_scs/`** (read its `VENDORED.md` + the
> 8-endpoint map). Build `tools/robyn_scs/` that wires callable endpoints around the vendored `utils/` —
> **don't modify `vendor/`, don't run the full pipeline** (verify by import + `inspect.signature`). Engine stays
> stdlib-only (heavy deps live in the tool). Branch from latest `main` (`git pull` first). Then your 6 corpora.
> **PR flow:** you have a PAT → **open your own PRs** (`gh pr create --base main`); the watcher's pr-review channel
> works. (If `gh` ever fails, the token-less push→approver-opens fallback remains sanctioned.) Blocked? `dev/HELP.md`.
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
| `frontend-and-data-planes` (A data planes #37 + B transparent front end #41) | rohan | 2026-06-24 | PRs #37/#41 |
| `experiment-design` (ED-2 fill.py) · vendor robyn_scs (#39) | hayes/rohan | 2026-06-24 | PRs #36/#39 |
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
