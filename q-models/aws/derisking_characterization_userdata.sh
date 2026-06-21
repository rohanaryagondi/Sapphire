#!/bin/bash
# De-risking deep characterization (overnight Phase 2). Self-contained venv. PROVEN toolchain
# (MolFormer-XL + ChemBERTa-2 + ADMET-AI; mostly CPU/fast). torch>=2.6 cu124 (MolFormer/ChemBERTa
# ship .bin checkpoints -> transformers blocks torch.load on torch<2.6). transformers PINNED 4.48.1:
# MolFormer-XL's trust_remote_code modeling file breaks on newer transformers (rotary/attention API
# drift) — 4.48.1 is the known-good pin. numpy<2 for rdkit==2022.9.5 C-ext ABI. NON-COMMERCIAL
# RESEARCH. No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== derisking characterization start: $(date -u) ==="
set +x  # SECURITY: do not echo creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="derisking_char"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no nvidia-smi (CPU fallback ok for this job)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
# torch>=2.6 cu124 REQUIRED (MolFormer-XL / ChemBERTa-77M ship .bin; transformers blocks torch.load <2.6).
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
# transformers PINNED to 4.48.1 (MolFormer-XL trust_remote_code modeling needs it) + protobuf for tok.
$PY -m pip install -q "transformers==4.48.1" protobuf "huggingface_hub>=0.24" accelerate \
    scikit-learn scipy "numpy<2" pyyaml sentencepiece pandas xgboost pytdc "rdkit==2022.9.5" safetensors 2>&1 | tail -3
# ADMET-AI best-effort (cross-check only; allowed to fail without sinking the job).
$PY -m pip install -q "admet-ai" 2>&1 | tail -2 || echo "[warn] admet-ai install failed; eval will skip it"
$PY -c "import torch,transformers,sklearn,scipy,rdkit,xgboost,tdc; from rdkit.Chem import AllChem; print('deps ok; transformers', transformers.__version__, 'cuda', torch.cuda.is_available())" || fail "deps" 92

aws s3 cp "s3://$BUCKET/$PREFIX/derisking_characterization.py" /opt/derisking_characterization.py || fail "dl-eval" 94

echo "=== run derisking characterization $(date -u) ==="
OUT=/root/derisking_out/derisking_characterization_result.json $PY /opt/derisking_characterization.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/derisking_out/derisking_characterization_result.json ] && \
  aws s3 cp /root/derisking_out/derisking_characterization_result.json "s3://$BUCKET/$PREFIX/derisking_characterization_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
