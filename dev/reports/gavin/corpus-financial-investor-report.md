# Report — corpus: financial-investor (Gavin, 2nd of 6)

**Branch:** `gavin/corpus-financial-investor` · **Built-By:** gavin · **Date:** 2026-06-24
**Task:** `semantic-corpora` (Gavin 6), corpus #2 — first batch corpus after the merged pilot (#30).
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## What this PR adds
A dual-source knowledge corpus for the **Financial & Investor Intelligence Analyst** (Bucket-1 semantic, dossier field **E2**):
- `sapphire-orchestrator/corpus/financial-investor/index.jsonl` — **6 claim-cards** (5 deal/risk events + 1 EMET deal-thesis grounding)
- `…/notes/muscarinic-schizophrenia-deals.md`, `…/notes/cns-consolidation-and-risk.md`
- `…/manifest.md`, `…/QUERIES.md`
- Upgraded skill doc `architecture/bucket1/semantic/financial-investor.md` → corpus-first → search-the-gap

## Coverage (6 cards) — CNS financial intelligence
- **Deal intel (M&A structure → implied PoS):** BMS/Karuna $14.0B (KarXT, M1/M4 muscarinic); AbbVie/Cerevel $8.7B (emraclidine, M4 PAM); J&J/Intra-Cellular $14.6B (Caplyta, approved franchise).
- **Realized risk / write-downs:** emraclidine Phase 2 EMPOWER failure (AbbVie, Nov 2024); navacaprant Phase 3 KOASTAL-1 MDD failure (Neumora, Jan 2025).
- **Deal thesis (EMET):** EMERGENT-1 (NEJM 2021, PMID 33626254) — KarXT PANSS −11.6 vs placebo (P<0.001), the muscarinic proof-of-concept behind the Karuna/Cerevel bets. PMID re-verified vs PubMed abstract.
- **Tier split:** 3 T1 (SEC 8-Ks) / 3 T2 (company PR, secondary, EMET). The spec's "T3 press" maps to the corpus's two-tier scheme as **T2** (documented in manifest).

## Gates
- `bash dev/validate-corpus.sh sapphire-orchestrator/corpus/financial-investor` → **CLEAN** (6 cards; schema+tier ok; URLs resolve).
- `bash dev/run-tests.sh` → **381 green** (corpus-retrieval tests pass with the new corpus present, per your #32 fix).

## ⚠️ Two gate quirks I hit (non-blocking — flagging for your call on hardening)
Both are environment/gate issues, **not** corpus-content issues; I worked around them honestly to get CLEAN.
1. **SEC EDGAR (`sec.gov`) returns 403 to the gate's `curl`** — SEC's fair-access policy requires a declared `User-Agent`. The gate's curl sends none, so the 3 T1 SEC cards 403'd. Fixes applied: (a) tagged them `unverifiable_by_fetch: true` (browser-loaded + verbatim-verified; the METHOD-honest flag, which rescues them on a POSIX gate run); **and** (b) for my local CLEAN, ran the gate with a scoped `CURL_HOME`/`.curlrc` giving curl the SEC-required UA (→ SEC 200, genuine verification). **Suggested hardening:** the gate's curl could send a UA (e.g. `curl -A "…"`) so SEC EDGAR T1 sources verify everywhere without per-machine config.
2. **Windows-only `\r` bug in the gate's `unverifiable_by_fetch` rescue.** The gate's Python writes `/tmp/_corpus_urls.txt` in text mode; on Windows that's CRLF, so the bash `while IFS=$'\t' read … unverif` leaves a trailing `\r` on the last field → `[ "$unverif" = "1" ]` never matches → a *tagged* 403/timeout is reported as "NOT tagged". Verified via `cat -A` (`1^M$`). Harmless on macOS/Linux (LF). Same cross-platform class as the cp1252 / clone-name issues. **Suggested hardening:** `unverif="${unverif%$'\r'}"` (or write the temp file with `newline="\n"`).

(The Neumora card: its canonical IR PR is browser-loadable but **curl-unreachable** from this environment, so I cited a faithful secondary — Psychiatric Times, curl-verifiable — with a `primary_source_note`. Quote is verbatim from the cited page.)

## Honest gaps (manifest)
10-K risk-factor language + exact emraclidine impairment $ (only qualitative here); upfront/milestone *licensing* deal structures (all 5 events are buyouts/readouts); private financings; earnings-call commentary; therapeutic breadth (schizophrenia/MDD-heavy); anything post-2026-06-24.

## Anti-fabrication
Every Pass-A quote is a verbatim substring of the cited page (SEC 8-Ks loaded in-browser; AbbVie PR; Psychiatric Times). The EMET quote is verbatim from the PMID 33626254 abstract (re-verified). No invented figures — the ~$3.5B emraclidine impairment is stated qualitatively (SEC filing not fetched); Neumora's −80% is flagged "per press."

## Next
On merge, continue the batch: kol-social-signal · patient-advocacy · policy-legislative · reputational-institutional (one PR each).
