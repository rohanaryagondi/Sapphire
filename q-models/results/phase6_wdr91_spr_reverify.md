# Phase 6 — WDR91 SPR real-data re-verification

**Date:** 2026-06-01. **Goal:** confirm the load-bearing WDR91 per-target claim
(AUROC 0.816 / top-5% enrichment 4.57×) reproduces. The audit (`docs/audit_findings.md`
#17) flagged this number as the strongest single piece of evidence that per-target
fine-tuning works, *and* as OVERSTATED ("canonical / genuinely separates binders") — so it
needs to be solid. Re-ran the exact original script `experiments/phase5_wdr91_spr.py`
(one model load, generative `binder_prob` readout, Ahmad 2023 SPR data).

## Reproduces — exactly

| metric | original (`phase5_wdr91_spr_20260529_113233.json`) | re-run (`phase5_wdr91_spr_20260601_134206.json`) | match |
|---|---|---|---|
| Binary AUROC | 0.8159203980099502 | 0.8159203980099502 | ✅ bit-identical |
| Top-5% EF | 4.574162679425838 | 4.574162679425838 | ✅ bit-identical |
| Top-10% EF | 4.3752860411899315 | 4.3752860411899315 | ✅ bit-identical |
| Avg precision | 0.5171407630818772 | 0.5171407630818772 | ✅ bit-identical |
| Mean score, binders | 0.015334917873631925 | 0.015334917873631925 | ✅ bit-identical |
| Mean score, non-binders | 0.0026593031686032434 | 0.0026593031686032434 | ✅ bit-identical |
| n binders / non-binders / total | 38 / 201 / 239 | 38 / 201 / 239 | ✅ |

The readout is deterministic (greedy `model.generate`, no sampling), so full float-precision
identity is expected and confirms the pipeline + data are stable. **REPRODUCE: YES.**

## The audit's distribution critique also reproduces (and is correct)

AUROC 0.816 is a real **ranking** statistic, but it does **not** mean the head "fires" on
binders. The re-run's top-10 list and per-class means confirm the degenerate near-zero mass:

- Binder **mean score 0.0153**, non-binder mean 0.0027 — both ~0; the head assigns near-zero
  binder-probability to almost everything.
- The **top-scoring compound is a true binder (0.36)**, but the **2nd-highest is a non-binder
  (0.319)** that outranks all but one true binder, and the **3rd is also a non-binder (0.175)**.
- Only a handful of binders score >0.1. The 0.816 reflects faint rank structure in a near-zero
  score field, not a usable per-compound binder probability.

So the corrected reading (already in the report card, under-weighted in the top-level synthesis
docs): **WDR91 = weak top-of-list enrichment only; useless as a calibrated per-compound score.**
"Canonical performance / genuinely separates binders" oversells it. Treat 0.816/4.57× as a
ranking-only, modest-enrichment result — real, reproducible, but not a binder oracle.

## Files
- Script (unchanged): `experiments/phase5_wdr91_spr.py`
- Re-run raw: `results/phase5_wdr91_spr_20260601_134206.json`
- Original raw: `results/phase5_wdr91_spr_20260529_113233.json`
- Data: `data/wdr91/ahmad2023_si_002.csv` (240 SPR compounds → 38 binders / 201 non-binders after
  neutral-parent standardization + dedup)
