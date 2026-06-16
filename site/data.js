// Auto-generated from capability_map.xlsx by _build/build_site_data.py
window.SAPPHIRE = {
  "meta": {
    "personas": 59,
    "prompts": 299,
    "pipelines": 399,
    "capabilities": 16,
    "atlasFreq": 104,
    "kgNodes": "1.8M",
    "kgEdges": "17.9M",
    "papers": "29k"
  },
  "capabilities": [
    {
      "id": "CAP-01",
      "area": "Functional similarity / embedding & clustering",
      "desc": "EP-signature proximity, antipodal/proximity, pathway reconstruction, KEGG clustering.",
      "layer": "Internal",
      "quiverData": "EP-CRISPR Atlas",
      "external": "STRING, Reactome, KEGG",
      "models": "Quiver encoder (native); MAMMAL (0.92), ESM-2-650M, ESM-C, SaProt, Ankh",
      "status": "Tested",
      "verdict": "MAMMAL NN-recall 0.92 on protein families, ties ESM-2-650M (0.75) on the 40-gene CRISPR-N panel; PROTON lost (0.49). Embedding/clustering is real & useful off-the-shelf. [Q-Mammal]",
      "gap": "—",
      "repPrompts": "006, 010-012, 031-041",
      "promptCount": 15,
      "topDiseases": [
        [
          "Cross-disease / platform",
          7
        ],
        [
          "TSC / mTOR",
          7
        ],
        [
          "Epilepsy / DEE",
          1
        ]
      ]
    },
    {
      "id": "CAP-02",
      "area": "Target discovery & prioritization",
      "desc": "Rank targets, antipodal-to-disease, convergent/common nodes across diseases.",
      "layer": "Internal",
      "quiverData": "EP-CRISPR Atlas",
      "external": "OpenTargets, DisGeNET, GWAS Catalog",
      "models": "Quiver DrugReflector (native); Open Targets + L2G, PandaOmics, TXGNN, PINNACLE",
      "status": "Native",
      "verdict": "Core Quiver function; external genetics/competition data re-ranks. Not an off-the-shelf-model question.",
      "gap": "Integrate CAP-06/CAP-12 for boosting",
      "repPrompts": "013-020, 030, 042-043, 071, 126-134, 175, 177-179, 181, 183-188, 190-193, 195-200, 202-213, 215-229, 231-243, 245, 247-256, 258-261, 263-264, 266-269, 271-272, 274",
      "promptCount": 106,
      "topDiseases": [
        [
          "Cross-disease / platform",
          43
        ],
        [
          "ASD / NDD",
          11
        ],
        [
          "Epilepsy / DEE",
          10
        ],
        [
          "Pain / channelopathy",
          10
        ]
      ]
    },
    {
      "id": "CAP-03",
      "area": "Drug-target binding / DTI / ligandability",
      "desc": "Single-target binder vs decoy triage, small-molecule rescue match, repurposing, ligandability.",
      "layer": "Internal + Predictivity",
      "quiverData": "EP-CRISPR Atlas",
      "external": "ChEMBL, BindingDB, DrugBank, RCSB PDB",
      "models": "Boltz-2 (mTOR 1.0/Nav 0.71), Chai-1, AF3, DeepPurpose; MAMMAL/ConPLex = chance on Nav",
      "status": "Tested",
      "verdict": "Off-the-shelf single-target triage ~= chance (MAMMAL Nav1.8 0.43, ConPLex 0.39). Boltz-2 split: mTOR AUROC 1.00, Nav1.8 0.71 (marginal, n=28). No off-the-shelf Nav oracle. [Q-Mammal]",
      "gap": "Quiver-data fine-tune for Nav-like triage (the lever)",
      "repPrompts": "045-054, 099-100",
      "promptCount": 12,
      "topDiseases": [
        [
          "Cross-disease / platform",
          10
        ],
        [
          "TSC / mTOR",
          1
        ],
        [
          "Pain / channelopathy",
          1
        ]
      ]
    },
    {
      "id": "CAP-04",
      "area": "ASO design & sequence generation",
      "desc": "Knockdown / allele-specific / splice-modulating ASOs, chemistry ranking, exact sequences.",
      "layer": "Internal",
      "quiverData": "EP-CRISPR Atlas + transcriptomics",
      "external": "gnomAD, ClinVar, RNAfold/ViennaRNA, NUPACK",
      "models": "RNAfold, NUPACK, SpliceAI/Pangolin, eSkip-Finder; OligoAI/ASOptimizer (preprint); no mature oracle",
      "status": "Gap",
      "verdict": "MAMMAL public artifact is a span-infiller (no usable de-novo design). ASO sequence design needs a dedicated stack. [Q-Mammal]",
      "gap": "Build / curate ASO-design toolchain",
      "repPrompts": "001-005, 008, 021-029, 044, 125, 176, 182, 189, 194, 246, 265, 275-299",
      "promptCount": 48,
      "topDiseases": [
        [
          "Cross-disease / platform",
          15
        ],
        [
          "Epilepsy / DEE",
          9
        ],
        [
          "ASD / NDD",
          8
        ],
        [
          "TSC / mTOR",
          5
        ]
      ]
    },
    {
      "id": "CAP-05",
      "area": "Mechanism disambiguation",
      "desc": "Synaptic vs intrinsic excitability, upstream/downstream, disease-modifying vs symptomatic.",
      "layer": "Internal",
      "quiverData": "EP-CRISPR Atlas (EP)",
      "external": "Reactome, KEGG",
      "models": "Quiver EP-assay decomposition (native)",
      "status": "Native",
      "verdict": "Quiver-unique: separates synaptic vs intrinsic signatures directly from electrophysiology.",
      "gap": "—",
      "repPrompts": "075-084",
      "promptCount": 10,
      "topDiseases": [
        [
          "Cross-disease / platform",
          8
        ],
        [
          "Depression / mood",
          1
        ],
        [
          "TSC / mTOR",
          1
        ]
      ]
    },
    {
      "id": "CAP-06",
      "area": "Genetics <-> function integration",
      "desc": "GWAS support, ClinVar mapping onto perturbation space, protective-variant simulation.",
      "layer": "Predictivity",
      "quiverData": "EP-CRISPR Atlas",
      "external": "GWAS Catalog, ClinVar, OMIM, DisGeNET",
      "models": "AlphaMissense, ESM-variant, VEP, Open Targets Genetics/L2G + KG join (Neo4j)",
      "status": "Untested",
      "verdict": "The boosting layer James described ('re-rank #7 to #1'): independent genetic corroboration of functional hits.",
      "gap": "Stand up KG join",
      "repPrompts": "085-094",
      "promptCount": 10,
      "topDiseases": [
        [
          "Cross-disease / platform",
          8
        ],
        [
          "ASD / NDD",
          1
        ],
        [
          "Depression / mood",
          1
        ]
      ]
    },
    {
      "id": "CAP-07",
      "area": "BBB / PK-PD / druggability",
      "desc": "BBB penetrance, required CNS exposure, metabolic liability.",
      "layer": "Context",
      "quiverData": "none / Atlas",
      "external": "SwissADME, ADMET-AI, B3DB",
      "models": "ADMET-AI (preferred), ADMETLab 3.0, SwissADME, pkCSM; MAMMAL BBBP (FP-biased)",
      "status": "Tested",
      "verdict": "MAMMAL BBBP AUROC 0.97 but false-positive biased -> soft positive only; ADMET-AI calibrated endpoints preferred. [Q-Mammal]",
      "gap": "—",
      "repPrompts": "095-098, 101, 103-104",
      "promptCount": 7,
      "topDiseases": [
        [
          "Cross-disease / platform",
          6
        ],
        [
          "Schizophrenia",
          1
        ]
      ]
    },
    {
      "id": "CAP-08",
      "area": "Toxicity & safety prediction",
      "desc": "Seizure/immunogenicity/ADMET risk, contraindications, the 'great target but causes cancer' check.",
      "layer": "Context",
      "quiverData": "none",
      "external": "ToxCast, Tox21, ADMET-AI, FAERS, VigiBase",
      "models": "ADMET-AI (DILI 0.83), ProTox-III, DeepTox, hERG ensembles; MAMMAL ClinTox unusable; seizure-liability = gap",
      "status": "Tested",
      "verdict": "ADMET-AI earns the tox-gate slot; MAMMAL ClinTox is memorized (0% sensitivity to external toxics) - do not gate on it. [Q-Mammal]",
      "gap": "—",
      "repPrompts": "009, 072, 102, 105-114",
      "promptCount": 13,
      "topDiseases": [
        [
          "Cross-disease / platform",
          12
        ],
        [
          "Epilepsy / DEE",
          1
        ]
      ]
    },
    {
      "id": "CAP-09",
      "area": "Combination & network strategy",
      "desc": "Synergistic pairs, dual-target profiles, hub genes that collapse multiple clusters.",
      "layer": "Internal",
      "quiverData": "EP-CRISPR Atlas",
      "external": "STRING, BioGRID, Reactome",
      "models": "Quiver combination-rescue (native) + network propagation",
      "status": "Native / Untested",
      "verdict": "Quiver functional combinations native; network topology from PPI/pathway DBs adds candidates.",
      "gap": "—",
      "repPrompts": "055-059, 115-124, 180, 201, 214, 230, 244, 257, 262, 270",
      "promptCount": 23,
      "topDiseases": [
        [
          "Cross-disease / platform",
          9
        ],
        [
          "ASD / NDD",
          3
        ],
        [
          "Depression / mood",
          3
        ],
        [
          "Epilepsy / DEE",
          3
        ]
      ]
    },
    {
      "id": "CAP-10",
      "area": "Biomarker & translational",
      "desc": "Fluid biomarkers aligned to EP phenotype, EEG correlation, symptom-domain mapping.",
      "layer": "Predictivity",
      "quiverData": "EP-CRISPR Atlas",
      "external": "GEO, Expression Atlas, Human Protein Atlas",
      "models": "Correlation analysis + literature",
      "status": "Untested",
      "verdict": "—",
      "gap": "—",
      "repPrompts": "060-064",
      "promptCount": 5,
      "topDiseases": [
        [
          "Cross-disease / platform",
          2
        ],
        [
          "Epilepsy / DEE",
          1
        ],
        [
          "Schizophrenia",
          1
        ],
        [
          "Depression / mood",
          1
        ]
      ]
    },
    {
      "id": "CAP-11",
      "area": "Variant -> disease / prevalence / genetic epidemiology",
      "desc": "Is gene X associated with disease Y; pathogenic-variant counts; patient population size.",
      "layer": "Context",
      "quiverData": "none",
      "external": "ClinVar, HGMD, gnomAD, OMIM, HPO, Orphanet",
      "models": "Knowledge-graph lookup (Neo4j, 1.8M nodes / 17.9M edges)",
      "status": "Untested",
      "verdict": "James' 'Amit question' set: a knowledge-graph/dataset capability, not a model. Largely served by the existing Sapphire v3 Neo4j graph.",
      "gap": "—",
      "repPrompts": "(none in the 299 - James' verbal add re: prevalence/variant-disease; nearest: 076, 089, 129)",
      "promptCount": 0,
      "topDiseases": []
    },
    {
      "id": "CAP-12",
      "area": "Protein-protein interaction / pathway membership",
      "desc": "Is gene in pathway X; PPI partners; cross-assay corroboration for re-ranking.",
      "layer": "Predictivity",
      "quiverData": "none",
      "external": "STRING, BioGRID, Reactome, KEGG",
      "models": "Graph / KG query",
      "status": "Untested",
      "verdict": "Boosting layer: independent assay corroboration (the 'appeared in two assays -> highly compelling' logic).",
      "gap": "—",
      "repPrompts": "(none in the 299 - James' verbal add re: PPI; nearest functional analogs: 033, 036-040)",
      "promptCount": 0,
      "topDiseases": []
    },
    {
      "id": "CAP-13",
      "area": "Competitive & commercial intelligence",
      "desc": "Active programs by phase, white-space, pricing, peak-sales, exclusivity.",
      "layer": "Context",
      "quiverData": "none",
      "external": "ClinicalTrials.gov, Cortellis, GlobalData, IQVIA, patents",
      "models": "LLM + curated feeds (Emit-style agentic web+DB)",
      "status": "Untested",
      "verdict": "This is the layer Emit/Sapphire orchestration must cover; test against the disease-MoA white-space prompts.",
      "gap": "Curated competitive-intel corpus",
      "repPrompts": "007, 070, 135-143",
      "promptCount": 11,
      "topDiseases": [
        [
          "Cross-disease / platform",
          9
        ],
        [
          "Schizophrenia",
          1
        ],
        [
          "TSC / mTOR",
          1
        ]
      ]
    },
    {
      "id": "CAP-14",
      "area": "Portfolio & capital allocation / financial optimization",
      "desc": "rNPV, $100M/$10B allocation, kill/fast-track decisions, peak-sales modeling.",
      "layer": "Meta",
      "quiverData": "none",
      "external": "Tufts CSDD, IQVIA, GlobalData; Gurobi/CPLEX solvers",
      "models": "LLM reasoning + optimization solvers",
      "status": "Untested",
      "verdict": "Pipelines already specify Monte-Carlo / ILP solvers; mostly LLM-orchestrated reasoning over market data.",
      "gap": "—",
      "repPrompts": "065-069, 073, 144-154, 273",
      "promptCount": 18,
      "topDiseases": [
        [
          "Cross-disease / platform",
          18
        ]
      ]
    },
    {
      "id": "CAP-15",
      "area": "Expert judgment / strategic reasoning",
      "desc": "'If you were CSO at Lilly...', regulatory strategy, clinical-trial design, franchise calls.",
      "layer": "Meta",
      "quiverData": "none",
      "external": "Public expert content (blogs, podcasts, talks, posts), regulatory precedent",
      "models": "EXPERT-AGENT (to build) - the '$50k Pfizer expert from public posts' idea",
      "status": "Gap",
      "verdict": "No off-the-shelf model. James' headline build: emulate a CNS regulatory/clinical expert from public output; the stock-sentiment-bot pattern applied to biology.",
      "gap": "BUILD expert-agent corpus + retrieval",
      "repPrompts": "074, 165-174",
      "promptCount": 11,
      "topDiseases": [
        [
          "Cross-disease / platform",
          11
        ]
      ]
    },
    {
      "id": "CAP-16",
      "area": "AI self-reflection / uncertainty quantification",
      "desc": "Where is data insufficient, confidence intervals, replication strength, model-drift sensitivity.",
      "layer": "Meta",
      "quiverData": "EP-CRISPR Atlas (replication)",
      "external": "—",
      "models": "Conformal (MAPIE/TorchCP), deep ensembles, abstention; Sapphire v3 plan layer",
      "status": "Partial / Native",
      "verdict": "Maps to Sapphire v3's transparent execution plans (which embeddings contributed, where data contradicts).",
      "gap": "—",
      "repPrompts": "155-164",
      "promptCount": 10,
      "topDiseases": [
        [
          "Cross-disease / platform",
          9
        ],
        [
          "ALS",
          1
        ]
      ]
    }
  ],
  "layers": {
    "Internal": {
      "blurb": "Quiver's unique functional data — the moat. Novel target signals nobody else has.",
      "sources": [
        [
          "Quiver EP-CRISPR Atlas",
          104,
          1
        ],
        [
          "GenomicsDB",
          27,
          2
        ],
        [
          "Sapphire Embedding Engine",
          9,
          3
        ]
      ]
    },
    "Context": {
      "blurb": "External data Quiver can't know — gates go/no-go. “Great pain target but causes cancer → no-go.”",
      "sources": [
        [
          "GTEx",
          45,
          1
        ],
        [
          "ClinVar",
          42,
          1
        ],
        [
          "OMIM",
          38,
          1
        ],
        [
          "DisGeNET",
          35,
          1
        ],
        [
          "HPO",
          29,
          2
        ],
        [
          "TCGA",
          27,
          2
        ],
        [
          "gnomAD",
          11,
          3
        ],
        [
          "Allen Brain Atlas",
          8,
          3
        ],
        [
          "Open Targets",
          7,
          3
        ],
        [
          "Cortellis",
          7,
          3
        ]
      ]
    },
    "Predictivity": {
      "blurb": "Independent corroboration → re-ranks hits. The #7 → #1 boost.",
      "sources": [
        [
          "STRING",
          45,
          1
        ],
        [
          "Reactome",
          39,
          1
        ],
        [
          "BioGRID",
          34,
          1
        ],
        [
          "LINCS L1000",
          29,
          2
        ],
        [
          "Connectivity Map",
          27,
          2
        ],
        [
          "Expression Atlas",
          27,
          2
        ],
        [
          "KEGG",
          10,
          3
        ],
        [
          "GWAS Catalog",
          7,
          3
        ]
      ]
    },
    "Reference": {
      "blurb": "Identifiers, structures, libraries, algorithms — the plumbing every layer depends on.",
      "sources": [
        [
          "DrugBank",
          55,
          1
        ],
        [
          "UniProt",
          45,
          1
        ],
        [
          "ChEMBL",
          17,
          2
        ],
        [
          "PDB / RCSB",
          13,
          3
        ],
        [
          "PubChem",
          11,
          3
        ],
        [
          "PubMed",
          11,
          3
        ],
        [
          "UCSC Genome Browser",
          11,
          3
        ],
        [
          "RNAfold",
          10,
          3
        ],
        [
          "NUPACK",
          9,
          3
        ],
        [
          "RDKit",
          9,
          3
        ],
        [
          "BLAST",
          8,
          3
        ],
        [
          "Scanpy / Seurat",
          8,
          3
        ],
        [
          "FAISS",
          7,
          3
        ]
      ]
    }
  },
  "methodology": [
    {
      "k": "personas",
      "n": "59",
      "t": "Personas",
      "d": "Fake-but-real-mandate execs (Pharma SVP, BD, Biotech CSO, VC GP) — who asks Sapphire, and with what philosophy."
    },
    {
      "k": "prompts",
      "n": "299",
      "t": "Prompts",
      "d": "The questions each persona would put to Sapphire — the demand side, across ~25 categories."
    },
    {
      "k": "pipelines",
      "n": "399",
      "t": "Pipelines",
      "d": "Each prompt expanded into a uniform 6-stage decomposition (inputs → tools → sub-prompts → outputs). 299 Sapphire + 100 Angelini."
    },
    {
      "k": "frequency",
      "n": "—",
      "t": "Tool frequency",
      "d": "Aggregate every pipeline's tool calls into a ranked list — the prioritized integration roadmap."
    },
    {
      "k": "map",
      "n": "16",
      "t": "Capability map",
      "d": "Cluster prompts into 16 capability areas; map each to candidate models + empirical status."
    },
    {
      "k": "gaps",
      "n": "2",
      "t": "Gaps → build",
      "d": "Where no off-the-shelf model exists (CAP-04 ASO design, CAP-15 expert judgment) → Quiver builds: curated corpus, expert agent, or data fine-tune."
    }
  ],
  "sampleQuery": {
    "query": "Which novel targets rescue Dup15q syndrome, outside UBE3A?",
    "tier": "Unified Orchestration (400–2000 ms)",
    "stages": [
      {
        "id": "L1",
        "name": "Internal latent",
        "kind": "internal",
        "detail": "Quiver EP-CRISPR fused embedding + DrugReflector rank rescuers by antipodal mechanism.",
        "result": "Ranked candidates. Gene Y = #1, Gene X = #7."
      },
      {
        "id": "L2",
        "name": "Context gate",
        "kind": "gate",
        "detail": "ClinVar / OMIM / GTEx / TCGA / ClinicalTrials.gov — a veto channel only (demote / kill, never promote).",
        "result": "One candidate flagged: oncogenic in TCGA → no-go. Gene X & Y pass."
      },
      {
        "id": "L3",
        "name": "Predictivity boost",
        "kind": "boost",
        "detail": "Independent corroboration: GWAS, STRING/BioGRID PPI with the disease gene, Reactome co-pathway, LINCS signature.",
        "result": "Gene X corroborated — PPI with UBE3A + hit in an academic screen → re-ranked #7 → #1."
      },
      {
        "id": "OUT",
        "name": "Answer + execution plan",
        "kind": "out",
        "detail": "Calibrated uncertainty gate. Confident → emit ranked hits + which embeddings/sources moved each rank. Uncertain → abstain & propose the experiment.",
        "result": "Gene X #1 with provenance. Confidence: HIGH."
      }
    ],
    "tiers": [
      [
        "Direct Run",
        "<100 ms",
        "internal latent similarity only"
      ],
      [
        "Atomic Fusion",
        "200–500 ms",
        "the re-ranking cascade (common case)"
      ],
      [
        "Unified Orchestration",
        "400–2000 ms",
        "planner + multi-agent panel over the metagraph"
      ]
    ]
  }
};
