# Adversarial audit of Phase 0–5 findings

**Date:** 2026-06-01. **Scope:** read every `results/*.md` writeup and the `results/*.json` it
cites, plus `docs/FINDINGS.md`, `HANDOFF.md`, `CLAUDE.md`, `docs/mammal_checkpoint_survey.md`. Checked
each load-bearing claim for (a) JSON support, (b) faithful interpretation, (c) small-n overconfidence,
(d) leakage/confounds, (e) internal contradictions. **No model was run** — this is a paper-trail audit.

**Headline:** The data-to-writeup fidelity is mostly good and the project is unusually honest about
its own failure modes (it self-caught the scalar-head false negative and the ClinTox input-form
artifact, both real). **But several numbers that have become load-bearing across HANDOFF/FINDINGS/
CLAUDE rest on tiny n with no significance reported, and two "canonical" Phase-5 results overstate
what the underlying score distributions actually show.** The single most over-leveraged number is the
**DTI PEER Spearman 0.43** (n=10, p=0.21, 95% CI [−0.28, 0.80] — not distinguishable from zero).

---

## Claim-by-claim verdict table

| # | Claim (as stated in docs) | Source .md | Backing JSON | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | **DTI PEER Spearman 0.43** on 10 known pairs; "soft cross-target re-ranker works", clears the >0.4 bar → PASS | `phase1_calibration.md`, propagated to FINDINGS/HANDOFF/CLAUDE/report card | `phase1_peer_comparison_20260528_194239.json` (`spearman 0.4303`, `pearson 0.3104`, n=10) | **OVERSTATED** | Number is in the JSON. But recomputed **p=0.214, not significant**; bootstrap **95% CI [−0.28, 0.80]**. Pearson 0.31 (p=0.38). The writeup *does* hedge ("n=10 small, Pearson only 0.31") but never says the correlation is statistically indistinguishable from zero, and downstream docs drop the hedge and cite "0.43" as established. A single point estimate from 10 pairs is being treated as a capability. |
| 2 | **DTI cold-split Spearman −0.03** (the "wrong checkpoint") | `phase1_calibration.md` | `phase1_correlation_20260528_191455.json` (`spearman −0.0303`) | **SUPPORTED** | Matches. The −0.03→0.43 "checkpoint choice matters" story is real *as a point estimate*; see #1 for the significance caveat on the 0.43 end. |
| 3 | **In-distribution control Spearman 0.61** proves pipeline works in-domain | `phase1_calibration.md` | `phase1_indistribution_20260528_192110.json` (`spearman 0.6135`, `pearson 0.767`, n=20) | **SUPPORTED** | Matches; n=20; reasonable as a diagnostic. |
| 4 | **Reproduced DTI NRMSE ~0.88 vs paper 0.906**; "SOTA is only ~9% better than the mean" | `phase1_calibration.md`, `benchmark_verification.md` | **None** — `phase1_nrmse_verify.py` "prints to stdout; numbers recorded in `phase1_calibration.md`" (per README) | **NEEDS-RERUN (unbacked by JSON)** | The NRMSE table (0.859 cold / 0.880 PEER / 0.906 paper / mean=1.0) exists **only in the .md narrative** — there is no `phase1_nrmse_*.json`. Not necessarily wrong, but it is the one quantitative benchmark claim with **zero raw artifact**, and it underpins the recurring "state-of-the-art on shit" framing. Re-run and save JSON. |
| 5 | **suzetrigine→Nav1.8 FAILS** (true binder below random small molecules) | `phase1_calibration.md`, `phase2b` | `phase1_calibration_20260528_191324.json` (pred 6.14, max neg 6.42, margin −0.28, FAIL); PEER value 7.00 in `phase1_peer_comparison` | **SUPPORTED** | Matches both checkpoints. The "post-Oct-2024 cutoff + truncation" explanation is *charitable to the model*; the writeup also lists the real cause (#3: over-scores generic small molecules). No overstatement — if anything understates the failure by offering excuses. |
| 6 | **Nav1.8 +0.00 / mTOR +0.10 binder-vs-decoy separation; truncation ruled out** (windowing doesn't help) | `phase2b_quiver_targets.md` | `phase2b_quiver_targets_20260528_202929.json` (nav full sep 0.004; mtor full 0.105; windows −0.05/−0.08/+0.11) | **SUPPORTED** but **small-n** | Numbers match. Caveat the writeup mostly states: **only 7 binders vs 4 decoys per target**. "Separation = mean_binder − mean_decoy" on n=4 decoys is extremely noisy; the qualitative conclusion (no usable single-target signal) is safe, but the specific separations (+0.00/+0.10) should not be over-read. |
| 7 | **BBBP held-out AUROC 0.968 (paper 0.957)** | `phase1_calibration.md`, `benchmark_verification.md` | `phase1b_molnet_bbbp_20260528_195541.json` (`auroc 0.9682`, n=204, pos 0.52) | **SUPPORTED** | Matches; balanced fold n=204. Solid. |
| 8 | **ClinTox-tox AUROC ~1.0 (paper 0.986)** | `phase1_calibration.md`, `benchmark_verification.md` | `phase1b_molnet_tox_20260528_195652.json` (`auroc 1.0`, n=148, **pos rate 0.07 → ~10 positives**) | **SUPPORTED, correctly flagged low-confidence** | Matches; the writeup itself rates this "low confidence — ~10 minority examples, possible split-overlap leakage." Honest. |
| 9 | **ClinTox-FDA AUROC ~1.0; trivial (94% positive, ~9 negatives)** | report card, README | `phase1b_molnet_fda_20260528_205148.json` (`auroc 1.0`, n=148); `phase4_molnet_audit` (pos_rate 0.939) | **SUPPORTED** | 148×(1−0.939)≈**9 negatives** — confirms the "tiny minority fold" caveat. "Trivial/not meaningful" verdict is correct. |
| 10 | **TCR-epitope AUROC 0.931 (paper 0.879)** | `benchmark_verification.md` | `phase1c_tcr_epitope_20260528_205314.json` (`auroc 0.9312`, n=400, balanced) | **SUPPORTED** | Matches; balanced n=400. The best-supported benchmark reproduction. |
| 11 | **Morgan fingerprints beat MAMMAL embeddings 0.96 vs 0.72** (same-class NN); use fingerprints for expansion | `phase2a_expansion_check.md` | `phase2a_similarity_20260528_200455.json` (`mammal 0.72`, `tanimoto 0.96`, n=25/5 classes) | **SUPPORTED** | Matches (0.72=18/25, 0.96=24/25). n=25 is small (writeup says so) but the gap (6 NN) is large enough that the direction is safe. |
| 12 | **Protein embeddings recover family, NN 0.92** (CRISPR-N / Sapphire) | `phase2_quiver_utility.md` | `phase2c_protein_embedding_20260528_211135.json` (`nn 0.92`, intra−inter +0.457, n=25/5) | **SUPPORTED** (sensible), but see #13 | 0.92=23/25; matches. Writeup correctly says "did NOT benchmark vs ESM" here. |
| 13 | **MAMMAL beats ESM-2 8M, 0.92 vs 0.88 NN recall; "sharper structural discrimination"** | `phase5_summary.md` | `phase5_esm_comparison_20260529_113901.json` (mammal nn 0.92 / gap 0.463; esm2-8M nn 0.88 / gap 0.093) | **OVERSTATED** | The NN-recall difference is **exactly 1 protein out of 25** (23 vs 22) — within sampling noise, no significance possible. The intra/inter **gap** difference (0.463 vs 0.093) is the real, defensible signal; the **"beats on NN recall"** clause is noise dressed as a win. Writeup correctly caveats the 8M-size choice but not the 1-protein NN artifact. ESM-2 8M is also a deliberately tiny baseline (650M/3B would likely win — writeup admits this). |
| 14 | **De-risking funnel: 2039→150→149 BBB+→43 non-toxic; BBBP 99% precision; ~0.16 s/cpd** | `phase2_quiver_utility.md` | `phase2a_pipeline_20260528_211024.json` (149 bbb_pass, precision 0.993, 43 final, 47.9 s) | **SUPPORTED**, but precision is a soft confound | Matches. Writeup itself flags the real issue: expanding from a CNS seed (diazepam) **pre-enriches for penetrant compounds** (`expanded_true_penetrant_frac 0.987`), so 99% precision is not a hard test. Honest. |
| 15 | **WDR91 generative AUROC 0.63, top-5% enrichment 5.25×** ("the triage capability DTI lacked"; existence proof for Q14) | `phase3_wdr91_finetune.md`, FINDINGS, HANDOFF, CLAUDE | `phase3_wdr91_final_20260528_223849.json` (`auroc 0.6313`, EF5 5.25 [7/26], EF10 2.95, n=27 vs 500) | **OVERSTATED (small-n existence proof)** | Numbers match. Recomputed **95% CI [0.52, 0.75]** — barely excludes 0.5. Writeup hedges ("wide CI ±0.09, N=27"). The concern is **load-bearing weight**: this single n=27 result is the entire empirical basis for "fine-tuning works / Q14 leans YES" across four top-level docs. EF 5.25× rests on **7 of the top 26** of 527 molecules. Treat as suggestive, not established. |
| 16 | **WDR91 readout choice** — P(`<1>`)@pos1=0.63 is "the legitimate readout, validated on BBBP=0.996" | `phase3_wdr91_finetune.md` | `phase3_wdr91_generative_20260528_223304.json` (sweep: `<1>@1=0.631`, `<1>@0=0.777`, **`<0>@0=0.805`** = JSON "best", several @0 readouts > 0.63) | **SUPPORTED (defensible, not a cherry-pick)** | Initially looked like a multiple-comparisons cherry-pick (10 readouts, n=27). On inspection the team reported the **lower** principled number (0.631) dictated by the BBBP validation, **not** the sweep maximum (0.805). That is conservative and correct. Flagging only so a future reader doesn't mistake the sweep maximum for performance. |
| 17 | **WDR91 SPR real-data AUROC 0.816, EF5 4.57×** — "should be taken as the canonical performance; the head genuinely separates confirmed non-binders from binders" | `phase5_summary.md` | `phase5_wdr91_spr_20260529_113233.json` (auroc 0.8159, n=38 binders/201 non; mean_score binders 0.015 vs non 0.003) | **OVERSTATED** | AUROC and CI ([0.73,0.90]) are fine **as a ranking statistic**. But the score distribution is **degenerate**: 92% of all 239 scores are <0.001; binder **median = 0.0003**, max = 0.36; only **2/38 binders score >0.1**, only 5/38 >0.01. Meanwhile **2 non-binders also exceed 0.1** (0.319, 0.175 — the top non-binder outranks all but one true binder). So the head assigns ~0 binder-probability to nearly all true binders; the 0.816 reflects faint rank structure in near-zero noise, **not** a model that "fires" on binders. "Canonical performance" / "genuinely separates" oversells the operational reality (which is: useless as a per-compound probability; weak top-of-list enrichment only). The writeup's own "top false positive scored 0.319, hard 0/1 outputs" line hints at this but the headline buries it. |
| 18 | **PGK2 head separates its hits from PGK1 homolog ligands AUROC 0.97** (genuine target specificity) | `phase3_wdr91_finetune.md`, FINDINGS, report card | `phase3_realdata_specificity_20260529_005231.json` (`pgk2_head P>PGK1 0.9734`) | **SUPPORTED, correctly caveated as in-distribution** | Matches; CI tight [0.96,0.98]. **But it is in-distribution positives (PGK2 hits = the head's own training data) vs OOD negatives** — the writeup states this plainly ("not proven recall on novel PGK2 scaffolds"). FINDINGS/HANDOFF lean on "0.97 homolog selectivity" as an existence proof while preserving the caveat — acceptable, but the 0.97 should never be quoted without "in-distribution." |
| 19 | **PGK2 in-distribution hits-vs-decoys 0.98 but Spearman vs DEL count ≈0** (recognizes chemotype, no graded ranking) | `phase3_wdr91_finetune.md` | `phase3_pgk2_indist_20260528_232751.json` (A_auroc 0.984, B_spearman −0.064, highcount-vs-low 0.41) | **SUPPORTED** | Matches; honestly framed as train-recall/memorization, not generalization. This is the project's sharpest, most honest result. |
| 20 | **WDR91 head is weak/non-specific: PGK2 mols outscore its own actives, AUROC 0.18** | `phase3_wdr91_finetune.md`, FINDINGS | `phase3_realdata_specificity_20260529_005231.json` (`wdr91_head W>P 0.1816`) | **SUPPORTED** | Matches. This directly **contradicts the "WDR91 works (0.63)" existence-proof framing** when read together (see Internal Contradictions). The report card does reconcile them (calls WDR91 "weak; chemotype-recall only"). |
| 21 | **ClinTox: 0% sensitivity to external clinically-toxic drugs; 0% false-alarm on safe; "memorization"** | `phase4_finetuned_report_card.md`, `phase4_bbbp_literature.md`(sic→clintox), FINDINGS | `phase4_clintox_literature_20260529_094957.json` (`toxic_sensitivity_EXTERNAL 0.0`, n_toxic_external 7; `safe_falsealarm 0.0`); `phase4_molnet_audit` (tox TNR 1.0, nontoxic_n 200) | **SUPPORTED** | Matches. 7 external toxics all missed (cerivastatin, terfenadine, thalidomide, cisapride, etc., all p_toxic ~1e-6). Pemoline (p=0.997) is caught but it's an *in-ClinTox* compound. "Don't use as a tox gate" is well-supported. n_external=7 is small but the effect (literally 0/7) plus the mechanism (memorization) is convincing. |
| 22 | **"ClinTox over-predicts" was an input-form artifact** (raw isomeric/charged SMILES) | report card, FINDINGS, `phase2b` | `phase2b` shows P(toxic)=1.0 on raw SMILES; `phase4_clintox_literature` shows ~0 on clean SMILES | **SUPPORTED** (self-caught error) | The reversal (over-predicts → under-detects) is real and documented. Genuine self-correction. |
| 23 | **BBBP literature: CNS-active 11/11 correct; false-positive bias (cetirizine/atenolol/domperidone passed); TNR 0.70** | `phase4_bbbp_literature.md`, report card | `phase4_bbbp_literature_20260529_014522.json`; `phase4_molnet_audit` (BBBP TNR 0.701) | **SUPPORTED with a leakage caveat the headline omits** | TNR 0.70 matches the molnet audit. "11/11" is literally true, **but 9 of the 11 positives were `in_train`/valid** (only morphine + metoclopramide genuinely held-out). And the 3 "smoking-gun" false positives: **cetirizine and atenolol were also `in_train`** (model saw them labeled 0 and still calls them penetrant — which *strengthens* the bias claim) while only domperidone is a held-out test-fold miss. The per-direction conclusion (soft positive, not rule-out gate) is sound; the **"11/11"** framing rests largely on memorized compounds and shouldn't headline without the fold breakdown (the table does show folds). |
| 24 | **BBBP robust to SMILES re-ordering (0/6 flip), sensitive to protonation/salt** | `phase4_bbbp_literature.md`, report card | `phase4_smiles_robustness_20260529_095537.json` (BBBP 0/6 flip; ClinTox 1/6 flip) | **SUPPORTED** | Matches. n=6 molecules × 8 variants — small but adequate for a robustness probe. |
| 25 | **Calibration: molnet heads hard 0/1 (BBBP 95%, ClinTox 100%, FDA 62%); protein heads calibrated (TCR 28%, sol 17%)** | report card, FINDINGS | `phase4_molnet_audit` (BBBP sat 0.951, tox 1.0, fda 0.622); `phase4_tcr_solubility_calib` (TCR 0.28, sol 0.166) | **SUPPORTED** | All saturation fractions match exactly. Clean, well-supported cross-cutting finding. |
| 26 | **Solubility acc 0.734 / AUROC 0.829 (~at DeepSol baseline 0.77)** | `benchmark_verification.md`, report card | `phase3_solubility_20260528_232430.json` (acc 0.7339, auroc 0.829, n=1992, pos 0.50) | **SUPPORTED** | Matches; n=1992 balanced. The one head with a large, clean test set. |
| 27 | **hERG heuristic rule: TPR=1.0, TNR=1.0 "perfect separation"; recommended as ClinTox replacement** | `phase5_summary.md` | `phase5_herg_test_20260529_113904.json` (liberal TPR 1.0 TNR 1.0 on **4 toxic + 6 safe**) | **OVERSTATED / NEEDS-RERUN** | "Perfect" is on **n=10**, and the rule (basic-N + logP>1.5 + aromatic) was evidently **tuned on this same 10-compound set** (the "liberal" variant exists precisely so haloperidol passes — `strict` misses it). A post-hoc-fit rule reporting 100%/100% on its fit set, then recommended for Quiver's funnel, is the textbook overfit-on-tiny-n trap. Also **haloperidol is labeled `herg_toxic:1` here but `toxic:0` (safe) in `phase5_tox_alternatives`** — inconsistent labeling within Phase 5 (see Contradictions). |
| 28 | **CRISPR-N panel: NN recall 0.75; per-family GPCR 100%/kinase 100%/ion-channel 88%/NR 33%/E3 25%; RARA mislabeled** | `phase5_summary.md` | `phase5_crispr_panel_20260529_113901.json` (nn 0.75, knn3 0.825, gap 0.374) | **SUPPORTED** (per-family verified from matrix) | Recomputed per-family NN from the similarity matrix: kinase 12/12, gpcr 8/8, ion 7/8, NR 2/6, e3 1/4, overall 0.75 — **all match**. The RARA-mislabeled-as-e3 narrative is **confirmed** (RARA is in `e3_ligase` in the JSON). Bonus uncaught nit: **TP53 is labeled `nuclear_receptor`** (it's a tumor-suppressor TF, not a classic NR) — doesn't change conclusions. Honest writeup. |
| 29 | **"Every paper benchmark with a public checkpoint reproduces (4/11)"** | `benchmark_verification.md`, FINDINGS | DTI(#4, md-only), BBBP(#7), TCR(#10), ClinTox(#8) | **MOSTLY SUPPORTED** | 3 of the 4 have JSON (BBBP, TCR, ClinTox); **DTI NRMSE has no JSON (#4)**. So "4/11 reproduce" is really "3 reproduce with raw artifacts + 1 reproduced in narrative only." Minor, but the cleanest claim of the doc has one leg without a receipt. |
| 30 | **Per-target heads ship a redundant 4.6 GB `last.ckpt` "verified equal to safetensors"** | HANDOFF, CLAUDE, survey | `phase3_wdr91_ckpt_20260528_215527.json` (head_allclose_base true, encoder_relL2 0.0235) | **PARTIALLY SUPPORTED** | The ckpt JSON proves the **scalar head == base** (the vestigial-head finding, solid). It does **not** show the `.ckpt`-vs-`.safetensors` byte-equality that HANDOFF/CLAUDE assert ("verified equal — safe to prune"). That equality claim has no artifact; before anyone deletes a 4.6 GB file on its strength, re-verify. |

---

## Internal contradictions found

1. **WDR91 "works (0.63 / existence proof)" vs WDR91 "weak/non-specific (0.18, inverted)."** Claim #15
   and claim #20 are about the *same head*. Read in isolation, FINDINGS/HANDOFF/CLAUDE's "fine-tuning
   works, Q14 leans YES" leans on the 0.63; the real-data specificity test shows the WDR91 head
   barely fires on its own actives and is beaten by PGK2 molecules (0.18). The report card *does*
   reconcile this (WDR91 = "weak; chemotype-recall only"; the *PGK2* head is the better existence
   proof) — but the top-level synthesis docs still front the WDR91 0.63/5.25× as the headline Q14
   evidence. **The honest existence proof is PGK2's in-distribution 0.97, not WDR91's fragile 0.63.**
   The summary docs should lead with that distinction.

2. **WDR91 "canonical performance" is quoted as two different numbers.** `phase3` calls the OOD
   0.63/5.25× "the honest generalization estimate" and "canonical"; `phase5` then calls the SPR
   0.816/4.57× "the canonical performance." Both can't be canonical. They are different tests
   (decoys vs SPR-zeros) and the EF actually *drops* (5.25×→4.57×) on the cleaner negatives, while
   AUROC rises (0.63→0.816) — which by itself signals the AUROC is sensitive to the negative set, i.e.
   not an intrinsic property of the head. Pick one framing and state both numbers with their negative-set.

3. **Haloperidol toxicity label flips within Phase 5.** `phase5_herg_test` labels haloperidol
   `herg_toxic: 1`; `phase5_tox_alternatives` labels it `toxic: 0` (and uses it as a safe CNS
   control elsewhere). Haloperidol does carry a real QT/hERG liability, so `herg_toxic:1` is
   arguably correct — but the inconsistent labeling across two files in the same phase means the
   hERG-rule TPR/TNR depends on an unstated labeling choice (and the rule was fit to it).

4. **README index is stale / Phase 5 unindexed.** `results/README.md` ("All from 2026-05-28") and
   HANDOFF's phase list **do not mention Phase 5 at all**, yet Phase 5 produced the now-most-cited
   numbers (SPR 0.816, ESM-2 0.92-vs-0.88, hERG rule). `docs/FINDINGS.md` is dated "as of 2026-05-28"
   and predates Phase 5 — so the project's "authoritative synthesis" doc is one phase behind the
   "canonical" results. A reader trusting FINDINGS/README would miss Phase 5 entirely.

---

## Claims rated OVERSTATED / UNSUPPORTED / NEEDS-RERUN (the actionable list)

| Claim | Rating | Why |
|---|---|---|
| **DTI PEER Spearman 0.43 "works as a re-ranker / PASS"** (#1) | **OVERSTATED** | n=10, p=0.21, 95% CI [−0.28, 0.80]. Not significantly different from 0. Most over-leveraged number in the repo. |
| **WDR91 SPR 0.816 "canonical / genuinely separates binders"** (#17) | **OVERSTATED** | 92% of scores <0.001; binders' median P≈0.0003; top non-binder outranks all but one binder. AUROC ≠ the head firing on binders. |
| **MAMMAL beats ESM-2 8M on NN recall (0.92 vs 0.88)** (#13) | **OVERSTATED** | 1-protein-of-25 difference, pure noise. (Gap metric 0.463 vs 0.093 is the real, keep-able signal.) |
| **WDR91 generative 0.63 / 5.25× as the Q14 existence proof** (#15) | **OVERSTATED (small-n, over-leveraged)** | CI [0.52, 0.75]; EF rests on 7/26 of n=527; carries four top-level docs. PGK2 0.97 (in-dist) is the stronger proof and should lead. |
| **hERG heuristic "perfect TPR/TNR=1.0," recommended for the funnel** (#27) | **OVERSTATED / NEEDS-RERUN** | n=10, rule visibly fit to that set (liberal vs strict). Validate on a held-out cardiotox set before recommending. |
| **DTI NRMSE 0.88 vs paper 0.906** (#4) | **NEEDS-RERUN (no JSON)** | Only quantitative benchmark claim with no raw artifact; underpins the "SOTA-but-weak" framing. Re-run, save JSON. |
| **`.ckpt` == `.safetensors` "verified equal — safe to prune 4.6 GB"** (#30) | **UNSUPPORTED (no artifact)** | The ckpt JSON proves head==base, not file equality. Re-verify before deleting. |
| **"11/11 CNS-active correct"** as a BBBP headline (#23) | **MILDLY OVERSTATED (leakage)** | 9/11 positives in-train; only 2 genuinely held-out. Conclusion still holds; headline should foreground folds. |

**Everything else audited (claims #2,3,5,6,7,8,9,10,11,12,14,16,18,19,20,21,22,24,25,26,28) is SUPPORTED**
— the numbers are in the JSON and the interpretations are faithful (several are exemplary about their
own caveats, especially the PGK2 in-distribution recall framing and the ClinTox memorization finding).

---

## Top claims to re-run on the model in Phase 2 (re-verification priority)

1. **[HIGHEST] DTI PEER Spearman on a properly powered known-pairs set.** The entire "soft
   cross-target re-ranker" capability (meeting use case #1, cited in every doc) rests on **0.43 from
   n=10, which is not statistically significant (p=0.21, CI crosses 0)**. Re-run on **≥50–100 diverse
   known pairs** (ChEMBL pChEMBL, PEER-held-out classes) and report Spearman **with a CI / p-value**.
   If it lands ~0.4 with a CI that clears 0, the re-ranker claim is real; if it collapses, a load-bearing
   capability across HANDOFF/FINDINGS/CLAUDE/report-card evaporates. **File: `results/phase1_peer_comparison_20260528_194239.json` → rerun `experiments/phase1_peer_comparison.py` with an expanded pair list.**

2. **WDR91/PGK2 enrichment on a genuinely held-out scaffold split with real negatives**, reporting
   **score distributions + EF/BEDROC**, not just AUROC. The two "canonical" numbers (0.63, 0.816)
   disagree, are n=27/38, and the SPR 0.816 sits on a near-zero score mass. This is the Q14 decision —
   it deserves a power-adequate, distribution-aware rerun. **Files: `phase3_wdr91_final_*.json`,
   `phase5_wdr91_spr_*.json`.**

3. **DTI NRMSE reproduction saved to JSON** (currently md-narrative only). Cheap, closes the one
   benchmark claim with no receipt. **Script: `experiments/phase1_nrmse_verify.py` (add JSON dump).**

4. **MAMMAL vs ESM-2 at 650M/3B** on a larger protein set (the writeup itself flags this). The 8M
   comparison is a strawman and the 0.92-vs-0.88 win is noise; the Sapphire decision needs the real baseline. **File: `phase5_esm_comparison_*.json`.**

### Single highest-priority claim to re-verify empirically
**DTI PEER Spearman 0.43 (n=10).** It is the most-cited, most-load-bearing number in the project
(it is the "DTI re-ranker works" capability in HANDOFF §0/§5, FINDINGS, CLAUDE.md, and the Phase-4
report card), and it is the **weakest-powered** (p=0.214, 95% CI [−0.28, 0.80] — statistically
indistinguishable from zero). **Backing file: `/Users/rohanaryagondi/Library/CloudStorage/OneDrive-YaleUniversity/Career/Quiver/Mammal/results/phase1_peer_comparison_20260528_194239.json`** (producing script `experiments/phase1_peer_comparison.py`).
