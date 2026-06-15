const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat, PageMarginOptions, convertInchesToTwip } = require('docx');
const fs = require('fs');

const doc = new Document({
  numbering: {
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
    ],
    abstract: [
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
  },
  styles: {
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
  },
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
      children: [
        // H1: Sapphire Pipeline Workflow
        new Paragraph({
          style: "Heading1",
          children: [
            new TextRun({
              text: "Sapphire Pipeline Workflow",
              bold: true,
              size: 32,
              font: "Arial"
            })
          ]
        }),

        // H2: Prompt
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Prompt: \"Which gene perturbations are anti-podal to TSC1/TSC2 based on their EP profiles/signatures?\"",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        // Body paragraph about the document
        new Paragraph({
          spacing: { after: 300, line: 360 },
          children: [
            new TextRun({
              text: "This document defines the complete Sapphire pipeline — the sequential stages, tools called, external datasets used, inputs, outputs, and decision logic — required to deliver a valid, actionable answer to this prompt.",
              size: 24,
              font: "Arial"
            })
          ]
        }),

        // H2: Pipeline Overview
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Pipeline Overview",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({
              text: "This pipeline identifies gene perturbations whose EP (Expression/Perturbation) signatures are maximally anti-correlated or inversely similar to TSC1/TSC2 reference profiles. Anti-podal genes represent functionally opposing biology — genes whose loss or gain produces phenotypes opposite to TSC1/TSC2 loss. These genes are candidates for counter-regulatory therapeutic intervention in TSC diseases.",
              size: 24,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 300, line: 360 },
          children: [
            new TextRun({
              text: "The pipeline progresses through six sequential stages: (1) extracting the TSC1/TSC2 reference EP profile, (2) computing anti-correlation metrics across all genes, (3) visualizing anti-podal relationships in feature space, (4) annotating biological pathways of anti-podal genes, (5) evaluating therapeutic target potential, and (6) designing validation strategies with confidence assessment.",
              size: 24,
              font: "Arial"
            })
          ]
        }),

        // ===== STAGE 1 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 1: TSC1/TSC2 Reference EP Profile Extraction",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Extract, normalize, and combine TSC1 and TSC2 individual EP signatures into a unified reference vector that defines the TSC1/TSC2 EP phenotype against which all other genes will be compared for anti-podal similarity.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quiver CRISPR EP Atlas database with TSC1 and TSC2 perturbation data", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Raw EP signatures (gene expression changes, pathway activation profiles, phenotypic readouts)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Metadata: cell type, perturbation conditions, timepoints, batch information", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Quiver CRISPR EP Atlas: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Query and retrieve TSC1/TSC2 perturbation profiles across conditions", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Quiver EP Feature Extraction Pipeline: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Normalize, batch-correct, and standardize EP signatures to comparable feature vectors", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "scikit-learn / pandas: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Statistical summarization and combination of multi-condition profiles", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"What are the complete EP signatures for TSC1 and TSC2 knockout in the Quiver Atlas?\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Normalize and average TSC1 and TSC2 signatures across multiple cell types and timepoints.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Generate a composite TSC1/TSC2 reference vector with confidence intervals.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Normalized TSC1/TSC2 composite EP signature vector (numeric array, ~1,000–10,000 features)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Feature metadata (gene names, pathway associations, functional annotations)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Batch correction and normalization parameters for reproducibility", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quality control metrics (variance explained, effect size, statistical power)", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "HDF5, JSON, or CSV with tabular format (rows = features, columns = TSC1/TSC2 composite scores). Include metadata JSON document with normalization parameters and QC metrics.", size: 24, font: "Arial" })
          ]
        }),

        // ===== STAGE 2 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 2: Anti-Correlation & Inverse Similarity Computation",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Compute multiple inverse similarity metrics between every gene's EP signature and the TSC1/TSC2 reference vector. Rank all genes by anti-podal score, identifying those whose perturbation produces opposite phenotypes. Use statistical significance testing to filter spurious hits.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "TSC1/TSC2 composite reference vector from Stage 1", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Complete Quiver CRISPR EP Atlas (all gene perturbation signatures across all conditions)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Statistical parameters: significance threshold (p < 0.05), effect size cutoffs", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Quiver EP Similarity Engine (inverse mode): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Compute negative Pearson correlation, anti-cosine similarity, and anti-Euclidean distance metrics", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "scipy / numpy: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Calculate correlation coefficients, cosine similarity, and distance metrics; perform rank aggregation", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Statistical Testing (scipy.stats): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Compute p-values, multiple testing correction (FDR), generate confidence intervals", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Compute the negative Pearson correlation between TSC1/TSC2 and all genes in the EP Atlas.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Rank genes by anti-cosine similarity (inverse similarity) to the TSC1/TSC2 signature.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Apply Benjamini-Hochberg correction and filter anti-podal genes at FDR < 0.05.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Generate a composite anti-podal score aggregating Pearson, cosine, and Euclidean distance ranks.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Ranked list of all genes with anti-podal scores (Pearson, cosine, Euclidean, composite)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "P-values and FDR-adjusted significance levels for each anti-podal gene pair", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Top 100–500 candidate anti-podal genes filtered at FDR < 0.05", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Confidence intervals and effect size estimates per gene", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "CSV/TSV table with columns: Gene, Pearson_Correlation, Cosine_Similarity, Euclidean_Distance, Composite_Anti_Podal_Score, P_Value, FDR_Q_Value, Effect_Size, Confidence_Interval_95pct.", size: 24, font: "Arial" })
          ]
        }),

        // ===== STAGE 3 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 3: EP Feature Space Visualization & Anti-Podal Mapping",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Visualize TSC1/TSC2 and top anti-podal genes in reduced dimensionality EP feature space. Assess whether anti-podal genes cluster together (coherent opposing pathway) or scatter (diverse mechanisms). Identify functional gene modules and co-regulation patterns.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "TSC1/TSC2 reference vector and ranked anti-podal gene list from Stage 2", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Complete EP signatures for top ~200 anti-podal candidates and control genes", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Gene functional annotations and pathway membership data", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "PCA (scikit-learn): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Reduce high-dimensional EP signatures to 2–3 principal components", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "UMAP / t-SNE (umap-learn, scikit-learn): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Non-linear dimensionality reduction preserving local and global structure", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "K-means clustering (scikit-learn): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Identify and group anti-podal genes by similarity, determine coherent functional modules", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "matplotlib / Plotly / D3.js: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Interactive and static visualization; highlight TSC1/TSC2 and top hits", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Project TSC1/TSC2 and top 100 anti-podal genes into PCA space and visualize.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Create UMAP plots showing anti-podal gene clustering and functional neighborhoods.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Apply k-means to partition anti-podal genes into 3–5 functional modules.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Generate an interactive D3.js visualization with gene names, anti-podal scores, and hover annotations.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "PCA scatter plots (PC1 vs PC2, PC1 vs PC3) with TSC1/TSC2 and top anti-podal genes highlighted", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "UMAP and t-SNE embeddings showing anti-podal gene landscape and clustering", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "K-means cluster assignments with cluster-specific functional enrichment summaries", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Interactive HTML/D3.js visualization with gene metadata and anti-podal score color-coding", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "High-resolution PNG/PDF plots (300 dpi) and interactive HTML5 visualizations. CSV files with PCA/UMAP coordinates and cluster assignments.", size: 24, font: "Arial" })
          ]
        }),

        // ===== STAGE 4 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 4: Pathway & Functional Annotation of Anti-Podal Genes",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Determine the biological pathways and functions of anti-podal genes. Test whether they represent known counter-regulatory mechanisms to mTOR/TSC signaling (e.g., AMPK activation, autophagy, growth inhibition, metabolic suppression). Annotate disease associations and mechanistic insights.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Top 100–500 anti-podal genes from Stage 2 with anti-podal scores", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Gene annotation databases: NCBI Gene, Entrez, Ensembl", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Prior knowledge of TSC1/TSC2 biology and mTOR signaling pathway", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "KEGG (Kyoto Encyclopedia of Genes and Genomes): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Pathway mapping, identify anti-podal genes in mTOR, autophagy, AMPK pathways", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Reactome: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Map genes to curated biological pathways and reactions", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "STRING (Search Tool for the Retrieval of Interacting Genes): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Protein–protein interaction networks; identify functional neighborhoods", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Gene Ontology (GO) Enrichment (gseapy, WebGestalt): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Identify overrepresented biological processes, molecular functions, cellular components", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "DisGeNET: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Retrieve disease-gene associations and phenotypes; assess therapeutic relevance", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Map top 100 anti-podal genes to KEGG pathways; identify enrichment in mTOR-opposing pathways (AMPK, autophagy).\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Perform GO enrichment analysis on anti-podal genes; identify overrepresented biological processes.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Extract protein–protein interaction networks from STRING for anti-podal genes and TSC1/TSC2.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Query DisGeNET for disease associations and phenotypes linked to anti-podal genes.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Pathway annotation table: gene, anti-podal score, KEGG pathway(s), Reactome pathway(s), GO terms, STRING interactions", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Enrichment analysis results: overrepresented pathways, processes, and gene ontology categories with p-values and FDR", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Protein–protein interaction networks highlighting TSC1/TSC2, anti-podal genes, and functional neighbors", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Disease association report: phenotypes, known disorders, and translational relevance", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Comprehensive CSV/TSV annotation table; pathway network diagrams (PDF/PNG); enrichment report (PDF or HTML with statistical tables).", size: 24, font: "Arial" })
          ]
        }),

        // ===== STAGE 5 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 5: Therapeutic Target Evaluation",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Assess whether anti-podal genes or their pathways represent druggable therapeutic targets for TSC disease management. Determine if activating/inhibiting anti-podal genes could rescue TSC phenotypes. Identify existing and potential drugs, clinical trials, and translational pathways.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Anti-podal gene list with functional annotations from Stage 4", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "TSC1/TSC2 phenotypic readouts and disease manifestations (growth, metabolism, autophagy, tumor formation)", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Published mechanistic and clinical literature on TSC and anti-podal gene function", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "DrugBank: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Identify approved and experimental drugs targeting anti-podal genes or their pathway products", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "ChEMBL: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Retrieve bioactive compounds and molecular target data; assess inhibitor/activator availability", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Quiver Compound Atlas: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Screen compound perturbations against anti-podal genes; identify phenotype-reversing molecules", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "ClinicalTrials.gov: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Search for ongoing and completed clinical trials in TSC, identify relevant therapeutic strategies", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "PubMed: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Curate and rank literature on anti-podal gene biology, TSC phenotype rescue, and therapeutic potential", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Search DrugBank for FDA-approved drugs targeting top 20 anti-podal genes.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Query Quiver Compound Atlas: do compounds that activate AMPK-pathway genes reverse TSC1 knockout phenotypes?\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Search ClinicalTrials.gov for TSC-focused trials; identify approved drugs that target anti-podal pathways.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Retrieve PubMed citations describing TSC phenotype rescue via anti-podal gene pathway activation.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Druggability assessment table: anti-podal gene, drug targets, approved drugs, clinical trial status, evidence level", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Therapeutic hypothesis report: TSC phenotype, hypothesized rescue mechanism, evidence, confidence score", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Compound screen results: compounds targeting anti-podal genes, effect on TSC phenotypes, potency/selectivity", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Literature summary: ranked publications describing anti-podal gene biology and TSC relevance", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Comprehensive therapeutic target report (PDF or HTML) with druggability table, compound screens, clinical trial summary, and ranked literature references with DOI/PubMed links.", size: 24, font: "Arial" })
          ]
        }),

        // ===== STAGE 6 =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Stage 6: Validation Strategy & Confidence Assessment",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Purpose: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Design experimental validation strategies to confirm anti-podal relationships in vitro and in vivo. Assign quantitative confidence scores to each anti-podal candidate based on EP statistical strength, functional coherence, druggability, and literature support. Prioritize candidates for follow-up studies.", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Inputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Complete anti-podal analysis from Stages 1–5: rankings, pathways, therapeutic targets", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Statistical confidence metrics: p-values, effect sizes, confidence intervals from Stage 2", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Expertise/prior knowledge: Sapphire team specifications for experimental design and validation protocols", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Tools & Databases Called:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Quiver EP Validation Protocols: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Standard perturbation, phenotyping, and rescue assays; multi-condition, multi-timepoint experiments", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Sapphire Confidence Scoring System: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Weighted integration of EP statistics, functional consistency, druggability, literature support, and feasibility", size: 24, font: "Arial" })
          ]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [
            new TextRun({ text: "Combinatorial Perturbation Experiments (CRISPRoff, CRISPRon, compound combinations): ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Co-perturb TSC1/TSC2 with anti-podal genes to test phenotypic rescue", size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Exemplary Sub-Prompts:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Design a combinatorial perturbation experiment to validate that knocking out anti-podal gene X rescues TSC1/TSC2 loss phenotypes.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Assign confidence scores (0–100) to top 20 anti-podal genes using Sapphire Confidence Scoring; integrate EP statistics, pathway coherence, druggability, and literature evidence.\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Rank anti-podal candidates by clinical translational potential (approved drug availability, trial status, safety profile).\"", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "\"Propose in vivo validation studies: animal models, phenotypic readouts, timelines for each priority candidate.\"", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { before: 0, after: 100, line: 360 },
          children: [
            new TextRun({ text: "Expected Outputs:", bold: true, size: 24, font: "Arial" })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Confidence-ranked anti-podal candidate list with scores (0–100 scale); scoring breakdown", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Validation protocol document: combinatorial perturbation designs, assay endpoints, cell types, timepoints, replicates", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "In vivo validation roadmap: animal models, phenotypic readouts, projected timelines, resource requirements", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Executive summary: top 5–10 priority anti-podal candidates with rationale, validation approach, and confidence level", size: 24, font: "Arial" })]
        }),

        new Paragraph({
          spacing: { after: 200, line: 360 },
          children: [
            new TextRun({ text: "Format: ", bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: "Multi-section validation report (PDF/HTML): confidence scoring methodology, ranked candidate table, detailed protocols, timeline projections, and executive summary with figures.", size: 24, font: "Arial" })
          ]
        }),

        // ===== TOOLS & DATABASES SUMMARY =====
        new Paragraph({
          style: "Heading2",
          children: [
            new TextRun({
              text: "Tools & Databases Summary",
              bold: true,
              size: 28,
              font: "Arial"
            })
          ]
        }),

        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quiver CRISPR EP Atlas — Comprehensive gene perturbation profiles and phenotypic readouts", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quiver EP Feature Extraction Pipeline — Normalization, batch correction, feature engineering for EP signatures", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quiver EP Similarity Engine — Compute inverse similarity metrics (Pearson, cosine, Euclidean) with statistical testing", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "scipy / numpy — Scientific computing, statistical analysis, numerical operations", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "scikit-learn — Machine learning: PCA, k-means clustering, dimensionality reduction", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "UMAP / t-SNE — Non-linear dimensionality reduction and visualization", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "matplotlib / Plotly / D3.js — Data visualization and interactive graphics", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "KEGG (Kyoto Encyclopedia of Genes and Genomes) — Pathway and genome annotations", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Reactome — Curated biological pathway database", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "STRING — Protein–protein interaction networks", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Gene Ontology (GO) — Gene annotation and functional enrichment", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "DisGeNET — Disease-gene association database", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "DrugBank — Drug–target interactions and FDA approvals", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "ChEMBL — Bioactive compounds and molecular target data", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Quiver Compound Atlas — Phenotypic effects of chemical perturbations", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "ClinicalTrials.gov — Clinical trial database and therapeutic information", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "PubMed — Literature indexing and citation retrieval", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 100, line: 360 },
          children: [new TextRun({ text: "Sapphire Confidence Scoring System — Integrated ranking framework for candidate prioritization", size: 24, font: "Arial" })]
        }),
        new Paragraph({
          numbering: { reference: "bullets", level: 0 },
          spacing: { after: 300, line: 360 },
          children: [new TextRun({ text: "Quiver EP Validation Protocols — Experimental assays and combinatorial perturbation designs", size: 24, font: "Arial" })]
        })
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/sessions/youthful-vigilant-planck/mnt/Desktop/Sapphire Prompt Work_Feb 2026/Sapphire Pipelines/Pipeline_012_Antipodal_Gene_Perturbations_EP.docx', buffer);
  console.log("Document created successfully!");
});
