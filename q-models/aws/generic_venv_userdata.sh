#!/bin/bash
# Generic self-contained-venv GPU job (DLAMI for the driver; our own venv+pip torch for reliability).
# Per-job vars injected by sed: __PREFIX__ __SCRIPT__ __DATA__ (comma-sep s3 keys) __EXTRAPIP__ __ARGS__
# NON-COMMERCIAL RESEARCH where applicable. No mkfs/dd/rm of existing data.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== job start: $(date -u) ==="
set +x  # SECURITY: never trace the credential block into the log
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
export HF_TOKEN="__HFTOK__"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"
PREFIX="__PREFIX__"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
# SECURITY: redact stray secrets before uploading the log to S3 (defense in depth)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/job.redacted.log 2>/dev/null; aws s3 cp /tmp/job.redacted.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 6000; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -2
$PY -m pip install -q "transformers>=4.45" accelerate "huggingface_hub>=0.24" numpy scikit-learn sentencepiece __EXTRAPIP__ 2>&1 | tail -3
$PY -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))" || fail "torch-cuda" 92

export HF_HOME=/opt/hf; mkdir -p /opt/hf
cd /opt
aws s3 cp "s3://$BUCKET/$PREFIX/__SCRIPT__" /opt/__SCRIPT__
IFS=',' read -ra FILES <<< "__DATA__"
for f in "${FILES[@]}"; do [ -n "$f" ] && aws s3 cp "s3://$BUCKET/shared/$f" "/opt/$f"; done
ls -la /opt/*.py /opt/*.json 2>&1

echo "=== run start $(date -u) ==="
HF_TOKEN="$HF_TOKEN" HF_HOME=/opt/hf $PY /opt/__SCRIPT__ __ARGS__
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
for r in /opt/*_result*.json /opt/result.json; do [ -f "$r" ] && aws s3 cp "$r" "s3://$BUCKET/$PREFIX/$(basename $r)"; done
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
