# Quiver model-evaluation benchmark — master leaderboard

_Last updated: 2026-06-13. Single source of truth: `benchmarks/build_benchmarks.py` (run it to regenerate)._

**What this is:** the empirical "best model per Quiver capability track" scorecard, tested on
**our own substrate** (CRISPR-N gene panel, Boltz test-bed Nav/mTOR targets, external tox/BBBP
panels) — not paper benchmarks. *"State-of-the-art on shit is still shit."* The canonical
narrative + Q3 punchlist lives in `docs/models_tracks_scorecard.md`; this folder is the
per-track leaderboard archive.

## Best model per track

| # | Track | 🏆 Best | Status |
|---|---|---|---|
| 1 | [Protein family clustering](01_family_clustering/README.md) | ESM-2-650M (best-layer 0.875, MIT) ≈ MAMMAL 458M (0.850). Use layer-selected + centered embeddings. | CLOSED on the 40-gene panel (saturated ~0.85-0.875) |
| 2 | [DTI / binder triage on Quiver targets](02_dti_binder_triage/README.md) | Boltz-2 (Nav1.8 AUROC 0.714, mTOR 1.000). [boltz branch owns the structure lane.] | Off-the-shelf eval DONE |
| 3 | [Structure-based binding (co-folding)](03_structure_binding/README.md) | Boltz-2 (same as Track 2). | Folded into Track 2 |
| 4 | [BBBP de-risking](04_bbbp/README.md) | MolFormer-XL (AUROC 0.889). ChemBERTa-2 (0.873) is a close commercial second. | DONE |
| 5 | [Toxicity / DILI / hERG](05_toxicity/README.md) | ChemBERTa-2 (commercial: hERG bal-acc 0.726, DILI ext TPR 0.73) + ADMET-AI (DILI TPR 0.83). | DONE — gap filled by a commercial model |
| 6 | [KG / hypothesis generation](06_kg_hypothesis/README.md) | PROTON link prediction — but ONLY in the binder-ranking direction (median 4.3% rank percentile; 60/106 top-5%, 80/106 top-10%). | CLOSED — operating envelope characterized (results/proton_characterization.md) |
| 7 | [Cross-modal Sapphire bridge (V1-T trace → compound)](07_crossmodal_bridge/README.md) | Nothing public works — and nothing public CAN (no voltage-trace modality exists by architecture). | FALSIFIED off-the-shelf |
| 8 | [Generative chemistry](08_generative/README.md) | Morgan fingerprints + Enamine REAL nearest-neighbor (boring, works). | SKIP (not a Quiver bottleneck) |
| 9 | [Off-target / paralog selectivity](09_selectivity/README.md) | Boltz-2 (ranks suzetrigine Nav1.8 #1, narrow margins). | Folded into Track 2 |

## Cross-cutting lessons from the campaign
1. **Layer selection > model scale** (Track 1): last-layer mean-pool undersells encoders ~0.10; 650M ≈ 15B.
2. **Off-the-shelf DTI is Nav-blind** (Track 2): only structure (Boltz-2) or a Quiver-data fine-tune works.
3. **ClinTox is dead** (Track 5): the *task* doesn't transfer to real withdrawals — 4 models confirm. Use ChemBERTa-2 hERG/DILI + ADMET-AI.
4. **The cross-modal bridge is the moat** (Track 7): no public model has a trace modality — build on Quiver V1-T data.
5. **Verify the readout before the model**: this project flipped its own conclusions multiple times by fixing I/O (wrong layer, wrong checkpoint, wrong env), not the model.

## Licensing note
Commercial-OK winners: ESM-2-650M (MIT), MolFormer-XL (Apache), ChemBERTa-2 (MIT), ADMET-AI (MIT),
Boltz-2 (MIT), MAMMAL (Apache). **Research-only (not shippable):** ESM-3, ESM-C 6B, TxGemma, Chai-1.

## What's NOT here (other branches)
- Boltz-2 specifics + Nav-paralog/TSC2 completion → `boltz` branch.
- EMET / agentic-research-platform eval → `emet` branch.
- Cross-cutting campaign report → `RohanOnly` branch.
