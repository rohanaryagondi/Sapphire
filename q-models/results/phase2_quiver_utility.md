# Phase 2 — Quiver-utility tests (de-risking funnel + protein embeddings)

**Date:** 2026-05-28. Scripts: `experiments/phase2a_pipeline.py`, `experiments/phase2c_protein_embedding.py`.

Two tests that exercise MAMMAL on what Quiver would actually do, using it where it's validated.

## Test 1 — End-to-end CNS de-risking funnel (meeting use case 2a / "how fast to molecules")
Workflow: seed CNS hit (diazepam) → expand by Morgan/Tanimoto over a 2039-compound library
(MoleculeNet BBBP, so survivors can be checked vs true penetrance labels) → BBBP filter →
ClinTox filter → ranked shortlist.

```
2039 library → 150 expanded → 149 BBB+ → 43 non-toxic → top 20      (48 s, 299 predictions)
```
- **Speed is real**: ~0.16 s/compound; a 150-candidate de-risk runs in under a minute. Answers
  the meeting's "how fast can we get to molecules" — fast.
- **BBBP filter is sound**: 99% precision vs true labels on the survivors. (Caveat: expanding from a
  CNS seed pre-enriches for penetrant compounds, so this isn't a hard test — the rigorous BBBP number
  is the held-out AUROC 0.968 in `benchmark_verification.md`.)
- **ClinTox is NOT deployable as-is**: it flagged 106/149 perfectly good CNS drugs (diazepam,
  chlorpromazine analogs, etc.) as toxic (median P_tox = 1.0). As a hard filter it would discard most
  viable candidates. Needs recalibration / a sensible threshold before use — do not gate on it.

**Takeaway:** the expand→de-risk workflow is fast and usable **with BBBP as the de-risking filter**;
swap ClinTox for a calibrated tox model (or recalibrate it) before relying on toxicity gating.

## Test 2 — Protein embeddings recover functional family (CRISPR-N clustering / Sapphire KG)
Embedded 25 proteins across 5 families (kinase, GPCR, ion channel, protease, nuclear receptor) with
the base model (encoder last-hidden-state, masked mean-pool, 768-d) and checked family structure.

```
nearest-neighbor same-family: 0.92  (random ~0.17)
intra-family − inter-family mean cosine: +0.457
```
- Strong family recovery — 23/25 nearest neighbors are same-family. The 2 misses are genuine
  outliers (GRIN1, a glutamate-gated channel grouped with kinases; CASP3, a small caspase).
- Contrast with **compound** embeddings (0.72, lost to Morgan fingerprints): for **proteins**,
  MAMMAL embeddings are strong and usable.
- **Relevance:** supports the meeting's CRISPR-N idea (cluster the ~1400 genes by functional state)
  and Sapphire (gene/drug nodes in a shared embedding space). MAMMAL gives sensible gene/protein
  representations off-the-shelf.
- **Caveat:** same-family proteins share sequence, so a plain ESM/k-mer baseline would likely also
  cluster them well — we did NOT benchmark against ESM. This shows MAMMAL embeddings are *sensible*,
  not that they beat a dedicated protein LM. If protein embeddings become load-bearing for Sapphire,
  benchmark MAMMAL vs ESM-2 directly.

## Net
MAMMAL's usable Quiver surface: **(1) BBBP de-risking** (deployable), **(2) protein/gene embeddings**
for clustering/KG (sensible; benchmark vs ESM before committing), **(3) a fast workflow harness**.
Not usable: ClinTox gating (over-predicts), DTI single-target triage, compound similarity search
(fingerprints win). See also the target-specific binder checkpoints in
`docs/mammal_checkpoint_survey.md` — the most promising untested lead.
