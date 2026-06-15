const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, LevelFormat, AlignmentType, UnorderedList, Table, TableRow, TableCell, BorderStyle, PageBreak } = require("docx");

const children = [];

// H1 TITLE
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [new TextRun({ text: "Sapphire Pipeline Workflow: Comprehensive Ranked ASO Candidate Library for Disease Clusters", bold: true, font: "Arial", size: 32 })],
}));

// Prompt paragraph
children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Prompt: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "For a given disease cluster (epilepsy, ASD, or TSC), generate a ranked list of 10 ASO sequences including: Exact nucleotide sequences (5'→3'), Predicted knockdown %, Off-target risk score, Immunogenicity risk, CNS stability prediction, EP rescue probability score, Recommended next validation experiments.", font: "Arial", size: 24 }),
  ],
}));

// 2 overview paragraphs
children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Antisense oligonucleotides (ASOs) represent a powerful therapeutic modality for neurological disease clusters including epilepsy, autism spectrum disorder (ASD), and tuberous sclerosis complex (TSC). This pipeline integrates advanced computational design, risk stratification, and mechanistic validation to systematically generate and rank ranked ASO candidates. By combining sequence optimization with CNS pharmacokinetics modeling and seizure rescue probability scoring, this workflow ensures that only the most promising candidates advance to experimental validation.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "The Sapphire Pipeline 299 leverages Quiver's EP CRISPR atlas to predict seizure rescue probabilities from epilepsy gene variants, combines multi-parameter risk assessment including off-target binding and immunogenicity, and implements rigorous CNS stability predictions to optimize ASO chemistry for brain delivery. Through six integrated stages, this pipeline transforms clinical disease presentation into experimentally-validated therapeutic candidates with ranked priority scores.", font: "Arial", size: 24 }),
  ],
}));

// H2 Pipeline Overview
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Pipeline Overview", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "This end-to-end pipeline systematically transforms disease cluster information into a ranked library of 10 ASO sequence candidates with comprehensive performance predictions. Each stage employs validated computational tools and databases to minimize off-target effects, predict immunogenicity, model CNS pharmacokinetics, and estimate seizure rescue probability based on mechanistic understanding of gene-disease relationships in epilepsy, ASD, and TSC.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "The pipeline is designed to output ASO sequences with exact nucleotide specifications (5'→3' orientation), quantitative knockdown predictions, multi-factor risk scores normalized to 0-100 scales, CNS stability indices, EP rescue probability scores integrating Quiver atlas data, and actionable next-stage validation experiments with specific assay parameters and success criteria.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 1 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 1: Disease Cluster & Target Gene Selection", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Identify and prioritize disease-associated target genes within the specified disease cluster (epilepsy, ASD, or TSC) based on variant frequency, functional impact, clinical severity correlation, and existing literature evidence supporting ASO therapeutic potential.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage1_inputs = [
  "Disease cluster designation (epilepsy DEE genes, ASD risk loci, or TSC1/TSC2 domain variants)",
  "Patient cohort genetic data with variant calls and phenotypic severity annotations",
  "Literature-curated gene-disease association scores from ClinVar and OMIM databases",
  "Functional impact predictions (LoF intolerance, constraint metrics from gnomAD)",
  "Previous ASO efficacy reports for disease cluster targets from published clinical trials",
];

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "", font: "Arial", size: 24 })],
}));

stage1_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage1_tools = [
  "ClinVar database for disease-variant-gene associations and pathogenicity assertions",
  "OMIM (Online Mendelian Inheritance in Man) for comprehensive disease-gene curations",
  "gnomAD constraint metrics (pLI, Z-scores) for gene intolerance to loss-of-function",
  "Quiver EP CRISPR atlas for variant-specific seizure rescue probability baseline data",
  "UniProt/Ensembl for protein domain annotations and orthologue conservation analysis",
  "PubMed full-text search with NLP for clinical trial outcome extraction",
];

stage1_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage1_subprompts = [
  "Query ClinVar for all pathogenic variants in PCDH19, SCN1A, and GABRB2 (epilepsy cluster) with assertion criteria and allele frequency in disease populations",
  "Extract from literature the functional consequence of TSC1/TSC2 haploinsufficiency and calculate predicted mRNA stability impact for truncation vs. missense mutations",
  "Rank candidate genes by composite score: (LoF intolerance × clinical severity × ASO feasibility + literature evidence weight) normalized to 0-100",
  "Identify conserved protein domains across orthologs for each candidate gene to inform ASO targeting strategy and expected phenotypic rescue",
  "Validate patient variant penetrance by cross-referencing gnomAD frequency against disease cohort prevalence",
];

stage1_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage1_outputs = [
  "Prioritized list of 3-5 target genes ranked by composite clinical utility score (0-100 scale)",
  "Gene-specific isoform information with tissue-specific expression patterns (CNS-enriched isoforms prioritized)",
  "Variant characterization table including allele frequency, functional impact class, and disease correlation coefficient",
  "mRNA target region recommendations (5'UTR, start codon region, exon-intron junctions, stop codon vicinity)",
  "Disease cluster phenotypic rescue hypothesis for each target gene linking genotype to seizure/behavioral outcomes",
  "Literature-derived baseline seizure rescue probability range for target genes (e.g., PCDH19: 45-65% based on prior studies)",
];

stage1_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Ranked gene table (CSV/JSON) with isoform identifiers (ENST/NM), tissue-specific expression (FPKM), variant class, and seizure rescue hypothesis.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 2 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 2: ASO Sequence Design & Chemistry Optimization", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Design 10-15 ASO candidates per target gene with optimized chemical modifications (2'MOE, phosphorothioate linkages, gapmer architecture) to maximize mRNA knockdown efficiency, CNS penetration, and stability while minimizing toxicity and immunogenic triggers.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage2_inputs = [
  "Target gene isoform sequences (mRNA reference from Ensembl with NCBI accession validation)",
  "ASO design constraints: length optimization (18-21 nt baseline), GC content (40-60%), thermodynamic stability (Tm calculation)",
  "CNS penetration criteria: hydrophobicity scores, charge distribution at physiologic pH",
  "Chemical modification preference profiles (2'MOE wings vs. full modifications; phosphorothioate gap density)",
  "Species pharmacokinetic data: human liver metabolism, BBB permeability, glial uptake rates",
];

stage2_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage2_tools = [
  "NCBI Blast for sequence specificity screening against off-target mRNA transcripts",
  "Oligo Design Tool (ODT) and GENSCAN for secondary structure prediction and binding site identification",
  "Tm calculation (nearest-neighbor thermodynamics) via OligoCalc and RNA structure prediction (RNAstructure, Mfold)",
  "MOEsearch database for published ASO designs targeting homologous sequences in disease genes",
  "Ionis (Antisense Pharma) gapmer design guidelines and ISIS/Ionis chemistry proprietary scoring",
  "COSMIC cancer database for somatic variant ASO design precedents in neurological indications",
];

stage2_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage2_subprompts = [
  "Design 5 ASO candidates (18-21 nt) targeting PCDH19 exon 1 splice junction with 2'MOE-PS gapmer architecture; calculate Tm and GC% for each",
  "Generate design variants with differential chemical modifications: (a) full 2'MOE, (b) 2'MOE wings + PS gap, (c) PS only; predict relative stability in mouse CSF",
  "Identify optimal binding site within SCNA1 mRNA (within 500 bp of start codon) based on predicted accessibility score using RNAfold secondary structure output",
  "For each ASO candidate, calculate charge distribution at pH 7.4 and estimate BBB penetration probability using logD and molecular weight constraints",
  "Design isoform-specific ASO variants that spare functional protein isoforms while targeting pathogenic truncation-inducing transcripts",
];

stage2_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage2_outputs = [
  "10-15 ASO candidates per target gene with exact nucleotide sequences (5'→3' orientation), chemically notated (e.g., [2MOE]ACGTACGT[PS]ACGTACGT[2MOE]ACGTACGT)",
  "Sequence-specific properties table: length (nt), GC%, Tm (°C), predicted secondary structure free energy (kcal/mol), predicted accessibility score (0-1)",
  "Chemical modification optimization rationale with predicted in vitro stability (T1/2 in human serum) and CNS stability index (0-100)",
  "Off-target binding site predictions via BLAST (top 10 homology hits with % identity and predicted binding affinity ΔG)",
  "mRNA target site context information: surrounding sequence, predicted RBP binding sites, accessibility in native cellular conditions",
  "Projected knockdown efficiency range (%) for each ASO candidate based on structural accessibility and chemical modification class",
];

stage2_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "ASO sequence design matrix (XLSX/JSON) with columns: ASO_ID, Sequence_5to3, Modification_Type, Tm, GC%, Target_Site, Accessibility, Predicted_Knockdown_Range.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 3 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 3: Off-Target & Immunogenicity Risk Assessment", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Systematically evaluate off-target binding potential and immunogenicity risk for all ASO candidates using comprehensive genome-wide screening, protein sequence homology analysis, and machine learning-based immunogenicity prediction to identify and deprioritize sequences with unacceptable safety profiles.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage3_inputs = [
  "ASO candidate sequences from Stage 2 with chemical modification specifications",
  "Complete human transcriptome reference (Ensembl GTF + NCBI RefSeq, including long non-coding RNAs)",
  "Human proteasome and immunological toll-like receptor (TLR) binding motif databases (TLR3, TLR7, TLR8 specificity)",
  "Off-target prediction scoring thresholds: seed match definition, base-pairing mismatch tolerance, binding free energy cutoffs",
  "Chemical modification effects on TLR activation: sequence context analysis for 2'MOE vs. PS linkage immunogenicity modulation",
];

stage3_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage3_tools = [
  "Ensembl/NCBI BLAST (whole-genome BLAT) for comprehensive off-target identification with seed/non-seed mismatch scoring",
  "TLR motif database (DREME, FIMO) for pattern matching of TLR3/7/8 immunogenic elements within ASO sequences",
  "Ionis SpliceAssay database and immunogenicity prediction model for chemical modification-specific TLR activation probability",
  "UniProt BLAST for protein sequence homology to identify predicted off-target protein translation effects",
  "DrugBank immunogenicity scoring algorithm (ASO-specific): sequence motif analysis + structural properties",
  "Published literature meta-analysis (PubMed) for experimental off-target toxicity reports in similar ASO chemistry classes",
];

stage3_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage3_subprompts = [
  "Screen each ASO candidate against full human transcriptome (Ensembl) allowing 0-2 seed mismatches (pos 1-8); report top 10 off-target hits with ΔG and seed match count",
  "For each off-target mRNA, predict functional consequence: coding sequence impact, regulatory region effects, tissue-specific expression patterns",
  "Calculate immunogenicity risk score (0-100) integrating TLR motif presence, GU-content (TLR3 trigger), cytosine position (TLR7/8), and chemical modification effects",
  "Identify problematic immunogenic motifs (CpG dinucleotides, UGUGU/UGUGUG repeats) and calculate alternative sequence variants with equivalent binding affinity but reduced immunogenicity",
  "Cross-reference predicted off-target transcripts against disease-relevant tissues (cortex, hippocampus, cerebellum) to stratify safety risk by cellular context",
];

stage3_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage3_outputs = [
  "Off-target risk score (0-100 scale) for each ASO: weighted combination of (a) number of off-target sites ≤2 mismatches, (b) ΔG for top off-target hits, (c) tissue-specific expression of off-targets",
  "Immunogenicity risk score (0-100 scale) incorporating TLR motif analysis, GC-rich region quantification, cytosine frequency, and chemical modification immunogenicity coefficient",
  "Detailed off-target report: top 10 predicted off-targets per ASO with Ensembl transcript ID, gene symbol, functional category (coding vs. regulatory), predicted functional impact",
  "TLR activation probability prediction (0-100) with sequence-specific motif positions and modification-dependent risk modulation",
  "Tissue-specific safety index for CNS-relevant cell types (neurons, glia, endothelial cells) based on off-target expression patterns",
  "Recommended alternative sequence variants with reduced immunogenicity (if score > 40) preserving on-target binding affinity within 2 kcal/mol",
];

stage3_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Risk assessment matrix (XLSX/JSON) with columns: ASO_ID, OffTarget_Risk_Score, Immunogenicity_Score, Top_Offtarget_Gene, TLR_Activation_Probability, Tissue_Safety_Index.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 4 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 4: CNS Stability & Pharmacokinetic Modeling", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Model ASO pharmacokinetics in CNS-relevant compartments, predict intracellular uptake mechanisms, quantify serum/CSF stability, estimate brain bioavailability, and determine optimal dosing strategies to achieve therapeutic knockdown in neurons while minimizing off-target effects in peripheral tissues.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage4_inputs = [
  "ASO sequences with chemical modifications and off-target/immunogenicity risk scores from Stage 3",
  "Physicochemical properties: molecular weight, logD, pKa, charge distribution, predicted membrane permeability",
  "CNS pharmacokinetic parameters: mouse/rat blood-brain barrier penetration data, glial cell uptake rates (sorted primary glia culture data)",
  "Stability data: serum half-life (T1/2 human serum at 37°C), CSF stability predictions, nuclease susceptibility profiles",
  "Literature-derived ASO brain concentration ranges for chemically similar compounds (reference ASOs: nusinersen, inotersen, tofersen)",
];

stage4_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage4_tools = [
  "ChemAxon LogD/pKa calculator and Molinspiration property predictor for physicochemical profiling",
  "FDA PharmaKinetics Simulator (PBPK) for whole-body pharmacokinetic modeling with CNS compartment",
  "Literature meta-analysis for BBB penetration prediction using ASO-specific models (charge-adjusted, modification-dependent)",
  "PubChem/DrugBank for reference ASO stability data and species-comparative pharmacokinetics",
  "Computational nuclease resistance prediction tools: ExonNuclease1 resistance scoring, RNase H susceptibility prediction",
  "GlialDB (transcriptomic database) for tissue-specific receptor expression predicting glial uptake efficiency",
];

stage4_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage4_subprompts = [
  "Calculate physicochemical properties (MW, logD, pKa, calculated charge at pH 7.4, H-bond donors/acceptors) for each ASO and predict BBB permeability using logD-adjusted Lipinski rule thresholds",
  "Model serum stability (T1/2) for each chemical modification class based on reference ASO data; predict hepatic metabolism rate and systemic clearance",
  "Simulate CSF penetration probability using literature-derived BBB permeability coefficients and glial uptake saturation kinetics; estimate steady-state brain concentration at clinically feasible IV doses",
  "Predict intracellular uptake mechanism (endocytosis vs. receptor-mediated) based on charge distribution and sequence motifs; calculate neuronal vs. glial cell uptake efficiency ratio",
  "Determine optimal dose regimen (loading dose + maintenance interval) to achieve target knockdown in CNS neurons while minimizing renal/hepatic toxicity risk",
];

stage4_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage4_outputs = [
  "CNS stability prediction score (0-100): composite index of serum T1/2, CSF stability, nuclease resistance, and predicted intracellular half-life in neuronal compartment",
  "BBB penetration prediction (0-100 scale): logD-adjusted permeability probability with confidence intervals from literature-derived ASO transport models",
  "Pharmacokinetic profile: predicted serum T1/2 (hours), CSF T1/2 (hours), steady-state Cmax in brain (nM at therapeutic dose), accumulation index (Cmax_SS / Cmax_single)",
  "Tissue distribution prediction: estimated concentration ratios (brain/plasma, CSF/plasma, neuron/glia) at steady state with dose normalization",
  "Optimal dosing recommendation: loading dose (mg/kg), maintenance interval, target steady-state CNS concentration (nM), anticipated time to maximum knockdown (weeks)",
  "Safety margin assessment: predicted organ-specific accumulation risk for liver/kidney/spleen with Cmax safety thresholds based on reference ASOs",
];

stage4_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Pharmacokinetic report (XLSX/PDF) with physicochemical properties, stability predictions, dosing regimen, tissue distribution, safety margin summary.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 5 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 5: EP Rescue Probability Scoring & Ranking", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Integrate Quiver's epilepsy (EP) CRISPR atlas seizure rescue probabilities with mechanistic predictions of ASO-mediated mRNA knockdown, CNS bioavailability, and off-target effects to generate comprehensive ranking scores for all candidates, prioritizing sequences with optimal seizure rescue probability-to-risk ratios.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage5_inputs = [
  "Quiver EP CRISPR atlas: variant-specific seizure rescue probability data (baseline + mechanistic modifiers for haploinsufficiency vs. dominant-negative)",
  "ASO knockdown efficiency predictions and chemical modification effects on mRNA degradation kinetics from Stage 2",
  "CNS bioavailability predictions, brain target site accessibility, and neuronal cell uptake efficiency from Stage 4",
  "Integrated off-target risk and immunogenicity scores from Stage 3 with tissue-specific CNS safety margins",
  "Disease-cluster-specific seizure severity data: baseline seizure frequency, EEG abnormality patterns, treatment resistance classification",
];

stage5_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage5_tools = [
  "Quiver EP CRISPR atlas database (Allen Institute) with variant-specific seizure rescue probability and mechanistic annotation",
  "Gene Therapeutics Knowledge Base (GTK) for ASO target coverage and predicted knockdown-to-phenotype relationships",
  "mRNA degradation kinetics models (UGCR, kinetic rate constant integration) for quantitative knockdown prediction",
  "Quantitative genetics modeling for haploinsufficiency vs. dominant-negative mechanism prediction specific to each variant",
  "Statistical meta-analysis framework for combining multiple seizure rescue probability sources into consensus predictions",
  "Clinical outcome prediction model integrating baseline seizure severity, pharmacoresistance, and age-of-onset factors",
];

stage5_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage5_subprompts = [
  "For each target variant in Quiver atlas, extract baseline seizure rescue probability and mechanistic modifiers (haploinsufficiency effect size, functional consequence of truncation)",
  "Calculate predicted knockdown effect (%) for each ASO candidate using structure-accessibility scores and chemical modification stability constants; convert to equivalent ASO-mediated rescue probability",
  "Integrate CNS bioavailability predictions from Stage 4 as modifier to rescue probability: apply dose-response saturation curve and neuronal uptake efficiency weighting",
  "Generate composite ranking score per ASO: (Predicted_Knockdown% × Quiver_Baseline_RescueProb × BBB_Penetration_Score) / (OffTarget_Risk × Immunogenicity_Risk × Safety_Concern_Weighting)",
  "Perform sensitivity analysis: vary key parameters (knockdown prediction ±10%, BBB permeability ±20%, off-target risk ±15%) to identify score robustness and rank stability",
];

stage5_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage5_outputs = [
  "EP rescue probability score (0-100 scale) for each ASO combining Quiver baseline data with knockdown kinetics and CNS bioavailability adjustments",
  "Ranked list of top 10 ASO candidates sorted by integrated rescue probability-to-risk score with 95% confidence intervals",
  "Detailed ranking rationale for each top-10 candidate: component scores for (a) predicted knockdown %, (b) Quiver baseline seizure rescue, (c) CNS penetration, (d) off-target risk penalty, (e) immunogenicity penalty",
  "Sensitivity analysis summary: parameter uncertainty ranges, rank stability assessment, critical decision drivers (e.g., BBB permeability > immunogenicity for final ranking)",
  "Per-candidate seizure outcome prediction: estimated seizure reduction % for mild, moderate, and severe baseline epilepsy phenotypes integrating disease severity modifiers",
  "Mechanistic rescue hypothesis per candidate linking ASO knockdown to gene dosage-specific seizure pathophysiology (e.g., 80% knockdown achieves haploinsufficiency rescue; >95% knockdown required for truncation suppression)",
];

stage5_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Ranked candidate table (XLSX/JSON) with columns: Rank, ASO_ID, Sequence_5to3, Knockdown%, EP_Rescue_Probability, OffTarget_Risk, Immunogenicity_Risk, Final_Score, Confidence_Interval.", font: "Arial", size: 24 }),
  ],
}));

// ===== STAGE 6 =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Stage 6: Validation Experiment Design & Final Ranking", bold: true, font: "Arial", size: 28 })],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Purpose: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Design comprehensive experimental validation protocols for top-ranked ASO candidates, including in vitro knockdown assays, cellular immunogenicity testing, CNS penetration quantification, and mechanistic seizure rescue verification in disease-relevant models, with explicit success criteria and resource allocation guidance.", font: "Arial", size: 24 }),
  ],
}));

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Inputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage6_inputs = [
  "Top-10 ranked ASO candidates from Stage 5 with complete sequence, property, and prediction data",
  "Disease-relevant cellular and animal models: patient-derived iPSC neurons, primary cortical cultures, transgenic mouse lines for epilepsy targets",
  "Experimental protocols: qPCR/ddPCR for knockdown quantification, RNA-seq for off-target detection, whole-cell patch-clamp electrophysiology for functional rescue",
  "Assay feasibility parameters: cell line availability, timeframe constraints (8-12 weeks for mammalian PK), regulatory requirements for animal studies",
  "Success criteria definition: minimum knockdown thresholds (typically 60-80%), seizure phenotype rescue benchmarks, safety margin requirements",
];

stage6_inputs.forEach((input) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: input, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Tools & Databases Called:", bold: true, font: "Arial", size: 24 })],
}));

const stage6_tools = [
  "Benchling protocol repository and OpenWetWare for standardized mammalian cell culture and transfection protocols",
  "NIH ReagentBank and Addgene for validated reporter plasmids and CRISPR verification tools",
  "Genomics protocol databases (e.g., Nature Protocols, JoVE) for qPCR, RNA-seq library prep, patch-clamp electrophysiology optimized for neuronal recordings",
  "AnimalDB (NIH) for transgenic mouse availability, phenotype characterization, and pharmacokinetic parameters for selected disease models",
  "Statistical power calculation tools (G*Power, PASS) for determining sample size requirements for neurophysiology experiments",
  "Electronic laboratory notebook (ELN) systems for tracking ASO synthesis, dose verification, batch characterization (purity, endotoxin, sterility)",
];

stage6_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, font: "Arial", size: 24 })],
}));

const stage6_subprompts = [
  "Design in vitro knockdown validation assay: patient iPSC-derived neurons exposed to ASO (dose range: 10 nM - 10 µM, 24-72 h exposure) with qPCR quantification of target mRNA (normalized to GAPDH/ACTB); success criterion ≥60% knockdown at ≤1 µM dose",
  "Design 24-well high-content imaging assay to detect off-target effects: immunofluorescence staining of predicted off-target gene products (IF antibodies) + cell viability marker (Hoechst/LDH) with automated microscopy; success criterion: <20% viability reduction at therapeutic dose",
  "Plan acute brain slice electrophysiology protocol: whole-cell patch-clamp recordings from ASO-treated transgenic seizure model neurons measuring intrinsic excitability, action potential firing frequency, and inhibitory/excitatory synaptic balance; endpoint: seizure threshold elevation ≥30% vs. vehicle control",
  "Design mouse pharmacokinetic study: IV dose ASO (5-10 mg/kg), collect blood/CSF at timed intervals (2 h, 24 h, 72 h, 7 days, 14 days), quantify ASO concentration via LC-MS/MS; target: CSF concentration ≥50 nM sustained for ≥7 days at therapeutic dose",
  "Outline acute toxicity assessment: serum cytokine profiling (TNFα, IL-6, IL-1β, IFNβ) via multiplex assay post-ASO in primary mouse macrophages and dendritic cells; success criterion: cytokine induction <5-fold vs. vehicle control (LPS positive control shows >50-fold)",
];

stage6_subprompts.forEach((subprompt) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: subprompt, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [new TextRun({ text: "Expected Outputs:", bold: true, font: "Arial", size: 24 })],
}));

const stage6_outputs = [
  "Detailed experimental validation plan for top 3-5 ASO candidates: assay design, cell/animal models, sample sizes, inclusion/exclusion criteria, blinding/randomization strategy, success thresholds",
  "In vitro validation protocol: dose-response curves for knockdown (qPCR), cell viability profiling, off-target mRNA detection by RNA-seq (with 4-fold change cutoff for flagged off-targets)",
  "In vivo pharmacokinetics protocol: ASO synthesis quality control, pharmacokinetic sampling schedule, LC-MS/MS assay validation, brain penetration quantification target (CSF/plasma ratio)",
  "Functional rescue verification protocol: seizure phenotype readout (EEG monitoring duration, spike quantification, seizure frequency comparison vehicle vs. treatment), neurophysiology endpoints (patch-clamp measurements, interneuron firing properties)",
  "Immunogenicity testing protocol: cytokine profiling in primary innate immune cells, TLR activation assays (reporter cell lines), complement activation screening (C5a/MAC deposition)",
  "Go/No-Go decision matrix: ranked thresholds for knockdown efficiency, off-target tolerance, CNS bioavailability, immunogenicity, and seizure reduction; advance only candidates meeting ≥4/5 criteria",
];

stage6_outputs.forEach((output) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: output, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

children.push(new Paragraph({
  spacing: { after: 200, line: 360 },
  children: [
    new TextRun({ text: "Format: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Comprehensive experimental protocols (DOCX/PDF) with materials, methods, timelines, budgets, success criteria, and go/no-go decision trees for lead candidate advancement.", font: "Arial", size: 24 }),
  ],
}));

// ===== COMPREHENSIVE TOOLS & DATABASES SUMMARY =====
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "Comprehensive Tools & Databases Summary", bold: true, font: "Arial", size: 28 })],
}));

const comprehensive_tools = [
  "Quiver EP CRISPR Atlas: Authoritative variant-specific seizure rescue probability predictions for epilepsy genes (PCDH19, SCN1A, GABRA1, etc.)",
  "ClinVar & OMIM: Comprehensive disease-variant-gene associations with assertion criteria and clinical phenotype curations",
  "gnomAD: Population allele frequencies and gene constraint metrics (pLI, Z-scores) for loss-of-function intolerance assessment",
  "Ensembl & NCBI RefSeq: Complete human transcriptome reference with isoform annotations and BLAT genome alignment",
  "UniProt: Protein sequence, domain, and ortholog information for target identification and off-target prediction",
  "NCBI BLAST & Whole-Genome BLAT: Sequence homology search against transcriptome and genome for off-target identification",
  "Oligo Design Tool (ODT) & RNAstructure: Secondary structure prediction and mRNA accessibility calculation",
  "OligoCalc: Tm calculation via nearest-neighbor thermodynamics and GC% quantification",
  "TLR Motif Databases (DREME, FIMO): Pattern matching for TLR3/7/8 immunogenic sequences",
  "Ionis Chemistry & Pharmacokinetics Database: Reference ASO modification effects on stability, immunogenicity, and CNS penetration",
  "ChemAxon LogD/pKa Calculator: Physicochemical property predictions for BBB penetration modeling",
  "Molinspiration Property Predictor: Molecular weight, LogP, H-bond donors/acceptors for Lipinski-derived permeability assessment",
  "FDA PBPK Simulator: Whole-body pharmacokinetic modeling with CNS compartment integration",
  "GlialDB: Transcriptomic database for glial cell receptor expression and ASO uptake prediction",
  "Gene Therapeutics Knowledge Base: ASO target coverage and knockdown-to-phenotype relationship mining",
];

comprehensive_tools.forEach((tool) => {
  children.push(new Paragraph({
    spacing: { before: 0, after: 100, line: 240 },
    children: [new TextRun({ text: tool, font: "Arial", size: 24 })],
    bullet: { level: 0 },
  }));
});

// ===== FINAL DOCUMENT ASSEMBLY =====
const doc = new Document({
  sections: [{
    properties: {},
    children: children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("Pipeline_299.docx", buffer);
  console.log("Pipeline_299.docx created successfully");
});
