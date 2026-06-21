# CNS data sources for Quiver model work — access guide + what we pulled

**Compiled 2026-06-15** (scout-verified access methods). Purpose: a single index of the CNS data online
that feeds Quiver's model work — ion-channel **binder/affinity** data (for the binder fine-tune) and
ion-channel **variant-function** data (for the Nav1.8 GoF/LoF model). Licenses are all open
(commercial + non-commercial both usable here). Data files are gitignored (`data/` is local-only); this
doc + the puller scripts in `experiments/` are the reproducible record.

Two findings frame the whole index:
- **Off-the-shelf binder triage is at chance (0.50) on CNS ion channels; a supervised scaffold-split probe
  hits 0.92** (`results/trunc_test_characterization.md`). So labelled ion-channel binder data is the
  missing ingredient — hence the binder sources below.
- **Nav1.8 (SCN10A) has no public GoF/LoF functional labels.** funNCion (the best public set) contains 44
  SCN10A variants but labels every one "unknown"; MissION is portal-only. So the Nav1.8 variant model is a
  build-on-Quiver-data target — the variant sources below give the *universe* + a *pathogenicity prior*, not
  the functional direction.

---

## Pulled to the repo (headless, done)

### 1. Guide to PHARMACOLOGY (IUPHAR/BPS) — ion-channel binder affinities  ✅ pulled
- **What:** curated small-molecule affinities (pKd / pIC50 / pKi) against voltage-gated (Nav/Cav/Kv) and
  ligand-gated (NMDA/GRIN) channels, with ligand SMILES, action, assay, PMID. High curation, modest volume.
- **CNS relevance:** the cleanest ion-channel binder set; Nav1.8 = targetId 585 (all Nav1.1–1.9 present).
- **Access (headless, no auth):** REST API `https://www.guidetopharmacology.org/services/` —
  `targets?type=VGIC` / `targets?type=LGIC`, `targets/{id}/interactions`, `ligands/{id}/structure`.
  Bulk SDF + interactions CSV at `https://www.guidetopharmacology.org/download.jsp`.
- **License:** ODbL (database) + CC-BY-SA-4.0 (content).
- **Puller:** `experiments/pull_gtopdb_ionchannel.py` → `data/cns_ionchannel/` (affinities CSV + targets CSV
  + `gtopdb_pull_summary.json` with per-family counts). See the summary JSON for exact row counts per
  nav/cav/kv/nmda family.

### 2. funNCion training tables — ion-channel GoF/LoF labels  ✅ pulled
- **What:** the canonical Nav/Cav GoF-vs-LoF curated label set (Brain 2022; funNCion AUROC 0.897).
  S1 = 6,930 pathogenic variants, of which **2,771 carry a usable functional label (1,007 GoF / 1,764 LoF)**;
  the rest are "unknown". S2 = 3,795 neutral variants. Fields: gene, pos, refAA, altAA, transcript, disease,
  `prd_mech_revised` (GoF/LoF), gnomAD_AF, penetrance, PMID. No raw electrophysiology — the curated GoF/LoF
  call IS the label.
- **CNS relevance:** the only headless source with real functional direction. Per-gene: SCN1A 1542,
  SCN5A 1484, SCN2A 753, CACNA1A 541, SCN9A 402, SCN8A 358, SCN4A 325, SCN3A 93, **SCN10A 44 (all "unknown")**.
- **Access (headless):** `https://raw.githubusercontent.com/heyhen/funNCion/master/` →
  `SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt`, `S2_neutralvariantsusedintraining3.txt`,
  `predictiontable_all_variants_CACNA1SCN.txt` (51 MB, funNCion predictions for all CACNA1/SCN variants —
  not pulled; use as a precomputed-prediction reference). Files are latin-1 encoded.
- **License:** GPL-3.0.
- **Stored:** `data/cns_variants/funncion/` (S1 + S2).

### 3. ClinVar — channelopathy variant universe + pathogenicity  ✅ pulled
- **What:** clinically-observed missense variants for the CNS channelopathy genes, with clinical
  significance (Pathogenic / Likely-path / VUS / Benign), review status, condition. **Pathogenicity only —
  NOT GoF/LoF direction.**
- **CNS relevance:** the variant *universe* + a pathogenicity prior; SCN10A has ~2,615 ClinVar records (vs
  funNCion's 44) — the breadth a Nav1.8 model would score.
- **Access (headless, no auth; add NCBI api_key for >3 req/s):** E-utilities
  `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term=<gene>[gene]...` + `esummary`;
  bulk `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz` (~439 MB).
- **License:** public domain (NCBI).
- **Puller:** `experiments/pull_clinvar_channelopathy.py` → `data/cns_variants/` (10,107 variants across 13
  genes, 800/gene cap: 648 pathogenic + 782 likely-path + 87 benign + 332 likely-benign + 8,251 VUS).
  Bump `retmax` to lift the per-gene cap if a full catalog is needed.

---

## Documented loaders (large — pull a subset on AWS, not to the laptop)

### 4. ChEMBL (ion-channel subset)
- **What:** large-scale bioactivity (Ki/IC50/pchembl) for ion-channel targets. human SCN10A = CHEMBL5440;
  mouse Nav1.8 = CHEMBL5158. Off-the-shelf DTI evals already pull per-target actives/inactives from here.
- **Access (headless):** REST `https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id=<id>`
  (paginated); Python `chembl_webresource_client`; bulk FTP
  `https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/`. **License:** CC-BY-SA-3.0.
- **Use:** reuse `aws/cns_dti_benchmark_eval.py`'s ChEMBL puller (now with a fail-fast socket timeout — an
  EBI 500 should skip a target, not hang). ChEMBL confirmed back up 2026-06-15.

### 5. BindingDB (ion-channel subset)
- **What:** ~3.2M binding measurements; full set has IC50/Ki ion-channel data (the `_Kd` split has zero Nav
  pairs — that's the split, not the DB). **Access:** bulk TSV
  `https://www.bindingdb.org/.../BindingDB_All_202606_tsv.zip` (~564 MB, no login). **License:** CC-BY-3.0.

### 6. Papyrus (standardized bioactivity)
- **What:** ~60M standardized bioactivity points (cleaner than raw ChEMBL for a fine-tune). v2024.2.
  **Access:** Zenodo `https://doi.org/10.5281/zenodo.13987985` (DOI 10.5281/zenodo.13987985) / 4TU
  `10.4121/16896406`; Python `papyrus-scripts`. **License:** CC-BY-4.0. Filter to ion-channel accessions.

### 7. Drug Target Commons (DTC)
- **What:** community-curated DTI incl. ion channels. **Access:** `https://drugtargetcommons.fimm.fi/`
  (download tab / API). **Caveat:** TLS cert-chain issue on automated fetch — use `curl --insecure` or a
  browser; verify before scripting. **License:** CC-BY-SA (confirm on download tab).

---

## Browser-only (Playwright) — oracle/benchmark, not a data feed
### 8. MissION (Synaptica Variant Interpreter)
- Best ion-channel GoF/LoF classifier (ROC-AUC 0.925 > funNCion 0.897), trained on 3,176 GoF/LoF variants
  (not published as a file). **Portal-only** — JS SPA at `https://www.synaptica.nl/variant-interpreter`;
  no repo/weights/API. Headless fetch sees ~1 KB → needs Playwright. Treat as a **prediction oracle to
  benchmark against**, not a data source. Paper: medRxiv 2025.10.16.25337735.

---

## Additional fine-tuning sources (scout round 2, 2026-06-15) — verified, additive

### Binder fine-tune (Track 2) — genuinely additive to ChEMBL/GtoPdb (headless, permissive)
- **SCION-adjacent confirmation:** *no open large Nav SAR series exists* — the Nav1.7 arylsulfonamide /
  Nav1.8 acyl-sulfonamide (VX-548) series are all paywalled JMC/EJMC supplements, and PubChem Nav records
  are ChEMBL-mirrored. **Nav binder data is Quiver's SPR lever**, confirming CLAUDE.md.
- **ExCAPE-DB v2** — `Zenodo 10.5281/zenodo.2543724` (one 432 MB `.tsv.xz`, CC BY-SA): 998k cpds / 70.85M
  pre-standardized PubChem+ChEMBL datapoints, gene-filterable to SCN/CACNA/GRIN/KCN. **HIGH** — fastest clean
  binder/decoy expansion. (ChEMBL portion overlaps ours; the PubChem portion is additive.)
- **WelQrate** — `welqrate.org` (CC BY 4.0, commercial-OK): ML-ready HTS sets KCNQ2 (247 act/289k),
  Cav3/T-type (652/95k), Kir2.1 (155/288k) with huge matched decoy pools. **HIGH** for class-balanced fine-tune.
- **PubChem BioAssay** (public domain) — gene-symbol → AIDs → activity CSV, headless: PUG-REST
  `…/assay/target/genesymbol/SCN9A/aids/JSON`, `…/assay/aid/<AID>/concise/CSV`,
  `…/compound/cid/<CID>/property/SMILES,ConnectivitySMILES/CSV` (note: `CanonicalSMILES→ConnectivitySMILES`,
  `IsomericSMILES→SMILES`; use `/concise/CSV`). Non-ChEMBL **MLPCN qHTS**: Cav3.2/CACNA1H AID 449739
  (104k cpds, 4,230 active) + 5 dose-response AIDs; KCNQ2 AID 2258. Bulk FTP
  `ftp.ncbi.nlm.nih.gov/pubchem/Bioassay/Concise/CSV/Data/`. **HIGH** raw volume / non-ChEMBL.
- **ToxCast/Tox21** — `EPA Figshare 10.23645/epacomptox.6062623` / `gaftp.epa.gov/COMPTOX/...` (CC0):
  NVS_IC_* radioligand ion-channel binding endpoints (Cav1.2 sites, Cav2.2, NMDA, 5-HT3, Na site-2) +
  dose-response. **HIGH for negatives/decoys at scale**, MED on-target.
- **PDBbind v2020 / Binding MOAD** — structure-aware affinity; only ~tens of ion-channel complexes
  (Nav1.7 7XM9/7XMF etc.). **MED** — pose/structure seed, not volume. HF/GitHub mirrors are headless.

### Variant fine-tune (Track 9) — SCION is the breakthrough
- **SCION** — `github.com/christianbosselmann/SCION` branch **master**, `data/clean_tbl.csv` (MIT, headless).
  **376 NaV missense with binary GoF/LoF (164 GoF / 211 LoF), and — critically — 16 SCN10A/Nav1.8 variants
  WITH direction (9 GoF / 7 LoF).** This is the ONLY flat-CSV source with real Nav1.8 functional labels
  (vs funNCion's 44 all-"unknown"). **PULLED → `data/cns_variants/scion/`** (clean_tbl.csv + dat_prep.csv
  feature table + raw_tbl.csv). The seed for a Nav-family GoF/LoF fine-tune with Nav1.8 as held-out transfer.
- **MaveDB** (CC0, API `api.mavedb.org`): hERG/KCNH2 ~22.8k surface-abundance + SCN5A S4 DMS (~252, explicit
  LoF) + KCNQ4 (4,085) + KCNQ2 (331). **HIGH** family-transfer volume, CC0, headless.
- **KCNQ1 MAVE** (Glazer/Roden 2025, CC BY, medRxiv `10.64898/2025.12.15.25341924` File S1): 13,403 KCNQ1
  variants with GoF/LoF + dominant-negative context. **HIGH** (PDF supplement → parse).
- **GRIN NMDA GoF/LoF** (Yuan/Traynelis, CC BY, HMG `ddae156`/`ddad104`): ~160 + 832 GRIN1/2A/2B variants
  with GoF/LoF + EP. **HIGH** for NMDA. (OUP xlsx throttles scripted curl → browser fetch.)
- **gnomAD v4.1** (CC0, GraphQL `gnomad.broadinstitute.org/api` + `gs://gcp-public-data--gnomad/`): common
  missense (AF≥1e-3) for SCN10A + all channel genes = **benign negatives**. **HIGH.**
- **ClinGen ERepo** (public, `erepo.genome.network`): PS3/BS3 functional evidence on epilepsy Na-channel +
  LQT K-channel VCEPs = pathogenicity prior. **HIGH** (family prior; no SCN10A-direct).
- **Channel_Distances** (Brünger/Lal, `github.com/LalResearchGroup/Channel_Distances`): 3,049 patho + 12,546
  population variants across 30 VGIC/LGIC subunits incl. SCN10A — pan-channel **negatives** (label axis is
  pathogenic-vs-population, not GoF/LoF). **MED.**
- Eval-only (NC / NC-ND licenses): SCN-viewer (CC BY-NC, 2nd Nav1.8 functional source), SCN8A-RF (CC BY-NC-ND).

**License-clean training order — variant:** SCION (MIT) > MaveDB Kv7/KCNH2 (CC0) > KCNQ1/GRIN (CC BY) >
gnomAD negatives (CC0); SCN-viewer + SCN8A-RF reserved for eval only.

---

## How this feeds the build targets
- **Ion-channel binder fine-tune:** GtoPdb (clean, pulled) + ChEMBL/BindingDB/Papyrus ion-channel subsets
  (loaders) → scaffold-split train, FP+GBT baseline. Substrate now in hand for the GtoPdb portion.
- **Nav1.8 variant model:** funNCion 2,771 GoF/LoF labels (Nav/Cav families) as transfer base + ClinVar
  universe + **Quiver's own functional readouts** for the Nav1.8 direction no public set has.
- **Cardiac multi-channel tox:** CToxPred2 (ion-channel-trained baseline, Track 5) on the FP recipe.
