# BBBP characterization — what is the head actually doing?

**As of 2026-06-07.** Follow-up to phase4 ([`phase4_bbbp_literature.md`](phase4_bbbp_literature.md))
asking *why* the BBBP head over-predicts "penetrant" (TNR ~0.70 in phase4).
Graham's hypothesis: it's effectively a molecular-weight heuristic ("below ~300 Da → brain"),
too permissive to trust on a "yes." Mahdi's usable rule: **trust the no's, investigate the yes's.**
Scripts: `experiments/characterize_bbbp.py`; raw `results/bbbp_characterization_*.json`;
scatter `results/bbbp_vs_physchem.png`.

## TL;DR

**The no's are gold. The yes's are noise.** On a 51-drug panel (phase4 set + Quiver
mTOR/Nav compounds + 15 more clearly-CNS-active / clearly-peripheral drugs):

- **P(BBB+) < 0.3 → 8/8 (100%) truly non-penetrant.** Every drug the head excluded is in
  fact peripherally restricted (fexofenadine, sirolimus, everolimus, temsirolimus,
  vancomycin, suzetrigine, ceftriaxone, dactolisib).
- **P(BBB+) > 0.7 → 29/43 (67%) truly penetrant.** A "yes" call is only ~2× better than
  the panel base rate. 14 known-peripheral drugs (atenolol, cetirizine, loperamide,
  metformin, aspirin, ibuprofen, digoxin, furosemide, hydrochlorothiazide, ranolazine,
  sulpiride, domperidone, loratadine, sapanisertib) score > 0.7.
- **Graham's MW-heuristic hypothesis is the *right shape* but not strict MW.** Spearman
  BBBP↔MW = **−0.726**, but the head excludes only the *extreme* large/polar tail. **All
  8 "no" calls have MW > 450** (smallest: dactolisib 470 Da); the smallest drug to score
  > 0.7 is **metformin at 129 Da**. So it's not literally "<300 Da → in"; it's "≳450 Da
  *and polar* → out, otherwise in." The threshold is on the *exclusion* side, much higher
  than 300 Da.

## What we ran

51 drugs: the 20-drug phase4 BBBP-literature panel + the phase2b Nav blockers and mTOR
inhibitors (suzetrigine, vixotrigine, sirolimus, everolimus, temsirolimus, dactolisib,
sapanisertib, lidocaine, mexiletine, ranolazine, lacosamide) + 15 more clearly-CNS
(SSRIs, TCAs, antipsychotics, antiepileptics) and clearly-peripheral (aspirin, ibuprofen,
metformin, ceftriaxone, digoxin, furosemide, hydrochlorothiazide) controls. Clean
neutral-parent SMILES from PubChem. Score = MAMMAL BBBP head's generative
P(`<1>`) = P(BBB-penetrant) via `mammal.examples.molnet.molnet_infer`. Physchem
from RDKit (`Descriptors.MolWt`, `Crippen.MolLogP`, `Descriptors.TPSA`,
`Lipinski.NumHDonors / NumHAcceptors / NumRotatableBonds`).

## Physchem correlations

| feature | Spearman ρ vs P(BBB+) | p-value |
|---|---:|---:|
| **MW** | **−0.726** | < 1e-4 |
| HBA | −0.668 | < 1e-4 |
| TPSA | −0.612 | < 1e-4 |
| HBD | −0.419 | 0.002 |
| RotB | −0.349 | 0.012 |
| logP | −0.253 | 0.073 |

All physchem features correlate *negatively* with the score, with **MW the strongest
single driver**, followed closely by HBA and TPSA — i.e. the head learned what is
roughly the Lipinski/CNS-MPO direction: smaller, less polar, fewer H-bond
acceptors → score → 1. Notably, **logP is barely correlated** (ρ −0.25, p = 0.07);
the "lipophilic → penetrant" intuition is *not* what the head latched onto. The
correlation is with *size and polarity* (MW + TPSA + HBA), not lipophilicity.

## The no-vs-yes asymmetry (the usable result)

| band | n | true positives in band | fraction "right" |
|---|---:|---:|---:|
| P(BBB+) < 0.3 — "no" | 8 | 8 truly non-penetrant | **100%** |
| 0.3 ≤ P(BBB+) ≤ 0.7 — "maybe" | 0 | — (the head is saturated) | — |
| P(BBB+) > 0.7 — "yes" | 43 | 29 truly CNS-active | **67%** |

Binarized at 0.5: **TPR 1.00, TNR 0.36, accuracy 0.73** (TP 29, FP 14, TN 8, FN 0).
The head literally never misses a true CNS-active drug in this panel, and it
correctly excludes every drug it puts below 0.3 — but the cost is that **two-thirds
of "BBB−" drugs end up in the "yes" band by mistake.** Note also: **no drug landed
in the 0.3–0.7 "maybe" band**; the head emits saturated near-0 or near-1 calls
(confirming phase4's calibration finding).

The 8 drugs in the "no" band are all genuinely peripheral. Three are macrocycles or
glycopeptides (sirolimus 914, everolimus 958, temsirolimus 1030, vancomycin 1449),
two are large+polar (ceftriaxone 555, fexofenadine 502), and three are mid-MW with
high polarity or high logP — **suzetrigine** (473 Da, TPSA 104, the Vertex Nav1.8
drug designed to be peripherally restricted), **dactolisib** (470 Da, logP 5.9, an
mTOR/PI3K kinase inhibitor — the only "maybe-ish" call at P 0.156), and dactolisib's
sibling **fexofenadine**.

The 14 misses in the "yes" band (cetirizine, atenolol, loperamide, ranolazine,
domperidone, sulpiride, metformin, aspirin, ibuprofen, furosemide, hydrochlorothiazide,
digoxin, loratadine, sapanisertib) are all small enough or non-polar enough to look
"drug-like" but are kept out of the CNS by efflux (P-gp/BCRP for cetirizine, loperamide,
domperidone) or by hydrophilicity + active secretion (atenolol, metformin) — neither
of which the head sees from SMILES alone.

## Does the "<300 Da → brain" rule hold?

Sharpening Graham's hypothesis on the data:

| MW band | n | mean P(BBB+) | n with P > 0.7 | n with P < 0.3 |
|---|---:|---:|---:|---:|
| < 200 Da | 8 | 1.000 | 8 | 0 |
| 200–300 Da | 15 | 1.000 | 15 | 0 |
| 300–400 Da | 15 | 0.996 | 15 | 0 |
| 400–500 Da | 6 | 0.693 | 4 | 2 |
| 500–1000 Da | 5 | 0.199 | 1 (digoxin) | 4 |
| > 1000 Da | 2 | 0.000 | 0 | 2 |

The MW-heuristic shape is real but the cliff is **above ~400–500 Da, not at 300**:
**every drug below 400 Da scored above 0.7** (regardless of clinical truth — including
atenolol 266, sulpiride 341, metformin 129, aspirin 180); above 500 Da the score
drops sharply, and above 900 Da the drug is essentially guaranteed to be excluded. So the
head is closer to a **"size + polarity exclusion gate"** than a "small → brain"
positive predictor: it confidently rules out macrocycles and very-polar large
molecules, and labels almost everything else "penetrant."

## Implications — when to trust BBBP

- **Use it as a rule-OUT, not a rule-IN.** P(BBB+) < 0.3 is a strong negative call
  in this panel (8/8). P(BBB+) > 0.7 is **only ~2× the panel base rate** of being
  actually CNS-active.
- **The score doesn't see efflux.** All 14 false-positives in the "yes" band are
  small-/medium-MW peripheral drugs that are kept out of the CNS by P-gp/BCRP or
  by hydrophilicity-driven exclusion — features the head can't infer from SMILES.
  A "BBB+ by MAMMAL" call on a small drug-like molecule does **not** rule out
  peripheral restriction.
- **Graham's MW intuition was directionally right** (ρ −0.73 with MW), but the
  operative threshold is on the *exclusion* side (~500 Da + polarity), not a 300 Da
  ceiling. The head behaves like a learned size+polarity gate, not a CNS-likelihood
  predictor.
- **Practical rule for the UI / triage layer:** keep showing P(BBB+) but **invert
  the framing**: surface the *low* scores as confident "will not cross BBB" flags;
  show the *high* scores as "drug-like, no large-polar red flag — efflux liability
  not assessed." This is exactly Mahdi's "trust the no's, investigate the yes's."

## Reconciliation with phase4
Phase4 reported 100% positive-direction accuracy (11/11) and ~50% negative-direction
accuracy (4/9) on 20 drugs; expanding to 51 drugs sharpens both numbers in the same
direction: **TPR 1.00 / TNR 0.36** with the asymmetry now load-bearing — the *bands*
(< 0.3 vs > 0.7) work even though the *threshold at 0.5* fails. Same head, more data,
same recurring theme: "honest benchmark, narrow usefulness" — but at least the
narrow usefulness is now characterized and operationally usable.
