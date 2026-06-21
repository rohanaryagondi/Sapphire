# Datafit ceiling — does MAMMAL's DTI head work where the training data IS?

**NEXT_STEPS item 1b.** The Nav1.8 binder-vs-decoy test failed (AUROC ≈ 0.5) and the
[data-distribution audit](dti_train_data_distribution.md) found BindingDB_Kd has **zero
Nav training pairs**. This experiment re-runs the same protocol on 6 targets that **are**
well-supported in the training pool (incl. mTOR, the one Quiver target with hundreds of
training pairs). The question was: data gap, or model limit?

Run: `experiments/datafit_ceiling.py` · raw: `results/datafit_ceiling_20260607_025514.json` · 2026-06-07.

## Verdict (one line)

**Mixed — neither the simple "data gap" nor "model limit" framing wins. The head works
brilliantly on 3 of 6 well-trained targets (RORC, CA2, Adrb2) and fails on 3 (BRAF —
the *most*-trained target in BindingDB — HRH1, and partially mTOR on the harder
property-matched decoys).** Data volume is necessary but not sufficient: at 100s of
training pairs the head's quality is **bimodal**, and there is no obvious family or
size predictor for which side a target lands on.

## Setup

- **Checkpoint:** PEER (`models/dti_bindingdb_pkd_peer`). Norm constants 6.286 / 1.542.
- **Binders:** top-30 BindingDB_Kd pairs at pKd ≥ 7.0 per target (distinct SMILES, harmonized via `max_affinity` + `convert_to_log`).
- **Random decoys (n=30):** SMILES drawn uniformly from BindingDB compounds never measured against this target (open-world non-binders).
- **Matched decoys (n ≈ 90):** 3 per binder, within ±50 Da MW from the off-target pool (harder property-matched negatives).
- **Spearman test pairs:** cold-split test fold (TDC default), converted to pKd. **Leakage caveat:** PEER used a *different* split, so these pairs may have been seen during PEER training. Report as upper bound, not a clean generalization measure.
- **EF@5%:** enrichment factor on the binder + matched-decoy pool.

Panel (6 targets across kinase / GPCR / NR / enzyme classes, with mTOR as the Quiver-relevant kinase):

| accession | gene  | class             | n_pairs | seq_len |
|-----------|-------|-------------------|--------:|--------:|
| P42345    | MTOR  | kinase            |     192 | 2549 (truncated to 1250) |
| P15056    | BRAF  | kinase            |     532 | 766 |
| Q8K4Z4    | Adrb2 | gpcr (rodent)     |     211 | 418 |
| P31389    | HRH1  | gpcr (human)      |     184 | 488 |
| P51449    | RORC  | nuclear_receptor  |     374 | 518 |
| P00918    | CA2   | other (carbonic anhydrase) | 269 | 260 |

Wall time on MPS: 537 s.

## Results — per target

| accession | gene  | n_pairs | AUROC random | AUROC matched | Spearman (test fold) | EF@5% |
|-----------|-------|--------:|-------------:|--------------:|---------------------:|------:|
| P42345    | MTOR  | 192     |  **0.76**    |  **0.56**     |   0.27 (n=42)        |  2.00 |
| P15056    | BRAF  | 532     |  **0.47**    |  **0.46**     |   0.45 (n=119)       |  4.00 |
| Q8K4Z4    | Adrb2 | 211     |  **0.87**    |  **0.88**     |   **0.76** (n=49)    |  4.00 |
| P31389    | HRH1  | 184     |  **0.40**    |  **0.33**     |  −0.14 (n=33)        |  0.00 |
| P51449    | RORC  | 374     |  **0.97**    |  **0.95**     |  −0.10 (n=82)        |  4.00 |
| P00918    | CA2   | 269     |  **0.87**    |  **0.84**     |   **0.87** (n=73)    |  4.00 |

Reading the AUROC columns under the pre-registered decision rule (≥ 0.80 = clearly
target-specific; 0.60–0.80 = modest triage; < 0.60 = doesn't separate binders):

- **Clearly works (AUROC ≥ 0.80 on BOTH random and matched):** RORC, CA2, Adrb2 — 3/6.
- **Random OK, matched ≈ chance:** mTOR — discrimination disappears once the decoys are MW-matched.
- **Below chance on both:** BRAF, HRH1. The head's predicted pKd is **higher for off-target compounds than for known binders** on these targets.

Spearman (graded ranking on potentially-leaked test pairs) is similarly heterogeneous: CA2
0.87 and Adrb2 0.76 (both strong), BRAF 0.45 and mTOR 0.27 (modest), RORC −0.10 and HRH1
−0.14 (no graded signal). **AUROC and Spearman do not track each other** — RORC
discriminates binders from decoys at 0.97 but cannot rank-order binders by potency, while
BRAF cannot discriminate but does rank-order. The head encodes binding evidence in two
different ways depending on the target.

## Off-target matrix — top-3 binders per target × 6 proteins

For each target the 3 highest-pKd binders are scored against all 6 panel proteins.
**Δ = on-target pKd − mean off-target pKd**. Positive Δ means the head ranks the binder
higher on its real target than on the other 5. Per-binder rows in the JSON.

| accession | gene  | mean Δ (on − mean off) |
|-----------|-------|-----------------------:|
| P00918    | CA2   | **+1.97**              |
| P15056    | BRAF  | **+1.18**              |
| Q8K4Z4    | Adrb2 | +0.83                  |
| P51449    | RORC  | +0.68                  |
| P31389    | HRH1  | +0.68                  |
| P42345    | MTOR  | **−1.12** (INVERTED)   |

Three observations:

1. **CA2 specificity is real (Δ +1.97)** — mirrors its clean AUROC + Spearman: the head
   has a coherent picture of this target.
2. **BRAF has Δ +1.18 despite AUROC at chance.** The head ranks BRAF binders higher on
   BRAF than on the other 5 proteins, but also predicts random off-target compounds with
   similar high pKd on BRAF → the *separation between binders and a target's own decoys*
   is gone even though *cross-target ranking of a specific molecule* survives.
3. **mTOR's Δ is INVERTED (−1.12)** — for the Quiver target, the head literally predicts
   the binders higher on the *other* 5 panel proteins than on mTOR. Worst possible
   off-target specificity. mTOR is also the only panel target that's truncated
   (2549 → 1250 aa); the kinase domain (~2182–2516) is **outside** the truncation window,
   so the head is reading the FAT/FRB/regulatory regions instead of the active site.

## Verdict (long form)

**The naive "test the head where the data is rich → confirm Nav failure was a data gap"
prediction does not survive contact with the data.** Three of six well-supported targets
work brilliantly (RORC, CA2, Adrb2); three do not (BRAF, HRH1, mTOR partially), and
BRAF — with 532 training pairs, the *most*-represented protein in the entire pool — is
flat at chance. This means:

1. **Data volume is necessary but not sufficient.** Above ~150 pairs the head's
   binder-vs-decoy quality is bimodal — either AUROC ~0.85+ or ~0.5 — with no clean
   class, size, or length predictor for which mode a target lands in. Confirmed by the
   threshold-curve experiment ([`datafit_curve.md`](datafit_curve.md)).
2. **The Nav failure is *consistent* with a data gap but cannot be cleanly *attributed*
   to one.** A Nav fine-tune isn't a guaranteed fix; we could push Nav from the 0-pair
   floor into either side of the bimodal distribution at the high end.
3. **mTOR — the one Quiver target with hundreds of training pairs — fails the property-
   matched test (AUROC 0.56) and inverts off-target (Δ −1.12).** The 1250-aa
   truncation excludes the kinase domain entirely, which is the obvious mechanistic
   suspect; that's worth one extra probe (re-run with a kinase-domain window only).
4. **Use the head as cross-target re-ranking for compounds the head already ranks
   highly somewhere — not as a per-target binder/non-binder triage gate.** Same
   conclusion as Phase 1/2b, with stronger evidence.

## Caveats

- The Spearman column is potentially-leaked through PEER training (the cold-split test
  fold may overlap with PEER's training set). It's an upper bound on graded-ranking
  ability for this checkpoint.
- The matched-decoy set is property-matched on MW only (not logP, HBD/HBA, rotatable
  bonds, or topological fingerprint distance). A DUD-E-style matched set would be a
  harder bar; AUROC numbers here are an upper bound for "matched-difficulty" tests.
- mTOR truncation is a real confound — the 2549-aa sequence is truncated to the
  N-terminal 1250 aa, which contains the HEAT repeats / FAT domain but not the
  ATP-binding kinase pocket (~2182–2516). A targeted retest with the kinase-domain
  window only is the obvious follow-up.
- n_binders ≤ 30 per target by design (uniform comparison); some targets have many
  more binders in BindingDB. AUROC at this scale is well-estimated but enrichment
  factors at top-5% are quantized (k = 6 at n_total = 120).
