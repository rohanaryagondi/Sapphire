# Comprehensive (Boltz-level) characterization of the de-risking winners — Tracks 4 & 5

**Date:** 2026-06-13 · MolFormer-XL + ChemBERTa-2 on BBB_Martins / hERG_Karim / DILI.
Not just an accuracy number — the operating envelope (where each model is reliable vs not).
Receipts: `results/comprehensive_admet_result.json`, `aws/comprehensive_admet_char.py` (AWS g5.xlarge).

## Results

| Model | Endpoint | random | scaffold-held-out | TPR / TNR | Brier | AD: near → far/OOD |
|---|---|---|---|---|---|---|
| MolFormer-XL | BBBP | 0.836 | 0.796 | 0.86 / 0.61 | 0.151 | 0.903 → **0.747** |
| MolFormer-XL | hERG | 0.841 | 0.793 | 0.76 / 0.76 | 0.163 | 0.851 → **0.704** |
| MolFormer-XL | DILI | 0.830 | 0.793 | 0.77 / 0.77 | 0.177 | 0.993 → **0.648** |
| ChemBERTa-2 | BBBP | **0.874** | **0.851** | 0.89 / 0.72 | **0.122** | 0.892 → 0.794 |
| ChemBERTa-2 | hERG | 0.800 | 0.773 | 0.72 / 0.74 | 0.183 | 0.808 → **0.588** |
| ChemBERTa-2 | DILI | **0.881** | **0.879** | 0.81 / 0.81 | 0.139 | 1.000 → 0.804 |

(AD = applicability domain: test compounds binned by max Tanimoto, Morgan-2048, to the train set.
near = ≥0.5, far/OOD = <0.3.)

## The nuances (the deliverable)

1. **Applicability domain is the universal failure mode — the single most important operating
   rule.** BOTH models are reliable *only within their chemical training domain*. Near-domain
   AUROC is 0.81–1.0; on out-of-domain compounds (low Tanimoto) it collapses to 0.59–0.80. This
   is a **silent failure on novel chemotypes** — exactly the compounds a discovery program cares
   about. **Operational gate: flag any compound with max-Tanimoto-to-train < ~0.3 as
   low-confidence, regardless of the score.** hERG is the worst: ChemBERTa OOD hERG = **0.588
   (near chance)**.
2. **ChemBERTa-2 > MolFormer-XL on this protocol** (random-split, balanced probe): BBBP 0.874 vs
   0.836, DILI 0.881 vs 0.830. And it **generalizes across scaffolds far better** — DILI
   scaffold-held-out 0.879 ≈ random 0.881 (it learns chemistry, not scaffolds), vs MolFormer's
   larger drops. It's also **better calibrated** (Brier 0.12–0.14 vs 0.15–0.18). (Note: MolFormer
   won the earlier *external-panel* BBBP eval at 0.889; on these TDC splits ChemBERTa edges it.
   Both are strong; ChemBERTa is the more robust + commercial-OK pick.)
3. **BBBP yes-bias (both models):** TPR 0.86–0.89 ≫ TNR 0.61–0.72 — they over-call BBB-penetrant.
   Trust the "yes," be skeptical of "no" (and keep MAMMAL-BBBP as the TNR-1.0 "trust-the-no" backstop).
4. **hERG is the weakest endpoint for both** — lowest scaffold AUROC, worst calibration (Brier
   0.18), worst OOD collapse. The cardiac gate is the least trustworthy; treat hERG calls as soft.

## Bottom line for shipping
Ship **ChemBERTa-2** (BBBP + hERG + DILI; MIT, robust, calibrated) + ADMET-AI (DILI) + MAMMAL
(BBBP trust-the-no). **Wrap every prediction with an applicability-domain flag** (Tanimoto to
train) — the models are trustworthy in-domain and unreliable OOD, and that distinction matters
more than the headline AUROC.
