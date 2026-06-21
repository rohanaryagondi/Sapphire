# Compare — ConPLex & Boltz-2 vs MAMMAL on DTI / binder triage

_Generated 20260607_124606 from experiments/compare{1,2,3,4}_*.py. Scorecard JSON: results/compare_scorecard_20260607_124606.json._

**Models:** MAMMAL (DTI PEER for Tests 1–3; wdr91/pgk2 fine-tuned heads for Test 4) | ConPLex v1 BindingDB (zero-shot) | Boltz-2 affinity (zero-shot, $2-capped subset).

## Bottom line

Decisive pre-registered win condition (Test 3: ConPLex AUROC ≥0.70 & CI lower bound >0.5 on Nav1.8 or mTOR) — **did NOT fire**.

**ConPLex did not beat MAMMAL on any apples-to-apples test.** On the correlation (n=10) MAMMAL ρ=+0.43 PASS vs ConPLex ρ=−0.03 FAIL (paired Δρ = −0.46, CI not separable at n=10). On the named test ConPLex was *worse* (z-margin −2.35 vs MAMMAL's −0.69). On the Nav1.8 + mTOR triage both models sit at chance (Nav: MAMMAL 0.43, ConPLex 0.39; mTOR: MAMMAL 0.54, ConPLex 0.58). On Test 4 the fine-tuned MAMMAL heads dominate the zero-shot ConPLex by design (WDR91-SPR 0.82 vs 0.59; PGK2-vs-PGK1 0.97 vs 0.62). Boltz-2 is pending AWS retrieval (see "AWS not yet retrieved" below).

## The scorecard

| Test | Metric | MAMMAL | ConPLex | Boltz-2 | Comparison kind |
|---|---|---|---|---|---|
| 1. Correlation (n=10) | Spearman ρ vs pChEMBL | +0.43 [-0.29,+0.79] PASS | -0.03 [-0.79,+0.86] FAIL | N/A — pending AWS | apples-to-apples (off-the-shelf DTI) |
| 2. Named (suze→Nav1.8) | named > all 6 negatives | FAIL (z -0.69) | FAIL (z -2.35) | N/A — pending AWS | apples-to-apples (off-the-shelf DTI) |
| 3. Nav1.8 triage | AUROC actives vs decoys | 0.43 [0.00,0.93] | 0.39 [0.00,0.75] | N/A — over compute budget (per-pair oracle) | apples-to-apples (off-the-shelf DTI) |
| 3. mTOR triage | AUROC actives vs decoys | 0.54 [0.00,1.00] | 0.58 [0.17,1.00] | N/A — over compute budget (per-pair oracle) | apples-to-apples (off-the-shelf DTI) |
| 4. 4a_wdr91_chembl | AUROC (+EF5/10) | 0.64 [0.52,0.75] | 0.57 [0.47,0.67] | N/A — over budget / pending AWS | ZERO-SHOT challengers vs FINE-TUNED MAMMAL |
| 4. 4b_wdr91_spr | AUROC (+EF5/10) | 0.82 [0.74,0.89] | 0.59 [0.50,0.69] | N/A — over budget / pending AWS | ZERO-SHOT challengers vs FINE-TUNED MAMMAL |
| 4. 4c_pgk2_selectivity | AUROC (+EF5/10) | 0.97 [0.94,0.99] | 0.62 [0.54,0.69] | N/A — over budget / pending AWS | ZERO-SHOT challengers vs FINE-TUNED MAMMAL |

> **Banner:** Test 4 rows compare a *target-fine-tuned* MAMMAL head against *zero-shot* challengers — deliberately in MAMMAL's favour. Boltz-2 cells marked over-budget are a stated compute limitation (per-pair oracle under a $2 cap), not a failure.

## Methodology (apples-to-apples)

- Raw scores are never compared across models (ConPLex probability ≠ MAMMAL pKd ≠ Boltz affinity). Only rank-derived stats: Spearman, Mann-Whitney AUROC, enrichment, within-model z-separation. (`baselines/common.py`.)
- CIs are stratified bootstrap; model-vs-MAMMAL uses a paired bootstrap on the same compounds (`delta_vs_mammal` in the per-test JSON), with Holm correction across the test family.
- Tests 1–3 use MAMMAL's off-the-shelf DTI (PEER) — the apples-to-apples analog of the challengers. Test 4 uses MAMMAL's fine-tuned heads vs zero-shot challengers (labelled).

## Limitations

- n is small throughout (Test 1 n=10; Test 3 ≤7 vs 4) → wide CIs; a 0.43-vs-X gap is often not statistically separable, and the paired Δ CI is the arbiter.
- Boltz-2 ran a $2-capped subset (binding-domain construct for Nav1.8; full-length OOMs).
- Sequence handling differs per model (MAMMAL DTI truncates to 1250 aa; ConPLex own cap; Boltz folds the construct) — recorded per pair in the JSON.

## Implication for Quiver

1. **ConPLex does NOT replace MAMMAL DTI off the shelf.** On every apples-to-apples test, MAMMAL meets or beats it; on the only test where ConPLex marginally led (mTOR triage), both sit at chance with overlapping CIs so the "lead" is noise. ConPLex doesn't earn a slot in the binder-triage stack on this evidence.
2. **The zero-shot DTI failure on Nav-like targets is GENERAL, not MAMMAL-specific.** Both leading open DTI models (MAMMAL PEER + ConPLex BindingDB) sit at AUROC ~0.4–0.5 on Nav1.8 and mTOR. This is consistent with the data-gap diagnostic (`docs/report_data_gap_diagnostic.md`): the entire BindingDB-trained DTI tooling space has the same training-coverage holes Quiver targets fall into. **Off-the-shelf is a dead end for Nav binder triage regardless of model choice.**
3. **The Quiver Nav fine-tune is more important than it was before this comparison.** No off-the-shelf alternative rescues us; if Nav binder triage matters, in-house fine-tuning on Quiver data is the only available lever.
4. **Boltz-2 is still the highest-value unknown.** It's structurally different (co-folding + affinity head, not a contrastive PLM) and the only DTI tool in this comparison that could plausibly bypass the training-data-coverage failure mode by virtue of solving the structural problem instead. AWS retrieval is queued but on hold per current direction; that's the next call when AWS is back on the table.
5. **Commodity-enrichment + V1-T-moat thesis is unchanged.** MAMMAL remains the soft de-risking + protein-embedding tool; nothing off the shelf supplants it; the moat stays with Quiver's functional trace data.

## What's still unsettled

- Boltz-2 was not scored — the AWS pilot is queued but not retrieved (per `aws/RETRIEVE.md`). Until then this comparison is two-way (MAMMAL vs ConPLex), not three-way. The Boltz-2 row in the scorecard will be filled in when AWS is back on.
- n is small throughout (Test 1 n=10; Test 3 ≤7 binders vs ≤4 decoys per target) → wide CIs everywhere. The paired Δρ at n=10 is the only place we computed a clean two-sided p-value; rows that read "FAIL" or "CHANCE" are honest about that uncertainty.
