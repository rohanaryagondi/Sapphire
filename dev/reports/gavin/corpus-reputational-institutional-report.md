# Report — corpus: reputational-institutional (Gavin, 6th & last of 6)

**Branch:** `gavin/corpus-reputational-institutional` · **Built-By:** gavin · **Date:** 2026-06-25
**Task:** `semantic-corpora` (Gavin 6) — final PR.
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md` (FDA-memory worked example).

## What this PR adds
A dual-source, queryable knowledge corpus for the **Reputational & Institutional Perception Analyst** (Bucket-1
semantic, dossier field **F4** — institutional/press perception):
- `sapphire-orchestrator/corpus/reputational-institutional/index.jsonl` — **4 claim-cards**
- `…/notes/` — 1 themed note · `…/manifest.md`, `…/QUERIES.md`
- Upgraded the skill doc `architecture/bucket1/semantic/reputational-institutional.md` → **corpus-first → search-the-gap**

## Coverage (4 cards, breadth-of-method over depth)
The dominant CNS reputational case — the amyloid field's credibility crisis — plus the perception≠merit grounding:
- **Process integrity (T1):** the bipartisan House Oversight + E&C 18-month investigation (Dec 2022) finding FDA's Aduhelm review "atypical" and preceded by "corporate greed."
- **Sponsor data-integrity / fraud (T1):** the SEC's >$40M Cassava Sciences / simufilam enforcement (Sept 2024) — a Cassava-affiliated scientist charged for manipulating trial results.
- **Foundational-science credibility (T2):** Nature's retraction of the 2006 Lesné Aβ*56 paper (24 Jun 2024) — one of the most-cited retractions ever.
- **Perception ≠ merit (EMET, 1 `emet-live` card):** the agent's signature check — the retraction invalidated the Aβ*56 claim only; the broader amyloid hypothesis is independently supported by human genetics (familial APP/PSEN1/PSEN2 all converge on Aβ) (PMID 28350801).

Subjects: amyloid class, Biogen/FDA process, Cassava/simufilam, Lesné/Aβ*56. Headwind/tailwind tagged per card.

## Tier split & tiering decision
**2 T1 / 2 T2.** Official **government findings/actions** (House Oversight on a .gov; SEC enforcement on sec.gov) are
**primary facts → T1**; journal/establishment signals (Nature retraction) + the EMET card are **T2**; **social
commentary (spec T4) is excluded** from pre-ingestion (live-only). A reputational *perception* never overrides T1–T2 evidence.

## Dual-source passes
- **Pass A (browser):** loaded official + establishment primaries in the shared Playwright browser; extracted **verbatim** (oversight.house.gov, sec.gov, nature.com).
- **Pass B (EMET):** 1 Thorough query executing the perception-vs-merit check; PMID re-verified vs the PubMed abstract.
  - chat: `emet.benchsci.com/chat/d2f5fdbd-8ffe-4411-be94-0afbadf746e7`

## Gate
`bash dev/validate-corpus.sh sapphire-orchestrator/corpus/reputational-institutional` → **`✓ corpus validation CLEAN`**
(4 cards; schema + tier-domain ok; all URLs resolve). **Pre-emptively audited in a clean (no-User-Agent)
environment** replicating the reviewer's setup — this caught the SEC press-release card (sec.gov) 403-ing
automated fetch; it's read in-browser (quote verbatim) and now tagged `unverifiable_by_fetch: true`, stays T1
(same fix class as PR #38's line-5 review). Branch synced to current `main`; suite **478 green**.

## Honest gaps (the ~30% the agent MUST harvest live)
1. **Other CNS classes/sponsors** — psychedelics (Lykos/MDMA AdComm-misconduct + 2024 retractions), gene therapy (Sarepta's 2025 Elevidys deaths) — not carded this pass; harvest live (STAT/Reuters/Endpoints/Retraction Watch).
2. **Social commentary (T4)** — X/Substack/blog reputation signals — live-only, never pre-ingested, never overrides T1–T2.
3. **SEC litigation/integrity disclosures** beyond Cassava — pull live per sponsor.
4. **Therapeutic breadth** — amyloid/Alzheimer's-heavy; other CNS areas thin.
5. **Anything after the retrieval window** — reputation shifts fast; always a live call.

## Omitted for lack of a clean primary this pass (NOT fabricated)
The Lykos/MDMA reputational story (therapist-misconduct allegations, functional-unblinding concerns, journal
retractions) and Sarepta's gene-therapy-death reputational hit are real and important but were not carded this
pass (gap #1) — flagged for live harvest rather than asserted without a fetched primary.

## Anti-fabrication
Every quote is a verbatim substring of the fetched page (Pass A) or an abstract-verified EMET synthesis (Pass B).
No invented PMIDs, dates, or quotes. Public identifiers only. Where a primary blocks automated fetch (SEC), the
card is browser-verified + tagged `unverifiable_by_fetch`, never up- or down-tiered to dodge the gate.

---
*This is the last of Gavin's 6 semantic corpora. Ship order: global-regulatory-divergence (#30, merged) → financial-investor (#38) → policy-legislative → kol-social-signal → patient-advocacy → reputational-institutional (this).*
