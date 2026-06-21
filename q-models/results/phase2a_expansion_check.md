# Phase 2a — hit-expansion step validation (SMILES similarity)

**Date:** 2026-05-28
**Question:** are MAMMAL base-model compound embeddings good for SMILES-similarity
nearest-neighbor search (the "expand a hit list" step)?
**Raw:** `results/phase2a_similarity_*.json`. Script: `scripts/phase2a_similarity_check.py`.

## Method
25 drugs across 5 classes (statins, β-blockers, SSRIs, benzodiazepines, NSAIDs) —
class members are structurally/functionally related. Embed each with the base model
(`encoder_last_hidden_state`, masked mean-pool, 768-d, L2-norm). For each molecule,
is its nearest neighbor (cosine) the same class? Compare to the standard
cheminformatics baseline: Morgan fingerprint (r=2, 2048 bit) Tanimoto.

## Result

| Metric | MAMMAL embedding | Morgan/Tanimoto |
|---|---|---|
| NN same-class rate | **0.72** (18/25) | **0.96** (24/25) |
| agreement w/ Tanimoto (Spearman, all pairs) | 0.33 | — |
| same-class − cross-class mean cosine | +0.132 | — |

## Read
- MAMMAL embeddings **do** carry real chemical-class signal (0.72 ≫ ~0.16 random; statins
  5/5, β-blockers 4/5, NSAIDs 3/5 recover cleanly).
- But **Morgan fingerprints are clearly better (0.96) and free.** MAMMAL's similarity only
  weakly tracks structural similarity (Spearman 0.33) and confuses flexible/small molecules
  (fluoxetine→ketoprofen, ibuprofen→metoprolol, several → citalopram).
- For *structural* hit-list expansion, classic fingerprints are the right tool. This test
  shows no advantage for MAMMAL embeddings on that job.

Caveats: n=25 / 5 classes (small); mean-pool of the encoder is one readout choice (a
different pooling or layer might do better); the base model's space is multimodal, so it's
unsurprising a SMILES-specific fingerprint wins at pure structural similarity.

## Implication for the Phase 2a workflow
MAMMAL's value in hit-list de-risking is the **property heads, not similarity search**:

1. **Expand** a hit list → use **Morgan/Tanimoto** (beats MAMMAL here).
2. **De-risk** → **MAMMAL BBBP (AUROC 0.968) + ClinTox (≈0.99)** — validated, reliable. ← MAMMAL's real contribution
3. **Re-rank** vs a target → **MAMMAL PEER DTI** (Spearman 0.43, tiebreaker only).

Net: MAMMAL is a strong **de-risking layer**, a usable **soft DTI re-ranker**, and **not**
the right tool for similarity expansion. Consistent with the "commodity enrichment" framing —
its edge here is calibrated property prediction, not embedding-based search.
