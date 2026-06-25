# Report — corpus: patient-advocacy (Gavin, 5th of 6)

**Branch:** `gavin/corpus-patient-advocacy` · **Built-By:** gavin · **Date:** 2026-06-25
**Task:** `semantic-corpora` (Gavin 6) — 5th PR.
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md` (FDA-memory worked example).

## What this PR adds
A dual-source, queryable knowledge corpus for the **Patient Advocacy Intelligence Analyst** (Bucket-1
semantic, dossier field **F1** — patient-advocacy landscape):
- `sapphire-orchestrator/corpus/patient-advocacy/index.jsonl` — **5 claim-cards**
- `…/notes/` — 1 themed note · `…/manifest.md`, `…/QUERIES.md`
- Upgraded the skill doc `architecture/bucket1/semantic/patient-advocacy.md` → **corpus-first → search-the-gap**

## Coverage (5 cards, breadth-of-method over depth)
CNS advocacy organized by **leverage point**, all cited + dated + verbatim-quoted:
- **Access:** Alzheimer's Association's campaign to overturn CMS's registry-restricted anti-amyloid coverage — advocacy shaping drug *access* (and a divergence from the skeptical KOL record).
- **FDA framework / patient voice:** FDA's ALS-specific drug-development guidance (2019) — patient-focused benefit-risk + flexible endpoints, which the organized ALS community pressed for.
- **Advocacy → FDA decision:** eteplirsen's 2016 accelerated approval ("first oligonucleotide approved based on very limited data") — the textbook DMD advocacy-influenced decision.
- **Agenda-setting scale:** Michael J. Fox Foundation ($62.4M into PD tracking tools/therapies) — scale of well-funded CNS advocacy shaping the research agenda.
- **Unmet-need grounding (1 `emet-live` card):** ALS kills within ~3 yrs of onset; riluzole extends survival only 3–6 months (PMID 21989247) — the quantified urgency behind ALS advocacy.

Communities: Alzheimer's, ALS, DMD, Parkinson's. Leverage points: access, FDA framework, FDA decision, research agenda.

## Tier split
**1 T1 / 4 T2.** T1 = FDA guidance (`fda.gov`). T2 = advocacy-org self-statements (alz.org, michaeljfox.org),
a PMC commentary, and the EMET card. (Per spec, PFDD/990 records are T1–T2; forum/social sentiment is T4 = live-only.)

## Dual-source passes
- **Pass A (browser):** loaded advocacy-org + FDA primaries in the shared Playwright browser; extracted **verbatim** quotes (alz.org, fda.gov, michaeljfox.org, PMC). fda.gov verified via the SEC/agency User-Agent.
- **Pass B (EMET):** 1 Thorough query grounding the ALS unmet need; PMID re-verified vs the PubMed abstract. EMET is intentionally thin for this advocacy agent — it grounds clinical urgency, not the advocacy facts.
  - chat: `emet.benchsci.com/chat/25c08c86-cb7a-4a4c-b2b6-c328ab702aca`

## Gate
`bash dev/validate-corpus.sh sapphire-orchestrator/corpus/patient-advocacy` → **`✓ corpus validation CLEAN`**
(5 cards; schema + tier-domain ok; all URLs resolve). Verified in a **clean (no-User-Agent) environment** — no
latent 403s. Branch synced to current `main`; suite **478 green**.

## Honest gaps (the ~30% the agent MUST harvest live)
1. **Advocacy-org funding / 990 conflicts** — the Alzheimer's Association's donors include anti-amyloid makers (Biogen, Eisai, Lilly, Genentech; reportedly ~$1.6M FY2021), which critics tie to its pro-access stance (the org denies influence). **Pull current IRS 990s (ProPublica Nonprofit Explorer) live** — figures change yearly, not pre-ingested.
2. **FDA PFDD "Voice of the Patient" reports** — indication-specific VOP PDFs not fetched this pass; ALS guidance stands in.
3. **Community/forum sentiment (T4)** — Reddit / HealthUnlocked / PatientsLikeMe — live-only, never pre-ingested.
4. **Therapeutic breadth** — AD, ALS, DMD, PD only.
5. **Anything after the retrieval window** — advocacy campaigns/funding shift; always a live call.

## Omitted for lack of a clean verbatim primary this pass (NOT fabricated)
The DMD "advocacy caused the approval" narrative is framed as documented *context*; the carded quote anchors the
limited-data/controversy (the commentary's words), not a direct causal assertion. MJFF's "largest nonprofit PD
funder / >$2B cumulative" is widely reported but not in the carded quote (which anchors the $62.4M figure on
michaeljfox.org). Exact pharma-funding figures are press/990-sourced → gap #1 (live).

## Anti-fabrication
Every quote is a verbatim substring of the fetched page (Pass A) or an abstract-verified EMET synthesis (Pass B).
No invented PMIDs, dates, or quotes. Public identifiers only. Advocacy-funding conflicts are flagged as a live
gap with the *direction* of the concern stated, never asserted with unverified figures.
