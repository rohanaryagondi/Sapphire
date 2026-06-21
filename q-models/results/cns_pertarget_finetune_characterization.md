# Per-target CNS binder fine-tunes — trained, deployed LIVE in the Explorer, 2026-06-15

The campaign's central lever, deployed. Trained one **per-target binder fine-tune** (Morgan-FP ECFP4 +
GradientBoosting) for every data-rich CNS target, validated by Murcko scaffold-split CV, saved as a
deployable joblib, and **wired LIVE into the Explorer's DTI track** (CPU, in-process, no AWS/GPU).
Local, **$0**. `experiments/cns_pertarget_finetune.py` → `models/cns_pertarget/*.joblib`.

## Why per-target FP+GBT (not the cross-channel ESM-2 model)
The campaign established: (a) cross-target transfer FAILS (ion-channel LOCO 0/4; variant LOGO 0.36), so each
target needs its OWN model; (b) within a target the protein embedding is constant, so the ligand fingerprint
does the discrimination (trunc_test); (c) the TSC2 PKM2/PPARD run already hit 0.99 scaffold-split with exactly
this FP+GBT recipe. So per-target FP+GBT is the **correct, sufficient, and deployable** form — and it runs on
CPU, so it serves live inside the Explorer (unlike the GPU models that need AWS).

## Results — 13 targets trained (4 re-pulling), family-mean scaffold-split CV AUROC 0.95–0.997
| Target | Family | ChEMBL actives | scaffold-split CV AUROC |
|---|---|---:|---:|
| PPARD | mtor_pathway | 1264 | **0.997** |
| SCN2A (Nav1.2) | nav | 294 | 0.996 |
| DRD2 | gpcr | 1199 | 0.995 |
| SCN9A (Nav1.7) | nav | 1912 | 0.995 |
| AKT1 | mtor_pathway | 2545 | 0.993 |
| LRRK2 | kinase | 2136 | 0.993 |
| MTOR | mtor_pathway | 614 | 0.991 |
| RPS6KB1 (S6K1) | mtor_pathway | 1592 | 0.991 |
| BACE1 | kinase | 1669 | 0.990 |
| **SCN10A (Nav1.8)** | nav | 501 | **0.987** |
| GRIN1 (NMDA-NR1) | nmda | 276 | 0.980 |
| GRIN2B (NMDA-NR2B) | nmda | 866 | 0.978 |
| CACNA1C (Cav1.2) | cav | 70 | 0.953 |
**Family means:** mtor_pathway 0.993 · nav 0.993 · gpcr 0.995 · kinase 0.992 · nmda 0.979 · cav 0.953.
vs **off-the-shelf zero-shot 0.50** on ion channels. (PKM2, SCN5A/Nav1.5, HTR2A, GSK3B re-pulling after
transient ChEMBL timeouts — disk-cached so they slot in without re-training the rest; the Explorer loads new
joblibs dynamically.)

## Deployed LIVE in the Explorer
The DTI track now returns a **real per-target binder probability** (not a stub): `EXPLORER_LOCAL_MODELS=1`,
served in-process from the joblibs. Verified: haloperidol→DRD2 P(binder)=1.0 (high confidence, in training);
each call carries a **Tanimoto-to-train applicability-domain confidence flag** (high ≥0.5 / medium ≥0.35 /
low <0.35) and the model's scaffold-split AUROC. `tracks.json` Track-2 best_model updated; the app reports
this track as live (not DEMO).

## Honest limit (the applicability-domain ceiling, same as everywhere)
In-domain these models are excellent (0.95–0.997 scaffold-split), but like all ligand-QSAR they **collapse on
novel chemotypes**. Concrete: **suzetrigine → Nav1.8 scores P=0.14 ("unlikely binder")** — it's a novel 2024
scaffold ABSENT from ChEMBL's SCN10A set (501 actives; suzetrigine not among them), max Tanimoto-to-train only
0.41. So the model under-recognizes it → flagged **medium confidence**, i.e. a weak prior to confirm
structurally with Boltz-2 (Track 3). This is the same OOD wall seen in the TSC2 deconvolution and the
de-risking far-OOD bands — which is exactly why every call is Tanimoto-gated and novel hits route to Boltz-2.

## Scope / data strategy
- Covers the **data-rich** CNS targets (FINE-TUNE NOW per `docs/cns_finetune_readiness.md`).
- **Excluded (data-poor → Quiver-data targets):** Nav1.1/SCN1A (Dravet, 21 actives), Nav1.6/SCN8A (0),
  Kv7.2/KCNQ2 (epilepsy, 20). No public fine-tune is possible; these need Quiver screening data — the moat.

## Scorecard impact
Track 2 (DTI): the per-target binder fine-tunes are now the **primary, LIVE** binder-triage model for
data-rich CNS targets (0.95–0.997 in-domain), Tanimoto-gated, with Boltz-2 as the structural/OOD confirm and
BALM/PLAPT zero-shot as the fallback for un-fine-tuned targets. This is the campaign's lever, deployed.

**Receipts:** `experiments/cns_pertarget_finetune.py`; `results/cns_pertarget_finetune_result.json`;
`models/cns_pertarget/*.joblib` (gitignored, local); Explorer wiring `ui/explorer/backend/local_models.py` +
`inference.py`; data cached in `data/cns_dti_cache/`. All local, $0 AWS.
