# Competitive Landscape — MAMMAL vs the biomedical foundation-model field

**Lane: competitive landscape. Written 2026-06-01.** Positions IBM MAMMAL
(`ibm/biomed.omics.bl.sm.ma-ted-458m`, npj Drug Discovery 2026, arXiv 2410.22367) against the
leading specialist and foundation models in each modality it touches. Companion to
`docs/FINDINGS.md` (our empirical Quiver results) and `01_*` (paper deep-dive).

**Bar, per the team mantra:** "state-of-the-art on shit is still shit." Paper benchmark badges are
not the question; the question is whether MAMMAL is genuinely distinctive (one shared multimodal
space) or whether per-modality specialists simply beat it. Short answer up top, receipts below.

---

## The one-paragraph verdict

**MAMMAL is a generalist that is competitive-but-not-leading in every modality, and beaten by the
frontier specialist in most of them.** It is a 458M-param T5-style encoder-decoder that shares ONE
tokenizer/vocabulary across proteins, antibodies, small molecules, and single-cell gene expression
— that breadth-in-one-checkpoint is its only genuine differentiator. But 458M is one to two orders
of magnitude smaller than the modality leaders (ESM-3 98B; State trained on 167M cells; AlphaFold3/
Boltz are structural, a capability MAMMAL lacks entirely). On its OWN paper benchmarks MAMMAL's
wins are mostly small single-digit deltas over *task-specific* baselines (BBBP +2.2 pts vs MolFormer,
DTI it actually *loses* by 3.8% NRMSE to the PEER baseline), and the field has moved past several of
those baselines since. Its multimodal-in-one-space story is real architecturally but **unproven where
it would matter** — there is no public benchmark showing cross-modal transfer (e.g. protein knowledge
improving the molecule head) beats running two specialists. For Quiver this confirms the existing
read: commodity enrichment, not core infrastructure.

---

## Per-modality comparison tables

Notation: **MAMMAL score** = the number from its own paper (arXiv 2410.22367, Table reproduced in
`01_*`). "Beats MAMMAL?" judges the *frontier today*, not the paper's chosen baseline. Open-ness is
the practical axis Quiver cares about (can we download weights, use commercially).

### (a) Proteins — embeddings, representation, design

| Model | Scale | What it does | Open / license | Vs MAMMAL |
|---|---|---|---|---|
| **MAMMAL** | 458M | AA-sequence embeddings, solubility, PPI ΔΔG, antibody infilling, TCR/Ab binding | Apache-2.0, fully open | baseline here |
| **ESM-2** (Meta) | 8M–15B | MLM protein LM; embeddings, contact/structure features; the field's default backbone | Open (MIT), commercial OK | **Beats** for pure representation at scale; 650M already ≈ MAMMAL-protein and 15B far exceeds it |
| **ESM-3** (EvolutionaryScale) | **98B** (open variant ~1.4B) | Generative multimodal (seq+structure+function) "chain-of-thought" protein design | esm3-open = **non-commercial**; commercial = paid/Forge | **Beats** decisively on protein design/generation; but gated for commercial use |
| **ESM C** (Cambrian) | 300M / 600M / 6B | Successor embedding models, cheaper/faster than ESM-2 | 300M/600M open-weight, commercial OK | **Beats or matches** as a drop-in embedding backbone, more accessible than ESM-3 |
| **ProtT5** (Rost lab) | 3B | T5 protein LM, strong per-residue embeddings | Open | Comparable representation; older, narrower |

**Read:** MAMMAL's protein side is a *reasonable* embedding model but is not where anyone competes.
ESM-2/ESM-C are the commodity backbone (open, commercial-friendly); ESM-3 owns generative design.
MAMMAL's protein-adjacent *wins* in the paper are on niche tasks — PPI ΔΔG (+28.5% vs BindProfX, an
old non-DL method) and antibody infilling (+19% vs dyMEAN) — both against weak/dated baselines, not
against an ESM-3-class model. Our own Phase 2 found MAMMAL protein embeddings recover functional
family at NN 0.92, but `docs/FINDINGS.md` flags the open action item: **benchmark vs ESM-2 before
Sapphire commits** — the literature predicts ESM-2/C win.

### (b) Small molecules

| Model | Scale | What it does | Open | Vs MAMMAL |
|---|---|---|---|---|
| **MAMMAL** | 458M (shared) | SMILES embeddings, property heads (BBBP, ClinTox), molecule generation | Apache-2.0 | baseline here |
| **MolFormer / MoLFormer-XL** (IBM) | ~47M, 1.1B SMILES | Linear-attention SMILES encoder; strong property prediction | Open weights | **The baseline MAMMAL beats** by ~2–4 pts on BBBP/ClinTox — but small margin, same lab |
| **ChemBERTa-2 / -3** | ~5–100M | BERT-style SMILES MLM; ChemBERTa-3 (2025) is a standardized open benchmark framework | Open | Comparable-to-below MAMMAL on MoleculeNet; ChemBERTa-3 matters as the *fair* benchmark harness |
| **Uni-Mol / Uni-Mol2** | ~50M–1.1B | **3D-aware** molecular representation (conformers) | Open | **Beats** on tasks where 3D geometry matters; MAMMAL is SMILES-only (no conformers) |
| **MolE** | — | Graph-transformer molecular foundation model, self-supervised | Open | Competitive on MoleculeNet; graph inductive bias MAMMAL lacks |

**Read:** MAMMAL's molecule wins are real but *narrow and same-lab* — it beats IBM's own MolFormer by
single digits on two MoleculeNet tasks. The frontier here is 3D/graph-aware (Uni-Mol2) which MAMMAL
does not attempt. Crucially, our Phase 2 found **Morgan fingerprints beat MAMMAL embeddings for
similarity (0.96 vs 0.72)** — i.e. for the cheapest cheminformatics baseline MAMMAL's molecule
representation is not even the right tool. Property heads are its only molecule edge, and those are
hard-0/1 uncalibrated (Phase 4).

### (c) Single-cell / gene expression

| Model | Scale | What it does | Open | Vs MAMMAL |
|---|---|---|---|---|
| **MAMMAL** | 458M (shared) | Cell-type annotation, transcriptomic lab-test prediction; gene-expression tokens | Apache-2.0 | baseline here |
| **scGPT** | ~50M, 33M cells | Generative scRNA foundation model; cell-type, integration, perturbation | Open | **Beats** on most scRNA tasks (purpose-built); the de-facto comparator |
| **Geneformer** | ~10–40M, ~30M cells | Rank-based gene-token transformer; in-silico perturbation | Open | **Beats/matches** on annotation; complementary to scGPT |
| **scFoundation** | ~100M, 50M cells | Large scRNA model, strong cross-batch embeddings | Open | **Beats** on integration-heavy tasks |
| **Arc Institute State (STATE)** | **167M cells obs + 100M perturb** | Virtual-cell perturbation prediction across 70 cell contexts; +50% on Tahoe-100M | Open | **Beats decisively** — this is the modality frontier MAMMAL is nowhere near |

**Read:** This is MAMMAL's weakest competitive position. Its single-cell capability is one head among
seven; the dedicated scRNA foundation models (let alone Arc's State, trained on >250M cells) dwarf it
in data and focus. Important caveat that *helps* the skeptical frame: the scRNA-FM field itself is
under fire — multiple 2024–2025 papers show scGPT/Geneformer **underperform simple linear baselines**
zero-shot for perturbation prediction and clustering (Nature Methods 2025; bioRxiv "Fundamental
Limitations"). So "specialists beat MAMMAL here" AND "the specialists themselves may be overhyped" are
both true. MAMMAL has no reason to be picked for single-cell work.

### (d) Drug–target interaction (DTI)

| Model | Scale | What it does | Open | Vs MAMMAL |
|---|---|---|---|---|
| **MAMMAL** | 458M (shared) | protein+SMILES → pKd regression / binding | Apache-2.0 | baseline here |
| **DeepPurpose** (toolkit) | varies | 15 encoders × 50 architectures for DTI; the standard library | Open | Library, not one model; provides the SOTA baselines MAMMAL is measured against |
| **MolTrans** | small | Substructure-interaction transformer, interpretable | Open | Comparable on benchmark DTI; older |
| **ConPLex** (Berger lab, PNAS 2023) | uses ESM-2 | **Contrastive protein-anchored co-embedding**; explicitly built for decoy specificity + proteome-scale screening | Open | **Beats MAMMAL on the exact thing we need** — single-target binder-vs-decoy discrimination, which MAMMAL fails (Phase 2b: Nav1.8/mTOR separation ≈ 0) |
| **PEER** (benchmark) | — | The DTI baseline in MAMMAL's paper | — | **MAMMAL LOSES to it**: NRMSE 0.906 vs PEER 0.942 is the paper's framing, but it's the only one of 11 tasks where MAMMAL does not clearly win, and our Phase 1 found the practical signal is weak (Spearman 0.43, ~9% better than predicting the mean) |

**Read:** DTI is where the competitive case against MAMMAL is sharpest *for Quiver specifically*. The
capability we want (does compound X bind target Y, decoy-resistant, single-target) is exactly
ConPLex's design goal — and ConPLex is open, ESM-2-based, and built for proteome-scale decoy
specificity. MAMMAL's DTI is a coarse cross-target re-ranker that fails single-target triage
(`docs/FINDINGS.md`). On its own benchmark it doesn't even lead. **If DTI is the use case, evaluate
ConPLex, not MAMMAL.**

### (e) Multimodal / cross-modal & structure

| Model | Scale | What it does | Open | Vs MAMMAL |
|---|---|---|---|---|
| **MAMMAL** | 458M | ONE shared vocab over protein/antibody/SMILES/gene; classification+regression+generation across modalities | Apache-2.0 | baseline here |
| **AlphaFold3** (DeepMind) | — | Joint structure of proteins+ligands+nucleic acids (diffusion) | **Closed** (non-commercial server, no commercial weights) | Different axis — structure, which MAMMAL cannot do; the gold standard for complexes |
| **Boltz-1 / Boltz-2** (MIT) | — | Open AF3-class structure; **Boltz-2 also predicts binding affinity** at near-FEP accuracy, 1000× faster | **MIT license, commercial OK** | **Beats MAMMAL on both structure AND affinity** — and is fully open. The most important competitor to flag |
| **BioMedGPT** (PharMolix) | ~10B (LLM-coupled) | Molecule/protein ↔ natural-language multimodal generative; QA + captioning | Open | Different flavor of multimodal (text-bridged, LLM-scale); broader language reasoning, weaker quantitative heads |
| **Galactica** (Meta, deprecated) | 120B | Scientific-text LLM (incl. some molecule/protein tokens) | Weights released, withdrawn | Largely abandoned; text-first, not a quantitative bio model |

**Read:** MAMMAL's claim to fame is "genuinely multimodal in ONE shared space," and architecturally
that is true and uncommon — most "multimodal" bio models either bridge through a text LLM (BioMedGPT)
or stitch separate encoders. **But the strategic threat is Boltz-2:** fully open (MIT, commercial),
it does structure (which MAMMAL can't) *and* binding affinity (which MAMMAL does poorly), at the
accuracy frontier. For the "target → assess a molecule" workflow Quiver discussed, Boltz-2 is a
stronger, more open, more capable tool than MAMMAL's DTI head.

---

## The central question: is MAMMAL distinctive (one shared space), or do specialists win per-modality?

**Specialists win per-modality. The shared space is real but its payoff is unproven.**

1. **Per modality, MAMMAL is beaten by the frontier in 4 of 5:** proteins (ESM-3/ESM-C), single-cell
   (State, scGPT/scFoundation), DTI (ConPLex for the triage we want; loses to PEER on its own
   benchmark), structure+affinity (Boltz-2). Only on a couple of *small-molecule property* tasks
   (BBBP, ClinTox) does it lead — and only by single digits over IBM's own MolFormer, against
   baselines the field has since standardized/surpassed (ChemBERTa-3).

2. **MAMMAL's wins cluster on weak/dated baselines and niche tasks.** Its largest paper margins —
   PPI ΔΔG +28.5% (vs BindProfX, a non-DL method) and antibody infilling +19% (vs dyMEAN) — are over
   comparators no one would call frontier. Its single-digit wins (BBBP, ClinTox, TCR, cancer-drug
   response) are exactly the "SOTA on a hard task = least-bad" pattern flagged in `docs/FINDINGS.md`.

3. **The one genuinely distinctive thing is breadth-in-one-checkpoint with a shared tokenizer.**
   MAMMAL covers protein + antibody + SMILES + gene expression in a single 458M model with a unified
   vocabulary and prompt syntax — you can in principle write a cross-modal prompt. That is rarer than
   it sounds: ESM does proteins only, scGPT cells only, Boltz structure only; BioMedGPT achieves
   multimodality by bolting modality encoders onto a text LLM (heavier, text-mediated).

4. **But "one shared space" has no demonstrated competitive payoff.** The paper does NOT show that
   training jointly improves any single head versus a specialist, nor that cross-modal transfer
   (protein knowledge helping the molecule head, or vice versa) beats just running two specialists.
   Every one of the 11 tasks is evaluated *within* its modality against a single-modality baseline.
   So the multimodality is an engineering convenience (one model to deploy, David's single interface)
   rather than a proven accuracy advantage. For a lab whose moat is functional trace data — a
   modality MAMMAL does not have and never will (no trace tokenizer; that's V1-T's job) — the shared
   space is not even shared with the data that matters.

**Net:** MAMMAL is a competent, fully-open, convenient generalist. It is not the best at anything
Quiver needs, and for the two workflows that matter most (single-target binder triage; structure/
affinity assessment) named open specialists — **ConPLex and Boltz-2** — beat it while being equally
or more open. This is consistent with, and sharpens, the project's standing verdict: **commodity
enrichment, not core infrastructure.** The reason to use MAMMAL at all is convenience (one interface,
de-risking property heads, sensible protein embeddings), not per-modality superiority.

---

## Practical implications for Quiver (so this lands)

- **Before adopting MAMMAL protein embeddings for Sapphire/KG → benchmark against ESM-2 650M / ESM-C
  600M first** (both open, commercial-OK). Literature strongly predicts they win; our NN-0.92 result
  needs that head-to-head. (Already an open item in `FINDINGS.md`; the landscape confirms its
  priority.)
- **For DTI / binder triage → evaluate ConPLex** (open, ESM-2-based, built for decoy specificity and
  proteome-scale screening) — it targets the exact capability MAMMAL fails at.
- **For "target → assess/score a molecule" with structure or affinity → evaluate Boltz-2** (MIT
  license, commercial, AF3-class structure + near-FEP affinity, 1000× faster than FEP). Strictly more
  capable and equally open than MAMMAL's DTI head for this job.
- **For single-cell / perturbation work → not MAMMAL.** Arc's State is the frontier; even it may not
  beat linear baselines zero-shot. This is V1-T / functional-trace territory anyway.
- **Where MAMMAL still earns its keep:** a single convenient interface for fast ADMET-style de-risking
  (BBBP as a soft positive signal), sensible off-the-shelf embeddings, and per-target chemotype-triage
  fine-tunes (the wdr91/pgk2 existence proof). Commodity enrichment — exactly as framed.

---

## Sources

MAMMAL: [npj Drug Discovery 2026](https://www.nature.com/articles/s44386-026-00047-4) ·
[arXiv 2410.22367](https://arxiv.org/html/2410.22367v1) ·
[GitHub BiomedSciAI/biomed-multi-alignment](https://github.com/BiomedSciAI/biomed-multi-alignment) ·
[HF ibm-research/…ma-ted-458m](https://huggingface.co/ibm-research/biomed.omics.bl.sm.ma-ted-458m).
Proteins: [ESM-3 (Science 2025)](https://www.science.org/doi/10.1126/science.ads0018) ·
[ESM-3 release](https://www.evolutionaryscale.ai/blog/esm3-release) ·
[ESM-3 license/weights](https://huggingface.co/EvolutionaryScale/esm3-sm-open-v1) ·
[ESM Cambrian / ESM C](https://www.evolutionaryscale.ai/blog/esm-cambrian) ·
[ESM-2 (Emergent Mind)](https://www.emergentmind.com/topics/protein-language-model-esm-2).
Small molecules: [MoLFormer (IBM GitHub)](https://github.com/IBM/molformer) ·
[ChemBERTa-3 (RSC Digital Discovery 2026)](https://pubs.rsc.org/en/content/articlehtml/2026/dd/d5dd00348b) ·
[ChemBERTa-2 (arXiv 2209.01712)](https://arxiv.org/pdf/2209.01712).
Single-cell: [scGPT (Nature Methods 2024)](https://www.nature.com/articles/s41592-024-02201-0) ·
[Arc Institute State](https://arcinstitute.org/news/virtual-cell-model-state) ·
[State (bioRxiv 2025)](https://www.biorxiv.org/content/10.1101/2025.06.26.661135v1) ·
[DL gene-perturbation vs linear baselines (Nature Methods 2025)](https://www.nature.com/articles/s41592-025-02772-6) ·
[Fundamental Limitations of scFMs (bioRxiv)](https://www.biorxiv.org/content/10.1101/2025.06.26.661767.full.pdf).
DTI: [DeepPurpose (Bioinformatics 2020)](https://academic.oup.com/bioinformatics/article/36/22-23/5545/6020256) ·
[ConPLex (PNAS 2023)](https://www.pnas.org/doi/10.1073/pnas.2220778120) ·
[ConPLex GitHub](https://github.com/samsledje/ConPLex).
Structure / multimodal: [Boltz-1 (MIT News)](https://news.mit.edu/2024/researchers-introduce-boltz-1-open-source-model-predicting-biomolecular-structures-1217) ·
[Boltz-2 (Cancer Grand Challenges)](https://www.cancergrandchallenges.org/news/boltz-2-democratising-the-future-of-drug-design) ·
[Boltz GitHub](https://github.com/jwohlwend/boltz) ·
[BioMedGPT (arXiv 2308.09442)](https://arxiv.org/pdf/2308.09442) ·
[OpenBioMed GitHub](https://github.com/PharMolix/OpenBioMed).
