# Justifying a target-specific binding-model fine-tune — public-data + published-precedent research

**Date:** 2026-06-14
**Scope:** Web research only. No AWS, no code. Every numeric claim carries a source link/DOI.
**Framing:** Purely public data + published methods. (Where this report says "the lead target," read SCN10A / Nav1.8 — a representative data-poor neuro/ion-channel binding target.)

---

## Executive bottom line

**A target-specific binding-model fine-tune is justified — *conditionally*.** The public
evidence is a *qualified yes*:

- **The data exists to attempt it, but it is thin and chemotype-narrow for Nav1.8 itself.**
  ChEMBL holds **~934 distinct compounds / 817 pChEMBL-valued activities** against human
  Nav1.8 (CHEMBL5451); BindingDB mirrors ~1,995 records. PubChem adds essentially **zero**
  net-new (no Nav1.8 HTS campaign exists — its ~200 assays are ChEMBL mirrors). The real
  *new* volume is in **Vertex + fast-follower patents (~1.5–6k binned-activity compounds,
  low confidence)**, dominated by a single acylsulfonamide/nicotinamide chemotype. The
  **Na-channel class as a whole is a genuine transfer asset: ~12,142 distinct compounds /
  36,575 activities**, anchored by Nav1.7 (SCN9A, 8,734 compounds).

- **Published precedent that fine-tuning beats off-the-shelf is strong, and strongest exactly
  in the low-N single-target regime we are in.** The most directly-relevant case — the BALM
  paper, which uses the same ESM-2 + ChemBERTa two-tower architecture as our current Nav1.8
  off-the-shelf ceiling — shows that fine-tuning the projection layer on **20% of one
  held-out target's ligands** lifts Pearson from **0.11 → 0.66 on SARS-CoV-2 Mpro (+0.55)**
  and **0.64 → 0.81 on USP7 (+0.17)** ([Gorantla et al. 2025, JCIM](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02063)).
  The Mpro case — a chance-level zero-shot target made usable with a few labeled examples — is
  the direct analogy to Nav1.8's current chance/marginal status.

- **Expected gain range (honest):** by precedent, a target-specific fine-tune on a few hundred
  to a few thousand Nav-relevant pairs should buy roughly **+0.1 to +0.5 Pearson / +0.10 to
  +0.20 AUROC over the zero-shot two-tower baseline** *if* the held-out chemistry resembles the
  training chemistry. Under a **strict Murcko-scaffold-held-out split** (which our success bar
  requires, and which BALM did *not* use), expect the **low end** of that range, and budget for
  the real risk that the gain is small or null.

- **The two hard caveats stakeholders must hear:** (1) below ~1,000 compounds, a plain
  **Morgan-fingerprint + RF/SVM baseline frequently matches or beats deep models** — the
  fine-tune must beat *that*, not just the off-the-shelf head
  ([van Tilborg 2022](https://doi.org/10.1021/acs.jcim.2c01073)); (2) **negative transfer is real**
  — fine-tuning/transfer can *hurt* when source and target chemistry diverge, and on tight
  congeneric R-group series even BALM's own few-shot fine-tune *regressed*
  ([Gorantla et al. 2025](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02063), Fig. 5;
  [Li 2024](https://arxiv.org/abs/2404.13393)). The Nav1.8 dataset's single-chemotype dominance
  makes scaffold-split evaluation the make-or-break test.

**Verdict:** Proceed with a pilot fine-tune, framed as low-N target/family adaptation of a
two-tower model, **evaluated on a scaffold-held-out split against a Morgan-FP+RF control**, with
explicit acceptance that the published expected gain is real but modest-and-conditional, not
guaranteed.

---

# DELIVERABLE 1 — Public data for a Nav1.8 / ion-channel binding fine-tune

## 1.1 ChEMBL — per-target counts (live ChEMBL 37 REST + Elasticsearch API, queried 2026-06-14)

All counts pulled live. Activity counts are `page_meta.total_count`; distinct-compound counts
are Elasticsearch `cardinality` aggregations on `molecule_chembl_id` (exact at these magnitudes,
treat as ±1%). Source URL pattern (substitute the ID):
`https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id=CHEMBL5451&format=json&limit=1`
and report card `https://www.ebi.ac.uk/chembl/explore/target/CHEMBL5451`.

| Target | Gene | ChEMBL target ID | Distinct compounds | Total activities | Assays | IC50/Ki/Kd | pChEMBL-valued |
|---|---|---|---:|---:|---:|---:|---:|
| **Nav1.8 (lead)** | SCN10A | **CHEMBL5451** | **934** | **2,159** | 117 | 885 | **817** |
| Nav1.7 | SCN9A | CHEMBL4296 | **8,734** | **17,017** | 398 | 10,831 | 9,934 |
| Nav1.5 (cardiac) | SCN5A | CHEMBL1980 | 3,630 | 5,996 | 564 | 3,404 | 1,706 |
| Nav1.6 | SCN8A | CHEMBL5202 | 1,175 | 6,096 | 133 | — | 1,995 |
| Nav1.1 | SCN1A | CHEMBL1845 | 1,028 | 3,556 | 107 | — | 979 |
| Nav1.2 | SCN2A | CHEMBL4187 | 341 | 640 | — | — | — |
| Nav1.4 | SCN4A | CHEMBL2072 | 448 | 597 | — | — | — |
| Nav1.3 | SCN3A | CHEMBL5163 | 230 | 377 | — | — | — |

- Human Nav1.8 single-protein target = **CHEMBL5451** (UniProt **Q9Y5Y9**), confirmed via
  [target search API](https://www.ebi.ac.uk/chembl/api/data/target/search?q=SCN10A&format=json).
- The Nav1.8 total of 2,159 activities filters to **885 IC50/Ki/Kd** and **817 pChEMBL-valued**
  (standardized, high-quality) measurements — verified live
  ([pchembl filter](https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id=CHEMBL5451&pchembl_value__isnull=false&format=json&limit=1) → 817).
- SCN1A has two human single-protein IDs; **CHEMBL1845** is the populated one (CHEMBL4906 is a
  near-empty duplicate, ~7 records — ignore).
- The ChEMBL "Sodium channel alpha subunit" family/group node (**CHEMBL2331043**) carries only
  ~30 directly-mapped activities — it is an organizing node, *not* where the data lives. The real
  class total is the enumerated-member sum below.

## 1.2 Nav-channel class total (the transfer set)

Querying all human Nav target IDs together and deduplicating compounds across paralogs
(Elasticsearch `terms` + `cardinality` agg, live 2026-06-14):

- **Total activities across the human Nav family: 36,575**
- **Distinct compounds (deduplicated across paralogs): 12,142**

The dedup count (12,142) is *lower* than the naive per-target sum because many compounds are
tested against multiple paralogs — which is exactly what makes the Na-channel class a coherent
transfer/multi-task pretraining set, and what makes **Nav1.5 a built-in cardiac-selectivity
transfer target** (3,630 compounds). Nav1.7 (SCN9A, 8,734 compounds) is the heavily-drugged
anchor. Source: ChEMBL ES aggregation over the 8 single-protein IDs + α/β complexes + group node.

## 1.3 BindingDB — Nav1.8

- **Human SCN10A / Nav1.8 (UniProt Q9Y5Y9): 1,995 binding records**, stable across affinity
  cutoffs. Source: `https://www.bindingdb.org/rest/getLigandsByUniprot?uniprot=Q9Y5Y9&response=application/json`
  (`bdb.hit = 1995`).
- Context — total BindingDB size: **~3.2M measurements, 1.4M compounds, 11.4K targets** (of which
  ~1.6M data / 752K compounds / 4.8K targets are BindingDB-curated; the rest ingested from
  ChEMBL/PubChem/PDB). Source: [BindingDB info page](https://www.bindingdb.org/rwd/bind/info.jsp);
  [Gilson et al., *NAR* 2024 / BindingDB-in-2024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11701568/).
- **BindingDB largely overlaps ChEMBL for Nav1.8** (it ingests ChEMBL). Treat ChEMBL ∪ BindingDB
  as roughly the same ~900 distinct compounds / ~1–2k measurements, not additive.

## 1.4 PubChem BioAssay — Nav1.8 (the disappointing part)

| Query route | Count | URL |
|---|---|---|
| Entrez `pcassay` term=SCN10A | **219 assays** | `https://www.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pcassay&term=SCN10A` |
| Entrez `pcassay` term=Nav1.8 | 206 assays | `https://www.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pcassay&term=Nav1.8` |
| PUG-REST protein accession Q9Y5Y9 → AIDs | **169 assays** | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/protein/accession/Q9Y5Y9/aids/JSON` |

**These assays add ~zero net-new data.** Essentially all are **ChEMBL-deposited literature
assays** with tiny compound counts (1–22 compounds each; e.g. AID 1233920 = 22 compounds / 14
actives, AID 549429 = 14/6, AID 404522 = 10/8). A spot-check of 7 representative AIDs returned
only **93 unique substances total**. The single largest "hit" in the SCN10A AID list
([AID 1508588, 18,119 substances](https://pubchem.ncbi.nlm.nih.gov/bioassay/1508588)) is a
**false positive** — a melanoma RNAi screen where SCN10A appears only in a gene list, not a
Nav1.8 compound screen. **There is no MLPCN/NCGC/Broad qHTS Nav1.8 campaign in PubChem** — Nav1.8
screening was done industrially (Abbott, Pfizer, Vertex) and never deposited as primary HTS.
**Net PubChem yield beyond ChEMBL ≈ 0.**

## 1.5 Patent / literature SAR — where the *new* volume is (with low confidence)

**Key structural fact:** Vertex did **not** publish a discovery/SAR paper for suzetrigine
(VX-548 / Journavx, FDA-approved Jan 2025). The peer-reviewed Vertex paper is pharmacology/MoA
(one IC50, not a SAR table). All suzetrigine-analog SAR lives in **patents**.

**Published SAR series with countable analogs (mostly non-Vertex):**

| Series / lead | Venue, year | DOI / PMID | ~Analogs w/ Nav1.8 data |
|---|---|---|---|
| Urea-derived selective Nav1.8 inhibitors (Dialer et al.) | ACS Med Chem Lett 2026 | [10.1021/acsmedchemlett.6c00130](https://doi.org/10.1021/acsmedchemlett.6c00130) (PMID 42157827) | ~30–60 |
| Chroman series, lead (R)-40 | Eur J Med Chem 2025 | [10.1016/j.ejmech.2025.117697](https://doi.org/10.1016/j.ejmech.2025.117697) (PMID 40347793) | ~40–60 |
| Pyridyl carboxamides | 2024–25 | PMID 39644938 | ~30–60 |
| Nicotinamide-azepane, lead 2c (50 nM) | Eur J Med Chem 2023 | [10.1016/j.ejmech.2023.115403](https://doi.org/10.1016/j.ejmech.2023.115403) (PMID 37084597) | ~30–50 |
| Adamantyl sulfonamide (Song et al.) | Bioorg Med Chem Lett 2024 | [10.1016/j.bmcl.2024.129862](https://doi.org/10.1016/j.bmcl.2024.129862) (PMID 38944398) | ~20–40 |
| ABBV-318 quinoline (AbbVie, dual Nav1.7/1.8) | Bioorg Med Chem 2022 | [10.1016/j.bmc.2022.116743](https://doi.org/10.1016/j.bmc.2022.116743) (PMID 35436748) | ~40–80 |
| Pfizer modulator series → PF-01247324 (Bagal et al.) | ACS Med Chem Lett 2015 | [10.1021/acsmedchemlett.5b00059](https://doi.org/10.1021/acsmedchemlett.5b00059) | ~30–50 |
| A-803467 furan-amide (Abbott, Jarvis/Kort) | PNAS 2007 + follow-ups | [10.1073/pnas.0611364104](https://doi.org/10.1073/pnas.0611364104) (PMID 17483457) | tens |

Reference IC50 anchors (reliable): suzetrigine ~0.7 nM (>30,000× selective); A-803467 hNav1.8
~8 nM; PF-01247324 ~196 nM. Catalogued in the
[IUPHAR/BPS Guide to Pharmacology, Nav1.8 (objectId 585)](https://www.guidetopharmacology.org/GRAC/ObjectDisplayForward?objectId=585)
(~15–18 distinct annotated ligands w/ pIC50). Review: [Medhat et al., *Molecules* 2026](https://doi.org/10.3390/molecules31020358).

**Distinct compounds in the open literature (papers only): ~300–600**, most already in ChEMBL.

**Patents** are the real net-new lever and the largest uncertainty. Suzetrigine patent filings
jumped 4 (2022) → 26 (2023) → 28 (2024); ~50+ publications, ~47 structurally VX-548-like, with
~7 distinct fast-follower families (Hengrui, Shanghai Huilun, Haisco, etc.) per
[PatSnap landscape](https://synapse.patsnap.com/blog/breakthrough-pain-relief-innovation-patent-exploration-of-next-generation-nav18-inhibitors).
Key Vertex genus patents: WO2020014246A1, US11377438B2, US11993581, US11802122. Standard
ion-channel composition-of-matter patents exemplify **~100–600 compounds each with *binned*
Nav1.8 IC50**. **Caveat (flagged, low confidence):** exact per-patent example counts could not be
verified — Google Patents/USPTO truncate before the examples tables, and one PatSnap-cited US
number was an unrelated patent (blog error). The per-patent multiplier is the single biggest
source of uncertainty in the estimate below.

## 1.6 Negatives / decoys for an ion-channel target

Public Nav1.8 data is almost entirely **positives** (measured inhibitors). A fine-tune needs
negatives. Methods and tools:

| Tool / method | What it does | Decoy:active ratio | Source / DOI | Ion-channel coverage |
|---|---|---|---|---|
| **DUD-E** | Property-matched decoys (MW, logP, HBD/HBA, rot-bonds, net charge) from ZINC, topologically dissimilar | **50:1** | [Mysinger 2012, *J Med Chem*, 10.1021/jm300687e](https://doi.org/10.1021/jm300687e); [dude.docking.org](https://dude.docking.org/) | Yes — 102 targets incl. GPCRs **and ion channels**; 22,886 ligands × 50 decoys |
| **DEKOIS 2.0** | Demanding property-matched decoy kits | ~30:1 | [Bauer 2013, *JCIM*, 10.1021/ci400115b](https://doi.org/10.1021/ci400115b); dekois.com | 81 targets (broad) |
| **DeepCoy** | *Generative* property-matched decoys; learns which properties to hold constant; reduces bias | user-set | [Imrie 2021, *Bioinformatics*, 10.1093/bioinformatics/btab080](https://doi.org/10.1093/bioinformatics/btab080); [github.com/oxpig/DeepCoy](https://github.com/oxpig/DeepCoy) | Validated on all 102 DUD-E + 80/81 DEKOIS 2.0 |
| **ZINC20 / ZINC22** | Purchasable library → random presumed-inactive negatives | n/a | [zinc20.docking.org](https://zinc20.docking.org/) (~1.4B); ZINC22 (multi-billion, [Tingle 2023, JCIM](https://doi.org/10.1021/acs.jcim.2c01253)) | n/a (source of decoy chemistry) |
| **Enamine REAL** | Make-on-demand space, presumed-inactive negatives | n/a | [enamine.net REAL](https://enamine.net/compound-collections/real-compounds) (~6B+) | n/a |

**Critical adverse evidence on decoys (must heed):**
[Chen et al. 2019, *PLoS ONE*, 10.1371/journal.pone.0220113](https://doi.org/10.1371/journal.pone.0220113)
showed that deep models' "superior enrichment" on DUD-E is **decoy/analogue bias, not learned
binding** — models exploit trivial property/topology differences between actives and decoys
rather than recognizing the target. **Implication:** property-match decoys *tightly* (DeepCoy or
strict DUD-E matching on MW/logP/HBD/HBA/rot-bonds/net charge), and **split by Murcko scaffold so
analogues of training actives can't leak into test** — otherwise the AUROC is an artifact.

## 1.7 Deliverable-1 bottom line: how many labeled pairs are realistically assemblable?

| Source | Net-new (compound, Nav1.8-activity) pairs | Confidence |
|---|---|---|
| ChEMBL (Nav1.8 directly) | **~817–934** (pChEMBL-valued / distinct cpds) | High |
| BindingDB | ~0 net-new (overlaps ChEMBL) | High |
| PubChem BioAssay | ~0 net-new (ChEMBL mirrors; no HTS) | High |
| Open-literature SAR not yet in ChEMBL | ~100–300 | Medium |
| **Patents (binned IC50, Vertex + followers)** | **~1,500–6,000** | **Low** |
| **Nav1.8 total realistic** | **~1,000 (clean) to ~3,000–6,000 (with patent mining, binned labels)** | Low–Medium |
| **Na-channel class transfer set (ChEMBL)** | **~12,142 compounds / 36,575 activities** | High |

**Is this enough to fine-tune?** Yes to *attempt*, with the right method:
- For Nav1.8 *alone* (~800–1,000 clean pairs, or low-thousands with binned patent data) we are in
  the **low-N regime where the precedent for fine-tuning is strongest but where simple baselines
  also compete** (§2.4). Patent data is **binned/censored** ("<100 nM", ">1 µM"), so treat it as
  **binary/ordinal labels**, not clean regression — and it is dominated by one Vertex chemotype,
  making scaffold-split evaluation brutal.
- The data-supported strategy is **Na-channel-family multi-task pretrain (12k compounds) →
  Nav1.8 target-specific fine-tune**, with Nav1.5 doubling as the cardiac-selectivity transfer
  target, and **scaffold-held-out** evaluation throughout.

---

# DELIVERABLE 2 — Published precedent that fine-tuning yields extra performance

## 2.1 The most directly-relevant case: BALM (same architecture as our off-the-shelf ceiling)

**Paper:** Gorantla, Gema, Yang, Serrano-Morrás, Suutari, Juárez-Jiménez, Mey. *"Learning Binding
Affinities via Fine-tuning of Protein and Ligand Language Models."*
[*J. Chem. Inf. Model.* 2025, 65(22):12279–12291, DOI 10.1021/acs.jcim.5c02063](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02063)
(PMID 41171175); preprint [bioRxiv 10.1101/2024.11.01.621495](https://www.biorxiv.org/content/10.1101/2024.11.01.621495v1);
code [github.com/meyresearch/BALM](https://github.com/meyresearch/BALM).

**Architecture:** two-tower — ESM-2 150M + ChemBERTa-2 77M → shared latent dim 256, **cosine
similarity = pKd**, cosine-MSE loss. PEFT = LoKr (protein) + LoHa (ligand), rank 16. Few-shot
fine-tuning retrains only the projection layer (~0.17% of params). **This is the same family of
model that gives our current best off-the-shelf Nav1.8 result — so its fine-tuning gains transfer
directly to our decision.**

**BindingDB split results (baseline → BALM → BALM+PEFT), Pearson:**

| Split | Baseline | BALM | BALM+PEFT | PEFT gain vs BALM |
|---|---:|---:|---:|---|
| Random | 0.46 | 0.67 | **0.78** | +17% Pearson, −8.5% RMSE |
| Cold Target | 0.26 | ~0.43–0.54 | 0.53 | +19.1% Pearson, −6.6% RMSE |
| Cold Drug | 0.35 | 0.62 | 0.61 | +9.7% Pearson |
| Scaffold | 0.27 | 0.55 | (+15.2%) | +16.4% Spearman, −7.4% RMSE |

(PEFT ablation: ligand LoHa-r16 +9.4%, protein LoKr-r8 +18.2%, combined +23.4% over no-FT BALM.
*Note:* the preprint is internally inconsistent on the cold-target BALM Pearson — 0.54 vs 0.43 in
two paragraphs; flagged as a likely preprint typo.)

**THE KEY RESULT — zero-shot → few-shot on held-out targets (Fig. 3; fine-tune on 20% of one
target's ligands, projection layer only):**

| Held-out target | Metric | Zero-shot | Few-shot (20%) | Delta |
|---|---|---:|---:|---|
| **USP7** (1,799 ligands) | Pearson | 0.64 | **0.81** | **+0.17** |
| USP7 | RMSE | 1.49 | 1.03 kcal/mol | −31% |
| **Mpro** (2,062 ligands) | Pearson | **0.11** | **0.66** | **+0.55** |
| Mpro | RMSE | 2.11 | 1.51 kcal/mol | −28% |

**Mpro is the load-bearing analogy:** a target where the zero-shot two-tower is at chance
(Pearson 0.11) becomes genuinely useful (0.66) after fine-tuning on a few hundred of its own
ligands, using <0.2% of parameters in ~15–25 min on one A100. **This is precisely the situation
for Nav1.8** (chance/marginal zero-shot for every public model except a marginal Boltz-2).

**Honest negatives from BALM's own paper:**
- **On tight congeneric series (MCL1/HIF2A/SYK, 25–43 ligands), few-shot fine-tuning did NOT
  reliably help — HIF2A ranking actually *worsened*, and RBFE/docking kept the edge.** BALM
  resolves *cross-chemotype, target-level* ranking, not fine R-group SAR.
- BALM's few-shot splits are **random, not Murcko-scaffold-held-out** — so its reported deltas are
  an **upper bound** relative to our stricter scaffold-split success bar (AUROC ≥ 0.80 / EF5 ≥ 5×).

## 2.2 Contrastive DTI fine-tuning: ConPLex

[Singh et al., *PNAS* 2023, 120(24):e2220778120, DOI 10.1073/pnas.2220778120](https://www.pnas.org/doi/10.1073/pnas.2220778120)
(PMC10268324). ESM-based two-tower, contrastive against decoys. **Contrastive fine-tuning on
DUD-E moved median target discrimination (Cohen's d) from 0.730 → 4.716** (i.e. dramatic
separation of binders from decoys after fine-tuning), with 12/19 prospective kinase predictions
validated (e.g. EPHB1 + PD-166326, Kd 1.30 nM). DTI AUPR: BIOSNAP 0.897 / BindingDB 0.628 /
DAVIS 0.458 (vs MolTrans 0.335). Directly supports decoy-contrastive fine-tuning for a single
target's binder-vs-decoy triage.

## 2.3 Consolidated precedent table — fine-tune / transfer gains

| # | Paper | Base model | Task / N | Baseline | Fine-tuned / transfer | Gain |
|---|---|---|---|---|---|---|
| 1 | **BALM** ([Gorantla 2025](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02063)) | ESM-2 150M + ChemBERTa two-tower | Mpro few-shot (20% of ~2k) | Pearson 0.11 (zero-shot) | 0.66 | **+0.55 Pearson** |
| 1b | BALM | same | USP7 few-shot (20% of ~1.8k) | 0.64 | 0.81 | +0.17 Pearson, −31% RMSE |
| 2 | **ConPLex** ([Singh 2023](https://www.pnas.org/doi/10.1073/pnas.2220778120)) | ESM two-tower, contrastive | DUD-E target discrimination | Cohen's d 0.730 | 4.716 | **+~4.0 d** (binder/decoy separation) |
| 3 | **MolFormer-XL** ([Ross 2022](https://arxiv.org/abs/2106.09553), via [Latent-Fusion](https://arxiv.org/abs/2310.13802)) | 1.1B-molecule pretrained transformer | MoleculeNet BBBP | D-MPNN 71.2 (from-scratch) | 93.7 | **+22.5 AUROC** (Tox21 +15.8, HIV +7.2) |
| 4 | **FS-Mol** ([Stanley 2021, NeurIPS](https://arxiv.org/abs/2310.00614)) | GNN meta-learn | 16–64-shot per assay, 157 assays | single-task ΔAUPRC +2.9% | meta-learn +23.4% | **+~18–20 AUPRC pts** at low N |
| 5 | **ActFound** ([Feng 2024, *Nat Mach Intell*](https://doi.org/10.1038/s42256-024-00876-w)) | Pairwise meta-learn foundation model | 16/32/128-shot, ChEMBL/BindingDB | 9 competing methods | best at 16- & 32-shot | wins concentrate at low N; **erode by 128-shot** |
| 6 | **AdaMBind** ([2024, *Nat Commun*](https://doi.org/10.1038/s41467-026-70554-5)) | Meta-learning DTA | 5-shot DTA, Davis/KIBA/BindingDB | DeepDTA/ColdDTA | KIBA MSE 0.638→0.546 | **−10 to −14% MSE** at N=5 |
| 7 | **MolPMoFiT** ([Li 2020, *J Cheminform*](https://doi.org/10.1186/s13321-020-00430-x)) | ULMFiT SMILES LM | small ChEMBL QSAR | no-pretrain | pretrain+fine-tune ≥ SOTA | positive; **biggest in small-data regime** |
| 8 | **Merck multitask DNN** ([Ma 2015, *JCIM*](https://doi.org/10.1021/ci500747n)) | Multitask DNN, 15 *internal* sets | industrial QSAR | Random Forest | DNN better prospectively | modest consistent R² gain on **proprietary data** |
| 9 | **KERMT (Merck)** ([2025, arXiv:2510.12719](https://arxiv.org/abs/2510.12719)) | Chemical pretrained model | public + *internal* ADMET | non-pretrained GNN | significantly improves | **adverse nuance: gain largest at *larger* data** |
| 10 | **Stokes halicin** ([2020, *Cell*](https://doi.org/10.1016/j.cell.2020.01.021)) | D-MPNN, 2,335 cpds | antibiotic discovery | HTS hit-rate ~1% | enriched hit-rate >> HTS | small training set → real prospective hits |

## 2.4 Adverse evidence and the data-volume threshold (be honest)

- **Simple descriptor models match/beat deep learning below ~1,000 compounds.**
  [van Tilborg, Alenicheva & Grisoni 2022, *JCIM*, 10.1021/acs.jcim.2c01073](https://doi.org/10.1021/acs.jcim.2c01073):
  across 30 ChEMBL targets (615–3,657 compounds each), **SVM/RF/GBM on ECFP fingerprints beat
  every deep model** (MPNN/GCN/GAT/Transformer/CNN/LSTM) on average, and were better on activity
  cliffs. Below ~1,000 training molecules, which method wins was unpredictable.
- **RF on ECFP beats pretrained transformers/GNNs at the smallest data fractions.**
  ["Taking a Respite from Representation Learning," arXiv:2209.13492](https://arxiv.org/abs/2209.13492)
  (*Nat Mach Intell* 2023): RF outperformed MolBERT/GROVER at the smallest labeled-data fractions;
  the pretraining advantage only emerges with more labels.
- **Negative transfer is real and depends on chemistry similarity, not just N.**
  ["Transfer Learning for Molecular Property Predictions from Small Data Sets," arXiv:2404.13393](https://arxiv.org/abs/2404.13393):
  transfer cut error ~17–20% on one dataset (HOPV) but **made it worse** on another (Freesolv,
  RMSE 0.56→0.61–0.66). Transfer only worked when source/target were aligned.
- **Meta-learning foundation models don't always generalize out of domain.** The independent
  [ActFound reusability report (PMC12363932)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12363932/)
  found R² dropped to 0.01–0.12 on a structurally-diverse natural-products task.

**Apparent data-volume threshold (synthesis):**
- **< ~50–100 examples/target:** meta-learning/few-shot fine-tune wins largest and most reliably
  (FS-Mol, ActFound, AdaMBind, BALM Mpro). Strongest regime for the fine-tune case.
- **~100–1,000 examples:** gains shrink, become dataset-dependent; **Morgan-FP+RF/SVM is a serious,
  often-winning baseline** — *always run it as the control.* **Nav1.8 sits right here.**
- **> ~1,000 examples:** deep/pretrained models pull ahead; large multitask DNNs beat RF
  prospectively (Merck, MolFormer). The Na-channel *class* transfer set (12k) sits here.
- **Orthogonal gate:** transfer fails when pretrain chemistry is unlike the target — so pretrain
  from **chemically/functionally related assays** (the Nav family), and validate on a
  scaffold-held-out split.

---

# What data to actually pull + how much (recommendation)

1. **Pull the clean core first (free, fast, high-confidence): ChEMBL.**
   - Nav1.8 (CHEMBL5451): **all 817 pChEMBL-valued activities / ~934 distinct compounds.** This is
     the gold-standard regression/classification core.
   - Na-channel family for transfer/multi-task pretrain: CHEMBL4296 (Nav1.7, 8,734 cpds),
     CHEMBL1980 (Nav1.5, cardiac, 3,630), CHEMBL5202 (Nav1.6), CHEMBL1845 (Nav1.1), plus
     CHEMBL4187/2072/5163 — **~12,142 distinct compounds / 36,575 activities total**, deduplicated.
   - Skip PubChem and treat BindingDB as ChEMBL-redundant (no net-new for Nav1.8).

2. **Generate negatives properly.** For each active, draw **~30–50 property-matched decoys** with
   **DeepCoy** (preferred — reduces the [Chen 2019](https://doi.org/10.1371/journal.pone.0220113)
   bias) or strict DUD-E matching (MW, logP, HBD/HBA, rotatable bonds, **net charge**), from
   ZINC20/22 or Enamine REAL. Match tightly so the model can't cheat on trivial properties.

3. **Optionally mine patents — only if the clean core underperforms.** Vertex genus patents
   (WO2020014246, US11377438, US11993581, US11802122) + ~7 follower families could add
   **~1.5–6k binned-activity compounds** — but as **binary/ordinal labels**, one dominant
   chemotype, and nontrivial OCR/IUPAC-parsing engineering. Low confidence on yield; treat as a
   second phase.

4. **Split by Murcko scaffold, not randomly.** The Nav1.8 / Vertex medchem recurs across paralogs
   and patents; a random split would massively overstate performance (this is exactly the
   [Chen 2019](https://doi.org/10.1371/journal.pone.0220113) failure mode).

5. **Always include a Morgan-FP + RF/SVM baseline.** At ~800–1,000 compounds, that baseline
   frequently matches deep models ([van Tilborg 2022](https://doi.org/10.1021/acs.jcim.2c01073)) —
   the fine-tune must beat *it*, not just the off-the-shelf head, to be worth deploying.

6. **Expected outcome, stated up front.** Precedent supports **+0.1 to +0.5 Pearson / +0.10 to
   +0.20 AUROC over zero-shot** if held-out chemistry resembles training; under a strict
   scaffold split expect the **low end**, and accept a real probability of a small/null gain on
   the hardest scaffolds (mirroring BALM's HIF2A regression and the data-volume threshold).

---

## Source index (primary)

- ChEMBL API (live, 2026-06-14): `https://www.ebi.ac.uk/chembl/api/data/` — targets CHEMBL5451,
  4296, 1980, 5202, 1845, 4187, 2072, 5163.
- BindingDB: [info](https://www.bindingdb.org/rwd/bind/info.jsp);
  [BindingDB-in-2024, PMC11701568](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11701568/).
- PubChem PUG-REST / Entrez (links inline §1.4); [IUPHAR objectId 585](https://www.guidetopharmacology.org/GRAC/ObjectDisplayForward?objectId=585).
- Decoys: [DUD-E 10.1021/jm300687e](https://doi.org/10.1021/jm300687e);
  [DEKOIS 2.0 10.1021/ci400115b](https://doi.org/10.1021/ci400115b);
  [DeepCoy 10.1093/bioinformatics/btab080](https://doi.org/10.1093/bioinformatics/btab080);
  [decoy-bias Chen 2019 10.1371/journal.pone.0220113](https://doi.org/10.1371/journal.pone.0220113).
- Fine-tune precedent: [BALM 10.1021/acs.jcim.5c02063](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02063);
  [ConPLex 10.1073/pnas.2220778120](https://www.pnas.org/doi/10.1073/pnas.2220778120);
  [MolFormer arXiv:2106.09553](https://arxiv.org/abs/2106.09553);
  [FS-Mol arXiv:2310.00614](https://arxiv.org/abs/2310.00614);
  [ActFound 10.1038/s42256-024-00876-w](https://doi.org/10.1038/s42256-024-00876-w);
  [AdaMBind 10.1038/s41467-026-70554-5](https://doi.org/10.1038/s41467-026-70554-5);
  [Ma 2015 10.1021/ci500747n](https://doi.org/10.1021/ci500747n);
  [Stokes halicin 10.1016/j.cell.2020.01.021](https://doi.org/10.1016/j.cell.2020.01.021).
- Adverse: [van Tilborg 10.1021/acs.jcim.2c01073](https://doi.org/10.1021/acs.jcim.2c01073);
  [Respite arXiv:2209.13492](https://arxiv.org/abs/2209.13492);
  [negative transfer arXiv:2404.13393](https://arxiv.org/abs/2404.13393);
  [ActFound reusability PMC12363932](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12363932/).

**Uncertainty flags:** (1) Patent compound counts are low-confidence (could not verify per-patent
example tables; one PatSnap-cited number was a blog error). (2) BALM cold-target Pearson has a
likely preprint typo (0.54 vs 0.43). (3) Distinct-compound counts are HLL cardinality aggregations
(±1%); activity counts are exact `total_count`. (4) A few secondary-table numbers (FS-Mol per-shot,
ChemBERTa-2 per-task) are from review tables, not primary PDFs.
