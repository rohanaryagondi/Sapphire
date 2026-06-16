# Fact Dossier Schema — the "done" definition for Bucket 1

The Research Manager judges Bucket 1 complete when the **required** fields for the engagement are filled
to the confidence bar. The Engagement Lead marks, per prompt, which fields are *required* vs *skip* —
that scoping is what makes "only run what's needed" concrete.

Every field carries: **value · source(s) · credibility tier · confidence · as-of date**. A field with
no source is not "filled" — it's a gap.

## Credibility tiers (for contradiction resolution)
`T1 regulatory/primary` (FDA label, approval letter, granted patent, SEC filing, trial registry record)
> `T2 curated DB / peer-reviewed` (EMET BEKG, ClinVar, ICER, published paper)
> `T3 reputable press / analyst` (STAT, Fierce, earnings transcript)
> `T4 social / informal` (X, Reddit, Substack, preprint discussion).
A conflict is resolved toward the higher tier; a T4-vs-T1 "contradiction" is usually just a low-tier
source being wrong, not a real conflict.

## The fields

### A. Target & mechanism *(usually required)*
- A1 target identity, modality in scope (SM / ASO / biologic / gene therapy)
- A2 internal-moat signal (Quiver EP/CRISPR) + provenance — **and any internal↔external divergence**
- A3 mechanism / pathway position, on-/off-target biology

### B. Scientific validation *(usually required)*
- B1 genetic / human evidence (GWAS, Mendelian, ClinVar)  ← EMET / semantic genetics
- B2 binding / potency / selectivity  ← Q-Models (Boltz, ion-channel FT)
- B3 functional efficacy evidence (rescue, phenotype)
- B4 ADMET / BBB / PK  ← Q-Models (ADMET-AI) + EMET

### C. Safety *(usually required)*
- C1 class & target safety liabilities (FAERS, labels, REMS)  ← EMET + Post-Market Safety
- C2 prior clinical safety signals for the class
- C3 ⛔ dispositive safety veto check (a prior CRL/withdrawal on the same flaw)  ← FDA-memory

### D. Clinical & regulatory *(required for development/diligence prompts)*
- D1 trial precedent + status (CT.gov, amendments, terminations)  ← Trial-Registry
- D2 FDA precedent / endpoint guidance / AdComm history  ← FDA-memory
- D3 ex-US regulator divergence  ← Global Regulatory
- D4 scheduling / controlled-substance status (if applicable)  ← DEA agent

### E. Competitive, IP & commercial *(required for prioritization/BD/portfolio prompts)*
- E1 ⛔ patent / freedom-to-operate  ← IP agent
- E2 competitive pipeline — who else, what stage, deals  ← Competitive/Financial
- E3 market size / prevalence
- E4 payer / reimbursement precedent  ← Payer agent
- E5 manufacturing / CMC feasibility (incl. DEA mfg for scheduled)  ← CMC agent

### F. Ecosystem / perception *(optional; on for go-to-market & franchise prompts)*
- F1 patient-advocacy landscape   F2 KOL / expert sentiment   F3 policy/legislative tailwinds   F4 institutional/press perception

## Per-prompt scoping examples
- *"Rank antipodal targets to TSC2 by druggability"* → require A, B; skip D–F.
- *"Design a Ph2 trial + predict FDA stance"* → require A2, C, D; light E.
- *"Is this program fundable / should we license it?"* → require A–E in full; F optional.
- *"Build a CNS franchise from the atlas"* → A,B,E across *many* targets; portfolio-level.

The dossier is the contract handed to Bucket 2: partners opine **only** on what's in it, and any field
they call insufficient becomes a targeted re-fetch (not a free re-run of everything).
