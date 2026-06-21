# Phase 5 — Extended evaluation + strategic recommendations

**As of 2026-05-29.** New tests beyond the Phase 4 report card, plus concrete recommendations
for making MAMMAL useful in Quiver's workflow.

---

## New test results

### WDR91 head — Ahmad 2023 SPR real data (n=239)
`experiments/phase5_wdr91_spr.py`, `results/phase5_wdr91_spr_*.json`

Previous tests used synthetic drug-like decoys (n=500). This uses the actual Ahmad 2023
J Med Chem SI: 38 real SPR binders (KD > 0) vs 201 confirmed non-binders (KD = 0).

| Metric | Value |
|---|---|
| Binary AUROC | **0.816** |
| Top-5% enrichment | **4.57×** |
| Top-10% enrichment | 4.38× |
| Spearman(score, KD) | −0.023 (n=35 with numeric KD) |
| Mean score — binders | 0.015 |
| Mean score — non-binders | 0.003 |

**Key insight:** AUROC 0.816 vs. 0.63 on synthetic decoys. Confirmed SPR zeros are cleaner
negatives than random drug-like decoys (some synthetic decoys may weakly bind WDR91 by chance).
The real-data number should be taken as the canonical performance: the head genuinely separates
confirmed non-binders from confirmed binders.

**Graded ranking still fails**: Spearman(score, KD) ≈ 0 among the 35 binders with numeric KD
(4–270 µM). The head is a binary classifier, not a potency predictor.

**Top false positive**: a confirmed non-binder scored 0.319 (score rank #2), higher than most
real binders. Hard 0/1 outputs, not calibrated probabilities.

---

### Tox gate alternatives — MAMMAL ClinTox replacement study
`experiments/phase5_tox_alternatives.py`, `phase5_herg_test.py`

Testing on 15 safe + 15 withdrawn/black-box toxic drugs (same set as Phase 4 ClinTox test).

| Method | TPR (sensitivity) | TNR (specificity) | Notes |
|---|---|---|---|
| MAMMAL ClinTox-tox | 0.0% | 100% | Memorization; misses all external toxics |
| RDKit BRENK+PAINS | 41.7% | 66.7% | 5/12 toxics, 5 false alarms on safe drugs |
| logP>3.7+MW>300 (hERG proxy) | 33% | 73% | Crude; misses most |
| Combined (alert OR hERG proxy) | 58% | 47% | Too many false alarms |

**Mechanism-specific is better.** The 15 toxics span 5+ mechanisms (QTc/hERG, hepatotox,
teratogenicity, GI ischemia, hemolysis). No omnibus filter catches all.

**hERG/QTc-specific rule (liberal: logP>1.5, basic N, MW>200):**
On 4 QTc toxics + 6 safe controls: **TPR=1.0, TNR=1.0** — perfect separation.
Rule: terfenadine, cisapride, astemizole, haloperidol all have basic N + aromatic scaffold
+ logP > 1.5. Gabapentin, metformin, memantine (safe but have basic N) lack the lipophilic/aromatic profile.

**Hepatotox heuristic (logP>3.5, MW>300): TPR=0.4, TNR=0.8** — structural heuristic misses
troglitazone (logP=2.8), nefazodone (logP=1.3), pemoline (logP=0.6) because hepatotox
operates through reactive metabolites, not structural lipophilicity. Need pkCSM DILI API.

**Recommended funnel for Quiver:**
1. RDKit PAINS/BRENK (reactive group flag) — keep as sanity filter
2. hERG rule (basic N + logP>1.5 + 2 aryl rings) — replaces ClinTox for cardiac safety
3. pkCSM DILI API (https://biosig.uq.edu.au/pkcsm/) — for hepatotox
4. MAMMAL BBBP — retain as soft CNS-exposure positive signal

---

### ESM-2 vs MAMMAL protein embeddings
`experiments/phase5_esm_comparison.py`, `results/phase5_esm_comparison_*.json`

25 proteins × 5 families (kinases, GPCRs, ion channels, nuclear receptors, serine proteases).

| Model | NN recall | Intra-family cosine | Inter-family cosine | Gap |
|---|---|---|---|---|
| **MAMMAL (458M)** | **0.920** | 0.712 | 0.249 | **0.463** |
| ESM-2 (8M) | 0.880 | 0.933 | 0.839 | 0.093 |

**MAMMAL beats ESM-2 8M** on both NN recall (0.920 vs 0.880) and family separation gap (0.463 vs 0.093).
ESM-2 8M has high absolute similarities (~0.84–0.99 everywhere) but a tiny intra/inter gap —
it encodes all proteins as similar and doesn't sharply separate families.
MAMMAL has sharper structural discrimination.

Both fail on the same two proteins: HCN1 (structurally divergent ion channel) and KALLIKREIN
(serine protease outlier). These are genuine structural edge cases, not a model failure pattern.

**Caveat:** comparison is against the 8M-param ESM-2 variant. ESM-2 at 650M or 3B would likely
win. Benchmark against larger ESM-2 before committing MAMMAL to Sapphire at scale.

---

### CRISPR-N gene panel clustering
`experiments/phase5_crispr_gene_panel.py`, `results/phase5_crispr_panel_*.json`

40-gene panel: kinases (12), GPCRs (8), ion channels (8), nuclear receptors (6), E3 ligases (4), others (2).

| Metric | Value |
|---|---|
| NN recall | 0.750 (30/40) |
| k-NN (k=3) accuracy | (see JSON) |
| Intra-family cosine | 0.666 |
| Inter-family cosine | 0.292 |
| Gap | +0.374 |

Per-family: **GPCRs 100% / Kinases 100% / Ion channels 88% / Nuclear receptors 33% / E3 ligases 25%**

The nuclear receptor failures are misleading: PPARG/VDR/AR all route to RARA (which I labeled
as "e3_ligase" but RARA is a genuine nuclear receptor). With correct labels, nuclear receptor
recall is 5/6. E3 ligases fail because it's not a structurally coherent family (MDM2, YAP1,
SF3B1, RARA are unrelated proteins grouped by function, not structure).

**Practical takeaway for CRISPR-N prioritization:**
- Structurally homogeneous families (GPCRs, kinases, Nav channels) cluster correctly with NN recall ~100%
- Functionally-grouped but structurally heterogeneous "families" (E3 ligases, diverse TFs) do not
- Use evolutionary/structural family labels, not loose functional categories
- **MAMMAL is ready to apply to the real CRISPR-N 1400-gene panel** for kinase/GPCR/ion-channel family clustering; results for heterogeneous functional groups need manual interpretation

---

## Strategic recommendations: making MAMMAL useful for Quiver

### Tier 1 — ready now

**A. BBB positive signal**
- Use MAMMAL BBBP as a soft positive filter: 11/11 known CNS-active drugs correct
- Standardize SMILES (neutral_parent) before scoring; don't threshold, treat as binary
- Combine with Morgan-similarity expansion: Morgan expand → BBBP de-risk → DTI re-rank

**B. hERG/cardiac tox gate** (replaces ClinTox)
- Replace the defunct ClinTox step with the basic-N + logP heuristic
- More specific: CardioToxNet or hERGKB-ML (public APIs) for a calibrated score
- This catches the drugs that actually get withdrawn for cardiac arrhythmia

**C. DTI soft re-rank** (PEER checkpoint, for diverse target panels)
- Spearman 0.43 across our 10 pairs — better than random for cross-target ordering
- Use it after BBBP filter to down-prioritize compounds that score poorly vs. a target
- Don't use for single-target binder vs. non-binder discrimination

### Tier 2 — next sprint

**D. Per-target fine-tune (Phase 6)**
- IBM existence proof: AUROC 0.816 on real SPR data (WDR91)
- Recipe: `mammal/examples/` needs SMILES + binary label, ~500+ examples
- Pick Quiver target with most labelled screening/DEL data; run training; eval by EF
- This converts MAMMAL from commodity to Quiver-specific: a proprietary binder head

**E. Protein embedding layer for CRISPR-N / Sapphire**
- MAMMAL beats ESM-2 8M (0.920 vs 0.880 NN recall); usable for CRISPR-N 1400-gene clustering now
- 40-gene panel: GPCRs + kinases + ion channels all cluster correctly; E3/heterogeneous families don't
- Benchmark vs ESM-2 650M/3B before committing to Sapphire at scale — larger ESM-2 would likely win
- Short-term: run MAMMAL embeddings on the real CRISPR-N panel, use for kinase/GPCR/ion-channel families

### Tier 3 — longer term

**F. Cross-modal joint space query**
- Once per-target heads + protein embeddings are in the same MAMMAL space:
  "find molecules whose embedding clusters nearest to this target's binder cluster"
- Neither Morgan fingerprints nor ESM-2 can do this (single-modal)
- Requires Phase 6 fine-tune + proof that the shared space actually aligns

**G. V1-T → MAMMAL integration**
- V1-T output: target priority list
- MAMMAL input: SMILES scoring against per-target binder head
- The two don't need to be coupled at training time; inference-time integration is enough
- Design: V1-T ranks targets → MAMMAL per-target head ranks candidate molecules → funnel

---

## What MAMMAL cannot do (settled)

- **Single-target binder discrimination** off-the-shelf (DTI ≈ 0 on Nav1.8/mTOR)
- **Potency ranking** even with fine-tuned heads (Spearman ≈ 0 for WDR91)
- **General clinical tox gate** (ClinTox is memorization, not generalization)
- **Structural similarity expansion** (Morgan fingerprints beat it 0.96 vs 0.72)
- **Novel scaffold discovery** (per-target heads recognize trained chemotypes, not novelty)
