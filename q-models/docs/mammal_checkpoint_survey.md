# MAMMAL checkpoint landscape (survey 2026-05-28)

Survey of every available MAMMAL (`ma-ted-458m`) checkpoint and its Quiver relevance.
458M is still the only model size; MAMMAL is published in npj Drug Discovery
(https://www.nature.com/articles/s44386-026-00047-4, arXiv 2410.22367). No v2, no follow-up.

## Published checkpoints (all have downloadable `model.safetensors`)

| Model id | Task | I/O | Quiver relevance |
|---|---|---|---|
| `ibm-research/…ma-ted-458m` (base) | foundation / embeddings | protein·SMILES·scRNA·gene → emb + generation | Med-High — gene/drug embeddings for KG & clustering |
| `…dti_bindingdb_pkd` | drug-target binding (general) | protein + SMILES → pKd | High (but off-the-shelf single-target triage fails — see phase1) |
| `…dti_bindingdb_pkd_peer` | DTI, PEER split | protein + SMILES → pKd | High — the correct DTI checkpoint for our target classes |
| `…moleculenet_bbbp` | BBB penetrance | SMILES → class | **High — validated, deployable de-risking** |
| `…moleculenet_clintox_tox` | clinical toxicity | SMILES → class | High task, but over-predicts off-the-shelf (needs calibration) |
| `…moleculenet_clintox_fda` | FDA-approval | SMILES → class | Medium |
| `…protein_solubility` | solubility | AA seq → class | Low-Med (biologics/expression) |
| `…tcr_epitope_bind` | TCR-epitope binding | AA seqs → class | Low (immuno-oncology) |
| `michalozeryflato/…ma-ted-458m.pgk2_del_cdd` | target-specific binder **classifier**, PGK2 (DEL) | SMILES + `<PGK2_DEL>`/`<PGK2_ASMS>` task token → P(active) (generative) | ✅ functional generative classifier (same profile as wdr91; full eval not run) |
| `michalozeryflato/…ma-ted-458m.wdr91_asms` | target-specific binder **classifier**, WDR91 (ASMS) | SMILES + `<WDR91_ASMS>` task token → P(active) (generative) | ✅ **works (modestly)** — WDR91 actives vs decoys top-5% enrichment 5.25× (AUROC 0.63), Phase 3 |
| `introvoyz041/…` mirrors | copies of base + solubility | — | Low — third-party re-uploads, use originals |

`ibm/…` is a mirror of the `ibm-research/…` namespace.

## The key lead: pgk2_del_cdd / wdr91_asms (target-specific binder heads) — **FUNCTIONAL (generative classifiers)**
Uploaded 2026-03 by Michal Ozery-Flato (a named MAMMAL co-author). MAMMAL **fine-tuned on a single
target's experimental hit data** (DEL = DNA-encoded library; ASMS = affinity-selection mass-spec) to
classify candidate molecules as binders for that one target — the workflow Quiver needs.

**Phase 3 validation: they WORK (modestly), once you use the right I/O.** These are **generative binary
classifiers**, not scalar regressors (despite the DTI-like config). The tokenizer carries dedicated task
tokens new vs base — `<WDR91_ASMS>`, `<PGK2_ASMS>`, `<PGK2_DEL>` (+ `<ACTIVE>`/`<ISACTIVE>`), and the
trained signal lives in the encoder + generative decoder (the `scalars_prediction_head` is untrained/
vestigial, exactly as in the MoleculeNet classifiers). **Readout:** molnet-style prompt with the task
token, `model.generate`, read P(`<1>`) at classification position 1 — validated on BBBP (reproduces
0.996). `wdr91_asms` ranks WDR91 actives (Ahmad 2023, ChEMBL `CHEMBL5465256`, doi
10.1021/acs.jmedchem.3c01471 / PMID 37996079) above drug-like decoys: **top-5% enrichment 5.25×, AUROC
0.63** (modest; strong inactive prior; no affinity ranking). → `../results/phase3_wdr91_finetune.md`.

*Gotcha:* reading the (untrained) scalar head instead gives AUROC 0.43 and looks "broken" — that's the
wrong readout. **Takeaway:** these ARE a usable existence proof — per-target fine-tuning gives real
target→binder triage signal (Q14 leans YES). The older 84M `biomed.sm.mv-te-84m` has the same two
targets but ships `.ckpt`-only (not standard-loadable).

## Train-code-only (NO checkpoint — can't test off-the-shelf)
`carcinogenicity`, `cell_line_drug_response`, `scrna_cell_type` (GitHub `mammal/examples/`) have
training code but no published weights. The 7 published task heads above are the only off-the-shelf set.
