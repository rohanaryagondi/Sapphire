# TSC2 target deconvolution — can sequence DTI recover PKM2/PPARD? (2026-06-14)

Ben (via Amy E.) delivered the **TSC2 Optopatch phenotype-rescue hits** (`aws/tsc2_deconv_panel.json`,
raw at `s3://…/quiver_data/`). Two hits (QS0069567, QS0113172) functionally matched **Dasa-58** (PKM2
activator) and **GSK 3787** (PPARD antagonist) in Quiver's DFP library, deconvolving to **PKM2** + **PPARD**.
Question for the models branch: **can an off-the-shelf sequence-based DTI model (BALM, PLAPT) recover this
deconvolution** — rank each hit's true target above the controls + the wrong target? **Setup:** g5.xlarge,
score all 9 compounds × {PKM2 P14618, PPARD Q03181}; both sequences fetched cleanly from UniProt. ~$0.4.

## Verdict: **No. Neither BALM nor PLAPT can deconvolve PKM2 vs PPARD — both are at chance, and the controls score as high as (or higher than) the real binders. Target deconvolution is a fine selectivity task these family-level-triage models cannot do. Quiver's own functional/DFP signature matching (which produced the deconvolution) and Boltz-2 co-folding are the routes — not commodity DTI.**

### Results
| Model | PKM2 AUROC | PPARD AUROC | deconv accuracy | failure mode |
|---|---|---|---|---|
| BALM (cosine) | **0.50** | 0.53 | 2/4 (chance) | **degenerate target bias** — argmax = PPARD for **all 9** compounds |
| PLAPT (affinity) | **0.40** | 0.67 | 2/4 (chance) | **compound bias** — control carbamazepine scores PPARD **8.45** (highest of all) |

- **BALM is degenerate here:** PPARD's cosine is systematically higher than PKM2's for *every* compound
  (controls included), so it "calls PPARD" for all 9 — the 2/4 it gets right (GSK 3787, QS0069567 — both
  genuinely PPARD) is a coin-bias artifact, not target discrimination. Dasa-58 (confirmed **PKM2**) is
  called PPARD. Controls (BIIB021 0.525, carbamazepine 0.460) outscore real binders (QS0113172 0.426).
- **PLAPT is driven by compound bias:** the control **carbamazepine** gets the highest PPARD score (8.45)
  of any compound, and two other controls (BIIB021, BMS 191011) top PKM2 — so binder-vs-control AUROC is
  0.40 (PKM2, below chance) / 0.67 (PPARD, weak). Dasa-58 (PKM2) is called PPARD.
- **n is small** (2–3 binders vs 5 controls per target), but the failure isn't noise: it's structural
  (a constant target bias in BALM; controls beating binders in both). More compounds wouldn't rescue a
  model that ranks a control #1.

## Why
Target deconvolution = *given a compound, which of two targets does it bind?* — a **fine selectivity /
discrimination** call. These models do **family-level binder-vs-decoy triage** (BALM 0.857 on Nav1.8 binders
vs random decoys), not "PKM2 vs PPARD for the same molecule." This is the same limit recorded for BALM on
**Nav paralog selectivity** (it biases to Nav1.5; see `models_tracks_scorecard.md` Track 2) — confirmed
again on a different target pair. PKM2/PPARD are also under-represented vs kinases in the BindingDB-family
training data, so per-target affinity is dominated by generic compound/target priors.

## The strategic read (the moat)
**Quiver already deconvolved these correctly — by functional signature matching against the DFP library**
(QS hits ↔ Dasa-58 / GSK 3787). That **functional** approach worked where off-the-shelf sequence DTI fails.
This is the recurring thesis: **Quiver's functional data (DFP, V1-T) is the moat; commodity DTI models don't
add deconvolution value.** The off-the-shelf complement worth trying is **structural** — **Boltz-2
co-folding PKM2 and PPARD with each compound** (the `boltz` branch's lane; the panel is in
`aws/tsc2_deconv_panel.json` + S3 for them). Co-folding models the actual pose per target, which is what a
PKM2-vs-PPARD call requires.

## Scorecard impact
**None to winners.** Track 2/9 note: **sequence DTI (BALM, PLAPT) fails target deconvolution / fine
selectivity** (PKM2-vs-PPARD at chance, controls outscore binders) — use for family-level triage only;
deconvolution needs functional data or co-folding (Boltz-2). Reinforces the BALM paralog-selectivity caveat.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/tsc2_deconv/tsc2_deconv_result.json`; eval
`aws/tsc2_deconv_eval.py`; panel `aws/tsc2_deconv_panel.json`; instances `i-0af44683b3bf76f65` (run1, venv
bug) + `i-0ae74e989f8ce4ba9` (run2) self-terminated; no strays.
