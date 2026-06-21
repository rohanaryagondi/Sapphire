# MAMMAL — Complete Understanding (Quiver Bioscience)

**The authoritative top-level reference.** Written 2026-06-01, integrating the Phase 0–5 empirical
evaluation, the 2026-06-01 adversarial audit, the five literature-lane deep-dives
(`docs/lit/0*.md`), and the new Phase 6 experiments (cross-modal alignment, generation, ESM-2 650M,
PGK2 full eval, WDR91 re-verify). It ties everything together; it supersedes nothing — the
phase-specific writeups in `results/` and the lit docs remain the detailed receipts.

> **Provenance & confidence convention.** Every empirical claim cites its experiment, n, and a
> confidence tag: **[HIGH]** (large/clean n, reproduced, or convergent evidence), **[MED]**
> (real but small-n or single-test), **[LOW]** (suggestive, wide CI, or confounded), **[PAPER]**
> (author-reported, not independently verified by us), **[SPEC]** (inference, not measured).
> Where this run contradicts or refines a prior claim, it is flagged **⟲ REVISION** inline.
> Team bar throughout: *empirical results on Quiver problems, not paper benchmark badges.*
> Mantra: *"state-of-the-art on shit is still shit."*

---

## 1. Executive verdict

**MAMMAL is commodity enrichment for Quiver, not core infrastructure — and the one strategic claim
that would have made it more (a shared protein↔molecule latent space for Sapphire) is now
empirically falsified.** Off the shelf, MAMMAL earns a narrow, real keep: a convenient single
interface for fast ADMET-style **de-risking** (BBB-penetrance as a *positive* signal), **sensible
protein/gene embeddings** that cluster targets by functional family (and now demonstrably hold their
own against a size-matched ESM-2 650M), and a **weak cross-target DTI re-ranker**. **Per-target
fine-tuning works as a chemotype-triage gate** — IBM's PGK2 head is a clean existence proof: it
fires sharply on its trained chemotype and rejects the PGK1 homolog at AUROC 0.97. That is the
ceiling of MAMMAL's usefulness, and it is genuinely useful in its lane.

But the value tracks task *difficulty*, not the SOTA badge. MAMMAL is **not a binding oracle**
(single-target binder-vs-decoy triage ≈ chance, confirmed three independent ways now), its
classification heads emit **uncalibrated hard 0/1 labels that mislead out-of-distribution**, it
**cannot generate** usable molecules off the shelf (the public weights expose only grammar-valid
span-infilling, not de-novo design), and **there is no off-the-shelf shared embedding space where a
target and its ligands are neighbors** — protein and SMILES occupy near-orthogonal subspaces. The
field agrees by its silence: 15+ months out, MAMMAL has ~6–8 passive citations, three lifetime
GitHub issues, and zero independent benchmarks — *this Quiver project is the most rigorous external
audit of MAMMAL that exists.* For the two jobs Quiver most wants (single-target binder triage;
structure/affinity scoring), named open specialists — **ConPLex** and **Boltz-2** — beat MAMMAL
while being equally or more open.

**Exact role for Quiver:** a downstream enrichment/representation layer behind David's single
interface — (1) protein/gene-family embeddings for the CRISPR-N panel and the Sapphire KG, (2) BBBP
as a soft positive de-risking signal in a property funnel, (3) optionally an in-house per-target
**chemotype-triage** fine-tune on Quiver screening/DEL data, evaluated by enrichment factor on a
held-out *scaffold* split. The moat stays Quiver's functional trace data + V1-T; MAMMAL enriches
insights, it is not the insight.

### The three strongest caveats (read these before deploying anything)

1. **Benchmark AUROC ≠ deployable per-compound filter.** Every classification head ranks well on its
   own dataset yet fails out-of-distribution: BBBP has a false-positive bias (held-out TNR 0.70,
   passes peripherally-restricted drugs as "penetrant"); ClinTox is pure memorization (0% sensitivity
   to external clinical toxics); the per-target heads re-recognize their trained chemotype with no
   graded potency. Treat molnet scores as binary labels, validate on scaffold splits, expect
   in-distribution-only reliability. **[HIGH — convergent across Phase 4/5/6 and the domain-context
   field ceilings.]**

2. **The "shared latent space" Sapphire pitch is not real off-the-shelf.** Phase 6 cross-modal
   alignment is a clean negative: binders are not systematically closer to their target than decoys,
   the two proximity readouts are *anti-correlated* (Spearman −0.90), and the modalities are
   near-orthogonal (cross-modal cosine 0.08). MAMMAL's molecule-side representation is weak (loses to
   Morgan fingerprints) and there is no protein↔molecule bridge to exploit. **[HIGH.]**

3. **The per-target "fine-tuning works" evidence is real but in-distribution and small-n, and one of
   the two public heads is near-broken.** PGK2's 0.97 / spike-in EF5 11× are measured on its *own
   training hits* vs out-of-distribution negatives (chemotype recall, not novel-hit discovery); WDR91
   is weak (median binder score ≈ 0; it barely fires; beaten by PGK2 molecules at AUROC 0.18). Novel-
   scaffold recall — the thing that would make this a discovery tool — remains **untested**. **[MED.]**

---

## 2. What MAMMAL is (architecture, modalities, numbers, generation, the 11 tasks)

From the primary-source deep-read (`docs/lit/01_paper_deepread.md`; npj Drug Discovery 2026;3:14,
DOI 10.1038/s44386-026-00047-4 + Supplementary; arXiv 2410.22367) and the upstream-code lane
(`docs/lit/05_upstream_code.md`).

**One-line identity.** MAMMAL is a single **458M-parameter T5-style encoder + autoregressive
decoder** seq2seq transformer, pretrained on **~2B samples** across **6 datasets / 7 tasks** spanning
proteins, antibodies, small molecules, and single-cell gene expression, that reframes *every*
biomedical task (classification, regression, generation) as text-to-text over a **modular
multi-domain tokenizer** — with a headline trick: **scalars are projected directly into the embedding
space via a learned `Linear(1→768)`** (no discretization). Fine-tuned per task, it reports SOTA on
9 of 11 benchmarks. **458M is the only published size; there is no v2 and no larger MAMMAL.** [PAPER]

### Architecture (the structural facts that matter)
- **T5 lineage, explicit** (Methods §4.1): inherits text-to-text framing + span-corruption
  pretraining (mean span 5, density 0.15), adds (1) representation+generation in one model, (2)
  flexible multi-domain prompts, (3) numerical-value integration.
- **Two modes, one shared encoder.** *Encoder-only* mode → a token-prediction head (vocab logits)
  plus an *optional* scalar-prediction head (regression). *Encoder-decoder* mode → the autoregressive
  decoder generates, with **encoder final-layer features injected via residual connections into each
  decoder layer**. **Weight sharing across modes** is the design crux — the same encoder serves both
  the classification/regression heads and the generative decoder.
- **This is exactly why the per-target heads behave as generative classifiers:** the trained signal
  lives in the shared encoder + generative decoder; the scalar regression head is left
  untrained/vestigial. (Verified at the code level, `docs/lit/05`.)
- **Concrete dims mostly unpublished [FLAG]:** 458M params and **d_model = 768** are confirmed (figure
  example + our 768-d embeddings); layer/head/FFN/vocab counts are *not* in the paper — read
  `models/base_458m/` config locally if needed, don't cite a number the paper doesn't give.
- **Max sequence length is per-task** ("effective yet efficient"), not global. Our DTI head
  empirically truncates protein to 1250 aa / SMILES to 256 tokens. Truncation during pretraining was
  randomized + flagged with `<SEQUENCE_NATURAL_START/END>` tokens.

### Numerical-value projection (the headline innovation)
- **Inputs:** a prompt parses into parallel (token-IDs, input-scalars-with-NaNs) sequences; token IDs
  → learned embedding; scalars → a learned `Linear(1→768)`; **the two are ADDED, not concatenated.**
  This ingests arbitrary continuous values (binding affinities, expression, ΔΔG) with no new vocab and
  no sequence-length inflation — the explicit contrast with digit-tokenization, critical for
  gene-expression prompts with "thousands of scalars."
- **Outputs:** an encoder-side scalar-prediction head emits a scalar per input element (MSE/RMSE
  loss). **Key limitation [FLAG, author-disclosed]:** scalar *outputs* are an **encoder-only**
  capability — the generative decoder cannot emit scalars ("future generations"). This is the root of
  the per-target-head trap.
- **⟲ Verified gap (Phase 6 code lane):** `project_input_scalars` exists in the weights but is
  exercised by **zero shipped tasks** — DTI's input uses a bare `<MASK>`, gene-expression uses ranked
  gene *names*. If Quiver wants to inject a real covariate (dose, concentration), this is the intended
  hook, but **we'd be the first to exercise it** — validate on a toy monotonic task first. [SPEC→action]

### Modular tokenizer + prompt syntax
- One unified vocabulary across sub-tokenizers (SMILES "C" and cysteine "C" share an ID); a meta token
  `<@TOKENIZER-TYPE=AA|SMILES|GENE|SCALARS_LITERALS>` switches the active sub-tokenizer. Entities are
  typed and nested (`<MOLECULAR_ENTITY>` → type token; `<COMPLEX_ENTITY>`; attributes like `<BBBP>`,
  `<TOXICITY>`, `<BINDING_AFFINITY_CLASS>`). The tokenizer is **extensible per fine-tune** — new task
  tokens like `<WDR91_ASMS>`, `<PGK2_DEL>` are added without disrupting existing function.
- **Sentinels are the output anchors:** a single `<SENTINEL_ID_0>` marks where the model emits a
  classification/regression answer; multiple sentinels enable multi-span infilling. This is the
  mechanism behind Quiver's validated readout: prompt with task token + `<SENTINEL_ID_0>`,
  `model.generate`, read **P(`<1>`) at classification position 1** (the class token lands at index 1;
  index 0 is the sentinel echo — confirmed in `mammal/model.py` and `molnet_infer.py`).

### Generation (what the decoder can actually do)
- **Mechanism:** encoder-decoder mode, autoregressive, output positions pinned by sentinels.
- **What the *paper* claims:** protein-sequence generation (PPI-gen, STRING positives), antibody CDR
  infilling (the flagship generative benchmark, CDRH3-AAR), general masked-span infilling, denoising.
  **It generates token sequences only — NOT scalars.**
- **⟲ What the *public artifact* actually exposes (Phase 6 generation + code lane — NEW):** the repo
  ships **no free-generation example, no checkpoint, no test** for any generative-output task. The
  base model genuinely does **local span-infilling** (grammar-valid) but **not accurate
  reconstruction**, and has **no usable de-novo prior** (details in §5). The antibody-design/PPI-gen
  heads that carry the paper's generation headline are **not public** → **untestable.** [HIGH]

### The 11 benchmark tasks (Table 1 — all *fine-tuned-per-task* MAMMAL, [PAPER])
| # | Benchmark | Domain | Type | Metric | SOTA | MAMMAL | Win? |
|---|---|---|---|---|---|---|---|
| 1 | Cell type | scRNA | cls | F1↑ | 0.710 | 0.763 ± .012 | ✅ |
| 2 | BBBP | small-mol | cls | AUROC↑ | 0.937 | 0.957 ± .006 | ✅ |
| 3 | ClinTox | small-mol | cls | AUROC↑ | 0.948 | 0.986 ± .007 | ✅ |
| 4 | Cancer-Drug Response 1 | GE+SM | reg | Pearson↑ | 0.887 | 0.917 | ✅ |
| 5 | Cancer-Drug Response 2 | GE+SM | reg | Pearson↑ | 0.900 | 0.931 | ✅ |
| 6 | Cancer-Drug Response 3 | GE+SM | reg | Pearson↑ | 0.923 | 0.928 | ➖ tie |
| 7 | **Ab Infilling** | protein | **gen** | CDRH3-AAR↑ | 0.375 | 0.446 | ✅ (+19%) |
| 8 | AbAg Bind | protein | cls | AUROC↑ | 0.924 | 0.928 | ➖ tie |
| 9 | TCR Bind | protein | cls | AUROC↑ | 0.862 | 0.879 | ✅ |
| 10 | **PPI ΔΔG** | protein | reg | Pearson↑ | 0.663 | 0.852 | ✅ (+28.5%) |
| 11 | DTI | prot+SM | reg | NRMSE↓ | 0.942 | 0.906 | ✅ (3.8%) |

**Skeptic's read:** the two biggest wins are over weak/dated baselines (PPI ΔΔG +28.5% vs BindProfX,
a non-DL method, sequence-only; Ab infilling +19% vs dyMEAN). The small-molecule wins are single
digits over IBM's own MolFormer on known-saturated MoleculeNet splits. DTI NRMSE 0.906 means error
only ~9.4% below predict-the-mean — "least-bad at a hard task." **Only 4 of 11 tasks ship a public
checkpoint** (DTI, BBBP, ClinTox, TCR) — the other 7 are unverifiable off-the-shelf, a caveat the
paper itself concedes.

### Pretraining (Table 3, [PAPER])
~2B effective samples (rows sum to ~2.88B pre-dedup): Protein LM (UniRef90, 180M), Antibody LM (OAS,
650M), Small-Molecule LM (ZINC22+PubChem, 200M), Cell-Genes LM (CELLxGENE, 30M), PPI classification
(STRING, 780M), PPI generation (STRING positives, 390M), Antibody Denoise (OAS, 650M). Trained 3
months on 32× A100-80G, FSDP, AdamW, cosine decay. The headline numbers are a **fine-tuning story** —
pre-trained-only MAMMAL is near-chance on the hard tasks (Supp S5–S7, AF3 comparison), matching our
empirical Phase 1/3 conclusion that the base model is commodity and the value is per-target fine-tuning.

### AlphaFold-3 comparison (Table 2, [PAPER] — framing matters)
MAMMAL (fine-tuned, sequence-only) beats AF3 (zero-shot, structure-confidence ipTM/pTM repurposed as
a binder classifier) on **5 of 7 antibody/nanobody–antigen targets** (HER2, Albumin, CD206, EGFR,
VWF; AF3 wins only TBG; TNFα ties). This says "a fine-tuned sequence model beats AF3-confidence for
binder triage on disordered/large/glycosylated antigens," **NOT** "MAMMAL > AlphaFold-3 at
structure." It depends entirely on fine-tuning (pre-trained MAMMAL ≈ chance, S5–S7).

---

## 3. Competitive positioning (per modality)

From `docs/lit/02_competitive_landscape.md`. **Bar = the frontier today, not the paper's chosen
baseline.** MAMMAL is a competent fully-open generalist, beaten by the frontier specialist in 4 of 5
modalities; its only genuine differentiator is breadth-in-one-checkpoint with a shared tokenizer —
and that breadth has **no demonstrated competitive payoff** (no published result shows cross-modal
transfer beating two specialists).

| Modality | Frontier today | Verdict vs MAMMAL |
|---|---|---|
| **Proteins** | ESM-2/ESM-C (open), ESM-3 98B (generative design, gated) | Specialists are the commodity backbone. **But ⟲ NEW: size-matched ESM-2 650M does NOT beat MAMMAL on our off-the-shelf mean-pool family-clustering recipe (§5).** ESM-3 owns design. |
| **Small molecules** | Uni-Mol2 (3D), ChemBERTa-3 (fair-benchmark harness) | MAMMAL's molecule wins are narrow + same-lab (beats IBM's MolFormer by single digits). Morgan fingerprints beat MAMMAL embeddings for similarity. Frontier is 3D/graph-aware, which MAMMAL doesn't attempt. |
| **Single-cell** | Arc Institute STATE (167M cells), scGPT/scFoundation | MAMMAL's weakest position — one head among seven, dwarfed in data/focus. (Caveat that *helps* the skeptical frame: scRNA-FMs themselves underperform linear baselines zero-shot — Nature Methods 2025.) No reason to pick MAMMAL here. |
| **DTI / binder triage** | **ConPLex** (open, ESM-2-based, built for decoy specificity + proteome-scale screening) | **Sharpest case against MAMMAL for Quiver.** ConPLex targets the exact capability MAMMAL fails (single-target, decoy-resistant). On its own benchmark MAMMAL even *loses* to the PEER baseline. **If DTI is the use case, evaluate ConPLex.** |
| **Structure + affinity** | **Boltz-2** (MIT license, commercial; AF3-class structure + near-FEP affinity, 1000× faster) | **The most important competitor to flag.** Does structure (MAMMAL can't) *and* affinity (MAMMAL does poorly), fully open. For "target → score a molecule," Boltz-2 is strictly more capable and equally open. |

**Net:** MAMMAL is not the best at anything Quiver needs. The reason to use it is convenience (one
interface, de-risking heads, sensible embeddings), not per-modality superiority. And the shared space
is "not even shared with the data that matters" — MAMMAL has no trace modality and never will.

---

## 4. Reception & external critique

From `docs/lit/03_reception_critique.md`. **The headline finding of this lane is the silence.**

- **Near-zero independent scrutiny.** 15+ months after the preprint, ~6–8 citations (OpenAlex: 6 on
  preprint, 0 on npj yet; Semantic Scholar ~8) — **every one passive** (survey / related-work / one
  option in a pipeline). **No second group has downloaded MAMMAL, run it on their own data, and
  published whether it held up.** The GitHub repo (107★, 29 forks, still maintained by IBM, last push
  2026-05-28) has had **3 issues in its entire lifetime**, all usage questions, zero bug reports. The
  HF base model (~2,280 dl/mo, 48 likes) has zero defect reports. **This Quiver project is the most
  rigorous external audit of MAMMAL that exists.** [HIGH]
- **Why it matters operationally:** if we hit a problem, there is no community to draw on — we found
  this firsthand (macOS TF-deadlock, PEER-vs-cold-split trap, vestigial-scalar-head trap — all
  undocumented, all solved in-house). The unified-prompt interface plausibly raises adoption friction
  (you can't `model.encode(seq)` like ESM-2), which both explains the silence and is a soft strike
  against MAMMAL as shared infrastructure.
- **The per-target heads are undocumented orphan uploads.** `wdr91_asms` / `pgk2_del_cdd` are **not in
  the MAMMAL paper** (zero hits searching arXiv for WDR91/PGK2/DEL/ASMS/CACHE/AIRCHECK), have **no
  model card, 0 likes, ~6 dl/mo, no training recipe.** Provenance traced [SPEC, high-confidence]:
  WDR91 ← public **AIRCHECK** DEL data (Wellnitz et al. 2025 — a **UNC/SGC/HitGen/Pfizer LightGBM**
  effort, **NOT IBM, NOT MAMMAL**; IBM reused the data) + Ahmad 2023 actives; PGK2 ← **CACHE Challenge
  #7** (1,388 hPGK2 DEL hits, de-enriched vs PGK1 — the exact count our experiments use). **They are
  demonstrations on borrowed public benchmark data, not productized or peer-reviewed capabilities.**
- **No v2, no larger model.** 458M is it. IBM's broader BMFM family (84M small-molecule predecessor;
  110–113M DNA/RNA — a *separate* lineage) does not change the verdict. There is no bigger MAMMAL coming.
- **Two independent lines converge:** our experiments (it's narrow) and the field's silence ("published,
  not adopted") reach the same read — **commodity enrichment.**

---

## 5. Complete empirical scorecard

Every capability we tested, with the receipt. **This table is the synthesis of Phases 0–6 with the
audit corrections applied.** Confidence and n are explicit. Where the audit downgraded a number, the
corrected reading is shown.

| Capability | Off-the-shelf verdict | Best number (with the honest caveat) | n / confidence | Receipt |
|---|---|---|---|---|
| **BBB-penetrance (BBBP)** | ⚠️ Soft **positive** signal, **NOT** a rule-out gate | Held-out AUROC **0.968** (paper 0.957); but **TNR 0.70**, false-positive bias (passes cetirizine/atenolol/domperidone); hard 0/1 (95% saturated); protonation-sensitive | n=204 balanced [HIGH]; literature direction-test n=11+ [MED] | `phase1b_molnet_bbbp`, `phase4_bbbp_literature` |
| **ClinTox toxicity** | ❌ **Not usable** as a tox gate | AUROC ~1.0 is **memorization** of ~112 training toxics → **0% sensitivity to external clinical toxics** (misses cerivastatin, terfenadine, thalidomide…); hard 0/1; encoding-fragile | tox fold ~10 positives; external n=7 (0/7 caught) [MED, but mechanism convincing] | `phase4_clintox_literature`, `phase4_molnet_audit` |
| **ClinTox-FDA** | ➖ Trivial | AUROC ~1.0 but 94% positive (~9 negatives) — not meaningful | n=148, ~9 neg [HIGH it's trivial] | `phase1b_molnet_fda` |
| **Solubility** | ✅ Functional ~baseline; **calibrated** | acc **0.734** / AUROC **0.829** (~at/just below DeepSol ~0.77); 17% saturated | n=1992 balanced [HIGH] | `phase3_solubility` |
| **TCR-epitope** | ➖ Works, low Quiver relevance | AUROC **0.931** (paper 0.879); 28% saturated (calibrated) | n=400 balanced [HIGH] | `phase1c_tcr_epitope` |
| **Protein/gene embeddings** | ✅ **Usable** — recovers functional family | NN recall **0.92**, intra−inter gap **0.463** | n=25/5 families [MED — small n] | `phase2c_protein_embedding` |
| **— vs ESM-2 8M** | ✅ MAMMAL wins | 0.92 vs 0.88 NN recall. ⟲ **Audit: the NN-recall win is 1 protein of 25 = noise; the gap 0.463 vs 0.093 is the real signal** | n=25 [LOW on NN, MED on gap] | `phase5_esm_comparison` |
| **— vs ESM-2 650M** ⟲ **NEW** | ✅ **MAMMAL wins — overturns the "bigger ESM wins" expectation** | MAMMAL **0.92** vs ESM-650M **0.84** NN recall (centering ESM makes it *worse*, 0.76). Scaling ESM 8M→650M *lowered* clustering. **Sapphire embedding blocker cleared.** | n=25 [MED — direction solid, CIs overlap; naive mean-pool is ESM's weakest mode] | `phase6_esm650_comparison` |
| **DTI single-target triage** | ❌ **No** (≈ chance) | Nav1.8 +0.00 / mTOR +0.10 binder-vs-decoy separation; truncation ruled out | 7 binders / 4 decoys per target [LOW n but safe direction] | `phase2b_quiver_targets` |
| **DTI cross-target re-rank (PEER)** | ⚠️ Coarse re-rank only | Spearman **0.43** on 10 pairs. ⟲ **Audit: n=10, p=0.21, 95% CI [−0.28, 0.80] — NOT significantly ≠ 0. Most over-leveraged number in the repo.** In-dist control 0.61 (n=20) proves pipeline works; the *task* is hard | n=10 [LOW] | `phase1_peer_comparison`, `phase1_indistribution` |
| **DTI NRMSE reproduction** | ✅ Reproduces (~at field ceiling) | ~0.88 (paper 0.906); ~9% better than mean (R²≈0.18). ⟲ **Audit: NEEDS-RERUN — no JSON artifact, md-narrative only** | [MED — unbacked by raw file] | `phase1_calibration` (narrative) |
| **Compound similarity** | ❌ Use Morgan fingerprints instead | Morgan **0.96** vs MAMMAL **0.72** same-class NN | n=25/5 [MED — 6-NN gap safe] | `phase2a_similarity` |
| **Per-target: PGK2 (`_del_cdd`)** ⟲ **NEW full eval** | ⚠️ **The strong existence proof** — chemotype-triage gate | Homolog selectivity (vs PGK1) **AUROC 0.973, CI [0.96, 0.985]**; **fires sharply** (94% of hits >0.5, median ≈1.0); spike-in **EF5 11.0×**; **but Spearman vs DEL count −0.07 (no potency ranking)** — and positives are **in-distribution** (its own training hits) | hits n=500 (in-dist), PGK1 n=99, decoys n=500 [HIGH on the numbers; in-dist caveat load-bearing] | `phase6_pgk2_fulleval` |
| **Per-target: WDR91 (`_asms`)** ⟲ **re-verified** | ⚠️ Weak / barely fires | SPR (Ahmad 2023) AUROC **0.816**, EF5 **4.57×** — *bit-identical reproduction*. ⟲ **Audit confirmed: 92% of scores <0.001, binder median ≈ 0.0003, top non-binder (0.319) outranks all but one binder → ranking-only, NOT a binder that "fires."** On real binders vs PGK2 mols, AUROC **0.18 (inverted)** | binders n=38 / non n=201 [MED ranking; the head is operationally weak] | `phase5_wdr91_spr`, `phase6_wdr91_spr_reverify`, `phase3_realdata_specificity` |
| **Per-target graded potency** | ❌ **No** (both heads) | Spearman(score, DEL count/pKd) ≈ 0 / −0.07 / −0.15 — saturates near 1.0, cannot order compounds it calls "active" | [HIGH — convergent] | `phase3_pgk2_indist`, `phase6_pgk2_fulleval` |
| **Cross-modal alignment** ⟲ **NEW** | ❌ **No shared binding space** (the Sapphire core claim) | Per-target AUROC ≈ chance (mean 0.570); two readouts **anti-correlated (Spearman −0.90)**; cross-modal cosine **0.08** (near-orthogonal subspaces); target-specificity ≈ chance (mean rank 3.15 vs 3.5) | 6 targets×6 families; WDR91 n=64/PGK2 n=40 anchors [HIGH] | `phase6_crossmodal_alignment` |
| **Generation (de-novo molecule)** ⟲ **NEW** | ❌ **No** | Greedy → single atom; forced length → invalid garbage. "valid_rate 1.0" is hollow (a lone atom parses) | 8 drugs, ≤12 samples [MED — mode is clear] | `phase6_generation` |
| **Generation (SMILES infill)** ⟲ **NEW** | ⚠️ Valid *analogs*, not reconstruction | Format-valid 8/8, RDKit-valid 8/8, **exact recovery 1/8** (trivial span); short-span aspirin → 5-Cl/5-OH/5-Br analogs, **0/8 recover parent**. Zero property conditioning | [MED] | `phase6_generation` |
| **Generation (protein infill)** ⟲ **NEW** | ⚠️ Plausible residues, ≈ chance recovery | AAR ≈ 0.07 sampling (chance for 20 AA); greedy collapses to homopolymers; AAR 1.0 only on hyper-conserved ubiquitin (memorized) | 3 proteins [MED] | `phase6_generation` |
| **Generation (antibody CDR / PPI — paper headline)** | 🚫 **Untestable** | Design heads not public — only base + 9 task heads ship | — [PAPER, unverifiable] | `phase6_generation`, `docs/lit/05` |
| **Model health control** | ✅ Healthy | Base PPI calmodulin–calcineurin → `<1>`, P1 = 0.946 — rules out load/decode artifacts in the generation probes | [HIGH] | `phase6_generation_probe2` |
| **Feeding functional traces** | ❌ No trace modality | Confirmed at the code level — modalities are AA/SMILES/GENE(ranked)/scalars/cell-attributes only. **That's V1-T's job, never MAMMAL.** | [HIGH] | `docs/lit/05` |

### Domain-context calibration (what the numbers *buy* in a real campaign)
From `docs/lit/04_domain_context.md`. The field ceilings recontextualize MAMMAL's headline numbers:
- **WDR91 EF 5.25× / PGK2 spike-in EF 11×:** field mean EF ≈ 6 at top 2%; 10–50× = "very good"; 6×
  was "noteworthy" prospectively. So MAMMAL's triage is **real but ordinary** (PGK2's 11× is squarely
  good, WDR91's 5× is normal) — not a moat. **AUROC is the wrong headline for screening; quote EF/BEDROC.**
- **PGK2 in-distribution AUROC 0.97:** the field's 0.97 came *with* potency ranking + prospective nM
  hits (X-Chem/Google 2020); MAMMAL's comes *without* either. **Same shape, far less payload.**
- **DTI "9% better than the mean":** **normal** for cold/PEER-split DTA — the whole field is bad here
  (best hard-split BindingDB Pearson ≈ 0.51). A property of the field, not a MAMMAL defect.
- **BBBP 0.957:** a **commodity** number a 30-line Random Forest matches on a known-saturated/leaky
  benchmark. TNR 0.70 is the real deployment story.
- **ClinTox AUROC 1.0:** *prima facie impossible* → memorization. No honest clinical-tox model exceeds
  ~0.80 out-of-distribution (DILI ceiling ~0.79–0.80; hERG ~0.835–0.95). **Treat 1.0 as a red flag,
  not a result.** Independently corroborates our "0% external sensitivity" finding.

---

## 6. The cross-modal-alignment finding and what it means for the Sapphire pitch

**This is the single most decision-relevant new result of this run, and it is a clean negative.**

The Sapphire vision's strongest version of "use MAMMAL as the latent-space layer" requires that a
target and its ligands be **neighbors in a shared embedding space** — so you could retrieve candidate
binders for a gene/target by proximity, or co-embed targets and molecules into one KG geometry.
**Phase 6 tested exactly this on the base model and it does not hold:**

- **The modalities are near-orthogonal.** Within-molecule cosine 0.72, within-protein 0.28, but *any*
  protein↔*any* molecule cosine sits in a tight band at **0.08** [0.013, 0.182]. There is barely a
  shared axis on which binding-specific "closeness" could live.
- **Binders are not closer than decoys.** Separate-encode per-target AUROC averages **0.570** with
  half the targets at/below chance and PGK2 *inverted* (binders farther than decoys, AUROC 0.225).
- **The two proximity readouts are anti-correlated (Spearman −0.90).** Targets that look "aligned"
  under separate-encoding (EGFR, ESR1) are the *most inverted* under joint-encoding, and vice-versa.
  A coherent shared binding space would make the two measures *agree*; they do the opposite. The
  apparent positives (ESR1, EGFR) are **chemotype clustering** (steroids/SERMs, anilinoquinazolines
  differ from generic decoys), not binding.
- **Target-specificity ≈ chance:** a binder's own target is its nearest only ~50% of the time
  (above 17% chance) but its *mean* rank among 6 targets is 3.15 vs 3.5 chance — once past the single
  best hit, no better than a coin flip.
- **It corroborates the supervised side:** MAMMAL's *purpose-built* DTI head also fails single-target
  binder-vs-decoy separation (Nav1.8 +0.00, mTOR +0.10). If even the trained binding head barely
  separates, the unsupervised geometry has no reason to — and it doesn't.

**What this means for the pitch, precisely:**
1. **A shared protein/ligand retrieval space is NOT something to buy MAMMAL for.** That specific
   Sapphire framing is off the table off-the-shelf. [HIGH]
2. **What Sapphire *can* still use MAMMAL for is single-modality structure:** protein/gene embeddings
   cluster by functional family (NN 0.92) and now survive a size-matched ESM-2 650M challenge (§5) —
   good enough to proceed for CRISPR-N gene-clustering / KG node features **without** a parallel ESM
   dependency. The KG geometry MAMMAL supports is *protein-side* (gene/target similarity), not
   cross-modal (target↔ligand).
3. **The honest caveat both ways:** the negative is a *global mean-pool* result; it does not prove no
   signal exists in some learned token-level projection. But the supervised DTI head — trained to
   extract exactly that — also fails, so a strong hidden recoverable signal is unlikely. And the
   embedding win is "as good as ESM up to 650M on a small panel with naive mean-pool," not "MAMMAL >
   ESM as protein encoders." Don't over-claim either direction.

---

## 7. What is settled that MAMMAL CANNOT do

High-confidence negatives, convergent across phases / the audit / the field:

1. **Single-target binder triage** ("does compound X bind target Y, decoy-resistant"). ≈ chance.
   Confirmed three ways: DTI head (Phase 2b), unsupervised cross-modal geometry (Phase 6), and the
   field ceiling (DTA is hard for everyone). [HIGH]
2. **Graded potency / lead ranking.** The per-target heads saturate near 1.0 and carry zero graded
   signal (Spearman ≈ 0). Lead optimization — where ranking is most valuable — is exactly where these
   heads stop helping. [HIGH]
3. **A shared protein↔molecule (cross-modal) latent space.** Near-orthogonal subspaces, anti-correlated
   readouts. [HIGH]
4. **De-novo molecule generation off-the-shelf.** The public base model produces grammar-valid
   *analogs* via span-infill but collapses on unconditional generation, with zero property
   conditioning. The paper's design heads are not public. [HIGH for public weights]
5. **Calibrated per-compound probabilities from the small-molecule classifiers.** BBBP/ClinTox emit
   hard 0/1 (95–100% saturated) — not usable as thresholds or rankings. [HIGH]
6. **Out-of-distribution classification reliability.** Every head ranks well in-distribution and fails
   per-compound OOD (BBBP over-passes, ClinTox under-detects, per-target heads only recognize trained
   chemotype). [HIGH]
7. **Toxicity gating (as shipped).** ClinTox is memorization with 0% external sensitivity;
   recalibration won't fix no-generalization. [HIGH]
8. **Anything with functional trace data.** No trace modality, by architecture. [HIGH]
9. **Verifying 7 of 11 paper tasks** (Cell type, 3× Cancer-Drug Response, Ab Infilling, AbAg Bind, PPI
   ΔΔG) — no public checkpoint. Flag, don't chase. [PAPER, unverifiable]

---

## 8. Open questions and recommended next steps

| # | Open question | Status / what's known | Recommended next step |
|---|---|---|---|
| **Q14** | **In-house per-target fine-tune** — does fine-tuning on Quiver screening/DEL data give deployable binder triage? | **Leans YES for chemotype-triage** (PGK2 is the clean existence proof: fires sharply, 0.97 homolog selectivity, EF5 11×). **NOT** novel-hit or potency. But all positive evidence is **in-distribution**; **novel-scaffold recall is untested** — the live decision. | **Pilot it.** Binary hit/non-hit, SMILES+label, generative readout. `carcinogenicity` example is the closest template (swap TDC `Tox` for our parquet). **Evaluate by EF/BEDROC on a held-out *scaffold* split** (not random — random is what makes 0.97/11× optimistic). This is the single highest-value next experiment. |
| 1 | **DTI re-ranker — is the 0.43 real?** | ⟲ Audit: n=10, p=0.21, CI crosses 0. The most over-leveraged number in the repo; a load-bearing capability rests on a non-significant point estimate. | Re-run on **≥50–100 diverse known pairs** (PEER-held-out classes), report Spearman **with CI/p**. If it collapses, the "re-ranker works" claim evaporates. **[HIGHEST re-verification priority.]** |
| 2 | **ESM at scale for Sapphire embeddings** | ⟲ NEW: 650M lost to MAMMAL on naive mean-pool (blocker cleared for now). But naive mean-pool is ESM's *weakest* mode; ESM-2 3B untested (won't fit on 18 GB). | If embeddings ever become *core* (not enrichment), re-test on the real **1400-gene CRISPR-N panel** with each model's *best* extraction (selected layer/whitened), not naive mean-pool. |
| 3 | **CRISPR-N at full scale** | Phase 5: homogeneous families (GPCR/kinase/ion-channel) cluster ~100%; heterogeneous functional groups (E3 ligases) fail. | Apply to the real **1400-gene CRISPR-N panel** — ready now for homogeneous families, manual interpretation for the rest. |
| 4 | **Tox gate replacement** | ClinTox unusable; no single filter catches 5+ mechanisms. Proposed mechanism-specific funnel (PAINS/BRENK → hERG rule → pkCSM DILI → BBBP). ⟲ Audit: the hERG rule's "perfect" TPR/TNR is on n=10, fit to that set — **NEEDS held-out validation.** | Validate the hERG/QTc rule on an independent cardiotox set before trusting it; source a calibrated DILI/P-gp model for the funnel's tox step. |
| 5 | **Numeric covariate injection** | `project_input_scalars` exists but **zero public tasks use it.** Intended hook for dose/concentration in a prompt; untested upstream. | If Quiver wants real-valued covariates in prompts, validate on a toy monotonic task first — we'd be the first to exercise this path. |
| 6 | **DTI NRMSE receipt** | ⟲ Audit: the one benchmark claim with no JSON artifact (md-narrative only). | Cheap fix — re-run `phase1_nrmse_verify.py`, dump JSON. Closes the gap. |
| 7 | **Unpublished-checkpoint tasks** (cell-type, cancer-drug-response, antibody design, PPI ΔΔG, generation heads) | No public weights → unverifiable without retraining. | **Note, don't chase.** Each is a standard 1-GPU fine-tune if ever needed. |

### Recommended posture (the one-paragraph action)
Deploy MAMMAL **as commodity enrichment behind David's single interface**: protein/gene-family
embeddings for the CRISPR-N panel + Sapphire KG (proceed; survived the ESM-650M challenge), BBBP as a
soft positive de-risking signal in a mechanism-specific funnel (not a rule-out gate, standardize
SMILES first), and **pilot one in-house per-target chemotype-triage fine-tune** on a Quiver target
with screening/DEL data, evaluated by enrichment factor on a scaffold split (Q14). **Do not** adopt
MAMMAL for single-target binder triage (evaluate ConPLex), structure/affinity scoring (evaluate
Boltz-2), molecule generation, a cross-modal retrieval space, or anything touching functional traces.
Re-power the DTI Spearman before citing it as a capability. The moat stays V1-T + functional trace
data; MAMMAL enriches insights, it isn't the insight.

---

## Document map (where the detail lives)
- **Entry point:** `HANDOFF.md` · **AI orientation:** `CLAUDE.md` · **Synthesis (Phase 0–5):** `docs/FINDINGS.md`
- **Audit (claim-by-claim, what to trust):** `docs/audit_findings.md`
- **Lit lanes:** `docs/lit/01_paper_deepread.md` (architecture/tasks), `02_competitive_landscape.md`,
  `03_reception_critique.md`, `04_domain_context.md` (field ceilings), `05_upstream_code.md` (real APIs)
- **Phase 6 (this run):** `results/phase6_crossmodal_alignment.md`, `phase6_generation.md`,
  `phase6_esm650_comparison.md`, `phase6_pgk2_fulleval.md`, `phase6_wdr91_spr_reverify.md`
- **Checkpoints:** `docs/mammal_checkpoint_survey.md` · **Per-experiment receipts:** `results/README.md`

*Written for the Q-MAMMAL evaluation (Quiver Bioscience), 2026-06-01. Confidence tags and n are
explicit per claim; verified is distinguished from speculative throughout. This document ties the
work together; the cited writeups remain the authoritative detail.*
