# Phase 6 — Cross-modal alignment: does MAMMAL share a protein↔molecule binding space?

**As of 2026-06-01.** Tests the single most load-bearing claim behind "MAMMAL as Sapphire's
latent-space layer": does the base `ma-ted-458m` model embed a protein target and its known
small-molecule binders into a **shared space** where binders sit systematically closer to the
target than matched decoys? Raw run: [`phase6_crossmodal_alignment_20260601_131645.json`](phase6_crossmodal_alignment_20260601_131645.json).
Script: [`../experiments/phase6_crossmodal_alignment.py`](../experiments/phase6_crossmodal_alignment.py).

---

## TL;DR — verdict: **NO. Cross-modal binding alignment does not exist in the base embedding space.**

Across **6 target+ligand sets** spanning 6 protein families (WDR91, PGK2/PGK1, EGFR kinase,
ADRB2 GPCR, SCN10A ion channel, ESR1 nuclear receptor), with two independent operationalizations
of "cross-modal proximity," **MAMMAL does not place binders closer to their target than decoys in
any consistent, mechanism-bearing way.** The two readouts not only fail to reach a usable AUROC —
**they are anti-correlated** (Spearman of per-target AUROC between the two methods = **−0.90**),
which is the opposite of what a real shared space would produce. The pooled AUROCs (~0.62–0.64)
are a *pooling artifact*, not a binding signal (see "Why the pooled number lies" below).

**Direct implication for the Sapphire pitch:** the "shared latent space where a gene/target and
its ligands are neighbors" is **not a property of MAMMAL's off-the-shelf embeddings.** Protein and
SMILES occupy **largely disjoint subspaces** (within-molecule cosine 0.72, within-protein 0.28,
but cross-modal cosine a tight **0.08, range [0.013, 0.182]**) — there is almost no shared axis on
which "binding" could be read by proximity. This corroborates, from the representation side, the
earlier finding that MAMMAL's *purpose-built* joint binding head (DTI PEER) also fails single-target
binder-vs-decoy separation (Nav1.8 +0.004, mTOR +0.105 in pKd; `phase2b_quiver_targets.md`). If even
the supervised binding head barely separates, the unsupervised embedding geometry has no reason to,
and it doesn't.

This is a **clean negative**, and a decision-relevant one: a shared protein/ligand retrieval space
is **not** something to buy MAMMAL for. (What MAMMAL *is* good for is unchanged — see the per-capability
cheat sheet in `HANDOFF.md`.)

---

## What "cross-modal proximity" can even mean here (and why we tested two forms)

Protein (AA) and SMILES tokenize into **different sub-vocabularies** of MAMMAL's modular tokenizer,
so it is not obvious that a cosine *between* a protein embedding and a molecule embedding means
anything. We tested both readings the architecture admits, on the **base model only** (no task head):

- **(A) Separate-encode cosine — the literal "shared latent space" claim.** Embed the protein alone
  and each molecule alone (masked mean-pool of the encoder's last hidden state, 768-d, L2-normalized —
  the same `mammal_quiver.embed` path used in Phase 2c), then score each molecule by
  `cos(target_emb, mol_emb)`. If binders are "near" their target, binder cosines > decoy cosines.

- **(B) Joint-encode block alignment — the alternative the architecture implies.** Co-encode
  protein + SMILES in **one** encoder pass using the *exact DTI-task prompt* (verified against
  `mammal.examples.dti_bindingdb_kd.task.DtiBindingdbKdTask.data_preprocessing`), but on the **base**
  model with **no DTI head**. In that pass the molecule tokens cross-attend to the protein tokens.
  We score by `cos(pooled molecule-token block, pooled protein-token block)` — a *target-conditioned*
  proximity. (We confirmed the token-block segmentation: the protein block is exactly the residue
  tokens between the 1st `<SEQUENCE_NATURAL_START>/END`, the molecule block the atom tokens between
  the 2nd pair; on WDR91 this recovers 747 residue tokens + 9 atom tokens, matching the real lengths.)

- **(A2) Target-specificity control.** For each binder, rank all 6 target proteins by cosine and ask:
  is the binder's *own* target the nearest? This controls for the "all molecules look vaguely alike to
  all proteins" confound that a single-target AUROC can't see.

Effect sizes reported throughout: AUROC, Cohen's *d*, Mann-Whitney *U* p-value. Decoys = a fixed,
shared pool of drug-like ChEMBL molecules (the curated WDR91 decoy set; 40 for leg A, a 12-decoy
subset for the expensive leg-B joint passes), target-agnostic by construction.

---

## Results

### Modality diagnostic — cosine is modality-dominated (the root cause)

| within-protein cos | within-molecule cos | cross-modal cos (mean) | cross-modal range |
|---|---|---|---|
| 0.278 | 0.725 | **0.080** | [0.013, 0.182] |

Molecules cluster tightly with each other (0.72) and proteins moderately with each other (0.28), but
*any* protein↔*any* molecule cosine sits in a narrow band near 0.08. The two modalities are in
**nearly orthogonal subspaces.** There is barely any shared dimension on which a binding-specific
"closeness" could live — so a proximity-based binder/decoy test starts with almost no usable signal,
and what little variance exists is dominated by molecule chemotype, not the target.

### (A) Separate-encode cross-modal cosine — inconsistent, no usable signal

| Target | family | n_binder / n_decoy | AUROC | Cohen's *d* | MWU p |
|---|---|---|---|---|---|
| WDR91 | WD-repeat | 64 / 40 | 0.665 | +0.69 | 0.005 |
| PGK2/PGK1 | kinase/metab | 40 / 40 | **0.225** | **−1.06** | 0.000 |
| EGFR | kinase | 6 / 40 | 0.842 | +1.07 | 0.007 |
| ADRB2 | GPCR | 6 / 40 | 0.454 | −0.10 | 0.720 |
| SCN10A | ion channel | 6 / 40 | 0.350 | −0.44 | 0.240 |
| ESR1 | nuclear recep | 5 / 40 | 0.885 | +1.84 | 0.005 |
| **mean-of-target** | | | **0.570** | | |

Three targets look "positive" (ESR1 0.885, EGFR 0.842, WDR91 0.665), but three are null-to-**inverted**
(PGK2 0.225 with binders *farther* than decoys; SCN10A 0.350; ADRB2 0.454). A real shared binding
space does not place a target's true ligands systematically *farther* than random drugs — the
inversions alone falsify the "alignment" reading. The apparent positives are best explained by
**chemotype clustering**: ESR1's ligands are steroids/SERMs and EGFR's are 4-anilinoquinazolines —
tight chemical families that differ from the generic drug-like decoy pool, so "looks like this
scaffold class" gets read as "near the target," with no actual target binding involved.

### (A2) Target-specificity — weak, ~chance by the stricter metric

| metric | observed | chance | read |
|---|---|---|---|
| rank-1 accuracy (binder's nearest of 6 targets is its own) | 0.496 | 0.167 | 3× chance, but unreliable |
| mean rank of true target (1=best, 6=worst) | **3.15** | 3.5 | essentially chance |

A binder lands closest to its own target ~50% of the time (above the 17% chance), but its *average*
rank among the 6 targets is 3.15 vs a 3.5 chance baseline — i.e. once you look past the single best
hit, the true target is no better placed than a coin flip. The rank-1 number is carried by the same
2–3 tight-chemotype targets, not by genuine target discrimination.

### (B) Joint-encode block alignment — also no signal, and it *disagrees* with (A)

| Target | AUROC | Cohen's *d* | MWU p | note |
|---|---|---|---|---|
| WDR91 | 0.533 | +0.14 | 0.770 | ~chance |
| PGK2/PGK1 | 0.661 | +0.63 | 0.157 | modest + |
| EGFR | 0.306 | −0.59 | 0.190 | inverted |
| ADRB2 | 0.889 | +2.08 | 0.009 | strong + |
| SCN10A | **nan** | — | — | molecule block truncated away (1956→1250 aa cap pushes SMILES past the 1512 limit) |
| ESR1 | 0.200 | −1.06 | 0.058 | inverted |

### The decisive statistic: the two readouts are anti-correlated

**Spearman(leg-A AUROC, leg-B AUROC) over the 5 evaluable targets = −0.90.** The targets that look
"aligned" under separate-encoding (EGFR 0.842, ESR1 0.885) are the *most inverted* under joint-encoding
(0.306, 0.200), and vice-versa (ADRB2 0.454 → 0.889). If MAMMAL had a coherent shared binding space,
the two proximity measures would agree and both exceed 0.5. They do the opposite. This is the clearest
evidence that **neither readout reflects a stable binding-relevant geometry** — each is picking up
different chemotype/length/scale artifacts that happen to point different ways.

### Why the pooled number lies

Pooled AUROC is 0.620 (leg A) / 0.645 (leg B), which looks "weakly positive." It is an artifact of
**pooling across targets with different binder-cosine baselines.** Targets with large binder sets and
high mean cosine (WDR91, the steroid/quinazoline families) dominate the pooled positive set; the
pooled metric then partly measures "which target" rather than "binder vs decoy." The honest
per-target picture (mean-of-target AUROC 0.570, with half the targets at/below 0.5 and the two methods
anti-correlated) is the one to trust. Do **not** quote the pooled 0.62 as evidence of alignment.

---

## Method caveats (read before citing)

1. **Embedding = masked mean-pool, L2-norm.** Standard, but a single pooled vector can wash out a
   localized binding-pocket signal. A negative here is "no *global*-embedding alignment"; it does not
   prove no signal exists in some learned projection of token-level states. (But note: the supervised
   DTI head, which *is* trained to extract exactly that, also fails — so a hidden recoverable signal
   is unlikely to be strong.)
2. **SCN10A leg-B is `nan` by design.** For proteins > 1250 aa the AA block is truncated and the SMILES
   block is pushed past the 1512-token encoder cap, so the molecule's token block doesn't survive the
   joint pass; `joint_block_cos` correctly returns `None` rather than scoring garbage. Joint-encode
   proximity is simply **not computable for large targets** without a different prompt budget — itself
   a practical limitation for any "co-encode the target + ligand" Sapphire workflow on big proteins.
3. **Decoy pool is shared & drug-like, not per-target property-matched (DUD-E style).** This makes the
   *positive* targets look better than they should (steroid-vs-random is easy), so it biases **toward**
   finding alignment. The negative result holds despite that favorable bias. A property-matched decoy
   set would likely push the "positive" AUROCs down further.
4. **Small binder sets for the classic targets** (EGFR/ADRB2/SCN10A/ESR1: 5–6 each) → wide CIs on those
   per-target AUROCs. The conclusion does not rest on any single target; it rests on (i) the modality
   diagnostic, (ii) the −0.90 cross-method anti-correlation, (iii) the near-chance target-specificity.
   WDR91 (64 binders) and PGK2/PGK1 (40) are the well-powered anchors, and both are unremarkable
   (0.665/0.533 and 0.225/0.661).
5. **A few decoys could in principle be real binders of a classic target** (random ChEMBL draws). This
   adds label noise but cannot manufacture the anti-correlation or the orthogonal-subspace geometry.
6. **Base checkpoint only, by design** (one-model-in-RAM constraint). The DTI-head comparison is cited
   from `phase2b`, not re-run. The base model is the right object to test for the "shared latent space"
   claim — that claim is about representations, not a supervised head.

---

## How this fits the broader MAMMAL evaluation

- It closes the **most important untested claim** behind treating MAMMAL as Sapphire's latent layer.
  Combined with the established results — DTI single-target triage ≈ chance (`phase1`/`phase2b`), Morgan
  fingerprints beat MAMMAL embeddings for molecule similarity (`phase2a`), per-target fine-tuning only
  re-recognizes its trained chemotype (`phase3`) — the picture is consistent: **MAMMAL's molecule-side
  representation is weak, and there is no protein↔molecule bridge to exploit.**
- What survives unchanged: protein/gene embeddings recover functional family (Phase 2c, NN 0.92) and the
  de-risking heads work in their lane (BBBP as a soft positive signal). MAMMAL stays **commodity
  enrichment**; the moat stays Quiver's functional trace data + V1-T.

## Reproduce
```bash
USE_TF=0 USE_FLAX=0 PHASE6_FORCE_CPU=1 \
  /opt/anaconda3/envs/mammal/bin/python experiments/phase6_crossmodal_alignment.py
```
(`PHASE6_FORCE_CPU=1` pins to CPU — this 18 GB machine thrashes swap when MPS competes for unified
RAM; CPU with `torch.set_num_threads(4)` was ~5× faster end-to-end here. Runtime ~4–5 min.)
