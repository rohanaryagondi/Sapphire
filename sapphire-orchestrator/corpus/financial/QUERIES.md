# QUERIES — the corpus answering real Financial-Investor checks

Six realistic checks this agent runs at runtime (dossier field **E2**), answered **from the local corpus**
(citing the claim-card(s) / note). The last two show corpus-first → **search-the-gap**.

Framing (from the spec): **facts only** — disclosed terms and statements; valuation opinions are the VC
partner's job in Bucket 2. Public identifiers only.

---

### Q1. "How has big pharma priced muscarinic (M1/M4) schizophrenia assets?"
**Answer — two multi-billion-dollar bets in Dec 2023.** BMS bought Karuna for **$14.0B** ($330/share) for
KarXT [card #1]; AbbVie bought Cerevel for **~$8.7B** ($45/share) for emraclidine [card #2]. Both all-cash
buyouts of pre-approval assets → high implied PoS. See `notes/muscarinic-schizophrenia-deals.md`.

### Q2. "Did those muscarinic bets pay off?"
**Answer — split.** KarXT (BMS) was FDA-approved (Cobenfy, Sep 2024) — validated [card #1]. AbbVie's
emraclidine **failed Phase 2 EMPOWER-1/-2** (Nov 2024), missing PANSS vs placebo, triggering a large
impairment [card #3]. Same mechanism, opposite outcomes — concentration risk in single-asset M&A.

### Q3. "What's the implied-PoS read on an *approved* CNS franchise vs a pre-approval asset?"
**Answer — stage de-risks price.** J&J paid **$14.6B** ($132/share) for Intra-Cellular's **approved**
CAPLYTA (lumateperone) with MDD label-expansion upside [card #4] — a commercial-stage, lower-variance bet
vs the binary Karuna/Cerevel pre-approval deals. See `notes/cns-consolidation-and-risk.md`.

### Q4. "What's the recent failure tape in CNS/MDD that resets valuations?"
**Answer — navacaprant.** Neumora's KOR-antagonist navacaprant **missed the Phase 3 KOASTAL-1 MDD primary
endpoint (MADRS)** (Jan 2025); shares ~−80% (press), program later discontinued [card #5]. CNS/MDD remains
high base-rate failure.

### Q5. "Is the muscarinic antipsychotic mechanism actually clinically validated, or just hype?"
**Answer — validated for KarXT.** EMERGENT-1 (Phase 2, NEJM 2021): PANSS total −17.4 vs −5.9 placebo
(LSM diff −11.6; P<0.001), without D2 blockade [EMET card #6; PMID 33626254]. Mechanism real; a *second*
molecule against it (emraclidine) still failed [card #3] — validation ≠ guaranteed for every asset.

---

## Checks the corpus CANNOT answer → search the gap (the design working)

- **"What's the exact emraclidine impairment charge AbbVie booked?"**
  → **GAP.** Card #3 states it qualitatively (reported ~$3.5B); the precise figure is in AbbVie's Q4-2024/
  Jan-2025 SEC filing, **not fetched this pass** (manifest gap #1). **Pull from EDGAR.**
- **"What does the deal *structure* (upfront vs milestone) imply for a licensing deal's PoS?"**
  → **GAP.** All carded events are all-cash buyouts/readouts; **upfront/milestone licensing deals** aren't
  covered yet (gap #2). **Live search** SEC/press for CNS licensing terms.
- **"Any private-company CNS financing or a deal after 2026-06-24?"**
  → **GAP / live call.** Private rounds (Crunchbase/PitchBook) and anything post-retrieval are not in the
  snapshot (gaps #3, #6). **Live search.**
- **"What candid risk-factor language do 10-Ks use about this class?"**
  → **GAP.** This pass used 8-K event filings + PRs, not 10-K risk factors (gap #1). **Pull the 10-K.**
