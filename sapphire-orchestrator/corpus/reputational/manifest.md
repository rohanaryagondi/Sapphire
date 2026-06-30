# Manifest — Reputational & Institutional Perception corpus

**Agent:** Reputational & Institutional Perception Analyst (Bucket 1, semantic) · dossier field **F4** (institutional/press perception).
**Built:** `gavin/corpus-reputational-institutional` (6th and LAST of Gavin's 6 semantic corpora; per `fda-institutional-memory/METHOD.md`). **Corpus dir:** `corpus/reputational/` (renamed from `corpus/reputational-institutional/` — Phase 0 ID fix, WO-6).
**Retrieval window:** 2026-06-25.
**Cards:** **4** in `index.jsonl` (3 reputational events + 1 EMET perception-vs-merit check) · **Notes:** 1 themed file in `notes/`.
**Tier split:** **2 T1 / 2 T2** — T1 = official .gov findings/actions (congressional report; SEC enforcement); T2 = a journal retraction + the EMET card. (Spec tiers press/institutional **T3** → corpus **T2**; social **T4** = live-only. Official .gov investigations/enforcement are primary facts → T1.)
**Scope:** the dominant CNS reputational case — the amyloid field's credibility crisis (process scandal · fraud · foundational retraction) — plus the crucial **perception≠merit** grounding. Breadth-of-method over depth (pilot); other classes/sponsors are gaps.

## Tiering decision
The spec tiers press/institutional **T3** and social **T4**; the corpus gate is **T1/T2**. Mapping: official
**government findings/actions** (House Oversight congressional report on .gov; SEC enforcement on sec.gov) are
**primary facts → T1**; **journal/establishment** signals (a Nature retraction) and the EMET card are **T2**;
**social commentary (T4)** is excluded from pre-ingestion (live-only). Rule kept: a reputational *perception*
is not a scientific fact and never overrides T1–T2 evidence.

## Dual-source method (both passes — METHOD.md Step 3)
- **Pass A (browser):** loaded official + establishment primaries in the shared Playwright browser, extracted
  **verbatim** (oversight.house.gov, sec.gov [via CURL_HOME UA], nature.com).
- **Pass B (EMET):** 1 Thorough query executing the agent's **perception-vs-merit** check (does the Lesné
  retraction undermine the amyloid hypothesis?), PMID re-verified vs the PubMed abstract. EMET here directly
  serves the agent's rule that perception ≠ scientific merit.

## EMET pass — 1 Thorough query
| # | Query | Serves | chat_url | Verified PMID |
|---|---|---|---|---|
| 1 | Amyloid-hypothesis status after the Lesné retraction (independent genetic support?) | the perception≠merit distinction (card #4) | `emet.benchsci.com/chat/d2f5fdbd-8ffe-4411-be94-0afbadf746e7` | 28350801 (Lanoiselée et al., PLoS Med 2017) |
**Finding:** the retraction invalidated the Aβ*56 claim only; the broader amyloid hypothesis is independently supported by human genetics (familial APP/PSEN1/PSEN2 mutations all converge on Aβ; the protective APP A673T variant, PMID 25531812).

## Coverage map — agent check types
| Check type (procedure) | Covered? | Cards |
|---|---|---|
| **Class/field credibility** (scandal/retraction/hype) | ✅ | #1 Aduhelm · #3 Lesné retraction |
| **Sponsor track record / data integrity** | ✅ | #2 Cassava (SEC) |
| **Press/institutional narrative** | ✅ | #1–#3 (congressional, SEC, Nature) |
| **Perception ≠ scientific merit** (validate via EMET) | ✅ | #4 |
| **Headwinds/tailwinds** (FDA scrutiny, partner/recruitment risk) | ✅ | headwind_tailwind field on each card |
| **Social commentary (T4)** | ⚠️ gap | live-only (not pre-ingested) |

**Subjects:** amyloid class, Biogen/FDA process, Cassava/simufilam, Lesné/Aβ*56. **All CNS/Alzheimer's** (a scope limit — see gaps).

## Source list (retrieved/verified 2026-06-25)
**Official .gov primary (T1):** U.S. House Committee on Oversight press release (oversight.house.gov, Dec 2022);
SEC press release 2024-151 (sec.gov, Sept 2024).
**Establishment (T2):** Nature retraction notice (nature.com, 24 Jun 2024).
**EMET grounding (T2 `emet-live`):** PMID 28350801 (Lanoiselée et al., PLoS Med 2017).

## Known gaps — the ~30% the agent MUST harvest live
1. **Other CNS classes/sponsors** — psychedelics (Lykos/MDMA: AdComm misconduct allegations + 2024
   *Psychopharmacology* retractions), gene therapy (Sarepta's 2025 Elevidys deaths / platform-credibility),
   etc. — not carded this pass; **harvest live** (STAT/Reuters/Endpoints/Retraction Watch).
2. **Social commentary (T4)** — X/Substack/blog reputation signals — live-only, never pre-ingested, never overrides T1–T2.
3. **SEC litigation/integrity disclosures** beyond Cassava — pull live per sponsor.
4. **Therapeutic breadth** — amyloid/Alzheimer's-heavy; other CNS areas thin.
5. **Anything after the retrieval window** — reputation shifts fast; always a live call.

## Omitted for lack of a clean primary this pass (NOT fabricated)
The Lykos/MDMA reputational story (therapist-misconduct allegations, functional-unblinding concerns, journal
retractions) and Sarepta's gene-therapy-death reputational hit are real and important but were not carded
this pass (gap #1) — flagged for live harvest rather than asserted without a fetched primary.
