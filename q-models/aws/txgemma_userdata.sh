#!/bin/bash
# TxGemma-9B-predict eval on g5.xlarge (A10G 24GB). NON-COMMERCIAL RESEARCH.
# SELF-CONTAINED python: build our own venv + pip-install CUDA torch, instead of hunting for
# the DLAMI's conda (which is interactive-only / appears late on slow instances -> rc=126/127).
# The DLAMI still gives us the NVIDIA driver, which is the part that's hard to install. No mkfs/dd/rm.
exec > >(tee -a /var/log/tx-run.log) 2>&1
echo "=== txgemma userdata start: $(date -u) ==="
set +x  # SECURITY: never trace the credential block into the log
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
export HF_TOKEN="__HFTOK__"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"
PREFIX="txgemma_run"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { aws s3 cp /var/log/tx-run.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAILED: $1"; echo "rc=$2 iid=$IID note=$1 done=$(date -u)" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 6000; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

# confirm GPU driver present (this is what the DLAMI buys us)
nvidia-smi || fail "no nvidia driver" 90

# self-contained venv from system python3
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
apt-get install -y python3-venv python3-pip >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv create" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
echo "=== installing torch (cu121) + transformers $(date -u) ==="
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -3
$PY -m pip install -q "transformers>=4.45" accelerate "huggingface_hub>=0.24" numpy 2>&1 | tail -3
$PY -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))" || fail "torch cuda check" 92

# HF cache on the big root disk
export HF_HOME=/opt/hf; mkdir -p /opt/hf

cd /opt
aws s3 cp "s3://$BUCKET/$PREFIX/txgemma_eval.py" /opt/txgemma_eval.py
aws s3 cp "s3://$BUCKET/$PREFIX/txgemma_panels.json" /opt/txgemma_panels.json
ls -la /opt/txgemma_eval.py /opt/txgemma_panels.json

echo "=== run start $(date -u) ==="
HF_TOKEN="$HF_TOKEN" HF_HOME=/opt/hf $PY /opt/txgemma_eval.py /opt/txgemma_panels.json /opt
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
aws s3 cp /opt/txgemma_results.json "s3://$BUCKET/$PREFIX/txgemma_results.json" || true
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
