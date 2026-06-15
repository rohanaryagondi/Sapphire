# Sapphire 3-Layer Integration Map

Re-cut of the **tool/data-source frequency analysis** (across 299 Sapphire pipelines) into James'
three-layer data vision from the 2026-06-11 meeting. Each external source is placed in the layer it
*serves*, with its pipeline-frequency count, priority tier, and the capability areas it feeds.

> Frequency source: `Sapphire_Tool_Frequency_Analysis.png` (Sapphire corpus) and
> `Common_Nodes_External_Data_Source_Frequency_v2.png` (Angelini corpus).
> Tiers from the chart: **Tier 1 = referenced in 30+ pipelines, Tier 2 = 15-29, Tier 3 = <15.**

---

## The three layers (James' framing)

> "There's our unique data; there's data that adds **context** to our hypotheses [a target may be
> great for pain but cause cancer - our data can't know that]; and there's data that adds
> **predictivity** and better **sorting** of our hypotheses [the same target shows up in a second,
> independent assay -> re-rank it from #7 to #1]."

| Layer | What it does | Why it matters |
|---|---|---|
| **Internal** | Quiver's unique functional data | The moat - novel target signals nobody else has |
| **Context** | External data Quiver *cannot* know | Gates go/no-go (safety, prevalence, competition) |
| **Predictivity** | Independent corroboration | Re-ranks / boosts hits (cross-assay agreement) |
| **Reference & compute** | Identifiers, structures, libraries, algorithms | Plumbing every layer depends on |

---

## Layer 1 - INTERNAL (the moat)

| Source | Freq | Tier | Serves | Note |
|---|---|---|---|---|
| Quiver EP-CRISPR Atlas | 104 | 1 | CAP-01,02,03,05,09 | The anchor - top source by 2x. Functional EP signatures + CRISPR perturbations. |
| Sapphire Embedding Engine | 9 | 3 | CAP-01,02 | Native latent space; unifies modalities. |
| GenomicsDB | 27 | 2 | CAP-02,06 | Internal genomics store (confirm scope vs external). |

**Do not** feed functional traces into any external model - that modality is V1-T's, permanently.

---

## Layer 2 - CONTEXT (things Quiver can't know -> go/no-go gating)

| Source | Freq | Tier | Serves | Why it's context |
|---|---|---|---|---|
| ClinVar | 42 | 1 | CAP-06,08,11 | Pathogenicity of variants - clinical truth Quiver data lacks. |
| OMIM | 38 | 1 | CAP-11 | Gene-disease inheritance / syndrome mapping. |
| GTEx | 45 | 1 | CAP-07,08 | Tissue expression baseline -> off-target / safety context. |
| DisGeNET | 35 | 1 | CAP-06,11 | Gene-disease association compendium. |
| HPO | 29 | 2 | CAP-11 | Phenotype ontology -> patient/clinical framing. |
| TCGA | 27 | 2 | CAP-08 | Cancer context - the literal "does this target cause cancer" check. |
| Allen Brain Atlas | 8 | 3 | CAP-07,10 | Regional brain expression -> CNS exposure/safety. |
| gnomAD | 11 | 3 | CAP-08,11 | Population constraint / tolerability of LoF. |
| ClinicalTrials.gov | (pipelines)* | - | CAP-13 | Active competitive programs by phase. |
| Cortellis | 7 | 3 | CAP-13 | Competitive & regulatory intelligence. |
| Open Targets | 7 | 3 | CAP-02,06,13 | Aggregated target-disease evidence (also boosting). |

\* ClinicalTrials.gov / GlobalData / IQVIA appear heavily in the commercial pipelines (143-154) but
below the global Tier-1 cut; they are the core CAP-13/CAP-14 context feeds.

---

## Layer 3 - PREDICTIVITY (independent corroboration -> re-rank / boost)

| Source | Freq | Tier | Serves | How it boosts |
|---|---|---|---|---|
| STRING | 45 | 1 | CAP-09,12 | PPI network - second-assay corroboration of a hit's relevance. |
| Reactome | 39 | 1 | CAP-05,09,12 | Pathway membership -> mechanistic agreement. |
| BioGRID | 34 | 1 | CAP-09,12 | Curated interactions - independent of EP signal. |
| LINCS L1000 | 29 | 2 | CAP-03,05 | Transcriptional perturbation signatures - cross-modal match. |
| Connectivity Map (CMap) | 27 | 2 | CAP-03,05 | Drug/gene signature similarity -> antipodal corroboration. |
| Expression Atlas | 27 | 2 | CAP-10 | Expression corroboration across studies. |
| KEGG | 10 | 3 | CAP-05,12 | Pathway structure (reconstruction tests). |
| GWAS Catalog | 7 | 3 | CAP-06 | Human-genetic support - the strongest boosting signal. |

**This is the layer James cares most about strategically** - it's how an independent hit ("appeared
in someone's academic screen, no one cared") re-ranks a Quiver prediction from #7 to #1.

---

## Layer 4 - REFERENCE & COMPUTE (plumbing under every layer)

| Source | Freq | Tier | Serves | Role |
|---|---|---|---|---|
| DrugBank | 55 | 1 | CAP-03,08,13 | Drug reference (targets, approvals, interactions). |
| UniProt | 45 | 1 | CAP-01,03 | Canonical protein reference. |
| ChEMBL | 17 | 2 | CAP-03 | Bioactivity database for DTI. |
| PDB / RCSB | 13 | 3 | CAP-03 | Structures (Boltz-2 / docking input). |
| PubChem | 11 | 3 | CAP-03 | Compound identifiers / SMILES. |
| PubMed / MEDLINE | 11 | 3 | CAP-13,15 | Literature retrieval (RAG). |
| UCSC Genome Browser | 11 | 3 | CAP-04,06 | Genomic coordinates. |
| RNAfold / ViennaRNA | 10 | 3 | CAP-04 | ASO secondary-structure / accessibility. |
| NUPACK | 9 | 3 | CAP-04 | Nucleic-acid thermodynamics for ASO design. |
| RDKit | 9 | 3 | CAP-03,07 | Cheminformatics (fingerprints beat MAMMAL embeddings - Q-Mammal). |
| BLAST / BLAT | 8 | 3 | CAP-04,06 | Sequence alignment / off-target. |
| Scanpy / Seurat | 8 | 3 | CAP-10 | scRNA-seq analysis. |
| FAISS / Annoy | 7 | 3 | CAP-01,02 | Vector similarity (Sapphire retrieval). |

---

## Build priority (what to integrate first)

1. **Tier-1 Context + Predictivity into the Neo4j knowledge graph** - ClinVar, OMIM, GTEx, DisGeNET,
   STRING, Reactome, BioGRID. Highest pipeline frequency *and* they directly enable the boosting/gating
   James wants. The Sapphire v3 graph (1.8M nodes / 17.9M edges) already exists as the substrate.
2. **LINCS / CMap** (Tier 2) - the transcriptional-corroboration layer for drug-rescue matching (CAP-03/05).
3. **Competitive-intel feeds** (ClinicalTrials.gov, Cortellis) - lower frequency but the CAP-13 backbone
   and the clearest Emit-overlap to pressure-test.
4. **ASO toolchain** (RNAfold, NUPACK, BLAST) - cheap, and CAP-04 has no off-the-shelf model.

## Cross-checks / open items

- **GenomicsDB** layer membership: confirm whether it's an internal Quiver store or an external genomics DB.
- Quiver Atlas at 104 vs everything else <55 confirms the strategy: the moat is internal; externals enrich.
- The Angelini/Common-Nodes corpus ranks **STRING (24), PubMed (19), Reactome (15)** highest - a
  literature- and network-heavier mix than the main corpus, reflecting its repurposing/clinical focus.
