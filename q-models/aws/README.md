# aws/ — in-house fine-tune pipeline (AWS g4dn)

Everything used to fine-tune MAMMAL on a cloud T4 GPU. Full writeup + results + gotchas:
[`../results/aws_finetune_pilot.md`](../results/aws_finetune_pilot.md). Retrieval of the trained
checkpoints/results from the persistent volume: [`RETRIEVE.md`](RETRIEVE.md).

## Files

| File | What it does |
|---|---|
| `build_pgk2_dataset.py` | Builds the PGK2 binder train/val CSVs (DEL hits vs PGK1 homolog ligands + decoys) from `../data/`. Run locally. Output → `data/pgk2_binder_{train,val}.csv`. |
| `setup.sh` | On-instance: clone `biomed-multi-alignment`, pip-install into the DLAMI `/opt/pytorch` venv, cache the 458M base model to the volume. |
| `pl_data_module_patched.py` | Drop-in replacement for `mammal/examples/carcinogenicity/pl_data_module.py`. Adds `FT_DATASET` selection (`bbbp` → TDC BBB_Martins scaffold split; `pgk2` → local CSVs) and `num_workers=4` (the GPU-starvation fix). |
| `run_finetune.sh` | One fine-tune: `run_finetune.sh {bbbp|pgk2}`. Efficient T4 config (fp16 AMP, batch 16, limit_val_batches 0.5), all temp/cache redirected to the volume. |
| `run_both.sh` | Run BBBP then PGK2 back-to-back. |
| `eval_finetuned.py` | Held-out AUROC + enrichment via the generative P(`<1>`) readout. **KNOWN ISSUE:** the hand-rolled `bd[SCORES]` extraction is fragile and silently degrades to a constant if the env is wrong — re-do with `CarcinogenicityTask.process_model_output` (see `main_infer.py`), and run it on a GPU with the full `mammal` env. |
| `autorun.sh` | Autonomous finisher: wait for training → run both evals (timeouts) → write `SUMMARY.txt` → **self-terminate** (EXIT trap → `shutdown` → terminate). |
| `data/pgk2_binder_{train,val}.csv` | The PGK2 pilot dataset (committed; regenerate with `build_pgk2_dataset.py`). |
| `RETRIEVE.md` | How to read results off the persistent volume after the instance terminated. |
| `.launch_vars`, `*.pem`, `userdata.sh` | Transients/secrets — **gitignored**. |

## Reproduce (fresh g4dn.xlarge in us-east-1b)

```bash
# 0. local: build the PGK2 dataset
/opt/anaconda3/envs/mammal/bin/python build_pgk2_dataset.py     # (or any python w/ rdkit not even needed)

# 1. launch g4dn.xlarge (DLAMI PyTorch), attach the 50GB data volume vol-066389517f2740f19,
#    create a keypair + SG (SSH from your IP), instance-initiated-shutdown-behavior=terminate.
#    (See ../results/aws_finetune_pilot.md §7 and the AWS CLI calls in the session history.)

# 2. on the instance: mount the volume at /mnt/rohan, then
bash setup.sh                                  # clone + install + cache model (set HF_HUB_DISABLE_XET=1)
cp pl_data_module_patched.py \
   biomed-multi-alignment/mammal/examples/carcinogenicity/pl_data_module.py
bash run_finetune.sh bbbp                       # or run_both.sh
bash run_finetune.sh pgk2

# 3. eval (ON A GPU, full env) — after fixing the readout to process_model_output:
python eval_finetuned.py bbbp runs/bbbp_ft best_epoch-v1.ckpt   # note the -v1 (stale-ckpt gotcha)
python eval_finetuned.py pgk2 runs/pgk2_ft best_epoch.ckpt

# 4. ALWAYS terminate the instance when done (the 50GB volume persists with results).
```

## Hard-won env fixes (baked into the scripts — see pilot writeup §6 for why)

```bash
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1
export HF_HOME=/mnt/rohan/mammal_ft/hf_cache TMPDIR=/mnt/rohan/mammal_ft/tmp \
       CLEARML_CACHE_DIR=/mnt/rohan/mammal_ft/clearml_cache   # keep heavy writes OFF the 40GB root
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
pip install -U "scikit-learn>=1.4" "setuptools<81"            # fuse needs new sklearn; PyTDC needs pkg_resources
pip uninstall -y tensorflow keras tensorboard                 # unused, frees ~2GB of root
# dataloaders MUST use num_workers>0 (else GPU starves at 0% in D-state) — in the patched data module
```

## Cost / safety

- One full pilot (2 fine-tunes + first-time debugging): **~$0.80** on g4dn.xlarge on-demand. Repeat with
  cached env: < $0.30.
- Instances launched with `InstanceInitiatedShutdownBehavior=terminate` + a 7 h `shutdown` kill-switch in
  UserData → they cannot run away. `autorun.sh` self-terminates after evals.
- **Shared company AWS account** (account 255493511886) — other people's instances run here (e.g. Matt's
  `oEP` g4dn). Only ever touch your own tagged resources (`Owner=Rohan, Project=MAMMAL`).
