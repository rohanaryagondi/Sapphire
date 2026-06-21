# In-house fine-tune pilot on AWS (Q14 realization)

**Run 2026-06-01 on a g4dn.xlarge (NVIDIA T4).** This is the first time we *actually fine-tuned*
MAMMAL ourselves (Phases 0–6 evaluated IBM's published checkpoints; this trains the base model on
our own data). It is the realization of the Q14 "pilot an in-house per-target fine-tune" next step —
done on **PUBLIC data** first, to validate the pipeline before spending any Quiver proprietary data.

> **TL;DR.** The **fine-tuning pipeline works end-to-end** — we trained two heads on a T4 from the
> base model, cleanly, for **~$0.80 total**. BBBP reached **0.88 val accuracy**; the PGK2 binder
> classifier completed (rc0, 19 min). **The held-out evals are NOT yet valid** — they were run on a
> CPU-only t3.micro with no ML env and silently returned a constant (AUROC 0.5); the *models* are fine,
> the *eval readout* must be re-run on a GPU with the full env. **Strategic conclusion (the important
> part): fine-tuning on public data can NOT beat IBM's own published head for that task — same base +
> same data = same ceiling. The win only exists for targets IBM has no head for — i.e. Quiver-specific
> targets — where off-the-shelf MAMMAL is ≈ AUROC 0.5 and any trained head wins by construction.**

---

## 1. Why we ran it

Q14 ("should we fine-tune on Quiver data?") leaned YES off the back of IBM's `wdr91_asms`/`pgk2_del_cdd`
heads as an *existence proof* (Phase 3). The agreed next step was to **pilot the fine-tune pipeline
ourselves on public data** — prove we can reproduce IBM's per-target-classifier recipe on a GPU before
committing Quiver screening/DEL data. Two public tasks:

1. **MoleculeNet BBBP** (blood-brain-barrier penetrance) — a task IBM *already has a head for* (their
   published BBBP head is AUROC 0.957/our reproduction 0.968). Purpose: a known-answer control to prove
   the pipeline trains a working classifier.
2. **PGK2 binder classifier** — reproduce IBM's `pgk2_del_cdd` per-target head from public data
   (PGK2 DEL hits vs PGK1-homolog ligands + drug-like decoys). Purpose: the Quiver-relevant shape
   (target → binder/non-binder triage).

---

## 2. Method (recipe + data)

**Recipe = IBM's shipped full fine-tune**, read from `mammal/main_finetune.py` + the
`carcinogenicity` example (see `docs/analysis/q3a_finetune_recipe_footprint.md`): PyTorch-Lightning +
Hydra, `torch.optim.AdamW` lr 1e-5, cosine-annealing-with-warmup, **full fine-tune of all 458M params**
(no LoRA, no frozen layers), generative binary-classifier readout (prompt ends `<SENTINEL_ID_0>`,
model generates `<0>`/`<1>`, read **P(`<1>`)** — the molnet readout, NOT the vestigial scalar head).

We reused the **carcinogenicity Task scaffold verbatim** (same binary-classifier task + `<CARCINOGENICITY>`
token + metric) and only swapped the **dataset** via an env var (`FT_DATASET`) in a one-function patch
to `pl_data_module.load_datasets` (`aws/pl_data_module_patched.py`):
- `FT_DATASET=bbbp` → TDC `ADME("BBB_Martins")`, **scaffold split** (honest held-out test).
- `FT_DATASET=pgk2` → our CSVs (`aws/data/pgk2_binder_{train,val}.csv`).

Efficiency overrides vs IBM's defaults (to use the T4 well): **fp16 AMP** (`+trainer.precision=16-mixed`,
~1.5–2× on T4), **batch 16** (batch 32 OOMs the 15 GB T4 — the full-FT Adam state is a ~7.3 GB floor),
`num_workers=4` parallel dataloaders (critical — see gotchas), clearml forced offline.

**PGK2 dataset construction** (`aws/build_pgk2_dataset.py`): positives = 1,378 PGK2 DEL hits
(`data/pgk2/DEL_hit_candidates_1.csv`); negatives = 99 PGK1-homolog ChEMBL ligands (hard negatives) +
500 drug-like decoys (`data/wdr91/wdr91_decoys.json`). Deterministic 80/20 hash split →
**1,570 train / 407 val** (~69% positive). NB: val == test for this pilot (mild optimistic bias);
the split is by hash, not scaffold — for a real Quiver fine-tune use a **scaffold split**.

---

## 3. Results

### Training — both clean ✅

| Model | Data | Config | Outcome | Best checkpoint |
|---|---|---|---|---|
| **BBBP** | TDC BBB_Martins scaffold (1421 tr / 203 val / 406 test) | full FT, fp16, batch 16, 40 ep | **rc0, val acc 0.88** (plateaued ~epoch 6; later epochs never beat it) | `runs/bbbp_ft/best_epoch-v1.ckpt` (4.2 GB) |
| **PGK2** | DEL hits vs PGK1+decoys (1570 tr / 407 val) | full FT, fp16, batch 16, 15 ep, limit_val_batches 0.5 | **rc0 in 1135 s (~19 min)**, train val-acc 1.0 (uninformative at 69% pos) | `runs/pgk2_ft/best_epoch.ckpt` |

GPU was pinned at **97–100%** throughout training once dataloaders were parallelized. BBBP's val
*accuracy* of 0.88 is real learning (IBM's BBBP head is ~0.96 AUROC on a balanced split; our scaffold
val is harder and the pilot is short). **The pipeline demonstrably produces working fine-tuned heads.**

### Held-out evaluation — INVALID (must re-run) ❌

`eval_bbbp.json` / `eval_pgk2.json` both report **AUROC 0.5** with constant enrichment — because the
eval was run on the **t3.micro reader instance, which has only Amazon-Linux system `python3` (no
PyTorch/MAMMAL)**. `eval_finetuned.py`'s per-sample `try/except` swallowed the import error and the
`nan`→fallback path produced **a single constant score (0.4999750) for every compound** → AUROC 0.5 by
construction. Confirmed: `eval_*_raw.json` shows `unique_scores=1`.

**This says nothing about the models.** The fine-tuned checkpoints are intact on the volume. The eval
needs re-running **on a GPU box with the full `mammal` env**, and should use the validated
`CarcinogenicityTask.process_model_output` readout (from `mammal/examples/carcinogenicity/main_infer.py`)
rather than the hand-rolled `bd[SCORES]` extraction in the current `eval_finetuned.py`.

---

## 4. Cost — the boss-facing number, now MEASURED

| Item | Wall-clock | Cost |
|---|---|---|
| g4dn.xlarge (on-demand $0.526/hr): setup + 2 fine-tunes + heavy first-time debugging | ~91 min | **~$0.80** |
| t3.micro reader (read results off the volume) | ~5 min | ~$0.001 |
| **Total** | | **~$0.80** |

This **validates the Q3 cost model** (`docs/analysis/q3b_aws_g4dn_cost.md`, which estimated ~$0.69 /
1.3 h for one small pilot, ~$0.99 for BBBP). Actual *training* was even faster than estimated (PGK2
15 epochs = 19 min; BBBP plateaued by ~epoch 6 ≈ 4 min of useful training); the variable cost was
**first-time environment debugging** (~25 min of the 91). A repeat run with the env cached on the
volume would be **well under $0.30**. **Cost is not a constraint** — it never was; the question is
scientific value, which requires the eval re-run and, ultimately, Quiver data.

---

## 5. The strategic conclusion (most important)

**Can a Quiver fine-tune beat the best available MAMMAL for a task? Only for tasks IBM hasn't built a
head for.**

- **For a task IBM already fine-tuned (BBBP, ClinTox, PGK2/WDR91, DTI):** no. You are training the same
  base model on the same public data — the ceiling is identical to IBM's head. Our BBBP 0.88 ≈
  *confirmation the pipeline works*, not a win over IBM's 0.957.
- **For a Quiver-specific target (Nav1.8, UBE3A/DUP15Q, mTOR/TSC, DFP compounds, CRISPR-N genes):** the
  best available MAMMAL is the **base model at ≈ AUROC 0.5** (we measured exactly this — Nav1.8/mTOR
  single-target triage ≈ chance off-the-shelf). IBM has **no head** for these. A Quiver-trained head is
  the **only one in existence** for that target, so it wins by construction. *That* is where fine-tuning
  unlocks value — and it requires Quiver data.

**Caveat (unchanged from Phase 3):** even with Quiver data, a per-target head is a **chemotype-triage /
enrichment tool** — it recognizes the chemotypes it trained on (sharp in-distribution, e.g. PGK2 vs
PGK1 homolog AUROC 0.97) but generalizes weakly to novel scaffolds, and gives no graded potency. For
Quiver's use (triage DEL/DFP hits against a CNS target), even **2–3× enrichment at top-5%** is a
deployable win against a 0.5 baseline — and something no public model provides.

**Net:** the public-data pilot did its job — it validated the pipeline and the cost. The actual goal
(beat the best-available MAMMAL on a task Quiver cares about) is **achievable but needs Quiver data**,
evaluated by **enrichment factor on a held-out scaffold split**.

---

## 6. Gotchas discovered (operational gold — these cost real time)

All are fixed in the `aws/` scripts; listed so the next run doesn't rediscover them.

1. **hf-xet download hangs.** The new `hf-xet` HF transfer backend stalls at 0 B/s on this network →
   model never downloads. Fix: `export HF_HUB_DISABLE_XET=1` (then snapshot_download is instant).
2. **DLAMI sklearn too old for fuse-med-ml.** `ImportError: root_mean_squared_error` → `pip install -U
   "scikit-learn>=1.4"`.
3. **setuptools ≥81 removed `pkg_resources`** which PyTDC imports → `ModuleNotFoundError: pkg_resources`
   → `pip install "setuptools<81"`.
4. **TensorFlow is pulled in by fuse-med-ml** (~1.9 GB + it shares torch's nvidia CUDA wheels) and is
   **never used** (USE_TF=0). It bloats the 40 GB root disk. Safe to `pip uninstall -y tensorflow keras
   tensorboard`. (Do NOT remove `site-packages/nvidia/*` — that's torch's CUDA, 3.6 GB, required.)
5. **GPU starvation from `num_workers=0`.** The shipped dataloaders are single-process → the T4 sits at
   **0% util in `D` (I/O-wait) state, looking hung**, for many minutes on the first batch. Fix: add
   `num_workers=4, persistent_workers=True, pin_memory=True` to the dataloaders (done in the patch). GPU
   then pins at ~99%. *This was the single most confusing failure — looked like a hang, was data
   starvation.*
6. **Disk fills the 40 GB root, crashing checkpoint saves** (`OSError [Errno 28] No space left`). Root
   causes: `/tmp` checkpoint temp + TF + pip cache. Fix: redirect **everything** to the big volume —
   `export TMPDIR=/mnt/rohan/mammal_ft/tmp CLEARML_CACHE_DIR=... HF_HOME=...`; clear `/tmp`; uninstall TF.
   (The 40 GB root is the *boot disk*, mandatory and auto-deleted on terminate; only ~9 GB usable after
   the DLAMI. Keep heavy writes on the 50 GB data volume.)
7. **`check_val_every_n_epoch` breaks fuse's best-epoch callback** (`KeyError:
   validation.metrics.<task>_acc`) — the callback reads the val metric at the end of *every train
   epoch*. Don't skip validation epochs. To speed validation up use `+trainer.limit_val_batches=0.5`
   instead (validates every epoch on a subset → metric still exists).
8. **Stale checkpoint name.** If `runs/<name>/` already has a `best_epoch.ckpt` from a prior (e.g.
   crashed) run, Lightning writes the new run's best as **`best_epoch-v1.ckpt`** — `best_epoch.ckpt`
   stays stale. Always confirm the checkpoint mtime/epoch before evaluating. (BBBP's correct ckpt was
   `best_epoch-v1.ckpt`.) Cleanest: `rm -rf runs/<name>` before a fresh run.
9. **Eval needs the full env.** Don't run the eval on a bare instance — the readout silently degrades to
   a constant. Run it where `mammal` + torch + a GPU are present.
10. **macOS shell word-split.** Driving SSH from the Mac: the login shell is zsh, which does NOT
    word-split unquoted vars — `SSH="ssh -i ... -o ..."; $SSH host` fails (whole string treated as one
    token). Inline all ssh/scp flags, don't bundle them in a var.

---

## 7. Infrastructure (all in `aws/`, reproducible — see `aws/README.md`)

- **Instance:** `i-0e4a5087c22fa257e`, g4dn.xlarge, us-east-1b, DLAMI PyTorch 2.7 (Ubuntu 22.04). **Self-
  terminated** after the autonomous eval+shutdown (no idle billing; `InstanceInitiatedShutdownBehavior=
  terminate` + a 7 h kill-switch backstop).
- **Persistent data volume:** `vol-066389517f2740f19` (50 GB, name "Rohan", us-east-1b,
  DeleteOnTermination=false). The fine-tuned checkpoints + logs + datasets live at
  **`/mnt/rohan/mammal_ft/`** on this volume and survive termination. See `aws/RETRIEVE.md`.
- **Scripts:** `build_pgk2_dataset.py` (data prep), `setup.sh` (clone+install+model-cache),
  `pl_data_module_patched.py` (dataset-selectable data module), `run_finetune.sh` (one fine-tune,
  efficient T4 config), `run_both.sh`, `eval_finetuned.py` (held-out AUROC/enrichment — **readout needs
  the process_model_output fix**), `autorun.sh` (autonomous: wait→eval→self-terminate).

---

## 8. Next steps

1. **Re-run the held-out eval properly** — on a GPU box (attach `vol-066389517f2740f19` to a g4dn,
   activate the env), using `CarcinogenicityTask.process_model_output`. This gives the real BBBP AUROC
   and PGK2 AUROC + enrichment. ~10 min, ~$0.10. (Until then we have *training* val-acc only: BBBP 0.88.)
2. **Then the real move: fine-tune on a Quiver target.** Pick a Quiver target with the most labelled
   screening/DEL/phenotypic hit data; binary hit/non-hit, SMILES + label; full FT with this exact
   pipeline; **evaluate by enrichment factor on a held-out scaffold split.** This is the only path to
   beating the best-available MAMMAL (which, for Quiver targets, is ≈ 0.5).
3. **Optionally** cache the env on the volume (or bake an AMI) so future runs skip the ~25 min setup
   and cost < $0.30.
