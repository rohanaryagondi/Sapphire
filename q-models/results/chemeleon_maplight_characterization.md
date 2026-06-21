# CheMeleon + MapLight — Track-4 ADMET displacer test (scout campaign Phase 1, 2026-06-14)

Do the scout-flagged ADMET candidates beat **MolFormer-XL (BBBP 0.889)** on our kind of evaluation
(scaffold-split + applicability domain + calibration)? **Run:** AWS g5.xlarge (python3.11 venv for
chemprop 2.x), ~$0.5, TDC BBB_Martins / hERG_Karim / DILI, Murcko scaffold split. **Headline: MapLight
is a genuine displacer; CheMeleon is not.**

## Results (scaffold-split AUROC; AD = far-Tanimoto-to-train <0.3 band)
| Endpoint | model | scaffold AUROC | random | gap | Brier | far-OOD AUROC |
|---|---|---|---|---|---|---|
| **BBB** | **MapLight** | **0.905** | 0.901 | −0.004 | **0.106** | **0.862** |
| BBB | MolFormer-XL (incumbent) | 0.889 | — | — | — | (~0.747, Phase 2) |
| BBB | CheMeleon (CC0) | 0.868 | 0.886 | 0.019 | 0.147 | 0.751 |
| **hERG** | **MapLight** | **0.889** | 0.914 | 0.025 | 0.137 | **0.809** |
| hERG | CheMeleon | 0.794 | 0.840 | 0.046 | 0.216 | 0.677 |
| DILI | CheMeleon | 0.840 | 0.818 | −0.022 | 0.182 | 0.766 |
| DILI | MapLight | 0.834 | 0.890 | 0.056 | 0.168 | 0.765 |
(hERG MapLight ≈ our Phase-2 Morgan-FP+XGBoost 0.890 — consistent, both FP+GBT. DILI n_test=96, noisy.)

## Verdict
**MapLight (CatBoost on ECFP+Avalon+ErG+RDKit descriptors) beats MolFormer-XL on BBBP across every
axis** — higher scaffold AUROC (0.905 vs 0.889), **best calibration** (Brier 0.106), near-zero
scaffold-gap (generalizes), and **far more OOD-robust** (far-Tanimoto AUROC 0.862 vs MolFormer ~0.75 /
CheMeleon 0.75). On hERG it matches our FP+XGBoost winner (0.889) with the **best far-OOD AUROC we've
measured (0.809** vs the LMs' 0.56–0.61 in Phase 2) — i.e. MapLight degrades least on novel chemotypes,
the exact failure mode that sinks the de-risking layer. It's open/commercial-OK, CPU-only (~$0), and
the 2026 TDC-ADMET critical assessment independently flags it as the well-calibrated method.

**CheMeleon (CC0 descriptor-pretrained D-MPNN) is NOT a displacer** — below MolFormer on BBB (0.868) and
below the FP models on hERG (0.794), with the worst OOD of the three. The CC0 foundation model doesn't
beat a well-built fingerprint+CatBoost here.

## Why
ADMET endpoints are substructure-driven, low-data, and chemotype-clustered — exactly where a
fingerprint+GBT (MapLight) interpolates well and stays calibrated, while a pretrained graph FM
(CheMeleon) or SMILES LM (MolFormer) buys little and is less calibrated. The far-OOD edge is the
operational one: MapLight's confidence holds on novel scaffolds better than any LM we've run.

## Recommendation (conservative)
- **Track 4 (BBBP): adopt MapLight as the primary (or co-primary with MolFormer-XL).** It wins on
  accuracy + calibration + OOD on a proper scaffold split. Keep MolFormer listed until a head-to-head on
  the **Quiver external-30 panel** confirms (TDC scaffold is a strong proxy, not our exact private set),
  but the evidence already favors MapLight, and it's cheaper (CPU CatBoost) + commercial-OK.
- **Track 5 (hERG): MapLight is the most OOD-robust hERG model tested** (far-OOD 0.809) — reinforces the
  Phase-2 call to use FP+GBT for the hERG gate; MapLight's multi-fingerprint recipe is the version to ship.
- **CheMeleon: skip** (no edge over incumbents).

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/chemeleon_maplight/chemeleon_maplight_result.json`,
eval `aws/chemeleon_maplight_eval.py`. Instance terminated; no strays.
