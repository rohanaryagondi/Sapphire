# LigUnity (2025 ranking DTI FM) on the CNS panel — BANKED (model assembles, dataloader plumbing doesn't), 2026-06-15

Phase B of the overnight campaign. **LigUnity** (IDEA-XL, Patterns 2025; Apache-2.0) is a protein-ligand
foundation model tuned for virtual-screening + hit-to-lead RANKING — the scout's strongest net-new Track-2
candidate, and notably it has a **pocket-free `protein_ranking` checkpoint** (encodes the protein from
SEQUENCE via ESM2-35M, discards pocket tensors), so unlike DrugCLIP/AEV-PLIG it is NOT pose-gated — the
right input class (sequence + SMILES) for a clean head-to-head vs BALM/PLAPT on the at-chance ion channels.
**Outcome: banked — the model fully assembles, but wiring its unicore dataloader to score arbitrary
(sequence, SMILES) pairs needs more integration than the fix budget allows.** ~$1.0 across 4 short runs (all
self-terminated).

## How far it got (the model IS assembled)
A cascade of fixes got everything in place — this was NOT a model that "doesn't run":
1. **Run 1 — rc=92:** HF `git clone` fetched a git-LFS POINTER `.pt` (134 B) → unicore
   `load_checkpoint: invalid load key 'v'`. **Fix #1:** `huggingface_hub.snapshot_download` (real LFS binary).
2. **Run 2 — rc=92:** still 134 B — run-1's old code had cached the POINTER to S3, so the relaunch pulled
   the poisoned cache and skipped the fix. **Fix #2:** >1 MB guard on the S3-cache check + delete poisoned cache.
3. **Run 3 — rc=92:** ✅ real **984 MB checkpoint** loaded, unicore + CUDA + ESM2-35M all OK; new failure was
   an EVAL bug — `lmdb.open(subdir=False)` needed the parent dir pre-created. **Eval fix:** `mkdir(parents)` in
   `write_lmdb`.
4. **Run 4 (final) — rc=92:** ✅ checkpoint from cache, pocket-LMDB created; new failure
   **`RuntimeError: each element in list of batch should be of equal size`** in `score_target` — LigUnity's
   unicore `test_demo` dataloader needs its own **pad-collator** for the variable-size mol/pocket token
   tensors, and feeding it our (placeholder-pocket + ligand) batch with the default collate fails to stack.

## Why banked (the honest blocker)
LigUnity's weights, toolchain (Uni-Core/Uni-Mol cu118), and the pocket-free path are all confirmed working.
The remaining blocker is **replicating its exact batch/collate contract** (a unicore pad-collator over
variable-length Uni-Mol atom tensors) to score off-distribution (sequence, SMILES) pairs through its
`test_demo` path — a multi-step dataloader-integration task, not a one-line fix. That is past the
toolchain-fix budget for this campaign. Banked with the integration path documented.

## If revisited (the fix)
Use LigUnity's own `UnicoreDataset` + its `collater`/`Dictionary` pad-collator to build the batch (don't
hand-stack tensors): instantiate the task's dataset for the mol+pocket lmdbs and iterate via its DataLoader
with `collate_fn=dataset.collater`, so variable-size atom tensors are padded as unicore expects. Then the
already-loaded `protein_ranking` model will score. Everything upstream (checkpoint, deps, pocket-free path)
is solved and cached in S3.

## Scorecard impact
**None.** Track-2 winners unchanged (Boltz-2 + BALM triage + PLAPT). LigUnity filed as: **2025 ranking FM,
pocket-free path confirmed (a genuine advantage over pose-gated DrugCLIP/AEV-PLIG), model fully assembles,
but unicore dataloader-collate integration exceeds the fix budget — banked, revisitable via its own
collater.** The ion-channel DTI gap stays the fine-tune's to fill (see `aws/ionchannel_finetune_eval.py`).

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/ligunity/run.log` (4 runs: LFS pointer → poisoned
cache → pocket-lmdb → collate); eval `aws/ligunity_eval.py`; userdata `aws/ligunity_userdata.sh`; checkpoint
cached `s3://.../ligunity/protein_ranking_checkpoint.pt` (984 MB real binary); instances `i-0c1b08…`,
`i-0643836f…`, `i-0bf4c286…`, `i-0bb8964a…` all self-terminated.
