# Models Campaign Report — off-the-shelf model evaluation across the 9 Quiver tracks

**To:** RohanOnly (cross-cutting campaign state) · **From:** Models branch · **Date:** 2026-06-13
**Scope:** what the `models` branch tested, the best model per capability track, and the
strategic pivot. Per-track leaderboard archive lives at `benchmarks/` on the `models` branch;
canonical narrative at `docs/models_tracks_scorecard.md`.

---

## 0. One-paragraph verdict
The off-the-shelf model search is **effectively complete across all 9 tracks** — ~16 models
evaluated on Quiver's *own* substrate (the 40-gene CRISPR-N panel, the Boltz Nav/mTOR test-bed,
external tox/BBBP panels). The headline shifts: there is **no off-the-shelf model left to test
that would change a track verdict**, and the remaining high-value levers are **not** model
downloads — they are Quiver-data fine-tunes (Nav1.8, the V1-T bridge), shipping the verified
models into the Explorer, and re-running Track 1 at the 1,400-gene scale. The de-risking gap
(Track 5) got *filled this campaign* by a commercial-OK model (ChemBERTa-2). MAMMAL holds its
own as commodity enrichment; the moat stays V1-T + CRISPR-N.

## 1. Best model per track (empirical, on our substrate)

| # | Track | 🏆 Best (commercial-OK unless noted) | Key number | Status |
|---|---|---|---|---|
| 1 | Protein family clustering | **ESM-2-650M** (MIT) ≈ MAMMAL 458M | best-layer NN-recall **0.875 / 0.850** | closed on 40-gene panel (saturated) |
| 2 | DTI / binder triage | **Boltz-2** (MIT) | Nav1.8 **0.714**, mTOR **1.000** | off-the-shelf done; fine-tune is the lever |
| 3 | Structure binding | **Boltz-2** | (folded into T2) | boltz branch |
| 4 | BBBP de-risking | **MolFormer-XL** (Apache) | AUROC **0.889** | done |
| 5 | Toxicity / DILI / hERG | **ChemBERTa-2** (MIT) + ADMET-AI | hERG bal-acc **0.726**, DILI ext **0.73-0.83** | **gap filled this campaign** |
| 6 | KG / hypothesis | **PROTON** | median **4.3%** binder rank | closed |
| 7 | Cross-modal bridge | **nothing public works (build, don't buy)** | cross-modal cosine 0.08 | the moat |
| 8 | Generative chemistry | Morgan FP + Enamine REAL | 0.96 vs 0.72 | skip |
| 9 | Off-target / selectivity | **Boltz-2** | suzetrigine Nav1.8 #1 | boltz branch |

## 2. Cross-cutting findings (the campaign's real lessons)

1. **Layer selection beats model scale (Track 1).** The canonical 0.750 numbers used naive
   last-layer mean-pool, which undersells encoders by ~0.10. With per-model layer selection:
   ESM-2-650M **0.875** ≈ MAMMAL **0.850** = ESM-2 **3B 0.850** = ESM-2 **15B 0.850** > ESM-C
   600M 0.825. **A 23× parameter increase moves nothing** — the 40-gene panel is saturated by
   design (2 singleton families + functional-not-fold e3/NR groups). Recommendation: whatever
   embedding backs Sapphire/KG, use an early-mid layer + mean-center, and don't pay for 3B/15B.
2. **Function-aware models are the only Track-1 frontier.** ESM-3 (research-only) is the *only*
   model to cluster nuclear receptors perfectly (1.0 vs ~0.83) — first evidence that
   function/annotation-aware models beat pure-sequence on function-defined families. Worth
   pursuing if the 1,400-gene panel has many such groups.
3. **Off-the-shelf DTI is Nav-blind in general (Track 2).** ConPLex (0.437), MAMMAL-DTI (0.43),
   and every BindingDB-trained model have zero Nav training pairs. Only Boltz-2 (structure)
   clears chance, and marginally. **The Quiver-data Nav fine-tune is the only remaining lever.**
4. **ClinTox is dead (Track 5).** External-panel AUROC is 0.24-0.47 across **four** models
   (MAMMAL/MolFormer/ChemBERTa/TxGemma) despite 0.80-0.96 in-distribution — the *task* doesn't
   transfer to real withdrawals. Drop it. A trained ChemBERTa-2 hERG classifier (bal-acc 0.726)
   beats the old logP rule (0.65); ChemBERTa-2 DILI + ADMET-AI cover hepatotox.
5. **3D doesn't help BBBP (Track 4).** Uni-Mol2 (3D-conformer) scored 0.785, below the 2D
   SMILES transformers (MolFormer 0.889, ChemBERTa 0.873).
6. **Verify the readout before the model.** This project repeatedly flipped its own conclusions
   by fixing I/O (wrong layer, wrong checkpoint, Forge-only API, gated weights), not the model.

## 3. Models evaluated this campaign (~16)

**Commercial-OK (shippable):** ESM-2 650M/3B/15B, MAMMAL 458M, MolFormer-XL, ChemBERTa-2,
Ankh-large, ProstT5, SaProt-650M, ADMET-AI, Boltz-2, PROTON, Morgan FP, Uni-Mol2.
**Research-only (NOT shippable without a commercial deal — tested per Rohan's research-use call):**
ESM-3-open, ESM-C 6B, TxGemma-9B. (Chai-1 skipped; DrugBAN/PerceiverCPI deferred — no inference
weights, would require training.)

## 4. Cost, infra, and safety
- **AWS spend this campaign ≈ $2** (under the $10/$15 caps). Self-contained-venv GPU pattern
  (`aws/generic_venv_userdata.sh`) after the DLAMI-conda race cost several relaunches; small
  models (≤~2B) run free locally. All instances terminated; **Rohan's EBS `vol-066389517f2740f19`
  never attached/touched**; no other accounts' resources touched.
- **SECURITY — action needed:** AWS keys, HF token, and Forge token were exposed broadly this
  session (system prompt, shell history, an S3 run.log since deleted, a committed log since
  removed). The userdata templates + trust_remote_code scripts are now hardened, but the robust
  fix is to **rotate the AWS access key, HF token, and Forge token.**
- **Repo state:** all work committed on `models` (worktree, unpushed). NOTE: the OneDrive-synced
  `.git` showed broken loose refs (`main`, `compare-dti-models`, `ui-*`) during this session —
  pre-existing branches, likely OneDrive sync corruption (not this campaign's work; `models`
  commits are intact). Worth a `git fsck` / re-clone when convenient.

## 5. The pivot — what's next (none of it is off-the-shelf)
1. **Quiver-data Nav1.8 fine-tune** (scaffold-held-out split) + **V1-T → compound contrastive
   bridge** — both blocked on data from **Mahdi**. Highest-value levers overall.
2. **Ship the verified de-risking layer into the Explorer:** MolFormer-XL (BBBP) + ChemBERTa-2
   (hERG/DILI) + ADMET-AI (DILI) + PROTON (KG evidence panel). Pure integration, no research.
3. **Track 1 at the 1,400-gene panel** (where function-aware models may finally separate) —
   needs the real accession list from **Caitlin**.

## 6. Where everything lives
- Per-track leaderboard archive: `benchmarks/` (regenerate via `benchmarks/build_benchmarks.py`).
- Canonical narrative + Q3 punchlist: `docs/models_tracks_scorecard.md`.
- Forward model-candidate slate: `docs/aws_model_candidates.md`.
- Per-model writeups + raw JSON: `results/*.md`, `results/*.json`.
- Eval scripts: `experiments/*.py` (local), `aws/*.py` (GPU).
- All on branch `models`; this report destined for `RohanOnly`.
