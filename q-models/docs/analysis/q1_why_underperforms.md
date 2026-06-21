# Q1 — Why MAMMAL underperforms on Quiver's problems despite SOTA on 9/11 benchmarks

**Written 2026-06-01.** Audience: Rohan's boss (non-ML exec). Bar: empirical, decision-relevant,
defensible. Builds on `docs/COMPLETE_UNDERSTANDING.md`, `docs/FINDINGS.md`, `HANDOFF.md`, and the
paper deep-read (`docs/lit/01_paper_deepread.md`) + domain context (`docs/lit/04_domain_context.md`).
Confidence tags: **[HIGH]** convergent/reproduced, **[MED]** real but small-n, **[PAPER]**
author-reported, **[SPEC]** inference.

> **The boss's question, verbatim:** *"Is MAMMAL doing poorly because we are not using the
> fine-tuned version?"* Short answer: **mostly no.** For 7 capabilities we DID use IBM's fine-tuned
> weights and they reproduced the paper's headline numbers — and they were still not useful for our
> jobs. Fine-tuning is the missing piece for exactly ONE gap (single-target binder triage), and even
> there only as in-distribution chemotype triage, not novel-hit discovery. The rest is two deeper
> problems that no fine-tune fixes: **benchmark scores don't survive real-world deployment**, and the
> **base model is weak at the specific things we need** (cross-modal binding, similarity, generation).

---

## The 5-minute version (read this if nothing else)

MAMMAL is genuinely state-of-the-art on its leaderboard. That fact and "it doesn't help Quiver" are
both true at once, for four reasons that compound:

- **We were already using the fine-tuned versions.** For all 7 tasks where IBM publishes a
  fine-tuned checkpoint, we loaded *those exact weights* and reproduced the paper (BBBP AUROC 0.968,
  DTI NRMSE ~0.88, TCR 0.93, ClinTox ~1.0, solubility 0.73/0.83, plus the two per-target binder heads
  PGK2/WDR91). The disappointing results are **not** a "you used the wrong/base model" mistake. The
  weights are right; the *capability* is the problem. **[HIGH]**

- **"SOTA on a benchmark" and "works on my compound" are different claims.** A benchmark score is an
  average rank on a curated, pre-cleaned test set. Deployment asks a harder question one molecule at a
  time. Every classification head we tested ranks beautifully on its own dataset and then **fails out
  of distribution**: the BBB head waves through drugs that don't enter the brain (held-out true-negative
  rate 0.70 — it over-passes), and the toxicity head scores a perfect-looking AUROC ~1.0 by
  *memorizing* its ~112 training toxics and catches **0% of external clinical toxics** it never saw
  (misses cerivastatin, terfenadine, thalidomide). The scores also come out as hard 0/1 labels, not
  graded probabilities, so you can't even set a sensible threshold. **[HIGH]**

- **"SOTA" sometimes means "least-bad at a problem nobody has solved."** The drug-target binding score
  (DTI, NRMSE 0.906) is only ~9% better than just guessing the average affinity for every pair. That's
  not a MAMMAL flaw — the entire field is stuck near this ceiling on honest test splits (best is
  ~0.51 correlation). But it means the "SOTA" badge here buys a coarse re-ranker, not the binder oracle
  Quiver wants. **The value tracks how hard the task is, not the size of the trophy.** **[HIGH]**

- **Our biggest needs depend on the BASE model, where there is no fine-tune to save it.** Cross-modal
  binding (is this target near its ligands in one shared space?), compound similarity, and molecule
  generation are all *base-model* capabilities. We tested them and they're broken off-the-shelf:
  protein and molecule embeddings are near-orthogonal (cosine 0.08), Morgan fingerprints beat MAMMAL
  at similarity (0.96 vs 0.72), and the public model can't generate a usable novel molecule. **No head
  fixes a weak foundation.** Only ONE of our failing use cases — single-target binder triage — is the
  kind of gap a fresh per-target fine-tune could actually close (IBM's PGK2 head proves it: 0.97
  homolog selectivity), and even that is in-distribution chemotype triage, not novel discovery. **[HIGH]**

- **The paper never claimed an off-the-shelf general model.** Every single headline number in the
  paper is a *separate model fine-tuned for that one task*. The pre-trained model alone is **near random
  guessing** on the hard tasks (the authors' own ablation: HER2 binder AUROC 0.53 pre-trained vs 0.88
  fine-tuned). "SOTA on 9 of 11" has always meant "if you fine-tune a dedicated head per task," never
  "this one downloaded model is good at everything." Our experience is exactly what the paper's own
  design predicts. **[PAPER + HIGH]**

---

## Direct answer to "is it because we are not using the fine-tuned version?"

**Partly yes for one narrow gap, but mostly no.** For the 7 tasks with public fine-tuned checkpoints,
we *used the fine-tuned weights* and reproduced the paper's numbers exactly — so the let-down is not a
case of running the wrong model. Fine-tuning is the right lever for precisely one of our failing use
cases: **single-target binder triage**, which the off-the-shelf DTI head can't do (binder-vs-decoy
separation ≈ 0 on Nav1.8/mTOR) but a per-target head *can* — IBM's PGK2 head is the existence proof,
telling its hits from the PGK1 homolog's ligands at AUROC 0.97 and enriching binders ~11× in a spike-in.
So "fine-tune it ourselves on a Quiver target" is a live, promising option *for that one job* (Q14). But
the rest of where MAMMAL disappoints is **not** a fine-tuning problem: (1) the fine-tuned heads we *do*
have are honest on their benchmarks yet unreliable per-compound out-of-distribution (benchmark ≠
deployable), and (2) the capabilities Quiver most wanted from a "shared latent space" — cross-modal
binding retrieval, compound similarity, de-novo generation, calibrated embeddings — live in the **base
model**, which is weak there and has *no* fine-tuned head that could rescue it. And even the winning
fine-tune (PGK2) only re-recognizes its trained chemotype and can't rank by potency (Spearman ≈ 0), so
fine-tuning upgrades us from "nothing" to "in-distribution triage," not to a discovery engine. Net: the
weights were right; fine-tuning helps one gap; the deeper issue is *benchmark-vs-deployment* plus
*base-model weakness*, neither of which a fine-tune fixes.

---

## The receipts (so the bullets above are defensible)

### (1) The fine-tuned-version question, answered precisely

There are two different "fine-tuned" counts; keeping them straight kills the ambiguity:

- **11 paper benchmarks → 4 ship a public Table-1 checkpoint** (DTI, BBBP, ClinTox, TCR). The other 7
  (cell-type, 3× cancer-drug-response, antibody infilling, AbAg-bind, PPI-ΔΔG) have **no public
  weights** — unverifiable off-the-shelf, and the paper concedes this. **[PAPER]**
- **7 fine-tuned heads we actually ran and reproduced:** the 4 Table-1 heads above **+ solubility +
  the 2 per-target binder heads (PGK2, WDR91)**. All loaded as fine-tuned weights; all reproduced their
  reported numbers (BBBP 0.968, DTI ~0.88, TCR 0.93, ClinTox ~1.0, solubility 0.73/0.83, PGK2
  homolog-AUROC 0.97, WDR91 SPR-AUROC 0.816). **[HIGH]**

So we can cleanly separate two situations:
- **"Right fine-tuned weights, still not useful for us":** BBBP, ClinTox, DTI, the per-target heads —
  used as-fine-tuned, reproduced, and *still* fail our deployment bar (details in §2–§4).
- **"The capability we need has no public fine-tuned head":** single-target binder triage for *our*
  targets. The fix is an **in-house** fine-tune (Q14), not a different download. **[HIGH]**

### (2) Benchmark-vs-deployment gap (why SOTA AUROC ≠ a usable per-compound filter)

The benchmark and the deployment ask different questions. The benchmark: "rank a curated, scaffold-split
test set." Deployment: "is *this* compound brain-penetrant / toxic / a binder — yes or no, calibrated."
Every head clears the first and fails the second:

- **BBBP false-positive bias:** held-out **TNR 0.70** (vs TPR 0.98) — passes small peripherally-restricted
  drugs (cetirizine, atenolol, domperidone) as "penetrant." Usable as a soft *positive* signal, not a
  rule-out gate. **[HIGH]**
- **ClinTox memorization:** AUROC ~1.0 is *prima facie* impossible for clinical tox (field external
  ceiling ~0.80). It memorized ~112 training toxics → **0% sensitivity** to external clinical toxics. **[HIGH]**
- **Uncalibrated hard 0/1 outputs:** the MoleculeNet heads emit saturated labels (BBBP 95% / ClinTox
  100% of scores at ~0 or ~1) — not probabilities you can threshold or rank. **[HIGH]**
- **Mechanism:** a benchmark test set is pre-cleaned and scaffold-similar to training; real compounds
  are out-of-distribution. AUROC weights the whole list equally, but deployment only ever acts on the
  top sliver / a single yes-no — so a great average rank hides per-compound unreliability. **[HIGH]**

### (3) Task-difficulty reality ("SOTA" can mean "least-bad")

- **DTI NRMSE 0.906 = ~9% better than predicting the mean** (R² ≈ 0.18). Field ceiling on honest splits
  is ~0.51 Pearson; proper de-leaking drops the best benchmark 0.74→0.67. DTA is hard *for everyone* —
  so SOTA here is a coarse cross-target re-ranker, not a single-target oracle. A property of the field,
  not a MAMMAL defect. **[HIGH]**
- **BBBP 0.957** is a *commodity* number a 30-line Random Forest matches on a saturated/leaky benchmark.
- **ClinTox 1.0** is a red flag (memorization), not a result.
- **Per-target EF (PGK2 11×, WDR91 5×):** field mean EF ≈ 6 at top 2%; 10–50× is "very good." So PGK2's
  triage is squarely good, WDR91's is ordinary — *real but not a moat.* **[HIGH]**

### (4) Base-vs-finetuned split of OUR failing use cases

| Our failing use case | Depends on | Can a fine-tune fix it? |
|---|---|---|
| Cross-modal binding / shared latent space (Sapphire) | **BASE** model geometry | ❌ No public head; geometry is near-orthogonal (cosine 0.08), readouts anti-correlated −0.90 **[HIGH]** |
| Compound similarity / hit expansion | **BASE** embeddings | ❌ Morgan beats it (0.96 vs 0.72); use fingerprints **[MED]** |
| De-novo molecule generation | **BASE** decoder | ❌ Public weights expose only grammar-valid span-infill; design heads not public **[HIGH]** |
| Calibrated per-compound probabilities | fine-tuned heads, but **architecture** emits hard 0/1 | ❌ Recalibration ≠ generalization (ClinTox) **[HIGH]** |
| **Single-target binder triage (our targets)** | **missing per-target fine-tune** | ✅ **YES** — PGK2 head is the existence proof (0.97 homolog selectivity); pilot an in-house fine-tune (Q14) **[MED]** |

**The split is the whole answer to the boss:** four of five failing jobs are base-model / architecture
limits with no fine-tune to call on; only the fifth (binder triage) is the kind of gap fine-tuning
closes — and even then as in-distribution chemotype triage, not potency ranking or novel-hit discovery
(both heads saturate near 1.0, Spearman ≈ 0). **[HIGH]**

### (5) The paper-design point — pre-trained MAMMAL alone is ~chance

Every Table-1 number is a *per-task fine-tune* (the table footnote says each is "fine-tuned from
…ma-ted-458m for the corresponding task"). The authors' own ablation (Supp S5): HER2 binder AUROC
**0.53 pre-trained → 0.88 fine-tuned** — the pre-trained model is near chance; fine-tuning carries
every headline. So "SOTA on 9/11" was *never* a claim about an off-the-shelf general model. Our
empirical experience (base model = commodity; value is per-task fine-tuning) is exactly what the
paper's design implies. **[PAPER]**

---

## One-line close

The weights were right, the benchmarks were honest, and MAMMAL is still commodity enrichment for
Quiver — because a leaderboard score is not a deployable per-compound filter, half our SOTA targets are
"least-bad at a hard problem," and the capabilities we most wanted live in a base model that's weak at
them with no fine-tune to call on. Fine-tuning closes exactly one gap (in-distribution binder triage),
not the others. *State-of-the-art on shit is still shit.*
