#!/bin/bash
# CNS-BROAD DTI benchmark: BALM (cosine) + PLAPT (affinity) on a ~15-20 target CNS panel
# (TSC2/mTOR pathway + epilepsy/excitability ion channels + CNS GPCRs + neurodeg kinases).
# Per-target binder-vs-decoy AUROC -> per-FAMILY aggregate. Data pulled on-instance from
# ChEMBL (chembl_webresource_client) + UniProt REST. Both models run from protein SEQUENCE
# + ligand SMILES (no 3D structure).
# Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
# TOOLCHAIN (union of the proven BALM + dti_nav/PLAPT stacks + ChEMBL client):
#   torch>=2.6 cu124  -- ChemBERTa-77M-MTR ships only pytorch_model.bin; transformers blocks
#                        torch.load on .bin unless torch>=2.6 (CVE-2025-32434). Needed by BOTH
#                        BALM (ChemBERTa drug tower) and PLAPT (ProtBERT/ChemBERTa embeddings).
#   transformers+peft -- BALM ESM-2 + ChemBERTa + lokr/loha PEFT adapters; PLAPT HF encoders.
#   onnxruntime-gpu   -- PLAPT affinity head is models/affinity_predictor.onnx.
#   rdkit==2022.9.5   -- SMILES sanity + DUD-E-style property-matched decoys (numpy<2 ABI pin).
#   chembl_webresource_client -- on-instance ChEMBL actives/inactives pull (this benchmark).
#   numpy<2, requests, scikit-learn, scipy, pydantic, pyyaml, sentencepiece -- BALM config/metrics.
# Clones BOTH repos on-instance (BALM = meyresearch/BALM, PLAPT = Bindwell/PLAPT).
# No mkfs/dd/rm of existing data. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== cns dti benchmark start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="cns_dti"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# Bigger panel (15-20 targets x ~30-180 pairs x 2 models) -> generous watchdog.
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; python3-venv (meta) alone did NOT
# pull it on the prior tsc2_deconv run, so `python3 -m venv` came up WITHOUT pip -> No module named
# pip/numpy cascade (the rc=1 failure). Install python3.10-venv on its OWN line; ensurepip + the
# pip-version guard below are MANDATORY (this is what the prior run was missing).
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (rdkit 2022.9.5 C-ext ABI). torch>=2.6 cu124 (transformers torch.load gate
# for the ProtBERT/ChemBERTa .bin checkpoints both models pull from HuggingFace).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
# Union of BALM + PLAPT deps + ChEMBL client. peft/pyyaml/sentencepiece/pydantic = BALM;
# onnxruntime-gpu = PLAPT; chembl_webresource_client = on-instance ChEMBL data pull.
$PY -m pip install -q "transformers>=4.45" peft "huggingface_hub>=0.24" accelerate safetensors \
    onnxruntime-gpu diskcache "rdkit==2022.9.5" scikit-learn scipy pandas tqdm requests \
    pyyaml sentencepiece pydantic chembl_webresource_client 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: BOTH models' core deps + the ChEMBL client must import.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, peft, onnxruntime, rdkit, sklearn, scipy, pydantic, yaml, requests
from rdkit import Chem
from chembl_webresource_client.new_client import new_client
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "onnxrt", onnxruntime.__version__,
      "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# Clone BOTH model repos on-instance.
# BALM ships default_configs/balm_peft.yaml; checkpoint pulled from HF at load time.
git clone --depth 1 https://github.com/meyresearch/BALM /opt/BALM 2>&1 | tail -2 || fail "clone-balm" 93
ls /opt/BALM/default_configs/ || echo "[warn] BALM default_configs not where expected"
# PLAPT ships models/affinity_predictor.onnx in-tree; ProtBERT/ChemBERTa pulled from HF at runtime.
git clone --depth 1 https://github.com/Bindwell/PLAPT /opt/PLAPT 2>&1 | tail -2 || fail "clone-plapt" 94
ls -la /opt/PLAPT/models/ || echo "[warn] PLAPT models/ dir missing"

# Stage the eval from S3 (the launcher uploads it to s3://$BUCKET/$PREFIX/). The target panel
# is defined IN the eval script (no separate panel file); data is fetched on-instance.
aws s3 cp "s3://$BUCKET/$PREFIX/cns_dti_benchmark_eval.py" /opt/cns_dti_benchmark_eval.py || fail "dl-eval" 95

echo "=== run cns dti benchmark $(date -u) ==="
export USE_TF=0 USE_FLAX=0
BALM_DIR=/opt/BALM PLAPT_DIR=/opt/PLAPT \
  OUT=/root/cns_out/cns_dti_result.json $PY /opt/cns_dti_benchmark_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/cns_out/cns_dti_result.json ] && \
  aws s3 cp /root/cns_out/cns_dti_result.json "s3://$BUCKET/$PREFIX/cns_dti_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
