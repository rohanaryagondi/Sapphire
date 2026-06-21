# Untested model candidates per track — online survey (2026-06-14)

What the literature/community rates highly that we **haven't tested yet**, per track. Builds on
[`community_consensus_2026-06-13.md`](community_consensus_2026-06-13.md) (which confirmed our
current winners). Ordered within each track by expected ROI for Quiver. "Tested" = in the
scorecard registry; don't re-run those.

---

## Track 1 — Protein family clustering  · current best: ESM-2-650M (0.875, saturated)
- **xTrimoPGLM** (1B/3B/10B) — the one embedding model in the 2025 crystallization benchmark we skipped. **Low expected upside**: same benchmark found ESM-2 (150M/3B) gave the best 3–5% gains and our 40/167-gene panels are already saturated at ~0.875 (scale doesn't move it). Test only if curious; cheap-ish for the 1B.
- **Verdict: largely closed.** Saturation + the function-vs-fold E3-ligase ceiling are model-agnostic. SaProt/ProstT5 already own the GPCR-structure niche.
- Sources: [PLM crystallization benchmark (Sci Rep 2025)](https://www.nature.com/articles/s41598-025-86519-5)

## Tracks 2/3 — DTI / structure binding  · current best: Boltz-2 (Nav1.8 0.714, mTOR 1.000)
The richest area. The 2025 Mac1 prospective study found **AF3 ≈ Boltz-2 ≈ Chai-1 all reproduce >50% poses, but Boltz-2's affinity head best separates true ligands from false positives** — Boltz-2 stays our affinity winner. Untested alternatives worth a cross-check:
- **IPBind** (2025) — geometric DL on interatomic potentials, explicitly claims **generalization to unseen proteins**. *This is the Nav-relevant claim* (Nav has ~0 training pairs). Highest-interest cross-check.
- **GatorAffinity** (bioRxiv 2025) — geometric scoring trained on 450K synthetic Boltz-1 complexes + 1M SAIR; a pure affinity scorer (no co-fold) → much faster than Boltz-2.
- **Interformer** (Nature Comms 2024) — interaction-aware docking + affinity in one model.
- **Chai-1 / Chai-2** — co-folding peers; Chai-1 open-source (non-commercial license — coordinate w/ boltz branch + Quiver legal). Would only be a Boltz-2 cross-check, unlikely new science.
- **NeuralPLexer** — co-folding diffusion; pose-focused, weaker affinity separation than Boltz-2.
- **In flight (this campaign):** BALM + DrugCLIP — the *shared-cosine-space* angle (compound↔target embedding), a different question from co-folding.
- Sources: [Mac1 prospective co-folding eval (bioRxiv 2025)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12776374/), [GatorAffinity](https://www.biorxiv.org/content/10.1101/2025.09.29.679384v1), [Interformer (Nat Commun)](https://www.nature.com/articles/s41467-024-54440-6), [Boltz-2](https://pmc.ncbi.nlm.nih.gov/articles/PMC12262699/)

## Track 4 — BBBP de-risking  · current best: MolFormer-XL (0.889) + MAMMAL backstop
- Field is moving to **mechanism-aware / multimodal** BBB models (2025 review) rather than a new SOTA classifier. Reported >97% accuracies (DeePred-BBB etc.) are **in-distribution** — our external-panel + applicability-domain finding (transformers competitive, not dominant; fingerprints match) still holds.
- **Verdict: low priority.** A descriptor-augmented MolFormer (+3–5% claim) is the only cheap nudge.
- Sources: [DL for BBB review 2025](https://arxiv.org/abs/2507.18557), [ML BBB review (Mol Inf 2025)](https://onlinelibrary.wiley.com/doi/full/10.1002/minf.202400325)

## Track 5 — Toxicity / hERG / DILI  · current best: ChemBERTa-2 (hERG bal-acc 0.726) + ADMET-AI
**Real upgrade opportunity, cheap.** Dedicated hERG models report well above our 0.726:
- **deephERG** — multitask DNN, AUC 0.967 (in-dist).
- **XGBoost_Morgan / Transformer_Morgan** (2025) — beat ADMETlab3.0, Cardpred, CardioDPI; acc 0.84–0.85, AUC 0.93.
- **CardioTox net** — meta-feature ensemble, robust hERG blockade.
- **BayeshERG** — Bayesian, gives calibrated uncertainty (useful for a de-risking gate).
- **Worth testing**: run one dedicated hERG model on **our external-30 withdrawn-drug panel** (the harsh test where ChemBERTa hit 0.726) — does it actually beat 0.726 out-of-distribution? Cheap (CPU/local-equivalent, AWS ~$0.30).
- Sources: [cardiotoxicity DL 2025](https://www.sciencedirect.com/science/article/pii/S2095177925000802), [CardioTox net](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8365955/), [ML cardiotox scoping review (MDPI 2025)](https://www.mdpi.com/2305-6304/13/12/1087)

## Track 6 — KG / hypothesis  · current best: PROTON (neuro-KG, ranking-only; forward = hub noise)
- **BioPathNet** (Nature BME 2025) — **the standout**. NBFNet path-based reasoning on PrimeKG; **beats TxGNN by 5.9–22.6 pts on indication prediction**, and being *path-based* it's explainable AND should resist the hub-bias that breaks PROTON's forward direction. Best Track-6 upgrade candidate. Medium setup (PrimeKG + NBFNet).
- **TxGNN** (Nature Med) — clinician-centered, 17,080-disease zero-shot repurposing on PrimeKG. The general-disease complement to PROTON's neuro niche.
- **Worth testing**: BioPathNet on PrimeKG for general repurposing + a hub-bias re-check on our 22 Quiver targets (does path-based avoid Bepridil-for-everything?).
- Sources: [BioPathNet (Nat BME 2025)](https://www.nature.com/articles/s41551-025-01598-z), [TxGNN (Nat Med)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11326339/)

## Track 7 — Cross-modal V1-T trace → compound (THE MOAT)  · current best: nothing public works
- **Tahoe-x1** (Tahoe Therapeutics, bioRxiv Oct 2025, **on HuggingFace** `tahoebio/Tahoe-x1`, up to 3B params) — perturbation-trained single-cell foundation model, pretrained on **Tahoe-100M** (100M cells × 1,100 small-molecule perturbations × 50 cancer lines). **The only external model that natively ingests cell-state + drug perturbation** — the closest thing to a trace↔compound bridge. Caveat: cancer-cell-line trained → CNS-transfer risk (V1-T is neuronal). Apache-ish; verify license.
- **chemCPA** — encoder-decoder that predicts transcriptional response to *unseen* drugs (compound-structure-aware). A lighter prior-art bridge.
- **Status: still build-don't-buy**, but Tahoe-x1 is now released and is the one external model worth a pilot — **blocked on paired (V1-T trace, compound) data from Mahdi.** When that lands, Tahoe-x1 is the first thing to fine-tune/probe.
- Sources: [Tahoe-x1 (bioRxiv)](https://www.biorxiv.org/content/10.1101/2025.10.23.683759v1.full.pdf), [Tahoe-x1 HF](https://huggingface.co/tahoebio/Tahoe-x1), [chemCPA (Nat Commun)](https://www.nature.com/articles/s41467-024-53457-1)

## Track 8 — Generative chemistry  · current best: Morgan FP + Enamine REAL (skip)
- **GenMol** (NVIDIA, discrete diffusion) — beats all 28 baselines incl. SAFE-GPT/REINVENT on goal-directed + fragment-constrained generation.
- **NovoMolGen** (1.5B molecules) — SOTA unconstrained + goal-directed Mol-LLM.
- **Verdict: still skip** (generation isn't a Quiver bottleneck) — but if Track 8 ever opens, GenMol/NovoMolGen are the picks, not SAFE-GPT/REINVENT.
- Sources: [GenMol](https://arxiv.org/html/2501.06158v1), [NovoMolGen](https://arxiv.org/html/2508.13408v2)

## Track 9 — Off-target / selectivity  · current best: Boltz-2 (folded into Track 2)
- Strong **kinase**-selectivity tooling exists — **KinomePro-DL** (multitask DNN, 191 kinases), **KinomeX** (140K pts, 391 kinases), **KinasePred** (ML + XAI). All kinome-wide.
- **Verdict: not our lane.** Quiver's selectivity question is **Nav paralogs (ion channels)**, not kinases — these kinase models don't transfer. Boltz-2 paralog ranking stays the pick. Flag KinomePro-DL only if a kinase target enters the pipeline.
- Sources: [KinomePro-DL](https://pubmed.ncbi.nlm.nih.gov/39320984/), [AI kinase selectivity review 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12412618/)

---

## Recommended next tests (highest ROI, beyond BALM + DrugCLIP already running)
1. **Track 5 — a dedicated hERG model** (deephERG or XGBoost/Transformer-Morgan) on our external-30 panel. Cheap (~$0.30), could beat ChemBERTa's 0.726 out-of-distribution → a real de-risking-layer upgrade.
2. **Track 2/3 — IPBind or GatorAffinity** as a fast affinity cross-check that claims unseen-protein generalization (the Nav blind spot). Validates/challenges Boltz-2 without per-pair co-folding.
3. **Track 6 — BioPathNet on PrimeKG** for general repurposing + a hub-bias re-check vs PROTON. Medium setup; the one rated model that should beat PROTON's forward-direction failure.
4. **Track 7 — Tahoe-x1** is *ready* but **gated on Mahdi's paired V1-T data**. Flag for when that lands — it's the moat play.

Skip: xTrimoPGLM (Track 1 saturated), new BBBP classifiers (in-dist only), GenMol/kinase models (not current bottlenecks).
