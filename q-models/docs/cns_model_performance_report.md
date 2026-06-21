# CNS Model-Performance Master Report — best open model per Quiver capability

**Status:** Phase 5 synthesis of the overnight CNS campaign. Canonical companion to
[`models_tracks_scorecard.md`](models_tracks_scorecard.md) (the live scorecard); this document is the
*narrative* — what we tested, what won, what failed and **why**, and the build/fine-tune calls.
**Substrate:** real CNS data — the 19-target CNS ChEMBL panel (mTOR-pathway / ion-channel / GPCR / kinase),
TDC + B3DB de-risking sets, NeuroKG/Hetionet, funNCion channelopathy variants, and Quiver panels
(Nav1.8, mTOR, TSC2 deconvolution). **No paper-benchmark-only claims; no n=11 over-reads.**

> Quiver = CNS drug discovery broadly, not one target. The campaign's job was to map the best off-the-shelf
> model per capability and, crucially, to mark the places where **nothing off-the-shelf is good enough and
> the answer is to build/fine-tune on Quiver data.**

---

## 1. Executive summary — best model per CNS capability

| # | Capability | Best off-the-shelf | Headline (CNS substrate) | The honest caveat |
|---|---|---|---|---|
| 1 | Protein family clustering | **ESM-2-650M** ≈ MAMMAL-458M | best-layer NN-recall 0.875 (4-way tie at ceiling) | scale doesn't help (650M≈3B≈15B); use mid-stack layer + centering, not naive last-layer. SaProt/ProstT5 perfect on GPCRs |
| 2 | DTI / binder triage | **Boltz-2** overall; **BALM** fast cosine triage; **PLAPT** first-pass | Boltz Nav1.8 0.714 / mTOR 1.000; BALM kinase 0.80, mTOR-path 0.72 | **at CHANCE (0.50) on the CNS ion-channel family** zero-shot → fine-tune lever (§3) |
| 3 | Structure-based binding | **Boltz-2** | mTOR 1.000; co-folds the complex itself (no holo needed) | all pose-gated re-scorers (DrugCLIP, AEV-PLIG, GatorAffinity) fail on no-holo Quiver targets |
| 4 | BBBP de-risking | **MapLight** (CatBoost FP+desc) | held-out B3DB 0.919 > MolFormer 0.854; far-OOD 0.674 vs 0.590 | even the winner is ~0.67 on far-OOD chemotypes → ship a Tanimoto-to-train confidence flag |
| 5 | Tox / DILI / hERG | hERG **Morgan-FP+XGBoost / MapLight** (0.89); DILI **ADMET-AI + ChemBERTa-2** | hERG 0.890, most OOD-robust (far 0.81) | hERG collapses to chance far-OOD for LMs (0.59); ADMET-AI's TDC 0.985 is leakage, external ~0.83 |
| 6 | KG / hypothesis generation | **PROTON + ULTRA** (co-winners) | PROTON NeuroKG recall median 4.3%; ULTRA zero-shot, hub-robust, inductive | both are hypothesis-shortlist tools, not binder predictors; neither trustworthy on kinases |
| 7 | Cross-modal embedding | **BALM** (compound↔protein co-embedding) | Nav1.8 shared-cosine 0.857 vs MAMMAL's dead 0.08 | the trace↔compound "Sapphire bridge" track was **removed** (nothing public; build-don't-buy) |
| 8 | Generative chemistry | **Morgan FP + Enamine REAL NN** | works, boring; MAMMAL public weights are span-infillers | low priority; skip the punchlist |
| 9 | Off-target / paralog selectivity | **Boltz-2** (folded into Track 2) | ranks suzetrigine Nav1.8 #1 but margins narrow (0.31–0.44) | BALM **fails** paralog selectivity (biased to cardiac Nav1.5); sequence DTI can't deconvolve (TSC2: PKM2-vs-PPARD at chance) |
| 10 | Variant effect / channelopathy GoF-LoF | **funNCion** (Apache-2.0) | paper AUROC 0.897; ESM-2 LLR only 0.665 | MissION (0.925) is portal-only/not adoptable; Nav1.8 absent from public sets → build-don't-buy |

*(The Phase-3 new-model scout — `cns_new_models` / DTIAM, a BerMol drug tower ⊕ ESM-2 few-shot probe — was
**banked**: setup verified (274 MB checkpoint downloaded, towers configured) but an external **ChEMBL/EBI
HTTP-500 + unreachable outage** stalled the on-instance panel build at target 10/22 before any AUROC. It is
relaunchable when the ChEMBL API recovers (add a fail-fast socket timeout first); it is a non-load-bearing
datapoint that cannot overturn the §2 ion-channel verdict. See `results/cns_new_models_characterization.md`.)*

---

## 2. The one finding that matters most: ion-channel DTI is a fine-tune, not a model-shopping problem

Across **every** zero-shot DTI model we tested — BALM, PLAPT, Boltz-2 (marginal), ConPLex (broken),
DrugCLIP (below chance), AdaMBind (chance) — the **CNS ion-channel family sits at chance (≈0.50 AUROC)**.
This is not a truncation artifact and not a "we haven't found the right model" problem:

- **`cns_dti`**: BALM/PLAPT per-family — kinase 0.80, mTOR-pathway 0.72, GPCR 0.58, **ion channel 0.50**.
  Within ion channels it is bimodal: decent on Nav1.7 (0.85) / Nav1.8 (0.78) but at/below chance on
  **Cav1.2 (0.20), NMDA/GRIN (0.32–0.33), Nav1.1 (0.29), Nav1.5 (0.46)** — i.e. exactly the channels
  Quiver cares about beyond Nav1.8.
- **`trunc_test`** (the green light): a **supervised** probe (ESM-2-650M ⊕ Morgan-FP, logistic,
  **5-fold scaffold-split / Murcko GroupKFold**) hits **family-mean AUROC 0.919** on the same channels —
  with the **biggest gains on the worst zero-shot targets**: Cav1.2 0.20→0.95, NMDA 0.32→0.96,
  Nav1.1 0.29→0.94. Truncated (1022 aa) and full-length probes are **identical to 4 decimals** → long
  context is not the lever. **The gap is target-specific supervision, and it is worth ~+0.42 AUROC.**

**Decision:** the Quiver ion-channel fine-tune is **de-risked, not a gamble**. The 0.50→0.92 gap is the
measured value of supervised ion-channel data. Build it on Quiver's own ion-channel screening data
(actives + matched inactives) + the public Na-channel-class set (~12k cpds), scaffold-split eval, vs an
FP+GBT baseline. (Justification + data sources: [`finetune_justification_research.md`](finetune_justification_research.md).)

> Caveat kept honest: the probe is a per-target ligand+target QSAR ceiling (the protein embedding is constant
> within a target, so it doesn't prove ESM-2 protein features are *necessary*) — but the load-bearing claim,
> "actives separate from decoys with supervision on held-out scaffolds," is robust and is exactly what a
> fine-tune exploits.

---

## 2b. Update 2026-06-15 — both fine-tunes executed (the lever proven + its boundary)

We sourced more CNS data online and **ran the two fine-tunes** this report calls for:
- **Ion-channel binder fine-tune (Track 2):** cross-channel ESM-2-650M ⊕ Morgan-FP MLP on a pooled **online**
  corpus (full ChEMBL ion-channel + GtoPdb, 21,556 pairs) → **scaffold-split AUROC 0.98** (Nav 0.98 / Cav 0.99
  / NMDA 0.99) vs off-the-shelf 0.50 and a ligand-only FP-GBT baseline 0.67. **The §2 lever is confirmed at
  scale (0.92 probe → 0.98).** BUT leave-one-channel-out transfer fails (0/4; Nav1.8 0.36, NMDA 0.18) —
  cross-channel transfer does not work. *(`results/ionchannel_finetune_characterization.md`.)*
- **Nav variant GoF/LoF fine-tune (Track 9, NEW capability tested):** on 2,212 pooled SCION+funNCion Nav/Cav
  variants, leave-one-gene-out 0.36 (< ESM-2-LLR baseline 0.61) and held-out Nav1.8 transfer 0.48 ≈ chance.
  Direction is channel-specific — public data does not transfer to Nav1.8. *(`results/variant_finetune_characterization.md`.)*
- **The sharpened conclusion:** the fine-tune lever is real and strong **per-target** (0.50 → 0.98), and
  **nothing transfers across channels/genes** — so Quiver per-target screening + electrophysiology is the
  irreplaceable input. "Nav1.8 is build-don't-buy" is upgraded from *labels absent* to *transfer demonstrably
  fails*. New off-the-shelf models tested: ProTrek-650M (Track 1 — text-anchored assignment cracks E3/NR
  0.75/1.0), CToxPred2 + LigUnity (banked). Data sourced: `docs/cns_data_sources.md`; full writeup:
  `docs/overnight_summary_2026-06-15.md`.

## 2c. Deployed LIVE in the Explorer (2026-06-15)

The lever is not just measured — it's **running in the Explorer** (CPU, in-process, no AWS, gated by
`EXPLORER_LOCAL_MODELS=1`): **Track 2 (DTI)** = 15 per-target binder fine-tunes (Morgan-FP+GBT, scaffold-CV
0.95–0.997; Nav1.8 0.987, Nav1.7 0.995, DRD2 0.995, PPARD 0.997 vs zero-shot 0.50); **Track 4 (BBBP)** =
MapLight-class FP+GBT 0.903; **Track 5 (tox)** = hERG 0.881 + DILI 0.934. Every call is Tanimoto-to-train
confidence-gated; novel chemotypes (e.g. suzetrigine→Nav1.8) are low-confidence weak priors → Boltz-2. The
GPU/graph tracks (1 family-clustering, 3 structure, 6 KG, 9 variant) stay best-model-documented + AWS-served.
Which targets are fine-tune-ready vs need Quiver data: `docs/cns_finetune_readiness.md`. Detail:
`results/cns_pertarget_finetune_characterization.md`, `results/derisking_local_characterization.md`.

## 3. Per-track detail + receipts

### Track 1 — Protein family clustering
ESM-2-650M (best-layer, centered) NN-recall **0.875**, in a 4-way tie with MAMMAL-458M and ESM-2 3B/15B at a
saturated ceiling — **scale buys nothing**. Naive last-layer mean-pool *undersells*; use a mid-stack layer +
centering. GPCR specialists **SaProt-650M_AF2** and **ProstT5** are perfect (8/8 / 1.0). ESM-3-open ties the
top and nails nuclear receptors but is non-commercial. PROTON is a **negative** datapoint here (0.487).

### Track 2 — DTI / binder triage  → see §2 (the headline)
- **Boltz-2** overall winner; **BALM** = family-level cosine triage (Nav1.8 0.857 on the small panel, kinase
  0.79; **GPCR 0.43 below chance**; protein embedding is a coarse global pool, *not* pocket-aware — N-terminal
  window = pore window, identical AUROC). **PLAPT** added as a near-instant sequence-only first-pass (Nav1.8
  0.75, beats Boltz-2/ConPLex; doesn't displace BALM).
- The old "Nav1.8 0.857" was a **small-panel (n=11) over-read** — the proper 60-active panel gives 0.78, and
  PLAPT collapses to 0.48 there. Lesson institutionalized: **proper panels, not n=11.**
- **`cns_rejected_dti`** (ConPLex/DrugBAN re-test): **banked** at the ≤2-fix cap (DGL toolchain wouldn't
  assemble); result predictable (BindingDB-distribution → chance on ion channels, like BALM).

### Track 3 — Structure-based binding
**Boltz-2** is the only structure route that works on Quiver targets, **because it co-folds the
complex itself** (no holo crystal needed). Every pose-gated re-scorer fails on our no-holo targets:
**DrugCLIP** below chance (Nav1.8 0.39, mTOR 0.25 — pocket-definition-sensitive, we lack holo pockets);
**AEV-PLIG** scored 0/18 (pose-manufacturing gated, AlphaFold-404). Pattern: *if it needs a bound pose,
it doesn't land here.*

### Track 4 — BBBP de-risking
**MapLight** is the new primary: held-out **B3DB 0.919** > MolFormer-XL 0.854 across every axis (accuracy,
calibration Brier 0.126, and **far-OOD 0.674 vs 0.590** where MolFormer collapses), confirmed on 6,142
leakage-removed molecules — not a scaffold-split artifact. Commercial-OK, CPU-only, ~$0. MolFormer-XL → backstop;
ChemBERTa-2 (0.873) the commercial-LM second. **Ship a Tanimoto-to-train confidence flag** (near-domain
≈0.96, far-OOD ≈0.67). *(This is the held-out BBB funnel the campaign called for — `task #6` — done.)*

### Track 5 — Toxicity / DILI / hERG
hERG: **Morgan-FP+XGBoost / MapLight** (0.889–0.890, most OOD-robust at far-OOD 0.809 vs LMs' 0.56–0.61) —
switch the gate to this. DILI: **ADMET-AI** (honest external ~0.83) **+ ChemBERTa-2**. **ClinTox dropped**
(worse than chance externally). **CardioGenAI** not adopted — its multi-channel cardiac concept (NaV1.5/CaV1.2
heads) is the right *idea* (catches late-Na blockers our single hERG gate misses) but the shipped heads emit
saturated 0/1 calls with textbook errors (suzetrigine P_hERG=1.0 false-pos) and a closed vocab that can't
even be benchmarked. **Reliability lever:** applicability domain dominates — gate every tox call by
Tanimoto-to-train; novel scaffolds are low-confidence. Don't quote ADMET-AI's TDC numbers as external (leakage).

### Track 6 — KG / hypothesis generation
**PROTON + ULTRA co-winners.** PROTON (purpose-built NeuroKG) does **known-binder ranking** well
(median 4.3%, top-5% recall 57%) but is **strongly asymmetric** — forward "which drug binds X?" is hub-biased
noise (Bepridil #1 for 9 targets), and it has zero novel-chemistry capability (suzetrigine is not in the KG).
**ULTRA** (zero-shot, MIT, 168k params) **fixes both PROTON failures** — hub-robust shortlists + genuine
inductive novel-target ranking — verified on **both** Hetionet and PROTON's own NeuroKG substrate. Use ULTRA
as the default for novel/weakly-connected targets; keep PROTON for Quiver-private edges + cross-check.
Both are **hypothesis-shortlist tools, not binder predictors**; neither is trustworthy on kinases.

### Track 7 — Cross-modal embedding space
Reframed per Rohan: the useful cross-modal question is **"drugs and proteins in one space so we can read
nearest distances."** That is **solved by BALM** (real shared compound↔protein cosine geometry: Nav1.8 sep
+0.31 / AUROC 0.857, vs MAMMAL's dead 0.08), and it lives inside Track 2. The former trace↔compound "Sapphire
bridge" sub-track was **removed** — nothing public bridges it; it is a build-don't-buy on Quiver data.
*(On Ben's TSC2 compounds specifically, BALM/PLAPT cannot deconvolve PKM2 vs PPARD — both at chance, controls
outscore real binders — so co-embedding is family-level triage, not fine target deconvolution; see Track 9.)*

### Track 8 — Generative chemistry
**Morgan FP + Enamine REAL nearest-neighbor** — unglamorous, works. MAMMAL's public generative weights are
span-infillers, not de-novo designers. Low priority; punchlist skip.

### Track 9 — Off-target / paralog selectivity
**Boltz-2** (folded into Track 2) is the selectivity tool, but **soft**: it ranks suzetrigine Nav1.8 #1, but
paralog margins are narrow (0.31–0.44) and Nav1.5 leaks. **Sequence DTI cannot do fine selectivity:** BALM is
biased to cardiac Nav1.5 (only 2/7 Nav1.8 binders rank Nav1.8 top); on Ben's **TSC2 deconvolution**
(`tsc2_deconv`), neither BALM nor PLAPT separates PKM2 from PPARD (AUROC ~0.5, deconvolution 2/4 = chance,
Dasa-58 misclassified, control carbamazepine outscores real binders). **Target deconvolution is Quiver's own
functional/DFP signature-matching + Boltz-2 co-folding, not sequence DTI.**

### Track 10 — Variant effect / channelopathy GoF-LoF (NEW)
**funNCion** (Apache-2.0, paper AUROC 0.897) is the adoptable model. **MissION** (0.925, marginally better) is
**portal-only — no repo/weights → not adoptable.** Generic **ESM-2 650M masked-marginal LLR** scores
deleteriousness, not GoF-vs-LoF *direction* → insufficient (overall 0.665; SCN5A 0.74, SCN4A 0.89 but several
genes single-class). **Nav1.8 (SCN10A) + SCN3A are absent from all public variant sets → build-don't-buy** for
the Quiver-relevant channels.

---

## 4. The negatives — what does NOT work, and why (so we don't re-buy)
| Model | Track | Why it failed | Re-test? |
|---|---|---|---|
| ConPLex / DrugBAN / PerceiverCPI | 2 | BindingDB-distribution → ion channels at chance; DGL toolchain unassemblable | No — predictable |
| AdaMBind | 2/3 | few-shot path broken by upstream Trainer.py bug; **no LICENSE** (not adoptable) | No |
| DrugCLIP | 3/7 | pocket↔mol cosine below chance without holo pockets (we have none) | Only with crystal pockets |
| AEV-PLIG / GatorAffinity | 9/3 | pose-gated; 0 pairs scored on no-holo targets | No |
| CardioGenAI | 5 | saturated 0/1 heads, textbook errors, closed vocab un-benchmarkable | Borrow the *concept*, not the heads |
| CheMeleon | 4/5 | below MolFormer on BBB, below FP on hERG | No |
| MissION | 10 | portal-only, no weights | If they release weights |
| MAMMAL cross-modal cosine | 7 | dead (0.08 separation) | No — BALM wins |
| PROTON (forward prediction) | 6 | hub-biased noise; no novel chemistry | Use ULTRA / recall-only |

**Build-don't-buy (no off-the-shelf is good enough):** ion-channel DTI fine-tune (§2), Nav1.8/SCN3A
variant-effect (Track 10), NaV1.5/CaV1.2 cardiac heads on our own FP+GBT recipe (Track 5 concept from
CardioGenAI), and target deconvolution via Quiver functional signatures (Track 9).

---

## 5. Receipts & cost
All evals: `aws/<prefix>_eval.py` + `_userdata.sh`; raw results
`s3://rohan-mammal-bootstrap-20260610-213029/<prefix>/<prefix>_result.json`; per-model writeups in
`results/<prefix>_characterization.md`. Every instance self-terminated (shutdown-behavior=terminate +
watchdog); no strays. Campaign AWS spend held well under the **$45 cumulative cap** (per-model evals
~$0.3–0.75 on g5.xlarge/g5.2xlarge). Phases banked: `boltz_cns` (deferred — H200-class,
already done on the boltz branch, no spend), `cns_rejected_dti` (DGL toolchain cap, ~$0.3),
`cns_roundout` (redundant, no spend), `cns_new_models`/DTIAM (external ChEMBL/EBI outage stalled the build,
~$0.7, relaunchable).
