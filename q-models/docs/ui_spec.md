# Quiver MAMMAL Explorer — UI spec

**Internal tool.** Purpose: *see what IBM's MAMMAL can actually do, with Quiver's empirically-grounded
confidence shown next to every prediction.* Inspired by David Margulies' MAMMAL Query UI (FastAPI +
single-page frontend) — we reuse his clean scaffold and setup recipe, and add the thing only Quiver has:
**a reliability verdict + the evidence behind it on every result.**

> **The differentiator.** Margulies' UI presents every capability at face value. We have run the
> experiments (Phases 0–6). So this UI lets the model predict *and* tells the user, per capability,
> whether to trust it and why — citing our own `results/` writeups. That reliability overlay is the
> point of building our own instead of just using his.

**Scope now:** all public IBM heads, badged with our confidence. **Future:** swap in Quiver-fine-tuned
per-target heads (the only place fine-tuning beats the best-available MAMMAL — see
`results/aws_finetune_pilot.md`). The frontend is for *us* to watch how the model does; production
polish comes later.

---

## 1. Capabilities to expose (every public head + base capabilities)

Verified published checkpoints (HF API, 2026-06-02): base + `dti_bindingdb_pkd[_peer]`,
`moleculenet_bbbp`, `moleculenet_clintox_tox`, `moleculenet_clintox_fda`, `protein_solubility`,
`tcr_epitope_bind`. **There is NO `carcinogenicity` checkpoint** (train-code only — do not build a tab
for it; Margulies' doc is wrong on this).

Each tab: input field(s) → **Predict** → model output **+ a reliability panel** (badge + one-line why +
"recommended use" + link to the `results/` doc). "Load example" prefills a known input.

| # | Tab | HF model | Input → Output | Readout |
|---|---|---|---|---|
| 1 | Drug–Target Binding (DTI) | `…dti_bindingdb_pkd_peer` | SMILES + protein AA → pKd | **scalar**, PEER norms (×1.542 +6.286) |
| 2 | Protein–Protein Interaction | base | 2 protein AA → interact? | generative P(`<1>`) |
| 3 | BBB Penetrance (BBBP) | `…moleculenet_bbbp` | SMILES → penetrant? | generative P(`<1>`) |
| 4 | Clinical Toxicity | `…moleculenet_clintox_tox` | SMILES → tox-trial fail? | generative P(`<1>`) |
| 5 | FDA Approval | `…moleculenet_clintox_fda` | SMILES → approved? | generative P(`<1>`) |
| 6 | Protein Solubility | `…protein_solubility` | protein AA → soluble? | generative P(`<1>`) |
| 7 | TCR–Epitope Binding | `…tcr_epitope_bind` | TCR + epitope AA → bind? | generative P(`<1>`) |
| 8 | *(optional)* Generation | base | masked SMILES/AA → infill | `model.generate` |
| 9 | *(optional)* Embeddings | base | protein/SMILES → 768-d vec + nearest-family | mean-pool |

**Readout correctness — do not get this wrong (it's how every prior eval broke):**
- **Classifier heads (2–7) use the GENERATIVE readout**, not the scalar head: prompt with the task token
  + `<SENTINEL_ID_0>`, `model.generate`, read **P(`<1>`)** at class position 1. The scalar head is
  vestigial → reading it gives garbage. Source of truth: **`mammal_quiver/wdr91.py` (`binder_prob`)** and
  `mammal/examples/carcinogenicity/main_infer.py` (`process_model_output`).
- **DTI (1) uses the PEER checkpoint** `dti_bindingdb_pkd_peer` with norms **mean 6.286 / std 1.542**
  (de-normalize the scalar). NOT the cold-split checkpoint. Truncates protein to 1250 aa, SMILES to 256
  tokens. Source: `mammal_quiver/dti.py` (`predict_pkd`).
- **Standardize SMILES** (neutralize charges, strip salts) before scoring 3–5 — predictions flip across
  valid encodings of the same molecule.

---

## 2. The reliability overlay (the core feature — Quiver's empirical verdicts)

Each capability ships a verdict from our experiments. Badges: **✅ Reliable · ⚠️ Caution · ❌ Don't use ·
➖ Low value**. This data lives in `backend/reliability.py` (one record per task) and renders on every
prediction. **Keep the wording honest — it's the whole point.**

| Capability | Badge | Headline | Why (our evidence) | Recommended use | Source |
|---|---|---|---|---|---|
| **DTI (pKd)** | ⚠️ Caution | Coarse cross-target ranking only — **not** single-target triage | Spearman just 0.43 across 10 known pairs; on single targets (Nav1.8, mTOR) binders score **no better than random decoys**; "SOTA" NRMSE is only ~9% better than predicting the mean; the named suzetrigine→Nav1.8 test **fails**. | Soft ranking across a *diverse* target set. Do NOT use to decide "does compound X bind target Y." | `results/phase1_calibration.md`, `phase2b_quiver_targets.md` |
| **PPI** | ✅ Reliable* | Paper-validated; light internal check | IBM's PPI benchmark reproduces honestly; our spot check (calmodulin–calcineurin) gives P≈0.95. *We did not benchmark it broadly ourselves.* | Reasonable for clear cases; treat borderline scores cautiously. | `results/benchmark_verification.md` |
| **BBBP** | ⚠️ Caution | Soft **positive** signal — not a rule-out gate | AUROC 0.968 held-out and 11/11 clearly CNS-active drugs correct, **but** a false-positive bias: passes small peripherally-restricted drugs (cetirizine, atenolol) as "penetrant"; hard 0/1, uncalibrated. | Trust a "penetrant" call as a soft positive; don't rule a compound IN on it; standardize SMILES first. | `results/phase4_bbbp_literature.md` |
| **ClinTox (tox)** | ❌ Don't use | Memorization — 0% sensitivity to real external toxics | Perfect benchmark AUROC is memorizing ~112 training toxics; **misses cerivastatin, troglitazone, terfenadine, thalidomide**. Recalibration won't fix a no-generalization head. | Do not gate on it. Use a mechanism-specific model (hERG rule / pkCSM DILI) for tox. | `results/phase4_finetuned_report_card.md`, `phase5_summary.md` |
| **FDA Approval** | ➖ Low value | Near-trivial task | ~94% of the FDA dataset is positive → a "FDA-approved" prediction carries little information. | Sanity-check only. | `docs/mammal_checkpoint_survey.md` |
| **Protein Solubility** | ✅ Reliable | Functional, ~at baseline | DeepSol test acc 0.734 / AUROC 0.829 — at (slightly below) the dedicated DeepSol baseline; behaves like a calibrated classifier. | Usable soluble/insoluble indicator; modest utility (biologics/expression). | `results/benchmark_verification.md` |
| **TCR–Epitope** | ✅ Reliable | Works; low Quiver relevance | AUROC 0.931 on the Weber benchmark, calibrated. Immuno-oncology — peripheral to Quiver's CNS focus. | Works; not core to us. | `results/benchmark_verification.md` |
| **Generation** | ❌ Don't use (for design) | Span-infill only, no de-novo | Public base model generates grammar-valid *analogs* (1/8 exact recovery); de-novo collapses; the paper's antibody/PPI generation heads aren't public. | Demo only. Not a design tool. | `results/phase6_generation.md` |
| **Embeddings** | ✅ / ❌ split | Family clustering YES; cross-modal binding NO | Protein embeddings recover functional family (NN recall 0.92, beats size-matched ESM-2 650M). But protein & SMILES embeddings are **near-orthogonal** (cross-modal cosine 0.08) — no shared space where a target and its ligands are neighbors. | Use for gene/protein family clustering (CRISPR-N, KG). Do NOT use for protein↔compound retrieval. | `results/phase6_crossmodal_alignment.md` |

**Strategic banner (show somewhere persistent):** *"MAMMAL is commodity enrichment, not a binding
oracle. The capabilities Quiver will actually win on are per-target binder heads fine-tuned on Quiver
data — not yet in this UI. See `results/aws_finetune_pilot.md`."*

---

## 3. Architecture (Margulies' scaffold + a reliability layer)

```
ui/
  backend/
    app.py            FastAPI: /health, /reliability/{task}, /predict/{dti,ppi,bbbp,clintox_tox,
                      clintox_fda,solubility,tcr}  (+ optional /generate, /embed)
    mammal_runner.py  lazy per-task model load + the CORRECT readouts (reuse mammal_quiver/wdr91.py
                      binder_prob + dti.py predict_pkd). One model cached per task; load on first call.
    reliability.py    the §2 verdicts as structured records (badge/headline/why/use/source) — served
                      to the frontend so every prediction shows its confidence.
    models.py         pydantic request/response schemas (prediction + embedded reliability).
  frontend/
    index.html        single-page tabbed UI. Each tab: inputs + Load-example + Predict; result card
                      shows the prediction AND a reliability panel (colored badge, headline, why,
                      recommended-use, source link). A persistent strategic banner (§2).
  tests/
    test_endpoints.py pytest smoke tests: /health, each /predict returns a number + its reliability,
                      /reliability/{task} returns the verdict. Mark model-loading tests "slow".
  scripts/
    predownload_models.py   cache the ~7 public checkpoints (avoid first-request latency).
  README.md           run instructions.
```

API shape: every `/predict/*` response includes both the raw model output and the reliability record,
e.g. `{ "prediction": {...}, "reliability": { "badge": "caution", "headline": "...", "why": "...",
"recommended_use": "...", "source": "results/phase2b_quiver_targets.md" } }`.

---

## 4. Setup (the recipe that worked — Margulies', adapted)

Two options. For an internal "watch the model" tool, **reuse our existing conda `mammal` env** (proven
for inference, Phases 0–6) and just add the server deps. Use the clean venv recipe for a deployable box.

**Option A — reuse the existing conda env (fastest):**
```bash
conda activate mammal       # /opt/anaconda3/envs/mammal — already has biomed-multi-alignment + deps
pip install fastapi uvicorn pydantic python-dotenv httpx pytest
```

**Option B — clean venv (Margulies' --no-deps recipe; avoids the TensorFlow bloat we hit on AWS):**
```bash
python3.12 -m venv venv && source venv/bin/activate
pip install biomed-multi-alignment --no-deps            # --no-deps skips the unused TF dependency
pip install "fuse-med-ml==0.4.0" --no-deps              # 0.4.1 conflicts with bma 0.2.4
pip install torch                                        # (CPU) or torch --index-url .../whl/cu121 (GPU)
pip install "transformers==4.47.0"                       # newer can break T5 loading
pip install huggingface-hub omegaconf hydra-core sentencepiece peft tabulate
pip install hdf5plugin h5py pandas "numpy<2" rdkit
pip install ipython termcolor psutil matplotlib deepdiff wget torchvision tensorboard scikit-learn scipy statsmodels
pip install fastapi uvicorn pydantic python-dotenv httpx pytest
```

**Env vars (always):** `export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1`. Point the HF cache at a disk
with space: `export HF_HOME=<dir with ~10GB>`. Pre-download with `scripts/predownload_models.py`.

**Run:** `uvicorn backend.app:app --reload` → open `frontend/index.html` (API at `http://localhost:8000`,
docs at `/docs`). M3 Pro / MPS or CPU is fine (slow, ~seconds/prediction) for an internal tool.

---

## 5. Explicitly out of scope (now) / future

- **No Quiver fine-tuned heads yet** — this UI shows IBM's public heads only. The real build-out (and the
  only place fine-tuning beats the best-available MAMMAL) is per-target binder heads on Quiver targets
  (Nav1.8, UBE3A/DUP15Q, mTOR, DFP/CRISPR-N). Architect the tabs so a Quiver head can drop in beside the
  IBM head for the same task. See `results/aws_finetune_pilot.md`.
- **No batch input yet** — single prediction per tab. Quiver's real use is triaging *many* compounds
  (DFP/DEL CSV); add a batch/CSV mode in the next iteration.
- **No production hardening** — internal localhost tool. nginx/Docker/auth later (Margulies'
  ENVIRONMENT doc has the deployment notes when we need them).
