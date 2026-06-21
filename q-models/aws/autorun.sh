#!/usr/bin/env bash
# Autonomous finisher: wait for PGK2 -> eval both models -> write results -> SELF-TERMINATE.
# Runs detached in tmux; survives disconnection. Results persist on the 50GB volume.
exec > /mnt/rohan/mammal_ft/autorun.log 2>&1
set -x
# ALWAYS terminate on exit (shutdown==terminate per the launch flag) — no idle billing, ever.
trap 'echo AUTORUN_EXIT_SHUTDOWN; sudo shutdown -h now' EXIT

source /opt/pytorch/bin/activate
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1 HF_HOME=/mnt/rohan/mammal_ft/hf_cache
export TMPDIR=/mnt/rohan/mammal_ft/tmp CLEARML_CACHE_DIR=/mnt/rohan/mammal_ft/clearml_cache
W=/mnt/rohan/mammal_ft
cd "$W/biomed-multi-alignment"

# 1. wait for PGK2 training to finish (rc0 or rc1), max ~30 min
for i in $(seq 1 180); do
  grep -q TRAIN_DONE_pgk2 "$W/pgk2.log" 2>/dev/null && { echo "PGK2 finished: $(grep -o 'TRAIN_DONE_pgk2[^ ]*' $W/pgk2.log|tail -1)"; break; }
  sleep 10
done

# 2. eval BBBP on held-out scaffold test (correct ckpt = best_epoch-v1.ckpt; -v0 is the crashed run)
timeout 900 python "$W/eval_finetuned.py" bbbp "$W/runs/bbbp_ft" best_epoch-v1.ckpt || echo "BBBP_EVAL_FAILED"

# 3. eval PGK2 on held-out binders/non-binders (newest checkpoint in the fresh dir)
PCK=$(ls -t "$W"/runs/pgk2_ft/best_epoch*.ckpt 2>/dev/null | head -1)
if [ -n "$PCK" ]; then
  timeout 900 python "$W/eval_finetuned.py" pgk2 "$W/runs/pgk2_ft" "$(basename "$PCK")" || echo "PGK2_EVAL_FAILED"
else
  echo "PGK2_NO_CKPT"
fi

# 4. consolidated summary (persists on the volume)
{
  echo "=== MAMMAL public-data fine-tune pilot — results $(date -u) ==="
  echo "[BBBP train] $(grep -o 'TRAIN_DONE_bbbp[^ ]*' $W/bbbp.log | tail -1)  best_val_acc=$(grep -oE 'carcinogenicity_acc[^|]*\| [0-9.]+' $W/bbbp.log | grep -oE '[0-9.]+$' | sort -rn | head -1)"
  echo "[PGK2 train] $(grep -o 'TRAIN_DONE_pgk2[^ ]*' $W/pgk2.log | tail -1)  best_val_acc=$(grep -oE 'carcinogenicity_acc[^|]*\| [0-9.]+' $W/pgk2.log | grep -oE '[0-9.]+$' | sort -rn | head -1)"
  echo "[BBBP eval] $(cat $W/eval_bbbp.json 2>/dev/null | tr -d '\n')"
  echo "[PGK2 eval] $(cat $W/eval_pgk2.json 2>/dev/null | tr -d '\n')"
} > "$W/SUMMARY.txt"
cat "$W/SUMMARY.txt"
echo "AUTORUN_DONE"
# EXIT trap -> shutdown -> instance terminates; volume (DeleteOnTermination=false) persists with results
