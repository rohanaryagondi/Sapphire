# Q-MAMMAL — Handoff

**Read this top to bottom. It is the single entry point.** It tells a fresh machine how to set
up, download the models, and understand *everything we have tried* evaluating IBM's MAMMAL
biomedical foundation model for Quiver Bioscience. Authoritative detail lives in `docs/` and
`results/`; this doc orients and points.

> **If you are an AI agent picking this up:** do the Quickstart, then read `docs/FINDINGS.md`
> (synthesis) and `results/phase4_finetuned_report_card.md` (per-head verdicts). Verify before
> claiming — this project has repeatedly turned false negatives into real results (and one real
> result into a false negative) by using the wrong checkpoint, readout, or input form. Empirical
> results on our data beat paper benchmarks.

---

## 0. One-paragraph verdict (what we concluded)

MAMMAL is **commodity enrichment, not core infrastructure**, for Quiver. Off-the-shelf it is a
useful **soft de-risking / representation layer** (BBB-penetrance as a *positive* signal; sensible
protein/gene embeddings) and a **weak cross-target re-ranker** (DTI). It is **not** a binding
oracle (single-target binder triage ≈ chance) and its classification heads emit **uncalibrated
hard 0/1 labels that mislead out-of-distribution**. **Per-target fine-tuning works but is bounded**
— IBM's `wdr91`/`pgk2` heads are generative binder *classifiers* that recognize their trained
chemotype (modest enrichment), not novel-hit or potency predictors. The moat stays Quiver's
functional trace data (the separate V1-T project); MAMMAL enriches insights, it isn't the insight.

---

## 1. Quickstart on a new machine

```bash
# 1. clone
git clone https://github.com/rohanaryagondi/Q-Mammal.git
cd Q-Mammal

# 2. environment (Python 3.11; conda recommended)
conda create -n mammal python=3.11 -y
conda activate mammal
pip install -r requirements.txt      # biomed-multi-alignment (MAMMAL) + PyTDC (brings rdkit)

# 3. download the model weights (~17 GB into ./models/, skips redundant .ckpt files)
bash scripts/download_models.sh                 # or pass names: base_458m moleculenet_bbbp ...

# 4. smoke test (must print a finite vector + a BBBP score)
USE_TF=0 USE_FLAX=0 python experiments/phase0_smoke_test.py
```

**Hardware:** built on an M3 Pro Mac (MPS), ~0.4–0.8 s/inference. CUDA or CPU also work — the code
auto-picks `mps` → `cuda` → `cpu`. No GPU strictly required; CPU is just slower.

**Critical env var — `USE_TF=0` (and `USE_FLAX=0`):** transformers auto-imports TensorFlow which
**deadlocks on macOS** (`[mutex.cc:452] RAW: Lock blocking`). The `mammal_quiver` package sets
these at import and every script sets them too — but any ad-hoc REPL must `export USE_TF=0
USE_FLAX=0` first.

**Run any experiment from the repo root:** `python experiments/phaseX.py`. They add the repo to
`sys.path` and import the `mammal_quiver` package.

---

## 2. The models (`./models/`, gitignored — fetched by the script)

10 checkpoints, each the full 458M model + a task head (~1.7 GB each, ~17 GB total). 458M is the
only model size IBM published; there is no v2.

| local dir | HuggingFace repo | task / readout | our verdict |
|---|---|---|---|
| `base_458m` | `ibm-research/…ma-ted-458m` | foundation; embeddings + generation | embeddings useful (proteins) |
| `dti_bindingdb_pkd` | `…ma-ted-458m.dti_bindingdb_pkd` | DTI pKd (cold-split) | **wrong checkpoint for us** (Spearman −0.03) |
| `dti_bindingdb_pkd_peer` | `…dti_bindingdb_pkd_peer` | DTI pKd (PEER split) | **the correct DTI checkpoint** (0.43); soft re-rank only |
| `moleculenet_bbbp` | `…moleculenet_bbbp` | BBB penetrance (generative class) | soft **positive** signal, not a rule-out gate |
| `moleculenet_clintox_tox` | `…moleculenet_clintox_tox` | clinical toxicity | **not usable** (0% external-toxic sensitivity) |
| `moleculenet_clintox_fda` | `…moleculenet_clintox_fda` | FDA approval | trivial (94% positive); not useful |
| `protein_solubility` | `…protein_solubility` | solubility (generative class) | functional ~baseline; calibrated |
| `tcr_epitope_bind` | `…tcr_epitope_bind` | TCR–epitope binding | works (0.93–0.96); low Quiver relevance |
| `wdr91_asms` | `michalozeryflato/…wdr91_asms` | **per-target** WDR91 binder classifier | weak; chemotype-recall only |
| `pgk2_del_cdd` | `michalozeryflato/…pgk2_del_cdd` | **per-target** PGK2 binder classifier | recognizes trained chemotype; not discovery |

Notes:
- `ibm/…` is a mirror of `ibm-research/…`; either resolves. The per-target heads are under
  `michalozeryflato` (a MAMMAL co-author), have **no model cards**, and ship a redundant 4.6 GB
  `last.ckpt` we skip (verified equal to the safetensors).
- **DTI normalization constants matter:** cold-split uses mean/std `5.794 / 1.338`; **PEER uses
  `6.286 / 1.542`** (pass these to `predict_pkd`). Using the wrong ones silently corrupts pKd.

---

## 3. Repo map

```
HANDOFF.md            ← you are here (entry point)
CLAUDE.md             ← terse orientation for AI agents (state + gotchas + conventions)
README.md             ← human-facing overview
requirements.txt / pyproject.toml
scripts/
  download_models.sh  ← fetch all 10 checkpoints (HF API + curl resume)
  download_data.sh    ← re-fetch the large/auto-downloadable datasets (optional)
mammal_quiver/        ← the package (thin inference wrappers; sets USE_TF=0 at import)
  dti.py              ← load_dti_model, predict_pkd        (DTI pKd regression)
  embed.py            ← load_base_model, embed             (768-d compound/protein embeddings)
  wdr91.py            ← load_target_model, binder_prob     (per-target generative classifiers)
  sequences.py        ← UniProt fetch + reference SMILES/targets
experiments/          ← runnable phase scripts (phase0 → phase4); each is self-contained
docs/                 ← planning + synthesis (read docs/README.md for order); FINDINGS.md is key
results/              ← authoritative .md writeups + timestamped .json raw runs; README.md indexes
data/
  wdr91/  pgk2/        ← curated test sets (committed — hard to regenerate)
  solubility/ *.tab    ← large / TDC-downloadable (gitignored; auto-fetched on first run)
```

The package + experiments split: `mammal_quiver/` is reusable inference code; `experiments/` are
one-off evaluation scripts that import it. Findings flow `experiments/*.py` → `results/*.json`
(raw) → `results/*.md` (writeups) → `docs/FINDINGS.md` (synthesis).

---

## 4. Everything we've tried — findings by phase

Condensed; full detail + numbers in the linked `results/` and `docs/` files. **Bar = empirical
results on our problems, not paper benchmarks.**

### Phase 0 — Instantiation
Got MAMMAL running locally, encoded a compound, inspected the embedding. Solved the macOS
TF-deadlock (`USE_TF=0`). → it's usable.

### Phase 1 — Calibration on ground truth (`results/phase1_calibration.md`, `benchmark_verification.md`)
- **The checkpoint you pick is everything.** DTI on our 10 known pairs: Spearman **−0.03** with the
  cold-split head vs **0.43** with the **PEER** head (our targets are PEER's held-out classes). Use
  PEER + its norm constants.
- **Paper benchmarks are honest but the DTI "SOTA" is modest:** reproduced NRMSE ~0.88 (paper
  0.906) — only ~9% better than predicting the mean. "State-of-the-art on shit is still shit."
- **Named test suzetrigine (Jernabix/Journavx/VX-548) → Nav1.8 FAILS** — post-cutoff drug + target
  truncated to 1250 aa (binding region in the unseen C-terminal).
- Independently verified 5 published heads reproduce: DTI 0.88, BBBP 0.968, TCR 0.931, ClinTox ~1.0,
  solubility 0.73/0.83. The other paper tasks ship no public checkpoint.

### Phase 2 — Real Quiver use cases (`phase2_quiver_utility.md`, `phase2a_expansion_check.md`, `phase2b_quiver_targets.md`)
- **DTI single-target triage FAILS:** Nav1.8 & mTOR binder-vs-decoy separation ≈ 0; truncation
  ruled out (binding-domain windows don't help). The model lacks the resolution.
- **2026-06-07 update — ConPLex does NOT beat MAMMAL** ([`results/compare_dti_models.md`](results/compare_dti_models.md)).
  First head-to-head off-the-shelf DTI comparison. ConPLex (zero-shot, BindingDB checkpoint) loses
  the correlation test (ρ −0.03 vs MAMMAL ρ +0.43) and is worse on the named test (z-margin −2.35 vs
  −0.69); both sit at chance on Nav1.8 and mTOR. **Zero-shot DTI failure on Nav-like targets is
  GENERAL, not MAMMAL-specific** — the entire BindingDB-trained DTI tooling space has the same
  training-coverage holes. Boltz-2 row pending AWS retrieval. Means: no off-the-shelf alternative
  rescues Quiver's Nav binder-triage need; an in-house Nav fine-tune is the only available lever.
- **2026-06-07 update — "data gap vs model limit" answered with nuance** (`results/datafit_summary.md`,
  with [`datafit_ceiling.md`](results/datafit_ceiling.md) and [`datafit_curve.md`](results/datafit_curve.md)).
  Re-ran the binder-vs-decoy protocol on 6 well-trained targets (incl. mTOR) and a 16-target threshold
  curve. **Data volume is necessary but not sufficient.** 3/6 ceiling targets clear AUROC ≥ 0.80 on
  both random and MW-matched decoys (RORC 0.97/0.95, CA2 0.87/0.84, Adrb2 0.87/0.88); BRAF — the
  *most*-trained target in BindingDB — sits at chance (0.47); HRH1 below chance; mTOR random-only
  (0.76), collapses on matched (0.56), inverts off-target (Δ −1.12). The threshold curve is
  non-monotonic (peak 0.77 at 40–149 pairs, drops to 0.60 in 150–2000 with σ doubling). **A Quiver
  Nav fine-tune lifts Nav off the 0-pair floor but has no guarantee of landing in the "good" mode at
  the high end** — plan for go/no-go on held-out scaffold AUROC.
- **Similarity expansion:** Morgan fingerprints beat MAMMAL embeddings (0.96 vs 0.72 same-class NN).
  Use fingerprints to expand hit lists, not MAMMAL.
- **Protein embeddings recover functional family** (NN 0.92) — promising for CRISPR-N gene
  clustering + the Sapphire KG. (Benchmark vs ESM-2 before committing — untested.)

### Phase 3 — Per-target fine-tuning (Q14) (`results/phase3_wdr91_finetune.md`)
The decisive question: does fine-tuning per target give the binder-triage off-the-shelf DTI lacks?
- **The per-target heads are GENERATIVE CLASSIFIERS, not scalar regressors.** This was a trap: the
  config looks like DTI (scalar head), but that scalar head is **untrained/vestigial** (bit-identical
  to base). Reading it gives AUROC 0.43 and looks "broken" — a false negative we initially fell for.
  **Correct readout:** prompt with the task token (`<WDR91_ASMS>`) + `<SENTINEL_ID_0>`,
  `model.generate`, read **P(`<1>`) at classification position 1** (validated on BBBP → 0.996).
  Use `mammal_quiver.wdr91.binder_prob`, **not** `score_smiles`.
- **It works, modestly:** WDR91 actives vs decoys, out-of-distribution, AUROC **0.63**, **top-5%
  enrichment 5.25×**. PGK2 head separates its hits from the **PGK1 homolog's** real ligands at
  **0.97** (but that's in-distribution recall; no graded ranking — Spearman vs DEL count ≈ 0).
- **Bounded:** recognizes its trained chemotype; weak/non-specific on novel compounds (the WDR91
  head barely fires; PGK2 molecules even outscore WDR91's own actives). No potency ranking.
- **Q14 leans YES** for an in-house *chemotype-triage* fine-tune on Quiver screening/DEL data — not
  as a novel-hit or potency predictor. Evaluate by enrichment factor on a held-out scaffold split.

### Phase 4 — Complete fine-tuned-head audit on real data (`results/phase4_finetuned_report_card.md`) ← most current
Tested every head on real/literature data (calibration, per-direction, out-of-distribution):
- **BBBP** (`phase4_bbbp_literature.md`): correct on clearly CNS-active drugs (11/11) and obvious
  exclusions, but **false-positive bias** — passes small peripherally-restricted/efflux drugs
  (cetirizine, atenolol, domperidone) as "penetrant" (held-out **TNR 0.70** vs TPR 0.98). → **soft
  positive signal, not a rule-out gate.**
- **ClinTox-tox:** AUROC 1.0 is **memorization of its ~112 training toxics** — **0% sensitivity to
  external clinically-toxic drugs** (misses cerivastatin, troglitazone, terfenadine, thalidomide…).
  The earlier "over-predicts toxicity" claim was an **artifact of raw isomeric/charged input SMILES**;
  with clean SMILES it under-detects. **Do not use as a tox gate** (recalibration won't fix
  no-generalization).
- **Calibration is head-specific:** the MoleculeNet small-molecule heads emit **saturated hard 0/1**
  (BBBP 95%, ClinTox 100% of scores at ~0/1 — not usable probabilities); the **protein heads are
  calibrated** (TCR 28%, solubility 17% saturated).
- **Input-form sensitivity:** BBBP is robust to SMILES atom-reordering (0/6 flip) but sensitive to
  protonation/salt form; ClinTox flips even on pure re-encoding (1/6). **Standardize protonation/
  salt/tautomer before scoring.**
- **Meta-rule:** benchmark AUROC ≠ deployable per-compound filter. Validate on held-out scaffold
  splits, treat molnet scores as binary labels, expect in-distribution-only reliability.

### Phase 5 — Extended evaluation on real data + deployment plan (`results/phase5_summary.md`)
Four tests past the Phase 4 audit, plus a tiered (ready-now / next-sprint / longer-term) plan for putting MAMMAL
to work. **Sharpens, doesn't overturn, Phases 1–4:**
- **WDR91 head on real SPR data (Ahmad 2023, n=239):** 38 confirmed SPR binders vs 201 confirmed non-binders →
  **AUROC 0.816, top-5% enrichment 4.57×** — *higher* than the 0.63 on synthetic decoys (confirmed SPR zeros are
  cleaner negatives than random drug-like ones). **Take 0.816 as the canonical** binary-separation number;
  graded potency ranking still fails (Spearman ≈ 0). Binary classifier, not a potency predictor.
- **MAMMAL vs ESM-2 protein embeddings:** beats **ESM-2 8M** on NN recall (0.920 vs 0.880) and family gap
  (0.463 vs 0.093) over 25 proteins × 5 families — but **benchmark vs ESM-2 650M/3B before committing** to
  Sapphire (8M is a weak bar).
- **Tox-gate alternatives (ClinTox replacement):** ClinTox's 0% external-toxic sensitivity reconfirmed; no single
  filter catches all 5+ mechanisms → proposed **mechanism-specific funnel** (PAINS/BRENK → hERG/QTc rule →
  pkCSM DILI → BBBP). The hERG/QTc rule (basic N + logP>1.5 + 2 aryl rings) hit TPR=1.0/TNR=1.0 on a small QTc set.
- **CRISPR-N 40-gene panel clustering:** structurally homogeneous families (GPCRs/kinases/ion channels) cluster
  at ~100% NN recall; structurally heterogeneous functional groups (E3 ligases) don't → **ready for the real
  1400-gene CRISPR-N panel** on homogeneous families, manual interpretation for the rest.

Full writeup + Tier 1/2/3 deployment plan: `results/phase5_summary.md`.

---

## 5. Per-capability cheat sheet (use / don't use, today)

| Capability | Verdict |
|---|---|
| BBB-penetrance (BBBP) | ✅ soft **positive** signal; ❌ not a rule-out gate; standardize SMILES; scores are hard labels |
| Protein/gene embeddings | ✅ functional-family clustering (NN 0.92); benchmark vs ESM-2 before Sapphire commits |
| DTI binding (PEER) | ⚠️ coarse cross-target re-rank only; ❌ single-target triage; needs PEER norms 6.286/1.542 |
| Solubility | ✅ functional ~baseline (acc 0.73 / AUROC 0.83), calibrated; modest utility |
| Per-target fine-tune (wdr91/pgk2) | ⚠️ chemotype-triage gate only (generative readout); not novel-hit/potency |
| ClinTox toxicity | ❌ not usable (0% external-toxic sensitivity; memorization) |
| Compound similarity | ❌ use Morgan fingerprints instead |
| TCR-epitope | ➖ works but low Quiver relevance |
| Feeding functional traces | ❌ no trace modality — that's the V1-T project's job, never MAMMAL |

---

## 6. Gotchas (consolidated — these cost us time)

1. **`USE_TF=0 USE_FLAX=0`** before importing transformers/mammal (macOS TF deadlock).
2. **HF downloader resume is broken on this network** — use `scripts/download_models.sh` (curl
   `-C - --retry`), not `huggingface-cli download`.
3. **DTI: use the PEER checkpoint + its norm constants** (6.286 / 1.542), not cold-split.
4. **Per-target heads (wdr91/pgk2) are generative classifiers** — read P(`<1>`) via `model.generate`,
   NOT the scalar head (which is untrained → false-negative 0.43). Use `wdr91.binder_prob`.
5. **MoleculeNet head scores are hard 0/1, not probabilities** — don't threshold-tune or rank by them.
6. **Standardize input SMILES** (strip salts, neutralize, fix protonation) before molnet scoring —
   predictions can flip across valid encodings/forms of the same molecule.
7. **DTI truncates protein to 1250 aa, SMILES to 256 tokens** — large targets lose their C-terminus.
8. **Benchmark AUROC ≠ deployable** — every head ranks well on its dataset yet fails out-of-distribution.

---

## 7. Open questions / next steps

1. **Pilot an in-house per-target fine-tune** (binary hit/non-hit on Quiver screening/DEL data;
   evaluate by enrichment factor on a held-out scaffold split). This is the live Q14 decision.
2. **Benchmark MAMMAL protein embeddings vs ESM-2** before Sapphire commits to MAMMAL embeddings.
3. **Apply protein-embedding clustering to the real CRISPR-N 1400-gene panel** (use case 4).
4. **Replace ClinTox** with a calibrated tox / P-gp-efflux model for the de-risking funnel's tox step.
5. The unverifiable paper tasks (cell-type, cancer-drug-response, antibody design, PPI ΔΔG) ship no
   public checkpoint — note, don't chase.

---

## 8. Reproduce any result

Every number above comes from a script in `experiments/`. Examples:
```bash
USE_TF=0 python experiments/phase1_peer_comparison.py        # DTI PEER vs cold-split on our pairs
USE_TF=0 python experiments/phase1b_molnet_eval.py bbbp      # BBBP held-out scaffold AUROC
USE_TF=0 python experiments/phase3_wdr91_final.py            # WDR91 binder enrichment (generative)
USE_TF=0 python experiments/phase3_realdata_specificity.py   # per-target real-data specificity
USE_TF=0 python experiments/phase4_molnet_audit.py           # BBBP/ClinTox calibration + TPR/TNR
USE_TF=0 python experiments/phase4_bbbp_literature.py        # BBBP vs textbook BBB pharmacology
USE_TF=0 python experiments/phase4_smiles_robustness.py      # SMILES-encoding stability
```
Outputs land in `results/phase*_*.json`; the `.md` files interpret them. `results/README.md` and
`docs/README.md` are the indexes.

---

## 9. Context / people / reporting

- Quiver Bioscience evaluation of IBM MAMMAL (`ibm/biomed.omics.bl.sm.ma-ted-458m`, npj Drug
  Discovery 2026, arXiv 2410.22367; code `github.com/BiomedSciAI/biomed-multi-alignment`).
- Owner: **Rohan Aryagondi** (rohan.gondi@quiverbioscience.com). David has a MAMMAL interface built.
- Strategic frame (`docs/meeting_context.md`): MAMMAL = downstream commodity enrichment; the moat is
  the functional trace data + the V1-T foundation model. Two questions the work serves: (1) how much
  does our measurement improve insight enrichment? (2) with the insight, how fast to molecules?
- Notion project page exists (private); push findings there only with Rohan's OK.
