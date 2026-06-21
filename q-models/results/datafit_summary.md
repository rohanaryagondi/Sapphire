# Where is MAMMAL actually data-suited? — synthesis

**NEXT_STEPS items 1b + 1c, follow-up to the per-target data audit
([`dti_train_data_distribution.md`](dti_train_data_distribution.md)).**

The Nav1.8 binder-vs-decoy AUROC test failed at chance (Phase 2b). The audit showed
BindingDB_Kd has **zero Nav training pairs** and only 5 incidental rodent SCN pairs
out of 42,236. We then asked: **where MAMMAL is data-suited, does the same test work?**

Two experiments answered this together: a tight **ceiling test** on 6 well-trained targets
(incl. mTOR, the one Quiver target with hundreds of training pairs), and a **threshold
curve** sweeping 16 targets stratified by training-pair count.

- Ceiling: [`datafit_ceiling.md`](datafit_ceiling.md) (6 targets, full rig: random AUROC + MW-matched AUROC + Spearman + off-target Δ)
- Curve: [`datafit_curve.md`](datafit_curve.md) (16 targets across 4 bins, random-decoy AUROC + EF@5%)
- Scripts: `experiments/datafit_ceiling.py`, `experiments/datafit_curve.py`
- Shared helpers: `mammal_quiver/datafit.py`
- Raw: `results/datafit_ceiling_20260607_025514.json`, `results/datafit_curve_20260607_030419.json`, `results/datafit_curve.png`

## The headline

**Data volume is necessary but not sufficient.** Above ~150 pairs the head's binder-vs-decoy
quality is **bimodal**: some data-rich targets work brilliantly (RORC 0.97/0.95, CA2 0.87/0.84,
Adrb2 0.87/0.88, HRH3 0.88, MELK 0.90), and others — including the *most*-trained target in
the entire BindingDB pool — sit at or below chance (BRAF 0.47, FCGRT 0.24, HRH1 0.40,
HSP90AA1 0.58). There is no obvious class, size, length, or family predictor for which mode
a target lands in.

The threshold curve (16 targets, 4 bins) makes the bimodality visible at the population level:
bin-averaged AUROC climbs from 0.61 (1–9 pairs) → 0.60 (10–39) → **peaks at 0.77 (40–149)** →
drops back to 0.60 (150–2000), with σ doubling in the top bin.

## The numbers in one place

### Ceiling (6 well-trained targets, full rig)

| accession | gene | class | n_pairs | AUROC random | AUROC matched | Spearman | Off-target Δ |
|-----------|------|-------|--------:|-------------:|--------------:|---------:|-------------:|
| P51449 | RORC | nuclear_receptor | 374 | **0.97** | **0.95** | −0.10 | +0.68 |
| P00918 | CA2 | other | 269 | **0.87** | **0.84** | **0.87** | **+1.97** |
| Q8K4Z4 | Adrb2 | gpcr | 211 | **0.87** | **0.88** | **0.76** | +0.83 |
| P42345 | MTOR | kinase | 192 | 0.76 | 0.56 | 0.27 | **−1.12** |
| P15056 | BRAF | kinase | 532 | 0.47 | 0.46 | 0.45 | +1.18 |
| P31389 | HRH1 | gpcr | 184 | 0.40 | 0.33 | −0.14 | +0.68 |

Reading: AUROC ≥ 0.80 on both decoy types = head clearly works for that target. **3 of 6
land there. BRAF — the most-represented target in the entire pool — is at chance.**

### Curve (16 targets across 4 bins, random-decoy AUROC)

| bin | range | n | mean AUROC ± std | targets in this bin |
|---|---|---:|---:|---|
| low | 1–9 | 4 | 0.61 ± 0.20 | Hrh1(0.34), PNP(0.78), CRHR1(0.82), PLAU(0.48) |
| low-mid | 10–39 | 4 | 0.60 ± 0.28 | SLC6A4(0.65), AGER(0.19), lpxC(0.97), Prkcd(0.58) |
| high-mid | 40–149 | 4 | **0.77 ± 0.09** | ADRB2(0.78), ROS1(0.69), MELK(0.90), TNNI3K(0.70) |
| high | 150–2000 | 4 | 0.60 ± 0.23 | FCGRT(0.24), HRH3(0.88), CDK2(0.71), HSP90AA1(0.58) |

## What this changes vs the prior story

| Belief going in | What we learned |
|---|---|
| Nav1.8 failed because of a data gap; rich-data targets will work. | Half do. Half don't. Data gap is *consistent with* the failure but doesn't *predict* the binary outcome at the high end. |
| Quiver per-target fine-tuning on Nav1.8 will close the gap. | Mechanically true (lifts Nav off the 0-pair floor), but the high-data regime is bimodal — a Nav fine-tune could land in either mode. Plan for go/no-go on held-out scaffold AUROC ≥ 0.80. |
| mTOR is the safe Quiver target (192 pairs, top-10 in BindingDB). | mTOR works on random decoys (0.76) but **collapses to chance on MW-matched** (0.56) and **inverts off-target (Δ −1.12)**. The Quiver-relevant kinase target is *not* a clean MAMMAL win. The kinase domain (~aa 2182–2516) is *outside* the 1250-aa truncation window — this is the obvious mechanistic suspect and a one-script follow-up. |
| The head encodes a single property "binding to target X". | AUROC and Spearman do not track each other. RORC discriminates binders from decoys at 0.97 but cannot rank-order binders by potency (Spearman −0.10). BRAF cannot discriminate (AUROC 0.47) but can rank-order (Spearman 0.45). The head encodes different binding signals on different targets. |

## What it means for Quiver

- **MAMMAL DTI head off-the-shelf is reliable on a minority of targets**, with no upfront
  way to know which targets those are without testing. As a screening tool it's a
  per-target gamble.
- **The "soft cross-target re-ranking" verdict stands.** Use the head to triage compounds
  the head already ranks highly *somewhere*; don't use it as a single-target binder/non-
  binder gate.
- **Nav1.8 fine-tune ROI is now uncertain rather than free-money.** Off-the-shelf is at
  chance; fine-tuning moves the floor; the ceiling depends on which mode Nav lands in at
  high data. Worth doing, but plan for the bad case.
- **mTOR specifically deserves a re-test with the kinase-domain window** (aa 1975–2549,
  similar to phase2b's mTOR window experiment). If the kinase-domain run rescues the AUROC,
  the mTOR finding here is a truncation artifact; if it doesn't, mTOR is the next BRAF —
  a top-10 target the head genuinely can't model.
- **The bimodality itself is the next investigation.** What property — chemotype
  homogeneity? measurement-source heterogeneity? annotation noise? sequence length /
  domain coverage? — predicts which side of the split a target lands in? Answering this
  is the difference between "use MAMMAL on every target and triage post-hoc" and "predict
  in advance whether MAMMAL is useful for a Quiver target before spending the fine-tune
  budget".

## Caveats (carried from the per-experiment writeups)

- Spearman uses TDC's cold-split test fold — pairs may have been in the PEER training
  split (different split scheme). All Spearman numbers are upper bounds.
- Matched decoys are MW-matched only (not logP / HBD-HBA / ring count / topological
  similarity). A DUD-E-style matched set would be a harder bar; matched AUROCs here are
  upper bounds for "matched-difficulty" tests.
- mTOR is the only ceiling target that's truncated; the truncation window excludes its
  kinase domain. This is a known confound, not a finding — flagged for follow-up.
- Binder count capped at 20 (curve) / 30 (ceiling) per target; uniform across the panel
  but not a full screen.
