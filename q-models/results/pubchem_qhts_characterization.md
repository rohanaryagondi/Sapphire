# Rescuing data-poor CNS channels via PubChem qHTS — KCNQ2 + Cav3.2 fine-tuned, 2026-06-15

The fine-tune readiness map flagged several epilepsy channels as "data-poor → Quiver-data" because **ChEMBL**
alone had too few actives (Kv7.2/KCNQ2 20, Cav3 absent). But the scout found large **non-ChEMBL** PubChem
qHTS screens for some of them. This pulls those (headless PUG-REST) and trains deployable per-target models,
**rescuing two channels into the live Explorer.** `experiments/pubchem_qhts_finetune.py`, $0, local.

## Result
| Channel | Source | actives / inactives | scaffold-split CV AUROC | status |
|---|---|---|---|---|
| **KCNQ2 / Kv7.2** (epilepsy) | PubChem AID 2156 | 3,407 / 6,000 (sampled) | **0.811** | rescued → LIVE |
| **CACNA1H / Cav3.2** (T-type; epilepsy/pain) | PubChem AID 449739 | 4,230 / 6,000 (sampled) | **0.791** | rescued → LIVE (new target) |

Negatives = the assays' **own measured inactives** (real non-binders, sampled). Both now serve live in the
Explorer DTI track (added to the UniProt→gene map: O43526→KCNQ2, O95180→CACNA1H).

## Honest read
- **qHTS models are weaker than the ChEMBL-curated ones (0.79–0.81 vs 0.95–0.99)** — single-concentration HTS
  is noisier than ChEMBL dose-response pChEMBL. Still well above zero-shot 0.50, and deployable with the
  standard Tanimoto-to-train confidence gate. Treat as a usable triage prior, not a calibrated affinity.
- Same out-of-domain limit: e.g. retigabine→KCNQ2 scores low (0.10) and is flagged low-confidence (novel
  chemotype vs the qHTS hit set) — confirm with Boltz-2.
- **Still genuinely build-don't-buy (no public rescue): Nav1.1/SCN1A (Dravet) and Nav1.6/SCN8A** — no large
  non-ChEMBL Nav screen exists (PubChem Nav records are ChEMBL-mirrored; the only open Nav SAR is paywalled
  JMC/EJMC supplements). These remain Quiver-data targets — the moat.

## Net effect on the live Explorer
DTI track now serves **18 per-target fine-tunes** (16 ChEMBL-curated 0.95–0.997 + 2 PubChem-qHTS 0.79–0.81),
covering every CNS target that can be fine-tuned from public data. The only un-coverable CNS targets are the
two Nav epilepsy channels with no public screening data — exactly where Quiver's own data is required.

**Receipts:** `experiments/pubchem_qhts_finetune.py`; `results/pubchem_qhts_finetune_result.json`;
`models/cns_pertarget/{KCNQ2,CACNA1H}.joblib`; data cached in `data/pubchem_qhts_cache/`.
