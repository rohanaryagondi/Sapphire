# CNS fine-tune readiness map — where Quiver can fine-tune today vs must generate data

**Generated 2026-06-15** (`experiments/cns_finetune_readiness.py`, ChEMBL active counts, headless, $0).
Operationalizes the campaign's central finding: a per-target binder fine-tune hits **0.92-0.98 where data exists**
(`trunc_test`, `ionchannel_finetune`); off-the-shelf zero-shot is family-specific (kinase 0.80 / mTOR 0.72 /
GPCR 0.58 / **ion-channel 0.50**); and **cross-target transfer fails** (LOCO 0/4) so each target needs its own data.
Thresholds: **>=200 actives = fine-tune now**, 50-199 marginal, **<50 build/Quiver-data**.

| Target | Gene | Family | ChEMBL actives (pChEMBL>=6) | Zero-shot (family) | Recommendation |
|---|---|---|---:|---:|---|
| DRD2 | DRD2 | gpcr | 11896 | 0.58 | **FINE-TUNE NOW** |
| BACE1 | BACE1 | kinase | 11858 | 0.8 | **FINE-TUNE NOW** |
| 5HT2A | HTR2A | gpcr | 7738 | 0.58 | **FINE-TUNE NOW** |
| Nav1.7 | SCN9A | ion_channel | 7038 | 0.5 | **FINE-TUNE NOW** |
| GSK3B | GSK3B | kinase | 5748 | 0.8 | **FINE-TUNE NOW** |
| LRRK2 | LRRK2 | kinase | 5099 | 0.8 | **FINE-TUNE NOW** |
| AKT1 | AKT1 | mtor_pathway | 5016 | 0.72 | **FINE-TUNE NOW** |
| mTOR | MTOR | mtor_pathway | 4846 | 0.72 | **FINE-TUNE NOW** |
| PPARD | PPARD | mtor_pathway | 1886 | 0.72 | **FINE-TUNE NOW** |
| S6K1 | RPS6KB1 | mtor_pathway | 1866 | 0.72 | **FINE-TUNE NOW** |
| NMDA-NR2B | GRIN2B | ion_channel | 985 | 0.5 | **FINE-TUNE NOW** |
| PKM2 | PKM | mtor_pathway | 821 | 0.72 | **FINE-TUNE NOW** |
| NMDA-NR1 | GRIN1 | ion_channel | 573 | 0.5 | **FINE-TUNE NOW** |
| Nav1.8 | SCN10A | ion_channel | 552 | 0.5 | **FINE-TUNE NOW** |
| Nav1.2 | SCN2A | ion_channel | 308 | 0.5 | **FINE-TUNE NOW** |
| Nav1.5 | SCN5A | ion_channel | 308 | 0.5 | **FINE-TUNE NOW** |
| Cav1.2 | CACNA1C | ion_channel | 91 | 0.5 | **FINE-TUNE (marginal)** |
| Nav1.1 | SCN1A | ion_channel | 21 | 0.5 | **BUILD / QUIVER DATA** |
| Kv7.2 | KCNQ2 | ion_channel | 20 | 0.5 | **BUILD / QUIVER DATA** |
| Nav1.6 | SCN8A | ion_channel | 0 | 0.5 | **BUILD / QUIVER DATA** |

## Read
- **FINE-TUNE NOW**: enough public data that a per-target model should reach ~0.9+ today — deploy the ionchannel_finetune/trunc_test recipe.
- **BUILD / QUIVER DATA**: data-poor; transfer from other targets fails, so Quiver-generated screening data is the only path (highest moat ROI).
- Even WITHIN ion channels it splits sharply: Nav1.7/1.8/1.2/1.5 + NMDA are data-rich; **Nav1.1 (Dravet), Nav1.6, Kv7.2 (epilepsy) are data-poor -> Quiver-data targets**.
- Off-the-shelf zero-shot only trustworthy for kinase/mTOR-pathway (0.72-0.80); never for ion channels (0.50).
## Update 2026-06-15 — PubChem qHTS rescue of data-poor channels
Two "data-poor" channels were rescued using LARGE non-ChEMBL PubChem qHTS screens + fine-tuned LIVE:
- **KCNQ2 / Kv7.2** (was 20 ChEMBL actives → data-poor): PubChem AID 2156, 3,407 actives → scaffold-CV AUROC **0.811**, LIVE.
- **CACNA1H / Cav3.2** (T-type, not in ChEMBL panel): PubChem AID 449739, 4,230 actives → **0.791**, LIVE (new target).
qHTS models are weaker than ChEMBL-curated (0.79–0.81 vs 0.95–0.99; noisier single-concentration data) but deployable + Tanimoto-gated.
**Still build-don't-buy (no public rescue):** Nav1.1/SCN1A (Dravet), Nav1.6/SCN8A — no large non-ChEMBL Nav screen exists → Quiver-data targets. See `results/pubchem_qhts_characterization.md`.
