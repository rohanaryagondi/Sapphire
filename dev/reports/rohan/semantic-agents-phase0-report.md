# WO-6 Phase 0 — PR report (semantic agents: corpus structural fixes)

**Branch:** `rohan/semantic-agents-phase0` · **Built-By:** rohan · **Tier:** Feature
**Spec:** `dev/work-orders/WO-6-semantic-agents.md` (Phase 0) + workboard row `semantic-agents-phase0`
**For:** Head Claude to gate + merge (I do not self-merge).

## Goal
Unblock the 13 Bucket-1 semantic agents' corpus loading — the 3 structural Phase-0 tasks. (Phase 1 — the
per-agent 3-dimension deepening, starting `clinical-trial-registry` — is queued separately, after this merges.)

## What shipped
**Task 1 — fixed the 3 corpus ID↔dir mismatches (rename, spec-preferred).** The engine ids are the short forms;
the corpus dirs used long names, so `has_corpus(id)` never matched and K2 silently skipped them. `git mv` (history
preserved): `corpus/financial-investor → financial`, `kol-social-signal → kol-social`,
`reputational-institutional → reputational`. In-dir `manifest.md` headers updated. The 3 long-named **spec files**
were kept (agents.json points at them) but their internal corpus-path **links** were updated to the new short dirs
(fixes the Gate-2 nit that they'd 404).

**Task 2 — first cited corpus for the 2 ungrounded agents** (`payer`, `manufacturing-cmc`), 5 real cited cards
each, built per the locked dual-pass METHOD (curated JSONL, real fetched public records, verbatim quotes):
- `payer/` — 2× T1 CMS (`cms.gov` NCD/coverage) + 3× T2 ICER (HTA bodies forced T2 per the gate). e.g. ICER
  lecanemab HBPB, CMS NCD 200.3, CMS Leqembi coverage statement.
- `manufacturing-cmc/` — 5× T1 FDA (`fda.gov` warning letters / DMF / inspections dashboard). Cangene, Sun Pharma,
  Intas warning letters; FDA DMF page; FDA Inspections Dashboard (403 → honestly tagged `unverifiable_by_fetch`).
- Each corpus ships the standard set (`index.jsonl` + `manifest.md` + `QUERIES.md` + `notes/`); manifests log
  honest known-gaps (NICE lecanemab appeal pending; no ASO-specific CMO warning letters found; EIRs require FOIA).
- Both pass `dev/validate-corpus.sh` (every non-403 URL resolves HTTP 200; invariants; quote ≤60 words; T1 only on
  primary `*.gov`).

**Task 3 — guard test** `corpus/tests/test_corpus_id_match.py` (stdlib, offline): derives agent ids from
`_BUCKET1_AGENTS` (authoritative) and corpus dirs from disk; asserts no orphan dir (a misnamed dir ⇒ silent K2
skip), every corpus dir loads ≥1 card via the reader, `has_corpus` True for each, plus explicit pins for the 5
fixed/added agents. **Non-tautology proven** (Gate 5): renaming a corpus dir wrong makes it FAIL with the right
error; it fails on pre-fix main (old long names are orphans) and passes now.

## Gate evidence
- **Gate 1 — full suite GREEN: 858 tests** (`bash dev/run-tests.sh`: contracts 52 · harness 109 · emet 76 ·
  memory 14 · selfimprove 20 · moat 95 · corpus 12 · tests 376 · frontend 67 · frontend2 37). +25 from the
  Phase-0 corpus/guard tests and the merged #139 tests.
- **Gate 2 — independent review: APPROVED** (different agent than the implementer). Independently live-verified 3
  corpus quotes verbatim against `icer.org` / `cms.gov` / `fda.gov` (all HTTP 200); confirmed tiering correctness,
  no invented PMIDs/URLs/figures, honest known-gaps, and the guard test's teeth. Engine untouched, stdlib-only.
- **Gate 5 — independent functional verification: PASS** (different agent). Ran K2 `read_corpus` for all 5 agents
  (`has_corpus`=True each); proved the guard test non-tautological by a destructive rename (failed correctly,
  restored, tree clean); re-fetched 3 card URLs and confirmed quotes verbatim on the live pages; confirmed
  honest-abstain on an off-scope query (0 cards) and `[]`/`has_corpus`=False for a nonexistent agent; full suite
  green.
- **Gate 3** — no secrets/keys/binaries committed; public identifiers only; provenance honest.
- **Gate 4** — engine stays stdlib-only: `corpus/reader.py` and `live_engine.py` gained no third-party import (the
  corpus is curated JSONL; no HTTP client entered the engine).

## Honesty notes (important — read these)
- **A regression I caught that the implementer mis-reported.** The implementer's first pass reported "3 pre-existing
  test failures, deviations: none." I verified against clean `origin/main`: only 2 were pre-existing
  (`test_moat_real_provenance`, `test_personas_simulated_moat_stays_real` — environmental: no
  `RohanOnly/moat/moat.sqlite` on the build box). The **third**, `TestBatchBucket1::test_batched_agents_land_facts_and_are_stamped`,
  passed on clean main and FAILED on the branch — i.e. **my change introduced it**. Root cause (correct behavior,
  stale test): `_batch_bucket1` skips agents where `has_corpus(aid)` is True; Phase 0 grounded all 13 semantic
  agents, so the batch path is now empty in production → no "batched" facts. The test was green on main only
  *because of* the very ID-mismatch bug we fixed. Fixed by monkeypatching `live_engine.has_corpus` in that test
  (via `addCleanup`) so the batch mechanism is exercised independent of grounding state — **no engine code changed**.
- **The 3 moat-DB environmental failures were resolved by building the real moat DB** locally
  (`python _build/build_moat_db.py` from the CNS_DFP parquet → gitignored `RohanOnly/moat/moat.sqlite`), so the
  full suite is genuinely green (858) rather than "green except env." The DB is **not** in this PR (gitignored);
  Head's gating environment needs the moat DB present for the 2 moat-provenance + 1 frontend2-plane tests to pass
  (the frontend2-plane one is the known gavin item from the 2026-06-28 HELP.md).
- **Merged `origin/main` #139** ("parallel Bucket-1 dispatch via ThreadPoolExecutor") into the branch — clean
  auto-merge; re-verified the batch fix still holds after #139's dispatch changes (suite green).

## Architectural finding (for the perf/parallelization WO — not resolved here)
Now that all 13 semantic agents are grounded, **`_batch_bucket1` (Opt-2 batch path) has no production agents to
batch** — it batched only corpus-less claude-subagent agents, and there are none left. This is a finding for the
perf WO (`rohan/claude-p-parallel` / #139), not a Phase-0 change. Noted in `corpus/payer/manifest.md`.

## Deferred to Phase 1 (documented, non-blocking — both gates agreed)
- **`financial` corpus retrievability:** the pre-existing `financial` cards use domain field names
  (`company`/`event`/`deal_structure`/…) not in `reader._MATCH_FIELDS`, so they're findable on terms in
  `claim`/`quote` (CNS/deal terms hit) but not on arbitrary financial terms (e.g. the spec's example "SEC filing"
  returns 0). Phase 0 made it *load* (the DoD); deepening + adding those fields to `_MATCH_FIELDS` is a Phase-1
  reader/deepening item (touches shared retrieval behavior — deliberately not expanded into Phase 0).
- `manufacturing-cmc` card 5's quote is a thin dashboard label (correctly tagged + accurate) — Phase-1 deepening.
- Batch-test import pattern — cosmetic, no fix needed.

## Files changed
- Renames: `corpus/{financial-investor→financial, kol-social-signal→kol-social, reputational-institutional→reputational}/`
  (index.jsonl/manifest.md/QUERIES.md/notes/ moved; manifest headers updated).
- New: `corpus/payer/` + `corpus/manufacturing-cmc/` (index.jsonl/manifest.md/QUERIES.md/notes/);
  `corpus/tests/test_corpus_id_match.py`.
- Edits: `tests/test_live_engine.py` (batch-test monkeypatch fix); `architecture/bucket1/semantic/{financial-investor,kol-social-signal,reputational-institutional}.md` (corpus-path links → short dirs); `corpus/payer/manifest.md` (architectural note).
- Engine source (`live_engine.py`, `corpus/reader.py`) **untouched** by Phase 0 (the #139 changes to live_engine.py are the merge, gated separately).

## DoD checklist
- [x] 3 corpus ID mismatches fixed; all corpus-having agents load via K2 (no silent skip)
- [x] `payer` + `manufacturing-cmc` have a first cited corpus (validate-corpus.sh clean)
- [x] guard test green + proven non-tautological
- [x] full suite green (858) · data-boundary + secrets clean · engine stdlib-only
- [x] Gate 2 Approved · Gate 5 PASS (both independent of the implementer)
