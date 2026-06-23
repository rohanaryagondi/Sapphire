# QUERIES — the corpus answering real FDA-memory checks

Six realistic checks this agent runs at runtime, answered **from the local corpus** (citing the
claim-card(s) / note). The last two show the corpus-first → **search-the-gap** behavior explicitly: where
the corpus can't answer, it says so, and that *is* the gap the agent escalates to a live web/EMET call.

Classification convention (from the spec): **`precedent`** = informative, shapes the path · **`veto`** =
dispositive prior FDA rejection of the *same* flaw (requires a **T1** citation to raise as dispositive).

---

### Q1. "Has the FDA rejected an amyloid-targeting Alzheimer's drug, and on what basis?"
**Answer — yes, twice over, but with a decisive nuance. `precedent` (not a clean veto).**
- The PCNS AdComm voted **0-10-1** against aducanumab's pivotal evidence (Nov 2020) over *discordant*
  pivotal trials — yet FDA still granted accelerated approval on the amyloid surrogate (June 2021), later
  discontinued [cards: aducanumab adcomm_vote 2020-11; aducanumab approval 2021-06].
- Lecanemab then won a **unanimous** AdComm and traditional approval on a single clean confirmatory trial
  (CLARITY AD) [cards: lecanemab adcomm_vote 2023-06; lecanemab approval 2023-07].
**Implication surfaced:** the amyloid *target class* is not a veto — the discriminator is a convincing,
non-discordant pivotal trial. A program leaning on post-hoc subgroups from discordant trials should expect
intense scrutiny. See `notes/advisory-committee.md` + `notes/endpoint-precedent.md`.

### Q2. "Is plasma neurofilament (NfL) an FDA-accepted surrogate for accelerated approval in ALS?"
**Answer — yes. Strong `precedent` (supports, doesn't veto).**
Tofersen (Qalsody, SOD1-ALS) was accelerated-approved Apr 2023 on plasma **NfL** reduction; the AdComm
voted **9-0** that NfL reduction is "reasonably likely to predict clinical benefit" even though the VALOR
primary clinical endpoint missed [cards: tofersen adcomm_vote 2023-03; tofersen approval 2023-04].
**Implication:** an NfL-led genetic-ALS program can cite this precedent directly; a program relying on
direct functional benefit cannot lean on it, and the accelerated approval carries a mandatory confirmatory
trial (ATLAS). See `notes/endpoint-precedent.md` + the cross-cutting surrogate card in `notes/guidances.md`.

### Q3. "Any CNS drug withdrawn or boxed for a cardiac-valve / 5-HT2B-fibrosis liability our serotonergic program might share?"
**Answer — yes. `veto`-candidate precedent (T2 → confirm primary before raising as dispositive).**
Pergolide (Permax), a Parkinson's dopamine agonist, was withdrawn at FDA's request (Mar 2007) for
**cardiac valvulopathy**, after escalating label/boxed warnings, with NEJM studies quantifying a
several-fold valve-damage risk [card: pergolide withdrawal 2007-03].
**Implication:** an off-target **5-HT2B** agonism / cardiac-fibrosis liability is established
FDA-recognized withdrawal precedent for serotonergic/dopaminergic agents — a flaw a new serotonergic CNS
program must clear. Card is T2; per the spec, **confirm against the FDA primary record before raising a
dispositive veto.** See `notes/cns-withdrawals.md`.

### Q4. "Is there CRL precedent against approving a broad neuropsychiatric label on a single positive trial with subgroup gaps?"
**Answer — yes. `precedent` (CRL on substantial-evidence/subgroup grounds).**
Pimavanserin (Nuplazid) for dementia-related psychosis drew a CRL (Apr 2021) despite a positive HARMONY
trial, citing "lack of statistical significance in some of the subgroups of dementia, and insufficient
numbers of patients with certain less common dementia subtypes" [card: pimavanserin CRL 2021-04].
**Implication:** a broad, heterogeneous CNS label invites subgroup-level efficacy scrutiny; a single
positive trial may be judged insufficient. Compare zuranolone (approved PPD, CRL'd for the broader MDD
indication) [card: zuranolone CRL 2023-08]. See `notes/cns-crls.md`.

### Q5. "Will a clean clinical package guarantee approval — or can a CNS NDA still be rejected for non-clinical reasons?"
**Answer — it can still be rejected. `precedent` (CMC-only CRL).**
AXS-07 (meloxicam/rizatriptan) for acute migraine received a CRL (May 2022) on **CMC grounds alone** —
the FDA "did not identify or raise any concerns about the clinical efficacy or safety data...and did not
request any new clinical trials" [card: AXS-07 CRL 2022-05].
**Implication:** the flaw-surface a program must clear includes manufacturing readiness, not just trial
outcomes. See `notes/cns-crls.md`.

### Q6. "What clinical-hold precedent applies to a CNS gene therapy with a hepatotoxicity or AAV-platform safety signal?"
**Answer — strong and recent. `precedent` (single-event hold; platform-level action).**
- Pfizer's mini-dystrophin gene therapy (PF-06939926, DMD) was placed on **clinical hold** (Dec 2021)
  after a single patient death in Phase 1b [card: PF-06939926 clinical_hold 2021-12].
- Sarepta's **AAVrh74 platform** drew clinical holds, a market-suspension request for the *approved*
  Elevidys, and platform-designation revocation (July 2025) after three deaths from acute liver failure
  [card: Sarepta/Elevidys clinical_hold 2025-07].
**Implication:** a single trial death triggers a hold, and a shared mechanistic liability (hepatotoxicity)
can gate an *entire platform* and reach an approved product — a class/platform-level precedent. See
`notes/endpoint-precedent.md`.

---

## Checks the corpus CANNOT answer → search the gap (this is the design working)

- **"What endpoint does the FDA expect for a Parkinson's disease *disease-modification* program?"**
  → **GAP.** No verified standalone PD guidance in the corpus (only the pergolide *withdrawal*). The agent
  must run a **live FDA-guidance search**. (`manifest.md` known-gap #1.)
- **"Is there an AdComm vote precedent in *epilepsy* or *pain* specifically?"**
  → **GAP.** No AdComm cards in those areas (covered only via guidance/withdrawal). **Live search.**
  (known-gap #2.)
- **"Has the FDA placed a clinical hold on a *small-molecule or ASO* CNS program (not gene therapy)?"**
  → **GAP / known-unknown.** Both hold cards are AAV/neuromuscular; a tominersen (Huntington's) ventricular-
  enlargement *safety signal* was found but **no verifiable FDA hold** — omitted rather than fabricated.
  **Live search**; treat any hold as a known-unknown until a primary source confirms. (known-gap #3.)
- **"What did the FDA's *actual CRL letter* say (verbatim) for drug X?"**
  → **GAP for T2 cards.** The corpus has the sponsor's announcement, not the FDA primary PDF (fetch was
  blocked this pass). Before raising a **dispositive veto**, the agent must confirm the wording against the
  Drugs@FDA review package / FDA primary record. (known-gap #5 + tiering note.)
- **"Any CRL/hold/AdComm action *after* the retrieval window (2026-06-23)?"**
  → **Always a live call.** The corpus is a snapshot. (known-gap #6.)
