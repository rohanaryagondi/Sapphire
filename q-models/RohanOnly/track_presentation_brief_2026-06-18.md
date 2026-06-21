# Track Presentation Brief — CNS Model Evaluation Campaign
*Quiver Bioscience · Prepared 2026-06-18 · For Rohan Aryagondi*

---

## Executive Summary

This campaign asked one question: for each computational capability Quiver needs in CNS drug discovery,
what is the best available open model — and is it actually good enough on our targets? We evaluated ~25
models across nine capability tracks, testing empirically on Quiver-relevant substrate (CNS ion channels,
GPCRs, kinases, knowledge graph targets, and our own screening data), not paper benchmarks.

**The two-sentence verdict:** De-risking (BBB, hERG, DILI) and protein-family clustering are solved —
cheap fingerprint and language models do the job reliably. Binder triage on ion channels, the core of
Quiver's program, is **not** solved by any off-the-shelf model; the gap from chance (0.50) to a
fine-tuned supervised model (0.92) is the concrete value of Quiver's screening data.

| Track | Best Model | Confidence |
|---|---|---|
| 1 — Protein-family clustering | ESM-2-650M (≈ MAMMAL-458M) | Reliable |
| 2 — DTI / binder triage | Boltz-2 + BALM + PLAPT | Family-dependent |
| 3 — Structure-based binding | Boltz-2 (per-fold) / library-screen (scale) | Use with caution |
| 4 — BBB penetrance | MapLight | Reliable |
| 5 — Toxicity / DILI / hERG | MapLight (hERG) + ADMET-AI (DILI) | Reliable (with domain flag) |
| 6 — KG / hypothesis generation | PROTON + ULTRA (co-winners) | Split (ranking only) |
| 7 — Generative chemistry | Morgan FP (analogs) + Boltz design (de-novo) | Situational |
| 8 — Off-target / selectivity | Boltz-2 | Directional only |
| 9 — Variant effect (channelopathy) | funNCion | Public channels only |

---

## At-a-Glance — One Block Per Track (the talking script)

*Each block: the question the track answers, how the winning model actually does (in context), the other models we tried, and the cost to run it. (Most evals are a sub-dollar ~1-hour run on a single AWS g5.xlarge GPU; the whole campaign ran well under a $45 cap.)*

**Track 1 — Protein-family clustering.** *Question:* given a panel of genes, do a model's embeddings group same-family proteins together — the foundation of "what looks like my target?" *How it does:* ESM-2-650M groups sequence-defined families near-perfectly and is effectively tied with models 5–23× larger, so we get the best result at the smallest size and the cleanest license; it only stumbles on families defined by *function* rather than sequence (e.g. E3 ligases). *Also tried:* MAMMAL-458M, ESM-2-3B, ESM-2-15B, ESM-C 600M, PROTON, and the structure-aware SaProt / ProstT5 (which are perfect on GPCR-heavy panels) plus ProTrek. *Run cost:* ESM-2-650M itself runs on CPU/locally for ~$0; the full size-ladder comparison (3B/15B) was ~$0.55 on a g5.xlarge.

**Track 2 — DTI / binder triage.** *Question:* given a CNS target and a compound, does it bind? *How it does:* off-the-shelf, the best models work on kinases and the mTOR pathway but are **at chance on ion channels as a family** — exactly Quiver's core program; the only thing that fixes Nav/Cav is a model fine-tuned on ion-channel data, which jumps from chance to near-perfect, and it has to be Quiver's *own* screening data because public data doesn't transfer between channels. This is the single most important result in the report and the clearest case for Quiver's proprietary data. *Also tried:* BALM and PLAPT (the fast winners on the families that work), ConPLex and MAMMAL's DTI head (both fail on Nav1.8); the fine-tune itself is ESM-2-650M target embeddings + Morgan-fingerprint ligands. *Run cost:* ~$0.50 on a g5.xlarge for the ion-channel fine-tune + scaffold-split eval; the BALM/PLAPT off-the-shelf triage evals are ~$0.50 each.

**Track 3 — Structure-based binding.** *Question:* does it bind, predicted by *co-folding the complex from sequence* — so it works on novel pockets with no crystal structure and no training pairs? *How it does:* Boltz-2 builds the protein–ligand complex itself, so it lands on data-poor Quiver targets where every pose-dependent rescorer fails; its real value is catching novel scaffolds the ligand model misses (it flagged suzetrigine, which the fine-tune scored as a false negative) and its cheap library-screen mode makes it the scale workhorse for triage. It complements the fine-tune rather than replacing it, and it is not an affinity oracle. *Also tried:* DrugCLIP, AEV-PLIG, and GatorAffinity — all pose-dependent rescorers that need a crystal-quality pocket and therefore fail on Quiver's targets. *Run cost:* hosted Boltz-API, **not an AWS GPU run** — ~$0.20 per co-fold, or **$0.025/molecule** via the cheaper library-screen mode.

**Track 4 — BBB penetrance.** *Question:* will a CNS compound actually cross the blood-brain barrier? *How it does:* MapLight — a "boring" fingerprint + gradient-boosting model — beats the fancy SMILES language model on every axis, and crucially keeps working on novel chemotypes where the language model collapses to near-chance; that out-of-domain robustness is exactly what a de-risking gate needs, and it runs free on CPU. *Also tried:* MolFormer-XL (the language-model runner-up, kept as a cross-check), CheMeleon, and MAMMAL (useful only as a confident-"no" backstop). *Run cost:* ~$0.40 on a g5.xlarge (~1 hr); MapLight itself is a CPU model, so production scoring is effectively free.

**Track 5 — Toxicity / DILI / hERG.** *Question:* is this compound likely to fail Phase 1 on safety (cardiac hERG, liver DILI)? *How it does:* for hERG, fingerprint models (MapLight) win again and stay robust on new chemistry; for DILI, ADMET-AI is a solid external gate. The headline lesson is what *not* to use — the popular ClinTox model is worse than chance on real drug withdrawals, so it must never be a safety gate. *Also tried:* a Morgan-FP + XGBoost model (ties MapLight on hERG), ChemBERTa-2 (a commercial-OK DILI option), TxGemma (great benchmark numbers but never tested on our panels — a candidate, not adopted), ClinTox (rejected), and MAMMAL. *Run cost:* ~$0.40 on a g5.xlarge; MapLight + ADMET-AI both score on CPU, so the gate runs free in production.

**Track 6 — KG / hypothesis generation.** *Question:* what is connected to this target or screen hit in the literature and knowledge graph — to surface candidate partners and mechanisms? *How it does:* the two winners cover opposite weaknesses — PROTON reliably ranks *known* drugs against *well-studied* targets but turns into hub-biased noise on novel targets, while ULTRA fixes the hub bias and still works when a target's edges are fully held out; both are shortlisting tools to generate hypotheses, never to be presented as confirmed hits, and neither is trustworthy on kinases. *Also tried:* EMET / BenchSci, the $150–500K/yr commercial product, which covers the same use case and is a wrong fit for Quiver. *Run cost:* ~$1 on a g5.xlarge for the two models (PROTON's early run was ~$1.07; ULTRA needs a one-time CUDA-kernel compile), against the $150–500K/yr commercial alternative.

**Track 7 — Generative chemistry.** *Question:* expand a hit into analogs (hit-to-lead) and design genuinely novel molecules for a target (de-novo)? *How it does:* for analogs, plain Morgan-fingerprint similarity over the Enamine REAL catalog beats MAMMAL's embeddings; for de-novo, Boltz can actually generate valid, novel, synthesizable candidates — something MAMMAL's public weights cannot do (they only infill fragments). Treat de-novo output as synthesis hypotheses to confirm downstream, and note this track is secondary to triage, not Quiver's bottleneck. *Also tried:* MAMMAL, whose public "generative" weights are span-infillers, not a real de-novo generator. *Run cost:* analog search runs locally for ~$0; Boltz de-novo design is hosted-API at **$0.025/molecule** (not an AWS GPU run).

**Track 8 — Off-target / selectivity.** *Question:* does a compound hit only the intended channel (Nav1.8), or also dangerous off-targets like cardiac Nav1.5? *How it does:* this is essentially **unsolved off-the-shelf** — Boltz-2 can rank a compound across a paralog panel directionally, but the margins are soft and in a hard test it scored the known Nav1.8-selective drug *last of nine*; sequence models even bias toward the cardiac off-target. Fine selectivity — and the TSC2 target-deconvolution case — was only resolved by Quiver's own functional / electrophysiology data. *Also tried:* BALM and PLAPT (both fail selectivity; BALM biases to cardiac Nav1.5); the deconvolution call was settled by Quiver's functional/DFP signatures, not a model. *Run cost:* hosted Boltz-API, **not AWS** — the suzetrigine × 9-paralog selectivity panel is ~$0.20/fold, or ~$0.23 total via library-screen.

**Track 9 — Variant effect (channelopathy).** *Question:* is an ion-channel missense variant gain-of-function or loss-of-function — the call that sets therapeutic direction? *How it does:* funNCion, a channel-specialized model, calls GoF vs LoF well on public channels, whereas a generic protein language model only tells you a variant is *damaging*, not the direction — so a specialist is genuinely required. The catch: Nav1.8/SCN10A is absent from every public training set and the model demonstrably fails to transfer to it, making it a build target on Quiver's data. *Also tried:* MissION (marginally better but web-portal-only with no downloadable weights — not adoptable) and ESM-2-650M (generic pLM, captures deleteriousness but not direction). *Run cost:* ~$0.40 on a g5.xlarge (~1 hr); funNCion is light enough to also run on CPU.

---

## Track 1 — Protein-Family Clustering

**The question:** Given a panel of genes, which embeddings correctly group same-family proteins together?

**Best model:** ESM-2-650M (MIT) — a 650M-parameter protein language model; runs in seconds once warm.

**Why it wins:** On the 40-gene reference CRISPR-N panel, ESM-2-650M reaches **nearest-neighbor (NN)
recall 0.875** (best layer), and **0.946** on a broader 167-gene panel. It sits in a four-way near-tie
with MAMMAL-458M (0.850), ESM-2-3B (0.850), and ESM-2-15B (0.850). Scaling from 650M to 15B — a 23×
parameter increase — buys nothing; the panel's signal is saturated. PROTON (KG-based embeddings) scored
only 0.487, because KG embeddings reflect link-prediction objectives (gene↔disease), not sequence-family
structure. ESM-C 600M (0.825) is not an upgrade over ESM-2-650M.

Two structure-aware specialists, SaProt and ProstT5, are **perfect on GPCRs (8/8)** — use them when the
panel is GPCR-dominated.

**Implementation note:** Use an early-to-mid layer (~20–25% depth) with mean-centering, not the naive
last-layer output. The last layer undersells every encoder by ~0.10 NN-recall.

**Tested on:** 40-gene CRISPR-N panel (Quiver's reference gene set); 167-gene extended panel.

**Confidence and caveat:** Reliable for sequence-defined families. One ceiling: function-defined families
(E3 ligases, nuclear receptors) plateau at ~0.50–0.65 for all sequence-only models at any size — these
need annotation-aware models (ProTrek's text-anchored family assignment cracks E3 ligases at 0.75 but
is not an overall winner).

---

## Track 2 — DTI / Binder Triage

**The question:** Given a Quiver CNS target and a compound, does it bind?

**Best model:** Boltz-2 (overall, MIT) + BALM (fast cosine triage) + PLAPT (near-instant first pass).
All are MIT-licensed.

**Why it wins — and the most important result in the report:** Across 19 CNS targets in four families,
off-the-shelf binder triage is **family-specific, not a general CNS capability:**

| Target family | BALM AUROC | Verdict |
|---|---|---|
| Kinase | **0.80** | Reliable |
| mTOR-pathway | **0.72** | Usable |
| GPCR | 0.58 | Mediocre |
| **Ion channel** | **0.50** | Chance — as a family |

Ion channels are bimodal within the family: BALM scores Nav1.7 at 0.85 and Nav1.8 at 0.78 but is at or
below chance on Cav1.2 (0.20), NMDA/GRIN (0.32), Nav1.1 (0.29), and Nav1.5 (0.46). On the head-to-head
Nav1.8 panel: **BALM 0.857 > PLAPT 0.75 > Boltz-2 0.714 >> ConPLex 0.44 / MAMMAL DTI 0.43 (failures)**.
For mTOR, BALM and Boltz-2 are both perfect (1.000). Protein truncation is not the cause — truncated and
full-length targets give identical results.

**The fine-tune is the lever, and it is de-risked.** A supervised model (ESM-2-650M target embedding +
Morgan FP ligand, logistic head) trained on a pooled online corpus (21,556 pairs from ChEMBL
ion-channel set + Guide-to-Pharmacology) reaches **scaffold-split AUROC 0.92** (Nav 0.98, Cav 0.99,
NMDA 0.99) vs off-the-shelf 0.50 and a ligand-only fingerprint baseline of 0.67. The 0.50→0.92 gap is
the concrete, measured value of training on ion-channel data. Leave-one-channel-out transfer fails
(0/4 channels transfer; Nav1.8 0.36) — which means **Quiver's own ion-channel screening data is the
irreplaceable ingredient**, not just any public corpus.

**Tested on:** 19 CNS targets across 4 families (ChEMBL panels); dedicated Nav1.8 binder/decoy panel
(11 compounds: 7 binders / 4 decoys); Nav family panel (9 paralogs, Nav1.1–Nav1.9).

**Confidence and caveat:** Reliable for kinase / mTOR-pathway. Chance for ion channels off-the-shelf.
The fine-tune result is strong but requires per-target Quiver data to be deployable for Nav1.8 specifically.

---

## Track 3 — Structure-Based Binding

**The question:** Does it bind — co-folded from sequence, so it works on novel pockets without a crystal
structure?

**Best model:** Boltz-2 (MIT), accessed via the hosted boltz-api (no GPU required).

**Why it wins:** Boltz-2 predicts the protein–ligand complex and a binding confidence score in one pass,
working where no BindingDB-trained model can — novel pockets and targets with zero training pairs. On
Quiver targets: **mTOR AUROC 1.000, Nav1.8 AUROC 0.714 (binding_confidence) / 0.893 (ligand_iptm)**.
Every pose-dependent rescorer tested (DrugCLIP, AEV-PLIG, GatorAffinity) fails on Quiver's targets
because they require a crystal-quality bound pocket, which data-poor Quiver targets don't have.

**Two ways to run it — use library-screen for scale:** A full per-fold `structure-and-binding` co-fold
costs ~$0.20 for the 1956-aa Nav1.8 and gives AUROC 0.71 (binding_confidence) / 0.89 (ligand_iptm).
The `library-screen` endpoint costs **$0.025/molecule (~8× cheaper)** and returns a better readout
(`optimization_score`): on a 44-molecule Nav1.8 set (panel + ChEMBL actives/inactives), **AUROC 0.81
overall, 0.89 panel-only, 0.86 within the suzetrigine sulfonamide-carboxamide series**. Use library-screen
for binder triage at scale; every screen row also returns a free per-molecule ADME column.

**The OOD rescue:** Boltz complements the per-target ligand fine-tune precisely where the fine-tune fails.
The per-target fine-tune scored suzetrigine→Nav1.8 = 0.14 (false negative — novel 2024 scaffold,
out-of-domain). Boltz binding_confidence = **0.479, the 2nd-highest of all 11**, cleanly above every
decoy. Structure sees binding that QSAR cannot.

**Tested on:** Nav1.8 binder/decoy panel (n=11); 44-molecule expanded Nav1.8 set including ChEMBL
actives/inactives; mTOR; TSC2 deconvolution (negative: co-folding failed to deconvolve PKM2 vs PPARD).

**Confidence and caveat:** Useful as a complement to the ligand fine-tune and as the route for novel
scaffolds / data-poor targets. Not an affinity oracle or selectivity ranker (see Track 8). Still below
the per-target fine-tune (0.987 in-domain) — structure complements, it does not replace, in-domain QSAR.

---

## Track 4 — BBB Penetrance

**The question:** Will a CNS compound actually cross the blood-brain barrier?

**Best model:** MapLight (MIT) — gradient-boosted model on ECFP + Avalon + ErG + RDKit fingerprint
descriptors. Runs on CPU at ~$0.

**Why it wins:** MapLight beats the best SMILES language model (MolFormer-XL) on every axis:

| Test | MapLight | MolFormer-XL |
|---|---|---|
| Held-out B3DB (6,142 leakage-removed compounds) | **0.919** | 0.854 |
| TDC scaffold-split | **0.905** | 0.889 |
| Calibration (Brier score, lower = better) | **0.106** | 0.157 |
| Far-OOD (novel chemotypes, Tanimoto < 0.3) | **0.674** | 0.590 (near chance) |

The far-OOD result is the one that matters. A de-risking model has to hold on chemistry it hasn't seen.
MolFormer-XL collapses to near-chance on novel scaffolds; MapLight degrades gracefully. CheMeleon (0.868)
is not a displacer. The boring fingerprint + gradient-boosting approach wins this substructure-driven
endpoint.

**Tested on:** Independent held-out B3DB (6,142 compounds with leakage removed); TDC scaffold-split
benchmark; far-OOD chemotype subset (Tanimoto < 0.3 to training set).

**Confidence and caveat:** Reliable in-domain (AUROC ~0.96 near-domain). Attach a Tanimoto-to-train
confidence flag — novel scaffolds drop to 0.67. Keep MolFormer-XL as a secondary cross-check and MAMMAL's
hard "no" prediction as a specificity backstop.

---

## Track 5 — Toxicity / DILI / hERG

**The question:** Is this compound likely to fail Phase 1 on safety?

**Best model:** MapLight (hERG, MIT) + ADMET-AI / ChemBERTa-2 (DILI, MIT / commercial-OK).

**Why it wins:** For **hERG** (cardiac liability), fingerprint models win again. MapLight and a
Morgan-FP + XGBoost model both reach **~0.89 AUROC**. More importantly, MapLight is the most
OOD-robust hERG model measured: **far-OOD AUROC 0.809 vs. language models at 0.56–0.61**.

For **DILI** (liver injury), ADMET-AI is a strong gate at **external true-positive rate 0.83**, and
ChemBERTa-2 adds a commercial-OK alternative (ext. TPR 0.73). TxGemma-9B reports a ~0.95 benchmark
ceiling on TDC — but that is a *paper benchmark*, and we have **not** tested it on our held-out panels
(the campaign's bar is empirical-on-our-data). Its license permits non-clinical R&D use; it is **not**
a hard blocker (see Talking Points). It is untested-for-us, not unusable — a candidate to benchmark, not yet adopted.

**ClinTox is dead for this purpose.** Across four different models, external withdrawn-vs-safe AUROC
is 0.24–0.47 — the "failed clinical trial" label does not transfer to real safety withdrawals. Never use
it as a toxicity gate.

The library-screen endpoint (Track 3) also returns a free ADME column per molecule (solubility,
permeability, logD) that is directionally correct — CNS-penetrant Nav blockers score high permeability,
hydrophilic decoys score low, A-803467 correctly flagged as high-risk solubility.

**Tested on:** External DILI validation set; withdrawn-drug / safety-withdrawn panel (ClinTox falsified);
Nav1.8 panel for ADME directional check (11 known CNS/non-CNS compounds).

**Confidence and caveat:** Reliable with a Tanimoto-to-train confidence flag. Every tox model
approaches chance on novel chemotypes — flag low-similarity inputs as low-confidence. A missing gap:
no public model has calibrated NaV1.5/CaV1.2 cardiac safety heads — those are a build target on
Quiver's data.

---

## Track 6 — KG / Hypothesis Generation

**The question:** What is connected to this target or screen hit in the literature and knowledge graph?

**Best model:** PROTON + ULTRA (co-winners, complementary). PROTON is MIT-licensed; ULTRA is Harvard
Dataverse (open).

**Why they win:** On NeuroKG (Quiver's neuro knowledge graph: 147K nodes, 14.7M edges), the two models
cover different failure modes:

**PROTON** ranks a known drug against a well-studied target with high fidelity: **median rank percentile
4.3%**, with 57% of known binders in the top 5%. But its forward "which drug binds this target?"
prediction is hub-biased noise — the same promiscuous drugs (e.g. Bepridil) surface as rank #1 for
9 unrelated targets. It has zero capability on novel chemistry or under-studied targets.

**ULTRA** (168k-parameter zero-shot graph foundation model) fixes both failures: no hub bias (top
drugs are correct pharmacology — kinase inhibitors for kinases, dopaminergics for DRD2), and real
inductive capability — with a target's edges fully held out it still ranks correct drugs in the top
**0.34%**. ULTRA is the right default for novel or weakly-connected targets.

**Tested on:** NeuroKG (147K nodes, 14.7M edges); 40-gene CRISPR-N panel for gene-family clustering
context; known-binder ranking task across Quiver target set.

**Confidence and caveat:** Split. Both models are shortlisting tools, not binder predictors — never
surface a forward "top drug" as a confirmed hit. Neither is trustworthy on kinase targets specifically.
The commercial alternative (EMET/BenchSci at $150–500K/yr) covers the same use case and is
wrong-fit for Quiver.

---

## Track 7 — Generative Chemistry

**The question:** Analog expansion (hit-to-lead) and de-novo design (novel scaffolds for a target).

**Best model:** Morgan FP + Enamine REAL NN (analogs); Boltz design via boltz-api (de-novo). RDKit /
Enamine / MIT licenses.

**Why it wins:**

*Analog expansion:* Morgan fingerprint similarity search over Enamine REAL beats MAMMAL's embedding
similarity (**0.96 vs 0.72**). MAMMAL's public generative weights are span-infillers (1/8 exact
recovery), not de-novo generators — "MAMMAL generates molecules" is false for the public artifact.

*De-novo design (2026-06-17, hosted boltz-api):* `small-molecule:design` generated **24 novel Nav1.8
candidates in Enamine REAL** (synthesizable space) at $0.025/mol. **24/24 valid, 22/24 novel Murcko
scaffolds, median max-Tanimoto to known binders = 0.19** (genuinely novel, not regurgitation).
`optimization_score` 0.25–0.35 — **the same band as the real screened actives from Track 3**. So Boltz
does real synthesizable de-novo design that public MAMMAL cannot do.

**Tested on:** Analog expansion benchmarked against MAMMAL SMILES embeddings on the Nav1.8 compound
panel. De-novo: 24 generated Nav1.8 candidates scored for validity, scaffold novelty (vs panel + top-200
ChEMBL Nav1.8 actives), and structural plausibility by library-screen scoring.

**Confidence and caveat:** Analog expansion via Morgan FP is reliable (0.96). De-novo is real and
cheap, but `optimization_score` is model self-consistency, not measured affinity — treat outputs as
synthesis hypotheses. Feed top candidates through the per-target fine-tune (Track 2) + a docking pose
before ordering. De-novo is **secondary** to target triage, not Quiver's bottleneck.

---

## Track 8 — Off-Target / Selectivity

**The question:** Does this compound only hit Nav1.8, or does it also hit Nav1.5 (cardiac) or Nav1.7?

**Best model:** Boltz-2 (MIT) — structure-based, needed because sequence-based DTI fails entirely here.

**Why it wins (directionally):** Boltz-2 ranks suzetrigine's intended target (Nav1.8) **#1 across 9 Nav
paralogs** by binding_confidence — the right order. Margins are narrow (0.31–0.44); the result is
directionally correct, quantitatively soft.

**The critical negative result:** Sequence-based DTI cannot do fine selectivity. BALM biases toward
Nav1.5 (the cardiac off-target Quiver needs to avoid). On the TSC2 target-deconvolution test (screen
hits → PKM2 vs PPARD), both BALM and PLAPT are at chance; control compounds outscore true binders. The
selectivity problem remains unsolved by any off-the-shelf model. **Boltz's own selectivity scores also
fail in an important calibration test (Tier-3):** when suzetrigine is run as a 1-molecule library-screen
against all 9 Nav paralogs, Nav1.8 scores **last of nine** (binding_confidence 0.355 vs Nav1.1 0.492).
Boltz scores relative pocket ligandability, not subtype-selective binding.

**Tested on:** Suzetrigine × 9 Nav paralogs (Nav1.1–Nav1.9, per-fold and library-screen); TSC2
target-deconvolution panel (4 compounds: true PKM2 and PPARD binders + controls).

**Confidence and caveat:** Directional only — use Boltz-2 to rank a compound across a paralog panel as
a hypothesis, not a selectivity ratio. Fine-grained selectivity (Nav1.8 vs Nav1.5 vs Nav1.7) is not
solved by any off-the-shelf model. The route that actually resolved the TSC2 call was Quiver's own
functional/DFP signatures — that remains the correct tool for target deconvolution.

---

## Track 9 — Variant Effect (Channelopathy GoF/LoF)

**The question:** Is this ion-channel missense variant gain-of-function or loss-of-function?

**Best model:** funNCion (Apache-2.0) — an ion-channel-specialized variant-effect predictor.
Runs in ~3 minutes.

**Why it wins:** funNCion calls **gain-of-function vs. loss-of-function** on ion-channel missense
variants at AUROC **0.897**. MissION is marginally better (0.925) but is web-portal-only with no
downloadable weights — not adoptable. A generic protein language model (ESM-2-650M masked-marginal
scoring) reaches only **0.665** — it captures deleteriousness, not GoF/LoF direction. A
channel-specialized model is required; a generic pLM is not sufficient.

**The fine-tune is an informative negative.** On 2,212 pooled SCION + funNCion Nav/Cav variants,
leave-one-gene-out AUROC = **0.36** (below ESM-2-LLR baseline of 0.61), and held-out Nav1.8 transfer
AUROC = **0.48 (chance)**. GoF/LoF direction is channel-specific; public data does not transfer across
channels. This upgrades "Nav1.8 is a build target" from "labels absent" to "transfer demonstrably fails."

**Tested on:** Public ion-channel variant databases (funNCion/SCION training sets); 2,212 pooled Nav/Cav
variants for leave-one-gene-out transfer evaluation; held-out Nav1.8 transfer set.

**Confidence and caveat:** Reliable for public channels (SCN1A/2A/5A, KCNQ2, etc.). Critical gap:
SCN10A (Nav1.8) and SCN3A are absent from every public training set — no public model calls GoF/LoF
direction on Quiver's flagship channel. This is a build target requiring Quiver's own functional data.

---

## Boltz Hosted-API Capabilities (Cross-Track)

*What the Boltz campaign established — relevant to Tracks 2, 3, 5, 7, and 8.*

The hosted boltz-api (boltz-2.1) removes the local CUDA-13 installation blocker entirely — no GPU, no
CUDA toolchain required. All six Boltz capabilities were characterized across three tiers of experiments
($3.8 + $1.9 + $1.0 = ~$6.7 total), plus an overnight druggability run (~$18.85).

**Small-molecule capabilities (reliable, cheap):**

- **Structure-and-binding (Track 3):** Nav1.8 AUROC 0.893 (ligand_iptm), 0.714 (binding_confidence).
  Use `ligand_iptm` as the structural binder score. Cost: ~$0.20/fold for a 1956-aa target.
- **Library-screen (Tracks 2/3):** Nav1.8 enrichment AUROC **0.81** (`optimization_score`) at
  **$0.025/molecule (~8× cheaper than per-fold)**. The operational workflow for binder triage at scale.
  Each result row carries a free ADME column.
- **De-novo design (Track 7):** 24/24 valid, 22/24 novel-scaffold Nav1.8 candidates in Enamine REAL
  space at $0.025/mol. optimization_score 0.25–0.35, matching real screened actives — genuinely novel,
  synthesizable.
- **ADME (Track 5 supplement):** Tier-1 solubility/permeability/logD at $0.01/mol; directionally
  correct and bundled free inside every library-screen call.

**Druggability map from the overnight run (23 CNS program targets):**

Five targets scored as strongly ligandable (bindconf_max 0.645–0.710): **SCN2A, TSC1, SRCAP, EP400,
EP300**. Moderate pocket engagement (0.538–0.603): KCNQ2, CHD8, STXBP1, HNRNPK, SMARCA4. Poor or
not tractable: KMT2A (0.312), WDR5 (0.403). Two targets (RPS17↔USP7-TRAF, iptm 0.774) show
structural support for rescue-pair interface plausibility above the positive-control band.

**Important calibration (Tier-3 negative):** Suzetrigine (Nav1.8-selective drug) scored **last of 9
Nav paralogs** on binding_confidence in Boltz's own selectivity test. **Boltz scores are relative
pocket ligandability, not affinity or subtype-selectivity measures.** Always calibrate against a
known inhibitor (e.g., WDR5+OICR-9429 hits 0.98; DOT1L+pinometostat hits 0.96) before trusting
de-novo or screen scores.

**Protein-side capabilities (exploratory only):**

- `protein:library-screen`: binding_confidence is degenerate (0.000 for all tested pairs); iptm is
  the only usable readout but is weak (~0.56 AUROC on Nav1.7 toxin selectivity task). Use only as
  directional confirmation, not evidence.
- `protein:design`: iptm up to 0.884 but generates generic amphipathic helices, not biologically
  realistic gating-modifier toxins. Model self-consistency ≠ design quality.

**How Boltz fits the stack:** Structure is a **complement** to the per-target ligand fine-tune (0.987
in-domain), not a replacement. Its two specific values: (1) novel-scaffold rescue — it caught the
suzetrigine OOD miss that the fine-tune failed on; (2) scale/cost — library-screen at $0.025/mol
for breadth-first triage before expensive follow-up.

---

## Talking Points / Anticipated Questions

**Q: Why not just use the biggest ESM-2?**
A: We tested it. ESM-2-3B and 15B tie ESM-2-650M on NN-recall (both 0.850); 23× the parameters buy
nothing on the clustering task. The signal in our 40-gene panel is saturated. Bigger is not better here,
and the small model has a cleaner license.

**Q: Are these benchmark numbers or real?**
A: These are our numbers, on our targets, with our compounds. The ChEMBL panels, the Nav1.8 binder/decoy
panel, the 40-gene CRISPR-N panel, and the TSC2 deconvolution test are all Quiver-relevant substrate.
We deliberately avoided quoting only the paper benchmarks, which is exactly how you end up with a
model that works on BindingDB and fails on your ion-channel program.

**Q: Why is MAMMAL not the answer?**
A: MAMMAL was our starting point, and it has real value for protein-family clustering and BBBP
(comparable to ESM-2 and MapLight respectively). But it fails on ion-channel binder triage (DTI AUROC
0.43 on Nav1.8), its ClinTox head is worse than chance on external data (AUROC 0.24–0.47), and its
public generative weights are span-infillers, not a de-novo generator. Better specialized models
exist for every track it was considered for.

**Q: What about TxGemma?**
A: It's the highest *reported* public tox/ADMET model (~0.95 on TDC benchmarks) — and we should test it,
not dismiss it. Two honest caveats, neither fatal: (1) **License** — contrary to an earlier note, the
Health AI Developer Foundations terms *permit* non-clinical drug-discovery R&D (the models are trained on
commercially-licensed data); the only hard bar is *clinical* use (patient diagnosis/treatment) or shipping
it as a medical-device product. So for our internal triage it's usable. (2) **Unproven for us** — that
0.95 is a paper benchmark; we've never run it on our held-out CNS panels, which is the only number that
counts here. Plus it's a 9B/27B LLM (GPU, generated text, not a calibrated probability) vs. our CPU
fingerprint winners (MapLight/ADMET-AI). **Recommendation: benchmark TxGemma-2b/9b-predict on our exact
hERG/DILI/BBBP panels (~$1–2 GPU run); if it beats the specialists empirically, adopt it with the
clinical-use caveat.** Right now it's a candidate, not a rejected model.

**Q: Why can't off-the-shelf structure-based models (Boltz, AlphaFold) do selectivity?**
A: Because subtype selectivity for Nav paralogs is determined by subtle pocket differences — the models
learn pocket shape and chemical complementarity in aggregate, not per-paralog tuning. Our Tier-3
experiment confirmed this directly: suzetrigine, a clinically validated Nav1.8-selective drug, scores
last of 9 Nav paralogs in Boltz's own selectivity test. Structure is a useful binder-vs-decoy tool;
it is not a selectivity oracle. For fine selectivity, the path is Quiver's electrophysiology data.

**Q: Is the 0.50→0.92 AUROC gap on ion channels a real gain or a benchmark artifact?**
A: Evaluated on held-out chemical scaffolds (Murcko scaffold split) — not random held-out, which would
be easier. The scaffolds used at test time did not appear in training. The 0.67 ligand-only fingerprint
baseline confirms the target-sequence side adds meaningful signal. And the leave-one-channel-out failure
(Nav1.8 transfer AUROC 0.36) confirms that the improvement requires per-channel data — i.e. it is a
signal about Quiver's specific compounds, not a generic ion-channel pattern.

**Q: What's the one thing to build first?**
A: The ion-channel binder model fine-tuned on Quiver's own screening data (Track 2). It has the highest
ROI, the gap is the largest (0.50→0.92), and every other off-the-shelf alternative we tested also fails.
This is the one place where Quiver's proprietary measurement data directly closes a gap no public model
can close.
