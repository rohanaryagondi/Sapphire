# Build Ledger

Append-only log of what shipped to `main`. Newest at the top. One entry per feature-sized change. Format:

```
## <date> — <title>   (<commit range or SHA>)
- What: one-paragraph summary.
- Gates: tests <N> green · review <verdict> · verify <verdict> · whole-branch <verdict>.
- Gaps/Follow-ups: anything deliberately deferred.
```

---

## 2026-06-25 — live-run visibility (#71) + reputational-institutional corpus 6/6 (#72)  (`main`)
- #71 (Built-By rohan): `run_live(on_progress=)` + incremental trace flush + front-end live step tree — the firm now streams step-by-step (plan → each Bucket-1 agent w/ status+provenance+timing → flags → personas → synthesis), abstain shown honestly (never fake ok). Browser-verified streaming; suite 540. **Exposed** that the front-end Live EMET fails (detached browser can't reach the logged-in session) → new task `real-live-emet-frontend` (moat is real; that was a worktree artifact).
- #72 (Built-By gavin): reputational-institutional corpus (4 cards: Cassava SEC + congressional probe, Lesne retraction, EMET check). **Gavin's semantic corpora COMPLETE: 6/6** (global-regulatory-divergence, financial-investor, policy-legislative, kol-social-signal, patient-advocacy, reputational-institutional).

---

## 2026-06-25 — patient-advocacy corpus — Gavin's 5th Bucket-1 corpus  (`main`, PR #68)
- Built-By: `gavin` (reviewed/gated/merged by Head Claude; reactive-net auto-gated). 5 cards: advocacy campaigns (Alzheimer's Assoc CMS), FDA ALS guidance (T1), eteplirsen accelerated-approval precedent, MJFF funding, EMET ALS-prognosis (PMID 21989247). Gate CLEAN · suite 527 · content clean.

---

## 2026-06-25 — kol-social-signal corpus — Gavin's 4th Bucket-1 corpus  (`main`, PR #66)
- Built-By: `gavin` (reviewed/gated/merged by Head Claude; auto-gated by the post-shift reactive net).
- What: dual-source corpus, 6 KOL-sentiment cards — named experts' public stances on lecanemab/aducanumab/Cobenfy (Kurkinen, Knopman, Bauchner+Alexander, Javitt), all PubMed-cited + correctly T2; EMET card (PMID 41352683) validates the lead KOL-skeptic claim.
- Gates: corpus gate CLEAN (all URLs resolve) · suite green · content audited clean (real PMIDs, 0 fabrication, quotes <=60w).

---

## 2026-06-25 — robyn_scs firm seam (fire-when-relevant Bucket-1 tool) — Track E  (`main`, PR #62)
- Built-By: `rohan` (reviewed + Gate-5-verified + merged by Head Claude).
- What: `tools/robyn_scs_seam.py` wires the vendored robyn_scs SCS/STA pipeline into the firm as a Bucket-1 tool seam — fires only with a real imaging `input_dir`; honest KNOWN_UNKNOWN on empty/absent plate (no fabricated connectivity); stdlib engine (heavy deps in the tool); internal plane; traced + provenance-stamped (`robyn-scs`). Fix-loop: empty-plate honesty + drop data_boundary from the internal-plane agent + non-mocked test.
- Gates: review Approved + Gate-5 PASS; suite **527 green**.
- **OVERNIGHT COMPLETE:** Tracks A (#57) + B (#56) + D (#61) + E (#62) all shipped. TSC2 demo runs live + replays. Report: dev/reports/overnight-2026-06-25-demo.md.

---

## 2026-06-25 — TSC2 demo scenario captured ($0 deterministic replay) — Track D / DEMO COMPLETE  (`main`, PR #61)
- Built-By: `rohan` (Rohan Claude; reviewed + Gate-5-verified + merged by Head Claude).
- What: `scenarios/tsc2_live_run.json` — a REAL captured `run_live` run (wall 1050s; real moat internal-plane facts + 8 live EMET PMIDs external-plane + 5-persona spread + DIVERGENCE + synthesis), replayed by the front end instantly $0/offline. Reproducible capture script (`_build/capture_tsc2_live.py` emits `_internal_only`/`_data_notice`), internal-only tagged, honest demo doc (`frontend/DEMO_TSC2.md`; guardrail-abstentions shown honestly, not as deliberate holds).
- Gates: review Approved + Gate-5 "Works as claimed" (verified REAL — not a dressed-up mock — and replays the full firm with the network blocked); 3-fix loop (reproducible tags, honest persona wording, TSC-relevant DIVERGENCE assertion). Suite **497 green**.
- **MILESTONE: the overnight demo goal is met.** Tracks A (live-EMET keystone #57) + B (dispatch-opt #56) + D (#61) complete — the TSC2 demo runs live (real PMIDs land via run_live) AND replays from the captured scenario. Track E (robyn firm seam #62, BONUS) is in a fix loop; corpora ongoing.

---

## 2026-06-25 — dispatch optimization (Opt-1 cache-stable + Opt-2 batch, flagged)  (`main`, PR #56)
- Built-By: `rohan` (Rohan Claude; reviewed/gated/merged by Head Claude). Transport/cost only — agent outputs/guards/provenance byte-identical.
- What: Opt-1 — `dispatch_claude` adds `--setting-sources user` + `--exclude-dynamic-system-prompt-sections` (drops redundant project CLAUDE.md per sub-agent, keeps the cacheable preamble first → cache-stable shared prefix); guards stay harness-enforced regardless; `SAPPHIRE_DISPATCH_FULL_CONTEXT=1` escape hatch. Opt-2 — `dispatch_claude_batch` (flagged, opt-in) one call per bucket, forwards the UNION of agents' `--allowedTools`, per-item provenance/guards preserved. Opt-3 (warm worker) parked → Claude Agent SDK is the durable path (HELP-resolved).
- Gates: review Approved (no behavior change — guards independent of CLAUDE.md) + Gate-5 PASS; suite **505 green**.

---

## 2026-06-25 — KEYSTONE: in-session EMET orchestration — real PMIDs land via run_live  (`main`, PR #57)
- Built-By: `rohan` (Rohan Claude; reviewed/gated/merged + LIVE-acceptance-tested by Head Claude).
- What: `emet/session_bridge.py::make_session_emet_handler(envelopes)` injects EMET envelopes captured from
  the orchestrator's OWN authenticated browser into `run_live` via the `make_emet_handler` seam (candidate-keyed,
  case-tolerant). Real cited PMIDs land as `emet-live` external-plane facts; honest-abstain (escalate) when no
  envelope; nothing written to disk (no credential-at-rest). Resolves the live-EMET keystone (mechanism c).
- Gates: Gate 2 Approved (fabrication analysis holds on every path); Gate 5 "Works as claimed" (injection lands
  real PMIDs; no-envelope→escalate/0 facts; no cross-wiring; data-boundary fires pre-dispatch); suite **495 green**.
  **Head Claude LIVE acceptance:** drove a fresh TSC2 Target-Validation run in an authenticated BenchSci session
  (chat 21801696) → real PMIDs (33307091 etc.) → captured envelope → `run_live` → 3 emet-live PMIDs on the
  external plane, emet-runner=ok. THE demo now has live external evidence.
- Fast-follow (nit): commit a positive multi-candidate cross-wiring test (behavior already Gate-5-verified).

---

## 2026-06-25 — cheap-live runs (live-EMET wiring + model lever + haiku profile)  (`main`, PR #52)
- Built-By: `rohan` (Rohan Claude; reviewed/gated/merged by Head Claude).
- What: W1 — `run_live` now lazily wires a real `emet_handler` into the live ctx (`setdefault`; engine import graph stays stdlib); EMET on `login_required` **abstains honestly** (escalate → no fabricated facts), session-reuse design parked to EMET-MCP / a `live-emet-session-reuse` interim. W2 — `CLAUDE_MODEL`/`SAPPHIRE_MODEL` → `--model` in BOTH `dispatch_claude` and the EMET subprocess; a 3rd Chainlit profile **"Live (cheap · haiku)"** (real backends, haiku reasoning, nothing mocked/relabeled). Demo/Live profiles unchanged; run_live contract additive.
- Gates: Gate 2 review = Approved; Gate 5 = "Works as claimed" — CRITICAL no-fabrication check passes (login_required → 0 EMET facts, agent `escalated`); lazy/stdlib boundary proven; `--model` argv present/absent verified; env set+restore leak-free. One fix-loop (thread `--model` into the EMET subprocess for honesty + cost). Suite **490 green**.
- Follow-ups: `live-emet-session-reuse` (interim for live-EMET demos; prefer in-session orchestration) + EMET-MCP (durable).

---

## 2026-06-24 — policy-legislative corpus — Gavin's 3rd Bucket-1 corpus  (`main`, PR #48)
- Built-By: `gavin` (reviewed/gated/merged by Head Claude).
- What: dual-source corpus, 6 cards — US CNS policy/pricing: CMS anti-amyloid CED coverage (2022), IRA Medicare price-negotiation cycle-2 (15 drugs, 2025), FDA/FDORA accelerated-approval reform (cms.gov/fda.gov T1); IRA small-molecule pill-penalty (KFF T2); 2 EMET cards on real PMIDs (36449413 lecanemab CLARITY-AD, 40225240 CDR-SB MCID).
- Gates: corpus gate CLEAN (all URLs resolve) · suite 478 green · content audited clean (0 fabrication, quotes <=60w, tiers honest).

---

## 2026-06-24 — financial-investor corpus — Gavin's 2nd Bucket-1 corpus  (`main`, PR #38)
- Built-By: `gavin` (reviewed/gated/merged by Head Claude).
- What: dual-source corpus, 6 cards — recent CNS M&A + clinical-failure signals (BMS/Karuna $14B, AbbVie/Cerevel $8.7B + emraclidine Ph2 failure, J&J/Intra-Cellular $14.6B, Neumora navacaprant Ph3 failure, KarXT EMET card). SEC 8-K primaries T1; press/secondary T2; EMET card cites real PMID 33626254.
- Gates: corpus gate CLEAN (unverifiable_by_fetch tags correct after fix-loop) · suite 478 green · content audited clean (0 fabrication, quotes ≤60w, tiers honest). One fix-loop: navacaprant card was missing the unverifiable_by_fetch tag → Gavin tagged it + synced main.

---

## 2026-06-24 — robyn_scs endpoint wiring — tools/robyn_scs/  (`main`, PR #44)
- Built-By: `hayes` (reviewed/gated/merged by Head Claude).
- What: `tools/robyn_scs/` exposes the vendored SCS/STA connectivity pipeline (`vendor/robyn_scs/`) as 10
  correctly-wired callable endpoints (detect_events · run_scs · run_sta · merge_and_classify · visualize ·
  run_fov · run_batch · discover_fov_quartets · load_stim_metadata · stim_mask_from_sidecar) — thin wrappers
  that import + delegate to the vendored `utils/`, docstrings naming each `module.func :line`. `vendor/` NOT
  modified; the full pipeline is NOT run (MATLAB splitter documented as a manual upstream step). Heavy deps
  (numpy/scipy/pandas/matplotlib) imported LAZILY inside the endpoints + isolated to `tools/robyn_scs/
  requirements.txt`; the Sapphire engine stays stdlib-only (enforced by a subprocess meta_path-blocker test).
- Gates: Gate 2 review = Approved; Gate 5 verification = "Works as claimed" (signature alignment proven via a
  FileNotFoundError-not-TypeError forward probe; `detect_events` synthetic call detects planted APs; vendor
  untouched). Suite **478 green** (15 wiring tests).
- Fast-follows (non-blocking, fold into next robyn touch): add a signature probe for `neuron_types_from_merged`;
  one-line comment on `run_fov`'s P1 trace-roster forwarding. Next step (separate task): a live_engine seam so
  the firm can call these endpoints as a Bucket-1 tool (once an ASO/SCS query path needs it).

## 2026-06-24 — Transparent front end (LOKA-fork → run_live) — feature work-stream B  (`main`, PR #41)
- Built-By: `rohan` (built by Rohan Claude worker session; reviewed/gated/merged by Head Claude — separation of powers).
- What: forks LOKA's Chainlit app into `frontend/` (real `q-state-biosciences/drug-discovery-agent` clone untouched;
  `FORKED_FROM.md` records upstream `8685382` + escalates the no-LICENSE question to a human) and re-points it from
  AWS Bedrock to **in-process `live_engine.run_live`** via `bridge.py`. `render.py` (chainlit-free, stdlib, unit-
  tested) maps the run_live contract to a **transparent firm view**: plan → per-agent (id·status·provenance,
  abstain shown) → dossier split into the **two distinct data planes** (internal moat vs external) → Bucket-2
  roundtable **spread** (per-persona, no consensus collapse, round1→round2) → synthesis → partial-run banner. Two
  profiles: Demo (mock ctx, $0) + Live (real firm). Engine stays stdlib-only (chainlit/pandas confined to
  `frontend/requirements.txt`); `site/` Console marked superseded.
- Gates: Gate 2 review (Approved-with-nits → fix-looped: non-vacuous spread test, CORS→localhost, status banner,
  sequences forwarding) + Gate 5 functional verification (PASS — bridge calls the real engine in-process, planes
  render with zero cross-contamination, degraded runs honest, app launches). Suite **463 green** (29 frontend tests).
- This + work-stream A complete the `frontend-and-data-planes` feature: the backend is now reachable through a
  transparent, honest control surface. Follow-ups: real (non-mock) Live-profile runs need the `claude` CLI;
  per-agent timing is aspirational (no contract field — render refuses to fabricate it); LOKA license sign-off
  before any EXTERNAL ship (internal reuse OK).

## 2026-06-24 — Two enforced data planes (internal vs external) — feature work-stream A  (`main`, PR #37)
- Built-By: `rohan`. Tier: Feature (work-stream A of `frontend-and-data-planes`; B = the LOKA-fork front end, next).
- What: the data-boundary call ("separate web/external from Quiver internal, + visible") made concrete.
  `contracts/provenance.py`: `plane_for(provenance) → internal|external` (only `moat-real` is internal;
  EMET·web·Q-Models·seams·corpus·qmodels:* are external) with a **bidirectional** import-time totality guard;
  `is_boundary_violation()` (fail-safe — internal fact + unidentifiable target → block) as the classification-
  level rule. `live_engine.py`: every dossier fact carries a **derived, unconditional** `plane` (additive in
  `run_live_schema.{md,py}`). Honest 2-layer documentation: the runtime enforcer is `harness/guardrails.py`
  `data_boundary()` (internal keys + identifier patterns; shared with the public-only memory subsystem, so it
  keys on raw internal data, not provenance labels); the plane map is the complementary classification layer
  (dossier tagging + UI), not a 2nd runtime gate.
- Gates: Gate 2 independent review (Approved-with-nits → fix-looped: unconditional plane, symmetric guard,
  fail-safe rule, honest docs after a runtime provenance-block proved too broad — it refused legit moat facts
  in the memory flow). Gate 5 functional verification (core: PASS — plane totality real, boundary blocks every
  realistic vector incl. nested/embedded, facts carry correct plane, contract conformant). Suite **434 green**.
- Follow-ups: work-stream B (front end) renders the planes distinctly; the UI plane visualization lands there.

## 2026-06-24 — global-regulatory-divergence corpus — Gavin's first Bucket-1 corpus  (`main`, PR #30)
- Built-By: `gavin` (reviewed/approved/merged by rohan).
- What: First contributor knowledge corpus, built dual-source (browser + EMET) per the locked METHOD. 9 cards
  (T1×2 MHRA/gov.uk regulator primaries, T2×7 HTA/secondary), themed notes, manifest with honest known-gaps,
  QUERIES.md, + the agent skill doc upgraded to corpus-first → search-the-gap. Lands at run time via K2.
- Gates: suite **381 green** · `validate-corpus.sh` **CLEAN** (all URLs resolve) · content audited CLEAN
  last pass (0 fabricated, all 3 EMET PMIDs real) · scope clean (no secrets/binaries). Branch carried the #31
  gate fix + #32 test fix (merged main before re-tier).
- Follow-ups: Gavin's remaining 5 corpora (financial-investor · kol-social-signal · patient-advocacy ·
  policy-legislative · reputational-institutional).

## 2026-06-24 — Fix: make the corpus-retrieval test corpus-agnostic (unblocks all multi-corpus PRs)  (`main`, PR #32)
- Built-By: `rohan` (engine/test fix — latent brittleness in the K2 keystone, surfaced by Gavin's PR #30 audit).
- What: `tests/test_corpus_retrieval.py::test_corpus_fact_lands_in_dossier` asserted EVERY corpus fact carried
  `field == "fda-institutional-memory"` — fine when one corpus existed, but a SECOND on-topic corpus (Gavin's
  global-regulatory-divergence surfaces Alzheimer's cards for the aducanumab query) legitimately lands its own
  facts and tripped the equality. Fixed: per-fact loop now asserts corpus-agnostic invariants (`from_corpus`,
  value/source/tier, non-empty `field`); a separate assertion proves the seeded fda corpus's facts specifically
  surface — keeps it precise + non-vacuous while tolerating additional corpora.
- Gates: verified BOTH single-corpus (suite 381 green) AND the broken two-corpus case (copied Gavin's corpus in
  → retrieval tests 4/4 OK, old assertion would have failed). Not Gavin's bug — latent in the overnight K2 test.
- **Unblocks every future corpus PR** (all 12 would have hit this). Lesson for the corpora template: retrieval
  tests must be corpus-agnostic.

## 2026-06-24 — Corpus gate: T1 allowlist extended to ex-US national regulators  (`main`, PR #31)
- Built-By: `rohan` (approver-owned gate machinery; prompted by Gavin's HELP request on PR #30).
- What: `dev/validate-corpus.sh` T1-domain rule was US-centric (`.gov`/`.edu`/PMC), so credentialed ex-US
  national-regulator *primaries* (EMA, MHRA/gov.uk, PMDA, Health Canada, TGA, Swissmedic, NMPA) failed it —
  wrongly forcing ex-US corpora to T2 vs the agent spec. Extended the T1 allowlist to those regulators
  (host-or-subdomain match, spoof-safe); HTA/reimbursement bodies (NICE/PBAC/G-BA/ICER) stay T2. METHOD.md T1
  definition updated; allowlist documented as approver-owned (add via HELP, don't edit the gate). Unblocks
  global-regulatory-divergence + future ex-US-primary corpora (policy-legislative).
- Gates: gate logic unit-tested (regulators incl. subdomains → T1; NICE/press/spoof-domain → T2); suite 381;
  audit clean. Answered + resolved Gavin's HELP request.

## 2026-06-24 — experiment-design ED-1: port design-form-agent  (`main`, PR #28)
- **Built-By: `hayes`** (his first self-opened PR — PAT works; branched off fresh main, no conflict) · merged by `rohan`.
- What: verbatim port of Matt Carey's `design-form-agent` (vendored at `vendor/`) into `tools/experiment_design/`
  — `extract.py` + `extraction_prompt.py` + `schema.py` + the golden `sample_extraction_jan6.json`; `app.py`
  (Slack bot) skipped; `vendor/` untouched. `anthropic` lazy-imported inside the tool (engine stays stdlib-only).
- Gates (auditor, both independent, isolated worktrees): reviewer **Approved** + Gate-5 **PASS** — the proprietary
  domain content (system prompt + Quiver optogenetics vocabulary + `MENUS_REFERENCE` + schema) is
  **character-for-character identical** to the vendored original (only an attribution header added); golden JSON
  byte-identical; fidelity test non-vacuous (`assertIn` substring lock + `assertEqual` on golden); no-key →
  honest `ExtractionError` (no fabricated plan); zero engine imports of anthropic/pypdf/dotenv. Suite **381 green** (+13).
- Next: **ED-2** (fill the design sheet — JSON + design MD, ± xlsx) on Hayes's queue, then his 6 semantic corpora.

## 2026-06-24 — [overnight] Task K2: corpus-first runtime retrieval (KEYSTONE)  (`main`, PR #26)
- Built-By: `rohan` (worker) · merged by `rohan` (auditor). **Bedrock — makes the corpora pay off at run time.**
- What: Bucket-1 agents now READ their knowledge corpus during `run_live`. New stdlib `corpus/reader.py`
  (deterministic overlap match on lens fields + entities, capped, robust to missing/malformed); `live_engine`
  wiring adds corpus-sourced facts (`provenance="corpus"`, `from_corpus=true`, carrying card source/tier/url)
  to the dossier, **traced** (`corpus_retrieval` event), **generic** for any agent with a `corpus/<id>/` dir;
  the live agent still runs the **gap** (corpus-first ≠ corpus-only). New `corpus` provenance label.
- Gates (auditor, both independent, isolated worktrees): reviewer **Approved** + Gate-5 **PASS** — proven: an
  aducanumab query → **5 of 14 dossier facts corpus-sourced** via `run_live` (offline, real fact dict w/ T1 +
  FDA url); generic across all 16 agents (only fda-memory has a corpus; others contribute 0, no error); both
  live dispatch + corpus_retrieval traced; **veto rule intact** (corpus facts never set a flag / touch
  veto_flags — tested); `dev/run-tests.sh` change is a clean one-line `+corpus` (not gaming the gate); stdlib +
  data boundary intact (no internal `_score` leak). Suite **368 green** (+12).
- **Significance:** with K1 (front door = live firm) + K2 (corpora read at run time), the backend is now
  end-to-end-capable on its own — corpus-grounded facts flow through the harnessed firm to `/api/run`. The 12
  delegated corpora will light up automatically as they merge. **Overnight worker scope (H + K1 + K2) COMPLETE.**

## 2026-06-24 — [overnight] Task K1: run_live service boundary + real /api/run front door (KEYSTONE)  (`main`, PR #24)
- Built-By: `rohan` (worker) · merged by `rohan` (auditor). **Bedrock — the front-door keystone.**
- What: froze the `run_live` output contract (`contracts/run_live_schema.md` + `.py` recursive validator +
  drift test) and made `serve.py`'s `/api/run` **default to the harnessed `live_engine.run_live`** (`via=engine-live`)
  — the canned scenarios + headless-claude paths kept as explicit labeled fallbacks (`?mode=canned`/`claude`).
  Honest degradation to a plan-only envelope if run_live ever raises. `live_engine.py`/`orchestrator.py`
  untouched (additive-only).
- Gates (auditor, both independent): reviewer **Approved** — contract cross-checked field-by-field vs
  `live_engine.py` (no invented/missing fields), validator real+recursive, serve routes to the real firm,
  stdlib-clean, scope-disciplined, non-vacuous tests incl. a real-run conformance test that fails on drift.
  Gate-5 **PASS** — `/api/run?mode=live` returns a genuine run_live result (fresh engagement, 71 dossier facts,
  5 partners, real synthesis), NOT canned; validator rejects broken dicts; canned fallback labeled; honest
  degradation; data boundary intact (harness guards block internal data pre-dispatch). Suite **356 green** (+13).
- **Significance:** the live harnessed firm is now reachable behind a stable contract — the integration point
  LOKA plugs into. The "front door is canned, not the live firm" gap is CLOSED.
- Follow-up (non-blocking nit): add a one-line test locking the canned *success* branch (scenario-hit +
  `_routed_from_query`) — reviewer verified it manually; worth a test later.

## 2026-06-24 — [overnight] Task H: cross-platform test hardening  (`main`, PR #22)
- Built-By: `rohan` (overnight worker session) · merged by `rohan` (auditor session).
- What: fixed 3 pre-existing cross-platform test failures — moat `test_client` derives the repo-dir name at
  runtime (no hardcoded `sapphire-capability-map`); `test_scenarios` reads files as UTF-8; `trace_view.py`
  gained `_safe_print` to tolerate a cp1252 stdout (+ a non-vacuous regression test that forces a cp1252 stream).
- Gates (auditor): suite **343 green** (+1); `_safe_print` sound + stdlib (UTF-8 path unchanged, only rescues a
  legacy codepage); moat assertion still substantive (full `/RohanOnly/moat/moat.sqlite` suffix); cp1252 test
  genuinely exercises the encode path. All green → auto-merged. First overnight PR.

## 2026-06-23 — Overnight shift setup (worker plan + briefs)  (`main`, PR #21)
- Built-By: `rohan`. Planning/docs for an autonomous overnight build run.
- What: `docs/superpowers/plans/2026-06-24-overnight-shift.md` — a dedicated rohan *worker session* (separate
  clone) builds 3 tasks serially: **H** crossplatform-test-hardening, **K1** run_live service boundary + real
  front door, **K2** corpus runtime retrieval (corpus-first→search-the-gap). Rohan's *auditor session* (this
  one) reviews + Gate-5 verifies + **auto-merges when all-green**, holds + documents anything that fails.
  Builder ≠ approver preserved (distinct sessions). Workboard rohan rows assigned to the worker.
- Decisions (Rohan): scope = K1+K2+hygiene; auto-merge if all-green; auditor stays purely reactive + AM report;
  worker self-paced (halt on scope-done / blocked / unrecoverable gate).
- Gates: docs only (342 green; audit clean).

## 2026-06-23 — LOKA end-to-end readiness prep + permanent no-Pro enforcement  (`main`, PR #20)
- Built-By: `rohan`. Docs/harness prep for tomorrow's LOKA (front end) + Quiver-tool access; no code.
- What: (1) **Readiness plan** `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md` — maps the
  end-to-end path (LOKA → `run_live` → Bucket-1 {EMET·moat·seams·corpora, corpus-first} → roundtable →
  synthesis → LOKA), the honest gaps, and the two **LOKA-independent critical-path builds**: K1 `run_live` as a
  clean service boundary (the keystone — `serve.py`'s `_run_live` is the canned path, NOT the harnessed firm)
  and K2 corpus runtime retrieval (corpora are inert until agents read them). New Quiver tools plug in via the
  existing seam pattern — no harness change needed. (2) `status/frontend-loka.md` area doc; reconciled
  `status/OVERALL.md` to reality (seams done, corpora delegated).
- **Enforcement is now permanent-no-Pro:** removed `dev/enable-branch-protection.sh` and scrubbed all
  "pending Pro / staged for Pro / for the day we go paid" language. Hooks + CODEOWNERS + `audit-history.sh`
  is the complete, permanent model (`dev/CONVENTIONS.md` §1) — do not reintroduce branch-protection talk.
- Gates: docs/harness only — no engine code (342 green); audit clean.
- Decisions surfaced to Rohan: build K1+K2 pre-LOKA (recommend yes, lead-driven); vendor LOKA into `vendor/loka/`
  vs call `run_live` as a service (decide on seeing the code).

## 2026-06-23 — Delegate the 12 semantic-agent corpora (Hayes 6 / Gavin 6)  (`main`, PR #17)
- Built-By: `rohan` (planning/assignment). Docs only.
- What: opened the `semantic-corpora` delegation per the locked dual-source method. Shared brief
  `docs/superpowers/plans/2026-06-23-semantic-corpora-delegation.md` (per-agent lens table, Pass A browser +
  Pass B self-authenticated EMET, the `dev/validate-corpus.sh` gate, mini pilot-gate = ship first/wait/batch).
  Assigned — **Hayes:** patent-ip · post-market-safety · clinical-trial-registry · payer-market-access ·
  manufacturing-cmc · dea-scheduling (after his experiment-design epic). **Gavin (his first task):**
  global-regulatory-divergence · financial-investor · kol-social-signal · patient-advocacy · policy-legislative ·
  reputational-institutional. Gavin onboarding note added (setup-contributor + watcher + first-corpus-then-wait).
- Decisions (Rohan): contributors self-authenticate BenchSci for EMET; the recommended 6/6 split.
- Gates: docs tier (no code; 342 green; audit clean). Each corpus ships as its own PR with my adversarial
  review (EMET PMIDs + T1 verbatim + the gate) before merge — same bar as the FDA-memory pilot.

## 2026-06-23 — Corpus PERFECTED: dual-source (browser + EMET) FDA-memory + locked template  (`main`, PR #16)
- Built-By: `rohan` (driven via subagents). Adds the two ingestion sources the pilot was missing and **locks
  the dual-source `METHOD.md` as the template** for the other 12.
- Browser pass: **T1 11 → 21** — 10 cards upgraded by actually loading the FDA-primary (aducanumab Dunn memo,
  tofersen/MDMA AdComm summaries, accessdata label PDFs, FDA press) with verbatim quotes. Honest about what
  stayed T2 (FDA doesn't publish CRLs; pergolide 2007 has no fetchable primary).
- EMET pass: **5 Thorough EMET queries** (auth required — Rohan logged into BenchSci; EMET hits a login wall
  otherwise) → **10 `emet-live` T2 cards** citing real PMIDs, grounding the class-safety/biomarker mechanism
  behind the precedents (5-HT2B→valvulopathy, amyloid→ARIA, NfL surrogate, SSRI pediatric suicidality,
  antipsychotic elderly mortality). Corpus now **45 cards** (35 regulatory + 10 EMET).
- Quality: adversarial verifier — **0 critical findings**; EMET PMIDs **10/10 real, on-topic, supported**
  (numbers checked vs abstracts); T1 quotes **6/6+1 verbatim** vs FDA-primary. 2 nits fixed (#39 "ApoE e4
  carriers" not "heterozygotes"; #44 aligned to its source OR 1.54). `METHOD.md` now distinguishes
  **T1/web quotes = verbatim substring** vs **EMET-card quotes = synthesized-but-faithful** (verify numbers/
  labels vs the PMID). `dev/validate-corpus.sh` documents both sources (logic unchanged, not weakened).
  Gate CLEAN 45/45; audit clean.
- **Template LOCKED.** Next: delegate Hayes 6 / Gavin 6 — each replicating the dual-source METHOD + passing
  the gate. NOTE for delegation: contributors need an authenticated EMET/BenchSci session (browser) for Pass B.

## 2026-06-23 — Bucket-1 knowledge-corpus PILOT: FDA Institutional Memory + the method  (`main`, PR #15)
- Built-By: `rohan` (driven via subagents). The pilot of a new initiative: give each Bucket-1 semantic agent a
  pre-ingested, queryable knowledge corpus so a run hits local for the stable ~70% and only searches the
  novel ~30% — cheaper, faster, grounded.
- What: `sapphire-orchestrator/corpus/fda-institutional-memory/` — 35 cited+dated claim-cards (`index.jsonl`),
  themed `notes/`, `manifest.md` (coverage map + honest gaps), `QUERIES.md` (worked checks), and `METHOD.md`
  (the repeatable recipe to replicate for the other 12). Upgraded the agent skill doc skeleton → real
  corpus-first→search-the-gap operating spec (with "AdComm is advisory; a dispositive veto needs a T1 primary
  citation; confirm a T2 card before veto"). Added **`dev/validate-corpus.sh`** — a mechanical citation-integrity
  gate (valid JSON + fields + quote≤60w; tier T1 only on a primary domain; every URL resolves or is tagged
  `unverifiable_by_fetch`; 404=hard fail, 403/timeout rescuable-by-flag).
- Quality (this is the value): an adversarial fact-check of 14 cards incl. all 5 high-stakes (aducanumab 0-10-1,
  tofersen 9-0, eteplirsen, pergolide, AXS-07) found **zero fabricated actions, zero wrong facts** — the
  regulatory memory is real. It also found a citation-hygiene defect class (a 404 URL, paraphrase-as-quote,
  press-wire-as-T1); all fixed against the new gate (which then surfaced + fixed 5 more dead/blocked URLs);
  2 repointed PMC quotes spot-verified verbatim by the controller. Corpus gate CLEAN (35/35).
- Honest limit: fda.gov/federalregister block automated fetch, so corpora lean T2; primary-but-unfetchable
  cards are tagged `unverifiable_by_fetch` and the skill doc requires confirming primary before a veto. A
  browser-capable pass to upgrade key T2→T1 is a deferred option (Rohan's call).
- Next (gated on Rohan's sign-off): delegate the other 12 — Hayes 6 / Gavin 6 — each replicating `METHOD.md`
  and passing `dev/validate-corpus.sh`. Separately, wire the runtime corpus-first→search-the-gap retrieval.

## 2026-06-23 — Vendor Matt's design-form-agent (unblock experiment-design ED-1)  (`main`, PR #14)
- Built-By: `rohan`. Per Rohan's direction ("consume Matt's full repo into Sapphire").
- What: imported a verbatim snapshot of `MatthewCarey24/design-form-agent` (private Quiver repo; upstream commit
  `afcf01b`) to **`vendor/design-form-agent/`** as the preserved-original reference (CONVENTIONS §4), with
  `VENDORED.md` (provenance + attribution to Matt Carey + how the port uses it). `.git` not included; flat
  snapshot. Secret-scanned clean (`.env.example` is placeholders only; keys read from env). No large binaries
  (largest 148 KB).
- Unblocks **`experiment-design` ED-1**: resolved Hayes's HELP request, flipped the workboard row active, and
  pointed the ED brief at `vendor/design-form-agent/` (port into `tools/experiment_design/`, domain content
  verbatim, golden-test vs the vendored `sample_extraction_jan6.json`).
- Gates: docs/vendor only — no engine code, suite unaffected (342). Audit clean.
- Hook fix (caught by dogfooding): `.githooks/pre-commit` was blocking `.env.example` (its filename rule
  `\.env\..+` matched the secret-free template). Relaxed to allow `.env.example`/`.sample`/`.template` while
  still blocking real `.env`/`.env.local`/keys; the content scan still runs on templates as a backstop.

## 2026-06-23 — g:Profiler enrichment seam — quant-fact-seams series ✅ COMPLETE  (`main`, PR #12)
- **g:Profiler seam authored by `hayes`** (`Built-By: hayes`, fresh branch off latest main — staleness fixed);
  merged by `rohan` directly (no integration branch needed — clean). Bookkeeping in PR #13.
- What: stdlib g:Profiler g:GOSt **POST** seam (`tools/geneset_enrichment_seam.py`) — enrichment over the query
  **gene set** (GO/HP/pathway terms + p-values), provenance `gprofiler`, tier **T2** (computed statistic, not a
  measured value). Introduces `genes` as a first-class `bucket1_inputs` field (the seam reads the set; other
  agents read `candidate`). Complete `output_schema` (incl. `error`); `data_boundary` guards the whole input
  blob (an internal id anywhere in the gene list blocks dispatch).
- Gates (approver, independent): Gate 1 **342 green** · Gate 2 **Approved** (3 Minor nits) · Gate 5 **PASS**
  (fact lands via `run_live` with real term IDs/p-values; schema-complete error path; honest degradation across
  6 paths; facts mock-derived; data boundary enforced on the gene LIST; non-vacuous tests).
- **Milestone: the 4-seam `quant-fact-seams` series is COMPLETE** — Sapphire's Bucket 1 now emits hard
  quantitative facts (constraint, expression, domains, enrichment) alongside EMET's narrative. Hayes's first
  feature epic, shipped through the harness end-to-end.
- Follow-ups: minor nits across the seams (p-value `:.2e`; a couple comment/assertion tightenings) — a cleanup
  pass. Next for hayes: the **experiment-design** epic, **blocked on ED-1 source** (Matt's repo) — escalated to
  Rohan; vendoring a snapshot is the plan.

## 2026-06-23 — InterPro protein-domains seam (quant-fact-seams PR-C)  (`main`, PR #11)
- **InterPro seam authored by `hayes`** (commit c4fcfcb, `Built-By: hayes`); **integrated + merged by `rohan`**
  (clean auto-merge this time; this commit also does approver bookkeeping — workboard bump, HELP answer, a
  CONTRIBUTOR_RULES clarification). Hayes credited via `Co-Authored-By`.
- What: stdlib-only Bucket-1 seam wrapping EBI's InterPro API (`tools/interpro_domains_seam.py`) — two-call
  flow (gene symbol → reviewed human UniProt accession → InterPro entries) behind one `_fetch`; emits a cited
  **T1** fact listing real domain/family IPR accessions with provenance `interpro`; complete `output_schema`
  (incl. `error`); `data_boundary` guardrail; wired into `_BUCKET1_AGENTS`+`python_fns`. Faithful to the
  gnomAD/gtex template.
- Gates (approver, independent subagents): Gate 1 **327 green** (+17) · Gate 2 reviewer **Approved** (3 Minor
  nits) · Gate 5 verifier **PASS** (interpro fact lands via `run_live`, status `ok`, real IPR accessions;
  schema-complete error path; honest degradation; facts proven mock-derived; data boundary enforced; no
  vacuous tests).
- Also in this commit: answered Hayes's HELP request (his gh-less Windows box can't `gh pr create` — sanctioned
  the push→approver-opens token-less flow; watcher runs board-only there; PAT provisioning escalated to Rohan);
  softened the CONTRIBUTOR_RULES "open your own PR" rule accordingly.
- Follow-ups: **g:Profiler (PR-D)** is the last seam. 3 Minor InterPro nits to fold into PR-D or a cleanup:
  `"1 entries"` grammar (count==1); UniProt-404-as-honest-empty comment accuracy; InterPro `page_size` for
  proteins with >25 entries (all non-blocking, self-noted).

## 2026-06-23 — Autonomous contributor operation (watcher + operating loop)  (`main`, PR #10)
- Built-By: `rohan` · merged by `rohan`. Docs + one bash script; no engine code.
- What: contributor agents now run continuously without prompting and unblock themselves.
  `dev/watch-assignments.sh <handle> <gh-user>` (run as a background Monitor) emits an event on:
  origin/main `WORKBOARD.md`/`HELP.md` change (new assignment / HELP answer / your PR merged → next task)
  and a new approver review/comment on your open PR. `CONTRIBUTOR_RULES.md` gains a §Autonomous operation
  loop; `HELP.md` answers land on `main`/the PR (the unblock trigger; pre-PR asks open a tiny `help-` PR);
  `PR_REVIEW.md` now mandates bumping the workboard on merge (the contributor's next-task signal).
- Gates: Gate 1 unaffected (no engine code; 310). Gate 2 reviewer **Approved-with-nits** — all 3 fixed:
  gh-auth preflight WARN (no silent dead channel), honest board_sig comment, mandatory workboard-bump on
  merge. Watcher functionally verified (clean start authed; WARN + board channel up when gh unauthed;
  bash-3.2/macOS-safe). Audit clean.
- Limits (honest): "runs forever" holds while the agent's session stays alive + gh stays authed; the watcher
  emits into a live session, it can't restart a dead one. Enforcement remains convention+hooks (free repo).

## 2026-06-23 — GTEx tissue-expression seam (quant-fact-seams PR-B)  (`main`, PR #9)
- **GTEx seam authored by `hayes`** (`Built-By: hayes` on his commit b13f86f); **integrated + merged by `rohan`**
  (this squash resolves a `status/WORKBOARD.md` conflict from his stale branch — see process note). Hayes credited
  via `Co-Authored-By`.
- What: stdlib-only Bucket-1 fact seam wrapping GTEx's public REST API (`tools/gtex_expression_seam.py`) —
  two-call flow (gene symbol → Ensembl gencodeId → medianGeneExpression, dataset `gtex_v8` pinned) behind one
  `_fetch`; emits a cited **T1** fact (top CNS-region median TPM + a CNS-selectivity rank computed over the
  returned tissue medians — a verifiable rank, not an invented score) with provenance `gtex`; harness agent +
  complete `output_schema` (incl. `error`); `data_boundary` guardrail; wired into `_BUCKET1_AGENTS`+`python_fns`.
  Reused the gnomAD pilot template; applied both pilot-review refinements (versioned source label; selectivity
  from real data).
- Gates (approver, independent subagents): Gate 1 **310 green** (+16) · Gate 2 reviewer **Approved** (2 Minor
  nits, non-blocking → follow-up) · Gate 5 verifier **PASS** (gtex fact lands via `run_live`, status `ok`, real
  TPM; schema-completeness/error-path ok; honest degradation on all 4 paths; selectivity proven data-derived;
  data boundary enforced; non-vacuous tests confirmed by wiring-deletion test) · no secrets.
- Process note (recurring, now addressed on the workboard): Hayes's branch was cut from a stale `main` (pre-#8)
  and he didn't open the PR — same as gnomAD. I resolved the resulting WORKBOARD conflict and opened/merged the
  PR. The workboard "start here" note now requires contributors to branch from the latest `main` (rebase if it
  moves) and to open their own PR.
- Gaps/Follow-ups: next seam = **InterPro (PR-C)**, then g:Profiler. The 2 review nits (rank 2–5 fixture;
  schema-subset assertion) are minor, fold into PR-C or a cleanup.

## 2026-06-23 — gnomAD constraint seam (quant-fact-seams PR-A pilot)  (`main`, PR #6)
- **Built-By: `hayes`** · merged by `rohan`. **First contributor PR — the harness's first external contribution.**
- What: stdlib-only Bucket-1 fact seam wrapping gnomAD's public GraphQL constraint API (`tools/gnomad_constraint_seam.py`)
  — emits cited **T1** facts (pLI, LOEUF, missense Z) with provenance `gnomad`, fires on a target gene symbol,
  degrades honestly (gene-not-found vs backend-error distinguished; never raises; never fabricates). Harness
  agent + complete `output_schema` (incl. `error`; `additionalProperties:false`), `data_boundary` guardrail,
  wired into `_BUCKET1_AGENTS` + `python_fns`. The pilot that locks the pattern for GTEx/InterPro/g:Profiler.
- Gates (approver, independent subagents): Gate 1 **294 green** (+16) · Gate 2 reviewer **Approved** (2 Minor
  nits → folded into the brief for the next seams) · Gate 5 verifier **PASS** (gnomAD fact lands via `run_live`,
  status `ok`, real numbers; **schema-completeness adversarial check passes — aso-tox trap NOT replicated**;
  data boundary structurally enforced; live API matches fixture) · provenance `gnomad` allowed; no secrets.
- Process: Hayes's Claude used `dev/HELP.md` correctly to flag 3 pre-existing cross-platform test conditions
  (verified pre-existing on clean main, scoped out) — answered + logged as `crossplatform-test-hardening` backlog.
- Gaps/Follow-ups: next seam = **GTEx (PR-B)**, then InterPro, g:Profiler — each its own PR off the pilot template.

## 2026-06-23 — Repo streamline + Hayes seam task + help desk + audit skill  (`main`, PR #5)
- Built-By: `rohan` · merged by `rohan`. Feature tier (docs/process/tooling; no engine code).
- What: (1) **Top-level cleanup** — top level now only `CLAUDE.md`+`README.md`; research-foundation docs →
  `docs/foundation/`, point-in-time reports → `docs/reports/`; every reference fixed (build scripts, CLAUDE.md
  Map, README, docs/README, sapphire-cascade links, REPORT.md's own links). (2) **quant-fact-seams reassigned
  to hayes**, rescoped to the clean-API set (gnomAD, GTEx, InterPro, g:Profiler), pilot-gate sequencing; brief
  rewritten as a self-contained, build-ready plan (seam template + worked gnomAD example + schema lesson +
  Gate-5). (3) **`dev/HELP.md`** — async Claude-to-Claude help desk, wired into the harness + a new
  CONTRIBUTOR_RULES rule 9. (4) **`sapphire-audit` admin skill** + `dev/audit-repo.sh` (macOS/bash-3.2-safe,
  python3 link parser) — found + fixed 2 broken doc links (1 a regression from the move).
- Gates: Gate 1 278 green · independent review **Approved-with-nits** (all 6 fixed) · whole-branch **Ready to
  merge** · Gate 5 verifier **PASS** (audit clean, 0 broken links, adversarial link-check discriminates, exit
  codes both directions, build-script paths resolve) · no secrets/binaries.
- Gaps/Follow-ups: `_build/build_xlsx.py` `CHECKLIST` is still a Windows abs path (pre-existing; only matters
  if regenerating the xlsx from raw input — not exercised). Hayes builds the seams next (gnomAD PR-A first).

## 2026-06-23 — Task assigned: quant-fact-seams (planning)  (`main`, PR #4)
- Built-By: `rohan` · merged by `rohan`. Planning/docs only — no code.
- What: Brief + workboard assignment for 6–10 quantitative-fact Bucket-1 seams (gnomAD constraint, GTEx,
  DepMap, AlphaMissense, ± Foldseek/InterPro/enrichment) in the `aso-tox` seam pattern — hard numbers that
  complement EMET's narrative. Reimplement select ToolUniverse Apache-2.0 wrappers as our own stdlib (`urllib`)
  seams; no ToolUniverse runtime, no Slurm. Brief: `docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md`.
- Gates: docs tier (suite untouched, 278). Implementation ships incrementally (gnomAD pilot first), each seam
  its own Standard-tier PR with Gate-5 proof the fact lands in the dossier via `run_live`.

## 2026-06-22 — Local enforcement hardening + vision + status/workboard  (`main`, PR #3)
- Built-By: `rohan` · merged by `rohan`.
- What: Repo stays **free, no GitHub Actions** (Rohan's call) → enforcement is fully local. Added
  `.githooks/pre-commit` (bio-safe secret scanner — AWS pattern word-bounded + digit-required so protein/DNA
  sequences don't false-positive); `pre-push` now runs the full suite (`dev/run-tests.sh`) on any Python
  change; `dev/audit-history.sh` is the detective backup (Built-By coverage since the convention + secret
  leaks), replacing the dropped CI; removed `dev/ci/`. Recorded Hayes (`@HayesStewart-QuiverBS`) + Gavin
  (`@GavinWongYF`) as write collaborators. Added **`docs/VISION.md`** and the **`status/`** directory
  (OVERALL + per-area + `WORKBOARD.md` per-agent assignments, Hayes/Gavin empty for now); `dev/DELEGATION.md`
  slimmed to the protocol pointing at the workboard.
- Gates: Gate 1 278 green (`dev/run-tests.sh`; no runtime code touched) · independent review
  **Approved-with-nits** (all fixed) · Gate 5 guards RUN & verified (fake gh-token / real AWS-key / aws_secret
  form BLOCKED; clean file + protein sequence ALLOWED; scanner self-exclusion; audit CLEAN; run-tests green) ·
  no secrets/binaries.
- Gaps/Follow-ups: enforcement is per-clone + `--no-verify`-bypassable (documented hard violation; audit
  catches it) — accepted residual risk of a free repo. No work assigned to Hayes/Gavin yet.

## 2026-06-22 — Strict branch enforcement + repo renamed to Sapphire  (`main`, PR #2)
- Built-By: `rohan` · merged by `rohan`.
- What: Canonical repo renamed to **`rohanaryagondi/Sapphire`**. Layered branch-rule enforcement, as strict as
  the free tier allows: client-side `.githooks/pre-push` (blocks main/protected pushes, enforces `<handle>/`
  naming + prefix==`sapphire.handle`, blocks when unset, lets tags through) and `.githooks/commit-msg`
  (requires a real `Built-By` trailer parsed via `git interpret-trailers`, cross-validated against the clone's
  handle; tight merge exemption); `dev/setup-contributor.sh` wires both; `dev/CONTRIBUTOR_RULES.md` binds
  hayes/gavin agents. CODEOWNERS → `@rohanaryagondi`. A detective `branch-guard` Action was authored but
  **parked in `dev/ci/`** (injection-safe) — GitHub Actions can't allocate a runner on this free private repo
  (jobs fail in ~4s with no steps), so an active workflow would red-X every PR; it activates with Pro.
- Gates: hooks functionally verified twice (push-to-main/wrong-name/wrong-prefix/unset-handle BLOCKED,
  own-branch + tags ALLOWED; commit without real `Built-By`, body-prose evasion, fake-"Merge", cross-handle
  all REJECTED; real trailer + real merge ACCEPTED; real `git push --dry-run` to main blocked end-to-end) ·
  independent review **Approved-with-nits** (all fixed) · independent verify **PASS** · injection-safe workflow.
- Gaps/Follow-ups: true server-side branch protection still needs **GitHub Pro** (free-tier 403) —
  `dev/enable-branch-protection.sh` applies it once upgraded; `--no-verify` is a known bypass (documented hard
  violation, caught by the Action). Need Hayes/Gavin GitHub usernames before granting collaborator access.

## 2026-06-22 — Collaborative dev harness (multi-contributor, PR-gated)  (`main`, PR #1)
- Built-By: `rohan` · merged by `rohan`.
- What: Turned the solo `dev/` harness into a 3-contributor harness (rohan · hayes · gavin), each driving
  their own Claude. Git-native attribution (branch prefix `<handle>/<slug>` + `Built-By` commit trailer +
  `dev/CONTRIBUTORS.md`); `dev/DELEGATION.md` task board + claim protocol; `dev/PR_REVIEW.md` approver
  playbook; `.github/CODEOWNERS` + PR template (gate-evidence checklist); tracked `dev/reports/<handle>/`
  (inaugural ASO-tox report migrated in). Refreshed README/METHODOLOGY/CONVENTIONS/GATES + root CLAUDE.md to
  the multi-contributor, `main`-is-bedrock model. Branch surgery: old `main` → `main-backup-2026-06-22`;
  `main` fast-forwarded to the former `Rohan` bedrock; `Rohan` retired. Dogfooded via PR #1.
- Gates: 278 tests green (docs/config-only; runtime untouched) · independent review **Approved-with-nits**
  (all findings fixed) · whole-branch integrator **Ready to merge** · no secrets/binaries.
- Gaps/Follow-ups: **GitHub branch protection BLOCKED** — private free-tier repo returns 403 for protection
  + rulesets; the sole-approver rule is convention + CODEOWNERS routing until a plan upgrade / paid Quiver
  org (decision surfaced to Rohan). Do NOT grant Hayes/Gavin write access until enforcement is resolved.
  Need Hayes/Gavin GitHub usernames. CI automation of gates is future scope.

## 2026-06-22 — ASO sequences wired into `run_live` → live aso-tox dossier facts  (Rohan)
- What: Gave `run_live(query, *, sequences=None, ...)` a sequence-input channel — the documented handoff point for the future ASO-Design tool. Sequences (explicit param, else a strict `\b[ATGC]{15,}\b` query-text extractor) thread into Bucket-1 `inputs`, so the `aso-tox` agent scores them and emits real GBR T2 facts (provenance `aso-tox`) into `discover["dossier"]`. Hardened the seam (`tools/aso_tox_seam.py`) to validate input: non-ATGC sequences are rejected (never scored), surfaced honestly in `invalid_sequences`; lowercase atgc normalized to uppercase. Extended the `aso-tox` `output_schema` in `harness/agents.json` (`invalid_sequences`+`error`, `additionalProperties:false` retained) — the load-bearing fix without which the harness silently abstained on any output carrying rejected sequences (would have dropped valid facts in the mixed case). First exercise of the dev harness (`dev/`).
- Gates: **278 tests green** · review **Approved** (independent sonnet reviewer, 3 rounds) · verify **PASS** (independent sonnet verifier RAN `run_live`: happy path 2 facts with GBR numbers matching the direct seam call; mixed valid+garbage → exactly 1 fact, status `ok`; all-garbage → 0 facts no crash; honest-empty intact; schema change proven load-bearing) · Gate 3 provenance `aso-tox` (allowed) + no secrets/binaries · Gate 4 stdlib-only runtime (`re` added) + vendor `predict.py`/`.pkl` untouched. Standard tier (no Gate 6).
- Gaps/Follow-ups: wire `run_live` to the front door (`serve.py`/Console — separate keystone task); chain the ASO-Design tool to feed its designed sequences into this channel when it lands; consider upstream sanitization of empty/whitespace strings before the seam.

## 2026-06-22 — Dev Harness established  (this change)
- What: Created `dev/` — the self-contained SDD methodology, conventions, gates, ledger, templates — plus runnable `.claude/agents/sapphire-dev-*` and the `sapphire-build` skill. Clean separation of the **dev harness** (building Sapphire) from the product **runtime harness** (`sapphire-orchestrator/harness/`). Refreshed all repo docs to current state.
- Gates: docs/process change — Gates 1–5 applied to any code touched; the harness itself dog-foods Gate 5 (a verifier confirmed the agent/skill files are well-formed and the workflow is runnable).
- Gaps/Follow-ups: adopt across all future work; consider a pre-commit hook for Gates 3–4.

## 2026-06-22 — Quiver ASO acute-tox tool integrated  (`79c1603`, `d18ae0d`)
- What: Hongkang's sequence-based ASO acute-toxicity model integrated as the callable `aso-tox` delegate. Canonical artifact in `tools/aso_tox/` (unmodified); verbatim `predict.py` runner; stdlib-only seam; harness agent + provenance `aso-tox`; wired into `live_engine` Bucket-1 (fires on ASO sequences → downstream of the future ASO Design tool). scikit-learn pinned 1.8.0 (GBR identical across 1.6.1/1.8.0).
- Gates: 268 tests green · golden-value test locks verbatim logic (Hagedorn exact, labels, GBR ordering) · stdlib runtime preserved · no secrets.
- Gaps/Follow-ups: confirm input contract + score interpretation with Hongkang; chain the ASO Design tool when it lands; chronic-tox model on the roadmap.

## 2026-06-22 — Review-driven fix pass  (`290530f`, `7c05985`)
- What: Two independent reviewers found 2 Criticals the overnight opus review missed — `must_cite_dossier` was miswired (`dossier_fields` passed in inputs, read from ctx → every persona force-abstained, roundtable was a no-op) and Q-Models output was silently dropped (no schema). Both fixed; masking tests hardened; data-honesty fixes. Roundtable verdicts 0 → 5/5.
- Gates: 252 tests green · 2-reviewer pass · 14 PMIDs verified against live PubMed.
- Gaps/Follow-ups: this is *why* Gate 5 (functional verification) exists.

## 2026-06-22 — Live harness wiring + transparency + scenarios + loop  (`e4a2bc8..9777ddd`)
- What: `live_engine.run_live` dispatches every agent + persona through `harness.run` (real moat live; other backends mockable → verified offline $0). `trace_view.py` CLI transparency. 3 new live-EMET scenarios (6 captured). Self-improvement loop running (memory/recall/blindspot/metrics).
- Gates: 250 tests green · opus whole-branch review "Ready to merge".
- Gaps/Follow-ups: wire `run_live` to the front door (serve.py/Console); real-LLM end-to-end run; broaden scenario coverage.

## (earlier) — Real internal moat; Phases 1–5
- What: Mock moat retired → real Loka CNS_DFP EP-distance substrate (`moat-real`). Earlier: the two-bucket firm end-to-end (canned), the agent harness, live EMET integration, Q-Models plumbing, the self-improvement loop. See `MORNING-REPORT.md` and `REPORT.md` for detail.
- Gates: per-task + whole-branch reviews; direction semantics verified biologically (TSC2→TSC1).
- Gaps/Follow-ups: reconcile moat rescue scoring with Loka's method (needs Loka repo + workflow doc).
