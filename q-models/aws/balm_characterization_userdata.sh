#!/bin/bash
# BALM deep characterization (overnight Phase 1). Self-contained venv. PROVEN BALM toolchain
# (torch>=2.6 cu124 for ChemBERTa .bin + pydantic). Adds rdkit+scipy for AD/calibration. NON-COMMERCIAL
# RESEARCH. No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== balm characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="balm_char"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
# torch>=2.6 cu124 REQUIRED (ChemBERTa-77M-MTR ships .bin; transformers blocks torch.load <2.6).
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
$PY -m pip install -q "transformers>=4.45" peft "huggingface_hub>=0.24" accelerate \
    scikit-learn scipy "numpy<2" pyyaml sentencepiece pandas pytdc pydantic safetensors "rdkit==2022.9.5" 2>&1 | tail -3
$PY -c "import torch,transformers,peft,sklearn,scipy,rdkit,pydantic; from rdkit.Chem import AllChem; print('deps ok; cuda', torch.cuda.is_available())" || fail "deps" 92

git clone --depth 1 https://github.com/meyresearch/BALM /opt/BALM 2>&1 | tail -2 || fail "clone" 93
aws s3 cp "s3://$BUCKET/$PREFIX/balm_characterization.py" /opt/balm_characterization.py || fail "dl-eval" 94
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 95

echo "=== run BALM characterization $(date -u) ==="
PANELS=/opt/crossmodal_panels.json OUT=/root/balm_out/balm_characterization_result.json \
  BALM_DIR=/opt/BALM $PY /opt/balm_characterization.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/balm_out/balm_characterization_result.json ] && \
  aws s3 cp /root/balm_out/balm_characterization_result.json "s3://$BUCKET/$PREFIX/balm_characterization_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
