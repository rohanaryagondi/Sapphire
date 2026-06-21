#!/bin/bash
# Track-2 thoroughness: two UNTESTED public DTI models (PLAPT + DeepPurpose MPNN_CNN_BindingDB_IC50)
# on the Quiver Nav1.8 + mTOR binder/decoy panels. Both run from protein SEQUENCE + ligand SMILES
# (no 3D structure). Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
# TOOLCHAIN: torch>=2.6 cu124 (transformers blocks torch.load <2.6 for ProtBERT/ChemBERTa .bin) +
#   transformers + onnxruntime-gpu (PLAPT affinity head is models/affinity_predictor.onnx) +
#   rdkit==2022.9.5 + numpy<2 (rdkit C-ext ABI) + DeepPurpose (pulls its own MPNN/CNN stack from
#   Harvard Dataverse at runtime). PLAPT repo cloned on-instance. No mkfs/dd/rm. Hardened: no creds
#   in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== dti_nav eval start: $(date -u) ==="
set +x  # SECURITY: do not echo creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="dti_nav"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git wget >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (rdkit 2022.9.5 C-ext ABI). torch>=2.6 cu124 (transformers torch.load gate for the
# ProtBERT/ChemBERTa .bin checkpoints PLAPT downloads from HuggingFace).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
$PY -m pip install -q "transformers>=4.45" "huggingface_hub>=0.24" accelerate safetensors \
    onnxruntime-gpu diskcache biopython "rdkit==2022.9.5" scikit-learn scipy pandas tqdm 2>&1 | tail -3
# DeepPurpose drags in its own MPNN/CNN deps; install last so it can't downgrade torch/numpy silently.
$PY -m pip install -q DeepPurpose 2>&1 | tail -2 || echo "[warn] DeepPurpose install non-zero (section is guarded)"
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: ensure nothing dragged numpy to 2.x

# FAIL-FAST gate on the CORE (PLAPT) deps only; DeepPurpose is best-effort + guarded in the eval.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, onnxruntime, rdkit, sklearn, pandas
from rdkit import Chem
print("core deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "onnxrt", onnxruntime.__version__, "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK
# Report DeepPurpose availability (non-fatal).
$PY -c "import DeepPurpose; from DeepPurpose import DTI; print('DeepPurpose ok')" || echo "[warn] DeepPurpose import failed — eval will skip it"

# PLAPT repo (ships models/affinity_predictor.onnx in-tree; ProtBERT/ChemBERTa pulled from HF at runtime).
git clone --depth 1 https://github.com/Bindwell/PLAPT /opt/PLAPT 2>&1 | tail -2 || fail "clone" 93
ls -la /opt/PLAPT/models/ || echo "[warn] PLAPT models/ dir missing"

aws s3 cp "s3://$BUCKET/$PREFIX/dti_nav_eval.py" /opt/dti_nav_eval.py || fail "dl-eval" 94
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 95

echo "=== run dti_nav eval $(date -u) ==="
export USE_TF=0 USE_FLAX=0
PANELS=/opt/crossmodal_panels.json PLAPT_DIR=/opt/PLAPT \
  OUT=/root/dti_out/dti_nav_result.json $PY /opt/dti_nav_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/dti_out/dti_nav_result.json ] && \
  aws s3 cp /root/dti_out/dti_nav_result.json "s3://$BUCKET/$PREFIX/dti_nav_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
