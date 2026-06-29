# QUERIES — post-market-safety corpus

Six realistic checks the `post-market-safety` agent would run for dossier fields **C1/C2**, answered **from the corpus** (`index.jsonl` / `notes/`). Checks the corpus can't answer are stated as the live-search gap.

### Q1. What's the class safety liability for an anti-amyloid antibody program?
**A (from corpus):** **ARIA** — amyloid-related imaging abnormalities (ARIA-E edema, ARIA-H microhemorrhage), a class boxed warning (lecanemab/Leqembi), serious/fatal esp. in ApoE4 homozygotes; baseline + periodic MRI required. FAERS confirms ARIA-E/ARIA-H post-launch. → lecanemab card.

### Q2. What real-world safety liability should an AAV gene-therapy CNS program expect?
**A (from corpus):** **Hepatotoxicity** — onasemnogene abeparvovec (Zolgensma) carries a boxed warning for serious liver injury + fatal acute liver failure; corticosteroid prophylaxis + ≥3-month liver monitoring required. FAERS shows AST/ALT increases (+ thrombocytopenia). → Zolgensma card.

### Q3. What class safety signals attach to an intrathecal ASO?
**A (from corpus):** ASO-class **thrombocytopenia/coagulation abnormalities + renal toxicity** (nusinersen/Spinraza, Warnings & Cautions — no boxed warning); intrathecal delivery adds lumbar-puncture risks (FAERS top term: post-LP syndrome). → nusinersen card.

### Q4. Key methodological caveat — can we read low FAERS counts as low risk?
**A (from corpus):** **No.** For vigabatrin (vision loss), CBD (hepatotoxicity), fluoxetine (suicidality), and nusinersen (thrombocytopenia/renal), the labeled class liability is **not** among the top FAERS terms — FAERS under-captures insidious/lab-detected/gradual harms. The label/trial record is the truth; FAERS is spontaneous (reporting bias, no denominator). → `notes/` "key C2 lesson" + each card's `trial_vs_realworld`.

### Q5. Cardiac risk for a serotonergic CNS drug?
**A (from corpus):** **Valvulopathy + pulmonary arterial hypertension** — fenfluramine (Fintepla) boxed warning + REMS with mandatory serial echocardiograms; FAERS shows tricuspid + mitral valve incompetence. → fenfluramine card.

### Q6. Which CNS comparators are managed under a REMS (a strong safety-burden signal)?
**A (from corpus):** Esketamine/Spravato (sedation/dissociation/abuse), fenfluramine/Fintepla (valvulopathy/PAH), vigabatrin/Sabril (vision loss) — all carry boxed warnings + restricted-distribution REMS. → those 3 cards' `rems_or_action`.

---
### Checks the corpus does NOT answer (live-search gaps)
- **Mechanism / biomedical literature** behind each class liability (e.g. 5-HT2B → valvulopathy; ApoE4 → ARIA) — EMET Pass B, blocked by the intermittent EMET host-permission (`manifest.md` Sources/gap 1). → EMET.
- **Ex-US pharmacovigilance** (EMA PSURs/DHPCs, WHO VigiAccess, Health Canada, TGA) — not queried. → live search.
- **Computed disproportionality (PRR/ROR)** + **PMR/PMC** post-market study commitments — only raw FAERS counts captured; `www.fda.gov` PMR/PMC is 403-blocked. → live search.
