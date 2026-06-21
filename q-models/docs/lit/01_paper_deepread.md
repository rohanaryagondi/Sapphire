# MAMMAL — Definitive Paper Deep-Read

**Lane: PAPER DEEP-READ.** What MAMMAL *actually is*, technically, from the primary sources. Every
number here is transcribed from the paper/supplementary; sources and exact locations are cited so a
later reader can re-verify. Where the paper is vague or a fact could not be verified, it is flagged
inline with **[FLAG]**.

## Sources read (and their relationship)
- **npj Drug Discovery version** (the journal paper) — `~/Downloads/2026-05-22 -- MAMMAL AI Model.pdf`,
  11 pages. DOI **10.1038/s44386-026-00047-4**, *npj Drug Discovery* (2026) **3:14**. Received 2 Sep 2025,
  accepted 23 Feb 2026, published **04 May 2026**. This is the authoritative version (Tables 1–3, Fig 1–2).
- **Supplementary Information** (npj) — 17 pages, fetched from Springer (`44386_2026_47_MOESM1_ESM.pdf`).
  Contains Architecture detail (§1 + Fig S1), Prompt Syntax (§2 + Figs S2–S3), Pretraining Details
  (§3: infra, hyperparameters, datasets, tasks), Additional Results (Tables S1–S8, Fig S4). **This is
  where the real mechanism lives** — the main text only sketches it.
- **arXiv 2410.22367** — same paper, preprint. v1 submitted 28 Oct 2024, final revision 6 May 2025.
  Title on arXiv: "MAMMAL — Molecular Aligned Multi-Modal Architecture and Language" (npj adds "for
  Biomedical Discovery"). Content matches npj; the npj headline number is **2 billion** pretraining
  samples. Not re-read page-by-page (PDF exceeds fetch limit); the local PDF + supplementary are the
  npj final and supersede it.

**One-line identity:** MAMMAL is a **single 458M-parameter T5-style (encoder + autoregressive decoder)
sequence-to-sequence transformer**, pretrained on **2B samples** across **6 datasets / 7 tasks** spanning
proteins, antibodies, small molecules, and single-cell gene expression, that reframes *every* biomedical
task — classification, regression, generation — as text-to-text over a **modular multi-domain tokenizer**,
with a **headline trick: scalars are projected directly into the embedding space via a learned linear
layer** (no discretization). Fine-tuned per task, it reports SOTA on 9 of 11 benchmarks.

---

## 1. Architecture (encoder-only vs encoder-decoder, shared weights, T5 lineage)

**T5 lineage, explicit.** Methods §4.1: "The MAMMAL architecture builds upon the transformer architecture
introduced by Vaswani et al. and draws inspiration from the **T5 framework** while introducing several key
modifications." It inherits T5's text-to-text framing and span-corruption pretraining (mean span length 5,
density 0.15 — see §6), but adds three features: (1) representation+generation in one model, (2) flexible
multi-domain structured prompts, (3) numerical-value integration.

**Two operating modes, one shared encoder (the key structural fact):**
- **Encoder-only mode** — used for representation-heavy tasks (classification, regression). A dedicated
  **token-prediction head** outputs logits over the vocabulary for token predictions, plus an **optional
  scalar prediction head** for scalar outputs (Fig 1B caption; Fig S1).
- **Encoder-decoder mode** — used for generative tasks. The encoder stack of self-attention blocks
  encodes the input; the **autoregressive decoder** generates the output sequence. Fig 1B caption:
  *"In encoder-decoder mode, residual connections inject features from the encoder's final hidden layer
  into each decoder layer, and a decoder-specific prediction head outputs the final logits."*
- **Weight sharing across modes (the design crux):** Methods §4.1 — *"By sharing encoder stack weights
  across these modes, MAMMAL facilitates efficient multi-task training, with parameter updates conducted
  through gradient accumulation across all tasks."* So the **same encoder** serves both the
  classification/regression heads and the generative decoder. This is exactly why Quiver's Phase-3
  finding holds — the trained signal in the per-target heads lives in the **shared encoder + generative
  decoder**, while the scalar head can be left untrained/vestigial.

**Concrete dimensions — mostly NOT in the paper. [FLAG]**
- **Parameter count: 458M** (stated everywhere; it is the only published size — no v2, no 84M-equivalent
  standard-loadable checkpoint; the older `mv-te-84m` is `.ckpt`-only per the checkpoint survey).
- **d_model = 768** — appears only as an *example* in Fig S1 ("model_dim (e.g. 768)") and is consistent
  with the 768-d embeddings Quiver observed empirically (`embed.py`). Treat 768 as confirmed by the figure
  + our own runs.
- **Number of encoder layers, decoder layers, attention heads, FFN dimension, vocab size, max positions:
  NOT stated** anywhere in the main text, supplementary, or the model card I could reach (HF
  `config.yaml` 404'd; model card prose omits them). **[FLAG — unverifiable from the paper.]** If these
  are needed, read the local `models/base_458m/` config directly (the SDK loads it); do not cite a number
  the paper does not give.
- **Max sequence length: "set per task to be effective yet efficient"** (Supp §3.2) — not a single global
  value. Per-task caps are visible in prompts: e.g. `@MAX-LEN=2100` for MoleculeNet SMILES, `=700` for
  Ab-Ag / TCR sequences, `=170` for epitopes (Table S1). (Quiver's DTI head empirically truncates protein
  to 1250 aa / SMILES to 256 tokens — a fine-tune-specific cap, consistent with "per task".)

**Truncation handling (subtle, matters for large proteins):** Supp §3.2 — rather than naively cutting the
end of a sequence, they "first wrapped the sequence with special start and end tokens to provide a hint
… whether the beginning or end … was truncated. Then we randomly cut a random sub-sequence with the
required length." So truncation is randomized + flagged during pretraining (`<SEQUENCE_NATURAL_START>` /
`<SEQUENCE_NATURAL_END>` tokens, seen in Table S1).

---

## 2. Numerical-value projection mechanism (the headline innovation)

This is the contribution the paper leads with ("a novel multi-alignment framework that integrates …
inputs … and natively incorporates **numerical values into its embedding space via continuous
projections**"). The real description is **Supp §1 + Fig S1**, not the main text.

**How a scalar enters the model (inputs):**
- A prompt is parsed into **two parallel sequences**: (a) **input token IDs** (integers indexing the
  vocabulary) and (b) **an input-scalars sequence**, *by convention containing NaNs at every position
  where no scalar is provided* (Supp §1, lines 22–25).
- Token IDs → **learned token embedding** (standard). Input scalars → a **learned linear transformation
  that projects each single scalar element into the model dimension** (e.g. 768): a `1 → model_dim`
  learned linear projection (Fig S1).
- **The two representations are ADDED, not concatenated** (Supp §1, line 29: *"Both representations are
  added (not concatenated) and fed into the encoder stack."*). So a position carries a token embedding
  *plus* (if present) its scalar's projected embedding, summed. This is why "the resulting embeddings
  align with the input token embeddings" (main text §4.1).
- Consequence: **arbitrary, possibly-unseen continuous values** are supported with **no new vocab tokens
  and no inflation of sequence length** — the paper's explicit contrast with digit-tokenization (which
  "inflates the number of input/output tokens significantly," critical for gene-expression tasks with
  "thousands of scalars in a single prompt").

**How a scalar comes out (outputs / regression):**
- The **encoder stack has an additional scalar prediction head** that outputs **a scalar value for every
  input element** (Supp §1, lines 33–35). Positions without a scalar label are by default ignored.
- **Loss:** regression loss (MSE / RMSE) on the scalar head; classification loss (cross-entropy / focal)
  on the token logits (Fig S1, Fig 1B). The paper cites the "**regress, don't guess**" line of work
  (ref 95, Zausinger et al.) as the motivation — a loss term that respects numerical proximity, avoiding
  a separate prediction head per scalar.
- **Important limitation [FLAG, from the paper itself]:** Supp §1 lines 37–38 — *"The support of scalar
  **outputs** in the **encoder-decoder mode** is an improvement that we intend to add in future
  generations."* So **scalar regression outputs are an ENCODER-ONLY capability**; the generative decoder
  cannot emit scalars directly. (Regression tasks like DTI/PPI-ΔΔG/Cancer-Drug-Response use the
  encoder-side scalar head — though note Table S1 shows DTI/CDR *decoder labels* as
  `<@TOKENIZER-TYPE=SCALARS_LITERALS>{standardized pKd}`, i.e. the scalar is also representable as a
  tokenized literal in the prompt syntax. The two are not fully reconciled in the text. **[FLAG —
  mild internal ambiguity: scalar head (encoder) vs SCALARS_LITERALS tokenization (prompt) coexist.]**)

**Why Quiver should care:** the projection is genuinely the differentiated piece — it is *the* reason
MAMMAL can natively ingest binding affinities, expression values, ΔΔG, etc., and the reason it can take
"thousands of scalars in a single prompt" for gene expression. It is also why the per-target binder heads
behave as generative classifiers (the scalar head is the regression path, vestigial there).

---

## 3. Multi-domain structured prompt syntax + modular tokenizer

**Entity hierarchy (Supp §2).** A prompt is built from typed entities, nested:
- **Sequence** — raw amino acids or other chemical reps (SMILES); a full sequence or a sub-region.
- **Molecule** — a complete molecule (protein chain or small molecule), may contain multiple
  sub-sequences. **Each molecule is opened by two special tokens:** a general hierarchical-level token
  `<MOLECULAR_ENTITY>`, then a type token (e.g. `<MOLECULAR_ENTITY_EPITOPE>`,
  `<MOLECULAR_ENTITY_SMALL_MOLECULE>`, `<MOLECULAR_ENTITY_TCR_BETA_VDJ>`,
  `<MOLECULAR_ENTITY_ANTIBODY_HEAVY_CHAIN>`, `<MOLECULAR_ENTITY_GENERAL_PROTEIN>`,
  `<MOLECULAR_ENTITY_CELL_GENE_EXPRESSION_RANKED>`). Optional `<SEQUENCE_NATURAL_START>` /
  `<SEQUENCE_NATURAL_END>` mark whether truncation occurred.
- **MolecularSystem** — a quaternary structure of multiple molecules, denoted `<COMPLEX_ENTITY>`.
- **GlobalSystem** — multiple interacting MolecularSystems.
- **Attribute** — properties/interactions among entities, e.g. `<ATTRIBUTE_ORGANISM>`,
  `<ATTRIBUTE_ORGANISM_HUMAN>`, `<BINDING_AFFINITY_CLASS>`, `<GENERAL_AFFINITY_CLASS>`,
  `<CELL_TYPE_CLASS>`, `<TOXICITY>`, `<FDA_APPR>`, `<BBBP>`, `<MUTATED>`.

**Task tokens.** Tasks are signaled by these attribute/class tokens placed in the prompt (e.g. `<BBBP>`,
`<TOXICITY>`, `<FDA_APPR>`, `<BINDING_AFFINITY_CLASS>`, `<CELL_TYPE_CLASS>`). In the **per-target
fine-tunes** (not in the paper but consistent with this scheme) the task token is a new dedicated token
like `<WDR91_ASMS>` / `<PGK2_DEL>` — confirming the tokenizer is extensible per fine-tune (Supp §2.1,
"New tags can be introduced … without disrupting existing functionality").

**Sentinel tokens (`<SENTINEL_ID_?>`) — the output anchors.** Supp §2, lines 57–70: sentinels are
"positionally aware anchors in the decoder output." For classification/regression, a **single** sentinel
`<SENTINEL_ID_0>` marks where the model emits the prediction. For complex generation (infilling, molecule
editing, antibody design) **multiple** sentinels `<SENTINEL_ID_0>`, `<SENTINEL_ID_1>`, … let the model
generate multiple disjoint output segments — exactly T5-style span sentinels, generalized across domains.
This is what unifies discrete + continuous + generative + discriminative under one seq2seq format.
*(This is the mechanism behind Quiver's validated readout: prompt with the task token + `<SENTINEL_ID_0>`,
`model.generate`, read P(`<1>`) at the class position.)*

**Modular tokenizer + meta tokens (Supp §2.1) — the multi-modal glue.** All sub-tokenizers share one
unified vocabulary / ID space (so SMILES carbon "C" and amino-acid cysteine "C" map to the **same ID** and
must be disambiguated). A **meta token** `<@TOKENIZER-TYPE=...>` switches the active sub-tokenizer for
everything up to the next meta token: e.g. `<@TOKENIZER-TYPE=AA>` (amino acids), `<@TOKENIZER-TYPE=SMILES>`,
`<@TOKENIZER-TYPE=GENE>`/`GENES`, `<@TOKENIZER-TYPE=SCALARS_LITERALS>`. Meta tokens can carry instructions:
`<@TOKENIZER-TYPE=AA@MAX-LEN=1000>` caps the tokenized length of *that* segment. **Meta tokens are not
themselves tokenized into any token** — they are instructions to the modular tokenizer. A dedicated
**numeric sub-tokenizer** handles continuous values by projecting them into embedding space (the §2
mechanism). `<EOS>` is the shared end-of-sequence token. Implementation:
`github.com/BiomedSciAI/fuse-med-ml/tree/master/fuse/data/tokenizers/modular_tokenizer`.

**Worked examples (Table S1, verbatim structure).** Each fine-tune is an (encoder input, decoder label)
pair. Examples:
- **BBBP** — enc: `<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE><BBBP>
  <SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100> C(C1)C1 <EOS>` → dec:
  `<@TOKENIZER-TYPE=SMILES><SENTINEL_ID_0><1><EOS>`. (Class label is the token `<1>` / `<0>`.)
- **DTI** — enc carries protein (AA) `<MASK>`'d affinity + `<MOLECULAR_ENTITY_GENERAL_PROTEIN>` AA seq +
  `<MOLECULAR_ENTITY_SMALL_MOLECULE>` SMILES → dec label is `<@TOKENIZER-TYPE=SCALARS_LITERALS>
  {standardized pKd}`.
- **Cancer-Drug Response** — enc has `<MASK>` scalar slot + SMILES + ranked gene list
  (`[B2M][RPL10]…[ZBTB16][ZNF429]`) → dec emits a scalar literal `3.966226`.
- **Cell type** — enc: ranked gene names `[MALAT1][RPL10]…<CELL_TYPE_CLASS><SENTINEL_ID_0>` → dec:
  `[CL:0001062]` (Cell Ontology ID).
- **Antibody design / Ab-Ag bind / TCR bind / PPI ΔΔG** — all in Table S1 with the same pattern (multiple
  sentinels for infilling; single sentinel + `<1>` for binding classification; SCALARS_LITERALS for ΔΔG).

---

## 4. How generation works (autoregressive decoder; what it can generate)

- **Mechanism:** encoder-decoder mode. Encoder produces hidden states; the decoder **autoregressively**
  emits tokens, with **residual connections injecting the encoder's final-layer features into each decoder
  layer** (Fig 1B). Output positions are pinned by sentinel tokens; the decoder fills each sentinel's span
  in order. Decoder-specific prediction head → vocabulary logits → CE/focal loss.
- **What it can generate (token sequences only — NOT scalars, see §2 [FLAG]):**
  1. **Protein sequences** — the PPI **generation** pretraining task: given an input protein, generate an
     *interacting* protein (trained on STRING positive pairs only; 390M samples). This is a genuine
     sequence-generation capability over proteins.
  2. **Antibody CDR infilling ("Ab Infilling")** — the flagship generative *benchmark*. CDR regions are
     replaced by sentinel/MASK tokens; the model generates the missing CDR amino-acid sequences given the
     antigen + the antibody framework (FR) regions. Metric: **CDRH3-AAR** (amino-acid recovery, fraction of
     correctly predicted residues in the masked CDR). Dataset: SAbDab subset. **MAMMAL CDRH3-AAR 0.446 vs
     SOTA (dyMEAN) 0.375 → +19.0%** (the single largest improvement in Table 1). Per-CDR detail (Table S4):
     CDRH1 0.832 / CDRH2 0.742 / **CDRH3 0.446** / CDRL1 0.780 / CDRL2 0.844 / CDRL3 0.724 (CDRH3 is the
     hardest, most variable region — hence the headline).
  3. **General masked-span infilling / molecule editing** — the unified prompt supports multi-sentinel
     infilling for any entity (the T5 span-corruption objective generalized); the LM pretraining tasks are
     all span-masking (mean span 5, density 0.15) over proteins, antibodies, SMILES, and ranked gene lists.
  4. **Denoising** — the Antibody Denoise pretraining task: corrupt an antibody AA sequence (sample
     t∈[1,500], uniformly corrupt tokens with prob ∝ t) and reconstruct it.
- **What generation is NOT (verify-before-claiming):** the paper does **not** demonstrate de-novo
  *small-molecule* generation as a benchmark (SMILES LM is a pretraining objective, but there is no
  molecule-generation downstream task in Table 1). PPI "generation" produces a protein *sequence*, not a
  structure or a scalar. No public checkpoint exists for the generative Ab-infilling / PPI-gen heads
  (consistent with the checkpoint survey: only the 7 discriminative/regression heads + 2 per-target
  classifiers are downloadable).

---

## 5. The 11 benchmark tasks — exact metrics + SOTA deltas (Table 1)

Table 1 (main paper). "Imp." = |SOTA−MAMMAL|/SOTA, MAMMAL counts as outperforming when Imp. > 1%. MAMMAL
values are means ± std over 3 random seeds unless the benchmark prescribes cross-validation. **↑ higher is
better; ↓ lower is better (NRMSE only).** SOTA bracketed values are the prior model's reported CI.

| # | Benchmark | Domain | Type | Metric | SOTA | MAMMAL | Imp. | MAMMAL wins? |
|---|---|---|---|---|---|---|---|---|
| 1 | Cell type | GE | cls | ↑ F1 | 0.710 | **0.763 ± 0.012** | 7.5% | ✅ |
| 2 | BBBP | SM | cls | ↑ AUROC | 0.937 | **0.957 ± 0.006** | 2.2% | ✅ |
| 3 | ClinTox | SM | cls | ↑ AUROC | 0.948 | **0.986 ± 0.007** | 4.0% | ✅ |
| 4 | Cancer-Drug Response 1 | GE+SM | reg | ↑ Pearson | 0.887 | **0.917 ± 0.001** | 3.4% | ✅ |
| 5 | Cancer-Drug Response 2 | GE+SM | reg | ↑ Pearson | 0.900 | **0.931 ± 0.000** | 3.4% | ✅ |
| 6 | Cancer-Drug Response 3 | GE+SM | reg | ↑ Pearson | 0.923 [0.917–0.929] | 0.928 ± 0.000 | 0.5% | ➖ tie (<1%) |
| 7 | Ab Infilling | Protein | **gen** | ↑ CDRH3-AAR | 0.375 | **0.446 ± 0.002** | **19.0%** | ✅ |
| 8 | AbAg Bind | Protein | cls | ↑ AUROC | 0.924 [0.923–0.925] | **0.928 ± 0.002** | 0.4% | ➖ tie (<1%) |
| 9 | TCR Bind | Protein | cls | ↑ AUROC | 0.862 [0.85–0.868] | **0.879 ± 0.003** | 2.0% | ✅ |
| 10 | PPI ΔΔG | Protein | reg | ↑ Pearson | 0.663 | **0.852 ± 0.002** | **28.5%** | ✅ |
| 11 | DTI | Prot.+SM | reg | ↓ NRMSE | 0.942 ± 0.028 | **0.906 ± 0.011** | 3.8% | ✅ |

**SOTA-on-9, comparable-on-2.** The two "comparable" (Imp. < 1%) are **Cancer-Drug Response 3** (0.928 vs
0.923) and **AbAg Bind** (0.928 vs 0.924). 9 wins are tasks 1,2,3,4,5,7,9,10,11.

**Per-task notes that matter for skepticism:**
- **DTI (task 11)** uses the **PEER split** of BindingDB; metric is **NRMSE = RMSE / std(test labels)**,
  so 0.906 means MAMMAL's error is ~9.4% below the naive "predict-the-mean" baseline (NRMSE=1). The paper
  itself frames this as "solid improvement of 3.8% over the SOTA." → consistent with Quiver's read that
  DTI SOTA here is "least-bad on a hard task," not a strong binder oracle. Norm constants: PEER uses
  mean/std the head was trained on (Quiver uses 6.286/1.542); cold-split differs.
- **PPI ΔΔG (task 10, +28.5%)** is on **SKEMPI S1131** (1131 single-point mutations), 10-fold CV, Gibbs
  ΔΔG = ΔG_mutant − ΔG_wild-type, **sequence-only** input (no structure). The huge delta is vs a weak
  sequence-only prior (0.663); structure-based methods are not the comparator.
- **TCR Bind (task 9)** is the Weber benchmark (TDC `tcrepitope`): 47,182 pairs, 192 epitopes, 23,139
  unique β-chains, 50% negatives by random pairing, 10-fold CV. Reported metric is the **β-chain epitope
  binding** classification head only (the fine-tune also did mask-infilling + CDR3 tasks). 0.879 vs SOTA
  0.862; result falls outside SOTA's CI → "statistically significant 2%."
- **Cancer-Drug Response 1/2/3** = GDSC1 / GDSC2 (via TDC) / a DeepCDR subset; stats Table S3:
  CDR1 958 cell lines × 208 drugs × **177K** pairs; CDR2 805 × 137 × **92K**; CDR3 561 × 223 × **107K**.
  Predicts continuous IC50 (Pearson) from **gene-expression profile + drug SMILES only** (no other omics).
- **BBBP / ClinTox** are MoleculeNet (MolFormer's splits). Comparator (SOTA) is **MolFormer** (0.937 /
  0.948); MAMMAL 0.957 / 0.986. (Quiver reproduced 0.968 BBBP held-out — slightly above paper.)
- **Cell type** = Zheng68k (68,579 PBMC cells, 11 types; 20,387 non-zero genes), 5-fold CV; predicts a
  Cell Ontology label (e.g. `CL:0001062`). MAMMAL F1 0.763 vs SOTA 0.710. Table S2: MAMMAL acc 0.856 /
  F1 0.763 vs scBERT 0.759/0.691, CIForm 0.820/0.710.
- **Ab Infilling** is the only **generative** benchmark (see §4).

**[FLAG] Reproducibility scope:** Only 4 of 11 tasks ship a public checkpoint Quiver could verify off the
shelf (DTI, BBBP, ClinTox, TCR — all reproduced). The other 7 (Cell type, 3× Cancer-Drug Response, Ab
Infilling, AbAg Bind, PPI ΔΔG) have training code but **no published weights** — unverifiable without
retraining. The paper's own Discussion concedes evaluation "is limited to models that publicly report
results on these tasks, and claims of state-of-the-art performance should therefore be interpreted within
this scope." Take that caveat seriously.

---

## 6. The 6 pretraining datasets / 7 tasks (Table 3 + Supp §3) — with sample counts

**Headline: pretrained on 2 billion samples, 6 datasets, 7 tasks, simultaneously (multitask, gradients
aggregated across tasks before each optimizer step).** Table 3 (npj main paper):

| Task name | Domain | Entity | Task type | Dataset | # Samples (post-filter) |
|---|---|---|---|---|---|
| Protein LM | Biologic | General protein | Spans-masking LM | UniRef90 | **180M** |
| Antibody LM | Biologic | Antibody | Spans-masking LM | OAS | **650M** |
| Small Molecule LM | Small molecules | Small molecule | Spans-masking LM | ZINC22 + PubChem | **200M** |
| Cell Genes LM | Single-cell transcriptomics | Cell genes | Spans-masking LM | CELLxGENE | **30M** |
| Protein-Protein Interaction | Biologic | General protein | Classification | STRING | **780M** |
| Protein-Protein Interaction Gen. | Biologic | General protein | Generation | STRING | **390M** |
| Antibody Denoise | Biologic | Antibody | Denoise sequence | OAS | **650M** |

Sum ≈ 2.88B listed; the paper's headline "2 billion" is the de-duplicated/effective figure ("post-filtering
number of samples actually used … A single model was pretrained with all of the listed tasks"). The 7
tasks map onto **6 distinct datasets** (OAS is reused for Antibody LM + Antibody Denoise; STRING for PPI
class + PPI gen). Note Table 3 lists **7 tasks** but the main text §6 and Supp §3.4 also say "seven tasks"
— consistent.

**Dataset construction details (Supp §3.3, exact):**
- **UniRef90** — UniProt clusters at ≥90% identity / 80% overlap with the seed; reduces redundancy.
- **OAS (Observed Antibody Space)** — unpaired antibody variable regions (heavy/light); filtered to
  complete variable domains + standard AAs only → **~650M** sequences, each annotated heavy/light + species.
- **STRING** — PPI; **390M positive** pairs (STRING confidence > 500) + **390M pseudo-negative** (random
  same-species pairs) → **780M** for the classification task; the generation task uses **390M positives
  only** (learn to generate an interacting protein given an input protein).
- **CELLxGENE** — human samples labeled "cell" in `suspension_type` → **30M** cells; sequences are
  **ranked lists of gene names** (Geneformer-style) but **log-normalized + binned** then alphabetically
  sorted on ties (binning removes read-count noise; alphabetic sort guarantees a unique correct answer per
  masked token).
- **Small molecules** — PubChem subset of **80M** drug-like (Lipinski rule-of-five) + **120M** sampled from
  ZINC22 (<30 heavy atoms) → **200M** total.
- **LM objective:** span-denoising like T5 — **mean noise span length 5, noise density 0.15**; a special
  token per entity type makes the model aware of the modality (e.g. `<MOLECULAR_ENTITY_TYPE_ANTIBODY_HEAVY_CHAIN>`),
  plus species tokens (e.g. `<ATTRIBUTE_ORGANISM_HUMAN>`).
- **Antibody Denoise** — corrupt with t∈[1,500], prob ∝ t (a diffusion-flavored discrete corruption schedule).

**Infrastructure / hyperparameters (Supp §3.1–3.2):**
- Trained on an **OpenShift cluster, 3 months, 2 nodes × 16 A100-80G GPUs** (32 A100s total), FuseMedML +
  PyTorch, **FSDP**.
- **AdamW**, β1=0.9, β2=0.999, weight decay 0.01, gradient-clip norm 1.0, **2K warmup steps**, **cosine
  decay to 10% of max LR**. Per-task max sequence length + per-task batch size (tuned to GPU memory).
  (Max LR value itself not stated. **[FLAG]** — fine-tune LR for DTI was 0.0004 per main text §DTI.)

---

## 7. AlphaFold-3 comparison (Table 2 + Fig 2 + Supp Tables S5–S7)

**Framing (be precise — this is NOT a head-to-head structure task).** AF3 is not a binding classifier;
the authors *derive* a binary binder/non-binder signal from AF3's **structure-confidence scores** (ipTM,
pTM) and compare it, **zero-shot**, against a **fine-tuned, sequence-only** MAMMAL. So it's "fine-tuned
sequence model vs zero-shot structure-confidence proxy." The paper is explicit that this is "relative
discriminative power for binding prediction rather than … the underlying modeling approaches."

**Table 2 — per-target AUROC, MAMMAL vs AF3, on held-out antibody/nanobody–antigen test subsets:**

| Target | Length (AA) | n | pos | MAMMAL AUROC | AF3 AUROC | ΔAUROC | p-value (DeLong) |
|---|---|---|---|---|---|---|---|
| HER2 ECD | 630 | 60 | 30 | **0.93** | 0.45 | +0.42 | 1.5×10⁻⁶ |
| Albumin | 609 | 28 | 11 | **0.91** | 0.59 | +0.32 | 7.4×10⁻³ |
| CD206 | 1,456 | 37 | 14 | **1.00** | 0.59 | +0.41 | 1.1×10⁻⁵ |
| EGFR | 1,210 | 28 | 11 | **0.94** | 0.49 | +0.45 | 2.2×10⁻⁵ |
| TBG | 384 | 32 | 5 | 0.63 | **1.00** | −0.37 | 1.0×10⁻⁴ |
| TNFα | 233 | 34 | 13 | 0.86 | 0.87 | −0.01 | NS (>0.1) |
| VWF | 2,813 | 34 | 13 | **0.83** | 0.32 | +0.51 | 3.9×10⁻⁶ |

**Result: MAMMAL beats AF3 on 5 of 7 targets** (HER2, Albumin, CD206, EGFR, VWF — all statistically
significant). AF3 wins decisively only on **TBG** (rigid globular antigen, AF3 1.00 vs MAMMAL 0.63);
**TNFα** is a tie (NS). The abstract phrases this as "significantly outperform AF3 … in five of seven
antigen targets."

**Mechanistic reason the paper gives (Fig 2):** for HER2, AF3 places binders *and* non-binders at the
*same* region of the ECD, distinct from the known trastuzumab/pertuzumab epitopes → AF3 can't discriminate
(AUROC 0.45). AF3 struggles with proteins containing intrinsically disordered regions (IDRs, 30–40% of the
proteome); MAMMAL (a protein-language-model-style approach) handles IDRs better. AF3's bias toward
true-positive PDB complexes + single static conformation is the proposed failure mode.

**Supp Tables S5–S7 (deeper AF3 ablation):**
- **S5 (HER2, AUROC/AUPRC):** MAMMAL **fine-tuned 0.881 / 0.915** vs MAMMAL **pre-trained 0.530 / 0.509**
  (fine-tuning is essential — zero-shot MAMMAL is near chance) vs AF3 variants: Heavy-only ipTM 0.448 /
  pTM 0.496; Heavy+Light ipTM 0.504 / pTM 0.497; a "Control: AF3 H CD206" run at ipTM 0.455 / pTM 0.66.
  (Note: S5 HER2 MAMMAL-fine-tuned AUROC 0.881 here vs **0.93 in Table 2** — Table 2 used a downsampled
  60-example balanced test set; S5 may be the fuller set. **[FLAG — the two HER2 numbers differ (0.881 vs
  0.93); the paper does not reconcile them explicitly.]**)
- **S6 (nanobody–antigen AUROC, 6 targets):** MAMMAL fine-tuned beats AF3 ipTM/pTM on Albumin (0.914),
  CD206 (0.997), EGFR (0.941), VWF (0.832); AF3 wins on TBG (ipTM 1.0) and TNFα (0.874). MAMMAL pre-trained
  is near-chance throughout (0.428–0.663) — again, fine-tuning carries it.
- **S7 (same, AUPRC):** consistent pattern.

**Honest read for Quiver:** the AF3 comparison is real and statistically clean, but it is *narrow* —
a sequence binder classifier (fine-tuned per antigen-set) vs AF3's structure-confidence repurposed
as a classifier it was never built to be. It says "for binder/non-binder triage on disordered or
large/glycosylated antigens, a fine-tuned sequence model can beat AF3-confidence," **not** "MAMMAL >
AlphaFold-3 at structure." And it depends entirely on fine-tuning (pre-trained MAMMAL ≈ chance, S5–S7).

---

## 8. Cross-cutting flags / things the paper is vague about

1. **No layer/head/d_model/vocab/FFN counts published** — only "458M params" + d_model=768 (figure
   example). Read `models/base_458m/` config locally if exact dims are needed. **[FLAG]**
2. **Scalar outputs are encoder-only** — the generative decoder cannot emit scalars (Supp §1, "future
   generations"). Yet Table S1 shows DTI/CDR decoder labels as `SCALARS_LITERALS` literals — the
   encoder-scalar-head path vs the prompt-literal path are not fully reconciled. **[FLAG]**
3. **"2B samples" vs Table 3 summing to ~2.88B** — headline is the effective/de-dup figure; the per-task
   rows are pre-dedup. Minor but worth knowing if anyone quotes the number.
4. **HER2 AUROC 0.881 (S5) vs 0.93 (Table 2)** — differ; likely different test subsets (downsampled
   balanced 60 vs fuller), not stated. **[FLAG]**
5. **7 of 11 benchmark heads have no public checkpoint** — Cell type, Cancer-Drug Response 1/2/3, Ab
   Infilling, AbAg Bind, PPI ΔΔG. Cannot be independently reproduced off-the-shelf. Paper concedes this.
6. **Max LR not given** (warmup/decay schedule is; the value isn't). Fine-tune LRs given per-task in a few
   cases (DTI 0.0004). **[FLAG]**
7. **The whole results table is fine-tuned-per-task MAMMAL**, not zero-shot. Every Table 1 / Table 2 number
   is a model "fine-tuned from ibm/biomed.omics.bl.sm.ma-ted-458m for the corresponding task" (Table 1
   footnote). Pre-trained-only MAMMAL is near-chance on the hard tasks (S5–S7). This is *the* most
   decision-relevant caveat: MAMMAL's headline numbers are a fine-tuning story, exactly matching Quiver's
   empirical Phase-1/3 conclusion that the base model is commodity and the value (where any) is per-target
   fine-tuning.

---

*Written for the Q-MAMMAL evaluation (Quiver Bioscience). Primary sources: npj Drug Discovery 2026;3:14
(DOI 10.1038/s44386-026-00047-4) + its Supplementary Information; arXiv 2410.22367. All numbers transcribed
from the PDFs read on 2026-06-01.*
