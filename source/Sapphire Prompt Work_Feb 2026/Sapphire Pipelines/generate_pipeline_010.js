const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');
const path = require('path');

// Configuration for numbering (bullets)
const numbering = {
  config: [
    {
      reference: "bullets",
      levels: [
        {
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: 720, hanging: 360 }
            }
          }
        },
        {
          level: 1,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: 1440, hanging: 360 }
            }
          }
        }
      ]
    }
  ]
};

// Styles configuration
const styles = {
  default: {
    document: {
      run: { font: "Arial", size: 24 }
    }
  },
  paragraphStyles: [
    {
      id: "Heading1",
      name: "Heading 1",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { size: 32, bold: true, font: "Arial" },
      paragraph: { spacing: { before: 240, after: 240 } }
    },
    {
      id: "Heading2",
      name: "Heading 2",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { size: 28, bold: true, font: "Arial" },
      paragraph: { spacing: { before: 200, after: 200 } }
    }
  ]
};

// Helper function to create bullet point
function createBullet(text) {
  return new Paragraph({
    text: text,
    bullet: {
      level: 0
    },
    spacing: { after: 100, line: 360 }
  });
}

// Helper function to create a paragraph with optional bold prefix
function createParagraph(boldText, normalText, spacingAfter = 200) {
  const runs = [];
  if (boldText) {
    runs.push(new TextRun({
      text: boldText,
      bold: true,
      font: "Arial",
      size: 24
    }));
  }
  if (normalText) {
    runs.push(new TextRun({
      text: normalText,
      font: "Arial",
      size: 24
    }));
  }
  return new Paragraph({
    children: runs,
    spacing: { after: spacingAfter, line: 360 }
  });
}

// Create document content
const sections = [
  // Title
  new Paragraph({
    text: "Sapphire Pipeline Workflow",
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 240, line: 360 }
  }),

  // Prompt heading
  new Paragraph({
    text: 'Prompt: "Which gene perturbations are most similar to TSC2 based on their EP profiles/signatures?"',
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  // Intro paragraph
  new Paragraph({
    children: [
      new TextRun({
        text: "This document defines the complete Sapphire pipeline — the sequential stages, tools called, external datasets used, inputs, outputs, and decision logic — required to deliver a valid, actionable answer to this prompt.",
        font: "Arial",
        size: 24
      })
    ],
    spacing: { after: 300, line: 360 }
  }),

  // Pipeline Overview heading
  new Paragraph({
    text: "Pipeline Overview",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "This pipeline identifies gene perturbations with electrophysiology (EP) profiles most similar to TSC2, leveraging Quiver's comprehensive CRISPR-based electrophysiology atlas. The workflow represents a core Quiver platform capability — cross-gene EP similarity search — enabling rapid discovery of genes with phenotypically similar cellular electrophysiological signatures.",
        font: "Arial",
        size: 24
      })
    ],
    spacing: { after: 300, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "The pipeline proceeds through six sequential stages: extracting TSC2's reference EP profile, constructing the multi-dimensional EP feature space, computing similarity metrics and rankings, enriching results with biological pathway context, assessing therapeutic implications, and providing confidence scoring with validation recommendations.",
        font: "Arial",
        size: 24
      })
    ],
    spacing: { after: 300, line: 360 }
  }),

  // ==================== STAGE 1 ====================
  new Paragraph({
    text: "Stage 1: TSC2 Reference EP Profile Extraction",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "Extract the complete electrophysiology signature for TSC2 perturbation from Quiver's CRISPR atlas. Normalize across all measured EP features to establish a reference profile for downstream similarity comparisons."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("TSC2 gene identifier (NCBI, Ensembl)"),
  createBullet("Raw electrophysiology recording data from Quiver CRISPR perturbation experiments"),
  createBullet("Cell type/culture conditions for TSC2 perturbation"),
  createBullet("Feature extraction templates and normalization parameters"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver CRISPR EP Atlas — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "retrieves complete EP recording dataset and metadata for TSC2 perturbation",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver EP Feature Extraction Pipeline — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "computes firing rate, burst frequency, amplitude, latency, waveform parameters",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Internal Normalization Algorithms — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "z-score normalization, batch effect correction, quantile normalization across features",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("What are the measured EP parameters for TSC2 CRISPR knockdown in neuronal cultures?"),
  createBullet("How do EP features vary across replicates and cell batches for TSC2 perturbation?"),
  createBullet("What is the optimal normalization strategy for cross-gene EP comparisons?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Normalized EP feature vector for TSC2 (e.g., [firing_rate, burst_freq, amplitude, ...])"),
  createBullet("Metadata: cell type, culture conditions, replicate count, confidence estimates"),
  createBullet("Quality metrics: signal-to-noise ratios, feature completeness, batch effect indicators"),

  createParagraph(
    "Format: ",
    "JSON with TSC2 EP vector, metadata tags, QC metrics. Stored in memory for Stage 2 input."
  ),

  // ==================== STAGE 2 ====================
  new Paragraph({
    text: "Stage 2: EP Feature Space Construction & Dimensionality Reduction",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "Build the multi-dimensional EP feature space across all gene perturbations in Quiver's atlas. Apply dimensionality reduction (PCA, UMAP) to visualize gene clusters and identify candidate similar genes before formal similarity scoring."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("TSC2 normalized EP vector (from Stage 1)"),
  createBullet("Complete Quiver EP Atlas: EP feature vectors for all gene perturbations"),
  createBullet("Feature metadata: feature names, units, biophysical interpretations"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver EP Atlas (full dataset) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "retrieves normalized EP vectors for all perturbed genes in the collection",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "scikit-learn (PCA) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "principal component analysis for variance decomposition and feature ranking",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "scikit-learn (UMAP) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "Uniform Manifold Approximation and Projection for 2D/3D visualization of gene-EP relationships",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "scipy (distance metrics) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "Euclidean, Manhattan, cosine distance calculations",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Which EP features explain the most variance across gene perturbations?"),
  createBullet("In UMAP space, which genes cluster closest to TSC2?"),
  createBullet("What are the principal axes of EP variation in the atlas?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("PCA variance explained by top K components"),
  createBullet("UMAP 2D/3D coordinates for all genes (for visualization)"),
  createBullet("Gene clusters and preliminary candidate similarity list (visual/heuristic)"),
  createBullet("Feature importance rankings for EP variation"),

  createParagraph(
    "Format: ",
    "Python dict/JSON with PCA components, UMAP coordinates, feature loadings. PNG visualization plots."
  ),

  // ==================== STAGE 3 ====================
  new Paragraph({
    text: "Stage 3: Similarity Metric Computation & Ranking",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "Compute pairwise similarity between TSC2 and all other gene perturbations using multiple distance/similarity metrics. Rank genes by composite similarity score to establish statistically robust candidate list."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("TSC2 normalized EP vector"),
  createBullet("All gene EP vectors from Quiver atlas"),
  createBullet("Distance metric parameters and similarity weighting scheme"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver EP Similarity Engine — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "optimized pairwise similarity computation across large EP datasets",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "scipy.spatial (distance) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "cosine_distances, euclidean_distances, correlation metrics",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Custom Weighted Similarity Scoring — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "composite score: w_cosine * cosine_sim + w_pearson * pearson_corr + w_euclidean * (1 / (1 + euclidean_dist))",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("What are the top 20 genes by cosine similarity to TSC2 EP profile?"),
  createBullet("How does Pearson correlation vs. Euclidean distance rank EP-similar genes?"),
  createBullet("What is the composite similarity score for candidate genes?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Ranked gene list with similarity scores (sorted by composite score, descending)"),
  createBullet("Per-gene metrics: cosine, Pearson, Euclidean, composite score"),
  createBullet("P-values/Z-scores from permutation or null distribution testing"),
  createBullet("Confidence intervals for top candidates"),

  createParagraph(
    "Format: ",
    "CSV/TSV with columns: gene_id | gene_name | cosine_sim | pearson_corr | euclidean_dist | composite_score | p_value | q_value"
  ),

  // ==================== STAGE 4 ====================
  new Paragraph({
    text: "Stage 4: Biological Pathway & Disease Context Enrichment",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "For top-ranked similar genes, assess shared biological pathways (e.g., mTOR signaling in TSC2), disease associations, and protein-protein interactions. Contextualize EP similarity in known biology to increase confidence and interpretability."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Top-ranked gene list (e.g., top 50 from Stage 3)"),
  createBullet("TSC2 biological context: known pathways, disease associations"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "KEGG (Kyoto Encyclopedia of Genes and Genomes) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "pathway membership, mTOR/TSC2 pathway annotations",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Reactome — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "curated pathway database for human reactions and complexes",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "STRING (Search Tool for the Retrieval of Interacting Genes/Proteins) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "protein-protein interaction networks",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Gene Ontology (GO) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "functional annotations: biological process, molecular function, cellular component",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "DisGeNET — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "gene-disease associations, disease relevance scores",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "OMIM (Online Mendelian Inheritance in Man) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "disease phenotypes and genetic associations",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Which top-ranked genes share mTOR/TSC2 pathway membership with TSC2?"),
  createBullet("Are tuberous sclerosis complex (TSC) disease genes enriched in EP-similar gene set?"),
  createBullet("Do top candidates interact directly or indirectly with TSC2 protein?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Pathway enrichment summary for similar gene set"),
  createBullet("Per-gene biological context: pathways, GO terms, PPI neighbors"),
  createBullet("Disease association scores and relevance to TSC phenotypes"),
  createBullet("Confidence boost flags: genes with strong biological linkage to TSC2"),

  createParagraph(
    "Format: ",
    "JSON/TSV with columns: gene_id | pathways | go_terms | ppi_neighbors | disease_assoc | confidence_boost"
  ),

  // ==================== STAGE 5 ====================
  new Paragraph({
    text: "Stage 5: Therapeutic Implication Assessment",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "Evaluate whether genes with similar EP signatures to TSC2 suggest shared therapeutic vulnerabilities, drug repurposing opportunities, or common modality strategies (ASO, small molecule, PROTAC). Link EP phenotypes to therapeutic actionability."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Ranked gene list with biological enrichment (from Stage 4)"),
  createBullet("TSC2 drug/compound sensitivity data"),
  createBullet("Therapeutic modality landscape for similar genes"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "DrugBank — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "drug targets, indication, clinical status for genes in candidate set",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "ChEMBL — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "bioassay data, compounds targeting similar gene set",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "ClinicalTrials.gov — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "active or completed trials targeting candidate genes or TSC-related indications",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver Compound Atlas — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "EP response profiles for compounds targeting similar genes",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Are TSC pathway inhibitors or mTOR inhibitors efficacious on EP-similar gene perturbations?"),
  createBullet("What compounds in ChEMBL target genes with similar EP profiles to TSC2?"),
  createBullet("Are any clinical trials active for therapeutic targeting of similar gene set?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Therapeutic modality summary: small molecule, ASO, PROTAC, antibody, etc."),
  createBullet("Druggability assessment per candidate gene"),
  createBullet("Drug repurposing opportunities: known compounds with potential off-target activity"),
  createBullet("Clinical trial landscape for TSC and related neurological indications"),
  createBullet("EP sensitivity data for lead compounds"),

  createParagraph(
    "Format: ",
    "JSON with columns: gene_id | modalities | druggability_score | repurposing_compounds | clinical_trials | compound_ep_response"
  ),

  // ==================== STAGE 6 ====================
  new Paragraph({
    text: "Stage 6: Confidence Scoring & Validation Recommendations",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createParagraph(
    "Purpose: ",
    "Assign confidence levels to similarity rankings, integrate multiple evidence types (EP, pathway, disease, therapeutic), and recommend orthogonal validation experiments to confirm true EP similarity and biological relevance."
  ),

  new Paragraph({
    text: "Inputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Ranked gene list with all enrichment layers (Stages 3–5)"),
  createBullet("Statistical test results and p-values"),
  createBullet("Cross-validation or hold-out test set performance metrics"),

  new Paragraph({
    text: "Tools & Databases Called:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Quiver Confidence Scoring — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "integrated confidence metric: ep_similarity + pathway_evidence + disease_evidence + druggability",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "scipy.stats (permutation tests) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "null distribution of similarity scores, empirical p-values",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    children: [
      new TextRun({
        text: "Statsmodels (FDR correction) — ",
        bold: true,
        font: "Arial",
        size: 24
      }),
      new TextRun({
        text: "multiple testing correction (Benjamini-Hochberg), adjusted q-values",
        font: "Arial",
        size: 24
      })
    ],
    bullet: { level: 0 },
    spacing: { after: 100, line: 360 }
  }),

  new Paragraph({
    text: "Exemplary Sub-Prompts:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("What is the confidence score for each top-ranked gene?"),
  createBullet("Which genes rank in the high-confidence tier (q < 0.05)?"),
  createBullet("What independent experiments would validate EP similarity?"),

  new Paragraph({
    text: "Expected Outputs:",
    bold: true,
    spacing: { after: 100, line: 360 }
  }),

  createBullet("Confidence-tiered ranking: high (q < 0.05), medium (0.05 < q < 0.20), exploratory (q > 0.20)"),
  createBullet("Composite confidence score per gene (0–100 scale)"),
  createBullet("Recommended validation experiments: patch-clamp, multi-electrode array (MEA), calcium imaging"),
  createBullet("Validation protocol suggestions: cell types, measurement conditions, positive/negative controls"),

  createParagraph(
    "Format: ",
    "JSON/TSV: gene_id | composite_confidence | confidence_tier | validation_priority | experiment_recommendations"
  ),

  // ==================== TOOLS & DATABASES SUMMARY ====================
  new Paragraph({
    text: "Tools & Databases Summary",
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 200, line: 360 }
  }),

  createBullet("Quiver CRISPR EP Atlas — comprehensive CRISPR perturbation electrophysiology data"),
  createBullet("Quiver EP Feature Extraction Pipeline — automated EP feature computation"),
  createBullet("Quiver EP Similarity Engine — optimized pairwise similarity computation"),
  createBullet("Quiver Confidence Scoring — integrated multi-evidence confidence metric"),
  createBullet("Quiver Compound Atlas — EP response profiles for therapeutic compounds"),
  createBullet("scikit-learn (PCA, UMAP) — dimensionality reduction and visualization"),
  createBullet("scipy (spatial distance, stats) — distance metrics and permutation testing"),
  createBullet("KEGG — pathway annotations and mTOR/TSC2 signaling context"),
  createBullet("Reactome — curated pathway database"),
  createBullet("STRING — protein-protein interaction networks"),
  createBullet("Gene Ontology (GO) — functional annotations"),
  createBullet("DisGeNET — gene-disease associations"),
  createBullet("OMIM — human disease genetics"),
  createBullet("DrugBank — drug targets and clinical information"),
  createBullet("ChEMBL — bioassay data and small molecule compounds"),
  createBullet("ClinicalTrials.gov — clinical trial registry"),
  createBullet("Statsmodels — statistical testing and FDR correction")
];

// Create the document
const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          margins: {
            top: 1440,
            right: 1440,
            bottom: 1440,
            left: 1440
          }
        }
      },
      children: sections
    }
  ],
  numbering: numbering,
  styles: styles
});

// Write the document
const outputPath = '/sessions/youthful-vigilant-planck/mnt/Desktop/Sapphire Prompt Work_Feb 2026/Sapphire Pipelines/Pipeline_010_Similar_Gene_Perturbations_EP_Profiles.docx';

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Document created successfully: ${outputPath}`);
});
