# Phase 2b — MAMMAL on real Quiver targets (Nav1.8, TSC→mTOR)

**Date:** 2026-05-28
**Checkpoint:** `dti_bindingdb_pkd_peer` (PEER) for DTI; `moleculenet_bbbp` / `moleculenet_clintox_tox` for de-risking.
**Script:** `experiments/phase2b_quiver_targets.py`. **Raw:** `results/phase2b_quiver_targets_*.json` (and ad-hoc `results/quiver_probes_20260528_202303.json`).

## Bottom line
On the two Quiver targets the meeting named, **off-the-shelf DTI gives no usable single-target
binder-vs-decoy signal**, and **truncation is not the fixable cause**. The **BBBP de-risking head is
genuinely useful** on these compounds; the **ClinTox head over-predicts toxicity** off-the-shelf.

## 1–2. DTI: known binders vs decoys (PEER pKd, separation = mean_binder − mean_decoy)

| target | sequence fed to model | separation | read |
|---|---|---|---|
| **Nav1.8** (SCN10A, 1956 aa) | full (1–1250 seen) | **+0.00** | blockers indistinguishable from decoys; ibuprofen/atenolol score top |
| Nav1.8 | C-terminal window 1000–1956 | +0.11 | still noise |
| **mTOR** (MTOR, 2549 aa) | full (1–1250 seen) | **+0.10** | rapalogs edge out caffeine/metformin but ibuprofen tops the list |
| mTOR | FRB+kinase window 1975–2549 | **−0.05** | binding-domain window does NOT help |
| mTOR | kinase window 2100–2549 | **−0.08** | worse |

Known Nav1.8 blockers tested: suzetrigine, A-803467 (selective tool cpd), lidocaine, mexiletine,
ranolazine, carbamazepine, lacosamide. mTOR inhibitors: sirolimus, everolimus, temsirolimus,
dactolisib, sapanisertib, AZD8055.

**Truncation is real but not the root cause.** mTOR's FRB (rapamycin site, ~2025–2114) and kinase
(ATP site, ~2182–2516) domains are entirely past the 1250-aa cutoff, so by default the model never
sees them — but feeding *only* the binding domain made separation **worse, not better**. The model
simply lacks the resolution to rank binders above decoys for a single target — consistent with its
weak global metric (NRMSE ~0.9 ≈ 9% better than the mean). Caveat: a bare domain fragment is an
out-of-distribution input, so windowing isn't a perfect isolation — but it clearly does not rescue
discrimination.

**Consequence:** the meeting's **TSC use case (2b: do rapamycin/everolimus rank above decoys vs
mTOR?) FAILS off-the-shelf** and is not fixable by windowing. Off-the-shelf MAMMAL DTI cannot be
used to nominate/triage candidates against a specific Quiver target.

## 4. De-risking on CNS-relevant compounds

| compound | P(BBB+) | P(toxic) |
|---|---|---|
| suzetrigine, A-803467, lidocaine, mexiletine, ranolazine, carbamazepine, lacosamide | **1.0** (penetrant ✓) | 1.0 |
| sirolimus | **0.02** (non-penetrant ✓) | 0.10 |
| everolimus | **0.002** (non-penetrant ✓) | 1.0 |
| temsirolimus | **0.00** (non-penetrant ✓) | 0.15 |
| dactolisib, sapanisertib, AZD8055 | 1.0 | 1.0 |

- **BBBP works and is useful**: small lipophilic CNS drugs → penetrant; large macrolide rapalogs
  (sirolimus/everolimus/temsirolimus) → correctly non-penetrant (0.00–0.02). Sensible, actionable.
- **ClinTox-tox over-predicts**: approved/safe drugs (lidocaine, carbamazepine) score P(toxic)=1.0.
  Despite the strong held-out AUROC, absolute scores are not trustworthy off-the-shelf — needs
  threshold/calibration before use as a filter. (Reinforces the earlier "ClinTox AUROC may be
  leakage-inflated on a tiny positive fold" caveat.)

## Implication
MAMMAL's usable value for Quiver narrows to the **BBBP filter**. DTI cannot triage candidates for our
(large) targets even with the right region; ClinTox needs calibration. Hit-list de-risking should use
**BBBP (MAMMAL) + a calibrated tox model + Morgan-fingerprint expansion** — MAMMAL is one validated
filter in that stack, not the engine.
