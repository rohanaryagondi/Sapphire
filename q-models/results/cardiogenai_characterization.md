# CardioGenAI — Track-5 tri-channel cardiac tox displacer test (scout campaign Phase 3, 2026-06-14)

**Question:** CardioGenAI (gregory-kyro/CardioGenAI, MIT) ships discriminative **hERG + NaV1.5 + CaV1.2**
blocker heads (GAT + fingerprint + SMILES-transformer). Does it (a) beat our hERG gate (FP-XGBoost 0.89 /
ChemBERTa 0.815) on TDC hERG_Karim, and (b) add a **cardiac multi-channel** readout our single hERG gate
lacks — does **NaV1.5** correctly flag the cardiac-Na liability of the Nav drugs? **Run:** g5.xlarge,
torch 2.1.0/cu121, openbabel-wheel; committed .pt heads + the 782 MB transformer-vocab CSV. Eval
`aws/cardiogenai_eval.py`. ~$0.3.

## Verdict: **NOT adoptable as-is. The multi-channel concept is the right idea (and the only model offering it), but the heads emit saturated 0/1 calls with textbook errors, and its closed SMILES vocab can't even be benchmarked on TDC hERG. Our hERG (FP-XGBoost 0.89 / MapLight) remains the Track-5 winner.**

## What ran: D — Quiver Nav-drug tri-channel panel (the Quiver-relevant question)
| Drug | Nav1.8 binder | P_hERG | P_NaV1.5 | P_CaV1.2 | reality check |
|---|---|---|---|---|---|
| suzetrigine (VX-548) | 1 | **1.0** | 0.0 | 0.0 | hERG=1.0 is a **false positive** (suzetrigine is clean-by-design); NaV1.5=0 correct |
| A-803467 | 1 | 0.0 | 1.0 | 1.0 | promiscuous Nav1.8 tool cpd — multi-channel flag plausible |
| lidocaine | 1 | 0.0 | **0.0** | 0.0 | **false negative** — lidocaine is *the* class-Ib cardiac NaV1.5 blocker |
| mexiletine | 1 | 0.0 | 1.0 | 0.0 | ✅ correct (class-Ib NaV1.5 blocker) |
| ranolazine | 1 | **0.0** | 1.0 | 0.0 | NaV1.5 ✅; hERG=0 is a **false negative** (ranolazine is a known IKr/hERG blocker) |
| carbamazepine | 1 | 0.0 | 0.0 | 0.0 | borderline |
| lacosamide | 1 | 0.0 | 0.0 | 0.0 | borderline |

NaV1.5 flagged at 0.5: A-803467, mexiletine, ranolazine (mean 0.43).

**Read:** the NaV1.5 head is *directionally* real — it catches mexiletine and ranolazine (genuine late-Na
blockers) — which is a cardiac-off-target signal our single hERG gate genuinely lacks. **But it is not
reliable in detail:** it **misses lidocaine** (the textbook class-Ib NaV1.5 blocker), and the **hERG head
errs on textbook cases** (suzetrigine false-positive, ranolazine false-negative). All outputs are
**saturated 0.0/1.0** — no graded probabilities, i.e. uncalibrated/over-confident.

## What didn't run, and why it's itself a finding
- **A/B/C (TDC hERG_Karim head-to-head + calibration + applicability domain): `KeyError: '[SH]'`.**
  CardioGenAI's SMILES transformer uses a **closed character vocabulary built from its training CSV**;
  any test SMILES containing an out-of-vocab token (`[SH]`, …) crashes featurization, and one bad molecule
  kills the whole batch. **So it cannot be benchmarked on the standard hERG set without retraining its
  tokenizer.** This is the operating-envelope limitation that matters: **CardioGenAI fails on chemotypes
  outside its training vocabulary** — exactly the novel-scaffold regime where a de-risking model has to be
  trustworthy. (We did *not* "fix" this by filtering to in-vocab molecules: that would cherry-pick an
  easier subset and produce a misleadingly favorable AUROC vs our full-set 0.89.)
- **E (panel discrimination): tensor-size mismatch (143 vs 135)** — a batch-padding bug across
  variable-length SMILES; orthogonal to the vocab issue, sidesteppable by per-molecule scoring, not worth
  a relaunch given the head reliability above.

## Why
The pitch — one model, three cardiac channels — is sound and unique; nothing else we've tested gives
NaV1.5/CaV1.2 alongside hERG. But the shipped discriminative heads are **saturated binary classifiers**
(not probabilities), make **errors on canonical drugs** (lidocaine, suzetrigine, ranolazine), and are
**vocab-locked** to their training distribution. That combination makes them unsafe as a de-risking gate.

## Recommendation (conservative)
- **Track 5 hERG: no change.** **FP-XGBoost 0.89 / MapLight (far-OOD 0.809)** stay the winners — they're
  calibrated, OOD-robust, and not vocab-locked.
- **CardioGenAI: do not adopt.** File the **multi-channel cardiac idea** as worth wanting: if a NaV1.5 /
  CaV1.2 cardiac-panel need arises, build it on our own FP+GBT recipe (which already generalizes and
  calibrates) rather than ship CardioGenAI's saturated, vocab-locked heads. The mexiletine/ranolazine NaV1.5
  hits show the *target* concept is learnable; the *implementation* here isn't trustworthy.

## Receipts
- Result: `s3://rohan-mammal-bootstrap-20260610-213029/cardiogenai/cardiogenai_result.json` (D rows +
  A/B/C `KeyError '[SH]'` + E tensor mismatch). Eval `aws/cardiogenai_eval.py`. Instance
  `i-0ad3c8bc2e8bff317` self-terminated; no strays.

## Scorecard impact
**None to the winner.** Track 5 stays **ADMET-AI DILI + FP-XGBoost/MapLight hERG**. CardioGenAI noted as:
*multi-channel cardiac concept (hERG+NaV1.5+CaV1.2) — NaV1.5 directionally catches late-Na blockers, but
heads are saturated/uncalibrated with textbook errors and vocab-locked (can't benchmark on TDC hERG); not
adoptable.*
