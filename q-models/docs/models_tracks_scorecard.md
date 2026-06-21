# Quiver Model Capability Report — best-in-class models for CNS drug discovery

**Prepared for James and the Quiver team.**
Computational-models evaluation · CNS drug-discovery pipeline · **Last updated 2026-06-15**

This report answers one question for each computational capability in Quiver's CNS pipeline:
**what is the best available model, how well does it actually perform on Quiver-relevant data, and can
you trust its output?** Every verdict is empirical — measured on real CNS targets and compounds (ChEMBL
target panels, independent held-out datasets, knowledge graphs, Quiver screens), **not** on the paper
benchmarks the models were tuned to win. Where the best public model isn't good enough, we say so plainly
and name what to build instead.

> **Guiding principle.** These are commodity tools that *enrich* Quiver's proprietary insights — they don't
> replace Quiver's data advantage. State-of-the-art on a hard problem can still be inadequate, so every
> number below is on real substrate, and we flag the operating envelope (where each model is reliable and
> where it breaks) rather than quoting a single headline AUROC.

---

## Executive summary

We evaluated ~25 public and commercial models across **nine capabilities**. Each is routed to the best
model we found, with an honest confidence verdict.

| # | Capability | Best model | How it performs | Confidence |
|---|---|---|---|---|
| 1 | Protein family clustering | **ESM-2-650M** (≈ MAMMAL-458M) | NN-recall 0.875 (best-layer) | ✅ Reliable |
| 2 | DTI / binder triage | **Boltz-2** + **BALM** triage + **PLAPT** | kinase 0.80 / mTOR 0.72 / **ion-channel 0.50 (chance)** | ⚠️ Family-dependent |
| 3 | Structure-based binding | **Boltz-2** (per-fold) + **Boltz library-screen** (scale) | mTOR 1.000; Nav1.8 enrichment 0.81 via screen @ $0.025/mol (8× cheaper than per-fold) | ⚠️ Use with caution |
| 4 | BBB penetrance | **MapLight** | held-out B3DB 0.919 (vs MolFormer 0.854) | ✅ Reliable |
| 5 | Toxicity / DILI / hERG | **MapLight (hERG)** + **ADMET-AI / ChemBERTa-2 (DILI)** | hERG 0.89; DILI ext. 0.83 | ✅ Reliable (with domain flag) |
| 6 | KG / hypothesis generation | **PROTON + ULTRA** | PROTON ranks known drugs (med. 4.3%); ULTRA fixes hub bias + novel targets | ◑ Split (ranking only) |
| 7 | Generative chemistry | **Morgan FP** (analogs) + **Boltz design** (de-novo) | analog sim 0.96; de-novo 24/24 valid, 92% novel-scaffold @ $0.025/mol | ◑ Situational (not a bottleneck) |
| 8 | Off-target / selectivity | **Boltz-2** | ranks Nav1.8 #1, margins narrow (0.31–0.44) | ⚠️ Directional only |
| 9 | Variant effect (channelopathy) | **funNCion** | GoF/LoF AUROC 0.897; generic pLM only 0.665 | ⚠️ Public channels only |

**The three findings that matter most for the pipeline:**

1. **Ion-channel binder prediction is a build, not a buy.** Every off-the-shelf binding model sits at
   **chance (~0.50 AUROC)** on the CNS ion-channel family — exactly where Quiver works — while it does fine
   on kinases (0.80) and mTOR-pathway targets (0.72). This isn't a "we haven't found the right model" gap:
   a supervised model trained on held-out scaffolds reaches **0.92** on those same channels. The 0.50 → 0.92
   gap is the measured value of a Quiver-data fine-tune (Track 2).

2. **De-risking is solved, cheaply, with fingerprint models — not language models.** For BBB penetrance and
   hERG, a gradient-boosted fingerprint model (**MapLight**) beats every SMILES language model on independent
   held-out data and, critically, degrades far less on novel chemotypes. It runs on CPU at ~$0. The one
   non-negotiable is shipping a **confidence flag** based on chemical similarity to the training set
   (Tracks 4–5).

3. **Knowledge-graph hypothesis generation has two complementary winners.** **PROTON** (Quiver's neuro
   knowledge graph) ranks *known* drugs against well-studied targets; **ULTRA** (a zero-shot graph model)
   fixes PROTON's two failure modes — it doesn't collapse to the same promiscuous drugs for every target,
   and it can rank candidates for novel targets with no prior edges. Both are *shortlisting* tools, not
   binder predictors (Track 6). The commercial alternative (EMET, $150–500K/yr) is a wrong-fit for this use.

**What to build (no public model is good enough):** an ion-channel binder model fine-tuned on Quiver's
screening data; a Nav1.8 variant-effect model (Nav1.8 is absent from every public training set); and cardiac
multi-channel safety heads on Quiver's own data. See [§ What to build vs. buy](#build-vs-buy).

---

## Update — 2026-06-15: fine-tunes run + new models tested

We sourced more CNS data online and **executed the two fine-tunes** the build-vs-buy section calls for. The
results sharpen the strategy: **a fine-tune is decisive where a target has data, and nothing substitutes for
a target's own data where it doesn't.**

- **Ion-channel binder fine-tune (Track 2) — the lever, proven.** A supervised cross-channel model
  (ESM-2-650M target embedding ⊕ Morgan-FP ligand → MLP) trained on a pooled **online** corpus (full ChEMBL
  ion-channel set + Guide-to-Pharmacology, **21,556 pairs**) hits **scaffold-split AUROC 0.98** (Nav 0.98 /
  Cav 0.99 / NMDA 0.99) — versus **off-the-shelf 0.50** and a ligand-only fingerprint baseline 0.67. **But
  leave-one-channel-out transfer fails (0/4** — Nav1.8 0.36, NMDA 0.18 below chance): you cannot predict an
  unseen channel from the others. *(`results/ionchannel_finetune_characterization.md`.)*
- **Nav variant GoF/LoF fine-tune (Track 9) — informative negative.** On 2,212 pooled SCION+funNCion Nav/Cav
  variants, leave-one-gene-out AUROC **0.36** (below the ESM-2-LLR baseline 0.61) and held-out **Nav1.8
  transfer 0.48 ≈ chance**. GoF/LoF direction is channel-specific; public data does not transfer. Upgrades
  "Nav1.8 is build-don't-buy" from *labels absent* to *transfer demonstrably fails*.
  *(`results/variant_finetune_characterization.md`.)*
- **The conclusion (reinforces [§ What to build vs. buy](#build-vs-buy)):** the fine-tune lever is real and
  strong **per-target** (0.50 → 0.98); for a channel/target without data, neither other channels, nor
  zero-shot models, nor a generic pLM substitute. **Quiver per-target screening + electrophysiology is the
  irreplaceable input.**
- **New off-the-shelf models tested:** **ProTrek-650M** (Track 1) — not a clustering upgrade (0.725 < 0.875),
  but its **text-anchored family assignment cracks the function-defined families** (E3-ligase 0.75,
  nuclear-receptor 1.0), the first method past that ceiling. **CToxPred2** (Track 5) and **LigUnity** (Track 2,
  2025 ranking FM with a confirmed pocket-free path) — both banked on packaging/integration, no winner change.
- **More CNS data sourced** (free, headless, license-clean): Guide-to-Pharmacology ion-channel affinities,
  funNCion + ClinVar + **SCION** (the only public source with real Nav1.8 GoF/LoF labels), plus catalogued
  ExCAPE-DB / WelQrate / PubChem qHTS / ToxCast / MaveDB. See `docs/cns_data_sources.md` and
  `docs/overnight_summary_2026-06-15.md`.

- **Deployed LIVE in the Explorer (no AWS):** the fine-tunes are running, not just measured. The three
  SMILES-input tracks serve real predictions on CPU in-process — **Track 2 (DTI):** 15 per-target binder
  fine-tunes (0.95–0.997 scaffold CV); **Track 4 (BBBP):** MapLight-class 0.903; **Track 5 (tox):** hERG
  0.881 / DILI 0.934 — each Tanimoto-to-train confidence-gated, novel chemotypes routed to Boltz-2.
  (Family-clustering, structure, KG, and variant tracks need GPU/graph infra and stay AWS-served.) See
  `results/cns_pertarget_finetune_characterization.md`, `results/derisking_local_characterization.md`.

## How to read this report

Each track below is one capability. The entry gives **the question Quiver asks**, the **best model** (and
its license + how long a run takes), **how it performs** (the numbers, in context), and **how to use it** —
including the honest caveats and the confidence verdict:

| Badge | Meaning |
|---|---|
| ✅ **Reliable** | Use the number; the verdict is well-supported on Quiver substrate. |
| ⚠️ **Use with caution** | Best available, but marginal or directional — read the envelope. |
| ◑ **Split verdict** | Trust one direction only (e.g. ranking yes, prediction no). |
| ➖ **Low value** | Works, but not a Quiver bottleneck — deprioritized. |
| 🔨 **Build, don't buy** | Nothing public is good enough; this is where Quiver's data wins. |
| ⛔ **Do not use** | Worse than chance / wrong task. |

"Performance" numbers are **AUROC** (area under the ROC curve; 0.5 = chance, 1.0 = perfect) unless noted.
"Held-out" / "scaffold-split" / "far-OOD" describe how hard the test is — far-OOD (novel chemistry unlike
anything in training) is the honest stress test for a de-risking model.

---

## The capabilities

### Track 1 — Protein family clustering

**Question:** given a panel of genes, which embeddings put same-family genes together?
**Best model:** **ESM-2-650M** (MIT) ≈ MAMMAL-458M · ~4 min/run (seconds warm) · ✅ Reliable

**How it performs.** On the 40-gene reference panel, ESM-2-650M reaches **NN-recall 0.875** (best layer),
and **0.946** on the broader 167-gene panel. It is in a **four-way near-tie** with MAMMAL-458M (0.850) and
the much larger ESM-2 3B / 15B (both 0.850) — a 23× increase in model size moves nothing, because the
panel's signal is saturated. ESM-C 600M (0.825) trails. Two structure-aware specialists, **SaProt** and
**ProstT5**, are *perfect on GPCRs* (8/8).

**How to use it.** Use ESM-2-650M (smallest, cleanest MIT license) or MAMMAL — but extract an **early-mid
layer (~20–25% depth) and mean-center** the embedding, *not* the naive last-layer output, which undersells
every encoder by ~0.10. Use SaProt or ProstT5 for GPCR-family hits. One honest limit: **function-defined
families** (E3 ligases, nuclear receptors) are a ceiling for sequence-only models at any size (~0.5–0.65) —
those need function/annotation-aware models, the live research frontier for this track.

---

### Track 2 — DTI / binder triage

**Question:** given a Quiver target and a compound, does it bind?
**Best model:** **Boltz-2** (overall) + **BALM** (fast cosine triage) + **PLAPT** (first pass) · MIT · ⚠️ Family-dependent

**How it performs — this is the most important result in the report.** Scored across **19 CNS targets in
four families** (proper ChEMBL panels, not anecdotes), off-the-shelf binder triage is **family-specific, not
a general CNS capability:**

| Target family | BALM AUROC | Read |
|---|---|---|
| Kinase | **0.80** | ✅ reliable (BindingDB is kinase-rich) |
| mTOR-pathway | **0.72** | ✅ usable |
| GPCR | 0.58 | ⚠️ mediocre |
| **Ion channel** | **0.50** | ⛔ **chance — as a family** |

The ion-channel family is bimodal: BALM does fine on Nav1.7 (0.85) and Nav1.8 (0.78) but is **at or below
chance on Cav1.2 (0.20), NMDA/GRIN (0.32), Nav1.1 (0.29), Nav1.5 (0.46)**. An earlier "Nav1.8 0.857" figure
was a small-panel (n=11) over-read; on a proper 60-active panel BALM is 0.78 and does *not* generalize across
channels. On the head-to-head Nav1.8 panel, **BALM 0.857 > PLAPT 0.75 > Boltz-2 0.714 ≫ ConPLex / MAMMAL
(0.44 / 0.43, failures)**; mTOR is perfect for BALM and Boltz-2 (1.000).

**The fine-tune is de-risked (this is the lever).** The chance result on ion channels is **not** a
representation problem — it is the absence of target-specific training. A supervised model
(ESM-2 + molecular fingerprint, logistic) tested on **held-out chemical scaffolds** reaches **0.92 mean
AUROC** on those same channels, with the biggest gains exactly where zero-shot fails (Cav1.2 0.20 → 0.95,
NMDA 0.32 → 0.95, Nav1.1 0.29 → 0.94). We ruled out protein truncation as the cause (truncated and
full-length give identical results). **The 0.50 → 0.92 gap is the concrete value of training on Quiver's
ion-channel screening data.**

**How to use it.** Triage compounds against CNS **kinase / mTOR-pathway** targets with BALM (or PLAPT for a
near-instant first pass); confirm top hits with Boltz-2 co-folding (Track 3). For **ion channels — Quiver's
core — do not trust off-the-shelf sequence DTI;** the move is a Quiver-data fine-tune (above) or a Boltz-2
co-fold. Treat all of these as **family-level binder-vs-decoy triage, not fine selectivity** (see Track 8).

---

### Track 3 — Structure-based binding

**Question:** does it bind — co-folded, so it works on novel pockets that binding databases don't cover?
**Best model:** **Boltz-2** (MIT) · ~12 min/run (2–5 min warm) · ⚠️ Use with caution

**How it performs.** Boltz-2 predicts the protein–ligand **complex and an affinity in one pass**, so it works
where no binding-data baseline can — novel pockets, targets with zero training pairs. On Quiver targets it
gives **mTOR 1.000** and **Nav1.8 0.714**; the literature rates it as approaching FEP (free-energy
perturbation) accuracy and beating AlphaFold-3 / Chai-1 on affinity. Crucially, it succeeds **because it
co-folds the structure itself** — every pose-gated re-scorer we tested (DrugCLIP 0.39/0.25, AEV-PLIG 0/18
scored, GatorAffinity) **fails on Quiver's targets**, because they require a crystal-quality bound pocket
Quiver's data-poor targets don't have.

**How to use it.** Use for structure-based triage and confirmation on targets without binding data. It is the
only structure route that lands on Quiver's targets; the same model also powers Tracks 2 and 8.

**Two ways to run it, and which to pick (2026-06-17, hosted boltz-api).** Per-fold `structure-and-binding`
co-folds one complex (~$0.20 for the 1956-aa Nav1.8) and gives `binding_confidence` / `ligand_iptm`; on the
11-cpd Nav1.8 panel that's AUROC 0.71 / **0.89**. But the **`library-screen`** endpoint folds each ligand at
a flat **$0.025/molecule** (~8× cheaper) and returns a better readout, **`optimization_score`** — on a
44-molecule Nav1.8 set (panel + ChEMBL actives≥7 / inactives<5) it gives enrichment **AUROC 0.81 overall,
0.89 panel-only (≈ the per-fold ligand_iptm), 0.86 separating potent from weak within the suzetrigine
series**. **So for binder triage at scale, use `library-screen` + `optimization_score`, not per-fold** —
same discrimination, far cheaper, and one call also returns a free per-molecule ADME column (Track 5) and the
complex CIF. All of this runs through the **hosted boltz-api with no GPU/CUDA** — the operational fix for the
broken local CUDA-13 install. Still below the per-target ligand fine-tune (Track 2, 0.987): structure
**complements**, doesn't replace, in-domain QSAR. Receipts: `results/boltz_tier2_characterization.md`,
`results/boltz_tier1_characterization.md`.

---

### Track 4 — BBB penetrance

**Question:** will a CNS compound actually cross the blood-brain barrier?
**Best model:** **MapLight** (MIT, gradient-boosted fingerprints) · ~2 min (CPU, instant warm) · ✅ Reliable

**How it performs.** MapLight (CatBoost on ECFP + Avalon + ErG + RDKit descriptors) beats the best SMILES
language model on **every axis, on an independent held-out dataset:**

| Test | MapLight | MolFormer-XL |
|---|---|---|
| Held-out B3DB (6,142 leakage-removed cpds) | **0.919** | 0.854 |
| TDC scaffold-split | **0.905** | 0.889 |
| Calibration (Brier, lower=better) | **0.106** | 0.157 |
| **Far-OOD** (novel chemotypes, Tanimoto<0.3) | **0.674** | 0.590 (≈chance) |

The far-OOD result is the one that matters: a de-risking model has to hold on chemistry it hasn't seen, and
the language model collapses to near-chance there while MapLight degrades gracefully. CheMeleon (0.868) is
not a displacer. Fingerprint + gradient boosting beats the language model on this substructure-driven
endpoint — and runs on CPU at ~$0.

**How to use it.** Default to MapLight's probability and **attach a confidence flag based on Tanimoto
similarity to the training set** (near-domain AUROC ≈0.96, far-OOD ≈0.67 — flag novel scaffolds as
low-confidence). Keep MolFormer-XL as a secondary cross-check and MAMMAL's confident "no" as a specificity
backstop.

---

### Track 5 — Toxicity / DILI / hERG

**Question:** is this compound likely to fail Phase 1 on safety?
**Best model:** **MapLight** (hERG) + **ADMET-AI / ChemBERTa-2** (DILI) · MIT · ✅ Reliable (with domain flag)

**How it performs.** For **hERG** (cardiac liability), the fingerprint models win again: MapLight and a
Morgan-FP + XGBoost model both reach **~0.89** AUROC and, more importantly, MapLight is **the most
OOD-robust hERG model measured** (far-OOD 0.809 vs the language models' 0.56–0.61). For **DILI** (liver
injury), ADMET-AI is a strong gate (external true-positive rate **0.83**) and ChemBERTa-2 adds a
commercial-OK option (ext. TPR 0.73). **ClinTox is dead** for this purpose — across four different models its
external withdrawn-vs-safe AUROC is **0.24–0.47** (the "failed clinical trial" label does not transfer to
real safety withdrawals). **TxGemma-9B** reports a ~0.95 TDC-benchmark ceiling; an earlier "research-license-
only / not shippable" note here was **overstated** (corrected 2026-06-18): the Health AI Developer Foundations
terms *permit non-clinical drug-discovery R&D* (models trained on commercially-licensed data); the only hard
bar is *clinical* use (patient diagnosis/treatment) or shipping as a medical-device product. The real reasons
it's not adopted: (1) **never tested on our held-out panels** — 0.95 is a paper benchmark, not an our-data
number; (2) it's a 9B/27B LLM (GPU, generated text) vs the CPU fingerprint winners. **Action: benchmark
`txgemma-2b/9b-predict` on our hERG/DILI/BBBP panels (~$1–2 GPU); adopt if it beats the specialists, with the
clinical-use caveat.**
CardioGenAI's multi-channel cardiac concept is appealing but its heads are uncalibrated and vocabulary-locked
(not adopted — but the *idea* of NaV1.5/CaV1.2 heads is worth building on Quiver data).

**How to use it.** Run a hERG + DILI gate (MapLight for hERG OOD-robustness, ADMET-AI/ChemBERTa-2 for DILI);
treat a high score as a flag, not a kill. As in Track 4, **attach a Tanimoto-to-train confidence flag** —
every tox model is near chance on novel chemotypes. **Never use ClinTox.**

---

### Track 6 — KG / hypothesis generation

**Question:** what is connected to this target or screen hit in the literature / knowledge graph?
**Best model:** **PROTON + ULTRA** (co-winners) · MIT + Harvard Dataverse · ◑ Split (ranking only)

**How it performs.** On NeuroKG (Quiver's neuro knowledge graph: 147K nodes, 14.7M edges), the two models are
complementary:
- **PROTON** ranks a **known** drug against a **well-studied** target well — median rank percentile **4.3%**,
  with 57% of known binders in the top 5%. But its *forward* "which drug binds this target?" prediction is
  **hub-biased noise** — the same promiscuous drugs surface for nearly every target (one drug ranked #1 for 9
  unrelated targets). It also has **zero** capability on novel chemistry or under-studied targets.
- **ULTRA** (a 168k-parameter, zero-shot graph foundation model) **fixes both failures**: no hub bias
  (its top drugs are correct pharmacology — kinase inhibitors for kinases, dopaminergics for DRD2, etc.), and
  real **inductive novel-target** capability — with a target's edges fully held out it still ranks the right
  drugs in the top **0.34%**.

**How to use it.** Use **ULTRA** as the default for novel / weakly-connected targets and hub-sensitive
shortlists; use **PROTON** for ranking known drugs against well-studied NeuroKG targets, and for any
Quiver-private edges not in the public export. Both are **hypothesis-shortlisting tools, not binder
predictors** — never surface a forward "top drug" prediction. Neither is trustworthy on kinases. (The
commercial alternative, EMET/BenchSci at $150–500K/yr, covers the same use case and is a wrong-fit for
Quiver — see `docs/emet_evaluation_2026-06-11.md`.)

---

### Track 7 — Generative chemistry

**Question:** analog expansion (hit-to-lead) and de-novo design (novel scaffolds for a target).
**Best model:** **Morgan-FP + Enamine REAL NN** (analogs) · **Boltz design** (de-novo) · RDKit / Enamine / MIT · ◑ Situational

**How it performs.** *Analog expansion:* Morgan-fingerprint similarity beats MAMMAL embedding similarity
(**0.96 vs 0.72**); MAMMAL's public generative weights are span-infillers, not de-novo generators (1/8 exact
recovery). *De-novo (2026-06-17, hosted boltz-api):* `small-molecule:design` generated **24 novel Nav1.8
candidates in Enamine REAL** at $0.025/mol — **24/24 valid, 22/24 novel Murcko scaffolds, median max-Tanimoto
to known binders 0.19** (genuinely novel, not regurgitation), with `optimization_score` 0.25–0.35 — the same
band as the real screened actives (Track 3). So Boltz **does** real synthesizable de-novo design, a capability
public MAMMAL lacks. Caveat: the score is model self-consistency (not affinity), bounded by the ~0.81–0.89
Track-3 panel AUROC — treat outputs as synthesis hypotheses to confirm through the per-target fine-tune + a
docking pose, not validated hits.

**How to use it.** Use Morgan-FP NN over Enamine REAL for hit-to-lead analog expansion. For **novel-scaffold
ideation against a structure**, use Boltz design (Enamine REAL space, `recommended` SMARTS filter) and gate
the top candidates through Track 2 (fine-tune) + Track 3 (co-fold). Still **secondary** to target ID and
triage — Quiver's bottleneck — but no longer "low value": de-novo is now a real, cheap option.
Receipts: `results/boltz_tier2_characterization.md`.

---

### Track 8 — Off-target / selectivity

**Question:** does this compound only hit Nav1.8, or also Nav1.5 / Nav1.7?
**Best model:** **Boltz-2** (MIT) · ~15 min (≈3 min/paralog warm) · ⚠️ Directional only

**How it performs.** Boltz-2 ranks suzetrigine's intended target (Nav1.8) **#1** across 9 Nav paralogs — the
right order — but with **narrow margins (0.31–0.44)**: directionally right, quantitatively soft. The key
negative result: **sequence-based DTI cannot do fine selectivity.** BALM biases toward Nav1.5 (the cardiac
off-target), and on a real target-deconvolution test (Ben's TSC2 screen hits → PKM2 vs PPARD) both BALM and
PLAPT are **at chance**, with control compounds outscoring true binders.

**How to use it.** Use Boltz-2 to rank a compound across a paralog panel for **directional** selectivity (a
hypothesis, not a ratio). **Do not** use sequence DTI (BALM/PLAPT) for selectivity or target deconvolution —
it is at chance. Fine deconvolution needs co-folding (Boltz-2) or **Quiver's own functional signatures**
(which is what actually made the TSC2 call).

---

### Track 9 — Variant effect (channelopathy GoF/LoF)

**Question:** is this ion-channel missense variant gain- or loss-of-function?
**Best model:** **funNCion** (Apache-2.0) · ~3 min/run · ⚠️ Public channels only

**How it performs.** funNCion calls **gain-of-function vs loss-of-function** on ion-channel missense variants
at AUROC **0.897**, and is open and downloadable. MissION (0.925) is marginally better but **web-portal-only
— no weights, not adoptable**. A generic protein language model (ESM-2 650M masked-marginal scoring) reaches
only **0.665** — it captures *deleteriousness*, not GoF-vs-LoF *direction* — so a channel-specialized model is
required.

**How to use it.** Use funNCion for GoF/LoF on the public channels (SCN1A/2A/5A, etc.). **The critical gap:**
SCN10A (Nav1.8) and SCN3A are **absent from every public training set**, so no public model calls direction
on Quiver's flagship channel — this is a build target on Quiver's own functional data (see below).

---

<a id="build-vs-buy"></a>
## What to build vs. buy

The map above is mostly "buy" (or "use for free") — but four capabilities are **build targets**, because no
public model is good enough and Quiver's proprietary data is exactly the missing ingredient:

1. **Ion-channel binder model (highest ROI).** Off-the-shelf is at chance (0.50); a supervised model on
   held-out scaffolds hits 0.92. Fine-tune on Quiver's ion-channel screening data (actives + matched
   inactives), evaluate on a scaffold-held-out split against a fingerprint+GBT baseline. This owns the
   targets public models have no head for. *(Track 2.)*
2. **Nav1.8 variant-effect model.** Nav1.8 is absent from every public GoF/LoF training set; a
   channel-specific model trained on Quiver's functional readouts fills a gap no one else can. *(Track 9.)*
3. **Cardiac multi-channel safety heads** (NaV1.5 / CaV1.2), built on Quiver's data with the same
   fingerprint+gradient-boosting recipe that wins Tracks 4–5 — the missing late-Na signal our single hERG
   gate lacks. *(Track 5.)*
4. **Target deconvolution** via Quiver's functional signatures — the route that actually resolved the TSC2
   screen, where sequence DTI is at chance. *(Track 8.)*

---

## Models evaluated

A complete record of what was tested, so the breadth of the search is auditable and we don't re-run dead ends.

| Model | Track(s) | Verdict |
|---|---|---|
| MAMMAL-458M (9 public heads) | 1–8 | Mixed; BBBP superseded by MapLight/MolFormer, ClinTox worse than chance, family clustering ties ESM-2, DTI fails ion channels |
| ESM-2-650M | 1 | **Track-1 winner** (best-layer 0.875); cleanest license |
| ESM-2 3B / 15B | 1 | No scale benefit (0.850); 23× params buy nothing |
| ESM-C 600M | 1 | Not an upgrade (0.825); trap default readout |
| ESM-3-open 1.4B | 1 | Ties top (0.875) + nuclear-receptor 1.0, but non-commercial |
| Ankh-large | 1 | Ties ceiling (0.850), below ESM-2-650M |
| SaProt-650M / ProstT5 | 1 | GPCR specialists (8/8 perfect); not overall winners |
| ProtST-esm1b / PINNACLE | 1 | Did not run / lost (no relevant cell contexts) |
| **Boltz-2** | 2,3,8 | **Best DTI/structure on Quiver targets** (Nav1.8 0.714, mTOR 1.000) |
| **BALM** | 2 | **Best sequence cosine triage** (Nav1.8 0.857) — family-level only, not selectivity |
| **PLAPT** | 2 | Fast first-pass (Nav1.8 0.75); not Nav-blind |
| ConPLex | 2,8 | Broken on Nav paralogs (0.437) |
| DrugCLIP / GatorAffinity / AEV-PLIG | 2,3 | Pose-gated; fail on Quiver's no-holo targets |
| AdaMBind | 2,3 | Not adoptable (no license; few-shot path broken) |
| DTIAM (BerMol) | 2 | Setup verified; eval blocked by a ChEMBL outage (relaunchable) |
| **MapLight** | 4,5 | **BBBP + hERG winner** (B3DB 0.919; most OOD-robust) |
| MolFormer-XL | 4 | Strong second (0.889 scaffold / 0.854 held-out); backstop |
| ChemBERTa-2 | 4,5 | Commercial-OK de-risking (hERG 0.726, DILI ext. 0.73) |
| CheMeleon | 4,5 | Below MolFormer on BBB, below FP on hERG — skip |
| Uni-Mol2 | 4 | BBBP 0.785; 3D doesn't help — skip |
| ADMET-AI | 5 | Strong DILI gate (TPR 0.83) |
| TxGemma-9B | 5 | ~0.95 ceiling but research-license-only (not shippable) |
| CardioGenAI | 5 | Concept good, heads uncalibrated/vocab-locked — not adopted |
| **PROTON** | 6 | **KG known-drug ranking** (median 4.3%); forward prediction is hub noise |
| **ULTRA** | 6 | **Zero-shot KG winner** — fixes hub bias + novel targets |
| EMET (BenchSci) | 6 | Real product, $150–500K/yr — wrong-fit for Quiver |
| Morgan FP + Enamine REAL | 7 | Boring winner (0.96 vs MAMMAL 0.72) |
| **funNCion** | 9 | **Variant-effect winner** (0.897); adoptable |
| MissION | 9 | 0.925 but portal-only — not adoptable |

---

## Where the evidence lives

- **Per-track writeups (full operating envelopes):** `results/*_characterization.md`
- **Narrative synthesis (companion to this report):** `docs/cns_model_performance_report.md`
- **Raw per-run results:** `results/*.json`, `results/aws_eval/*`
- **EMET evaluation:** `docs/emet_evaluation_2026-06-11.md`

*Models not worth testing (with receipts): single-cell foundation models — scFoundation, scGPT, Geneformer,
CellPLM — underperform a mean-of-training baseline on perturbation prediction (Nature Methods 2025,
DOI 10.1038/s41592-025-02772-6).*
