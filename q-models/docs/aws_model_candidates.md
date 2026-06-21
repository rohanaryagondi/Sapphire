# AWS model-test candidate slate — every model worth testing for the 9 Quiver tracks

**Date:** 2026-06-12 · **Branch:** `models` · Companion to `docs/models_tracks_scorecard.md`
(verdicts) and `docs/track_test_plan_2026-06-12.md` (the immediate 3-job wave).

**Purpose:** the full forward list — what to test next on AWS (and locally) across all 9
tracks, so we converge on the best model for each Quiver capability. Prioritized by
**decision-value to Quiver**, not benchmark novelty. The strategic frame holds: the moat is
V1-T + CRISPR-N; these are commodity tools that *enrich* insights. "SOTA on shit is still shit"
— every candidate gets tested on real Quiver substrate (the Boltz test-bed, the CRISPR-N panel,
the external tox/BBBP panels), never paper benchmarks.

**Two hard filters applied to every candidate:**
1. **License must allow commercial use** (Quiver is a company). Non-commercial weights
   (ESM-3, ESM-C 6B, Chai-1, TxGemma) are *research-only* — listed but flagged, test only
   if Quiver legal clears them and only as a science cross-check, never as shippable infra.
2. **Empirical-on-our-data, layer-swept where it's an embedding** (last-layer mean-pool
   undersells by ~0.10 — the 2026-06-12 Track-1 lesson).

**Caveat:** assistant knowledge cutoff is Jan 2026. Models released after that (mid-2026)
are not in this list — do a web/HF scan for "2026 protein LM / DTI / molecular FM" before
finalizing. Existence + license of every candidate below should be re-verified at launch
(HF repo + LICENSE file); the ones marked ✓-verified were curl-checked on HF 2026-06-12.

---

## Status snapshot (what's already settled)

| Track | Winner | State |
|---|---|---|
| 1 Family clustering | ESM-2-650M ≈ MAMMAL (layer-selected ~0.85–0.875) | **Closed on 40-gene panel** (saturated); open = 1,400-gene + function-aware |
| 2 DTI triage | Boltz-2 (Nav 0.714, mTOR 1.0) | Nav marginal; baselines in flight |
| 3 Structure binding | Boltz-2 | `boltz` branch; Chai-1 cross-check only |
| 4 BBBP | MolFormer-XL (0.889) | Strong; Uni-Mol2 cross-check in flight |
| 5 Tox/DILI/hERG | ADMET-AI DILI (0.83) | **GAP: hERG rule weak (0.65), ClinTox dead** — needs dedicated classifiers |
| 6 KG/hypothesis | PROTON | Closed |
| 7 Cross-modal bridge | nothing public works | Build, not buy; Tahoe-x1 = only external test |
| 8 Generative | Morgan FP + Enamine | Skip |
| 9 Off-target | Boltz-2 (folded into T2) | `boltz` branch |

Already tested (don't repeat): MAMMAL 458M, ESM-2 650M/3B/15B, ESM-C 600M, SaProt-650M_AF2,
ProstT5, PINNACLE, PROTON, ConPLex, MAMMAL-DTI, Boltz-2, MolFormer-XL, ADMET-AI, Morgan FP,
hERG rule, MolFormer-ClinTox.

---

## Tier 1 — launch next (highest decision-value, cheap, commercial-OK)

### A. Track 5 — dedicated hERG + DILI classifiers *(fills the gap we just exposed)*
The 2026-06-12 work showed the hERG *rule* is weak (bal-acc 0.65) and ClinTox doesn't
transfer for *any* model. Track 5 has a real hole. The fix is a **trained classifier on the
big TDC safety sets**, not a rule:
- **hERG:** train a probe/fine-tune on TDC `hERG_Karim` (~13K, we already have it) +
  `hERG` / `hERG_central`. Backbones to compare: **MolFormer-XL**, **ChemBERTa-2**
  (`DeepChem/ChemBERTa-77M-MLM`, MIT ✓), Morgan-FP+GBM baseline. Eval on a held-out scaffold
  split + the phase5 cardiac panel. **Target: bal-acc ≥ 0.75 (beat the 0.65 rule).**
- **DILI:** same recipe on TDC `DILI` + DILIst, eval vs ADMET-AI's 0.83 on the 27-drug panel.
- **Systematically eval ADMET-AI's *other* endpoints** (it predicts ~40: hERG, CYP450s, AMES,
  Caco-2, etc.) on held-out TDC sets — we've only ever used its DILI head.
- **Cost:** mostly **local/CPU or one g5.xlarge ~$0.30**. Highest ROI: turns a known gap into
  a shippable Explorer gate.

### B. Track 2 — finish the DTI baseline sweep *(for the deck's "we checked everything")*
- **DrugBAN** + **PerceiverCPI** — *in flight this wave*. BindingDB-trained; expect Nav-blind.
- **+ one more:** **PLAPT** (ProtBERT+ChemBERTa affinity head, fast) or **DrugCLIP**
  (contrastive virtual-screening) on the same Nav/PKM2/HSD11B1/mTOR-FRB test-bed.
- **Purpose:** confirm the pattern — *all* BindingDB DTI models are Nav-blind (zero Nav
  training pairs) → only structure (Boltz) and a Quiver fine-tune work. 2–3 confirmations
  is enough for the deck; diminishing returns after. **Cost: ~$0.30 each.**

### C. Track 1 — function-aware model for the e3/NR gap *(the one unsolved Track-1 sub-problem)*
Every sequence model (MAMMAL, ESM-2/C, SaProt, ProstT5) fails identically on the
**functional-not-fold** families (E3 ligases bal ≤0.5, mislabeled NRs) — it's intrinsic to
sequence embeddings. A model that ingests **functional annotations/text** could crack it:
- **ProtST** (`mila-intel/ProtST-esm1b`, MIT ✓) — protein-sequence ⊕ biomedical-text
  multimodal. Test whether text grounding clusters E3 ligases that fold-homology can't.
- **Ankh / Ankh-large** (`ElnaggarLab/ankh-large` ✓) — efficient protein LM, claims >ESM-2 on
  some tasks at fewer params; layer-sweep it on the 40-gene panel. Cheap completeness check.
- **Cost:** likely **local CPU $0** (both ~ESM-2-650M size) or ~$0.30. Decision-value: the
  *only* path to beating ~0.875 on this panel runs through function, not bigger sequence models.

---

## Tier 2 — run when Tier 1 lands or a gap appears

### Track 4 — BBBP robustness
- **Uni-Mol2** (3D conformer-aware, MIT) — *in flight*. Distributed via Uni-Mol GitHub, not HF
  weights — needs the `unimol_tools` install path on the instance.
- **ChemBERTa-2** — cheap SMILES-transformer cross-check; also reusable for Track 5.
- **MapLight / TDC-BBB-leaderboard GBM** — descriptor models, CPU $0; often competitive.
- Priority is the **held-out 100-drug validation** of the MolFormer+MAMMAL funnel (local $0),
  not new models — MolFormer is already winning.

### Track 3 — structure cross-check (coordinate with `boltz` branch)
- **Chai-1** (`chaidiscovery/chai-1`) — AF3-class. **Non-commercial license — legal check
  first.** Only as a Boltz-2 second oracle on the Nav panel; won't ship. ~$3–8 A100.
- **NeuralPLexer3** — co-folding alt; check license. Lower priority than finishing Boltz.

### Track 7 — cross-modal bridge (the moat-adjacent test)
- **Tahoe-x1** (`tahoebio/Tahoe-x1`, Apache-2.0 ✓) — perturbation FM with a drug token; the
  one external model that could plausibly map V1-T trace embeddings ↔ compounds. **BLOCKED on
  paired (trace, compound) data — ask Mahdi.** CNS-transfer risk from cancer-line training is
  real. ~$3 g5. Don't launch until we can feed it real V1-T embeddings.
- Everything else here is **build, not buy**: a contrastive head on Quiver's own paired data
  (prior art: CLOOME / MolPhenix, cell-painting→SMILES). Not a model to download.

---

## Tier 3 — license-flagged (test ONLY if Quiver legal clears non-commercial research use)

These could inform the science ceiling but **cannot ship** in a commercial product:
- **ESM-C 6B** (EvolutionaryScale, non-commercial) — the "does scale finally help Track 1"
  ceiling test. Our commercial-OK ladder (650M–15B) said no; 6B is unlikely to differ but
  would close the question. Research-only.
- **ESM-3** (non-commercial open weights) — generative protein model; license trap.
- **TxGemma-9B-predict** (Google, HAI-DEF research-only) — unified 66-task TDC head; would be
  a strong Track-5 multi-endpoint baseline if licensing allowed. Skip per standing user call.
- **Chai-1** (non-commercial) — see Track 3.

## Do NOT test (settled negatives — don't burn AWS)
- **scFoundation / scGPT / Geneformer / CellPLM** — Nature Methods 2025 (Ahlmann-Eltze et al.,
  DOI 10.1038/s41592-025-02772-6): all underperform a mean-of-training baseline on perturbation
  prediction. Relevant if Track 7 ever reopens with sc-data; still don't use these.
- **MAMMAL-DTI, ConPLex on Nav** — already Nav-blind.
- **MAMMAL/MolFormer ClinTox heads** — ClinTox label doesn't transfer (2026-06-12).
- **Generative-chemistry models (REINVENT4, SAFE-GPT, etc.)** — Track 8 is a non-priority;
  Quiver's bottleneck is target ID + triage, not de-novo generation.

---

## The two things that beat any off-the-shelf model (not "test", but "train")
The off-the-shelf eval is essentially done. The real remaining wins are Quiver-data fine-tunes
on tasks IBM/public models have no head for:
1. **Nav1.8 fine-tune** on Quiver SPR/binding data, scaffold-held-out split (Q3 #1). Needs the
   data — **ask Mahdi/David.** This is the highest-value model work overall.
2. **V1-T → compound contrastive bridge** (Track 7 build) on Quiver's paired perturbation data.
   The moat made into a model. Needs paired data — **ask Mahdi.**

## Recommended launch order
1. **Now (mostly local $0, some 1× g5):** Tier-1A hERG/DILI classifiers + Tier-1C function-aware
   (ProtST/Ankh) — these close real gaps.
2. **This wave (3× g5 ~$0.90):** DrugBAN + PerceiverCPI (T2, in flight) + Uni-Mol2 (T4, in flight)
   + add PLAPT/DrugCLIP if a slot frees.
3. **Gated on data (ask Mahdi):** Tahoe-x1 (T7), then the two fine-tunes.
4. **Legal-gated:** Chai-1 / ESM-C 6B only if cleared, science-only.
Total off-the-shelf spend to exhaust Tiers 1–2: **< $5**, well under the $15/session cap.
