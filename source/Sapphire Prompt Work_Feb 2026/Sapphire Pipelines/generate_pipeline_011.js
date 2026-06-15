const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, convertInchesToTwip, UnorderedList, LevelFormat } = require('docx');
const fs = require('fs');

// Configuration
const numbering = {
  config: [
    {
      reference: 'bullets',
      levels: [
        {
          level: 0,
          format: LevelFormat.BULLET,
          text: '\u2022',
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
          text: '\u2022',
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

const styles = {
  default: {
    document: {
      run: { font: 'Arial', size: 24 }
    }
  },
  paragraphStyles: [
    {
      id: 'Heading1',
      name: 'Heading 1',
      basedOn: 'Normal',
      next: 'Normal',
      quickFormat: true,
      run: { size: 32, bold: true, font: 'Arial' },
      paragraph: { spacing: { before: 240, after: 240 } }
    },
    {
      id: 'Heading2',
      name: 'Heading 2',
      basedOn: 'Normal',
      next: 'Normal',
      quickFormat: true,
      run: { size: 28, bold: true, font: 'Arial' },
      paragraph: { spacing: { before: 200, after: 200 } }
    }
  ]
};

// Helper function to create a body paragraph
function createBodyParagraph(text, spacing = { after: 300, line: 360 }) {
  return new Paragraph({
    text: text,
    spacing: spacing
  });
}

// Helper function to create a paragraph with mixed formatting
function createMixedParagraph(parts, spacing = { after: 300, line: 360 }) {
  const runs = parts.map(part =>
    new TextRun({
      text: part.text,
      bold: part.bold || false,
      font: 'Arial',
      size: 24
    })
  );
  return new Paragraph({
    children: runs,
    spacing: spacing
  });
}

// Helper function to create bullet points
function createBulletList(items, level = 0) {
  return items.map(item =>
    new Paragraph({
      text: item,
      numbering: {
        reference: 'bullets',
        level: level
      }
    })
  );
}

// Helper function to create bold label with text
function createLabelParagraph(label, text, spacing = { after: 200, line: 360 }) {
  return new Paragraph({
    children: [
      new TextRun({
        text: label,
        bold: true,
        font: 'Arial',
        size: 24
      }),
      new TextRun({
        text: text,
        font: 'Arial',
        size: 24
      })
    ],
    spacing: spacing
  });
}

// Helper function to create standalone bold label
function createStandaloneBoldLabel(label, spacing = { after: 100 }) {
  return new Paragraph({
    children: [
      new TextRun({
        text: label,
        bold: true,
        font: 'Arial',
        size: 24
      })
    ],
    spacing: spacing
  });
}

// Build document
const doc = new Document({
  numbering: numbering,
  styles: styles,
  sections: [{
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
        text: 'Sapphire Pipeline Workflow',
        heading: HeadingLevel.HEADING_1
      }),

      // H2: Prompt
      new Paragraph({
        text: 'Prompt: "Do the TSC1 and TSC2 gene perturbations have close proximity?"',
        heading: HeadingLevel.HEADING_2
      }),

      // Body paragraph about pipeline definition
      new Paragraph({
        children: [
          new TextRun({
            text: 'This document defines the complete Sapphire pipeline — the sequential stages, tools called, external datasets used, inputs, outputs, and decision logic — required to deliver a valid, actionable answer to this prompt.',
            font: 'Arial',
            size: 24
          })
        ],
        spacing: { after: 300, line: 360 }
      }),

      // H2: Pipeline Overview
      new Paragraph({
        text: 'Pipeline Overview',
        heading: HeadingLevel.HEADING_2
      }),

      new Paragraph({
        children: [
          new TextRun({
            text: 'This pipeline evaluates whether TSC1 and TSC2 gene perturbations cluster closely in electrophysiological (EP) feature space, testing the hypothesis that genes in the same pathway (mTOR/TSC complex) produce convergent electrophysiological phenotypes. The analysis proceeds through six sequential stages: extraction of complete EP profiles, computation of pairwise distances and similarities, contextualization within the broader EP feature space, assessment of pathway-level convergence, biological interpretation of proximity patterns, and therapeutic implications.',
            font: 'Arial',
            size: 24
          })
        ],
        spacing: { after: 300, line: 360 }
      }),

      new Paragraph({
        children: [
          new TextRun({
            text: 'The question of proximity in EP feature space is critical for understanding whether TSC1 and TSC2 perturbations, despite being in the same cellular complex and pathway, produce similar or divergent electrophysiological consequences. Close proximity would suggest redundancy or convergent pathway logic; divergence would indicate specialized or context-dependent roles.',
            font: 'Arial',
            size: 24
          })
        ],
        spacing: { after: 300, line: 360 }
      }),

      // ============= STAGE 1 =============
      new Paragraph({
        text: 'Stage 1: TSC1 & TSC2 EP Profile Extraction',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'Extract complete EP signatures for both TSC1 and TSC2 perturbations from the Quiver atlas. Normalize feature vectors identically to ensure comparability.',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'Quiver CRISPR EP Atlas (curated gene perturbation database)',
        'TSC1 knockout or knockdown EP measurements (raw signals: voltage, current, spike frequency, etc.)',
        'TSC2 knockout or knockdown EP measurements (parallel experimental design)',
        'EP feature extraction parameters (window sizes, threshold definitions, normalization method)'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'Quiver CRISPR EP Atlas: Query and retrieve gene-specific EP profiles',
        'Quiver EP Feature Extraction Pipeline: Normalize raw signals into standardized feature vectors'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'What are the complete EP measurements for TSC1 knockout in [cell type]?',
        'What are the complete EP measurements for TSC2 knockout in [cell type]?',
        'How should EP features be normalized for cross-gene comparison?',
        'Are TSC1 and TSC2 measurements acquired under identical experimental conditions?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'Normalized EP feature vector for TSC1 (e.g., 50–200 features: rheobase, input resistance, spike amplitude, AHP, ISI, etc.)',
        'Normalized EP feature vector for TSC2 (same dimensionality as TSC1)',
        'Metadata: cell type, perturbation method, recording conditions, sample sizes',
        'Quality flags: data completeness, outlier status'
      ]),

      createLabelParagraph(
        'Format: ',
        'Structured arrays or DataFrames (Python: pandas.DataFrame or numpy.ndarray); JSON or HDF5 for interchange.',
        { after: 200, line: 360 }
      ),

      // ============= STAGE 2 =============
      new Paragraph({
        text: 'Stage 2: Pairwise Distance & Similarity Computation',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'Compute direct pairwise distance and similarity between TSC1 and TSC2 EP profiles using multiple metrics. Compare this pairwise distance against the background distribution of all gene-gene distances to assess statistical significance.',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'Normalized TSC1 EP feature vector (from Stage 1)',
        'Normalized TSC2 EP feature vector (from Stage 1)',
        'Complete EP feature matrix for all genes in Quiver (background distribution)',
        'Distance metric selection (Euclidean, cosine, Pearson, Spearman, Wasserstein)'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'Quiver EP Similarity Engine: Compute multi-metric pairwise similarities',
        'scipy.spatial.distance: Cosine, Euclidean, and other distance metrics',
        'scipy.stats: Pearson and Spearman correlations',
        'Statistical significance testing: permutation tests, z-scores, p-values'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'What is the cosine distance between TSC1 and TSC2 EP profiles?',
        'What is the Pearson correlation between TSC1 and TSC2 EP features?',
        'How does the TSC1–TSC2 distance compare to the distribution of all pairwise distances?',
        'Is the TSC1–TSC2 proximity statistically significant (p < 0.05)?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'Pairwise distance (multiple metrics): cosine, Euclidean, Pearson, Spearman',
        'Similarity score (inverse distance or correlation)',
        'Percentile rank of TSC1–TSC2 distance in background distribution (e.g., top 5%)',
        'P-value and z-score for statistical significance',
        'Comparative table: TSC1–TSC2 vs. nearest gene, vs. median gene-gene distance'
      ]),

      createLabelParagraph(
        'Format: ',
        'Tabular: CSV/TSV with distance metrics, p-values, ranks. Visualization: histogram of all pairwise distances with TSC1–TSC2 marked.',
        { after: 200, line: 360 }
      ),

      // ============= STAGE 3 =============
      new Paragraph({
        text: 'Stage 3: EP Feature Space Contextualization',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'Place TSC1 and TSC2 in the full EP feature space alongside all other gene perturbations. Assess whether they cluster together relative to the overall distribution using dimensionality reduction and clustering techniques.',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'Complete EP feature matrix for all genes (Quiver)',
        'TSC1 and TSC2 feature vectors (from Stage 1)',
        'Optional: gene metadata (pathway, protein class, cellular compartment)',
        'Parameters: PCA components, UMAP/t-SNE perplexity, k for k-NN, epsilon for DBSCAN'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'scikit-learn.decomposition.PCA: Principal Component Analysis',
        'umap-learn: UMAP dimensionality reduction',
        'scikit-learn.manifold.TSNE: t-SNE visualization',
        'scikit-learn.neighbors.NearestNeighbors: k-NN analysis',
        'scikit-learn.cluster.DBSCAN or hdbscan.HDBSCAN: Density-based clustering'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'In PCA space, are TSC1 and TSC2 clustered together or separated?',
        'In UMAP space, which genes are nearest neighbors to TSC1 and TSC2?',
        'Are TSC1 and TSC2 in the same DBSCAN cluster?',
        'What is the density of genes near TSC1/TSC2 compared to random points?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'PCA projection (2D or 3D): TSC1 and TSC2 positions',
        'UMAP projection: TSC1 and TSC2 with local neighborhood',
        't-SNE projection: TSC1 and TSC2 clustering context',
        'k-NN results: 10–50 nearest genes to each of TSC1 and TSC2',
        'DBSCAN cluster assignments: whether TSC1 and TSC2 share a cluster',
        'Local density estimates around TSC1 and TSC2'
      ]),

      createLabelParagraph(
        'Format: ',
        'High-resolution 2D/3D scatter plots with labeled axes, color-coded by cluster or pathway. CSV table of k-NN results.',
        { after: 200, line: 360 }
      ),

      // ============= STAGE 4 =============
      new Paragraph({
        text: 'Stage 4: Pathway-Level EP Convergence Analysis',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'Assess whether other mTOR pathway genes (MTOR, RHEB, DEPDC5, NPRL2, NPRL3) also show EP proximity to TSC1 and TSC2, testing the hypothesis of pathway-level convergence in EP phenotypes.',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'KEGG mTOR pathway definition (members: TSC1, TSC2, MTOR, RHEB, DEPDC5, NPRL2, NPRL3, etc.)',
        'Reactome pathway database (mTOR signaling)',
        'EP feature vectors for all mTOR pathway members (from Quiver)',
        'STRING protein interaction network'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'KEGG API or database: Query mTOR pathway member list',
        'Reactome: Cross-validate pathway membership',
        'Quiver EP Atlas: Multi-gene query for all mTOR members',
        'STRING: Protein interaction network and clustering'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'What are all members of the mTOR pathway in KEGG?',
        'Which mTOR members have EP data in Quiver?',
        'What are the pairwise EP distances among all mTOR pathway members?',
        'Do mTOR pathway members cluster together in EP space, or are there sub-clusters?',
        'Are TSC1 and TSC2 more similar to each other than to other mTOR members?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'List of mTOR pathway members and their EP data availability',
        'Pairwise distance matrix for all pathway members',
        'Within-pathway vs. between-pathway distance statistics',
        'Sub-cluster analysis: which pathway genes co-cluster?',
        'Pathway diagram annotated with EP distances and clustering'
      ]),

      createLabelParagraph(
        'Format: ',
        'Distance matrix (heatmap), network diagram showing EP distances as edge weights, summary table of pathway-level statistics.',
        { after: 200, line: 360 }
      ),

      // ============= STAGE 5 =============
      new Paragraph({
        text: 'Stage 5: Biological Interpretation & Mechanism',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'Interpret EP proximity (or divergence) between TSC1 and TSC2 in terms of shared vs. distinct biology. TSC1 and TSC2 form a catalytic complex — do their perturbation phenotypes reflect this physical and functional relationship?',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'TSC1–TSC2 EP distance and clustering results (from Stages 2–4)',
        'UniProt: TSC1 and TSC2 protein structure, domains, interaction motifs',
        'PubMed literature: TSC1, TSC2, mTOR pathway biology',
        'Quiver transcriptomic data: TSC1 and TSC2 knockout gene expression signatures',
        'Gene Ontology: Biological processes and molecular functions'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'UniProt: Protein sequences, domains, post-translational modifications',
        'PubMed / PubMed Central: Literature mining on TSC complex and EP phenotypes',
        'Quiver Transcriptomic Module: RNA-seq signatures for TSC1/TSC2 knockouts',
        'Gene Ontology: Enrichment analysis of shared vs. unique genes affected'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'Does the TSC1–TSC2 EP proximity match their physical complex structure?',
        'What is known in the literature about TSC1 vs. TSC2 specific roles?',
        'Do TSC1 and TSC2 knockouts produce similar transcriptomic changes?',
        'Are there known redundant or non-redundant functions between TSC1 and TSC2?',
        'Does EP proximity imply functional redundancy, or are there context-dependent differences?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'Biological interpretation: Do EP results align with complex structure and known biology?',
        'Summary of TSC1 vs. TSC2 unique vs. shared functions',
        'Transcriptomic comparison: Overlap in affected genes',
        'Literature summary: Key papers on TSC complex biology and EP phenotypes',
        'Hypothesis for any divergence: context, isoform-specific effects, tissue-dependent roles'
      ]),

      createLabelParagraph(
        'Format: ',
        'Narrative summary with supporting tables, literature citations, Venn diagrams for transcriptomic overlap.',
        { after: 200, line: 360 }
      ),

      // ============= STAGE 6 =============
      new Paragraph({
        text: 'Stage 6: Therapeutic Implications & Confidence Assessment',
        heading: HeadingLevel.HEADING_2
      }),

      createLabelParagraph(
        'Purpose: ',
        'If TSC1 and TSC2 are proximal in EP space, assess whether therapeutic strategies (antisense oligonucleotides, small molecules, biologics) targeting one could inform therapeutic approaches for the other. Quantify confidence in the overall conclusion.',
        { after: 200, line: 360 }
      ),

      createStandaloneBoldLabel('Inputs:', { after: 100 }),
      ...createBulletList([
        'TSC1–TSC2 proximity and statistical significance (from Stage 2)',
        'Pathway-level convergence results (Stage 4)',
        'Quiver Compound Atlas: Known compounds targeting TSC1, TSC2, or mTOR pathway',
        'DrugBank: Drug-gene interaction data',
        'ClinicalTrials.gov: Ongoing clinical trials for TSC-related conditions (TSC1/TSC2 mutations)',
        'Sapphire Confidence Scoring framework'
      ]),

      createStandaloneBoldLabel('Tools & Databases Called:', { after: 100 }),
      ...createBulletList([
        'Quiver Compound Atlas: Drug efficacy predictions for TSC1, TSC2, mTOR',
        'DrugBank: Drug target information and chemical structures',
        'ClinicalTrials.gov: Real-world therapeutic evidence',
        'Sapphire Confidence Scoring: Multi-factor scoring (statistical significance, effect size, biological coherence, clinical validation)'
      ]),

      createStandaloneBoldLabel('Exemplary Sub-Prompts:', { after: 100 }),
      ...createBulletList([
        'Are there known inhibitors or modulators of TSC1 or TSC2?',
        'If TSC1 is targeted therapeutically, are there predicted effects on TSC2 function or phenotype?',
        'What compounds target the mTOR pathway, and would they be effective for both TSC1 and TSC2 dysregulation?',
        'Are there clinical trials for TSC-related disorders, and how do they inform therapeutic strategy?',
        'What is the overall confidence level in the proximity conclusion, and how does it affect therapeutic generalization?'
      ]),

      createStandaloneBoldLabel('Expected Outputs:', { after: 100 }),
      ...createBulletList([
        'Therapeutic recommendation: Can a single drug strategy address both TSC1 and TSC2?',
        'Candidate drugs (top 3–5) with predicted efficacy for both targets',
        'Clinical evidence: Relevant TSC trials and patient outcome data',
        'Confidence score (0–100) for the proximity conclusion with confidence intervals',
        'Final answer statement: "TSC1 and TSC2 perturbations are [proximal/divergent] in EP space with [high/moderate/low] confidence."'
      ]),

      createLabelParagraph(
        'Format: ',
        'Summary table, confidence score card, therapeutic recommendation brief, supporting evidence grid.',
        { after: 200, line: 360 }
      ),

      // ============= TOOLS & DATABASES SUMMARY =============
      new Paragraph({
        text: 'Tools & Databases Summary',
        heading: HeadingLevel.HEADING_2
      }),

      ...createBulletList([
        'Quiver CRISPR EP Atlas: Curated database of gene perturbation electrophysiological measurements',
        'Quiver EP Feature Extraction Pipeline: Normalization and feature engineering for EP signals',
        'Quiver EP Similarity Engine: Multi-metric distance and similarity computation',
        'Quiver Transcriptomic Module: Gene expression data for perturbation contexts',
        'Quiver Compound Atlas: Compound efficacy and toxicity predictions',
        'scipy: Distance metrics, statistical tests, signal processing',
        'scikit-learn: PCA, UMAP, t-SNE, k-NN, DBSCAN clustering',
        'KEGG: Pathway definitions and member lists',
        'Reactome: Cross-validation of pathway membership',
        'STRING: Protein interaction networks',
        'UniProt: Protein sequences, domains, structures',
        'PubMed / PubMed Central: Literature mining and citations',
        'Gene Ontology: Biological function enrichment analysis',
        'DrugBank: Drug-gene interactions and chemical data',
        'ClinicalTrials.gov: Clinical trial information and outcomes',
        'Sapphire Confidence Scoring: Multi-factor confidence assessment framework'
      ])
    ]
  }]
});

// Write document to file
const filepath = '/sessions/youthful-vigilant-planck/mnt/Desktop/Sapphire Prompt Work_Feb 2026/Sapphire Pipelines/Pipeline_011_TSC1_TSC2_EP_Proximity.docx';
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(filepath, buffer);
  console.log(`Document created successfully at ${filepath}`);
});
