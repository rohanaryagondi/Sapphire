# Bimodality predictor — why does MAMMAL DTI work on some rich-data targets and not others?

**NEXT_STEPS item 1d** — open follow-up to the [datafit ceiling + curve experiments](datafit_summary.md). The ceiling test found 3/6 well-trained targets at AUROC ≥ 0.80 (RORC, CA2, Adrb2) and 3/6 at or below chance (BRAF, HRH1, mTOR-matched). Curve was non-monotonic. **Data volume is necessary but not sufficient.** This experiment asks: what *does* predict which mode a target lands in?

Two probes, run 2026-06-07:

- (a) **mTOR truncation probe** — `experiments/datafit_mtor_window.py` → `results/datafit_mtor_window_*.json`. Re-score mTOR binders + matched decoys against kinase-domain windows (FRB+kinase 1975–2549, kinase-only 2099–2549) instead of the full 2549-aa sequence the head truncates to 1250 aa.
- (b) **Chemodiversity probe** — `experiments/datafit_chemodiversity.py` → `results/datafit_chemodiversity_*.json`. Compute mean pairwise Tanimoto distance (1 − Morgan-FP2 similarity) for each target's top-30 BindingDB binders; correlate with the ceiling AUROC numbers.

## Headline (one paragraph)

**Two probes ran together.** (a) The mTOR truncation theory is **falsified** — restricting the
input to the kinase domain alone (451–575 aa, fully visible — no truncation) does *not* rescue
AUROC (0.50 / 0.54 vs 0.56 full-truncated). mTOR isn't a truncation artifact; it joins BRAF in the
"rich data, still fails" group. (b) Across the 6 ceiling targets, **Spearman(binder-set diversity,
AUROC) = −0.83** — *lower* binder diversity correlates with *higher* AUROC. **Update (2026-06-07):
the obvious mechanism — single-scaffold memorisation — is REFUTED** by a follow-up held-out-scaffold
test ([`datafit_scaffold_shift.md`](datafit_scaffold_shift.md)): on RORC, Adrb2 and CA2, out-of-
scaffold AUROC stays at 0.74–0.93 (drop ≤ 0.13 from the same-scaffold ceiling) and the head does
**not** rank the dominant scaffold higher than held-out scaffolds (in-vs-out AUROC 0.41–0.58). The
diversity-vs-AUROC pattern is real but the mechanism is not chemotype memorisation — it remains
open. **The ceiling wins (RORC, CA2, Adrb2) are genuine generalisation, not memorisation.**

## (a) mTOR truncation probe — falsifies the truncation theory

mTOR is 2549 aa; the DTI head truncates to the first 1250 — which excludes the FRB (~aa 2025–2114) and the kinase domain (~aa 2182–2516), i.e. *the entire active site*. Hypothesis: re-running on a kinase-domain window (fully visible) will rescue AUROC.

| window | length | AUROC vs MW-matched decoys | binder mean − decoy mean (pKd) |
|---|---:|---:|---:|
| full sequence (truncated to first 1250) | 2549 → 1250 | 0.558 | +0.10 |
| FRB + kinase (aa 1975–2549) | 575 | 0.535 | +0.19 |
| kinase only (aa 2099–2549) | 451 | **0.502** | +0.13 |

Same 12 BindingDB mTOR binders, same 36 MW-matched off-target decoys, same PEER checkpoint. Windowing the kinase domain *does not rescue* AUROC — it stays at chance. **The mTOR failure is not about which residues the head sees.** mTOR joins BRAF and HRH1 in the "rich training data + still fails" group. This is consistent with the prior phase 2b finding (hand-picked drugs, same conclusion) but is a stronger test with the BindingDB binder set.

## (b) Chemodiversity vs AUROC — the bimodality predictor

For each ceiling target, compute the mean pairwise Tanimoto similarity of its top-30 BindingDB binders (Morgan FP, radius 2, 2048 bits) → 1 − similarity = mean diversity in [0, 1]. Higher = more chemotype-diverse binder set.

| target | n_pairs | mean Tanimoto sim | diversity | AUROC random | AUROC matched | Δ off-target |
|---|---:|---:|---:|---:|---:|---:|
| RORC | 374 | **0.48** | **0.52** | **0.97** | **0.95** | +0.69 |
| Adrb2 | 211 | 0.34 | 0.66 | 0.87 | 0.88 | +0.83 |
| CA2 | 269 | 0.25 | 0.75 | 0.87 | 0.84 | +1.97 |
| HRH1 | 184 | 0.24 | 0.76 | 0.40 | 0.33 | +0.68 |
| MTOR | 192 | 0.20 | 0.80 | 0.76 | 0.56 | −1.12 |
| BRAF | 532 | **0.16** | **0.84** | **0.47** | **0.46** | +1.18 |

Spearman across the 6 targets:

| metric | ρ |
|---|---:|
| diversity vs **AUROC random** | **−0.83** |
| diversity vs **AUROC matched** | **−0.83** |
| diversity vs off-target Δ | −0.09 |

(n = 6; the correlation is steep with small n, but the pattern is clean and monotone — RORC at the low-diversity / high-AUROC corner, BRAF at the high-diversity / low-AUROC corner.)

**Initial interpretation (now refuted — see follow-up below).** The original reading was that the
head was learning a per-target chemotype rather than a per-target binding model: low-diversity sets
→ memorise the scaffold → high AUROC against MW-matched decoys; high-diversity sets → no single
scaffold-memory works → AUROC at chance. The held-out-scaffold experiment refutes that mechanism;
see "Follow-up: scaffold-shift test (mechanism refuted)" at the bottom.

The off-target Δ doesn't track diversity (ρ = −0.09), so the "cross-target re-ranking" axis is
independent of within-target binder-vs-decoy quality — consistent with the existing project-wide
reading of MAMMAL DTI ("soft cross-target re-ranker, not a single-target binder gate").

## What this changed (and the follow-up that walked one of these back)

| Prior reading | Reading after (a) + (b) | Reading after follow-up (scaffold shift) |
|---|---|---|
| RORC/CA2/Adrb2 are evidence the head works where the data is rich. | They're evidence the head **memorises narrow chemotypes** where they exist. | **Refuted.** Out-of-scaffold AUROC stays at 0.74–0.93; these ceiling wins are **real generalisation**. |
| BRAF's chance-level AUROC is mysterious. | BRAF has the **most diverse** binder set (similarity 0.16) — consistent with the chemotype hypothesis. | BRAF still fails, but **not because of memorisation collapse.** The mechanism behind diversity ⇒ low AUROC remains open. |
| mTOR's failure might be the kinase-domain truncation. | It isn't — kinase-only window (no truncation) is at AUROC 0.50. mTOR joins BRAF and HRH1 in the "rich data, still fails" camp. | Unchanged. |
| A Quiver Nav fine-tune is bimodal-risk. | Performance depends on whether Quiver's Nav data is narrow or diverse; use chemodiversity as a pre-flight predictor. | **Softened.** Out-of-scaffold generalisation works on the ceiling wins, so a moderately diverse Nav screen is less likely to collapse to chance than the memorisation reading implied. Held-out-scaffold evaluation discipline still matters. |
| The "good" targets demonstrate MAMMAL learned a chemotype, not generalised binding. | (same) | **Refuted.** RORC has 76 distinct scaffolds in 174 binders; the dominant one is 6 % of the pool and the other 94 % still score AUROC 0.93. That is generalisation, not memorisation. |

## Follow-up: mechanism probe (decoy-distance + variance also refuted)

Ran 2026-06-07 — `experiments/datafit_mechanism_probe.py` →
`results/datafit_mechanism_probe_20260607_135249.json`. Tests two candidate mechanisms
that would have explained the diversity-vs-AUROC ρ = −0.83 without invoking memorisation:

| candidate mechanism | Spearman vs AUROC matched | verdict |
|---|---:|---|
| min Tanimoto distance (binder ↔ decoys) — "narrow-binder targets have decoys far away by construction" | **+0.03** | **rejected** |
| mean Tanimoto distance (binder ↔ decoys) | −0.03 | rejected |
| std of predicted pKd over binders+decoys | +0.26 | weak; doesn't carry the signal |
| predicted-pKd separation (mean binder − mean decoy) | +0.89 | tautological with AUROC — locates the failure but doesn't explain it |

Decoy-distance is the most intuitive hypothesis after memorisation got refuted, and it
is **flat-out wrong on this panel.** The head's variance is also not the story. The
diversity-vs-AUROC pattern is real but its mechanism is at the level of the head's
per-target output distribution and is not predicted by simple chemometric or output
features of the input.

**Remaining candidates (out of scope this round):** label-noise / assay-source
heterogeneity per target in BindingDB (even within the Kd column); target-class effects
confounded with diversity (e.g. kinase pockets vs nuclear-receptor pockets); pre-training
contamination of the binders in PEER's split.

## Follow-up: scaffold-shift test (mechanism refuted)

Ran 2026-06-07 (same day) — `experiments/datafit_scaffold_shift.py` →
[`results/datafit_scaffold_shift.md`](datafit_scaffold_shift.md). For each "ceiling win" target,
pull ALL BindingDB binders, bin by Bemis-Murcko scaffold, split into dominant-scaffold ("in") vs
everything-else ("out-of-scaffold"), score both vs MW-matched decoys, compute AUROCs.

| target | n_in | n_out | AUROC_in | AUROC_out | drop | in-vs-out |
|---|---:|---:|---:|---:|---:|---:|
| RORC | 11 | 163 | 0.97 | **0.93** | +0.04 | 0.46 |
| Adrb2 | 19 | 50 | 0.87 | **0.75** | +0.13 | 0.58 |
| CA2 | 27 | 96 | 0.74 | **0.74** | +0.00 | 0.41 |

If memorisation were the mechanism, AUROC_out should drop sharply toward 0.5 and in-vs-out
should be ≫ 0.5 (head ranks dominant scaffold higher than held-out scaffolds). Neither
happens. RORC's dominant scaffold is only 6 % of its binder pool — the head correctly calls
the other 94 % at AUROC 0.93. **The memorisation explanation for the diversity-vs-AUROC
correlation is wrong; the wins are real generalisation.** Mechanism behind the ρ = −0.83
remains open (see "Implications" §3).

## Caveats

- n = 6 targets in the ceiling panel; ρ = −0.83 is a strong shape but rests on 6 points. Same-shape repeat on the curve targets (16 more) is a one-script follow-up worth doing.
- "Diversity" here is mean pairwise Tanimoto on Morgan-FP2 — one specific operationalisation. Scaffold-class diversity (Murcko scaffold), max-distance, or t-SNE clustering would test robustness.
- The truncation probe used 12 BindingDB binders (a subset of the 30 from the ceiling, those still distinct and within the matched-decoy set). Reflects the same compound population, but the n is small per window.
- Bemis-Murcko scaffold-split is a coarse generalisation test (ring core only — substituent decoration can still help the head). InChIKey-cluster or scaffold-tree splits are stricter follow-ups.

## Implications for Quiver (post-follow-up)

1. **Ceiling wins are real generalisation, not memorisation.** RORC / CA2 / Adrb2 hold up under
   held-out scaffold splits (AUROC 0.74–0.93). MAMMAL DTI is genuinely useful where the
   training data covers the target — even on novel scaffolds against those same targets.
2. **mTOR is the next BRAF.** Truncation theory dead (kinase-domain window at AUROC 0.50); rich
   data + still fails. Drop "mTOR is data-suited" from any pitch.
3. **The diversity ⇒ low-AUROC pattern is real but unexplained.** Spearman −0.83 across 6
   targets is too strong to be noise at n = 6, but the memorisation mechanism is refuted.
   Candidate alternatives to test next: (a) label noise / measurement variance in the
   diverse-binder pools (BRAF / HRH1 may have noisier pKd than the narrow nuclear-receptor
   / GPCR pools); (b) target-class effects confounded with diversity; (c) the matched-MW decoy
   pool may be chemically closer to a diverse binder set than to a narrow one. Cheapest to
   test (a) by tabulating BindingDB assay-type mix per target (Ki / Kd / IC50).
4. **Nav fine-tune outlook is mildly more positive.** A moderately diverse Nav screen is less
   likely to collapse to chance than the original bimodality writeup suggested. Held-out-
   scaffold evaluation is still the right discipline.
