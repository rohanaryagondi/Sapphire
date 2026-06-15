# Sapphire Model & Tool Landscape

The **supply side** of the capability map: for each of the 16 capability areas, the candidate
models/tools/data resources that could serve it (2023–2026), with maturity and an honesty flag.

**Maturity:** `production` · `research` · `preprint` · `data-resource`
**Honesty flag:** `proven` (widely validated) · `paper-claim` (unverified for our use)

> Ground rules (Quiver's empirical culture):
> - "State-of-the-art on shit is still shit" — paper benchmarks ≠ performance on our targets.
> - The moat is Quiver's internal EP-CRISPR / V1-T data; everything below is **enrichment**.
> - Never feed proprietary functional data into an external model/service. These are queried with
>   public identifiers (gene symbols, disease terms, SMILES, trial IDs) only.
> - Where a row says "Quiver fine-tune is the lever," the real win is training on Quiver data, not
>   adopting the off-the-shelf model.

Empirically-tested-here rows (from the Q-Mammal eval) are marked **[Q-Mammal]**.

---

## CAP-01 Functional similarity / embedding & clustering

- **ESM-2 (650M/3B/15B) (2022)** — open (MIT), GPU. Sequence-only PLM embeddings for family clustering / EP-signature proximity. `production`/`proven`. **[Q-Mammal]** NN-recall 0.75 on the CRISPR-N panel; the 650M is the practical workhorse.
- **IBM MAMMAL (2024)** — open (Apache-2.0), GPU. Multi-task molecular/protein FM usable as an embedding backbone. `research`/`proven`. **[Q-Mammal]** family NN-recall **0.92**, beats ESM-2-650M — the current embedding lever; a Quiver EP-signature fine-tune on top is the differentiator.
- **ESM Cambrian / ESM-C (300M/600M/6B) (Dec 2024)** — open weights + gated Forge API (commercial OK), GPU. Drop-in ESM-2-650M replacement at lower inference cost, stronger structure signal. `production`/`proven`. Worth A/B-ing vs MAMMAL on the CRISPR-N panel.
- **SaProt (650M) (2024)** — open, GPU (needs Foldseek 3Di tokens). Structure-aware embeddings where EP phenotype tracks fold class. `research`/`proven`.
- **Ankh / Ankh2 (2023)** — open, GPU/TPU. Efficient encoder-only PLM matching ProtT5+ESM-2 at lower param count. `research`/`proven`.
- **ProtT5-XL-U50 (2021)** — open, GPU. Robust legacy embedding baseline / sanity floor. `production`/`proven`.

*PROTON lost the Q-Mammal embedding eval (NN-recall 0.49) — deprioritize.*

## CAP-02 Target discovery & prioritization

- **Open Targets Platform (2024)** — open (portal + GraphQL + bulk), hosted/local. Integrates genetic/genomic/expression/tractability evidence into target-disease scores. `production`/`proven`. The neutral, auditable backbone; ingests no proprietary data.
- **PandaOmics (Insilico) (2024)** — gated/commercial SaaS. >20 models scoring association + druggability + novelty + safety; CNS/ALS track record. `production`/`proven` (validated in ALS, GBM).
- **Open Targets Genetics / L2G (2024)** — open, hosted. ML locus-to-gene causal assignment from GWAS + functional genomics. `production`/`proven`.
- **PINNACLE (2024)** — open research, GPU. Context-aware (cell-type/tissue) PPI-network target representations — relevant for neuron-subtype prioritization. `research`/`paper-claim`.
- **TXGNN (2024, Nat Med)** — open, GPU. Zero-shot repurposing/indication prediction over a disease KG. `research`/`proven` (peer-reviewed; CNS-specific validation limited).

*Quiver angle: externals rank from public evidence; Quiver's EP-CRISPR functional hits are the orthogonal re-ranking layer, kept internal.*

## CAP-03 Drug–target binding / DTI / ligandability

- **Boltz-2 (Jun 2025)** — open (MIT), GPU. Co-folding + binding-affinity FM, ~1000× cheaper than FEP, strong HTS enrichment. `preprint`/`proven` (independent JCIM evals). **[Q-Mammal]** split — mTOR AUROC 1.0, Nav1.8 only 0.71 (marginal); good for tractable pockets, weak on Nav.
- **AlphaFold3 (2024)** — gated (server, non-commercial), GPU. Best-in-class complex structure incl. protein-ligand; no native affinity scalar. `production`/`proven` (structure); affinity `paper-claim`.
- **Chai-1 (2024)** — open weights + commercial API, GPU. AF3-class co-folding; pose generation feeding a downstream scorer. `research`/`proven` (structure).
- **MAMMAL DTI head (2024)** — open, GPU. **[Q-Mammal]** Nav1.8 **0.43 ≈ chance** — not a usable Nav oracle off the shelf. `research`/`paper-claim`.
- **ConPLex (2023)** — open, GPU. PLM-anchored contrastive DTI. **[Q-Mammal]** Nav1.8 **0.39 ≈ chance**. `research`/`proven` (general).
- **DeepPurpose (2020) / DiffDock (2023)** — open, GPU. DeepPurpose = 50+ DTI architectures for custom training; DiffDock = diffusion blind docking. `production`/`proven` (as frameworks).

*Verdict: no off-the-shelf Nav oracle. The lever is a **Quiver-data fine-tune** — a Nav/CNS-channel affinity head on Quiver readouts; use Boltz-2/DeepPurpose as the trainable scaffold, not the answer.*

## CAP-04 ASO / antisense oligonucleotide design

- **ViennaRNA / RNAfold (2.6.x)** — open, CPU. MFE structure / accessibility for target-site selection. `production`/`proven`. Foundational, not efficacy-predictive alone.
- **NUPACK (4.x) (2024)** — open academic / gated commercial, CPU. Nucleic-acid thermodynamics, hybridization, duplex design. `production`/`proven`.
- **SpliceAI (2019) + Pangolin (2022)** — open, GPU. Splice-site usage CNNs; core for splice-modulating ASO exon selection. `production`/`proven`.
- **OligoAI + ASO Atlas (2025)** — open web tool, GPU. ML over sequence + chemical mods on 188k RNase-H gapmer measurements (334 genes) for knockdown efficacy. `preprint`/`paper-claim`.
- **ASOptimizer (2025, NAR)** — open web. DL optimization of gapmer chemistry + off-target eval. `research`/`paper-claim`.
- **eSkip-Finder (2021)** — open web. ML for exon-skipping ASO efficacy. `production`/`proven` (niche). Pair with BLAST/GGGenome for off-target scans.

*No mature generative ASO oracle; this remains a CAP-04 build/curate target. Quiver's value: validating ASO mechanism in its EP/CRISPR readout.*

## CAP-05 Mechanism disambiguation

*Largely **Quiver-native** — EP signatures separate synaptic vs intrinsic-excitability phenotypes that no external model reproduces. External tools only contextualize the implicated genes/pathways.*

- **GSEA / fgsea** — open, CPU. Rank-based enrichment to interpret which pathways a hit-set touches. `production`/`proven`.
- **Reactome + ReactomeFIViz (2024)** — open, CPU/Cytoscape. Curated pathway/FI-network analysis incl. synaptic pathways. `production`/`proven`.
- **SynGO (2024)** — open, web. Expert-curated synaptic ontology — closest external proxy to the synaptic-vs-intrinsic axis. `production`/`proven`.
- **STRING / GeneMANIA (2024)** — open, web. Cluster implicated genes into mechanistic modules. `production`/`proven`.
- **CellOracle (2023) / SCENIC+ (2023)** — open, GPU/CPU. GRN inference + in-silico perturbation to corroborate (never replace) CRISPR directionality. `research`/`proven`.

## CAP-06 Genetics ↔ function integration

- **AlphaMissense (2023)** — open predictions (weights non-commercial), precomputed table. Proteome-wide missense pathogenicity; #1 of 65 VEPs in 2024-25 benchmarks. `production`/`proven`. Use precomputed scores.
- **Ensembl VEP (2024)** — open, CPU. Canonical variant annotation engine; hosts AlphaMissense/SpliceAI plugins. `production`/`proven`.
- **Open Targets Genetics / L2G (2024)** — open, hosted. GWAS fine-mapping + locus-to-gene. `production`/`proven`.
- **ClinVar + GWAS Catalog (2024)** — open, hosted/bulk. Curated clinical variant + GWAS ground truth. `production`/`proven`.
- **ESM1b / ESM-variant (2023)** — open, GPU. Zero-shot missense variant-effect scores; complements AlphaMissense. `research`/`proven`.
- **PrimateAI-3D (2023)** — gated (Illumina), GPU. 3D-structure-aware variant pathogenicity. `research`/`proven`.

*Quiver angle: overlay Quiver functional/EP variant-effect calls on top of AlphaMissense/L2G — internally. This is the "re-rank #7 → #1" boosting layer.*

## CAP-07 BBB / PK-PD / druggability

- **ADMET-AI (2024)** — open (web + local, Chemprop), CPU/GPU. Fast batch ADMET incl. BBB + PK, calibrated vs TDC. `production`/`proven`. **[Q-Mammal] Preferred for BBB** (well-calibrated).
- **MAMMAL BBBP head (2024)** — open, GPU. **[Q-Mammal]** AUROC 0.97 but **false-positive biased** — recall-oriented prefilter only, not go/no-go. `research`/`paper-claim`.
- **ADMETLab 3.0 (2024)** — gated (free web), cloud. 119 endpoints incl. BBB/CNS/logBB. `production`/`proven`.
- **SwissADME** — open web, CPU. BOILED-Egg BBB/GI + drug-likeness; fast triage. `production`/`proven`.
- **pkCSM (2018, maintained)** — open web, CPU. Graph-signature ADMET incl. BBB/CNS permeability. `production`/`proven`.
- **B3DB (2021)** — open dataset (7,807 molecules). Training/benchmark set for in-house BBB classifiers (AUC 0.93-0.96). `data-resource`/`proven`.

## CAP-08 Toxicity & safety prediction

- **ADMET-AI (2024)** — open, CPU/GPU. Broad tox panel incl. DILI/hERG/ClinTox/AMES. `production`/`proven`. **[Q-Mammal] DILI TPR 0.83** — the preferred general tox screen.
- **ProTox 3.0 (2024)** — open web, cloud. Oral tox class, organ tox, Tox21 pathway flags. `production`/`proven`.
- **ADMETLab 3.0 (2024)** — gated (free web). hERG, carcinogenicity, respiratory, DILI. `production`/`proven`.
- **DeepTox / Tox21 models (2015, maintained)** — open, GPU. Tox21-challenge-winning DNN for 12 endpoints. `production`/`proven`.
- **MAMMAL ClinTox head (2024)** — open, GPU. **[Q-Mammal] unusable — memorized** the split; do not use. `research`/`paper-claim`.
- **CardioTox / hERG ensembles (2023-24)** — open, GPU/CPU. Cardiac de-risking. `research`/`proven`.

*No reliable off-the-shelf **seizure-liability** predictor exists — a gap where Quiver's EP readout is the genuine differentiator.*

## CAP-09 Combination & network strategy

*Most "synergy predictors" are trained on cancer cell-line screens and transfer poorly to CNS; network/PPI tools are databases + graph algorithms, not predictive models.*

- **STRING v12 (2023)** — open, web DB + API. Confidence-scored PPI network; substrate for propagation + hub ranking. `data-resource`/`proven`.
- **DrugComb / DrugCombDB (2021–2024)** — open, portal + matrices. Aggregated combination screening (HSA/Bliss/Loewe/ZIP) for training/benchmarking. `data-resource`/`proven`.
- **DeepSynergy (2018)** — open, runnable. Reference synergy baseline, but oncology-trained. `research`/`proven` (oncology); `paper-claim` for CNS.
- **MD-Syn / DPASyn (2025)** — open. Multimodal/attention synergy predictors, incremental gains on oncology benchmarks. `preprint`/`paper-claim`.
- **Network propagation — RWR / DIAMOnD / NetCore / Hierarchical HotNet** — open algorithms over any PPI graph. Diffuse seed genes to prioritize neighbors/modules + hubs. `research`/`proven` (method); specific calls `paper-claim`.
- **NetworkX / igraph + STRING** — open libraries. Centrality/hubs + custom propagation; the glue layer. `production`/`proven`.

## CAP-10 Biomarker & translational

*Dominated by expression/proteomics **data resources** + standard DE/correlation methods; no turnkey phenotype-to-biomarker model.*

- **GEO (ongoing)** — open, DB + API (`GEOquery`). Primary transcriptomic repository for cross-study biomarker mining. `data-resource`/`proven`.
- **Expression Atlas / Single Cell Expression Atlas (EMBL-EBI)** — open, DB + API. Curated baseline/differential expression; tissue specificity of candidate markers. `data-resource`/`proven`.
- **Human Protein Atlas v24 (2024)** — open, DB + downloads. Antibody imaging + transcriptomics + MS + spatial; brain-elevated/CSF-secreted classes support fluid-marker triage. `data-resource`/`proven`.
- **NIAGADS brain–CSF–plasma pQTL atlases (2023-24)** — gated (registered), datasets. Link proteins across brain/CSF/plasma to neuro disorders. `data-resource`/`proven` (assoc.); causal use `paper-claim`.
- **Methods: limma / DESeq2 + WGCNA, EEG-omics correlation** — open R/Python. DE + co-expression modules, then correlate against EEG/phenotype. `production` (methods)/`paper-claim` (specific linkages).

## CAP-11 Variant→disease / prevalence / genetic epidemiology

*Overwhelmingly a **knowledge-graph/dataset** capability, not a model — assemble answers by querying, never by trusting a generative guess. (James' verbal add; not in the 299-prompt corpus.)*

- **ClinVar** — open, DB + API + FTP. Variant–phenotype assertions; pathogenic-variant counts per gene. `data-resource`/`proven`.
- **gnomAD v4 (2023-24)** — open, DB + downloads. Population allele frequencies (~800k exomes/genomes) for carrier-frequency / prevalence. `data-resource`/`proven`.
- **OMIM + HPO** — open/registered, DB + API. Curated gene–disease (OMIM) + phenotype ontology (HPO). `data-resource`/`proven`.
- **Orphanet / Orphadata** — open, DB + downloads. Rare-disease prevalence + gene associations — best for rare-CNS sizing. `data-resource`/`proven`.
- **Open Targets Platform (2025, NAR)** — open, + GraphQL + BigQuery/Parquet. Pre-built target–disease KG with prioritisation + direction-of-effect. `data-resource`/`proven` (data); composite score `paper-claim`.
- **DisGeNET (2024)** — now gated/commercial, web + API. ~380k associations (curated + text-mined). `proven` (curated subset)/`paper-claim` (text-mined). HGMD (gated, QIAGEN) is the comprehensive curated set where licensed.

## CAP-12 Protein–protein interaction / pathway membership

*All **data resources** via API/DB; no model. Best practice: require concordance across two independent sources before trusting a link. (James' verbal add.)*

- **STRING v12 (2023)** — open, DB + API. Functional + physical associations with evidence channels. `data-resource`/`proven`.
- **BioGRID (~4.4)** — open, DB + REST + downloads. Experimentally curated physical/genetic interactions incl. CRISPR screens. `data-resource`/`proven`.
- **IntAct (EMBL-EBI)** — open, DB + PSICQUIC API. Curated molecular interactions w/ method detail + MI scores. `data-resource`/`proven`.
- **Reactome** — open, DB + REST + `ReactomePA`. Manually curated reaction-level pathways + enrichment. `data-resource`/`proven`.
- **KEGG** — gated for bulk/commercial (free academic/web), DB + REST. Curated pathway maps. `data-resource`/`proven`.

## CAP-13 Competitive & commercial intelligence

*The clearest overlap with "Emit"-style AI: an LLM agent doing RAG-synthesis over free registries + gated commercial DBs, with citations. The model aggregates/reasons; gated DBs supply ground truth.*

- **ClinicalTrials.gov + API v2 (2023–)** — open, DB + REST. Trials by phase/sponsor/status/date — the free backbone. `data-resource`/`proven`.
- **Clarivate Cortellis CI + Regulatory AI Assistant (2025)** — gated/commercial, web + API + LLM assistant (Dec 2025, cited answers). Curated pipeline/patents/deals/regulatory/safety. `production`/`proven` (data); assistant synthesis `paper-claim`.
- **GlobalData Pharma Intelligence** — gated/commercial, web + API. Pipelines/trials/forecasts/deals + consensus sales. `production`/`proven`.
- **Evaluate (EvaluatePharma)** — gated/commercial, web + API. Consensus peak-sales, NPV, patent-expiry/exclusivity. `production`/`proven`.
- **IQVIA** — gated/commercial, feeds + API. Real-world sales/Rx + pricing/volume. `production`/`proven`.
- **LLM-agent pattern: web+DB retrieval orchestration (2025-26)** — build-it-yourself (agentic RAG over CT.gov, patents, press + a licensed DB). `research`–`production`/`paper-claim` (autonomous CI claims unproven; treat as decision support).

## CAP-14 Portfolio & capital allocation / financial optimization

*No off-the-shelf "pharma portfolio AI"; the realistic build is **LLM-orchestrated reasoning over market data feeding standard quant tools**, with benchmark PoS priors.*

- **rNPV + Monte-Carlo (methods)** — open/build (NumPy/SciPy/`pymc`; or `@RISK`/Crystal Ball). Stage-gated cash flows × cumulative PoS, distributions over cost/timing/sales. `production`/`proven`.
- **Solvers — Gurobi / CPLEX / CBC / HiGHS / OR-Tools** — commercial or open, libraries. Constrained budget/resource MILP across a portfolio. `production`/`proven`.
- **PoS benchmarks — BIO/Informa success rates + Tufts CSDD (2024-25)** — gated/commercial (some free), reports/datasets. Empirical phase-transition probabilities + cost/cycle-time priors by TA (CNS notably lower). `data-resource`/`proven`.
- **Consensus forecasts — Evaluate / GlobalData** — gated/commercial, web + API. Peak-sales/revenue inputs. `data-resource`/`proven`.
- **LLM-orchestrated reasoning layer (2025-26)** — build-it-yourself. Agent pulls inputs, runs rNPV/MC/optimization, narrates kill/fast-track. `research`/`paper-claim`.

## CAP-15 Expert judgment / strategic reasoning

***No off-the-shelf model.*** Intended build = the **expert agent** (see [`expert-agent/`](expert-agent/) — proposal + runnable scaffold). Patterns, with the honest caveat that persona-conditioning improves tone/framing but has shown near-zero/negative effect on specialized-task accuracy — so claims must be grounded in retrieved, cited public sources, not "pretend you are Dr. X."

- **RAG / GraphRAG over an expert corpus (2024-25)** — open (LangChain, LlamaIndex, Microsoft GraphRAG). Ground + cite claims from one expert's public output; GraphRAG adds multi-hop structure. `production` (framework)/`paper-claim` (fidelity).
- **Persona-conditioned LLMs / role agents (2024-26)** — build pattern (system-prompt persona ± LoRA on corpus). Tone/framing gains; accuracy degradation risk on reasoning tasks. `research`/`paper-claim`.
- **Source-credibility / recency weighting in retrieval** — build pattern (metadata-weighted retrieval + reranking). Standard in financial-sentiment pipelines. `research`/`paper-claim`.
- **LLM-as-panel / multi-agent debate** — build pattern. Multiple expert personas debate to surface disagreement + calibrate the spread of views. `research`/`paper-claim`.
- **Comparable products** — AlphaSense (generative search over expert-call transcripts), Cortellis Regulatory AI Assistant. Closest shipped analogs; none emulate a *named individual*. `production` (products)/`paper-claim` (emulation fidelity).

## CAP-16 AI self-reflection / uncertainty quantification

*Combine rigorous statistical wrappers (conformal) with LLM calibration + explicit abstention; LLM self-reported confidence is poorly calibrated.*

- **Conformal prediction — MAPIE / TorchCP (2024)** — open, Python. Distribution-free prediction sets/intervals with finite-sample coverage; wraps any model. `production`/`proven`.
- **Ensemble / Bayesian UQ — deep ensembles, MC-dropout, `laplace-torch`, `pymc`** — open. Epistemic uncertainty for molecular-property UQ under shift. `production`–`research`/`proven` (method); calibration under shift `paper-claim`.
- **LLM self-consistency / calibration — ConU / ConfAgents (2024-25)** — open methods + research code. Sample-agreement confidence or conformal wrappers on LLM outputs. `research`–`preprint`/`paper-claim`.
- **Selective prediction / abstention (conformal risk control, 2024-26)** — open methods. Calibrated "I don't know" / escalate — serves "where is data insufficient." `research`/`paper-claim`.
- **Replication & drift — meta-analytic concordance + Evidently AI / `nannyml` / ADWIN (2024-25)** — open/freemium. Cross-assay agreement as confidence; input/prediction drift monitoring. `production` (drift)/`paper-claim` (replication-as-confidence).

---

## Cross-cutting takeaways

1. **Foundation models are enrichment, not oracles.** On the hard internal task (single-target binder triage), MAMMAL and ConPLex are ≈ chance; Boltz-2 helps on tractable pockets only. The win is Quiver-data fine-tunes + the functional moat.
2. **Half the capability areas (CAP-11/12/13/14) are data-resource / agent-orchestration problems, not ML-model problems** — they're solved by querying ClinVar/STRING/CT.gov/Evaluate with an LLM that aggregates + cites, never invents. This is the Emit-overlap zone.
3. **CAP-04 (ASO) and CAP-15 (expert judgment) are the genuine build gaps** — no mature off-the-shelf solution; CAP-15 has a scaffolded proposal in `expert-agent/`.
4. **Honesty:** rows marked `paper-claim` have not been validated on Quiver targets. Treat them as candidates to test, not capabilities we have.
