# MapLight held-out BBB confirmation on B3DB — Track-4 follow-up (2026-06-14)

Before retiring MolFormer-XL as the Explorer BBB head, confirm Phase 1's finding (MapLight BBBP scaffold
0.905 > MolFormer 0.889) on an **independent, held-out** dataset. **Setup:** train both MapLight (CatBoost
on ECFP+Avalon+ErG+RDKit) and MolFormer-XL (mean-pool embeddings + LogReg) on the **full TDC BBB_Martins**;
test on **B3DB** (theochem, CC0, 7,807 cpds), with **exact canonical-SMILES leakage removed** (1,665
overlaps dropped → **6,142 held-out test molecules**). g5.xlarge, ~$0.35.

## Verdict: **CONFIRMED. MapLight beats MolFormer-XL on held-out B3DB across every axis — overall, calibration, and (decisively) out-of-domain. Promote MapLight to BBB primary; keep MolFormer only as a backstop.**

| Model | AUROC | AUPRC | Brier | Acc | far-OOD AUROC (Tanimoto<0.3, n=824) | mid (n=548) | near (n=4,770) |
|---|---|---|---|---|---|---|---|
| **MapLight** | **0.919** | **0.938** | **0.126** | **0.830** | **0.674** | **0.721** | **0.961** |
| MolFormer-XL | 0.854 | 0.861 | 0.157 | 0.799 | 0.590 | 0.655 | 0.923 |

- **Overall AUROC +0.065** (0.919 vs 0.854) on 6,142 truly held-out molecules — not a scaffold-split
  artifact, a different dataset entirely.
- **Better calibrated** (Brier 0.126 vs 0.157).
- **Most important — far-OOD:** on novel chemotypes (max Tanimoto-to-train < 0.3), **MapLight 0.674 vs
  MolFormer 0.590** (near chance). +0.084 where it matters: the de-risking layer has to hold on chemistry
  it hasn't seen, and MolFormer collapses there while MapLight degrades gracefully. This reproduces Phase
  1's far-OOD finding (MapLight 0.862 vs MolFormer ~0.75 on the TDC far-band) on independent data.

## Why
BBB permeability is substructure-driven and chemotype-clustered — a multi-fingerprint + gradient-boosted
model (MapLight) interpolates well and stays calibrated, while a SMILES language model (MolFormer-XL) buys
little and is less robust off-distribution. The held-out B3DB result removes the "TDC scaffold split is a
soft proxy" caveat from Phase 1: MapLight's edge is real and persists out-of-sample.

## Recommendation / scorecard
- **Track 4 (BBBP): MapLight is the primary**, confirmed (scaffold 0.905 in Phase 1 + held-out B3DB 0.919
  here, both > MolFormer). Commercial-OK, CPU-only (~$0). Keep MolFormer-XL listed only as a secondary
  cross-check.
- **Ship the OOD flag:** even MapLight is only ~0.67 AUROC on far-OOD chemotypes, so the Explorer should
  attach a **Tanimoto-to-train confidence flag** on every BBB call (high confidence near-domain ≥0.4 where
  AUROC ≈0.96; low confidence far-OOD <0.3 where AUROC ≈0.67). The model ranking is settled; the honest
  reliability signal is the remaining UI work.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/maplight_b3db/maplight_b3db_result.json`;
eval `aws/maplight_b3db_eval.py`; instance `i-025e0c92adf159948` self-terminated; no strays.
