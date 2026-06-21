# Q2 — Specialist models vs one cohesive MAMMAL: the architecture call

**Written 2026-06-01 for the Q-MAMMAL evaluation (Quiver Bioscience). Audience: Rohan's boss —
numbers must be defensible.** This answers the second of the boss's questions: *should Quiver
integrate/test the specialist models that beat MAMMAL, or is one cohesive MAMMAL model better?*

It builds directly on the established evaluation — it does **not** re-derive it. Take as given
(receipts in `docs/COMPLETE_UNDERSTANDING.md`, `docs/FINDINGS.md`, `HANDOFF.md`, `docs/lit/02`,
`docs/lit/04`):

- For the 7 tasks with public checkpoints we used the **fine-tuned heads** and **reproduced paper
  SOTA** (BBBP 0.968, DTI NRMSE ~0.88, TCR 0.93, ClinTox ~1.0, solubility 0.73/0.83). The failures
  are **OOD / deployability / base-model weakness, not wrong weights.** [HIGH]
- **Cross-modal binding alignment is FALSIFIED off-the-shelf** (Phase 6): protein and SMILES
  subspaces near-orthogonal (cosine 0.08), the two proximity readouts anti-correlated (Spearman
  −0.90), per-target binder-vs-decoy AUROC ≈ chance (0.570). **This kills the "one shared latent
  space" advantage that was MAMMAL's whole cohesive-model argument.** [HIGH]
- **Per-target fine-tuning WORKS as in-distribution chemotype triage** (PGK2 homolog-selectivity
  AUROC 0.973, spike-in EF5 11×) — but not novel-hit, not potency, all in-distribution. [MED]
- Prior work also found **Morgan fingerprints beat MAMMAL for similarity** (0.96 vs 0.72) and a
  **hERG rule + pkCSM-class tox model beat MAMMAL ClinTox** (which has 0% external-toxic
  sensitivity).

> **Confidence tags:** [HIGH] reproduced/convergent · [MED] real but small-n/single-source ·
> [PAPER] author-reported, not independently verified by us · [SPEC] inference. Facts about
> external tools (license, hardware, adoption) are dated 2026-06-01 and sourced at the bottom.

---

## 0. The decision in three sentences

The "one cohesive model" thesis rested entirely on a **single shared cross-modal latent space**, and
our Phase 6 test falsified that off-the-shelf — so the cohesion argument has **already lost its
load-bearing premise**, and the choice is no longer "cohesion vs best-of-breed" but "a generalist
that is weak at the hard jobs vs specialists that are strong at them." **Adopt a best-of-breed funnel
for the jobs Quiver actually wants to do** (binder triage, structure/affinity, ADMET de-risking),
and **keep MAMMAL only for the two narrow things it is genuinely good at** (protein/gene-family
embeddings, BBBP as a soft *positive* signal) — these are cheap to keep because they are read-only
representation/enrichment, not pipeline-critical scoring. Concretely: **slot in ConPLex (binder
triage), Boltz-2 (structure + affinity), and ADMET-AI (multi-endpoint de-risking)**; keep MAMMAL as a
downstream embedding/soft-signal layer behind David's interface; do **not** try to make one model do
all of it.

This is not a close call. The cohesive-model advantage was never an *accuracy* advantage (the paper
never showed cross-modal transfer beating two specialists) — it was a *convenience* advantage (one
interface). Convenience is real but cheap to replicate (a thin dispatcher in front of N tools), while
the specialists' accuracy gaps on the hard jobs are **not** cheap to close (we exhausted the
off-the-shelf options and they bottom out at chance). You buy convenience back with ~200 lines of
router code; you cannot buy back binder-triage accuracy MAMMAL structurally lacks.

---

## 1. The specialists, scored on Quiver's actual jobs

For each: openness/license, hardware, install/integration effort, maturity/adoption, and **exactly
which Quiver job it serves**. All facts dated 2026-06-01.

### 1a. ConPLex — drug-target binder triage *(the job MAMMAL fails hardest)*

| Axis | Detail |
|---|---|
| **Quiver job** | **Single-target, decoy-resistant binder triage** + proteome-scale screening — "does compound X bind target Y, and not just look drug-like." This is *exactly* the capability MAMMAL's DTI head fails (Phase 2b: Nav1.8 +0.00, mTOR +0.10 binder-vs-decoy separation ≈ chance) and the cross-modal geometry fails (Phase 6). |
| **What it is** | Contrastive **protein-anchored co-embedding** built on **ESM-2** protein features; reduces DTI to a distance in a learned shared space; *purpose-built for decoy specificity* (the design goal is rejecting non-binders, not just ranking actives). Berger lab, PNAS 2023. |
| **Openness / license** | **MIT** — fully open, commercial use OK. Weights + training code public. |
| **Hardware** | GPU-friendly, CPU possible. Proteome × all-of-ChEMBL (~2×10¹⁰ pairs) in **<24 h on one A100** — embarrassingly cheap once protein/drug features are cached. Fits Quiver hardware trivially (even an M3 for small panels; one cloud A100 for proteome scans). |
| **Install / integration** | `pip install conplex-dti`, Python 3.9. v0.1.13 (May 2025). Readthedocs + CLI. **Low effort** — train/predict scripts shipped; the heaviest step is generating ESM-2 features (one pass). Integration cost: **~1–2 days** to wrap predict + a Quiver target/compound adapter. |
| **Maturity / adoption** | PNAS 2023, **~59 citations**, 150★/37 forks, **maintained through 2025**. Real external uptake (cited in 2025 proteome-scale VS work, e.g. SPRINT). Far more independently validated than MAMMAL's per-target heads (which have **0 independent benchmarks**). |
| **Caveat (honest)** | We have **not** run ConPLex on Quiver targets yet — the case is "purpose-built for the exact failure mode + open + cheap," not a measured Quiver win. **Recommend a head-to-head pilot** (ConPLex vs MAMMAL DTI vs MAMMAL per-target head) on a Quiver target with known binders/decoys before trusting it in production. The DTA field ceiling is real (best hard-split BindingDB Pearson ≈ 0.51) — ConPLex won't be an oracle either, but it is *built for* the triage axis MAMMAL ignores. |

### 1b. Boltz-2 — structure + binding affinity *(the job MAMMAL cannot do at all)*

| Axis | Detail |
|---|---|
| **Quiver job** | **"Target → score / pose a molecule"** with *structure* (MAMMAL can't do structure at all) **and** *affinity* (MAMMAL does poorly, R²≈0.18). Two outputs: `affinity_probability_binary` (binder-vs-decoy) and `affinity_pred_value` (graded affinity for hit-to-lead / analog ranking) — the latter is exactly the **potency ranking MAMMAL's per-target heads fail by construction** (saturate near 1.0, Spearman ≈ 0). |
| **What it is** | Open **AF3-class** structure predictor (proteins+ligands+nucleic acids) **plus** a binding-affinity module at **near-FEP accuracy, ~1000× faster than FEP**. MIT + Recursion + NVIDIA. |
| **Openness / license** | **MIT** — fully open, **no restriction on academic or commercial use.** (Contrast AlphaFold3: closed, non-commercial server, no commercial weights. Boltz-2 is the open AF3-class option.) |
| **Hardware** | **The compute-heavy one — flag this for the boss.** ~**24–40 GB VRAM** ideal (24/32 GB works for most inputs; **NVIDIA NIM build wants ≥48 GB**). Runtime ~**20–45 s per complex** on an A100 in pose+affinity mode → ~**80–120 complexes per A100-hour**. CPU works but is "significantly slower" — **not practical at scale.** So: a **cloud-GPU job**, not a laptop tool. Big screens (10⁵–10⁶ compounds) need real GPU budget (e.g. 10⁶ complexes ≈ ~10⁴ A100-hours brute-force → triage with a cheaper filter first; see funnel §3). |
| **Install / integration** | `pip install boltz[cuda] -U`. v2.2.1 (Sept 2025). Also available as a **managed NVIDIA NIM / hosted API** (BioLM, NVIDIA) — Quiver can call it as a service and skip the GPU-ops entirely for low volume. Integration cost: **~2–4 days** for the local path (env + GPU + MSA inputs); **~1 day** if consuming the hosted API. |
| **Maturity / adoption** | **By far the most adopted model here — 4,000★/834 forks**, very active (the Boltz lineage is the open AF3 community default), already spawning derivatives (Boltzina, LMI4Boltz VRAM tooling). This is a *well-supported* dependency, unlike MAMMAL (3 lifetime GitHub issues, zero independent benchmarks). |
| **Caveat (honest)** | Structure-based affinity has its own failure modes (needs a reasonable pocket; apo/disordered/allosteric targets degrade; MSA dependency). It is **not** a universal oracle. But on the "score a molecule against a structured target" job it is **strictly more capable and equally open** than anything MAMMAL offers. Compute is the real cost, not capability. |

### 1c. ESM-2 / ESM-3 / ESM-C — protein embeddings *(the job MAMMAL is actually good at — and a license trap)*

| Axis | Detail |
|---|---|
| **Quiver job** | **Protein/gene-family embeddings** for the CRISPR-N panel clustering and the Sapphire KG node features. This is the *one representation job MAMMAL holds its own at.* |
| **The in-repo result that matters** | Phase 6: **MAMMAL beats ESM-2 650M on our off-the-shelf naive mean-pool family-clustering recipe** (NN recall 0.92 vs 0.84; centering ESM made it *worse*, 0.76). **⟲ This overturns the "just use ESM" default for this specific recipe** and *clears the Sapphire-embedding blocker without adding an ESM dependency.* [MED — direction solid, CIs overlap, n=25; naive mean-pool is ESM's weakest extraction mode.] |
| **Openness / license** | **ESM-2: MIT, commercial OK** — on HF (8M→15B), `pip`/`transformers`, trivial. **ESM-3 and ESM-C-600M: NON-commercial off the shelf** (esm3-sm-open-v1, ESM-C-600M weights = research-only; commercial requires paid **Forge** API / **AWS SageMaker**). **ESM-C-300M is open.** **⚠️ Licensing trap:** the *strong* generative/successor ESM models are **not** free for commercial use — this alone is a reason not to casually swap MAMMAL (Apache-2.0) for ESM-3 in a commercial Quiver pipeline. |
| **Hardware** | ESM-2 8M–650M run comfortably on the M3/MPS or a small GPU; **ESM-2 3B won't fit on 18 GB**, 15B needs a real GPU. For Quiver's panel sizes, the small/medium ESM-2 checkpoints are laptop-class. |
| **Install / integration** | ESM-2 via `transformers` is the lowest-friction model in this whole doc — `model.encode(seq)` ergonomics MAMMAL's prompt syntax lacks. **~0.5 day.** |
| **Maturity / adoption** | ESM-2 is **the field-default protein backbone** — orders of magnitude more adoption than MAMMAL. This is the *commodity* layer. |
| **Recommendation** | **Keep MAMMAL embeddings as the current default for CRISPR-N/KG** (it survived the size-matched challenge), but treat **ESM-2 650M (MIT)** as the drop-in fallback/cross-check — **not** ESM-3/ESM-C-600M (commercial-gated). If embeddings ever become *core* infrastructure (not enrichment), re-benchmark on the real 1400-gene panel with each model's *best* extraction (selected layer / whitened), not naive mean-pool — that test could flip the result toward ESM. |

### 1d. ADMET-AI — small-molecule property de-risking *(replaces the broken ClinTox step)*

| Axis | Detail |
|---|---|
| **Quiver job** | The **ADMET de-risking funnel** — the step where MAMMAL's ClinTox is **unusable** (0% external-toxic sensitivity, memorization) and BBBP is a *positive-only* soft signal. ADMET-AI gives **41 calibrated TDC ADMET endpoints** in one call, including **BBB, hERG, DILI, CYP, clearance, solubility** — i.e. the whole mechanism-specific tox/PK panel the Phase-5 funnel proposed (PAINS/BRENK → hERG → DILI → BBBP), in one tool. |
| **What it is** | Chemprop-RDKit graph-NN multi-task model + 8 RDKit physchem properties; web tool **and** Python package; trained on TDC ADMET datasets. Swanson et al., *Bioinformatics* 2024. |
| **Openness / license** | **MIT** — fully open, commercial OK. Web server (admet.ai.greenstonebio.com) + pip package + Zenodo archive. |
| **Hardware** | **CPU-fine** (GPU optional, auto-used if present). Designed for **large-library batch** prediction. Laptop-class. |
| **Install / integration** | `pip install admet-ai`, installs in minutes, any OS. **Lowest-effort production dependency here (~0.5–1 day).** Batch API for thousands of SMILES. |
| **Maturity / adoption** | Widely used ADMET reference (TDC-aligned), peer-reviewed 2024, actively maintained, hosted web tool. Far more deployable as a *de-risking gate* than MAMMAL's hard-0/1 heads. |
| **Why it beats MAMMAL here** | (1) **Calibrated** continuous probabilities (MAMMAL's molnet heads are saturated hard 0/1 — unusable as thresholds/rankings). (2) **Multi-endpoint** (one tox mechanism per MAMMAL head vs 41 here). (3) **Maps to TDC** so it's externally benchmarkable. Prior work already concluded a hERG rule + pkCSM-class model beat MAMMAL ClinTox — **ADMET-AI is the single-package, open, maintained version of that conclusion.** *(pkCSM is an alternative but is web-form / less batch-friendly and not as cleanly packaged; ADMET-AI is the better fit for a programmatic funnel.)* |

### 1e. (for completeness) Morgan fingerprints — similarity / hit-list expansion

Not a "model," but the established in-repo result: **Morgan/ECFP fingerprints (RDKit) beat MAMMAL
embeddings for compound similarity (0.96 vs 0.72 same-class NN).** Free, instant, CPU, zero
integration. **Use fingerprints, not MAMMAL, to expand hit lists.** Listed here so the funnel is
complete and so no one reaches for MAMMAL embeddings for the similarity step.

---

## 2. The architecture call — best-of-breed vs one cohesive MAMMAL

### 2a. The cohesive-model argument has already lost its premise

The case for "one cohesive MAMMAL" was **never** that MAMMAL is the most accurate per modality — the
paper itself only ever benchmarked each task *within* its own modality against a single-modality
baseline, and **never demonstrated cross-modal transfer beating two specialists.** The case was that
MAMMAL has **one shared cross-modal latent space** — so a target and its ligands would be neighbors,
you could retrieve binders by proximity, co-embed a KG, and run everything through one interface with
one set of weights.

**Phase 6 falsified the load-bearing half of that.** Off the shelf there is no shared protein↔molecule
geometry: cross-modal cosine 0.08 (near-orthogonal), binder-vs-decoy AUROC ≈ chance (0.570), the two
proximity readouts anti-correlated (−0.90). The supervised DTI head — trained to extract exactly that
signal — also fails single-target triage. **So the cohesion is real only as a *single-interface
convenience*, not as a *capability*.** [HIGH]

That reframes the whole decision:

> It is **not** "one elegant cohesive model vs N messy specialists."
> It is "a generalist that is **weak at every hard job Quiver wants** but convenient, vs specialists
> that are **strong at those exact jobs** at the cost of N interfaces."

### 2b. Weighing it honestly (cost of N interfaces is real, but small and bounded)

**The genuine cost of best-of-breed** is maintenance: N packages, N environments, N input formats,
N upgrade cadences, N failure modes — and a thin orchestration layer to route a compound/target to
the right tool. That is real and should not be hand-waved.

But it is **bounded and cheap relative to the alternative**, for four reasons:

1. **The "one interface" benefit is replicable for ~200 lines.** David already built a MAMMAL
   interface; the same dispatcher pattern fronts ConPLex/Boltz-2/ADMET-AI (each is `pip install` +
   a `predict(smiles, target)` call). You keep the single-interface UX *and* the specialist
   accuracy. The cohesion MAMMAL offered was always an *integration* property, not a *model*
   property — so you can buy it back in software.
2. **All four picks are MIT/Apache + pip-installable + actively maintained** (ConPLex MIT, Boltz-2
   MIT, ADMET-AI MIT, ESM-2 MIT, MAMMAL Apache-2.0). No license blockers, no closed APIs forced.
   This is a much healthier dependency set than MAMMAL alone, which has **zero independent
   benchmarks and 3 lifetime GitHub issues** — i.e. *MAMMAL itself is the fragile dependency* (we hit
   the macOS TF-deadlock, the PEER-split trap, the vestigial-scalar-head trap, all undocumented, all
   solved in-house). Adding well-supported specialists *reduces* per-tool bus-factor risk.
3. **The specialists are not all hot paths.** Only Boltz-2 needs real GPU ops; ConPLex and ADMET-AI
   are laptop/CPU-class and run as cheap batch jobs; ESM-2 and Morgan are trivial. The maintenance
   surface is "one GPU service (Boltz-2, or just call the hosted NIM) + three pip libraries."
4. **You cannot buy back the accuracy.** We exhausted the off-the-shelf MAMMAL options for binder
   triage (three independent confirmations of ≈ chance) and structure (it has none). No amount of
   interface convenience closes that. The specialists' edge is on **capability**, which is the
   expensive thing; MAMMAL's edge is on **convenience**, which is the cheap thing. Optimize for the
   expensive thing.

### 2c. Where one-cohesive-MAMMAL still wins (and we keep it)

MAMMAL stays for the jobs where it is genuinely competitive **and** where "one interface, read-only,
no scoring-criticality" makes it the low-cost choice:

- **Protein/gene-family embeddings** (CRISPR-N panel, Sapphire KG node features): survived the
  size-matched ESM-2 650M challenge on our recipe; Apache-2.0 (vs ESM-3's commercial gate). Keep as
  default; ESM-2 650M as the open fallback.
- **BBBP as a soft *positive* de-risking signal** inside the funnel (not a rule-out gate): cheap
  enrichment flag, fine alongside ADMET-AI's calibrated BBB endpoint as a second opinion.
- **Optional in-house per-target chemotype-triage fine-tune** (Q14): PGK2 is the clean existence
  proof. This is a *Quiver-data* play, evaluated by EF/BEDROC on a held-out **scaffold** split —
  orthogonal to the off-the-shelf specialists, and worth piloting regardless of the funnel.

These three are **read-only / enrichment / experimental** — none is a pipeline-critical scoring gate,
so keeping MAMMAL for them costs almost nothing and we already have the interface.

---

## 3. Recommended posture — the funnel, concretely

**Adopt a best-of-breed funnel behind David's single dispatcher. Slot in three specialists; keep
MAMMAL for two narrow jobs + one optional in-house fine-tune. Do not pursue one-cohesive-MAMMAL for
the hard jobs.**

A hit-finding / de-risking funnel for "we have a target and a pile of compounds," cheap→expensive:

| Step | Job | Tool | Why this tool (not MAMMAL) | Cost |
|---|---|---|---|---|
| **0. Expand / dedupe hit list** | similarity | **Morgan/ECFP (RDKit)** | Beats MAMMAL embeddings 0.96 vs 0.72; free, instant | CPU, ~0 |
| **1. Binder triage (cheap, wide)** | "binds target, decoy-resistant?" | **ConPLex** | Purpose-built for the exact axis MAMMAL fails (≈chance); proteome-scale on 1 A100; MIT | GPU-light / cloud A100 for big scans |
| **2. ADMET de-risk (cheap, wide)** | tox/PK liabilities (hERG, DILI, BBB, CYP…) | **ADMET-AI** (+ MAMMAL BBBP as a 2nd-opinion *positive* flag) | 41 calibrated TDC endpoints; replaces MAMMAL ClinTox (0% external sensitivity, unusable) | CPU, minutes |
| **3. Structure + affinity (expensive, narrow)** | pose + graded affinity on the *survivors* | **Boltz-2** | Structure (MAMMAL: none) + near-FEP affinity + graded ranking for hit-to-lead (MAMMAL per-target heads saturate, Spearman≈0); MIT | **GPU-heavy** — run only on the top slice after steps 1–2 prune the library |
| **(parallel) Target/gene context** | family clustering, KG node features | **MAMMAL embeddings** (ESM-2 650M fallback) | Survived size-matched ESM-2 650M; Apache-2.0; no commercial-license trap | M3/small-GPU |
| **(optional) In-house gate** | Quiver-target chemotype triage | **MAMMAL per-target fine-tune** | PGK2 existence proof; EF/BEDROC on scaffold split | 1-GPU fine-tune |

**The funnel ordering is the cost story for the boss:** ConPLex + ADMET-AI are cheap and run on the
*whole* library to prune it; **Boltz-2's GPU heft only hits the small survivor set** (e.g. top 1–5%),
so the expensive model never sees the full 10⁵–10⁶ compounds. That keeps Boltz-2's ~80–120
complexes/A100-hour economical, and is the standard structure-AI deployment pattern (cheap filter →
expensive scorer).

### Migration / risk notes
- **Pilot before production.** ConPLex and Boltz-2 are *purpose-built + open + adopted*, **not yet
  measured on Quiver data.** Run one head-to-head each (ConPLex vs MAMMAL DTI on a Quiver target with
  known binders/decoys; Boltz-2 affinity vs known potencies on one series) before trusting them in
  the funnel. This mirrors the project's own meta-rule: *empirical results on our problems beat paper
  badges.*
- **Boltz-2 GPU budget is the one real cost delta** — flag it for approval before any cloud spend
  (per project policy: AWS spend changes need sign-off). Cheapest start: consume the **hosted NVIDIA
  NIM / BioLM API** for low volume, stand up a local GPU only if screen volume justifies it.
- **Do not adopt ESM-3 / ESM-C-600M** for embeddings — commercial-license-gated. ESM-2 650M (MIT) is
  the only ESM you'd swap in, and only as a cross-check; MAMMAL is fine here today.
- **Net dependency health improves.** We trade "one fragile, unbenchmarked, prompt-syntax model
  (MAMMAL)" carrying every hard job, for "MAMMAL on two easy jobs + three well-supported MIT
  specialists each on the job they were built for." Lower capability risk, modestly higher
  integration surface, fully bounded.

---

## 4. One-paragraph answer for the boss

**Integrate the specialists — this isn't close.** The "one cohesive MAMMAL" argument depended on a
single shared cross-modal latent space, and our own Phase 6 test falsified that off the shelf
(protein and molecule embeddings are near-orthogonal, binders aren't closer than decoys), so the
cohesion MAMMAL offered is just *one convenient interface*, not a capability — and that convenience
is replicable with ~200 lines of router code in front of best-of-breed tools. The jobs Quiver
actually wants (decoy-resistant binder triage; structure + binding affinity; real ADMET de-risking)
are exactly the jobs MAMMAL is weakest at, and three **open, MIT-licensed, pip-installable,
actively-maintained** specialists do each of them properly: **ConPLex** (binder triage, built for the
decoy-specificity axis MAMMAL scores at chance), **Boltz-2** (open AF3-class structure + near-FEP
affinity — the one GPU-heavy piece, so run it only on the survivor slice), and **ADMET-AI** (41
calibrated tox/PK endpoints, replacing MAMMAL's unusable ClinTox). **Keep MAMMAL for the two narrow
things it's genuinely good at** — protein/gene-family embeddings (it beat a size-matched ESM-2 650M on
our recipe, and unlike ESM-3 it's commercial-license-clean) and BBBP as a soft *positive* signal — plus
an optional in-house per-target chemotype-triage fine-tune on Quiver data. Compose them in a
cheap→expensive funnel (Morgan similarity → ConPLex → ADMET-AI → Boltz-2), pilot ConPLex and Boltz-2
on one Quiver target each before production, and budget the Boltz-2 GPU spend explicitly. The moat
stays Quiver's functional trace data + V1-T; this funnel is best-of-breed enrichment around it, not a
bet on any one vendor's "cohesive" story.

---

## Sources (verified 2026-06-01)

- **ConPLex** — [GitHub samsledje/ConPLex](https://github.com/samsledje/ConPLex) (MIT, 150★/37 forks,
  v0.1.13 May 2025, `pip install conplex-dti`, Python 3.9) ·
  [PNAS 2023, proteome×ChEMBL <24h on 1 A100, ~59 citations](https://www.pnas.org/doi/10.1073/pnas.2220778120) ·
  [readthedocs](https://conplex.readthedocs.io/en/latest/) ·
  [SPRINT 2025 follow-on VS](https://arxiv.org/pdf/2411.15418)
- **Boltz-2** — [GitHub jwohlwend/boltz](https://github.com/jwohlwend/boltz) (MIT commercial-OK,
  4,000★/834 forks, `pip install boltz[cuda]`, v2.2.1 Sept 2025) ·
  [Boltz-2 paper, near-FEP + 1000× faster](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12262699/) ·
  [Lab Manager: 24–40 GB VRAM ideal](https://www.labmanager.com/new-ai-model-boltz-2-may-save-early-stage-drug-discovery-labs-significant-time-and-money-34084) ·
  [NVIDIA NIM ≥48 GB VRAM](https://docs.nvidia.com/nim/bionemo/boltz2/latest/release-notes.html) ·
  [~20–45 s/complex, ~80–120/A100-hr](https://neurosnap.ai/blog/post/boltz-2-fast-controllable-physically-grounded-binding-affinity-prediction-and-how-it-leaps-past-boltz-1/68501df28b35985103e377f2) ·
  [Boltzina screening derivative](https://arxiv.org/html/2508.17555v1)
- **ESM-2 / ESM-3 / ESM-C** — [facebook/esm2_t33_650M (MIT)](https://huggingface.co/facebook/esm2_t36_3B_UR50D) ·
  [EvolutionaryScale ESM license — esm3/ESM-C-600M non-commercial, ESM-C-300M open](https://github.com/evolutionaryscale/esm/blob/main/LICENSE.md) ·
  [esm3-sm-open-v1 (non-commercial)](https://huggingface.co/EvolutionaryScale/esm3-sm-open-v1) ·
  [ESM Cambrian / ESM-C scales 300M/600M/6B](https://www.evolutionaryscale.ai/blog/esm-cambrian)
- **ADMET-AI** — [GitHub swansonk14/admet_ai (MIT)](https://github.com/swansonk14/admet_ai) ·
  [Bioinformatics 2024, 41 TDC endpoints incl. BBB/hERG/DILI](https://academic.oup.com/bioinformatics/article/40/7/btae416/7698030) ·
  [PyPI admet-ai](https://pypi.org/project/admet-ai/) ·
  [web tool](https://admet.ai.greenstonebio.com/)
- **In-repo grounding (not re-derived here):** `docs/COMPLETE_UNDERSTANDING.md` (Phase 6 cross-modal
  falsification, ESM-650M comparison, full scorecard), `docs/FINDINGS.md`, `HANDOFF.md`,
  `docs/lit/02_competitive_landscape.md`, `docs/lit/04_domain_context.md` (field ceilings: EF, DTA,
  BBB, DILI/hERG).

*Q2 of the Q-MAMMAL evaluation. Confidence tags and n explicit; external-tool facts dated and
sourced. Audience: defensible for Rohan's boss.*
