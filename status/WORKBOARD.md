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
| `fix-tsc2-envelope-collision` | ✅ **merged (#96)** | **Fix.** Resolve the TSC2 EMET-envelope case-collision on the case-insensitive macOS FS: lowercase `tsc2.json` (#90, 9 evidence/9 PMIDs) + uppercase `TSC2.json` (#91, 24 evidence/14 PMIDs) mapped to one physical file → ambiguous front-end load + git churn. Keeps **ONE canonical** envelope = the richer #91 capture under the documented lowercase filename (`git rm --cached` the uppercase dup; tracked blob byte-identical to `52d5502`, zero content loss); `git ls-files` now lists exactly one TSC2 envelope. Updated 4 content-pin assertions (`emet/tests/test_envelopes.py`, `frontend/tests/test_bridge.py`) 9→24 (full set = 14 PMIDs + 10 DOIs) / 9→14 (PMID-only via `run_live`); engine untouched. Gated by Head Claude's delegate: scope CLEAN (4 files, zero engine touch), exactly one envelope (24 evidence / **14 PMIDs**), loader resolves (`load_envelope_for("TSC2"/"tsc2")` + `bridge._resolve_emet_envelopes(...)` all → 14-PMID envelope), secret-scan CLEAN + public PMIDs/DOIs only, suite **662 green** (the sole RED was the pre-sanctioned `test_consult_round1` flake — proven PR-independent: `tests` group 276/276 in isolation, full re-run 662 green). | `rohan/fix-tsc2-envelope-collision` | [engine](engine.md) · [runtime-harness](runtime-harness.md) |
| `boltz-firm-wire` | ✅ **merged (#82)** | **Feature.** Wires the Boltz seam into `live_engine.py` Bucket-1: registers the `boltz` agent in `harness/agents.json` (`kind: python`, provenance `boltz` external-plane, guardrails incl. `data_boundary`, `timeout_s: 360`, retry→abstain); adds a `structure=` param + `_extract_structure_inputs` query-text fallback (protein-only; SMILES never extracted from free text); threads only the whitelisted PUBLIC structural keys into `bucket1_inputs`. Fires on structure/affinity inputs, **dormant (no network) otherwise** — mirrors `aso-tox`. `TestBoltzWiring` (6 tests: fires-on-structure, query-text channel, dormant+no-network, honest-degrade on missing-key/API-down, internal-id boundary-block). Gated by Head Claude's delegate: GATE-1 secret-scan CLEAN (zero `sk_bc_ws_live_*` hits; key read only at runtime from gitignored `RohanOnly/boltz_api.env`), scope confined to `sapphire-orchestrator/`, stdlib boundary intact, data-boundary verified, suite **571 green** (known flake did not occur), TestBoltzWiring 6/6. | `rohan/boltz-firm-wire` | [tools](tools.md) · [**BOLTZ.md**](../sapphire-orchestrator/tools/BOLTZ.md) |
| `boltz-seam` | ✅ **merged (#80)** | **Feature.** Boltz Compute API (Boltz-2 structure + binding) as a Bucket-1 tool seam (`tools/boltz_seam.py`), stdlib-only urllib, public-only tripwire, honest KNOWN_UNKNOWN degrade, `boltz` external-plane provenance, 25 mocked tests + opt-in $0 live check. **Wired into `live_engine`** by #82 (above). Gated by Head Claude's delegate: GATE-1 secret-scan CLEAN, suite 565 green, $0 live path (`/auth/me`+`estimate-cost`) 200. | `rohan/boltz-seam` | [tools](tools.md) · [**BOLTZ.md**](../sapphire-orchestrator/tools/BOLTZ.md) |
| `sapphire-aws-infra` | ✅ **merged (#81)** | **Feature.** AWS Q-Models run infra: `.claude/skills/sapphire-aws/` (SKILL.md run procedure + README inventory) + `.claude/agents/sapphire-aws-runner.md` (sonnet runner) + ledger append for the live-created Sapphire EBS warm-weights volume `vol-0372a48d8defda8e6` (gp3, 50 GiB, us-east-1b). Safety model = account-gate (`255493511886`/`Rohan-Sapphire`) → `Name=Sapphire` g6e.xlarge → attach EBS → S3-staged eval → retrieve → teardown-by-ledgered-id. **No EC2 launched** (launcher `_render_tool_userdata` wiring is the follow-on, plan `2026-06-25-qmodels-aws-wiring.md`). Gated by Head Claude's delegate: scope clean (`.claude/`+ledger only), secret-scan CLEAN, ledger re-parses, launcher safety primitives confirmed real, suite 565 green. | `rohan/sapphire-aws-infra` | [runtime-harness](runtime-harness.md) · [**SKILL**](../.claude/skills/sapphire-aws/SKILL.md) |
| `qmodels-aws-gpu` | ✅ **merged (#86)** — **Task-2 CODE merged; GPU track honestly labeled `gpu-unproven`; live GPU proof still pending** | **Feature.** The `sapphire-aws-infra` follow-on (plan `2026-06-25-qmodels-aws-wiring.md`): `launcher.py` (+304/-38) renders per-tool userdata, stages code+inputs, launches a tagged self-terminating box, retrieves `result.json`, tears down by ledgered id — GPU async path **code-complete + dry-run-validated** (no EC2 launched). `test_qmodels_launcher.py` (+263). Re-gated by Head Claude's delegate: the only prior hold was honesty labeling — fix commit `cd4f97e` flips all 6 GPU-launch entries (`structure_binding`/`selectivity`/`family_clustering` + `boltz2`/`balm`/`esm2`) `live → gpu-unproven` (+ legend), registry-only (+7/-6, no engine touch); credential-clean (only the dummy `testkey`/`testsecret` test fixture), no binaries, suite **591 green**. **Next milestone:** a real Boltz-2 g6e.xlarge run that flips `gpu-unproven → live`. | `rohan/qmodels-aws-gpu` | [runtime-harness](runtime-harness.md) · [**plan**](../docs/superpowers/plans/2026-06-25-qmodels-aws-wiring.md) |
| `real-live-emet-frontend` | ✅ **MERGED (#90) — Gate-5 PASSED (real PMIDs land)** | **Feature.** Front-end Live EMET. The detached `claude -p`/CDP browser path tool-fails / is too slow even on sonnet (#77/#84, Gate-5). **Resolved via the session-bridge** (#90, supersedes #77/#84): `frontend/bridge.py` injects captured `emet_envelopes` (auto-loaded from `scenarios/emet_envelopes/<candidate>.json`) → `make_session_emet_handler` → `run_live`. A **covered candidate (TSC2) lands 9 real `emet-live` PMIDs** (`emet-runner: ok`) + 8 `moat-real`; an **uncovered candidate abstains honestly** (escalate → KNOWN_UNKNOWN, no fabricated PMIDs); `claude -p` kept as a documented NON-default fallback. Verified by Head Claude's delegate (Gate-5 a+b+c). | `rohan/emet-session-bridge` | [frontend-loka](frontend-loka.md) · [**brief**](../docs/superpowers/plans/2026-06-25-real-live-emet-frontend.md) |
| `emet-capture-hardening` | ✅ **merged (#91)** | **Feature.** Deterministic, **LLM-free** EMET capture (replaces the `claude -p` runner that tool-fails / is too slow). `emet/capture.py`: pure-stdlib `parse_emet_html` (DOM→§7 envelope: answer text + PubMed/DOI/Sources, schema-valid, honest-abstain on login/timeout/no-citations — never fabricates) + a **lazy-Playwright** live driver (CDP/profile, TipTap submit, deterministic stable-length wait) + `python -m emet.capture` CLI → `scenarios/emet_envelopes/<candidate>.json`. `test_capture.py` (9, all stdlib) + HTML fixtures + `TSC2.json` (14 real PMIDs). Gated by Head Claude's delegate: scope CLEAN (5 files, zero engine touch), secret-scan ZERO (fixture emails are placeholder/RFC-2606-redacted), **stdlib-boundary verified empirically** (`import live_engine` + `import emet.capture` → 0 playwright; parser pure-stdlib), suite **600 green** (no `test_consult_round1` flake), `test_capture.py` 9/9 (live TSC2 fixture → 14 real PMIDs). | `rohan/emet-capture-hardening` | [runtime-harness](runtime-harness.md) · [engine](engine.md) |
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
| `semantic-corpora` (6) | **4/6 merged (#76,#83,#85,#87)** | Dual-source corpora for **~~patent-ip ✅~~ · ~~post-market-safety ✅~~ · ~~clinical-trial-registry ✅~~ · payer-market-access · manufacturing-cmc · ~~dea-scheduling ✅~~**, per the **locked** method. 4 merged (#76/#83/#85/#87). **post-market-safety merged (#87, squash `30ea750`):** 8 verified cards, **all T1 `api.fda.gov`** (openFDA — FDA boxed warnings byte-verified vs raw JSON + FAERS T2 supporting/caveated): CNS class liabilities (anti-amyloid ARIA · AAV hepatotox · ASO thrombocytopenia/renal · 5-HT2 valvulopathy · GABA-T vision-loss · SSRI suicidality · CBD hepatotox · NMDA-ant) + the FAERS-under-captures-insidious-harms C2 finding; gate CLEAN, suite 591, anti-fabrication spot-verified (3 boxed warnings + 2 no-boxed-warning W&C cards re-checked live vs openFDA). **EMET driving turned out INTERMITTENT** (host-perm flickers per-tab — a read worked once, then reads + the computer-tool blocked), so the Pass-B mechanism layer is pending a stable EMET path (Rohan's `real-live-emet-frontend` / a permanent site-grant). Reachable T1 fetch paths: `api.fda.gov`, `clinicaltrials.gov` v2 API, `govinfo.gov` HTML; **`www.fda.gov` + `cms.gov` are 403** → manufacturing-cmc (fda.gov; 5 T2 cards held) + payer-market-access (cms.gov) remain hard. | — | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **Hayes — run autonomously** (`dev/CONTRIBUTOR_RULES.md` §Autonomous operation): keep
> `bash dev/watch-assignments.sh hayes HayesStewart-QuiverBS` running (board + HELP + PR-review channels).
> **✅ Your violet console design was ADOPTED + merged (#97 mock + #99 Chainlit tint, 2026-06-25)** — the user
> chose Hayes's full design; #99 intentionally supersedes #94's sapphire-blue as the runtime look. Both gated green
> (render-checked :8015, suite 662). No action needed; continue your `semantic-corpora` queue below.
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
| `demo-claude` | **🟢 assigned → Gavin (NEW)** | **Standard.** Run a **"Demo Claude"** session that stands up + runs a working live Sapphire demo on YOUR redesigned front-end (the #94 restyle is the runtime look now). Use a FREE port (e.g. `--port 8002`; :8000/:8001 may be other live sessions). Drive via computer use (or Playwright); Playwright is also the EMET agent's tool. Profiles: `Live (demo · simulated models)` **if** you have `RohanOnly/` data (moat/Boltz/EMET — local to Rohan's device, NOT in git; ask if absent), else the committed frozen-real `Replay (TSC2 · session-bridge EMET · $0)` / `Demo (mock)`. DoD: the demo up + a TSC2 run rendering the full firm (moat + EMET PMIDs + spread + synthesis), honestly labeled (live vs replay vs mock). **You do NOT gate/merge** — Head Claude (Rohan) is the approver; flag issues via `dev/HELP.md`. | runs merged `frontend/` (no PR needed) | [**brief**](../docs/superpowers/plans/2026-06-25-gavin-demo-claude.md) |
| `site-console-redesign` | ✅ **merged (#79)** | **Side task (not the assigned one).** Visual polish of the **static** `site/` Console (depth/elevation tokens, animated hero, faceted CSS gem brand mark, gradient Send button, inline-SVG gem favicon). Pure CSS/HTML — no JS/engine/data, every hook preserved; binary-free. Restyles the legacy `site/` surface (superseded by `frontend/`); distinct from `console-ui-design-refinement` and does not touch `frontend/`. | `gavin/site-console-redesign` | [tools](tools.md) |
| `semantic-corpora` (6) | **✅ 6/6 COMPLETE (#30,#38,#48,#66,#68,#72)** | ~~global-regulatory-divergence ✅~~ · ~~financial-investor ✅~~ · ** · kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional** — one PR per agent, per the **locked** method. First corpus reviewed + merged (gate CLEAN, suite 381) — **method proven; batch the remaining 5.** Self-auth BenchSci for the EMET pass. | `gavin/corpus-<agent>` | [tools](tools.md) · [**brief**](../docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md) |

> **🟢 Gavin — NEW: `demo-claude` (assigned).** Run a **Demo Claude** that stands up a working live demo on
> your redesigned front-end (#94 is the runtime look now). Read the
> [**brief**](../docs/superpowers/plans/2026-06-25-gavin-demo-claude.md) — it has a ready-to-paste Demo Claude
> prompt + the data caveat (the LIVE profiles need Rohan's gitignored `RohanOnly/` moat/Boltz/EMET; if you don't
> have it, use the committed **frozen-real Replay** profiles or `Demo (mock)`). Use a **free port** (`--port 8002`;
> :8000/:8001 may be other live sessions). You do **NOT** gate/merge — **Head Claude (Rohan)** is the approver.
>
> **🎨 Gavin — NEW: `console-ui-design-refinement` (assigned).** Refine the LOKA-native 3-pane console WITH Gavin
> into the agreed design. Read the [**brief**](../docs/superpowers/plans/2026-06-25-console-ui-design-refinement.md) +
> [`docs/design/console-ui/README.md`](../docs/design/console-ui/README.md). View it:
> `python3 -m http.server 8090 --directory docs/design/console-ui` → open `/index.html` (★ LOKA-native loads first).
> Work **collaboratively** — present the open choices (trace rail · density · left-card grouping · spread/DIVERGENCE ·
> two-plane signposting), get Gavin's calls, iterate `sapphire_loka.html`. **Stay inside LOKA/Chainlit tokens** (no new
> aesthetic); **do NOT modify `frontend/`** (the fold-in is a later task, only when Gavin signals ready). Keep it
> binary-free + self-contained; preserve the honesty markers; real TSC2 data is **internal-only**. Branch
> `gavin/console-ui-design-refinement` from latest `main`; ship via PR (Head Claude reviews/merges). Blocked? `dev/HELP.md`.
> The **COMPLETE showcase** (★ LOKA-native + the 3 explorations + the `index.html` switcher + `demo_data.json` + README)
> is in [`docs/design/console-ui/`](../docs/design/console-ui/README.md) — serve it (`python3 -m http.server 8090 --directory docs/design/console-ui`)
> and open `index.html` for the exact `:8090` UI.
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
| `console-chainlit-violet` (**adopted** — Chainlit runtime violet tint, mock parity: dark `--background`→`256 19% 11%`=`#1a1722`, header/composer neutral; intentionally overrides #94 sapphire-blue. frontend/public only. Render-checked :8015 ✓, suite 662 ✓) | hayes | 2026-06-25 | PR #99 |
| `console-ui-refine` (**adopted** — violet MOCKUP: canvas `#1a1722` + `--purple #a07cff`, per-sub-agent cards 14→**42**, blue↔purple attributed-finding highlight; docs/design only, runtime untouched. Rendered :8015 ✓, 0 console errors) | hayes | 2026-06-25 | PR #97 |
| `console-ui-chat-tweaks` (mock-only: agent wing as 14-category expandable tree + 5 attributed `#4d7cfe` findings on Gavin's chat-first prototype; composes with #94, runtime untouched) | hayes | 2026-06-25 | PR #95 |
| `real-live-emet-frontend` (session-bridge = front-end's real-EMET path; supersedes #77/#84; Gate-5 a+b+c PASS — 9 real TSC2 PMIDs) | rohan | 2026-06-25 | PR #90 |
| `semantic-corpora` (post-market-safety — Hayes's 4th corpus) | hayes | 2026-06-25 | PR #87 |
| `qmodels-aws-gpu` (Task-2 CODE; GPU track labeled `gpu-unproven`; live proof pending) | rohan | 2026-06-25 | PR #86 |
| `semantic-corpora` (clinical-trial-registry — Hayes's 3rd corpus) | hayes | 2026-06-25 | PR #85 |
| `site-console-redesign` (static `site/` visual polish) | gavin | 2026-06-25 | PR #79 |
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
