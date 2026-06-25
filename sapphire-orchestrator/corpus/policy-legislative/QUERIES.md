# QUERIES — the corpus answering real Policy-Legislative checks

Six realistic checks this agent runs at runtime (dossier field **F3**), answered **from the local corpus**
(citing the claim-card(s) / note). The last two show corpus-first → **search-the-gap**.

Framing (from the spec): **facts only** — what's introduced/enacted and who's pushing; don't predict passage
as fact. Public sources only. Hand DEA-scheduling and pricing-detail to the respective agents.

---

### Q1. "What US policy gates patient access to anti-amyloid Alzheimer's drugs?"
**Answer — the CMS CED coverage policy.** Medicare covers anti-amyloid antibodies that get traditional FDA
approval only "under coverage with evidence development (CED)" — i.e. registry participation [card #1, CMS
2022]. **Impact:** an access/reimbursement headwind specific to this CNS class. See `notes/`.

### Q2. "Are CNS drugs exposed to US Medicare price negotiation yet?"
**Answer — yes.** The IRA negotiation program's 2nd cycle (selected Jan 2025; prices 2027) includes **Vraylar**
(cariprazine) and **Austedo** (deutetrabenazine) [card #2]. **Impact:** marketed CNS franchises now face direct
US price-setting once eligible.

### Q3. "Does the IRA disadvantage small-molecule CNS programs specifically?"
**Answer — yes, structurally.** Small molecules are negotiation-eligible at 7 years post-approval vs 11 for
biologics (the "pill penalty") [card #4, KFF citing the IRA]. **Impact:** a shorter pre-negotiation window
discourages small-molecule R&D — and CNS is overwhelmingly small-molecule. Fix attempt: EPIC Act (H.R. 1492).

### Q4. "Did the Aduhelm controversy change FDA's accelerated-approval rules?"
**Answer — yes, via FDORA (2022).** It set up an Accelerated Approval Coordinating Council (Section 3210) and
tightened confirmatory-trial expectations; FDA still "require[s]…studies to confirm the anticipated clinical
benefit" [card #3, FDA]. **Impact:** a higher bar for surrogate-based CNS accelerated approvals.

### Q5. "Why do coverage bodies call the anti-amyloid benefit 'too small'?"
**Answer — the effect size is below clinician MCIDs.** Lecanemab slowed CDR-SB by just −0.45 points over 18
months [EMET card #5, van Dyck 2022], vs MCIDs of ~0.98 (MCI) / 1.63 (mild dementia) [EMET card #6, Lanctôt
2025]. **Impact:** this gap is the biomedical crux of CED (US) and NICE/EMA scrutiny — links policy to the science.

---

## Checks the corpus CANNOT answer → search the gap (the design working)

- **"What's the exact statutory text / current status of the EPIC Act or the IRA negotiation subsection?"**
  → **GAP.** congress.gov was Cloudflare-blocked this pass (manifest gap #1); statute facts are via CMS/FDA/KFF.
  **Fetch bill text/status live** (Congress.gov API).
- **"Who is lobbying on CNS drug pricing, and how much?"**
  → **GAP.** No power-signal (OpenSecrets/LDA) data this pass (gap #2). **Live search.**
- **"What is the EU pharma-legislation reform doing to orphan/CNS incentives?"**
  → **GAP.** US-only this pass (gap #3). **Live (eur-lex.europa.eu / EC).**
- **"Any policy change after the retrieval window (new final rule, EO, vote)?"**
  → **Always a live call.** The corpus is a snapshot (gap #6).
