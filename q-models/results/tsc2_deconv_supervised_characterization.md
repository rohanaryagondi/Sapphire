# TSC2 deconvolution, supervised attempt (PKM2 vs PPARD) — ligand QSAR fails on the novel hits; + a data-quality flag, 2026-06-15

Follow-up to `results/tsc2_deconv_characterization.md` (zero-shot BALM/PLAPT failed to deconvolve Ben's
TSC2-Optopatch screen hits: PKM2 0.50/0.40, PPARD 0.53/0.67). This applies the **supervised per-target**
approach that wins everywhere else in the campaign (trunc_test 0.92, ion-channel fine-tune 0.98): train a
PKM2-binder and a PPARD-binder classifier (Morgan-FP ECFP4 + GradientBoosting) from ChEMBL, validate by
Murcko scaffold-split, then score Ben's 9 panel compounds → P(PKM2), P(PPARD). Local, headless ChEMBL pull,
CPU, **$0 (no AWS).** `experiments/tsc2_deconv_supervised.py`.

## Headline: **Even a supervised QSAR that is near-perfect on ChEMBL (0.99) does NOT deconvolve the novel screen hits — they are out-of-domain. Ligand similarity (zero-shot OR supervised) is the wrong tool for these hits; structure (Boltz-2) or Quiver functional signatures are required.**

### The classifiers are excellent on ChEMBL chemistry
| Target | ChEMBL actives (pChEMBL≥6) | scaffold-split CV AUROC |
|---|---|---|
| PKM2 (CHEMBL2107) | 821 | **0.993** |
| PPARD (CHEMBL3979) | 1,264 | **0.990** |
(Negatives = each target's inactives + the other target's actives as near-certain non-binders.)

### …but they fail on Ben's 9 screen hits
| Compound | true PKM2/PPARD | P_PKM2 | P_PPARD | read |
|---|---|---|---|---|
| **QS0113172** (the hit) | 1 / 1 | 0.159 | 0.366 | ❌ low on both — not recognized |
| QS0069567 | 0 / 1 | **0.750** | 0.090 | ❌ calls PKM2, true PPARD |
| GSK 3787 (PPARD ref) | 0 / 1 | 0.042 | **0.921** | ✅ correct (but it's a ChEMBL PPARD ligand → near-memorization) |
| "Dasa-58" (PKM2 ref) | 1 / 0 | 0.059 | 0.463 | ⚠️ **wrong SMILES — see flag below** |
| GF 109203X (control) | 0 / 0 | **0.801** | 0.021 | ❌ false-positive PKM2 |
| Biperiden (control) | 0 / 0 | **0.736** | 0.045 | ❌ false-positive PKM2 |
| BMS 191011 (control) | 0 / 0 | 0.388 | **0.731** | ❌ false-positive PPARD |
| carbamazepine (control) | 0 / 0 | 0.214 | 0.007 | ✅ low both |
| BIIB021 (control) | 0 / 0 | 0.462 | 0.098 | ✅ low both |

**Panel AUROC: PKM2 0.143 (below chance), PPARD 0.722** — vs zero-shot BALM/PLAPT (PKM2 0.50/0.40, PPARD
0.53/0.67). The supervised model is no better (PKM2 actually worse) at deconvolving the actual hits, despite
0.99 on ChEMBL.

### Why — the applicability-domain wall
The QS-hits are **novel scaffolds from a 30K phenotypic screen**, far outside the ChEMBL PKM2/PPARD training
chemistry. A QSAR — however good in-domain — collapses off-distribution (the same far-OOD failure documented
for the de-risking models, `results/derisking_characterization.md`). The only compound the model nails
(GSK3787→PPARD 0.921) is literally a ChEMBL PPARD ligand, i.e. in-domain. The novel hits (QS0113172,
QS0069567) and several controls are mis-scored. **Conclusion: ligand-based methods cannot deconvolve novel
phenotypic-screen hits; this needs (a) Boltz-2 co-folding (does the binding pose discriminate, independent of
ligand-to-training similarity?) or (b) Quiver's own functional/DFP signatures — which is what actually made
the original PKM2/PPARD call.** More training data won't fix this (it's an OOD problem, not a volume problem).

## ⚠️ Data-quality flag (action for Ben/Amy)
The panel's **PKM2 reference "Dasa-58" (QS0321744) has the wrong SMILES.** It is encoded as
`O=C(O)C[C@@H](C(O)=O)NC(C1=C(N)N([C@H]2...COP(O)(O)=O...)C=N1)=O` = **C13H19N4O12P, MW 454, a
phosphoribosyl nucleotide (SAICAR-like; has a phosphate, no sulfonamide).** Real **DASA-58** is a
**quinoline-6-sulfonamide PKM2 activator (C19H18N2O4S2, MW ~402, sulfonamide, no phosphate).** So the PKM2
reference-validation point is invalid (the model scored a nucleotide, not DASA-58). Worth correcting in
`TSC2 target deconvolution hits_6.11.2026_AE.xlsx` and re-checking the other QS→structure mappings.

## Scorecard impact
Track 2/9 (deconvolution): reinforces "sequence/ligand DTI can't do fine target deconvolution" — now shown
for the **supervised** case too (0.99 in-domain → fails on novel hits). The TSC2 PKM2-vs-PPARD deconvolution
remains a **Boltz-2 co-fold + Quiver-functional-signature** problem. (PKM2 530 aa / PPARD 441 aa are small →
Boltz-2 co-folding is viable on a normal GPU — the recommended next step.)

## Caveats
- Panel n=9 (tiny) → panel AUROCs have very wide CIs; the qualitative finding (novel hits mis-scored,
  controls false-positive, only the in-ChEMBL ligand correct) is the robust signal.
- Negatives use cross-target actives — a deliberate discrimination design; the ChEMBL CV AUROC (0.99)
  confirms the classifiers are real, so the panel failure is genuinely OOD, not an undertrained model.
- "Dasa-58" excluded from the conclusion given its wrong SMILES.

**Receipts:** `results/tsc2_deconv_supervised_result.json`; `experiments/tsc2_deconv_supervised.py`;
panel `aws/tsc2_deconv_panel.json`; ChEMBL PKM2=CHEMBL2107 / PPARD=CHEMBL3979.
