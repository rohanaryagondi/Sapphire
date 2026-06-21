# CToxPred2 (ion-channel-trained cardiac tox) — BANKED at the 2-fix cap (weight-packaging won't assemble), 2026-06-15

Phase B of the overnight campaign. **CToxPred2** (issararab, JCIM 2024) is the only verified-downloadable
model explicitly **trained on ion-channel blockade** — a multitask hERG / Nav1.5 / Cav1.2 classifier
(ligand-only SMILES → per-channel block probability). Plan: score its hERG head on the SAME TDC hERG_Karim
protocol as our Track-5 winner (MapLight 0.889 / FP-XGBoost 0.890), plus a Nav1.5/Cav1.2 ChEMBL bonus.
**Outcome: banked — the repo's weight packaging would not assemble within the ≤2-fix cap.** ~$0.3 across 3
short runs (all self-terminated).

## Why banked (2 fixes used, weights still truncated)
1. **Run 1 — rc=92, unpickle:** `AttributeError: Can't get attribute 'CorrelationThreshold' on __main__`.
   The repo's saved sklearn pipelines reference a custom selector class pickled from `__main__`.
   **Fix #1 (correct):** import `CorrelationThreshold` from `CToxPred2/pairwise_correlation.py` into
   `__main__` before `joblib.load`. This worked — run 2 got *past* the unpickle to actually reading the
   weight arrays.
2. **Runs 2 & 3 — rc=92, truncated weights:** the model weights ship **as `.rar` archives stored via
   git-LFS**. The shallow `git clone` fetched ~130-byte LFS *pointer* stubs, so `unar` reported
   "Extraction failed (4 files failed / 1 file failed)" and the resulting files were truncated →
   `ValueError: EOF reading array data, expected 21184 bytes got 7184` (the RF `.npy`) and
   `RuntimeError: PytorchStreamReader failed finding central directory` (the DL `.pt` zip).
   **Fix #2:** added `git-lfs` + `git lfs pull`. This populated the directory tree (hERG/Nav1.5/Cav1.2
   subdirs appeared), but `unar` **still partially fails on the `.rar` archives** — i.e. even with the real
   LFS blobs, `unar` cannot fully extract them (likely a RAR5/format quirk unar mishandles), leaving the
   same truncated weights. **Cap reached.**

## Why this is the right call
The model *concept* is sound and the eval (CorrelationThreshold fix + TDC protocol + ChEMBL bonus) is
correct — the blocker is purely the upstream **`.rar`-via-git-LFS weight packaging**, which is an unusually
fragile distribution choice (most repos ship `.joblib`/`.pt` directly or via HF). Fixing it would need a
3rd toolchain fix (e.g. a different RAR extractor like `unrar`/`7z`, or fetching the `.rar` via the GitHub
LFS media API and verifying byte counts before extraction) — past the ≤2-fix budget, for a LOW-MED-priority
model (cardiac Nav1.5/Cav1.2, ligand-only — not CNS-channel target-conditioned DTI, and our hERG gate is
already strong at MapLight 0.89).

## Scorecard impact
**None.** Track 5 winner unchanged (MapLight / Morgan-FP+XGBoost hERG 0.89 + ADMET-AI/ChemBERTa-2 DILI).
CToxPred2 filed as: **ion-channel-trained, eval-correct, but weight-packaging (`.rar`-via-LFS + unar partial
extraction) won't assemble in ≤2 fixes — banked.** The multi-channel cardiac *idea* (NaV1.5/CaV1.2 heads our
single hERG gate lacks) remains worth building on Quiver's own FP+GBT recipe if a cardiac-panel need arises
(same conclusion as CardioGenAI).

## If revisited (the 3rd fix)
Swap `unar` for `7z`/`unrar`, or pull each `.rar` via the GitHub LFS media API
(`https://github.com/issararab/CToxPred2/raw/<sha>/...`) and assert each archive is >1 KB (not a pointer)
before extraction; verify the extracted `.joblib`/`.pt` byte counts match before predicting.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/ctoxpred2/run.log` (3 runs: unpickle → 2×
truncated-weights); eval `aws/ctoxpred2_eval.py` (CorrelationThreshold fix landed); userdata
`aws/ctoxpred2_userdata.sh` (git-lfs added); instances `i-0054406c…`, `i-0758f0f1…`, `i-098ceddec…` all
self-terminated.
