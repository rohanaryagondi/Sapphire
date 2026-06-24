# Build Ledger

Append-only log of what shipped to `main`. Newest at the top. One entry per feature-sized change. Format:

```
## <date> — <title>   (<commit range or SHA>)
- What: one-paragraph summary.
- Gates: tests <N> green · review <verdict> · verify <verdict> · whole-branch <verdict>.
- Gaps/Follow-ups: anything deliberately deferred.
```

---

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
