# Manifest — Patient Advocacy Intelligence corpus

**Agent:** Patient Advocacy Intelligence Analyst (Bucket 1, semantic) · dossier field **F1** (patient-advocacy landscape).
**Built:** `gavin/corpus-patient-advocacy` (5th of Gavin's 6 semantic corpora; per `fda-institutional-memory/METHOD.md`).
**Retrieval window:** 2026-06-25.
**Cards:** **5** in `index.jsonl` (4 advocacy-landscape + 1 EMET unmet-need grounding) · **Notes:** 1 themed file in `notes/`.
**Tier split:** **1 T1 / 4 T2** — T1 = FDA (fda.gov) guidance; T2 = advocacy-org self-statements, a PMC commentary, and the EMET card. (Per spec, PFDD/990 records are T1–T2; forum/social sentiment is T4 = live-only.)
**Scope:** representative CNS advocacy by **leverage point** — access (Alzheimer's Association), FDA framework (ALS), an FDA decision (DMD/eteplirsen), agenda-setting scale (MJFF/Parkinson's) — + the quantified ALS unmet need. Breadth-of-method over depth (pilot).

## Dual-source method (both passes — METHOD.md Step 3)
- **Pass A (browser):** loaded advocacy-org + FDA primaries in the shared Playwright browser; extracted
  **verbatim** quotes (alz.org, fda.gov, michaeljfox.org, PMC). fda.gov verified via the CURL_HOME UA.
- **Pass B (EMET):** 1 Thorough query grounding the **unmet need** that drives ALS advocacy (survival, riluzole
  effect), PMID re-verified vs the PubMed abstract. EMET is **thin for this advocacy agent** (per the brief);
  it grounds the clinical urgency, not the advocacy facts — and demonstrates the spec's "validate against EMET" step.

## EMET pass — 1 Thorough query
| # | Query | Grounds | chat_url | Verified PMID |
|---|---|---|---|---|
| 1 | ALS survival & functional-decline burden / unmet need | ALS advocacy urgency (cards #2, #5) | `emet.benchsci.com/chat/25c08c86-cb7a-4a4c-b2b6-c328ab702aca` | 21989247 (Hardiman et al., Nat Rev Neurol 2011) |

## Coverage map — agent check types
| Check type (procedure) | Covered? | Cards |
|---|---|---|
| **Advocacy landscape** (who · org/funding · stated priorities) | ✅ | #1 Alz Assoc · #4 MJFF |
| **FDA patient voice** (PFDD / benefit-risk framework) | ✅ | #2 FDA ALS guidance |
| **Advocacy → FDA decision** | ✅ | #3 DMD/eteplirsen |
| **Funding/conflict ties color positions** (990s) | ⚠️ partial | noted in `notes/` + gap (best harvested live off current 990s) |
| **Community/forum sentiment** (T4) | ⚠️ gap | live-only (Reddit/forums — not pre-ingested) |
| **Unmet-need grounding** (EMET) | ✅ | #5 |

**Communities:** Alzheimer's (Alzheimer's Association), ALS, DMD (PPMD/community), Parkinson's (MJFF). **Leverage points:** access, FDA framework, FDA decision, research agenda.

## Source list (retrieved/verified 2026-06-25)
**FDA primary (T1):** FDA ALS drug-development guidance (fda.gov, Docket FDA-2013-N-0035, Sept 2019).
**Advocacy-org self-statements (T2):** Alzheimer's Association CMS-coverage page (alz.org); Michael J. Fox
Foundation (michaeljfox.org).
**Secondary (T2):** PMC commentary on eteplirsen's limited-data approval (PMC5312460).
**EMET grounding (T2 `emet-live`):** PMID 21989247 (Hardiman/van den Berg/Kiernan, Nat Rev Neurol 2011).

## Known gaps — the ~30% the agent MUST harvest live
1. **Advocacy-org funding/990 conflicts** — the Alzheimer's Association's top donors include anti-amyloid
   makers (Biogen, Eisai, Lilly, Genentech; reportedly ~$1.6M in FY2021), which critics tie to its pro-access
   stance (the org denies influence). **Pull current IRS 990s (ProPublica Nonprofit Explorer) live** for the
   exact, dated figures — they change yearly (not pre-ingested here).
2. **FDA PFDD "Voice of the Patient" reports** — the specific VOP report PDFs (per indication) were not
   fetched this pass; the ALS guidance stands in. Pull the indication-specific VOP live.
3. **Community/forum sentiment (T4)** — Reddit/HealthUnlocked/PatientsLikeMe attitudes — live-only, never pre-ingested.
4. **Therapeutic breadth** — AD, ALS, DMD, PD only; epilepsy, migraine, psychiatry advocacy absent.
5. **Anything after the retrieval window** — advocacy campaigns/funding shift; always a live call.

## Omitted for lack of a clean verbatim primary this pass (NOT fabricated)
The DMD advocacy-influenced-FDA narrative is framed as documented *context*; the card's verbatim quote anchors
the limited-data/controversy (the commentary's words), not a direct "advocacy caused the approval" assertion.
MJFF's "largest nonprofit Parkinson's funder / >$2B cumulative" is widely reported but not in the carded
quote (which anchors the $62.4M figure on michaeljfox.org). Exact pharma-funding figures are press/990-sourced
→ gap #1 (live).
