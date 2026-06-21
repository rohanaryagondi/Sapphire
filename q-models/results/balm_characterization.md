# BALM — deep operating-envelope characterization (overnight Phase 1, 2026-06-14)

**Model:** BALM (ESM-2-150M + ChemBERTa-77M two-tower, cosine = pKd). **Run:** AWS g5.xlarge ~$0.50,
`aws/balm_characterization.py`, all 5 sections completed cleanly, instance terminated.

**TL;DR — the n=11/7 win was real but NOT the whole story.** BALM is a useful *family-level
binder-vs-decoy triage* tool on **some** targets, but it **cannot do paralog selectivity** (it's
biased toward the wrong Nav), it is **below chance on GPCRs**, and its strong Nav1.8/mTOR numbers do
**not** generalize uniformly across families. Use it as coarse triage on data-rich / kinase-like
targets → hand the shortlist to Boltz-2 for selectivity and the data-poor targets.

## A. Per-target binder-vs-decoy (Quiver panels) — reproduces the win
| Target | n | cosine-AUROC | binder/decoy sep |
|---|---|---|---|
| Nav1.8 | 11 | 0.857 | +0.31 |
| mTOR | 7 | 1.000 | +0.30 |
Confirms the original cross-modal result on the small panels.

## B. Cross-paralog SELECTIVITY — ❌ BALM cannot resolve the right paralog (critical)
For the 7 Nav1.8 binders, scored against Nav1.8/1.7/1.5/1.1: **only 2/7 (0.29) rank Nav1.8 highest.
Nav1.5 (SCN5A, the *cardiac* channel — the off-target you most want to avoid) is the argmax for 5/7**,
including **suzetrigine** (the actual Nav1.8-selective drug: Nav1.5 0.58 > Nav1.8 0.51). Only A-803467
and carbamazepine land Nav1.8 on top.

**Implication:** BALM's cosine answers "does this compound bind *a* Nav channel" but is *worse than
useless* for "which Nav paralog" — it systematically prefers Nav1.5. For selectivity, **Boltz-2**
(which ranked Nav1.8 #1, albeit narrowly) is the tool, not BALM.

## C. Multi-family generalization (ChEMBL actives/inactives, n=40+40) — the reality check
| Target | family | AUROC | sep | calibration (Spearman pKd vs pChEMBL) |
|---|---|---|---|---|
| DRD2 | GPCR | **0.43** (below chance) | −0.02 | −0.14 |
| ADRB2 | GPCR | **0.42** (below chance) | −0.02 | −0.14 |
| EGFR | kinase | 0.62 | +0.08 | 0.23 |
| BRAF | kinase | **0.96** | +0.08 | **0.68** |
| MTOR | kinase/lipid | 0.64 | +0.10 | 0.37 |
| **by family** | | **GPCR 0.43 · kinase 0.79 · kinase-lipid 0.64** | | |

**This is the load-bearing finding.** On proper independent panels with real n, BALM is **below
chance on GPCRs**, mixed on kinases (BRAF excellent, EGFR/mTOR modest). The headline Nav1.8 0.857 /
mTOR 1.000 came from **small, favorable Quiver panels** — they overstate the general case.
Calibration tracks discrimination: pKd is meaningful only where AUROC is high (BRAF Spearman 0.68);
on GPCRs it's noise/negative. So BALM's absolute pKd is **not** trustworthy off its strong targets.

## D. Applicability domain / leakage — inconclusive (underpowered)
On the 18 Quiver compounds, "all" AUROC 0.90 but the novel-scaffold stratum (max-Tanimoto < 0.3)
had only **n=5** → AUROC not computable (insufficient label balance). **The memorization-vs-
generalization question is not cleanly resolved by this run** — but section C is the better proxy:
BALM clearly *does* generalize to unseen ChEMBL actives on BRAF/kinases and clearly *fails* on
GPCRs, so it's distribution/target-dependent, not pure memorization. (A future run should stratify
the larger ChEMBL pool by novelty.)

## E. Truncation probe — embedding is global/coarse, not pocket-specific
Nav1.8 (1956 aa, ESM-2 1024 cap): N-terminal-1024 AUROC **0.857** = pore-window(900–1924) AUROC
**0.857** — *identical*. Feeding the actual pore/DIV region changes nothing. **BALM's protein
representation is a coarse global pool, not pocket-aware** — which mechanistically explains why it
can't do paralog selectivity (paralogs differ in specific pore residues BALM's global embedding
washes out) and why truncation doesn't matter.

## Operating envelope (when to trust BALM, and why)
- ✅ **Coarse binder-vs-decoy triage on data-rich / kinase-like targets** (BRAF 0.96; the Quiver
  Nav1.8/mTOR panels). Fast, library-scale cosine retrieval. Good first-pass filter.
- ❌ **Paralog / isoform selectivity** — fails (Nav1.8 vs 1.5/1.7); biased to the cardiac off-target.
- ❌ **GPCRs** — below chance on real panels.
- ⚠️ **Uniform cross-family use** — performance is target-dependent (GPCR 0.43 → BRAF 0.96); do not
  assume the Nav/mTOR numbers transfer.
- ⚠️ **Absolute pKd** — trust only where discrimination is strong (BRAF); elsewhere rank-only at best.
- **Mechanism:** sequence-level two-tower over BindingDB Kd → learns coarse compound-class × protein-
  family affinity; the global pooled protein embedding (truncation-invariant) lacks the pocket-level
  resolution needed for selectivity, and coverage is family-skewed (kinase-rich, GPCR-weak here).

**Operational rule:** BALM cosine = cheap family-level triage on favorable targets → **Boltz-2** for
selectivity and data-poor/novel targets. The two are complementary, not interchangeable.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/balm_char/balm_characterization_result.json`,
eval `aws/balm_characterization.py`. Supersedes the n=11/7-only read in `results/balm_crossmodal.md`.
