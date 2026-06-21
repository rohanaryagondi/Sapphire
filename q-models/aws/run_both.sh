#!/usr/bin/env bash
# Run both public-data fine-tunes back-to-back, full runs. Markers + per-job logs.
cd /mnt/rohan/mammal_ft
rm -f ALL_DONE
echo "=== BBBP @ $(date -u +%H:%M:%S)Z ==="
bash run_finetune.sh bbbp > bbbp.log 2>&1
echo "=== PGK2 @ $(date -u +%H:%M:%S)Z ==="
bash run_finetune.sh pgk2 > pgk2.log 2>&1
touch ALL_DONE
echo "=== BOTH DONE @ $(date -u +%H:%M:%S)Z ==="
