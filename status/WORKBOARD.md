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
> **🌙 OVERNIGHT DEMO SHIFT (2026-06-25, report by 08:30):** get a real, reproducible **TSC2** demo working — in-session live EMET · all-haiku · full scope. Rohan Claude builds **B (finish dispatch-opt) → A (live-emet-session-reuse) → D (capture TSC2 scenario) → E (robyn_scs firm seam)**; Head Claude audits/merges. Plan: [overnight-demo-shift](../docs/superpowers/plans/2026-06-25-overnight-demo-shift.md).
> **Overnight shift (2026-06-23→24): ✅ COMPLETE** — all 3 worker tasks merged: H (#22), K1 (#24), K2 (#26).
> Backend is now end-to-end-capable: front door serves the live firm (K1) + agents read their corpora at run
> time (K2). Suite 368 green. (Auditor: auto-merged all-green; none held.)

| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `real-live-emet-frontend` | **🔨 assigned → Rohan Claude (HIGH)** | **Feature.** Front-end Live EMET fails (detached browser can't reach the logged-in session → tool-failure). Give the EMET runner a dedicated persistent authenticated profile (`$SAPPHIRE_EMET_PROFILE`, one-time login helper) or CDP-connect, so a Live run lands REAL PMIDs; honest-abstain if none. Credential-at-rest = gitignored RohanOnly. Also bound per-agent claude timeout. | `rohan/real-live-emet-frontend` | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-25-real-live-emet-frontend.md) |
| `live-run-visibility` | **🔨 assigned → Rohan Claude (HIGH — fix now)** | **Feature.** Live runs show only an opaque "Convening the firm…" spinner — zero visibility. Stream the firm step-by-step: engine `run_live(on_progress=…)` + incremental trace flush; front end renders a live step tree (plan → each Bucket-1 agent w/ result+timing, internal moat + EMET visibly first → flags → each persona verdict → synthesis). Additive; outputs/guards unchanged. | `rohan/live-run-visibility` | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-25-live-run-visibility.md) |
| `live-emet-session-reuse` | ✅ **MERGED (#57) — keystone, live-acceptance PASSED** | In-session EMET orchestration so a logged-in BenchSci session is reused → live PMIDs in the external plane; honest-abstain kept for no-session; shared-profile fallback if blocked. | `rohan/live-emet-session-reuse` | [runtime-harness](runtime-harness.md) · [**plan**](../docs/superpowers/plans/2026-06-25-overnight-demo-shift.md) |
| `tsc2-demo-scenario` | ✅ **MERGED (#61) — DEMO COMPLETE** | Capture the real TSC2 run as a deterministic scenario (instant $0 replay) + a demo-script note. | `rohan/tsc2-demo-scenario` | [engine](engine.md) · [**plan**](../docs/superpowers/plans/2026-06-25-overnight-demo-shift.md) |
| `robyn-scs-firm-seam` | ✅ **merged (#62)** | Wire vendored+endpoint-wired robyn_scs into the firm as a Bucket-1 tool seam (heavy deps in tool; honest fire-when-relevant). | `rohan/robyn-scs-firm-seam` | [tools](tools.md) · [**plan**](../docs/superpowers/plans/2026-06-25-overnight-demo-shift.md) |
| `cheap-live-runs` | ✅ **merged (#52)** | **Standard.** Make a live run usable + cheap: (1) wire `emet_handler` into `run_live`'s live ctx (lazy) so a logged-in EMET session is actually used — or abstain honestly + HELP if session-reuse needs a design call; (2) `CLAUDE_MODEL`→`--model` pass-through in `dispatch_claude` + a **"Live (cheap)"** front-end profile (haiku and/or mock personas, real facts). Engine stays stdlib; data boundary intact. | `rohan/cheap-live-runs` | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-24-cheap-live-runs.md) |
| `dispatch-optimization` | ✅ **merged (#56)** | **Standard→Feature.** Keep Claude agents warm + stop re-reading context: spike+baseline (token/latency) → Opt1 sub-agents stop loading CLAUDE.md (cache-friendly prefix) → Opt2 batch-per-bucket (flagged) → Opt3 warm stream-json worker (per-agent context reset, cold fallback). All behind `dispatch_claude`; outputs/guards/provenance unchanged; subscription, no API. | `rohan/dispatch-optimization` | [runtime-harness](runtime-harness.md) · [**brief**](../docs/superpowers/plans/2026-06-24-dispatch-optimization.md) |
| `frontend-and-data-planes` | ✅ **COMPLETE (A #37 + B #41)** | **Feature DONE.** A: two enforced data planes (`plane_for`, fail-safe boundary rule, derived `plane` on every fact). B: **transparent front end** — `frontend/` forks LOKA's Chainlit app (real repo untouched), re-points to in-process `live_engine.run_live`, renders the full firm process (plan→per-agent→dossier split by **two distinct planes**→roundtable **spread**→synthesis→partial-run banner); Demo + Live profiles; engine stays stdlib. Gate 2 ✅ + Gate 5 ✅ (PASS — bridge hits real engine, planes zero cross-contamination, app launches). Suite **463**. `site/` superseded. | — | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-24-sapphire-frontend-and-data-planes.md) |
| `loka-integration-plan` | ✅ merged (#34) | Analyzed LOKA source (read-only), wrote plan + `/api/run` wire contract + open questions; data-boundary ruled (separate planes). | — | [frontend-loka](frontend-loka.md) |
| `crossplatform-test-hardening` | ✅ merged (#22) | Fixed 3 cross-platform test fails (moat dir-name, cp1252). Suite 343 green. | — | [dev-harness](dev-harness.md) |
| `k1-run-live-service` | ✅ merged (#24) | **Keystone DONE.** `/api/run` now serves the harnessed `run_live` (`via=engine-live`); contract frozen + validated; canned = labeled fallback. Suite 356. | — | [frontend-loka](frontend-loka.md) |
| `k2-corpus-retrieval` | ✅ merged (#26) | **Keystone DONE.** Bucket-1 agents read `corpus/<id>/` at run time; corpus facts land in the dossier (traced, `provenance=corpus`), live path runs the gap. Veto rule intact. Suite 368. | — | [runtime-harness](runtime-harness.md) |

## hayes  (`@HayesStewart-QuiverBS`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `robyn-scs-endpoint-wiring` | ✅ **merged (#44)** | **Standard DONE.** `tools/robyn_scs/` — 10 callable endpoints wrapping the vendored SCS/STA pipeline; thin wrappers, `vendor/` untouched, pipeline not run (verified by signature alignment + synthetic `detect_events`); engine stays stdlib (heavy deps lazy/isolated). Gate 2 Approved + Gate 5 PASS, suite 478. Fast-follows (optional): `neuron_types_from_merged` signature probe; `run_fov` trace-roster comment. Next (separate task): live_engine seam to call these as a Bucket-1 tool. | — | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-24-robyn-scs-endpoint-wiring.md) |
| `quant-fact-seams` | ✅ **COMPLETE** | All 4 seams shipped: gnomAD (#6) · GTEx (#9) · InterPro (#11) · g:Profiler (#12). | — | [tools](tools.md) |
| `experiment-design` | ✅ **ED-1 (#28) + ED-2 (#36) merged** | **Epic done.** Port Matt's `design-form-agent` → filled design sheet. `tools/experiment_design/` (extract.py + fill.py), vendor-verbatim, golden-locked, stdlib-only. Follow-up nit (next ED push): add `scan_direction`/`addition_protocol` to `_MENU_FIELDS` validation. | — | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md) |
| `semantic-corpora` (6) | **1/6 merged (patent-ip #76)** | Dual-source corpora for **~~patent-ip ✅~~ · post-market-safety · clinical-trial-registry · payer-market-access · manufacturing-cmc · dea-scheduling**, per the **locked** method. **patent-ip merged Pass-A-first** (#76): 7 verified granted-patent cards (ASO/SM/AAV/platform, SMA-franchise-anchored), `validate-corpus.sh` CLEAN, suite 540 green. Pass B (EMET) pending the Claude-extension host-permission for `emet.benchsci.com`; T1 re-tier pending HELP `patent-ip-t1-patent-domains` (both non-blocking). **Method proven — batch the remaining 5.** | `hayes/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Hayes — run autonomously** (`dev/CONTRIBUTOR_RULES.md` §Autonomous operation): keep
> `bash dev/watch-assignments.sh hayes HayesStewart-QuiverBS` running (board + HELP + PR-review channels).
> **Status:** `quant-fact-seams` ✅ · `experiment-design` (#28/#36) ✅ · `robyn-scs-endpoint-wiring` (#44) ✅ — all complete.
> **🔨 NOW: your 6 `semantic-corpora`** (patent-ip · post-market-safety · clinical-trial-registry ·
> payer-market-access · manufacturing-cmc · dea-scheduling). Read the
> [corpora brief](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) + the **locked** METHOD
> (`sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`) + study the worked example. Build dual-source
> (browser + EMET), run `bash dev/validate-corpus.sh sapphire-orchestrator/corpus/<agent>` + `bash dev/run-tests.sh`
> until both green. **Ship your FIRST, wait for my review, then batch the rest in parallel** (one PR each). Branch
> from latest `main` (`git pull` first). Self-auth `emet.benchsci.com` for the EMET pass.
> **PR flow:** you have a PAT → **open your own PRs** (`gh pr create --base main`); the watcher's pr-review channel
> works. (If `gh` ever fails, the token-less push→approver-opens fallback remains sanctioned.) Blocked? `dev/HELP.md`.
> Always branch from the **latest `main`** (`git pull` first; merge `origin/main` if it moves). Blocked? `dev/HELP.md`.

## gavin  (`@GavinWongYF`) — contributor
| Task id | Status | Goal | Branch / PR | Area |
|---|---|---|---|---|
| `console-ui-design-refinement` | **🎨 assigned → Gavin** | **Standard.** Iterate the **★ LOKA-native 3-pane console** WITH Gavin into the agreed design (collaborative: present options → get Gavin's calls → refine). LEFT = agent cards by the two data planes · CENTER = synthesis + roundtable spread + DIVERGENCE · RIGHT = live trace. Stay strictly inside LOKA/Chainlit tokens (no new aesthetic); **do NOT touch the runtime `frontend/`** — design iteration only, in `docs/design/console-ui/`. DoD: a refined `sapphire_loka.html` Gavin signs off + a short decisions note. Keep binary-free + self-contained; preserve honesty markers; real TSC2 data stays internal-only. | `gavin/console-ui-design-refinement` | [**brief**](../docs/superpowers/plans/2026-06-25-console-ui-design-refinement.md) · [`docs/design/console-ui/`](../docs/design/console-ui/README.md) |
| `semantic-corpora` (6) | **✅ 6/6 COMPLETE (#30,#38,#48,#66,#68,#72)** | ~~global-regulatory-divergence ✅~~ · ~~financial-investor ✅~~ · ** · kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional** — one PR per agent, per the **locked** method. First corpus reviewed + merged (gate CLEAN, suite 381) — **method proven; batch the remaining 5.** Self-auth BenchSci for the EMET pass. | `gavin/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **🎨 Gavin — NEW: `console-ui-design-refinement` (assigned).** Refine the LOKA-native 3-pane console WITH Gavin
> into the agreed design. Read the [**brief**](../docs/superpowers/plans/2026-06-25-console-ui-design-refinement.md) +
> [`docs/design/console-ui/README.md`](../docs/design/console-ui/README.md). View it:
> `python3 -m http.server 8090 --directory docs/design/console-ui` → open `/index.html` (★ LOKA-native loads first).
> Work **collaboratively** — present the open choices (trace rail · density · left-card grouping · spread/DIVERGENCE ·
> two-plane signposting), get Gavin's calls, iterate `sapphire_loka.html`. **Stay inside LOKA/Chainlit tokens** (no new
> aesthetic); **do NOT modify `frontend/`** (the fold-in is a later task, only when Gavin signals ready). Keep it
> binary-free + self-contained; preserve the honesty markers; real TSC2 data is **internal-only**. Branch
> `gavin/console-ui-design-refinement` from latest `main`; ship via PR (Head Claude reviews/merges). Blocked? `dev/HELP.md`.
>
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
| `live-emet-session-reuse` | rohan | Live-EMET demo interim: run EMET in the orchestrator's own authenticated session (prefer in-session orchestration over a shared --user-data-dir profile) so a logged-in BenchSci session is actually reused; durable answer = EMET-MCP. Credential-at-rest call for Rohan if the profile route is chosen. (HELP-resolved 2026-06-25) | [runtime-harness](runtime-harness.md) |
| ~~`frontdoor-wire-run-live`~~ | rohan | ✅ Folded into `frontend-and-data-planes` (active above) — the new `frontend/` connects directly to `run_live`; `serve.py /api/run` already serves it (K1). | [frontend-loka](frontend-loka.md) |
| `aso-design-tool` | hayes | Build the ASO Design tool; feed designed sequences into the `aso-tox` `sequences=` channel | [tools](tools.md) |
| `scenario-coverage` | gavin | Broaden captured scenario coverage across the 10-axis variety matrix | [engine](engine.md) |
| `retire-mocks` | — | Audit + honestly label/retire remaining mock surfaces | [tools](tools.md) |
| `chronic-tox` | hayes | Scope + integrate the chronic-tox model (roadmap) | [tools](tools.md) |
| `crossplatform-test-hardening` | rohan/gavin | Fix 3 pre-existing cross-platform test failures Hayes flagged (HELP.md, resolved): moat clone-name test hardcodes `sapphire-capability-map`; `test_scenarios`/`test_trace_view` assume UTF-8 (fail on Windows cp1252). Low-risk: derive the moat suffix from the repo root; add `encoding="utf-8"` + guard the `✓` stdout write. | [dev-harness](dev-harness.md) |

## Recently merged
| Task id | Owner | Merged | Ledger |
|---|---|---|---|
| `semantic-corpora` (patent-ip — Hayes's 1st corpus) | hayes | 2026-06-25 | PR #76 |
| `semantic-corpora` (patient-advocacy — Gavin 5th) | gavin | 2026-06-25 | PR #68 |
| `semantic-corpora` (kol-social-signal — Gavin's 4th) | gavin | 2026-06-25 | PR #66 |
| `robyn-scs-firm-seam` (Track E) | rohan | 2026-06-25 | PR #62 |
| `tsc2-demo-scenario` (DEMO COMPLETE) | rohan | 2026-06-25 | PR #61 |
| `dispatch-optimization` | rohan | 2026-06-25 | PR #56 |
| `dispatch-optimization` (Opt-1+2) | rohan | 2026-06-25 | PR #56 |
| `live-emet-session-reuse` (KEYSTONE) | rohan | 2026-06-25 | PR #57 |
| `cheap-live-runs` (live-EMET wiring + haiku profile) | rohan | 2026-06-25 | PR #52 |
| `semantic-corpora` (policy-legislative — Gavin's 3rd corpus) | gavin | 2026-06-24 | PR #48 |
| `semantic-corpora` (financial-investor — Gavin's 2nd corpus) | gavin | 2026-06-24 | PR #38 |
| `robyn-scs-endpoint-wiring` (tools/robyn_scs) | hayes | 2026-06-24 | PR #44 |
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
