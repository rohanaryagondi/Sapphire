#!/bin/bash
# Nav/Cav VARIANT-EFFECT FINE-TUNE: train a supervised GoF-vs-LoF classifier on the pooled
# SCION + funNCion Nav/Cav missense corpus on top of ESM-2-650M features (masked-marginal LLR
# + WT/MUT per-residue embeddings), and test (1) leave-one-GENE-out family generalization vs
# the generic ESM-2 LLR baseline (~0.665) and funNCion (0.897), and (2) cross-channel TRANSFER
# to held-out Nav1.8/SCN10A (the 16 SCION SCN10A variants). Self-contained /opt/venv via EXPLICIT
# python (conda-activate fails in DLAMI userdata). Instance: g5.xlarge.
# TOOLCHAIN:
#   torch>=2.6 cu121  -- transformers torch.load gate (CVE-2025-32434) for the ESM-2 HF checkpoint.
#   transformers      -- ESM-2-650M (facebook/esm2_t33_650M_UR50D) masked-LM + hidden states.
#   scikit-learn      -- GradientBoostingClassifier + GroupKFold (leave-one-gene-out) + scaler.
#   numpy<2, requests -- ABI safety + UniProt REST WT-sequence fetch (with socket timeout).
# DATA (launcher stages to s3://$BUCKET/$PREFIX/): scion clean_tbl.csv + funNCion S1 labels.
# No model-repo clone (ESM-2 is a HF download). No mkfs/dd/rm of existing data.
# Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== variant_finetune start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="variant_finetune"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# ~3.1k variants x ESM-2 (mask pass + WT-emb pass + MUT-emb pass) + GBT GroupKFold + held-out -> ~4000s watchdog.
( sleep 4000; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; python3-venv (meta) alone did NOT
# pull it on a prior run, so `python3 -m venv` came up WITHOUT pip -> No module named pip/numpy
# cascade. Install python3.10-venv on its OWN line; ensurepip + the pip-version guard below are
# MANDATORY (this is what a prior failing run was missing).
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (ABI safety). torch>=2.6 cu121 (transformers torch.load gate for the ESM-2 HF checkpoint).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1
# ESM-2 encoder stack + sklearn for the supervised classifier/CV.
$PY -m pip install -q "transformers>=4.45" "huggingface_hub>=0.24" accelerate safetensors \
    scikit-learn scipy pandas tqdm requests 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: ESM-2 deps + sklearn classifier/CV must import.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, safetensors, sklearn, scipy, requests
from transformers import AutoModelForMaskedLM, AutoTokenizer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "sklearn", sklearn.__version__,
      "cuda", torch.cuda.is_available())
assert numpy.__version__.startswith("1."), "numpy must be <2 for ABI safety"
PYCHK

# Stage the eval + the two variant tables from S3 (launcher uploads them to s3://$BUCKET/$PREFIX/).
mkdir -p /opt/data
aws s3 cp "s3://$BUCKET/$PREFIX/variant_finetune_eval.py" /opt/variant_finetune_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/scion_clean_tbl.csv" /opt/data/scion_clean_tbl.csv || fail "dl-scion" 95
aws s3 cp "s3://$BUCKET/$PREFIX/funncion_S1_pathogenic_GoF_LoF_labels.txt" /opt/data/funncion_S1_pathogenic_GoF_LoF_labels.txt || fail "dl-funncion" 95

echo "=== run variant_finetune $(date -u) ==="
export USE_TF=0 USE_FLAX=0
export SCION_CSV=/opt/data/scion_clean_tbl.csv
export FUNNCION_TSV=/opt/data/funncion_S1_pathogenic_GoF_LoF_labels.txt
OUT=/root/variant_finetune_out/variant_finetune_result.json $PY /opt/variant_finetune_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/variant_finetune_out/variant_finetune_result.json ] && \
  aws s3 cp /root/variant_finetune_out/variant_finetune_result.json "s3://$BUCKET/$PREFIX/variant_finetune_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
