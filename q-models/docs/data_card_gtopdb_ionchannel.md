# Data card — GtoPdb CNS ion-channel ligand-affinity corpus

**Pulled 2026-06-15** · `experiments/pull_gtopdb_ionchannel.py` → `data/cns_ionchannel/` (gitignored; reproducible
from the puller + this card). Source: **Guide to PHARMACOLOGY (IUPHAR/BPS)** REST API, headless, no auth.
**License:** ODbL (database) + CC-BY-SA-4.0 (content) — commercial use OK.

## What it is
Curated, literature-backed small-molecule **affinities against ion channels** (the cleanest public
ion-channel binder data — high curation, modest volume by design), with ligand SMILES. This is the substrate
the campaign's ion-channel binder fine-tune has pointed at: off-the-shelf DTI is at chance (0.50) on CNS ion
channels, while a supervised scaffold-split probe hits 0.92 — so labelled ion-channel affinity data is the
missing ingredient (`results/trunc_test_characterization.md`, `results/cns_dti_characterization.md`).

## Contents
- **`gtopdb_ionchannel_affinities.csv`** — 837 rows, one per (target, ligand, affinity) interaction with a
  resolvable SMILES. Columns: family, target_type (VGIC/LGIC), target_id, target_name, target_species,
  ligand_id, ligand_name, **smiles**, affinity_type, **affinity_median**, original_affinity, original_type,
  action, interaction_type, primary_target, interaction_id.
- **`gtopdb_ionchannel_targets.csv`** — the 152 channel targets pulled (+ CNS family tag + per-target n).
- **`gtopdb_pull_summary.json`** — counts.

## Coverage (the numbers)
- **837 affinity datapoints · 480 unique compounds (with SMILES) · 152 targets with affinity.**
- Affinity types: pIC50 482 · pEC50 215 · pKd 84 · pKi 53 · pKB 1 · pA2 2 (median used when a range was given).
- Per CNS family (the fine-tune-relevant ones): **Nav 80 · Cav 43 · Kv (incl. KCNQ) 162 · NMDA/GRIN 15**;
  plus broad ligand-gated **other_lgic 148** (GABA-A, nicotinic, 5-HT3, P2X — all CNS-relevant) and
  **other_channel 389** (remaining VGIC/LGIC). Nav1.8 = targetId 585.

## How to use it
- **Ion-channel binder fine-tune:** combine with the ChEMBL/BindingDB ion-channel subsets (loaders in
  `docs/cns_data_sources.md`) for volume; GtoPdb gives the high-quality, low-noise core. Define a binding
  label by thresholding `affinity_median` (e.g. pX ≥ 6 = active) or regress on it; scaffold-split (Murcko)
  for eval, vs an FP+GBT baseline — the protocol that already de-risked the fine-tune at 0.92.
- **Caveats:** GtoPdb is high-curation/low-volume — 80 Nav / 43 Cav / 15 NMDA datapoints are not enough to
  train a per-channel model alone; treat as the clean anchor set to merge with ChEMBL/Papyrus, or as a
  held-out high-confidence test set. Affinity types are mixed (IC50/EC50/Kd/Ki) — keep type as a feature or
  split by type. `action` distinguishes blockers/antagonists vs activators (useful for directionality).

**Provenance:** puller `experiments/pull_gtopdb_ionchannel.py`; API base
`https://www.guidetopharmacology.org/services/`; see `docs/cns_data_sources.md` for the full source index.
