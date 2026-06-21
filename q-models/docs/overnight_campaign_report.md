# Overnight campaign report — Boltz-level characterization of the per-track winners (2026-06-14)

Autonomous overnight shift (ScheduleWakeup self-chain). Goal: give each per-track **winner** the
operating-envelope depth Boltz-2 got — *where it works, where it fails, and why*. Plan:
[`overnight_campaign_2026-06-14.md`](overnight_campaign_2026-06-14.md). Budget $20; **spent ≈ $2.9**.

## Executive summary — what we now know cold
1. **BALM (compound↔target shared cosine)** — real but **target-dependent and selectivity-blind**.
   It's a cheap *family-level* binder-vs-decoy triage on data-rich/kinase-like targets; it is **not**
   a selectivity tool and **not** uniform across families. Don't promote it past "fast first-pass triage."
2. **De-risking layer (MolFormer-XL / ChemBERTa-2 / ADMET-AI)** — the reliability lever is the
   **applicability domain**, not the model: all collapse on novel scaffolds. And a **plain
   Morgan-FP+XGBoost beats the LMs on hERG**. Ship a Tanimoto-to-train confidence flag; switch the
   hERG gate to the fingerprint model.
3. **Structure-based DTI (DrugCLIP, GatorAffinity)** — both are **gated on pocket/pose quality Quiver
   lacks**. Neither adds a usable lever on our no-holo-crystal targets. **Boltz-2 remains the only
   structure-grounded affinity tool that works here.**

## Phase 1 — BALM deep dive  (`results/balm_characterization.md`)
- **Reproduces** the small-panel win (Nav1.8 0.857, mTOR 1.000) but the bigger picture is harsher:
- **Paralog selectivity FAILS** — only 2/7 Nav1.8 binders rank Nav1.8 over its paralogs; biased to
  **Nav1.5 (the cardiac off-target)**, even for suzetrigine. → use **Boltz-2** for selectivity.
- **Multi-family ChEMBL (n=40+40): GPCRs below chance** (DRD2 0.43, ADRB2 0.42); kinases mixed
  (BRAF 0.96, EGFR 0.62, mTOR 0.64). The 11/7-compound win was favorable-target selection.
- **Truncation-invariant** (pore-window AUROC = N-term AUROC) → the protein embedding is a coarse
  global pool, **not pocket-aware** — the mechanism behind the selectivity failure.
- **Rule:** BALM cosine = family-level triage on data-rich/kinase targets → Boltz-2 to confirm/select.

## Phase 2 — De-risking layer  (`results/derisking_characterization.md`)
- **Applicability domain dominates reliability.** On TDC scaffold splits, every model is good
  near-train and collapses on novel chemotypes — **hERG far-OOD (Tanimoto<0.3): 0.56–0.61 ≈ chance**
  vs ~0.85 near; BBB OOD 0.65–0.75 vs ~0.90. → **emit a Tanimoto-to-train confidence flag per call.**
- **Dedicated fingerprint model wins hERG:** Morgan-FP+XGBoost **0.890** vs ChemBERTa-LM **0.815**
  (+0.075). Adopt the FP model for the cardiac gate.
- **MolFormer-XL** is the more OOD-robust BBB model (confirms Track-4 winner). **ADMET-AI's TDC numbers
  (0.96–0.99) are leakage-inflated** (it's trained on TDC); honest external DILI ≈ 0.83.
- Scaffold-vs-random gaps are otherwise small (−0.03…+0.08) — scaffold novelty alone isn't the killer; AD is.

## Phase 3 — Structure-based generalization (GatorAffinity)  (`results/dti_generalization.md`)
- Full toolchain installed + checkpoints loaded + pockets + poses built (3 cheap cached-ckpt runs),
  but **`process_pdbs` featurized 0 pairs** — it needs a real docked **complex** (LIG residue in the
  pocket); our docking-free centroid-translated conformer isn't valid input. **Not landable in scope.**
- Mirrors DrugCLIP (below-chance on an apo-AlphaFold pocket). **Both structure-based models are
  pose/pocket-quality-gated** on Quiver's data-poor targets. BALM/Boltz-2 stay the Track-2 answers.
- (Stopped at the relaunch cap; checkpoints S3-cached + toolchain solved for a future real-pose retry.)

## Phase 4 — skipped (deliberate)
ESM-2-650M (Track 1) is already the *most*-characterized winner (layer sweeps + scale ladder +
167-gene panel — saturation & function-vs-fold ceiling settled). A re-run would be marginal, so we
banked the budget rather than spend on low-information confirmation.

## The through-line for Quiver
For **data-poor / no-holo-crystal targets** (Nav1.8 et al.), the model landscape splits cleanly:
- **Sequence models run but are coarse** — BALM gives family-level triage; useful, not selective.
- **Structure models would be sharper but can't run** — DrugCLIP/GatorAffinity need crystal-quality
  pockets/poses we don't have.
- **Boltz-2 is the bridge** — it *generates* the structure (co-folding) so it doesn't depend on a
  pre-existing pocket, which is exactly why it's the one structure-grounded tool that works here.
Operational stack: **sequence-model triage (BALM) → Boltz-2 co-fold for affinity/selectivity**;
de-risk with **MolFormer (BBB) + Morgan-FP/XGBoost (hERG) + ADMET-AI (DILI), each gated by a
Tanimoto-to-train confidence flag**.

## Accounting
- **AWS spend this session ≈ $2.9 / $20** (BALM-char ~$0.5, de-risking ~$0.4, GatorAffinity ×3
  ~$0.8 [cached ckpts kept retries cheap], plus ~$1.2 earlier today on BALM-crossmodal + DrugCLIP).
- **Teardown: every instance self-terminated; verified no stray `Owner=RohanAryaGondi` instances.**
  No EBS attached/grown; no model weights on this laptop; only our own S3 prefix touched.
- **Artifacts:** `results/balm_characterization.md`, `results/derisking_characterization.md`,
  `results/dti_generalization.md`; scorecard Tracks 2/4/5 updated; all pushed to `models`.
