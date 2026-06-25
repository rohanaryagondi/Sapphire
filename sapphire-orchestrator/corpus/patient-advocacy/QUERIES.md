# QUERIES — the corpus answering real Patient-Advocacy checks

Six realistic checks this agent runs at runtime (dossier field **F1**), answered **from the local corpus**
(citing the claim-card(s) / note). The last two show corpus-first → **search-the-gap** (live 990s + forum sentiment).

Framing (from the spec): **facts only — report what advocates say and how organized they are**; don't infer
demand size; down-weight informal sources; validate load-bearing clinical claims against EMET.

---

### Q1. "Can organized advocacy change drug ACCESS for a CNS indication?"
**Answer — yes; the Alzheimer's Association case.** It mobilized Congress, state AGs, clinicians, and grassroots
advocates to push CMS to broaden Medicare coverage of anti-amyloid antibodies [card #1]. Note the divergence:
advocacy pushed *for* access while KOLs (corpus #4) were skeptical of benefit. See `notes/`.

### Q2. "Does an organized community shape the FDA's benefit-risk FRAMEWORK?"
**Answer — yes; ALS.** The community pressed for and FDA issued ALS-specific drug-development guidance (2019)
with patient-focused benefit-risk/flexible endpoints [card #2]. The urgency is quantified: death within ~3
years of onset; riluzole adds only 3-6 months [card #5, EMET].

### Q3. "Is there precedent for advocacy influencing a specific FDA approval DECISION?"
**Answer — yes; DMD/eteplirsen (2016).** Approved on "very limited data," "shrouded in controversy" — widely
credited in part to intense DMD patient-family advocacy [card #3]. (Pairs with the eteplirsen divergence card
in corpus #1.)

### Q4. "How well-funded/organized is advocacy in a given CNS indication?"
**Answer — varies; Parkinson's is heavily resourced.** MJFF reports deploying tens of millions (e.g. $62.4M)
into PD tools and therapies [card #4] — agenda-setting scale. Alzheimer's and ALS communities are likewise
highly organized [cards #1, #2].

### Q5. "What's the unmet need that gives a community its urgency (for benefit-risk framing)?"
**Answer — quantifiable; ALS example.** ~3-year survival from onset; only-drug riluzole adds 3-6 months
[card #5, EMET, Hardiman 2011]. This is the kind of figure that shapes FDA's risk tolerance.

---

## Checks the corpus CANNOT answer → search the gap live (the design working)

- **"Does this advocacy org have pharma funding that colors its position?"**
  → **GAP — harvest live.** E.g., the Alzheimer's Association's top donors include anti-amyloid makers, tied by
  critics to its pro-access stance — but exact figures live in **current IRS 990s** (ProPublica), which change
  yearly (manifest gap #1). **Pull live.**
- **"What is the indication-specific FDA 'Voice of the Patient' (PFDD) report saying?"**
  → **GAP.** Specific VOP PDFs not fetched this pass (gap #2). **Pull the indication's VOP live.**
- **"What's grassroots community sentiment (forums) on unmet need / willingness to enroll?"**
  → **GAP — and the agent's live job.** Reddit/HealthUnlocked/PatientsLikeMe sentiment is **T4, live-only** (gap #3).
- **"Advocacy in epilepsy / migraine / psychiatry?"**
  → **GAP.** Corpus is AD/ALS/DMD/PD only (gap #4). **Live search.**
