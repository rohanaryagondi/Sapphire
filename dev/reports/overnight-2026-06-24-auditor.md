# Overnight shift — Auditor report (2026-06-24)

**Role:** AUDITOR (reactive). A separate "rohan worker" session built H→K1→K2; Hayes/Gavin pushed
contributor work. My job: independent review + Gate-5 verification on every PR, auto-merge what passed all
gates, hold + document what didn't, keep `status/` + `dev/LEDGER.md` current. No own build PRs (avoid merge
contention with the worker).

**Bottom line:** clean shift. Every keystone landed; **0 PRs held**; suite went 278 → **381 green**. The
backend is now end-to-end-capable on its own (live front door + corpus-first retrieval). One PR (#30) is open
and correctly parked on the contributor.

## Merged (all gated: suite green · independent review · provenance/secrets · stdlib-runtime · Gate-5 run)
| PR | What | Track |
|---|---|---|
| #16 | FDA-memory dual-source corpus (browser+EMET) + locked template | corpus method |
| #17–#21 | Delegation/onboarding/LOKA-readiness/no-Pro enforcement/worker-plan docs | prep |
| #22 | Cross-platform test hardening (clone-dir + cp1252) — **Task H** | worker |
| #24 | `run_live` service boundary + real `/api/run` front door — **K1 keystone** | worker |
| #26 | Corpus-first runtime retrieval for Bucket-1 agents — **K2** | worker |
| #28 | ED-1: port `design-form-agent` into `tools/experiment_design/` | hayes |
| #31 | Corpus gate: T1 allowlist for ex-US national regulators | rohan (fix) |
| #32 | Corpus-retrieval test made corpus-agnostic | rohan (fix) |
| (+#23/#25/#27/#29 bookkeeping) | ledger/status updates per keystone | — |

## Two fixes I authored (controller/approver scope — engine-level, not a contributor's job)
- **#31 — gate blind spot.** Gavin's HELP request surfaced that `validate-corpus.sh` only allowed T1 on US
  `.gov`/`.edu`/PMC, forcing every credentialed ex-US regulator primary (EMA/MHRA/PMDA/Health Canada/TGA/
  Swissmedic/NMPA) to T2 — contradicting the agent spec. Extended the T1 allowlist (host/subdomain match,
  spoof-safe); HTA/reimbursement bodies (NICE/PBAC/G-BA/ICER/CDA-AMC) stay T2. Also unblocks
  `policy-legislative` and any future ex-US-primary corpus. METHOD.md updated.
- **#32 — latent multi-corpus brittleness in the K2 keystone test.** `test_corpus_fact_lands_in_dossier`
  asserted every corpus fact was from `fda-institutional-memory` — true with one corpus, but a *second*
  on-topic corpus (Gavin's global-regulatory-divergence surfaces Alzheimer's cards for the aducanumab query)
  legitimately lands its own facts and tripped the equality. Made the assertion corpus-agnostic while still
  proving the seeded fda corpus surfaces. **Not Gavin's bug** — latent in the overnight K2 test; would have
  broken all 12 future corpus PRs. Verified single-corpus (381) AND the two-corpus case (copied Gavin's
  corpus in → retrieval 4/4 OK; old assertion would fail).

## Open / handoff
- **PR #30 (gavin/corpus-global-regulatory-divergence)** — content **audited CLEAN** (9 cards: 7 verified,
  2 unverifiable-by-fetch-but-confirmed, 0 wrong, 0 fabricated; all 3 EMET PMIDs real). Parked on Gavin: pull
  `main` (gets #31 + #32), re-tier regulator primaries → T1, re-run `validate-corpus.sh`, push. I merge when
  green. Instructions posted to the PR + `dev/HELP.md` answered.
- **Next contributor work:** Hayes → ED-2 (fill the design sheet) then his 6 semantic corpora; Gavin → 5
  more corpora after #30.
- **LOKA adapter** — front door + frozen `run_live` contract are ready; wire when the LOKA code lands.
- **Console UI** still renders the canned data file — `/api/run` is live but the static page needs
  re-pointing before we call the Console demo "live."

## Wind-down
Monitors disarmed (session-scoped); backup cron `f6328ad6` cancelled (overnight window closed); no AWS/cloud
resources touched (this was a pure code-audit shift — no GPU boxes). `status/OVERALL.md` + `dev/LEDGER.md`
current. Nothing left running.
