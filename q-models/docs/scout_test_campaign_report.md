# Scout-candidate AWS test campaign — master report (2026-06-14)

Empirically tested the highest-ROI untested models from `docs/model_scout_2026-06-14.md` at Boltz-level
detail (where each works/fails + why), to see whether any beats a current scorecard winner **on our
substrate**. Plan: `docs/scout_test_campaign_2026-06-14.md`. Budget $20; **spent ~$4–5** across ~10
g5.xlarge runs (incl. toolchain-fix relaunches). All instances self-terminated; no strays; nothing
touched outside `Owner=RohanAryaGondi` + our S3 prefix.

## Bottom line
**2 of 4 candidates changed the scorecard; 2 did not.**

| Phase | Model | Track | Verdict | Scorecard |
|---|---|---|---|---|
| 1 | **MapLight** (CatBoost on ECFP+Avalon+ErG+RDKit) | 4 BBBP | ✅ **DISPLACER** | **BBBP primary → MapLight** |
| 1 | CheMeleon (CC0 D-MPNN FM) | 4 BBBP | ❌ not a displacer | — |
| 2 | **ULTRA** (zero-shot KG FM, MIT) | 6 KG | ✅ **CO-WINNER** | **Track 6 → PROTON + ULTRA** |
| 3 | CardioGenAI (tri-channel cardiac, MIT) | 5 tox | ❌ not adoptable | no winner change |
| 4 | AdaMBind (MAML few-shot DTI) | 2/3 DTI | ❌ not adoptable | no winner change |

## Per-phase findings

### Phase 1 — MapLight beats MolFormer-XL on BBBP (`results/chemeleon_maplight_characterization.md`)
- **MapLight BBBP scaffold-AUROC 0.905 > MolFormer-XL 0.889**, best calibration (Brier 0.106), near-zero
  scaffold gap, **far-OOD 0.862** (vs MolFormer ~0.75). On hERG it ties our FP+XGBoost (0.889) with the
  **best far-OOD we've measured (0.809)** — degrades least on novel chemotypes, the failure mode that sinks
  the de-risking layer. Open/commercial-OK, CPU-only (~$0).
- **CheMeleon (CC0 graph FM) is not a displacer** — below MolFormer on BBB (0.868), below FP models on hERG.
- **Action:** adopt MapLight as BBBP primary; confirm on the Quiver external-30 before retiring MolFormer.

### Phase 2 — ULTRA is a Track-6 co-winner (`results/ultra_kg_characterization.md`)
- **Matches PROTON's known-binder ranking ZERO-SHOT** (median 3.2% vs 4.3%), **nails Quiver ion channels**
  (Nav1.8 median rank 3 / 0.7%, Nav1.5/1.7/Cav1.2 all top-8).
- **Fixes both of PROTON's documented failures:** no hub bias (top-10 Jaccard 0.087 — no Bepridil effect),
  and **real inductive novel-target capability** (edges held out → median rank 0.71%; the `binder_not_in_kg`
  case PROTON has zero capability on).
- **Weak on kinases** (BRAF 60%, EGFR 19%) — same hard regime as our data-fit finding.
- **Action:** co-deploy ULTRA as the default for novel-target / hub-sensitive / ion-channel queries; keep
  PROTON for NeuroKG-specific signal. Follow-up: run ULTRA on Quiver's NeuroKG export for a same-substrate
  head-to-head.

### Phase 3 — CardioGenAI not adoptable (`results/cardiogenai_characterization.md`)
- Its unique **NaV1.5 head directionally catches late-Na blockers** (mexiletine, ranolazine) — a cardiac
  off-target signal our single hERG gate lacks — **but** the heads emit **saturated 0/1** calls with
  **textbook errors** (misses lidocaine on NaV1.5; suzetrigine hERG false-+, ranolazine hERG false-−), and
  its **closed SMILES char-vocab** crashes on out-of-vocab chemotypes (`KeyError '[SH]'`) so it **can't be
  benchmarked on TDC hERG** without retraining its tokenizer.
- **Action:** keep FP-XGBoost/MapLight for hERG. File the multi-channel *idea* (build NaV1.5/CaV1.2 on our
  own FP+GBT recipe if a cardiac-panel need arises); don't ship CardioGenAI's heads.

### Phase 4 — AdaMBind not adoptable (`results/adambind_characterization.md`)
- **No LICENSE file** (research-only) → not adoptable regardless. Un-adapted **zero-shot is chance** on our
  panels (Nav1.8 0.43, mTOR 0.50). The **few-shot k=5 claim could not be tested** — meta-training and
  adaptation both crash with `UnboundLocalError: 'y'` inside the repo's own `Trainer.py` MAML loop.
- **Action:** Track 2/3 stays Boltz-2 + BALM-triage. The Nav fine-tune plan (scaffold-split on Quiver data)
  is unaffected; BALM (Apache-2.0, Nav1.8 0.857) is the better-licensed few-shot reference if needed.

## Net scorecard deltas
- **Track 4 (BBBP):** primary → **MapLight** (keep MolFormer as specificity backstop until Quiver-30 confirm).
- **Track 5 (hERG):** MapLight noted as most OOD-robust; CardioGenAI rejected.
- **Track 6 (KG):** **PROTON + ULTRA co-winners**; ULTRA the default for novel-target/hub/ion-channel queries.
- **Tracks 2/3:** unchanged (Boltz-2 + BALM).

## Deferred (unchanged from plan, with reason)
- **Protenix-v2** (Track 9 co-folding) — `boltz` branch's lane (A100 + cuequivariance); coordinate there.
- **CLOOME / PhenoScreen** (Track 7 moat) — need Mahdi's paired (V1-T trace, compound) data; off-the-shelf
  they ingest Cell-Painting images, not our traces.
- **MissION** (ion-channel GoF/LoF variant effect) — Quiver-native and worth doing, but a different task
  (variant effect, not binding) + needs the variant dataset. Queue next.

## Follow-up confirmations (2026-06-14, same session)
Both follow-ups from the original report's "open follow-ups" ran (3-parallel, event-driven Monitor + cron):

- **ULTRA on NeuroKG — same-substrate head-to-head** (`results/ultra_neurokg_characterization.md`). Rohan
  supplied the NeuroKG dataverse export (= PrimeKG + Quiver neuro augmentation, 147,020 nodes; PROTON's
  actual training graph), now in S3 `neurokg_src/`. ULTRA zero-shot on PROTON's own graph **fixes both of
  PROTON's documented failures**: (B) **no hub bias** — top-10 Jaccard 0.065, and top drugs are correct
  pharmacology (PI3K/mTOR inhibitors for MTOR, EGFR/RAF inhibitors for EGFR/BRAF, Na-blockers for the Nav
  paralogs), vs PROTON's Bepridil-for-9; (C) **inductive novel-target** median rank 0.34% with all binder
  edges held out (Phenytoin→Nav top-0.3%, Sirolimus→MTOR top-2.5%), a capability PROTON lacks entirely.
  **Caveat / correction:** section A (known-binder retrieval) is strong (target ranked top ~0.03%) but is a
  different protocol/denominator than PROTON's 4.3%, so it is NOT a clean ranking win — and the earlier
  Hetionet writeup mis-scaled its A percentages 100× (e.g. "3.2%" → 0.032%); corrected in both files. The
  co-winner verdict stands on B + C, which are protocol-fair. Track 6 = **PROTON + ULTRA**, confirmed.

- **MapLight held-out BBB on B3DB** (`results/maplight_b3db_characterization.md`). Trained on TDC
  BBB_Martins, tested on B3DB (7,807 cpds, CC0; exact-SMILES leakage removed → 6,142): **MapLight AUROC
  0.919 vs MolFormer-XL 0.854**, Brier 0.126 vs 0.157, **far-OOD 0.674 vs 0.590** — wins on every axis on
  an independent dataset. Confirms **MapLight as the BBBP primary; MolFormer demoted to backstop** (the
  external-30 in the original report was a tox panel, not BBB — B3DB is the correct held-out test).

## CNS/Quiver-focused batch (2026-06-14, same session) — 3 model tests + an organizational fix
Driven by "test on Quiver neuro/CNS stuff (Nav1.8, TSC2), Ben's compounds, things found online." First a
**data-status finding:** Ben's **DFP089 compound was never delivered as SMILES** (blocker since 2026-06-11;
only artifact `dfp089_v1_bundle/` on the EBS volume is flagged collaborator-don't-touch), and **TSC2 has no
binder panel** — both are the `boltz` branch's lane. So this batch focused on the Quiver data we have
(Nav1.8/mTOR/NeuroKG) + online sources. Consolidated the scattered panels into **`docs/quiver_data_index.md`**.

- **DTI-Nav** (`results/dti_nav_characterization.md`): **PLAPT** (ProtBERT+ChemBERTa, ONNX, seq-only) is NOT
  Nav-blind — Nav1.8 **0.75** (beats Boltz-2 0.714 + ConPLex 0.437; below BALM 0.857), mTOR 1.000. Added as a
  fast first-pass triage; BALM stays the Nav winner. (Tiny n=11 panel → within noise; DeepPurpose failed on
  a descriptastorus dep, not re-run.)
- **MissION / variant-effect** (`results/mission_characterization.md`, NEW Track-10 capability): **funNCion**
  (Apache-2.0, AUROC 0.897) is the adoptable ion-channel GoF/LoF model; **MissION** (0.925) is portal-only =
  not adoptable; generic ESM-2 LLR is insufficient (0.665, direction not captured). **Nav1.8 absent from all
  public sets → Quiver V1-T fine-tune is the moat.**
- **AEV-PLIG** (`results/aev_plig_characterization.md`): **pose-gated, n_scored 0/18** — third structure
  scorer (after DrugCLIP, GatorAffinity) confirmed unusable on no-holo Quiver targets. Sequence-based
  (BALM/PLAPT) + co-fold (Boltz-2) remain the route.

## TSC2 target deconvolution (2026-06-14) — Ben's data, unblocked
Ben delivered the TSC2-Optopatch hits (`aws/tsc2_deconv_panel.json`; raw in S3 `quiver_data/`), deconvolving
to **PKM2 + PPARD** (Dasa-58 / GSK 3787 confirmed refs + 5 controls). **Sequence-DTI cannot recover the
deconvolution** (`results/tsc2_deconv_characterization.md`): BALM PKM2/PPARD AUROC 0.50/0.53, PLAPT 0.40/0.67,
both 2/4 deconvolution accuracy (chance); BALM is degenerate (always argmax PPARD), PLAPT compound-biased
(a control scores highest). **Target deconvolution is fine selectivity, not family triage** — the routes are
Quiver's functional/DFP signatures (which already made the call) or **Boltz-2 co-fold** (boltz lane; panel
shared). The DFP089 compound *itself* remains unprovided/separate; this batch covered the deconvolved targets.

## Process note
Ran up to **3 parallel** jobs under an **event-driven Monitor** (pinged on each DONE marker, success or
fail) + a **cron backup heartbeat** — replaced the earlier passive ScheduleWakeup polling. Recurring
toolchain gotchas this campaign: chemprop 2.x needs py3.11 (Phase 1); ULTRA needed a PyG-vocab rebuild,
a CPU relation-graph build, and system `ninja-build` for its rspmm CUDA kernel (Phase 2); openbabel-wheel
for CardioGenAI (Phase 3). The ≤2-fix-then-bank discipline held except for ULTRA, where the user
explicitly re-authorized further attempts (and it paid off).
