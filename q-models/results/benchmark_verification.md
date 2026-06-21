# MAMMAL published-benchmark verification

**Date:** 2026-05-28
**Question:** the paper (arXiv 2410.22367, Table 2) claims SOTA on 9/11 downstream tasks.
Do the claims hold when we reproduce them with the published checkpoints?

## Headline
**Every claim we can independently verify reproduces — MAMMAL's published numbers are honest.**
4 of the 11 tasks have public finetuned checkpoints and obtainable test sets; all 4 met or
beat the paper. The other 7 ship no public checkpoint, so they can't be verified off-the-shelf
(would require reproducing IBM's fine-tuning).

This does NOT change the usefulness verdict: high benchmark scores ≠ useful on Quiver's
problems (see `phase1_calibration.md`, `phase2b_quiver_targets.md`). "Honest benchmarks" and
"useful for us" are different questions — the benchmarks are honest; usefulness is narrow.

## Verified (4/11) — all hold

| Task | Metric | Paper | Reproduced | Verdict | Confidence |
|---|---|---|---|---|---|
| Drug-Target Interaction (PEER/BindingDB) | NRMSE | 0.906 | **~0.88** | ✅ holds | high — reproduces the metric; not the exact PEER holdout split |
| BBBP (MoleculeNet) | AUROC | 0.957 | **0.968** | ✅ holds | high — balanced held-out scaffold test (n=204) |
| TCR-epitope (Weber) | AUROC | 0.879 | **0.931** | ✅ holds | high — balanced sample (n=400, pos 0.48) |
| ClinTox (MoleculeNet) | AUROC | 0.986 | **~1.00** (CT_TOX ~1.0, FDA 1.0) | ✅ holds | **low** — both scaffold test folds have only ~9–10 minority examples; perfect AUROC is high-variance and possible split-overlap leakage |

DTI detail: on a BindingDB_Kd test sample, PEER NRMSE 0.880 (cold-split 0.859) — matches the
paper's 0.906. Reminder: NRMSE 1.0 = predicting the mean, so 0.906 is only ~9% better than the
mean (Pearson ~0.5–0.65) — the claim is real but the task is barely-solved.

## Not verifiable off-the-shelf (7/11) — no public checkpoint

| Task | Metric | Paper | Why not verifiable |
|---|---|---|---|
| Cell-Type Annotation (Zheng68k) | F1 | 0.763 | no published `scrna_cell_type` checkpoint |
| Cancer-Drug Response GDSC1 (TDC) | Pearson | 0.917 | no published `cell_line_drug_response` checkpoint |
| Cancer-Drug Response GDSC2 (TDC) | Pearson | 0.931 | " |
| Cancer-Drug Response (DeepCDR) | Pearson | 0.928 | " |
| Targeted Antibody Design (SAbDab) | CDRH3-AAR | 0.446 | no published antibody-design checkpoint |
| Antibody-Antigen Binding (HER2) | AUROC | 0.928 | no published checkpoint |
| PPI ΔΔG (SKEMPI S1131) | Pearson | 0.852 | no published PPI checkpoint |

Public checkpoints exist only for: `dti_bindingdb_pkd[_peer]`, `moleculenet_bbbp`,
`moleculenet_clintox_fda/tox`, `tcr_epitope_bind`, `protein_solubility`. The 7 above would each
need the dataset + a reproduced fine-tune to check, which is out of scope (and the meeting said
no fine-tuning).

## Extra published head (not in the 11-task table): protein_solubility

`protein_solubility` is an *example* fine-tune (not one of the paper's 11 tasks), benchmarked on
**DeepSol** (Khurana 2018; data Zenodo 1162886). We ran the full DeepSol test fold (1992 of 1999
proteins scored, 7 parse errors; balanced, pos rate 0.50) with MAMMAL's own generative readout
(`<SOLUBILITY><SENTINEL_ID_0>` → P(`<1>`) at class position 1):

| Task | Metric | Reference | MAMMAL head | Verdict |
|---|---|---|---|---|
| Protein solubility (DeepSol test) | accuracy | ~0.77 (DeepSol paper) | **0.734** | ✅ functional, **slightly below** the dedicated DeepSol baseline |
| " | AUROC | — | **0.829** | solid discrimination |

So it's a genuinely working head, ~at (a touch under) the task-specific baseline — competent, not
SOTA. Card reports no metric, so this is "our measured value vs the external DeepSol baseline," not
a paper-claim check. Script: `experiments/phase3_solubility.py`; raw `results/phase3_solubility_*.json`.

## How to reproduce
```
experiments/phase1_nrmse_verify.py            # DTI NRMSE vs paper
experiments/phase1b_molnet_eval.py bbbp       # BBBP AUROC
experiments/phase1b_molnet_eval.py tox        # ClinTox CT_TOX AUROC
experiments/phase1b_molnet_eval.py fda        # ClinTox FDA AUROC
experiments/phase1c_tcr_epitope_eval.py 400   # TCR-epitope AUROC
```
Raw: `results/phase1b_molnet_*_*.json`, `results/phase1c_tcr_epitope_*.json`.

## Caveats on the verification itself
- Splits: BBBP/ClinTox use a deepchem ScaffoldSplitter reproduced with rdkit (close to, maybe
  not identical to, MAMMAL's exact fold); TCR uses TDC's weber split; DTI uses TDC BindingDB_Kd,
  not the exact PEER protein-class holdout. Minor split mismatch could cause small train/test
  overlap (optimistic bias) — most material for the tiny ClinTox folds.
- For the high-confidence three (DTI, BBBP, TCR) the numbers are robust and clearly support the
  claims. ClinTox is "consistent with" rather than "independently confirmed."
