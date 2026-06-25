# Report — corpus: policy-legislative (Gavin, 3rd of 6)

**Branch:** `gavin/corpus-policy-legislative` · **Built-By:** gavin · **Date:** 2026-06-25
**Task:** `semantic-corpora` (Gavin 6) — 3rd PR (after global-regulatory-divergence #30 merged, financial-investor #38).
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md` (FDA-memory worked example).

## What this PR adds
A dual-source, queryable knowledge corpus for the **Policy & Legislative Intelligence Analyst** (Bucket-1
semantic, dossier field **F3** — policy/legislative tailwinds & headwinds):
- `sapphire-orchestrator/corpus/policy-legislative/index.jsonl` — **6 claim-cards**
- `…/notes/` — 1 themed note
- `…/manifest.md`, `…/QUERIES.md`
- Upgraded the skill doc `architecture/bucket1/semantic/policy-legislative.md` → **corpus-first → search-the-gap**

## Coverage (6 cards, breadth-of-method over depth)
US policy levers that move CNS development/pricing, all cited + dated + verbatim-quoted:
- **Coverage/reimbursement rulemaking (CMS):** anti-amyloid Coverage with Evidence Development NCD (2022) — registry-gated Medicare coverage for the whole anti-amyloid class.
- **Drug-pricing policy (IRA negotiation):** 2nd-cycle Medicare Drug Price Negotiation list (Jan 2025) reaching two CNS drugs — **Vraylar** (cariprazine) and **Austedo** (deutetrabenazine).
- **FDA review-pathway policy:** FDORA (2022) accelerated-approval reform — Section 3210 Coordinating Council + confirmatory-trial framework, tightened post-aducanumab.
- **Exclusivity/structural policy:** the IRA small-molecule "**pill penalty**" (7-yr vs 11-yr negotiation eligibility) — a structural headwind for the overwhelmingly small-molecule CNS field; EPIC Act (H.R. 1492) named as the proposed fix.
- **Biomedical basis behind the policy (EMET, 2 `emet-live` cards):** lecanemab CDR-SB effect (−0.45) vs clinician MCIDs (0.98 / 1.63) — the effect-size-vs-threshold gap that *drives* CED and HTA non-reimbursement (PMIDs 36449413, 40225240).

Bodies: CMS, FDA, Congress (IRA, FDORA). Levers: coverage (CED), price negotiation, exclusivity window, accelerated approval.

## Dual-source passes
- **Pass A (browser):** loaded CMS/FDA primaries (cms.gov, fda.gov) + a KFF analysis in the shared Playwright browser; extracted **verbatim** quotes. **congress.gov is Cloudflare-blocked to automation** ("Just a moment…"), so the statutory "pill penalty" is cited via KFF (faithful T2) with the statute (P.L. 117-169) named — see gaps.
- **Pass B (EMET):** 1 Thorough query → 2 `emet-live` cards; **both PMIDs re-verified against the PubMed abstract**. EMET is intentionally thin for a pure-policy agent, but here it materially grounds *why* the coverage policy exists (the effect-size debate). Honest, non-redundant.
  - chat (effect size vs MCID): `emet.benchsci.com/chat/a4b68c31-9491-4f45-8cfc-1499bfd0fe5e`

## Tier split
**3 T1 / 3 T2.** T1 = CMS/FDA primaries (`cms.gov`, `fda.gov` — on the gate allowlist). T2 = KFF policy analysis + the 2 EMET cards.

## Gate
`bash dev/validate-corpus.sh sapphire-orchestrator/corpus/policy-legislative` → **`✓ corpus validation CLEAN`**
(6 cards parsed; schema + tier-domain ok; all URLs resolve). Verified in a **clean (no-User-Agent) environment**
replicating the reviewer's setup — no latent 403s. Branch synced to current `main`; suite **478 green**.

## Honest gaps (see manifest — the ~30% the agent MUST still search live)
1. **congress.gov primaries** — Cloudflare-blocked this pass (bill text/status for IRA, FDORA, EPIC Act H.R. 1492, FDAMA 2.0). Statute facts cited via CMS/FDA/KFF; re-fetch live (or via the Congress.gov API) for T1 statutory anchoring.
2. **Power signals** — lobbying spend (OpenSecrets / Senate LDA), PhRMA/BIO coalitions — not covered; live.
3. **EU / ex-US & state policy** — EU pharma-legislation reform, state laws — not covered.
4. **DEA scheduling bills** — deliberately deferred to the `dea-scheduling` agent (hand-off, not duplicated).
5. **Committee hearings/testimony** (Senate HELP, House E&C) — not mined this pass.
6. **Anything after the retrieval window** — votes, final rules, EO actions — always live.

## Anti-fabrication
Every quote is a verbatim substring of the fetched page (Pass A) or an abstract-verified synthesis of the EMET
answer (Pass B). No invented PMIDs, dates, or quotes. Public identifiers only. Where a primary couldn't be
fetched (congress.gov), the fact is cited to a faithful T2 with the statute named — never up-tiered or fabricated.
