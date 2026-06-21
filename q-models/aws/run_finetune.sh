#!/usr/bin/env bash
# Fine-tune MAMMAL on one public dataset. Usage: run_finetune.sh {bbbp|pgk2}
# Efficient T4 use: fp16 AMP + batch 32. Reuses the carcinogenicity task scaffold;
# the dataset is selected by FT_DATASET (see patched pl_data_module.load_datasets).
set -uxo pipefail
source /opt/pytorch/bin/activate
export USE_TF=0 USE_FLAX=0 TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # reduce fragmentation on the 15GB T4
export HF_HOME=/mnt/rohan/mammal_ft/hf_cache
# keep ALL temp/cache writes on the 37GB volume, not the 40GB root (which filled & crashed BBBP)
export TMPDIR=/mnt/rohan/mammal_ft/tmp
export CLEARML_CACHE_DIR=/mnt/rohan/mammal_ft/clearml_cache
mkdir -p "$TMPDIR" "$CLEARML_CACHE_DIR"
export HF_HUB_DISABLE_XET=1              # xet backend hangs on this box; model is already cached
export CLEARML_OFFLINE_MODE=1            # belt: never phone home
DS="${1:?usage: run_finetune.sh bbbp-or-pgk2}"
export FT_DATASET="$DS"
if [ "$DS" = "pgk2" ]; then
  export PGK2_TRAIN=/mnt/rohan/mammal_ft/data/pgk2_binder_train.csv
  export PGK2_VAL=/mnt/rohan/mammal_ft/data/pgk2_binder_val.csv
fi

B=/mnt/rohan/mammal_ft/biomed-multi-alignment
CFG="$B/mammal/examples/carcinogenicity"
cd "$B"

START=$(date -u +%s)
echo "=== TRAIN START $DS @ $(date -u +%H:%M:%S)Z ==="
python -m mammal.main_finetune --config-path "$CFG" --config-name config \
  name="${DS}_ft" \
  root=/mnt/rohan/mammal_ft/runs \
  task.data_module_kwargs.batch_size=16 \
  task.data_module_kwargs.drug_max_seq_length=300 \
  task.data_module_kwargs.encoder_input_max_seq_len=320 \
  trainer.max_epochs=15 \
  +trainer.limit_val_batches=0.5 \
  +trainer.precision=16-mixed \
  track_clearml.offline_mode=True
RC=$?
END=$(date -u +%s)
echo "=== TRAIN END $DS rc=$RC elapsed=$(( END - START ))s ==="
echo "TRAIN_DONE_${DS}_rc${RC}_secs$(( END - START ))"
