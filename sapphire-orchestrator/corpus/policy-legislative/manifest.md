# Manifest — Policy & Legislative Intelligence corpus

**Agent:** Policy & Legislative Intelligence Analyst (Bucket 1, semantic) · dossier field **F3** (policy/legislative tailwinds & headwinds).
**Built:** `gavin/corpus-policy-legislative` (3rd of Gavin's 6 semantic corpora; per `fda-institutional-memory/METHOD.md`).
**Retrieval window:** 2026-06-24/25.
**Cards:** **6** in `index.jsonl` (4 policy events + 2 EMET policy-grounding) · **Notes:** 1 themed file in `notes/`.
**Tier split:** **3 T1 / 3 T2** — T1 = CMS/FDA primaries (`cms.gov`, `fda.gov`); T2 = KFF policy analysis + 2 EMET cards.
**Scope:** a representative slice of current US policy that moves CNS development/pricing — coverage gating, price negotiation reaching CNS drugs, the small-molecule "pill penalty," and accelerated-approval reform. Breadth-of-method over depth (pilot). US-focused (EU/state policy = gap).

## Dual-source method (both passes — METHOD.md Step 3)
- **Pass A (browser):** loaded CMS/FDA primaries (cms.gov, fda.gov) + a KFF analysis in the shared Playwright
  browser; extracted **verbatim** quotes. **congress.gov is Cloudflare-blocked to automation** ("Just a
  moment…"), so the statutory "pill penalty" is cited via KFF (faithful T2) with the statute (P.L. 117-169)
  named — see gaps.
- **Pass B (EMET):** 1 Thorough query → 2 `emet-live` cards, both PMIDs re-verified vs the PubMed abstract.
  EMET is **thin for a pure policy agent** (per the brief) — but here it materially grounds *why* the coverage
  policy exists: the lecanemab effect size (−0.45 CDR-SB) vs the clinician MCID (0.98–1.63). Honest, non-redundant.

## EMET pass — 1 Thorough query
| # | Query | Grounds | chat_url | Verified PMIDs |
|---|---|---|---|---|
| 1 | Lecanemab CDR-SB effect magnitude & clinical-meaningfulness (MCID) debate | #1 CMS CED + the coverage debate | `emet.benchsci.com/chat/a4b68c31-9491-4f45-8cfc-1499bfd0fe5e` | 36449413 (van Dyck, CLARITY AD), 40225240 (Lanctôt, MCID) |

## Coverage map — agent check types
| Check type (procedure) | Covered? | Cards |
|---|---|---|
| **Drug-pricing policy** (IRA negotiation, exclusivity) | ✅ | #2 Vraylar/Austedo negotiation · #4 pill penalty |
| **Coverage / reimbursement rulemaking** (CMS) | ✅ | #1 anti-amyloid CED |
| **FDA review-pathway policy** (accelerated approval) | ✅ | #3 FDORA accelerated-approval reform |
| **Program impact** (timeline / exclusivity / pricing) | ✅ | all (program_impact field) |
| **Biomedical basis behind a policy** (EMET) | ✅ | #5/#6 (effect size vs MCID → coverage gating) |
| **Power signals** (lobbying spend, coalitions) | ⚠️ gap | none this pass (OpenSecrets/LDA — live) |

**Bodies:** CMS, FDA, Congress (IRA, FDORA). **CNS drugs touched:** lecanemab/donanemab (coverage), Vraylar
(cariprazine), Austedo (deutetrabenazine). **Levers:** coverage (CED), price negotiation, exclusivity window,
accelerated approval.

## Source list (retrieved/verified 2026-06-24/25)
**Primary (T1):** CMS press releases (cms.gov) — anti-amyloid CED coverage; 2nd-cycle negotiation selected
list (Vraylar/Austedo). FDA Accelerated Approval Program (fda.gov) — FDORA Section 3210 + confirmatory-trial
framework.
**Policy analysis (T2):** KFF — IRA small-molecule (7-yr) vs biologic (11-yr) negotiation-eligibility ("pill penalty").
**Biomedical grounding (EMET, T2 `emet-live`):** PMID 36449413 (van Dyck, *NEJM* 2022, CLARITY AD),
PMID 40225240 (Lanctôt, *Alz & Dementia: TRCI* 2025, MCID). URLs `pubmed.ncbi.nlm.nih.gov/<pmid>/`.

## Known gaps — the ~30% the agent MUST still search live
1. **congress.gov primaries** — Cloudflare-blocked to automation this pass (bill text/status for the IRA,
   FDORA, EPIC Act H.R. 1492, FDA Modernization Act 2.0). Statute facts are cited via CMS/FDA/KFF; re-fetch
   bill text/status live (or via the Congress.gov API) for T1 statutory anchoring.
2. **Power signals** — lobbying spend (OpenSecrets/Senate LDA), PhRMA/BIO coalitions — not covered; live.
3. **EU / ex-US policy** — EU pharma-legislation reform (eur-lex.europa.eu), state laws — not covered.
4. **DEA scheduling bills** — deliberately deferred to the `dea-scheduling` agent (hand-off, not duplicated).
5. **Committee hearings/testimony** (Senate HELP, House E&C) — not mined this pass.
6. **Anything after the retrieval window** — policy status changes (votes, final rules, EO actions) — always live.

## Omitted for lack of a verifiable (loadable) primary this pass (NOT fabricated)
The FDORA "confirmatory trial must be underway before approval" + expedited-withdrawal specifics are
described in `program_impact` but the card's verbatim quote is the fda.gov accelerated-approval + Section-3210
text (the statutory subsection text lives on congress.gov, Cloudflare-blocked). The EPIC Act (H.R. 1492)
status is named, not quoted (congress.gov blocked).
