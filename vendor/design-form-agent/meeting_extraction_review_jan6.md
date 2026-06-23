# Meeting Extraction Review
## Follow-up: Aim 1 Inhibitory Neuron Experiments
**Date:** January 6, 2026 | **Duration:** 39 min | **Attendees:** James Fink, Steven Ryan, Kathy, +1 unidentified

> **Instructions:** Please review the extracted experiments, action items, and open questions below. Mark any corrections directly, then confirm so the experiment design sheets can be generated.

---

## Experiments Identified (3)

### Experiment 1: Potassium Titration for GABA Reversal Potential ✅ Ready for layout

**What:** Dose-response of external potassium in Tyrodes imaging buffer to modulate membrane potential and observe IPSP reversal (inhibitory → excitatory transition).

**Key decision:** Use **potassium methyl sulfate (KMeSO4)** instead of KCl to avoid confounding chloride reversal. KMeSO4 chosen over K-gluconate (chelates calcium), K-acetate (too permeable), and K-methanesulfonate.

| Parameter | Value | Confidence |
|-----------|-------|------------|
| Assay type | Synaptic | ✅ High |
| Cell type | NGN2D.S. + DLX2 co-culture | ✅ High |
| Imaging buffer | Tyrodes (modified with KMeSO4) | ✅ High |
| Compound | KMeSO4 in buffer | ✅ High |
| Concentrations | 3 levels: low (~2 mM), standard (~5.4 mM), high (~8-10 mM) | ⚠️ Medium — exact values need Nernst calculation |
| NaCl adjustment | Must reduce NaCl proportionally for osmolarity | ⚠️ Unresolved — needs recipe + calculation |
| Plate layout | 3 buckets per plate: standard/low/high repeating rows | ✅ High |
| Control | Sister plate with same K+ concentrations in **excitability assay** (checks for depolarization block) | ✅ High |
| Timing | Acute — applied in imaging buffer at time of imaging | ✅ High |

**⚠️ Needs before proceeding:**
- [ ] Tyrodes recipe from Jen
- [ ] Gemini calculation of exact KMeSO4 concentrations + NaCl compensation

---

### Experiment 2: GABA-A PAM Panel 🔶 Pending drug availability

**What:** Test subtype-selective positive allosteric modulators of GABA-A receptors to boost IPSP/EPSP amplitude. Designed to confirm GABRA subunit composition matches functional readout.

| Compound | Target | Purpose | Available? |
|----------|--------|---------|------------|
| **Diazepam** | Alpha-2,3,5 (general benzo) | Broad PAM — should boost all GABA-A signals | ❓ Check with Ben |
| **Zolpidem** | Alpha-1 selective | **Expected negative control** — NGN2 neurons lack GABRA-A1 | ❓ Check with Ben |
| **KRM-II-81** | Alpha-2/3 selective | Research-grade, avoids alpha-1 sedation | ❓ New compound — needs ordering |
| **MP-III-022** | Alpha-5 selective (Ki 55 nM) | Tests alpha-5 contribution | ❓ New compound — needs ordering |
| **Barbiturates** (unspecified) | GABA-A general | Additional modulator | ❓ Check with Ben |

**Key prediction (from James):** If the alpha-1 PAM (zolpidem) does nothing but alpha-2/3 PAMs work, that confirms the subunit composition (high alpha-3, low alpha-1) matches the functional phenotype.

**Status:** Designated as **second experiment** (after K+ titration) since drugs need to be ordered and prepped.

| Parameter | Value | Confidence |
|-----------|-------|------------|
| Assay type | Synaptic | ✅ High |
| Cell type | NGN2D.S. + DLX2 co-culture | ✅ High |
| Concentrations | Not yet determined | ❌ Unresolved |
| Plate layout | Not yet determined | ❌ Unresolved |
| Imaging buffer | Tyrodes | ⚠️ Medium |

---

### Experiment 3: Inhibitory Neuron Ratio Experiment 🔶 Needs layout design

**What:** Vary the ratio of DLX2:NGN2 neurons (3 ratios) to test whether inhibitory neuron density affects IPSP detection. May be combined with PAMs or K+ titration.

| Parameter | Value | Confidence |
|-----------|-------|------------|
| Assay type | Synaptic | ✅ High |
| Ratios | 3 ratios (values TBD) | ⚠️ Medium |
| Critical control | **NGN2-only wells** (no inhibitory neurons) with GABA assay + blockers — to rule out CheRiff artifacts | ✅ High |
| Plate layout | Kathy to draft | ❌ Unresolved |

**James's note:** "Anything more granular than 3 ratios is kind of useless — what's the difference between 60/40 and 70/30?"

---

## Action Items

| # | Task | Assignee | Priority | Deadline |
|---|------|----------|----------|----------|
| 1 | Get Tyrodes imaging buffer recipe from Jen | Kathy | 🔴 High | ASAP |
| 2 | Feed buffer recipe to Gemini → propose KMeSO4 dose-response + NaCl compensation | James/Kathy | 🔴 High | Before Friday |
| 3 | Check with Ben on drug availability (diazepam, zolpidem, KRM-II-81, MP-III-022, barbiturates); order as needed | Kathy/Ben | 🔴 High | ASAP |
| 4 | Draft plate layout for K+ titration (3 conditions, repeating rows) | Kathy | 🔴 High | Before Friday |
| 5 | Draft plate layout for ratio experiment (3 ratios + NGN2-only control) | Kathy | 🟡 Medium | Before Friday |
| 6 | Schedule small group meeting Friday to finalize designs | James | 🔴 High | ~Jan 9 |
| 7 | Investigate GABA sniffers feasibility (back-burnered — illuminator/filter concerns) | Kathy | 🟢 Low | TBD |

---

## Open Questions Requiring Decision

1. **Exact KMeSO4 concentrations?** — Need Tyrodes recipe first, then Nernst calculation. Steven suggests ~half and ~double the baseline K+ concentration. *(Owner: Steven + Gemini)*

2. **Run K+ titration and PAM experiments together or separately?** — James leans toward separate since drugs need ordering. *(Owner: James)*

3. **What 3 DLX2:NGN2 ratios to test?** — Not yet decided. *(Owner: James/Kathy)*

4. **Are GABA sniffers feasible?** — Steven unsure if genetically encoded or aqueous; may lack optics. Back-burnered. *(Owner: Steven)*

---

## Context Notes

- This meeting follows the **Dec 15 brainstorming session** which generated hypotheses for scarce IPSPs in human co-cultures.
- **Baseline signal:** Hong Kang detected ~13 IPSPs from 6 FOVs; dropped to 0 with gabazine. This confirms GABA is being released and detected — the goal is to amplify this signal.
- **Critical biological insight:** NGN2 neurons express **GABRA-A3** (fetal, slow kinetics) not **GABRA-A1** (adult, fast). IPSPs are expected to be broader/slower than rodent — analysis pipeline may need adjustment.
- **Parallel culture-side experiments** (Kathy/Luis, separate from these): Thermo proprietary media, forskolin + rolipram, chronic muscimol.
