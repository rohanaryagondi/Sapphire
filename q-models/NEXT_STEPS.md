# NEXT_STEPS — `models` branch

**Scope of this branch:** the 9-track model scorecard + Q3 model punchlist +
Quiver Nav1.8 fine-tune + MAMMAL Explorer integration. EMET work is on the
`emet` branch; Boltz-2 specifics are on the `boltz` branch. **Don't
duplicate their work.**

Read `CLAUDE.md` on this branch first; it briefs you on the lane. Read
[`docs/models_tracks_scorecard.md`](docs/models_tracks_scorecard.md) for
the canonical state across all 9 tracks.

---

## Q3 top-3 priorities

### 1. Quiver Nav1.8 fine-tune — biggest open question

The off-the-shelf eval is done. Nav1.8 is below chance for every public DTI
model except Boltz-2, and Boltz at 0.714 is still marginal (n=11, p=0.16).
Datafit work (`results/datafit_summary.md`) showed data volume is necessary
but not sufficient — Nav having zero training pairs in BindingDB_Kd means a
Quiver-data fine-tune is the only remaining lever.

**Plan:**
1. **Source Quiver SPR / binding data on Nav1.8.** Ask Mahdi or David —
   could be Quiver's own assays or licensed external data.
2. **Build the train/eval split:**
   - 80% train, 20% scaffold-held-out test (Murcko scaffolds).
   - Match decoys by MW (MW-matched is the harder, more honest decoy class
     from the ceiling work).
   - Pre-flight a chemodiversity check (Spearman(diversity, AUROC) = −0.83
     across the 6 ceiling targets — narrow binder sets predict higher AUROC,
     which we want to know up front).
3. **Fine-tune:**
   - Base: `base_458m` (`models/base_458m/`).
   - Approach: per-target binder classifier (mirror IBM's `wdr91_asms` /
     `pgk2_del_cdd` heads — generative binder classifier, P(active) via
     `<SENTINEL_ID_0>` + `model.generate`).
   - Or: SCALAR head with proper output process. Whichever scaffold
     converges on the BBBP pilot recipe.
   - Compute: g4dn.xlarge T4 (pilot already worked there at $0.80 — see
     `results/aws_finetune_pilot.md`).
4. **Eval:**
   - AUROC on the held-out scaffold split.
   - Enrichment factor (EF5, EF10).
   - Cross-paralog selectivity test (Nav1.7, Nav1.5 known binders + decoys).
   - Off-target sanity (UBE3A, TUBB) to confirm target-conditioned not
     drug-bias.
5. **Success criterion:** AUROC ≥ 0.80 or EF5 ≥ 5× on the held-out chunk.

Receipts that matter going in: `results/aws_finetune_pilot.md`,
`results/phase3_wdr91_finetune.md` (the generative binder classifier
pattern), `results/datafit_summary.md` (why this is the only lever).

### 2. Ship MolFormer-XL + ADMET-AI + hERG rule + PROTON evidence panel to Explorer

Pure integration, no research. Highest "users see better answers tomorrow" ROI.

**Plan:**
1. **MolFormer-XL as BBB head** — replaces MAMMAL BBBP as the default scorer
   (AUROC 0.889 vs 0.833). Keep MAMMAL BBBP as the "trust the no's"
   specificity backstop (TNR | P<0.3 = 1.000 vs MolFormer's 0.917). Surface
   both scores per drug with operational rule: trust MolFormer for yes's,
   MAMMAL for no's.
2. **ADMET-AI DILI** for toxicity gate — replaces ClinTox (which is worse
   than chance on external toxics). Use the saved `comparison_vs_mammal`
   threshold (TPR 0.83 / AUROC 0.73).
3. **hERG rule** — basic-N + logP + 2 aryl rings boolean filter as the
   cardiac liability flag. Code already exists from phase5 work.
4. **PROTON link-prediction evidence panel** — when a user asks about a
   target, surface the top-5 KG-connected drugs from PROTON's NeuroKG
   decoder, with explicit "hypothesis shortlist, NOT binder predictor"
   framing on the UI (because top-5 mixes real chemistry with KG hairball
   noise — Cenobamate at Nav1.8 is real, Efavirenz at Nav1.8 is noise).

Briefs: `docs/ui_handoff.md`, `docs/ui_spec.md`. Setup: `ui/SETUP_NEW_MACHINE.md`.
Verdicts source: `docs/models_tracks_scorecard.md`.

### 3. Q3 model punchlist (cheap, run in parallel)

From `docs/models_tracks_scorecard.md` track-by-track punchlists:

| Model | Track | What to test | Cost | Success |
|---|---|---|---|---|
| ~~ESM-C 600M~~ | 1 | ✅ **DONE 2026-06-12 — not an upgrade** (0.825 best-layer < ESM-2-650M 0.875; 0.625 default-readout trap). `results/compare_esmc_600m.md` | $0 local | — |
| ~~ESM-2 3B / 15B~~ | 1 | ✅ **DONE 2026-06-12 — scale doesn't help** (650M 0.875 ≥ 3B 0.850 ≈ 15B 0.850; panel saturated). `results/esm_scale_ladder_track1.md` | ~$0.55 AWS | — |
| ~~MAMMAL layer sweep~~ | 1 | ✅ **DONE 2026-06-12** — best block 8 = 0.850 (up from 0.750); ties ESM-2 3B/15B, ~ ESM-2-650M 0.875. Track-1 best-vs-best settled (4-way tie). `results/mammal_layer_sweep.json` | $0 local | — |
| **ProstT5** | 1 (family) | Same panel, esp. GPCRs. **Sweep its layers too** (last-layer is a trap). | $0 local (like ESM-C) | Match SaProt's GPCR perfection |
| **DrugBAN** | 2 (DTI) | Nav panel head-to-head with ConPLex | ~$0.30 g5.xlarge | Expect Nav-blind; baseline check |
| **PerceiverCPI** | 2 (DTI) | Same Nav panel | ~$0.30 g5.xlarge | Same |
| **Uni-Mol2** | 4 (BBBP) | If MolFormer-XL has edge cases in Explorer | ~$0.20 | TBD |
| **MolFormer-XL on ClinTox** | 5 (tox) | Does it also beat MAMMAL on ClinTox? | ~$0.20 | Better than ADMET-AI? |
| **Tahoe-x1** | 7 (bridge) | Can it ingest V1-T traces against compounds? | ~$3 g5.xlarge | Speculative — CNS transfer risk from cancer-line training |

**Track-1 lesson learned (2026-06-12):** the canonical 0.750 NN-recall numbers use the naive
last-layer mean-pool, which undersells every encoder by ~0.10–0.12. **Layer selection (early-mid
layer + mean-center) is the lever; model size is not** (ESM-2 650M ≈ 3B ≈ 15B). Any future Track-1
embedding test must sweep layers, and the 1,400-gene panel re-test is where scale could still matter.

**Full forward plan (all 9 tracks + the next 3-parallel-AWS wave): [`docs/track_test_plan_2026-06-12.md`](docs/track_test_plan_2026-06-12.md).**

**Don't test (Nature Methods 2025 receipts):** scFoundation, scGPT, Geneformer, CellPLM.
**Don't test (license traps):** ESM-3 (non-commercial), ESM-C 6B (non-commercial), TxGemma (research-only).
**Don't test (we already did):** ConPLex, MAMMAL, ESM-2 650M/3B/15B, ESM-C 600M, Boltz-2, PROTON, MolFormer-XL, PINNACLE, SaProt, ADMET-AI, Morgan FP.

---

## Open follow-ups from prior phases (lower priority)

### 1d-(c). BindingDB assay-type mix per target
TDC harmonises Kd; original BindingDB has Ki / IC50 / Kd separately. Check
whether the failing-target subset (BRAF, HRH1, mTOR) is mostly-non-Kd. Cheap
SQL query, not yet done. Could explain bimodality.

### 1d-(d). Validate chemotype-memorisation directly
Score known binders from a withheld scaffold class against the same target
(e.g. RORC, where AUROC 0.97 — prediction is that performance drops sharply
on out-of-scaffold). One-script test. Half-done in
`results/datafit_scaffold_shift.md` (RORC/Adrb2/CA2 held 0.74-0.93 on
held-out Murcko, refuting the memorisation hypothesis). Could expand to BRAF
and HRH1 next.

### PROTON hypothesis generation on a Quiver CRISPR-N hit
Needs Caitlin on the KG side. Use PROTON's link-prediction decoder to
hypothesize KG-connected drugs for one specific Quiver hit; have Caitlin
validate which connections are biologically plausible.

---

## Hard rules (AWS guardrails)

- **Hard budget cap: $15 per session.** Per-model evaluations are $0.20-$1.
- **Only touch user's 50GB EBS** (`vol-066389517f2740f19`) **and instances
  you launch.** Never `aws s3 ls` other buckets. Shared Quiver account.
- **Ask before deleting** any S3 bucket, instance, or volume.
- **Label `Rohan-<Model>-*`** for cost tracking.
- **Polling cadence: 60s** on running instances + cost watch.

---

## What this branch deliberately ignores

- **EMET / agentic research platforms** — `emet` branch.
- **Boltz-2 TSC2 + Nav paralog completion** — `boltz` branch.
- **The Sprint Friday EMET slide deck** — `emet` branch.

If Rohan asks about any of those on this branch, point at the relevant
sibling branch.

---

## Reporting

- Append findings to Notion project page `36ee87e515f181289939ee64294ab5e8`.
- Weekly check-in with Matt — 6/11 Phase 2 use cases. Track 1, 4, 5, 6
  updates all fit here.
- **If you change a track verdict, change `docs/models_tracks_scorecard.md`
  first.** That file is the single source of truth across the project.
