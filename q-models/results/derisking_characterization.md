# De-risking layer — deep operating-envelope characterization (overnight Phase 2, 2026-06-14)

**Models:** MolFormer-XL + ChemBERTa-2 (LM→logreg probes) on TDC **BBB_Martins**, **hERG_Karim**,
**DILI** — all **Murcko-scaffold-split** — plus a dedicated **Morgan-FP+XGBoost** hERG model and an
**ADMET-AI** cross-check. **Run:** AWS g5.xlarge ~$0.40, `aws/derisking_characterization.py`, 111 s,
instance terminated. The deep axis here is **applicability domain (AD)**: AUROC stratified by
max-Tanimoto-to-train (far/OOD <0.3 · mid 0.3–0.5 · near >0.5).

## Headline findings
1. **Applicability domain is the dominant reliability lever.** Every model is good *near* training
   data and unreliable on novel scaffolds. hERG is the starkest:

   | endpoint | model | far/OOD (<0.3) | mid (0.3–0.5) | near (>0.5) |
   |---|---|---|---|---|
   | hERG | MolFormer-XL | **0.609** | 0.722 | 0.852 |
   | hERG | ChemBERTa-2 | **0.562** (≈chance) | 0.773 | 0.826 |
   | BBB | MolFormer-XL | 0.747 | 0.736 | 0.904 |
   | BBB | ChemBERTa-2 | 0.645 | 0.869 | 0.894 |
   | DILI | MolFormer-XL | 0.648 | 0.978 | 0.993* |
   | DILI | ChemBERTa-2 | 0.817 | 0.785 | 1.000* |

   *DILI near/mid bands have tiny n (24 each) → unstable. **Operational rule: gate every de-risking
   call by Tanimoto-to-train; on novel chemotypes (Tanimoto<0.3) treat the prediction as
   low-confidence — hERG in particular is near chance there.**
2. **Dedicated Morgan-FP+XGBoost BEATS the LMs on hERG.** On TDC scaffold-split hERG (n_test 2689):
   **XGBoost(Morgan-2048) AUROC 0.890 vs ChemBERTa-LM 0.815 (+0.075)**, Brier 0.138. For the hERG
   cardiac gate, the simple fingerprint model is the better predictor — adopt it over the LM probe.
   (Consistent with the literature: fingerprints are competitive-to-better on ADMET.)
3. **Scaffold generalization is mostly OK.** Random-vs-scaffold AUROC gaps are small (−0.03 to +0.08)
   — these models don't collapse purely from scaffold novelty; the AD/Tanimoto effect (point 1) is
   the real degrader. The one notable scaffold-sensitivity: ChemBERTa-2 on DILI (gap +0.08).
4. **ADMET-AI numbers here are leakage-inflated — do not quote them as external.** ADMET-AI DILI
   0.985 / BBB 0.964 look spectacular, but ADMET-AI (Chemprop multitask) is **trained on these exact
   TDC datasets**, so on the TDC test split this is effectively in-distribution. Use ADMET-AI as a
   gate, but its honest external performance is the ~0.83 DILI we measured on our independent panel,
   not 0.98.

## Per-track verdicts
**Track 4 — BBBP: MolFormer-XL stays the winner, with an AD caveat.** It is the more OOD-robust of
the two (far/OOD 0.747 vs ChemBERTa 0.645; near 0.904). Trust it near training chemistry; flag
novel-scaffold compounds. ChemBERTa-2 is a fine commercial second but weaker on novel scaffolds.

**Track 5 — hERG/DILI: switch the hERG gate to Morgan-FP+XGBoost.** It beats the LM (0.890 vs 0.815)
and is cheaper. DILI stays the hardest endpoint — small data, modest OOD AUROC (0.65–0.82), and
ADMET-AI's apparent strength is TDC-training leakage; keep ADMET-AI + ChemBERTa as a soft DILI gate
but don't over-trust it. **For all tox endpoints, report a Tanimoto-to-train confidence flag** — the
single most decision-relevant addition to the de-risking layer.

## Mechanism / why
These are all ligand-only models learning local chemical-space regularities; they interpolate well
near labeled chemistry and extrapolate poorly. The LM embeddings don't beat a Morgan-FP+XGBoost on
hERG because the signal is substructure-driven (fingerprints capture it directly). hERG's OOD
collapse (→0.56) reflects how chemotype-specific blockade is — a novel scaffold's blockade isn't
inferable from distant training analogs.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/derisking_char/derisking_characterization_result.json`,
eval `aws/derisking_characterization.py`. Deepens the earlier MolFormer/ChemBERTa results with the
scaffold + AD + dedicated-hERG axes.
