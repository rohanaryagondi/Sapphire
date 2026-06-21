#!/bin/bash
# Exhaustive Track-1 ranking on the 167-gene de-saturation panel (g5.xlarge A10G).
# Mixed deps: torch cu124 (>=2.6, for Ankh .bin) + transformers==4.48.1 (esm-SDK compat) + esm.
# Self-contained venv (DLAMI only for the driver). NON-COMMERCIAL where applicable. No mkfs/dd/rm.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== big_panel start: $(date -u) ==="
set +x  # SECURITY: never trace creds into the log
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
export HF_TOKEN="__HFTOK__"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="big_panel_run"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 6600; echo "WATCHDOG"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -2
$PY -m pip install -q "transformers==4.48.1" esm httpx numpy sentencepiece 2>&1 | tail -3
$PY -c "import torch,transformers,esm; print('torch',torch.__version__,'tf',transformers.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))" || fail "deps" 92

export HF_HOME=/opt/hf; mkdir -p /opt/hf
cd /opt
aws s3 cp "s3://$BUCKET/$PREFIX/big_panel_sweep.py" /opt/big_panel_sweep.py
aws s3 cp "s3://$BUCKET/$PREFIX/big_panel.json" /opt/big_panel.json
ls -la /opt/big_panel_sweep.py /opt/big_panel.json

echo "=== run start $(date -u) ==="
HF_TOKEN="$HF_TOKEN" HF_HOME=/opt/hf $PY /opt/big_panel_sweep.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
aws s3 cp /opt/big_panel_result.json "s3://$BUCKET/$PREFIX/big_panel_result.json" || true
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
