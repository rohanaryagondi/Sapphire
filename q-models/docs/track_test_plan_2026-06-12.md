# Models track test plan — what to test next (2026-06-12)

**Branch:** `models`. **Goal:** drive each of the 9 tracks toward a "perfect track" =
a confident winner with a Boltz-style architectural-limit table (where it works / where it
fails / why / best-fit Quiver use). Canonical status: `docs/models_tracks_scorecard.md`.

**Constraint this session:** up to **3 parallel AWS jobs**. Many tests are **free locally**
(CPU), like the ESM-C / ESM-2-650M / MAMMAL sweeps — those don't consume an AWS slot.

**Two methodology rules now baked in (from the 2026-06-12 ESM ladder):**
1. **Any embedding-based test must sweep layers + mean-center** — last-layer mean-pool
   undersells encoders ~0.10–0.12. Never trust a single-readout number.
2. **Every model gets the A/B/C/D treatment** (works / fails / architectural reason /
   best-fit + cost), not just a headline metric.

---

## Per-track status + next test

| Track | Winner now | Confidence | Next test (this plan) | Where |
|---|---|---|---|---|
| 1 Family clustering | ESM-2-650M 0.875 ≈ MAMMAL 0.850 (best-layer; 4-way tie) | High (panel saturated, MAMMAL ✅ swept) | **ProstT5** (last open model) → then full 1,400-gene panel | local |
| 2 DTI / binder triage | Boltz-2 (Nav 0.714, mTOR 1.0) | Med (Nav marginal) | **DrugBAN + PerceiverCPI** baselines on Nav/PKM/HSD | AWS #1 |
| 3 Structure binding | Boltz-2 | Med | *(boltz branch owns; nothing here)* | — |
| 4 BBBP | MolFormer-XL (0.889) | High | **Uni-Mol2** 3D cross-check + held-out 100-drug validation | AWS #3 + local |
| 5 Tox / DILI / hERG | ADMET-AI + hERG rule | Med | **MolFormer-XL on ClinTox** + **hERG rule on TDC hERG_Karim** | AWS #2 + local |
| 6 KG / hypothesis | PROTON | High (closed) | none (closed) | — |
| 7 Cross-modal bridge | nothing public works | High (falsified) | **Tahoe-x1** feasibility — *blocked on paired V1-T data (ask Mahdi)* | staged |
| 8 Generative | Morgan FP + Enamine | High (skip) | none | — |
| 9 Off-target / selectivity | Boltz-2 (folded into T2) | Med | *(boltz branch)* | — |

---

## The next parallel AWS wave (3 jobs, cheap small-GPU — capacity-safe)

Small models (DTI heads, MolFormer, Uni-Mol2) fit a single g5.xlarge/g6.xlarge, which has
**far more capacity** than the big-GPU types that were starved on 2026-06-12. Run all three
concurrently (separate instances, same userdata-+-S3-+-poll pattern as `aws/esm2_big_layer_sweep.py`).

**AWS Job 1 — Track 2 DTI baselines (DrugBAN + PerceiverCPI).** g5.xlarge, ~$0.40.
- Panel: the Boltz test-bed — Nav1.8 known-binder set, PKM2 dimer, HSD11B1, mTOR FRB
  (calibration anchors with known "good" values).
- Both are BindingDB-trained; **expect Nav-blindness** (like ConPLex 0.437). Success =
  *confirm* the off-the-shelf-DTI-fails-on-Nav story is general → strengthens the
  "Nav fine-tune is the only lever" conclusion. If either unexpectedly clears Nav AUROC
  ≥ 0.65, that's a real find.

**AWS Job 2 — Track 5 MolFormer-XL on ClinTox + phase5 tox panel.** g5.xlarge, ~$0.25.
- We only beat MAMMAL on BBBP. Does the same model also beat MAMMAL's broken ClinTox
  (TPR 0.08) and rival ADMET-AI's DILI (TPR 0.83)? Success = TPR ≥ 0.70 on the
  withdrawn-vs-safe panel → MolFormer becomes the unified chem head for Tracks 4+5.

**AWS Job 3 — Track 4 Uni-Mol2 BBBP cross-check.** g5.xlarge, ~$0.25.
- 3D-conformer-aware. Does it beat MolFormer-XL's 0.889 on the external BBBP panel, esp.
  on stereochemistry/3D edge cases? Success = AUROC ≥ 0.889 or a clean win on a
  MolFormer failure subset.

**Est. wave cost: ~$0.90** (3 × small GPU, <1 hr each). Hard caps unchanged ($15/session;
shutdown-on-terminate + watchdog + S3-poll per job).

## Local / free wave (run alongside, no AWS slot)

- **MAMMAL layer sweep (Track 1)** — *running this session.* Closes the fair best-vs-best.
- **ProstT5 (Track 1)** — Rostlab seq↔3Di T5; likely CPU-runnable like ESM-C ($0). Sweep
  its layers; target SaProt's perfect GPCR recall. (If too slow on CPU, fold into a 4th AWS job.)
- **hERG rule validation (Track 5)** — the basic-N + logP + 2-aryl-ring rule on TDC
  `hERG_Karim` (~13K compounds). Pure rdkit/CPU, $0. Target TPR ≥ 0.70 / TNR ≥ 0.70 to
  promote it from n=10 anecdote to a validated gate.
- **Held-out BBBP funnel validation (Track 4)** — MolFormer + MAMMAL combined funnel on a
  100+ drug set disjoint from BBB_Martins train. CPU, $0.

## Staged / blocked (need data or a sibling branch)

- **Track 7 Tahoe-x1** ($3 AWS) — the only external model that could touch the Sapphire
  V1-T-trace → compound bridge. **Blocked: need paired (trace, compound) data — ask Mahdi.**
  Don't burn the $3 until we know we can feed it real V1-T embeddings; CNS-transfer risk
  from cancer-line training is real. This is the moat-adjacent test; scope carefully.
- **Track 1 full 1,400-gene panel** — where scale *might* finally matter (the 40-gene panel
  is saturated). Needs the real CRISPR-N accession list (Caitlin/KG).
- **Q3 #1 Nav1.8 fine-tune** — the biggest lever overall, blocked on Quiver SPR data
  (ask Mahdi/David). Not a model-search item; the real move once data lands.
- **Boltz Track 2/3/9 completion** (TSC2 + DFP, Nav paralog finish) — **`boltz` branch.**

## Recommended order

1. **Now (local, $0):** MAMMAL sweep ✅ done (Track 1 best-vs-best settled) → ProstT5 → hERG validation → held-out BBBP.
2. **Next (parallel AWS wave, ~$0.90):** Jobs 1+2+3 concurrently.
3. **Then:** chase Mahdi for (a) Nav SPR data → fine-tune, (b) paired V1-T data → Tahoe-x1.
4. **Parallel, no research:** ship MolFormer + ADMET-AI + hERG + PROTON into the Explorer
   (Q3 #2, pure integration — highest user-facing ROI).
