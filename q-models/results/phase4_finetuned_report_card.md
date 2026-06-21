# Phase 4 — Fine-tuned MAMMAL heads: complete performance report card

**As of 2026-05-29.** Every publicly available fine-tuned MAMMAL-458M head, tested on **real /
literature data** (not just benchmark AUROC), with calibration, per-direction reliability, and
out-of-distribution behavior. This is the consolidated picture. Per-head detail:
`phase1_calibration.md` (DTI), `phase4_bbbp_literature.md` (BBBP), `phase3_wdr91_finetune.md`
(per-target); raw runs `results/phase*_*.json`.

## The report card

| Head | Task | Benchmark | Real/literature result | Calibration | Out-of-distribution | Quiver verdict |
|---|---|---|---|---|---|---|
| `dti_bindingdb_pkd` (cold) | drug–target pKd | NRMSE 0.86 | Spearman **−0.03** on our 10 pairs | regression | dead on our target classes | ❌ wrong checkpoint for us |
| `dti_bindingdb_pkd_peer` | drug–target pKd | NRMSE 0.88 (≈paper 0.906) | Spearman **0.43** our pairs; single-target triage (Nav1.8/mTOR) **≈0** | regression, ~9% better than predicting the mean | coarse cross-target ranking only | ⚠️ soft re-rank; **no** single-target triage |
| `moleculenet_bbbp` | BBB penetrance | AUROC **0.968** | lit: CNS-active 11/11; **TNR 0.70** (over-passes cetirizine/atenolol/domperidone) | **95% hard 0/1**, uncalibrated | over-calls "penetrant" on small peripheral drugs | ⚠️ soft **positive** signal, not a rule-out gate |
| `moleculenet_clintox_tox` | clinical toxicity | AUROC **1.000** | **0% sensitivity to external toxic drugs**; 0% false-alarm on safe | **100% hard 0/1**; encoding-fragile (1/6 flip) | memorizes ~112 train toxics; no generalization | ❌ **not usable as a tox filter** |
| `moleculenet_clintox_fda` | FDA approval | AUROC **1.000** | posRate 0.94 (trivially imbalanced); TPR 0.93 / TNR 1.00 | 62% saturated | near-trivial majority-class task | ❌ not meaningful for Quiver |
| `tcr_epitope_bind` | TCR–epitope binding | AUROC **0.931** | balanced n=200: AUROC **0.959**, TPR 0.94 / TNR 0.79 | **28% saturated — reasonably calibrated** | not tested OOD | ➖ low Quiver relevance (immuno-oncology); best-behaved head |
| `protein_solubility` | solubility | (not a paper task) | DeepSol test **acc 0.734 / AUROC 0.829** (n=1992); balanced AUROC 0.850, **TPR 0.62** / TNR 0.84 | **17% saturated — calibrated** | held-out test fold (real) | ✅ functional, ~at DeepSol baseline; misses ~38% of soluble; modest |
| `…wdr91_asms` (per-target) | WDR91 binder | none published | OOD AUROC **0.63**, top-5% enrichment **5.25×**; loses to PGK2 mols on real-data specificity (0.18) | generative hard 0/1 | weak; barely fires on own actives | ⚠️ weak; chemotype-recall only |
| `…pgk2_del_cdd` (per-target) | PGK2 binder | none published | in-dist **0.97** vs PGK1 homolog ligands; **no graded ranking** (Spearman vs DEL count ≈0) | generative hard 0/1 | recognizes trained chemotype; unproven on novel | ⚠️ chemotype triage, not discovery |

## Five findings that hold across the whole model

1. **Benchmark AUROC ≠ deployable per-compound filter.** Every head ranks well on its own
   dataset (0.93–1.0) yet fails per-compound out-of-distribution — over-passing, under-detecting,
   or flipping. The headline numbers are honest for *ranking on the training distribution*, not
   for *using the model on a new compound*.

2. **The small-molecule (MoleculeNet) heads emit saturated hard 0/1, not calibrated
   probabilities** (BBBP 95%, ClinTox-tox 100%, ClinTox-FDA 62% of scores at ~0 or ~1) — you
   cannot threshold-tune or rank within a class by their "probability." The **protein heads are
   better calibrated** (TCR 28% saturated, solubility 17%), giving more usable graded scores.
   So this is a MoleculeNet-head pathology, not a whole-model one.

3. **Out-of-distribution generalization is poor and head-specific.** ClinTox-tox: 0% sensitivity
   to external clinically-toxic drugs (memorization). BBBP: over-passes small efflux substrates.
   Per-target heads: recognize their trained chemotype, not novel scaffolds. The model is
   reliable inside its training distribution and unreliable outside it.

4. **Input-form sensitivity, varying by head.** BBBP is robust to SMILES atom-reordering (0/6
   flip) but sensitive to protonation/salt form. ClinTox-tox flips on pure re-encoding (1/6).
   → standardize protonation/salt/tautomer before scoring; for ClinTox even that isn't enough.

5. **The earlier "ClinTox over-predicts toxicity" was an artifact.** It came from feeding raw
   isomeric/charged SMILES (phase2b). With clean neutral SMILES + the validated readout, ClinTox
   does the opposite — it under-detects (calls almost everything non-toxic). The real problem is
   no generalization, which recalibration can't fix.

## Net: what MAMMAL's fine-tuned heads are actually good for at Quiver

- **Genuinely useful:** `moleculenet_bbbp` as a *soft positive* CNS-exposure signal (not a rule-out
  gate); protein/gene embeddings (separate finding, see `phase2_quiver_utility.md`); DTI-PEER for
  coarse cross-target re-ranking only.
- **Modest:** `protein_solubility` (≈baseline); per-target fine-tunes as chemotype-triage gates on
  in-house screening data (the recipe works but is bounded — `phase3_wdr91_finetune.md`).
- **Not usable as-is:** `moleculenet_clintox_*` (tox gate misses real toxics; FDA trivial), DTI
  single-target triage.
- **Cross-cutting rule for any deployment:** standardize input structures; treat scores as binary
  labels, not probabilities; validate on a held-out scaffold split, not benchmark AUROC; expect
  in-distribution-only reliability.

## Scripts / raw
`experiments/phase4_bbbp_literature.py`, `phase4_molnet_audit.py`, `phase4_clintox_literature.py`,
`phase4_smiles_robustness.py`, `phase4_tcr_solubility_calib.py`; DTI + per-target in earlier phases.
Raw JSON: `results/phase4_*_*.json`.
