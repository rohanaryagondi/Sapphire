# Datafit curve — binder-vs-decoy AUROC vs # of per-target training pairs

**NEXT_STEPS item 1b** (companion to [`datafit_ceiling.md`](datafit_ceiling.md)).
Nav1.8 has **0 training pairs** in BindingDB_Kd and Phase 2b's binder-vs-decoy AUROC was
≈ 0.5. **How does the DTI head's binder-vs-decoy AUROC scale with the number of training
pairs per target, and is there a threshold above which it becomes useful?**

Run: `experiments/datafit_curve.py` · raw: `results/datafit_curve_20260607_030419.json` ·
plot: `results/datafit_curve.png` · 2026-06-07.

## Verdict (one line)

**The curve is NOT monotonic.** Bin-averaged AUROC climbs from 0.61 at 1–9 pairs → 0.60 at
10–39 → **peaks at 0.77 in the 40–149 bin** → drops back to 0.60 at 150–2000 pairs (with
σ doubling, 0.09 → 0.23). At the high end the head's quality is **bimodal**: some
data-rich targets are at 0.85+ (e.g. HRH3 0.88, MELK 0.90), others at chance or below
(FCGRT 0.24, HSP90AA1 0.58, HRH1 0.40 — the last from the ceiling experiment). No bin
average crosses the 0.80 "useful" line. **Data volume alone does not predict whether the
head learned a usable representation for a target.**

## Setup

- Checkpoint: PEER (`models/dti_bindingdb_pkd_peer`). Norms 6.286 / 1.542.
- Per target: up to 20 binders at pKd ≥ 7.0 (BindingDB_Kd, harmonized) + 60 random
  decoys (from compounds never measured against this target).
- One metric per target: random-decoy AUROC. EF@5% as a cross-check.
- 4 bins × 4 targets = 16 targets, seeded random pick (seed = 42), disjoint from the
  ceiling panel.
- Re-draw rule: if a candidate has < 5 binders at pKd ≥ 7.0, pick the next in the same
  bin. Heavy re-draw in the low and low-mid bins (most low-pair targets simply lack
  binders ≥ 7.0); see "Redraws" in the JSON for the full log.

### Picked targets

- **low (1–9 pairs):** P31390 Hrh1 (rodent, 7), P00491 PNP (5), P34998 CRHR1 (8), P00749 PLAU (6)
- **low-mid (10–39):** P31645 SLC6A4 (20), Q15109 AGER (14), P47205 lpxC (32), P28867 Prkcd (15)
- **high-mid (40–149):** P07550 ADRB2 (114), P08922 ROS1 (81), Q14680 MELK (79), Q59H18 TNNI3K (79)
- **high (150–2000):** P55899 FCGRT (166), Q9JI35 HRH3 (211), P24941 CDK2 (239), P07900 HSP90AA1 (157)

(Full redraw log in the JSON: ~48 redraws in low, ~8 in low-mid, 1 in high-mid, 0 in
high — confirms the per-target binder coverage is itself a function of per-target data
volume, as expected.)

## Per-target results

| bin | accession | gene | class | pairs | seq_len | n_binders | AUROC | EF@5% | mean pred binder/decoy | separation |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| low | P31390 | Hrh1 | gpcr | 7 | 486 | 6 | 0.344 | 0.00 | 7.56 / 7.79 | −0.231 |
| low | P00491 | PNP  | other | 5 | 289 | 5 | 0.783 | 0.00 | 8.01 / 7.83 | +0.179 |
| low | P34998 | CRHR1 | gpcr | 8 | 415 | 8 | 0.823 | 2.83 | 7.46 / 6.92 | +0.535 |
| low | P00749 | PLAU | protease | 6 | 431 | 6 | 0.481 | 0.00 | 6.15 / 6.26 | −0.118 |
| low-mid | P31645 | SLC6A4 | other | 20 | 630 | 15 | 0.650 | 1.25 | 8.24 / 8.01 | +0.233 |
| low-mid | Q15109 | AGER | other | 14 | 404 | 12 | 0.190 | 0.00 | 4.62 / 5.04 | −0.420 |
| low-mid | P47205 | lpxC | other | 32 | 303 | 5 | **0.973** | 13.00 | 7.38 / 6.22 | +1.152 |
| low-mid | P28867 | Prkcd | kinase | 15 | 674 | 8 | 0.583 | 0.00 | 6.62 / 6.56 | +0.062 |
| high-mid | P07550 | ADRB2 | gpcr | 114 | 413 | 20 | 0.782 | 3.00 | 7.57 / 6.85 | +0.719 |
| high-mid | P08922 | ROS1 | kinase | 81 | 2347 (trunc) | 9 | 0.693 | 5.11 | 6.35 / 5.90 | +0.449 |
| high-mid | Q14680 | MELK | kinase | 79 | 651 | 5 | **0.903** | 4.33 | 6.92 / 6.26 | +0.650 |
| high-mid | Q59H18 | TNNI3K | kinase | 79 | 835 | 5 | 0.697 | 0.00 | 6.49 / 6.36 | +0.131 |
| high | P55899 | FCGRT | other | 166 | 365 | 9 | **0.244** | 0.00 | 5.95 / 6.29 | −0.336 |
| high | Q9JI35 | HRH3 | gpcr | 211 | 445 | 20 | **0.877** | 4.00 | 8.64 / 7.81 | +0.833 |
| high | P24941 | CDK2 | kinase | 239 | 298 | 20 | 0.713 | 3.00 | 6.63 / 6.30 | +0.329 |
| high | P07900 | HSP90AA1 | other | 157 | 732 | 20 | 0.582 | 0.00 | 5.87 / 5.78 | +0.097 |

## The curve

Bin-averaged AUROC vs log10(per-target training pairs):

| bin | range | n | mean AUROC | std | mean log10(pairs) |
|---|---|---:|---:|---:|---:|
| low | 1–9 | 4 | 0.608 | 0.202 | 0.81 |
| low-mid | 10–39 | 4 | 0.599 | 0.278 | 1.28 |
| **high-mid** | **40–149** | **4** | **0.769** | **0.085** | **1.94** |
| high | 150–2000 | 4 | 0.604 | 0.233 | 2.28 |

Plot: `results/datafit_curve.png` (one point per target, colored by bin; chance and
useful thresholds; Nav1.8 anchor at 0 pairs / AUROC ~0.5 from Phase 2b).

## Interpretation

- **Nav1.8 (Phase 2b anchor):** 0 BindingDB pairs, AUROC ≈ 0.5 (chance).
- **low (1–9 pairs):** mean 0.61 ± 0.20 — close to chance, high variance. Most targets at this volume don't have enough binders ≥ 7.0 to test at all (heavy redraw log).
- **low-mid (10–39):** 0.60 ± 0.28 — still no consistent signal; large variance.
- **high-mid (40–149):** 0.77 ± 0.09 — the only bin where the head is consistently above chance, with tight error bars.
- **high (150–2000):** 0.60 ± 0.23 — drops back to near-chance on average because two of the four picks (FCGRT 0.24, HSP90AA1 0.58) sit below the chance line, dragging the mean down.

**Threshold for "useful" (AUROC ≥ 0.7):** first crossed at bin-average level in the
high-mid (40–149) bin. NOT preserved in the high bin.

**Threshold for "strong" (AUROC ≥ 0.8):** not crossed by any bin average. Crossed by
individual targets in every bin (CRHR1 at 8 pairs, lpxC at 32, MELK at 79, HRH3 at 211).

### What this says about Nav1.8

The simple "Nav fails because of the data gap → close the gap and you're done" narrative
is too clean. Nav at 0 pairs is firmly in the data-poor floor; fine-tuning would
mechanically lift it off that floor. But landing somewhere at 100+ pairs only gives a
~50/50 shot at the 0.80+ "good" regime versus the 0.50-ish "bad" regime — there are
targets in BindingDB with 150+ pairs that are still at chance, and we don't know what
makes the difference.

**Practical implication for a Quiver Nav fine-tune:** the experiment is still worth
doing, but should plan for the bimodal outcome — set a clear go/no-go threshold (e.g.
held-out scaffold AUROC ≥ 0.80) and budget for the case where Nav ends up in the FCGRT /
HSP90AA1 / BRAF (ceiling) "trained but unusable" camp.

### Caveats

- Random decoys only — same-MW matched decoys (the harder test) covered in the ceiling experiment.
- Binder count per target capped at 20; some high-bin targets have many more pairs but only their top-20 strongest binders are scored (keeps comparison uniform).
- AUROC ≈ 1.0 on a sub-10-binder target (lpxC, CRHR1) should be read with care — it says "the head ranks these binders above random decoys", not "the head could pick novel binders out of a real screen".
- BindingDB train/test split is opaque per-target; PEER's training set may include some of these binders. The numbers are an *upper bound* for the head's binder-vs-decoy ability per target. The conclusion (non-monotonic, bimodal at the high end) is robust to that bias because it's a relative comparison across targets, not an absolute pKd claim.
