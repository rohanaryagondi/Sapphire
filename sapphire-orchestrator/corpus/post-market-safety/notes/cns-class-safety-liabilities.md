# CNS class-level safety liabilities (the post-market record)

The `post-market-safety` agent answers **C1/C2** by reading the real-world adverse-event record of *approved drugs that share the candidate's mechanism, target, or modality* — the trial-vs-real-world gap is the best predictor of a program's safety challenges. All facts below come from the **openFDA API** (`api.fda.gov`, reachable here — distinct from the 403-blocked `www.fda.gov` HTML): the **boxed warning / Warnings & Cautions** (the FDA label, **T1**, byte-verified against the raw JSON `boxed_warning` field) plus **FAERS** disproportionality counts (**T2** — spontaneous reports, reporting bias, no denominator). Retrieved 2026-06-25.

## Class liabilities by modality (the comparator record)
- **Anti-amyloid mAbs → ARIA.** Lecanemab (Leqembi) carries a class boxed warning for **amyloid-related imaging abnormalities** (ARIA-E edema, ARIA-H microhemorrhage); FAERS confirms ARIA-E (449) and ARIA-H (414) among the top post-launch terms.
- **AAV gene therapy → hepatotoxicity.** Onasemnogene abeparvovec (Zolgensma) carries a boxed warning for **serious liver injury and acute liver failure (fatal cases)**; FAERS shows AST/ALT/hepatic-enzyme increases — the labeled liability corroborated post-market.
- **Intrathecal ASO → thrombocytopenia/renal.** Nusinersen (Spinraza) carries ASO-class Warnings for **thrombocytopenia/coagulation abnormalities and renal toxicity**; notably FAERS is dominated by the *intrathecal-administration* burden (post-lumbar-puncture syndrome, procedural pain) instead.
- **Serotonergic (5-HT2) → valvulopathy/PAH.** Fenfluramine (Fintepla, a Dravet/LGS antiseizure drug) carries a boxed warning for **valvular heart disease + pulmonary arterial hypertension** under a REMS; FAERS shows tricuspid + mitral valve incompetence.
- **GABA-T inhibitor → permanent vision loss.** Vigabatrin (Sabril) carries a boxed warning for **permanent bilateral concentric visual-field constriction** under a REMS.
- **SSRI → suicidality.** Fluoxetine (SSRI class) carries the antidepressant-class **suicidality** boxed warning (pediatric/young-adult).
- **NMDA antagonist → acute CNS.** Esketamine (Spravato) carries a boxed warning for **sedation/dissociation/respiratory depression/abuse + suicidality** under a REMS.
- **Cannabidiol → hepatotoxicity.** Epidiolex carries a Warnings-&-Cautions **transaminase-elevation** liability (amplified by valproate/clobazam) — no boxed warning.

## The key C2 lesson — FAERS under-captures insidious harms
FAERS frequency is **not** incidence, and it systematically **under-reports** gradual / lab-detected / insidious harms. For **vigabatrin (vision loss)**, **cannabidiol (hepatotoxicity)**, **fluoxetine (suicidality)**, and **nusinersen (thrombocytopenia/renal)**, the *labeled* class liability does **not** appear among the top FAERS terms — those are dominated by efficacy-loss, the underlying disease, or procedural events. **A low FAERS count for a known label liability is a reporting artifact, not reassurance** — the trial/label record is the truth. Reading the two together (label = the liability; FAERS = what surfaces at scale) is the agent's distinctive value.

> **Scope note.** This is the FDA label + FAERS layer (openFDA). The **mechanism literature** behind each class liability (EMET) and **ex-US pharmacovigilance** (EMA PSURs, WHO VigiAccess) are pending — see `manifest.md`.
