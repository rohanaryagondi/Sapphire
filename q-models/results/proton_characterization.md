# PROTON — Track 6 KG / hypothesis-generation operating envelope

**Date:** 2026-06-13 · **Model:** PROTON (`mims-harvard/PROTON`, NeuroKG bilinear link-prediction decoder)
**Run:** `proton_tier1_20260612-122415` (full-KG strength eval, 154.6 s, ~$0.30) — the comprehensive
re-run (`proton_char_run`, 2026-06-13) is **superseded**: the `cli download-proton` checkpoint ships
only anonymous embeddings (columns `'0'`–`'511'`, no node-name/type table, no edge list), so it could
not anchor any analysis. The tier1 run built/loaded the full graph and is the authoritative source.

## What PROTON actually is
A graph neural net trained on **NeuroKG**: 147,020 nodes · **14,733,490 edges** · **16 node types**
(anatomy, brain_region, brain_structure, cell_cluster/subcluster/type, disease, drug, gene/protein,
pathway, phenotype, exposure, …) · **94 canonical relation types**. The released artifact is a
`[94 × 512]` relation-embedding **bilinear decoder** + a `[147020 × 512]` node-embedding matrix.
The node types make it explicit: this is a **neuroscience-centric KG** (brain regions, cell clusters),
not a general biomedical graph.

Link-prediction score for a (head, relation, tail) triple = bilinear decoder over the two node
embeddings and the relation embedding. We tested the 2 gene↔drug relations on real Quiver substrate.

## The headline is real — but only in ONE direction

PROTON's link-prediction is **strongly asymmetric.** The same decoder is genuinely useful one way
and actively misleading the other.

### ✅ Direction 1 — binder RANKING (recall): WORKS
*"Given a known drug and a target, where does the drug rank among all 8,160 KG drugs for that target?"*

| Metric | Value |
|---|---|
| Known binder–target pairs attempted | 116 |
| Resolvable (drug in KG) | 106 |
| **Median rank percentile** | **4.3%** |
| Mean rank percentile | 9.0% |
| In top-1% | 15 / 106 |
| **In top-5%** | **60 / 106 (57%)** |
| In top-10% | 80 / 106 (75%) |
| In bottom half (>50%) | 2 / 106 |

A real binder lands in the top ~4% of the drug pool → a useful **triage / literature-recall shortlist**.

### ❌ Direction 2 — forward PREDICTION (generation): HUB-BIASED NOISE
*"Which drug binds target X?"* — returns the **same promiscuous hub compounds for nearly every target.**

Top-1 predicted drug per Quiver target (scores all saturated ~0.99+):

| Hub drug | Is #1 for… |
|---|---|
| **Bepridil** | SCN10A, SCN9A, SCN1A, SCN5A (all 4 Navs) + ADRB2, DRD2, HTR2A, OPRM1, KCNQ2 — **9 unrelated targets** |
| **Obinepitide** | EGFR, BRAF, MAPK1, MAPK3, PKM, LDHA, UBE3A, HCN1, PPARD, RXRA — **10 targets** |
| **Beta carotene** | PPARA, PPARG |

Frequency across the 22 targets' top-20 lists: N-cyclohexyltaurine & Beta carotene (13/22), Bepridil &
Obinepitide (12/22), **Caffeine (11/22)**, Halothane (11/22). For SCN10A (Nav1.8), the top-5 predicted
"binders" are Bepridil, Amitriptyline, **Caffeine**, Etomidate — generic promiscuous compounds, not
Nav1.8-selective chemistry. **Do not use PROTON as a binder/hit generator.** The CRISPR-hit-hypothesis
mode (25/25 targets resolved) has the identical failure — EGFR's top drugs are Obinepitide / Peptide YY.

## Where the signal fades — exactly on Quiver's targets
Per-target median rank percentile (lower = better):

| Strong (well-studied, drug-rich) | | Weak (Quiver's peripheral interest) | |
|---|---|---|---|
| DRD2 | 0.026 | OPRM1 | 0.073 |
| SCN1A | 0.028 | **SCN9A (Nav1.7)** | **0.124** |
| EGFR | 0.029 | **MTOR** | **0.142** |
| HTR2A | 0.035 | **SCN10A (Nav1.8)** | **0.254** |
| SCN5A (central) | 0.038 | | |
| ADRB2 | 0.046 | | |

This is **popularity bias, not biology**: dense, well-published targets (central Na_v channels, classic
GPCRs, EGFR) rank their binders tightly; under-studied peripheral targets (Nav1.7/1.8, mTOR) degrade.
And the actual Nav1.8 drug **suzetrigine / VX-548 is `binder_not_in_kg`** — post-cutoff novel chemistry
simply isn't in the graph, so PROTON has **zero novel-drug capability** on it (10/116 pairs were
`binder_not_in_kg` for this reason).

## Operating envelope — one line
**Use PROTON as a literature-recall shortlist that re-ranks *known* drugs against *well-studied* targets.
Never as a binder predictor, a hit generator, or on novel chemistry / under-studied targets** — those are
precisely where it collapses to hub bias, which is the same place Quiver's actual value lives (V1-T +
functional traces on targets others can't see). Commodity KG tools enrich well-trodden ground; they
don't illuminate the dark targets.

## Verdict vs alternatives
PROTON remains the **Track-6 pick for the neuro-KG recall use case** (it's purpose-built NeuroKG, MIT +
Harvard Dataverse, runs in 154 s for ~$0.30). The 2025 literature ([community consensus
doc](../docs/community_consensus_2026-06-13.md)) rates **TxGNN** (general-disease zero-shot repurposing,
Nature Medicine) and **BioPathNet** (NBFNet path-based, explainable) as the general-graph SOTA — both
untested here and worth a look *only if* Quiver wants disease-level repurposing beyond the neuro-KG.
EMET (BenchSci) is the same use case as a commercial product, wrong-fit at $150-500K/yr (see `emet` branch).

## Receipts
- `s3://rohan-mammal-bootstrap-20260610-213029/proton_tier1_20260612-122415/proton/` — `summary.json`,
  `known_binder_rank.json` (per-pair ranks), `quiver_target_drug_rankings.json` (22 targets × top-20),
  `crispr_hit_hypotheses.json` (25 targets), `edge_types.json` (schema).
- Family-clustering (Track 1) is a separate, negative result: PROTON NN-recall 0.487 (loses to ESM-2/MAMMAL
  0.750) — `results/aws_eval/proton_results.json`. KG embeddings ≠ sequence-family embeddings.
