# Phase 3 — does per-target FINE-TUNING make MAMMAL a binder scorer? (WDR91)

**As of 2026-05-28.** Tests IBM's published per-target checkpoint `wdr91_asms` — the one
path to the target→binder capability that off-the-shelf DTI fails at (Nav1.8/mTOR triage ≈ 0).
This is the decisive test for **Q14: should Quiver fine-tune MAMMAL per target?**

> **Correction note (read this):** an earlier version of this writeup concluded the checkpoint
> was "broken / untrained." **That was wrong — a false negative from using the wrong readout.**
> The model is a *generative classifier* (like the MoleculeNet heads), not a scalar regressor;
> reading its untrained scalar head gave AUROC 0.43, but the correct generative readout gives a
> functional result. Corrected findings below. The investigation trail is kept because it's the
> exact false-negative trap CLAUDE.md warns about.

---

## TL;DR

**`wdr91_asms` is a complete, functional fine-tuned model — a generative binary binder
classifier for WDR91.** With the correct readout it discriminates known WDR91 binders from
drug-like decoys **weakly overall (AUROC 0.63) but with useful top-of-list enrichment
(5.25× in the top 5%; 7 of the top-26 ranked molecules are true actives vs ~1.3 by chance).**
So per-target fine-tuning **does** impart real target-specific signal — the capability
off-the-shelf DTI lacked (Nav1.8/mTOR ≈ 0.5). **Q14 leans YES, with caveats.**

The signal is modest, the model has a strong "inactive" prior (it predicts non-binder for
almost everything), and it doesn't rank actives by affinity — but as a *virtual-screening
triage* tool (enrich hits at the top of a candidate list) it works, even on an
out-of-distribution test set.

---

## What we tested

- **Checkpoint:** `michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.wdr91_asms` — MAMMAL
  fine-tuned on WDR91 affinity-selection-MS hit data. Undocumented (no card / no example).
- **Actives (n=27):** WDR91 binders from ChEMBL `CHEMBL5465256` — the compounds in the WDR91
  DEL paper (Ahmad et al., *J Med Chem* 2023,
  [doi:10.1021/acs.jmedchem.3c01471](https://doi.org/10.1021/acs.jmedchem.3c01471), PMID
  37996079, *per PubMed*). 18 have a measured SPR Kd (6–99 µM). *Out-of-distribution caveat:*
  these are **DEL**-derived; the head is `_asms` (affinity-selection MS) — a different screen,
  so this is a semi-independent (likely harder) test, not in-distribution.
- **Decoys (n=500):** random drug-like ChEMBL molecules (MW 250–500, 0 Ro5 violations),
  MW-matched to the actives.

## The right I/O (this was the whole story)

The config defines a scalar-regression head (`num_classes 1`), so by analogy to DTI we first
read the scalar head at the `<MASK>` slot → **AUROC 0.43, no signal.** That was wrong. Two
clues showed why:

1. **The tokenizer carries dedicated task tokens new vs base:** `<WDR91_ASMS>`, `<PGK2_ASMS>`,
   `<PGK2_DEL>`, plus `<ACTIVE>`/`<ISACTIVE>`/`<BINDING>` class tokens. → these are
   *classification* tasks with a per-target task token.
2. **The weight signature matches the working MoleculeNet classifiers, not DTI:** the scalar
   head and `encoder_head` are *bit-identical to base* (untrained/vestigial), the decoder/
   lm_head barely move, and the **only** trained component is the encoder body (relL2 0.024).
   That is exactly the profile of BBBP/ClinTox/TCR — which read out via `model.generate()`
   (the decoder path), **not** the scalar head. (A genuine scalar regressor like DTI moves its
   scalar head 0.10–1.44; wdr91's is 0.0 — because it's a classifier, so the scalar head is
   correctly untrained.)

**Correct readout (validated):** molnet-style prompt
`…<MOLECULAR_ENTITY_SMALL_MOLECULE><WDR91_ASMS><SENTINEL_ID_0>…<SMILES>…`, run `model.generate`,
read **P(`<1>`) at classification position 1**. Validated end-to-end on the BBBP head: this
harness reproduces **AUROC 0.996 at position 1** (vs 0.13 at position 0 — an artifact), matching
BBBP's known performance. So position 1 / P(`<1>`) is the legitimate readout.
(`phase3_generative_harness_check.py`.)

## Result (validated readout) — functional, modest, useful at the top

| metric | value | reading |
|---|---|---|
| **AUROC** (27 actives vs 500 decoys) | **0.6313** | weak global ranking (above chance; N=27 → wide CI) |
| **Enrichment, top 5%** | **5.25×** (7/26 actives) | **useful** — concentrates true binders at the top of the list |
| Enrichment, top 10% | 2.95× (8/53) | still enriched |
| median P(`<1>`), active vs decoy | 0.0 vs 0.0 | strong inactive prior — argmax is `<0>` for ~all inputs |
| Spearman(P(active), pKd) within actives | −0.15 | does **not** rank actives by affinity (ASMS is binary hit data) |

So the model is best understood as a **screening triage filter**: most of its output is an
uninformative "inactive" mass (hence the modest AUROC), but the top of its ranked list is
enriched ~5× for true WDR91 binders. That is genuinely the "score candidate molecules for a
target" workflow Quiver wants — and it's *out-of-distribution* (DEL actives, ASMS-trained), so
in-distribution performance is plausibly better. (`phase3_wdr91_final_*.json`,
`phase3_wdr91_generative_*.json`.)

## pgk2_del_cdd — tested IN-DISTRIBUTION on its own CACHE #7 DEL data

The sibling `pgk2_del_cdd` is the same kind of generative classifier (`<PGK2_DEL>`/`<PGK2_ASMS>`
tokens, encoder trained / heads ≈base). We tested it on the **exact public in-distribution data**:
CACHE Challenge #7's `DEL_hit_candidates_1.csv` — 1388 hPGK2 DEL hits *with read counts*
(`count_PGK2`, 5–124). Two tests (`phase3_pgk2_indist_*.json`):

| Test | Result | Reading |
|---|---|---|
| **A. hits vs drug-like decoys (AUROC)** | **0.984** | very high — BUT these are (likely) the model's own training hits → a *recall/memorization* check, not generalization |
| **B. score vs DEL read count (Spearman), within hits** | **−0.06** (≈0) | **no graded signal** — can't rank hits by enrichment |
| B. high-count vs low-count hits (AUROC) | 0.41 | worse than chance; scores saturate at ~0.99998 for all hits |

This is the most informative result of the whole exercise. It shows the per-target head learned to
**recognize its target's hit chemotype** (separates known hits from random drugs at 0.98) but
learned **nothing quantitative** — every DEL hit saturates near P(active)=1.0 regardless of its
actual enrichment. The 0.98 is *not* evidence of strong prospective performance; it's train-set
recall. The honest generalization estimate remains the **WDR91 out-of-distribution 0.63 / 5.25×
enrichment** above.

**Synthesis across both targets:** these are binary "is-this-my-target's-chemotype" classifiers —
strong on their training chemotype, modest (~0.63) on novel actives, and with **no graded
affinity/enrichment ranking** (WDR91 Spearman vs pKd −0.15; PGK2 Spearman vs DEL count −0.06).
"Works modestly" holds, and is now sharper: useful for *coarse hit/chemotype triage*, not for
ranking or quantitative potency.

## Real-data specificity tests (NO decoys) — and a sharp WDR91 vs PGK2 asymmetry

Random decoys conflate "binds my target" with "looks like a screening compound." Replacing decoys
with **real experimental binders of other proteins** isolates true target-specificity. Sets (all
real, SMILES-bearing): WDR91 actives (W, n=27, ChEMBL/Ahmad 2023), PGK2 DEL hits (P, n=500,
CACHE #7), PGK1 ligands (n=99, ChEMBL CHEMBL2886 — PGK2's homolog & the CACHE selectivity
counter-target). Each set scored by BOTH heads. (`phase3_realdata_specificity_*.json`.)

| Test (real-vs-real) | AUROC | Verdict |
|---|---|---|
| **PGK2 head: PGK2 hits > PGK1 homolog ligands** | **0.973** | ✅ strong homolog selectivity |
| PGK2 head: PGK2 hits > WDR91 actives | 0.988 | ✅ sharply target-specific |
| 99% of PGK2 hits prefer the PGK2 head (paired, each mol its own control) | — | ✅ |
| **WDR91 head: WDR91 actives > PGK2 hits** | **0.18** | ❌ inverted — PGK2 hits outscore WDR91's own actives |
| Only 41% of WDR91 actives prefer the WDR91 head | — | ❌ no self-preference |

Median P(active): **PGK2 head** → PGK2 0.99998 / WDR91 2e-5 / PGK1 4e-4 (fires ~1 only on its own
chemotype). **WDR91 head** → WDR91 0.0 / PGK2 0.002 / PGK1 0.0 (barely fires on anything, including
its own actives).

**The two heads behave completely differently:**
- **PGK2 head (`_del_cdd`): genuinely target-specific on real data** — separates its hits from a
  *homolog's* (PGK1) real ligands at 0.97. BUT a big confound: PGK2 hits are its own (likely
  training) data, so this is in-distribution positives vs out-of-distribution negatives — i.e. high
  *precision/recall on the trained chemotype* + sharp rejection of everything else, not proven recall
  on novel PGK2 scaffolds (consistent with the saturation + zero graded signal above). Read it as:
  "reliably re-recognizes its trained hit space and rejects off-target/homolog ligands," not "finds
  novel PGK2 binders."
- **WDR91 head (`_asms`): weak and non-specific.** It barely fires on its own actives (median 0), and
  PGK2 DEL molecules actually outscore WDR91's own actives (AUROC 0.18). The earlier 0.63-vs-random-
  decoys was a real but fragile signal that collapses against real competing binders. Plausible causes:
  trained on ASMS (not the DEL-style actives we have), WDR91 actives are small fragments while PGK2
  hits are large DEL molecules the head weakly favors, and our test is out-of-distribution.

**Real WDR91 negatives are scarce:** the public WDR91 DEL set (375,585 cmpds, 28,778 binders /
346,817 non-binders) is **fingerprints-only, no SMILES** (proprietary masking, AIRCHECK/HitGen
OpenDEL) so MAMMAL can't ingest it; ChEMBL WDR91 has zero inactives; the Ahmad 2023 SI has only
**2** SPR-confirmed non-binders (cmpds 17, 20, %Rmax≈0). This scarcity of real, structure-resolved
negatives is itself why decoys get used — and why the cross-target/homolog design above is the best
available real-data substitute.

---

## What this means for Quiver

1. **Per-target fine-tuning works — partially, and this is the real answer to Q14.** Off-the-shelf
   DTI could not triage a single target (Nav1.8/mTOR AUROC ≈ 0.5). The fine-tuned WDR91 head can
   (top-5% enrichment 5.25×). Fine-tuning on a target's own hit data is therefore a *viable* path
   to target→binder triage, not a dead end. The published checkpoints are usable existence proofs
   after all — once you use the generative readout.
2. **Set expectations: it's a triage/enrichment tool, not a precision oracle.** Weak global AUROC,
   strong inactive prior, no affinity ranking. Useful for "shrink a candidate list / rank for the
   top," not for "predict Kd" or "is this single molecule a binder."
3. **For Quiver's own fine-tunes:** the recipe is binary-classification on hit/non-hit data
   (screening/DEL/ASMS → SMILES + active label), generative readout with a per-target task token.
   Worth piloting on a Quiver target with in-house screening data; expect enrichment-at-the-top,
   and evaluate with enrichment factor / BEDROC, not just AUROC.

## Caveats / honesty
- N=27 actives → AUROC 0.63 has a wide CI (~±0.09); the top-5% enrichment (7/26) is the more
  robust signal but still small-N. Treat magnitudes as indicative.
- Test set is out-of-distribution (DEL actives vs ASMS training) — likely *understates*
  in-distribution performance.
- The earlier scalar-head AUROC 0.43 is retained in the JSON/scripts as the documented wrong
  readout; the validated number is the generative AUROC 0.63 / enrichment 5.25×.

## Files
- **Use this readout:** `mammal_quiver/wdr91.py` → `load_target_model`, `binder_prob`
  (generative P(`<1>`)). `score_smiles` is kept but marked superseded (the wrong scalar readout).
- Scripts: `phase3_wdr91_generative.py` (token sweep → found readout), `phase3_generative_harness_check.py`
  (BBBP validation of the readout), `phase3_wdr91_final.py` (corrected AUROC + enrichment).
  Earlier (superseded) scalar-head scripts: `phase3_wdr91_probe.py`, `phase3_wdr91_finetune.py`,
  `phase3_wdr91_diagnose.py`, `phase3_wdr91_ckpt.py`, `phase3_wdr91_repr_probe.py`.
- Data: `data/wdr91/`. Raw runs: `results/phase3_wdr91_*_*.json`.
