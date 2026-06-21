# Results — index

Experiment outputs. The `.md` files are the authoritative writeups; the `.json` files are the raw
per-run outputs they summarize. Spans the MAMMAL evaluation (May–June 2026), the CNS model campaign,
and the Boltz work. **Do not delete — these are experiment data.**

**Where to start:** the synthesis lives outside this folder — `../docs/models_tracks_scorecard.md`
(the 9-track best-model scorecard) and `../RohanOnly/` (presentation briefs). This README indexes the
raw per-model receipts.

## Navigate by topic

*Grouped map of every writeup here. The phase-by-phase detail (MAMMAL era) continues below.*

- **Boltz (structure / screen / design):** `boltz_tier1_characterization`, `boltz_tier2_characterization`,
  `boltz_tier3_characterization`, `boltz_cns_characterization` — see `../RohanOnly/boltz_work_summary_2026-06-18.md`
  for the one-page synthesis and the overnight/partner deep-dives.
- **Track 1 · protein-family clustering:** `esm_scale_ladder_track1`, `compare_esm2_650m`, `compare_esmc_600m`,
  `protrek_characterization`, `proton_characterization`.
- **Track 2 · DTI / binder triage:** `compare_dti_models`, `compare_conplex_nav_offtarget`, `balm_characterization`,
  `balm_crossmodal`, `cns_dti_characterization`, `dti_nav_characterization`, `dti_generalization`,
  `ligunity_characterization`, `ionchannel_finetune_characterization`, `cns_pertarget_finetune_characterization`,
  `cns_new_models_characterization`, `cns_rejected_dti_characterization`.
- **Track 3/8 · structure-based binding & selectivity:** `boltz_*`, `atomica_nav18_characterization`,
  `aev_plig_characterization`, `drugclip_crossmodal`, `tsc2_deconv_characterization`,
  `tsc2_deconv_supervised_characterization`.
- **Track 4/5 · BBB & toxicity (de-risking):** `maplight_b3db_characterization`, `chemeleon_maplight_characterization`,
  `compare_admet_ai`, `comprehensive_admet_char`, `derisking_characterization`, `derisking_local_characterization`,
  `cardiogenai_characterization`, `ctoxpred2_characterization`, `bbbp_characterization`, `pubchem_qhts_characterization`,
  `phase4_bbbp_literature`.
- **Track 6 · KG / hypothesis generation:** `ultra_kg_characterization`, `ultra_neurokg_characterization`,
  `proton_characterization`.
- **Track 7 · generative:** `phase6_generation`, `phase7_finetune_probe`, Boltz de-novo (in `boltz_tier2`).
- **Track 9 · variant effect:** `variant_finetune_characterization`, `mission_characterization`,
  `mission_playwright_nav18`.
- **Where MAMMAL is data-suited (data-fit):** `datafit_summary`, `datafit_ceiling`, `datafit_curve`,
  `datafit_bimodality`, `datafit_scaffold_shift`, `dti_train_data_distribution`, `trunc_test_characterization`.
- **MAMMAL fine-tuning & per-target heads:** `aws_finetune_pilot`, `phase3_wdr91_finetune`,
  `phase4_finetuned_report_card`, `phase6_pgk2_fulleval`, `phase6_wdr91_spr_reverify`,
  `cns_roundout_characterization`, `adambind_characterization`.
- **MAMMAL off-the-shelf evaluation (phases 1–6):** `phase1_calibration`, `phase2_quiver_utility`,
  `phase2a_expansion_check`, `phase2b_quiver_targets`, `phase5_summary`, `phase6_crossmodal_alignment`,
  `phase6_esm650_comparison`, `benchmark_verification`, `offtarget_ube3a`.

## Writeups (authoritative findings)

| File | What it covers |
|---|---|
| [`phase1_calibration.md`](phase1_calibration.md) | Phase 1 bottom line. DTI: use the **PEER** checkpoint (Spearman 0.43 on our 10 pairs) not the cold-split one (−0.03); reproduces paper NRMSE ~0.88 but "SOTA" is only ~9% better than the mean. Named test suzetrigine→Nav1.8 **FAILS** (post-cutoff drug + truncation). De-risking heads work at SOTA off-the-shelf: BBBP AUROC 0.968, ClinTox-tox ~1.0. |
| [`phase2a_expansion_check.md`](phase2a_expansion_check.md) | Phase 2a hit-expansion step. Morgan/Tanimoto fingerprints beat MAMMAL embeddings for SMILES-similarity NN (0.96 vs 0.72 same-class). Use fingerprints for expansion; MAMMAL's edge is the de-risking property heads, not similarity search. |
| [`phase2b_quiver_targets.md`](phase2b_quiver_targets.md) | MAMMAL on the meeting's real targets. DTI gives **no** binder-vs-decoy separation for Nav1.8 (+0.00) or mTOR (+0.10), and the binding-domain window does NOT rescue it (truncation isn't the root cause) → TSC/mTOR ranking fails off-the-shelf. BBBP de-risking genuinely useful (rapalogs correctly non-penetrant); ClinTox over-predicts toxicity. |
| [`benchmark_verification.md`](benchmark_verification.md) | Independent check of the paper's 11-task SOTA claims. All 4 tasks with public checkpoints reproduce (DTI ~0.88, BBBP 0.968, TCR-epitope 0.931, ClinTox ~1.0); the other 7 have no public checkpoint so can't be verified off-the-shelf. Benchmarks are honest; usefulness is a separate (narrow) story. |
| [`phase2_quiver_utility.md`](phase2_quiver_utility.md) | Quiver-utility tests. (1) De-risking funnel (expand→BBBP→ClinTox): fast, BBBP deployable, ClinTox over-predicts (don't gate on it). (2) Protein embeddings recover functional family (NN 0.92) — usable for CRISPR-N clustering / Sapphire KG (benchmark vs ESM before committing). |
| [`phase3_wdr91_finetune.md`](phase3_wdr91_finetune.md) | **The per-target fine-tuning test (Q14) — fine-tuning WORKS, modestly.** IBM's `wdr91_asms`/`pgk2_del_cdd` are **generative binder classifiers** (task token `<WDR91_ASMS>` → P(active); NOT the scalar head, which is untrained/vestigial). Correct readout validated on BBBP (0.996). `wdr91_asms` ranks WDR91 actives over decoys: **top-5% enrichment 5.25×, AUROC 0.63** — modest but real, the triage capability off-the-shelf DTI lacked. (First pass used the wrong scalar readout → AUROC 0.43 "broken" — a corrected false negative.) |
| **`phase6_*.md`** (crossmodal_alignment, generation, esm650_comparison, pgk2_fulleval) | **Phase 6 comprehensive pass.** Cross-modal alignment = **NO** (the Sapphire shared-space pitch is falsified); generation = span-infiller only; ESM-2 650M does NOT beat MAMMAL (0.84 vs 0.92); PGK2 is the real per-target existence proof (homolog selectivity AUROC 0.97). Synthesized in [`../docs/COMPLETE_UNDERSTANDING.md`](../docs/COMPLETE_UNDERSTANDING.md). |
| [`aws_finetune_pilot.md`](aws_finetune_pilot.md) | **First in-house fine-tune (AWS g4dn, 2026-06-01).** We trained `base_458m` ourselves on BBBP + a PGK2 binder classifier for **~$0.80** — pipeline works (BBBP val acc 0.88, PGK2 rc0). Held-out eval **invalid** (ran on a bare instance → constant 0.5; re-run on a GPU). **Strategic:** fine-tuning can't beat IBM on a public task; the win exists only for **Quiver-specific targets** (off-the-shelf ≈ 0.5). 10 hard-won env gotchas documented. Pipeline in [`../aws/`](../aws/). |
| [`dti_train_data_distribution.md`](dti_train_data_distribution.md) | **DTI training-data composition audit (NEXT_STEPS 1c, Graham's data-gap hypothesis).** BindingDB_Kd (42,236 harmonized pairs, 1,090 UniProt targets) is **kinase-skewed (72.8% of pairs)**; Gini 0.572, top-10% of targets hold 30% of pairs. **Headline: Nav1.8 (SCN10A) is ABSENT** — no target ID, and its 1,956-aa sequence + 50-aa probe match nothing. Whole Nav/SCN family = **5 incidental, mostly-rodent pairs (0.012%)**; ion channels overall = 427 pairs (1.0%). → the Nav binding failure is **consistent with a data gap** — but see the data-fit follow-up below for the qualifier. Script `experiments/dti_data_distribution.py`; raw `dti_data_distribution_*.json` + per-target `dti_train_data_per_target.csv`. |
| [`offtarget_ube3a.md`](offtarget_ube3a.md) | **Graham's off-target sanity check (NEXT_STEPS 1a).** Score Nav drugs against UBE3A + TUBB (unrelated proteins, no truncation excuse). PEER head emits pKd 5.7–7.7 for everything — every drug × every target. Faint on-target lean (+0.5 to +1.3 pKd) is swamped by the ~2-pKd background. **The DTI head encodes essentially no target specificity off the shelf.** |
| **[`datafit_summary.md`](datafit_summary.md)** | **Where is MAMMAL actually data-suited? — synthesis of ceiling + curve** (NEXT_STEPS 1b expanded). One stop for "the answer Rohan asked for in the 6/7 session." Headline: **data volume is necessary but not sufficient**; at 100+ training pairs the head's binder-vs-decoy AUROC is **bimodal** (some targets at 0.85+, others at chance, no class/size predictor). The Nav data-gap argument stands but cannot guarantee a Quiver Nav fine-tune will land in the "good" mode. mTOR — the one Quiver target IN the top-10 of BindingDB — works on random decoys (0.76) but collapses on MW-matched (0.56) and inverts off-target (Δ −1.12). |
| [`datafit_ceiling.md`](datafit_ceiling.md) | **6-target ceiling test** (mTOR, BRAF, ADRB2, HRH1, RORC, CA2). Full rig: random AUROC + MW-matched AUROC + Spearman + 6×6 off-target matrix. 3/6 clearly work (RORC 0.97/0.95, CA2 0.87/0.84, Adrb2 0.87/0.88); BRAF (the *most*-trained target!) at chance (0.47); HRH1 below chance; mTOR random-only with inverted off-target. |
| [`datafit_curve.md`](datafit_curve.md) | **Threshold curve** — 16 targets across 4 training-pair bins. Bin-averaged AUROC: low 0.61, low-mid 0.60, **high-mid 0.77 (peak)**, high 0.60 (σ doubles in high bin). Non-monotonic; "useful" 0.7 line crossed only in 40–149-pair bin. PNG at `datafit_curve.png`. |
| **[`compare_dti_models.md`](compare_dti_models.md)** | **MAMMAL vs ConPLex vs Boltz-2 head-to-head on DTI / binder triage** (NEXT_STEPS item 2). Four pre-registered tests + paired-bootstrap CIs. **ConPLex did NOT beat MAMMAL anywhere** (correlation: MAMMAL ρ+0.43 PASS vs ConPLex ρ−0.03 FAIL; Nav1.8/mTOR triage: both at chance; Test 4 fine-tuned MAMMAL wins by design). Zero-shot DTI failure on Nav-like targets is **general, not MAMMAL-specific** — the BindingDB-trained DTI tooling space all has the same coverage holes. Boltz-2 row pending AWS retrieval. Orchestrator: `experiments/compare_all.py`. |
| **[`datafit_bimodality.md`](datafit_bimodality.md)** | **NEXT_STEPS 1d** — why does MAMMAL's DTI head work on some rich-data targets and not others? Two probes: (a) mTOR kinase-domain window (AUROC 0.50 vs 0.56 full-truncated — **truncation does NOT explain the mTOR failure; mTOR is the next BRAF**); (b) chemodiversity vs AUROC across the 6 ceiling targets — **Spearman = −0.83**. Initially interpreted as chemotype memorisation; **[scaffold-shift follow-up](datafit_scaffold_shift.md) refuted that mechanism** — out-of-scaffold AUROC stays at 0.74–0.93, the ceiling wins are real generalisation. Mechanism behind the ρ = −0.83 pattern remains open. |
| **[`datafit_scaffold_shift.md`](datafit_scaffold_shift.md)** | **Scaffold-shift falsification of memorisation hypothesis.** For RORC / Adrb2 / CA2, split binders by Bemis-Murcko scaffold and run AUROC on the held-out scaffolds. **Memorisation refuted.** RORC AUROC_out=0.93 (vs in-scaffold 0.97); Adrb2 0.75 vs 0.87; CA2 0.74 vs 0.74. Ceiling wins survive a real generalisation test — important positive update for the Nav fine-tune outlook. |
| `datafit_mechanism_probe_*.json` | Probe of two alternative mechanisms for the diversity-vs-AUROC ρ=−0.83 (decoy distance + predicted-pKd variance). Both refuted (ρ=+0.03 and +0.26). Detail folded into the [bimodality writeup](datafit_bimodality.md) — mechanism remains open. |
| **[`compare_esm2_650m.md`](compare_esm2_650m.md)** | **ESM-2-650M vs MAMMAL on the 40-gene CRISPR-N panel.** MAMMAL 0.750 NN-recall vs ESM-2-650M raw 0.725, **centered 0.750 (tie)**. The prior "MAMMAL 0.92 vs ESM-2-8M 0.88" was on a 25-protein toy panel and didn't transfer. **Under standard anisotropy correction, MAMMAL ties with the open MIT-licensed ESM-2-650M on the canonical panel.** Sapphire embedding-layer pitch survives at parity, not superiority. |
| **[`bbbp_characterization.md`](bbbp_characterization.md)** | **NEXT_STEPS item 5** — characterize the MAMMAL BBBP head. 51-drug panel; Spearman(P(BBB+), MW) = **−0.73** (Graham directionally right). Head behaves as a **size + polarity exclusion gate** (≳450 Da + polar → exclude), not a "<300 Da → brain" rule. **8/8 of "predicted no" are truly non-penetrant; 67% of "predicted yes" are CNS-active.** Saturated at 0/1. Mahdi's "trust the no's, investigate the yes's" reframe fully validated. PNG: `bbbp_vs_physchem.png`. |
| **[`compare_admet_ai.md`](compare_admet_ai.md)** | **ADMET-AI vs MAMMAL on the de-risking layer** (NEXT_STEPS 2 #3). 30-drug panel (15 safe / 15 withdrawn-tox). **ADMET-AI DILI catches 10/12 toxics (TPR 0.83, AUROC 0.73)** vs MAMMAL ClinTox 0.08 / 0.28. ClinTox itself is the wrong endpoint (ADMET-AI's own ClinTox is also TPR 0.00) — failure is the dataset, not the model. **ADMET-AI earns a slot in the de-risking funnel** as the toxicity layer; the mechanism-specific funnel (DILI / hERG / AMES) replaces the broken ClinTox. |
| **[`compare_conplex_nav_offtarget.md`](compare_conplex_nav_offtarget.md)** | **ConPLex full Nav family + off-target sanity** (closes the alternative-models story). 9 SCN paralogs (Nav1.1–Nav1.9) — mean AUROC 0.437, **0/9 above the useful 0.60 line**: ConPLex is pan-Nav blind. Off-target probe (Graham's protocol) — strongest "specificity" signal in the table belongs to *ibuprofen*, not Nav drugs. **Off-the-shelf DTI failure on ion channels is a property of the BindingDB-trained tooling, not MAMMAL-specific.** |
| **[`aws_eval/README.md`](aws_eval/README.md)** | **PROTON + Boltz-2 AWS evaluation (2026-06-07/08)**. PROTON: full success on the 40-gene CRISPR-N panel — **NN-recall 0.487 vs MAMMAL/ESM-2 0.750. PROTON loses to sequence-only embeddings on family clustering** (KG link-prediction objective doesn't optimize for protein-family structure). Boltz-2: 2/5 complexes succeeded (ADRB2/propranolol prob=0.997, DRD2/haloperidol prob=0.988 — both real known binders); 3 failed on a missing CUDA kernel-ops package. Total AWS spend: ~$1.07. |

## Raw run outputs (JSON)

| File | Producing script | Contents |
|---|---|---|
| `phase1_calibration_*.json` | `experiments/phase1_calibration.py` | suzetrigine→Nav1.8 vs negative controls (cold-split checkpoint). Named-test verdict + pKd records. |
| `phase1_correlation_*.json` | `experiments/phase1_correlation.py` | 10 known pairs, predicted pKd vs experimental pChEMBL, **cold-split** checkpoint (Spearman ≈ −0.03). |
| `phase1_peer_comparison_*.json` | `experiments/phase1_peer_comparison.py` | Same 10 pairs on the **PEER** checkpoint (Spearman 0.43) — the fix. Includes PEER suzetrigine→Nav1.8. |
| `phase1_indistribution_*.json` | `experiments/phase1_indistribution_check.py` | In-distribution control on TDC BindingDB_Kd test split (Spearman ~0.61) — proves the model/pipeline work in-domain. |
| `phase1b_bbbp_*.json` | `experiments/phase1b_bbbp_check.py` | Quick hand-set BBBP check (flawed — P-gp/truncation confounds; superseded by the proper eval below). |
| `phase1b_molnet_bbbp_*.json` | `experiments/phase1b_molnet_eval.py bbbp` | Proper scaffold-split held-out BBBP AUROC (0.968, paper 0.957). |
| `phase1b_molnet_tox_*.json` | `experiments/phase1b_molnet_eval.py tox` | Proper scaffold-split held-out ClinTox-tox AUROC (~1.0, paper 0.986). |
| `phase1b_molnet_fda_*.json` | `experiments/phase1b_molnet_eval.py fda` | ClinTox FDA-approval AUROC (~1.0); tiny minority fold (~9 negatives) — high variance. |
| `phase1c_tcr_epitope_*.json` | `experiments/phase1c_tcr_epitope_eval.py` | TCR-epitope (TDC Weber) AUROC 0.931 vs paper 0.879 — balanced n=400, robust. |
| `phase2a_pipeline_*.json` | `experiments/phase2a_pipeline.py` | De-risking funnel (diazepam seed): 2039→150→149 BBB+→43 non-toxic; funnel counts, BBBP precision, ClinTox over-prediction caveat, timing. |
| `phase2c_protein_embedding_*.json` | `experiments/phase2c_protein_embedding.py` | Protein-family embedding recovery (NN same-family 0.92, intra−inter cosine +0.457). |
| `phase2a_similarity_*.json` | `experiments/phase2a_similarity_check.py` | MAMMAL embedding vs Morgan/Tanimoto nearest-neighbor same-class rates + agreement. |
| `phase2b_quiver_targets_*.json` | `experiments/phase2b_quiver_targets.py` | Nav1.8 & mTOR binder-vs-decoy separation (full seq + binding-domain windows) + BBBP/ClinTox de-risking on CNS drugs. Supersedes the earlier ad-hoc `quiver_probes` run. |
| `phase3_wdr91_final_*.json` | `experiments/phase3_wdr91_final.py` | **The corrected, validated result.** Generative readout P(`<1>`)@pos1: AUROC 0.63, **top-5% enrichment 5.25×** (7/26), top-10% 2.95×, Spearman(P(active),pKd) −0.15. |
| `phase3_pgk2_indist_*.json` | `experiments/phase3_pgk2_indist.py` | PGK2 head IN-DISTRIBUTION on CACHE #7 DEL data (1388 hits + read counts): hits-vs-decoys AUROC 0.98 (train-overlap recall, optimistic), but Spearman(score, DEL count) ≈0 → no graded ranking. Sharpens "modest". |
| `phase3_solubility_*.json` | `experiments/phase3_solubility.py` | protein_solubility head on DeepSol test (1992 proteins): acc 0.734, AUROC 0.829 — functional, ~at/slightly below the DeepSol baseline (~0.77). |
| `phase3_realdata_specificity_*.json` | `experiments/phase3_realdata_specificity.py` | **Real binders only (no decoys).** PGK2 head: hits > PGK1 homolog ligands AUROC 0.97, hits > WDR91 actives 0.99 (in-dist recall, sharp). WDR91 head: actives > PGK2 hits AUROC 0.18 (inverted) — weak/non-specific. Sharp head asymmetry. |

## Phase 4 — fine-tuned head real-data audit

| File | What it covers |
|---|---|
| [`phase4_finetuned_report_card.md`](phase4_finetuned_report_card.md) | **THE complete picture — all 9 fine-tuned 458M heads** on real/literature data: benchmark vs real result, calibration, OOD behavior, Quiver verdict. 5 cross-cutting findings (AUROC≠deployable; molnet heads hard-0/1 while protein heads calibrated; OOD failure; input-form sensitivity; the "ClinTox over-predicts" correction). Start here. |
| [`phase4_bbbp_literature.md`](phase4_bbbp_literature.md) | BBBP vs textbook BBB pharmacology — revises "deployable as-is." CNS-active 11/11 but false-positive bias on small peripheral drugs (cetirizine/atenolol/domperidone); hard 0/1 (95% sat); robust to SMILES re-order but protonation-sensitive. Soft positive signal, not a rule-out gate. |

Raw Phase-4 runs: `phase4_bbbp_literature_*.json`, `phase4_molnet_audit_*.json` (BBBP/ClinTox-tox/fda AUROC+saturation+TPR/TNR), `phase4_clintox_literature_*.json` (0% external-toxic sensitivity), `phase4_smiles_robustness_*.json` (encoding flips), `phase4_tcr_solubility_calib_*.json`. Scripts `experiments/phase4_*.py`.

## Phase 5 — extended evaluation on real data + strategic recommendations

| File | What it covers |
|---|---|
| [`phase5_summary.md`](phase5_summary.md) | **The Phase 5 writeup — start here.** Four tests beyond the Phase 4 report card + **tiered deployment recommendations** (Tier 1 ready-now / Tier 2 next-sprint / Tier 3 longer-term) for making MAMMAL useful in Quiver's workflow. Synthesizes the five raw runs below. |
| `phase5_wdr91_spr_*.json` | `experiments/phase5_wdr91_spr.py` — WDR91 head on **Ahmad 2023 SPR real data** (n=239: 38 confirmed binders vs 201 confirmed non-binders, not synthetic decoys). Binary **AUROC 0.816**, top-5% enrichment 4.57× — the **canonical** real-data number (vs 0.63 on synthetic decoys; confirmed SPR zeros are cleaner negatives). Graded potency ranking still fails (Spearman ≈ 0). |
| `phase5_tox_alternatives_*.json` | `experiments/phase5_tox_alternatives.py` — **ClinTox-replacement study** (15 safe + 15 withdrawn/black-box toxic drugs). MAMMAL ClinTox 0% TPR (misses all external toxics); RDKit BRENK+PAINS 41.7%. No omnibus filter catches all 5+ tox mechanisms → proposes a **mechanism-specific funnel** (PAINS/BRENK → hERG rule → pkCSM DILI → BBBP). |
| `phase5_herg_test_*.json` | `experiments/phase5_herg_test.py` — **hERG/QTc-specific rule** (basic N + logP>1.5 + 2 aryl rings): TPR=1.0 / TNR=1.0 on 4 QTc toxics + 6 safe controls. The proposed cardiac-safety replacement for ClinTox. |
| `phase5_esm_comparison_*.json` | `experiments/phase5_esm_comparison.py` — MAMMAL vs **ESM-2 8M** protein embeddings (25 proteins × 5 families). MAMMAL wins NN recall (**0.920** vs 0.880) and family-separation gap (**0.463** vs 0.093). Caveat: benchmark vs ESM-2 650M/3B before committing to Sapphire at scale. |
| `phase5_crispr_panel_*.json` | `experiments/phase5_crispr_gene_panel.py` — **40-gene CRISPR-N panel** clustering. NN recall 0.750; GPCRs/kinases 100%, ion channels 88%, but structurally heterogeneous functional "families" (E3 ligases) fail. MAMMAL **ready for the real 1400-gene CRISPR-N panel** on structurally homogeneous families. |

Raw Phase-5 runs are the five `phase5_*.json` above; scripts `experiments/phase5_*.py`. Full writeup + per-test funnel recommendations: [`phase5_summary.md`](phase5_summary.md).

## Phase 6 — cross-modal alignment (the Sapphire "shared latent space" claim)

| File | What it covers |
|---|---|
| [`phase6_crossmodal_alignment.md`](phase6_crossmodal_alignment.md) | **Does the base model embed a protein target and its known binders into a SHARED space where binders are closer than decoys? Verdict: NO.** 6 targets × 6 families, two readouts: (A) separate-encode protein↔molecule cosine, (B) joint-encode molecule-block↔protein-block alignment (DTI-style prompt, base model). Both fail per-target AUROC, and the two readouts are **anti-correlated (Spearman −0.90)** — the opposite of a real shared space. Cosine is modality-dominated (within-mol 0.72, within-prot 0.28, cross-modal a tight 0.08); the modalities are near-orthogonal. Apparent "positives" (ESR1/EGFR) are chemotype clustering, not binding. Target-specificity ≈ chance (mean rank 3.15 vs 3.5). Corroborates DTI-head failure (`phase2b`). Directly determines the Sapphire shared-latent-space pitch is **not real off-the-shelf**. |

Raw Phase-6 run: `phase6_crossmodal_alignment_20260601_131645.json` (modality diagnostic; per-target + pooled AUROC/Cohen's d/MWU for legs A and B; target-specificity). Script `experiments/phase6_crossmodal_alignment.py` (base model only; `PHASE6_FORCE_CPU=1` to avoid MPS swap-thrash on the 18 GB machine).

## Phase 6 — generation capability (MAMMAL as an actual GENERATOR, not the classifier readout)

| File | What it covers |
|---|---|
| [`phase6_generation.md`](phase6_generation.md) | **What can the PUBLIC base_458m actually generate off-the-shelf? Verdict: only local span-infilling inside a valid scaffold — and only grammar-valid, not accurate. No usable de-novo prior.** Exercised `model.generate` (greedy/beam/sampling) on the base T5's pretraining span-corruption task. **SMILES infill:** format-compliant 8/8, reconstructed-valid 8/8, but **exact recovery 1/8** — produces valid *analogs* (5-Cl/5-OH/5-Br aspirin), never the held-out parent. **SMILES de-novo:** collapses to a single atom; forcing length → invalid garbage → **no de-novo molecule generation** (the "valid_rate 1.0" is hollow — a lone atom parses). **Protein infill:** format/AA-valid 3/3, but recovery ≈ chance (mean AAR 0.07 under sampling; greedy collapses to homopolymers) except hyper-conserved ubiquitin (memorized, AAR 1.0). Model proven healthy via the base PPI classification control (`<1>`, P1=0.946). **Antibody-CDR-infill / PPI-generation (paper headlines) are UNTESTABLE — those design heads are not public.** Reinforces: the generation badge, like the SOTA badges, doesn't survive our bar; the public artifact doesn't even expose the generation the paper sells. |

Raw Phase-6 generation runs: `phase6_generation.json` (SMILES infill/de-novo + protein infill summaries & per-row; probe2 merged under `followup_probe2`), `phase6_generation_probe2.json` (classifier-path integrity, forced de-novo, sampling infill). Scripts `experiments/phase6_generation.py` + `experiments/phase6_generation_probe2.py` (base model only; `PHASE6_GEN_FORCE_CPU=1`).
| `phase3_wdr91_generative_*.json` | `experiments/phase3_wdr91_generative.py` | Token/position sweep that found the readout: `<WDR91_ASMS>` prompt → model emits `<0>` (inactive prior); P(`<1>`)@pos1 AUROC 0.63. |
| `(BBBP harness check)` | `experiments/phase3_generative_harness_check.py` | Validates the generative readout on BBBP: P(`<1>`)@pos1 = 0.996 (matches known), @pos0 = 0.13 → position 1 is the legit readout. Prints to stdout. |
| `phase3_wdr91_finetune_*.json` | `experiments/phase3_wdr91_finetune.py` | **Superseded (wrong readout).** Scalar-head scoring → AUROC 0.43. Kept as the documented false negative. |
| `phase3_wdr91_diagnose_*.json` | `experiments/phase3_wdr91_diagnose.py` | Superseded — scalar-head I/O sweep (all ~0.5); the real fix was the generative readout, not a scalar-readout variant. |
| `phase3_wdr91_ckpt_*.json` | `experiments/phase3_wdr91_ckpt.py` | Shows the `scalars_prediction_head` is base-identical (the clue it's a classifier, not a regressor — the head is vestigial). |
| `phase3_wdr91_repr_probe_*.json` | `experiments/phase3_wdr91_repr_probe.py` | Mean-pooled encoder separability (CV centroid AUROC base 0.857 / wdr91 0.798 / Morgan 0.943) — the task-conditioned generative signal isn't captured by generic mean-pool embeddings. |

`phase1_nrmse_verify.py` (paper NRMSE reproduction) prints to stdout; its numbers are recorded in `phase1_calibration.md`.
