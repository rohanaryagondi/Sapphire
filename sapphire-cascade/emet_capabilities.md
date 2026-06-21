# EMET Capabilities Reference

The live EMET (BenchSci) tool surface, captured from `emet.benchsci.com` on **2026-06-21** (signed in as
the user). This is the menu the EMET-driving agent picks from. Companion to
[`emet_protocol.md`](emet_protocol.md) (how to drive it). Everything below is invoked by **natural
language** — there are no per-capability toggles.

## Thinking level (the chat control; default = Balanced)
- **Quick** — single-step lookups.
- **Balanced** — standard execution.
- **Thorough** — multi-stage research: EMET builds an agentic **Research Plan**, loads named **Skills**
  (e.g. Gene Resolver · ClinVar Variants · GWAS Associations · Open Targets Associations · PubMed
  Literature), and queries databases in parallel. Use Thorough for any substantive evidence question.

## Interpretation stringency (set by phrasing)
"Standard" (default) · "High-Stringency" · "Exploratory" — or specify custom thresholds inline
(pLI, expression level, p-value, confidence, composite weights). E.g. "use high-stringency thresholds".

## Workflows (9) — invoke via the `+` menu or "Run the <name> workflow for <target> in <disease>"
| Workflow | Tag | Time | Phases | Use for |
|---|---|---|---|---|
| **Target Validation** | Target discovery | 3–15 min | 4 | genetic evidence + druggability + expression + safety flags for a target |
| **Lead Discovery** | Drug discovery | 12–18 min | 4 | binding-site analysis, bioactivity, developability of lead compounds |
| **Drug Repurposing** | Drug discovery | 8–12 min | 4 | repositioning: MoA ↔ disease biology ↔ clinical feasibility |
| **Safety Assessment** | Safety & PV | 15–30 min | 8 | deep target safety: expression, homology, modulators, clinical signals, PGx |
| **Pathway Analysis** | Pathways | 10–15 min | 4 | signaling cascades, enrichment, network topology |
| **Quantitative Evidence** | Evidence | 15–30 min | 5 | TPM, mutation burden, constraint, dependency, survival metrics |
| **Drug Safety** | Safety & PV | 12–18 min | 3 | post-market signal detection (FAERS) + mechanistic toxicity |
| **Target Modulation** | Variant & modulation | 10–15 min | 3 | perturbation data + drug-response profiles |
| **Database Q&A** | Q&A | 3–8 min | 3 | a specific factual question, cross-validated across DBs |

**Sapphire mapping:** EMET Analyst safety/contraindication → *Drug Safety* / *Safety Assessment*; target
corroboration → *Target Validation* / *Target Modulation*; pathway/network → *Pathway Analysis*; effect
sizes → *Quantitative Evidence*; prevalence/general → *Database Q&A*.

## Capabilities (22) — name · what it does
Target Validation · Drug Discovery · Expression Analysis · Variant Interpretation · Pathway & Network
Analysis · Literature & Evidence · Structure & Protein Analysis · Cancer Genomics · Safety & Toxicity ·
Spatial & Cell Biology · Sequence Analysis · Phenotype & Disease · Cheminformatics & Molecular Design
(descriptors, Lipinski/Veber/QED, PAINS, SAR, activity cliffs) · Enzyme & Biochemistry (Km/kcat/Vmax) ·
Differential Expression & Multi-Omics (DESeq2/limma, volcano/heatmap, DIABLO/MOFA2) · Epigenomics & Gene
Regulation (ENCODE ChIP-seq, TFBS, histone marks) · Functional Genomics & CRISPR Screens (essentiality,
synthetic lethality, sgRNA design) · Machine Learning for Biology (ESM-2 embeddings, variant impact,
UMAP) · Research Planning & Methodology · HPC Bioinformatics Pipelines (Galaxy, 9k+ tools) · Molecular
Cloning Simulation · Configurable Interpretation (the stringency modes above).

## Data sources (~70, by category)
- **Literature & knowledge:** PubMed, Europe PMC, NCBI PMC, BenchSci Corpus (full-text), PubTator3,
  OpenAlex, iCite, GeneRIF, MyGene.info, NCBI Gene, Monarch, OpenTargets, BioAtlas, OpenI, SciCrunch, BioStudies.
- **Clinical & variants:** ClinVar, ClinGen, ClinicalTrials.gov, gnomAD, GWAS Catalog, Genebass,
  Pan-UK Biobank, dbNSFP, MyVariant.info, Gene2Phenotype, PharmGKB, CADD/CPIC.
- **Drug discovery:** ChEMBL, BindingDB, PubChem, MyChem.info, DGIdb, GtoPdb, Pharos, DrugMechDB,
  DailyMed, OpenFDA (FAERS), DDInter, FRDB, KTMine Patents (100M+), L1000FWD, PPB Affinity, BRENDA, ChEBI.
- **Expression & omics:** GTEx, GEO, Protein Atlas, CellxGene, Human Cell Atlas, Bgee, ENCODE, Ensembl,
  GeneRanger, UCSC Genome Browser, miRBase, miRDB, recount3 (+ meta-skills: Normal Gene Expression).
- **Cancer genomics:** cBioPortal, TCGA (+ TCGA Cancer Variants), GDC, DepMap, CCLE, Xena, OncoKB, CIViC,
  SynLethDB, GenomeCRISPR, Perturbation Catalogue.
- **Pathways & interactions:** Reactome, STRING, IntAct, SIGNOR, QuickGO, JASPAR, EpiGraphDB.
- **Protein & structure:** UniProt, PDB, AlphaFold, InterPro, ESM-2 Embeddings, Proteomic Data Commons.
- **Spatial & anatomy:** UBERON, Cell Ontology, HuBMAP, Human Reference Atlas, Tissue Mapper.
- **Lab tools / calculators (internal):** RDKit Cheminformatics, Molecular Properties (ADMET), SAR
  Analysis, Variant Annotator, Target Assessment (GO/CAUTION/NO-GO), Safety Target Validator, Primer
  Design, MSA Alignment, DEG Analysis, Experimental Design Advisor, PDF Report Generator, Notebook Export,
  Zotero/Citation Export. Platforms: Galaxy, AnVIL/Terra, EBI Job Dispatcher, MouseMine.

## Outputs (right rail + builders)
Inline **answer** (structured markdown, inline `[PMID …]` citations) · **Sources** panel (reference list)
· **Interactive Knowledge Graph** · **Dashboard** (Preview / HTML / Print) · **Report** (Print / HTML) ·
**Slides / SVG editor** (Download PNG). Visualizations: Bar/Line/Pie/Scatter, Interactive Table, plus
Statistical / Clinical / Genomic / Networks-&-Flow / Drug-Discovery / Diagram chart families.

## Data-boundary note (keep our public-only guard)
Several capabilities accept inputs that can be **proprietary** — Differential Expression / HPC pipelines
(FASTQ, private accessions), Molecular Cloning (plasmid sequences), Cheminformatics / Molecular Properties
/ SAR (SMILES of unpublished compounds), ML-for-Biology / ESM-2 (raw sequences), AnVIL/Terra (controlled
datasets). Sapphire sends **public identifiers only** (gene symbol, published SMILES, disease term, trial
ID). Never feed Quiver internal scores, candidate IDs (`QS…`), or EP/CRISPR/functional traces — the
harness `data_boundary` guard enforces this, and so must the human driver. *(Note: prior EMET chats in
this workspace contain `QS…` IDs from earlier exploratory use — that predates the Sapphire guard.)*
