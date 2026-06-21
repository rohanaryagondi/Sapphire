#!/bin/bash
# ION-CHANNEL BINDER FINE-TUNE: train a real CROSS-CHANNEL DTI model (frozen ESM-2-650M
# protein tower + Morgan-FP ligand tower -> MLP head) on a POOLED ChEMBL + Guide-to-
# PHARMACOLOGY ion-channel corpus, then test genuine generalization via (1) Murcko
# scaffold split and (2) Leave-One-Channel-Out. The concrete "the fine-tune is the lever"
# run: off-the-shelf zero-shot DTI is at chance (0.50) on CNS ion channels; a per-target
# probe already hit 0.92; this scales it to a deployable cross-channel binder model.
# Data: ChEMBL pulled on-instance (chembl_webresource_client, full Nav/Cav/NMDA/Kv panel,
# NO cap, per-target signal.alarm fail-fast) + UniProt REST sequences + a GtoPdb anchor CSV
# staged from S3. g5.xlarge. Self-contained /opt/venv via EXPLICIT python (conda-activate
# fails in userdata).
# TOOLCHAIN (ESM-2 encoder + torch MLP + sklearn baseline — no BALM/PLAPT repos, no onnx):
#   torch>=2.6 cu121  -- transformers torch.load gate (CVE-2025-32434) for the ESM-2 HF
#                        checkpoint; also runs the MLP head on GPU.
#   transformers      -- ESM-2-650M (facebook/esm2_t33_650M_UR50D) EsmModel encoder.
#   rdkit==2022.9.5   -- Morgan-FP ligands + Murcko scaffolds + DUD-E decoys + canonical
#                        SMILES dedup (numpy<2 C-ext ABI pin).
#   scikit-learn      -- GradientBoosting FP baseline + GroupKFold scaffold split.
#   chembl_webresource_client -- on-instance ChEMBL actives/inactives pull (full panel).
#   numpy<2, requests, scipy, pandas -- ABI pin + UniProt fetch + sklearn deps.
# No model-repo clone (encoder is a HF download). No mkfs/dd/rm of existing data.
# Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== ionchannel finetune start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="ionchannel_finetune"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# Full ~21-target Nav/Cav/NMDA/Kv ChEMBL pull (NO cap) + ESM-2 embedding of every channel +
# pooled MLP training + scaffold-split CV + 4x LOCO retrain -> generous watchdog.
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; python3-venv (meta) alone did NOT
# pull it on a prior run, so `python3 -m venv` came up WITHOUT pip -> No module named pip/numpy
# cascade. Install python3.10-venv on its OWN line; ensurepip + the pip-version guard below are
# MANDATORY (this is what the failing run was missing).
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (rdkit 2022.9.5 C-ext ABI). torch>=2.6 cu121 (transformers torch.load gate
# for the ESM-2 HF checkpoint; also runs the MLP head on GPU).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1
# ESM-2 encoder stack + ChEMBL client + RDKit/sklearn for the ligand rep + FP-GBT baseline.
$PY -m pip install -q "transformers>=4.45" "huggingface_hub>=0.24" accelerate safetensors \
    "rdkit==2022.9.5" scikit-learn scipy pandas tqdm requests chembl_webresource_client 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: encoder deps + RDKit + sklearn + the ChEMBL client must import.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, safetensors, rdkit, sklearn, scipy, requests
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from transformers import AutoModel, AutoTokenizer
from chembl_webresource_client.new_client import new_client
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "sklearn", sklearn.__version__,
      "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# Stage the eval from S3 (the launcher uploads it to s3://$BUCKET/$PREFIX/). The full
# ion-channel panel is defined IN the eval script; ChEMBL data is fetched on-instance.
aws s3 cp "s3://$BUCKET/$PREFIX/ionchannel_finetune_eval.py" /opt/ionchannel_finetune_eval.py || fail "dl-eval" 95
# Stage the GtoPdb anchor corpus (the launcher uploads data/cns_ionchannel/gtopdb_ionchannel_affinities.csv).
aws s3 cp "s3://$BUCKET/$PREFIX/gtopdb_ionchannel_affinities.csv" /opt/gtopdb_ionchannel_affinities.csv || echo "[warn] no GtoPdb csv (eval will proceed ChEMBL-only)"

echo "=== run ionchannel finetune $(date -u) ==="
export USE_TF=0 USE_FLAX=0
GTOPDB_CSV=/opt/gtopdb_ionchannel_affinities.csv \
  OUT=/root/ionchannel_out/ionchannel_finetune_result.json $PY /opt/ionchannel_finetune_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ionchannel_out/ionchannel_finetune_result.json ] && \
  aws s3 cp /root/ionchannel_out/ionchannel_finetune_result.json "s3://$BUCKET/$PREFIX/ionchannel_finetune_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
