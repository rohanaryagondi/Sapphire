# Phase 6 — PGK2 head: first FULL real-data verdict

**Date:** 2026-06-01. The checkpoint survey flagged `pgk2_del_cdd` as **"full eval not run."**
Phase 3 had only fragments (in-distribution hits-vs-decoys 0.984; Spearman vs DEL count ≈0; a
PGK1-homolog 0.973 buried inside a two-model script). This brings PGK2 to the **same standard as
the WDR91 SPR test** (`experiments/phase5_wdr91_spr.py`): one model load, real negatives,
AUROC + average precision + bootstrap CI + rare-positive enrichment + full score distribution +
graded potency. Script: `experiments/phase6_pgk2_fulleval.py`. Raw:
`results/phase6_pgk2_fulleval_20260601_134617.json`.

Readout: generative `binder_prob` (P(`<1>`) @ class position 1) with the `<PGK2_DEL>` task token —
the validated per-target readout. SMILES neutral-parent standardized (same as phase5). One model
in memory; loads, scores all sets, dumps JSON, exits.

## Test sets

| set | role | source | n (after std) |
|---|---|---|---|
| PGK2 DEL hits | positives | CACHE Challenge #7 `DEL_hit_candidates_1.csv` (read-count stratified) | 500 |
| **PGK1 ligands** | **real negatives** | ChEMBL `CHEMBL2886` — PGK2's paralog & the CACHE #7 selectivity counter-target | 99 |
| drug-like decoys | synthetic negatives | `wdr91_decoys.json` (MW-matched ChEMBL) | 500 |

**Critical caveat (stated up front):** PGK2 DEL hits are almost certainly the head's own
training data. So positives measure **chemotype RECALL, not novel-hit discovery.** Every number
below is an *in-distribution* result for the positives. This is the same caveat the audit raised
for the 0.97; it is load-bearing for how Quiver should read this verdict.

## Verdict — numbers

| Test | Result | Reading |
|---|---|---|
| **[1] PGK2 hits vs PGK1 HOMOLOG ligands (real neg)** | **AUROC 0.9734, 95% CI [0.960, 0.985], AP 0.995** | ✅ **strong, tight homolog selectivity on real negatives** — separates its hits from a paralog's real ligands |
| [2] PGK2 hits vs drug-like decoys (all hits) | AUROC 0.982, CI [0.972, 0.990], AP 0.988 | chemotype-recall upper bound — separates trained chemotype from random drugs |
| **[2b] Spike-in EF (top-50 strongest hits in 500 decoys)** | **EF5 11.0×, EF10 9.6×, AUROC 0.980** | ✅ **2.4× better top-of-list enrichment than WDR91 SPR (EF5 4.57×)** |
| [3] Graded: Spearman(score, DEL read count) | **−0.07, p=0.116 (n.s.)** | ❌ **no quantitative/potency ranking** — does not track enrichment |

EF is *not* reported for test [1] because positives outnumber negatives ~5:1 there (EF is bounded
near 1 when positives aren't rare); the spike-in test [2b] is the rare-positive design that makes
EF directly comparable to WDR91's SPR EF.

## The score distribution — the opposite of WDR91 (this is the key contrast)

The audit's sharpest critique of WDR91 (#17) was that its 0.816 sits on a degenerate near-zero
score mass — the head never actually "fires." **PGK2 is the inverse:**

| set | median | mean | max | frac >0.5 | frac <1e-3 |
|---|---|---|---|---|---|
| **PGK2 hits** | **0.99997** | **0.941** | 1.000 | **0.94** | 0.03 |
| PGK1 ligands | 0.00043 | 0.0031 | 0.026 | 0.00 | 0.61 |
| decoys | 0.00003 | 0.0020 | 0.144 | 0.00 | 0.80 |

The PGK2 head **genuinely fires** on its chemotype — 94% of hits score >0.5 (median ≈1.0) — while
both negative sets are crushed near zero (top PGK1 false positive only 0.026; even the top decoy
only 0.14). This is a clean, well-separated, calibrated-looking binary classifier on its trained
chemotype, **not** the faint-rank-structure-in-noise pattern WDR91 shows. The AUROC 0.97 is backed
by real separation, not a ranking artifact.

## What PGK2 is — and isn't

**IS:** a sharp **chemotype recognizer**. Given a candidate, it confidently re-identifies whether
the molecule belongs to PGK2's experimentally-derived hit space and rejects off-target/homolog
ligands (incl. the PGK1 paralog) and random drugs. High precision on its trained scaffold space;
EF5 11× when its strongest hits are spiked into a decoy library.

**ISN'T:** a novel-hit finder or a potency ranker. (a) The 0.97/0.98/11× are all **in-distribution
positives** (its own training hits) vs OOD negatives — it has *not* been shown to recall novel PGK2
scaffolds. (b) Within its hits, the score is flat-saturated near 1.0 and carries **zero graded
signal** (Spearman vs DEL read count −0.07, n.s.) — it cannot rank binders by strength/enrichment.

## PGK2 vs WDR91 — the honest existence proof

This confirms the audit's internal-contradiction finding (#1, #20): **PGK2 is the strong per-target
existence proof, not WDR91.**

| | PGK2 (`_del_cdd`) | WDR91 (`_asms`) |
|---|---|---|
| Homolog/real-neg selectivity | **0.973 [0.96, 0.985]** | — (WDR91 head: 0.18 vs PGK2 mols, inverted) |
| Fires on own chemotype? | **Yes — 94% of hits >0.5, median ≈1.0** | No — median 0.0; barely fires even on own actives |
| Spike-in EF5 (rare pos in decoys) | **11.0×** | 4.57× (SPR) / 5.25× (ChEMBL decoys) |
| Graded ranking | No (ρ=−0.07) | No (ρ=−0.15) |
| Test type | in-distribution recall | out-of-distribution (DEL actives vs ASMS head) |

The asymmetry is largely an in-/out-of-distribution artifact: PGK2 is tested on its own training
hits (so it looks excellent), WDR91 on a semi-independent DEL set (so it looks weak). Neither is a
clean prospective test. But the *capability ceiling* PGK2 demonstrates — a fine-tune that fires
sharply (94% >0.5) and rejects a close homolog at 0.97 — is real evidence that **per-target
fine-tuning on a target's own hit data yields a high-precision chemotype-triage classifier.**

## For Quiver (Q14)

1. **Per-target fine-tuning works as chemotype triage — PGK2 is the cleanest demonstration.** A
   fine-tune on a target's experimental hits gives a classifier that confidently re-recognizes that
   chemotype and rejects homolog ligands. That is a real, deployable virtual-screening triage gate.
2. **Expect recall + sharp rejection, not discovery or potency.** Saturated near-binary output, no
   graded ranking. Evaluate an in-house fine-tune by **enrichment factor on a held-out *scaffold*
   split** (not a random split — the random split here is what makes 0.97/11× optimistic), and do
   not expect Kd/potency ranking from it.
3. **The open question both heads leave unanswered:** novel-scaffold recall. PGK2's 0.97/11× are
   in-distribution; WDR91's OOD test collapses to non-specific. A genuine scaffold-split eval on
   Quiver screening/DEL data is the live decision (HANDOFF §7.1).

## Files
- Script: `experiments/phase6_pgk2_fulleval.py`
- Raw: `results/phase6_pgk2_fulleval_20260601_134617.json`
- Data: `data/pgk2/DEL_hit_candidates_1.csv` (1393 hits → 500 stratified), `data/pgk2/pgk1_chembl_ligands.json` (99), `data/wdr91/wdr91_decoys.json` (500)
- Supersedes the PGK2 fragments in `results/phase3_pgk2_indist_20260528_232751.json` and the
  PGK2 columns of `results/phase3_realdata_specificity_20260529_005231.json` (consolidated + CI'd here).
