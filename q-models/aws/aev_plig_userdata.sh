#!/bin/bash
# AEV-PLIG (oxpig) structure-based affinity re-scorer on the Quiver Nav1.8 + mTOR panels.
# AEV-PLIG is POSE-GATED: it scores a BOUND 3D complex (sdf ligand pose + pdb protein), NOT
# sequence+SMILES. We have NO holo structures for these targets, so the eval docks/places each
# panel compound into the apo AlphaFold model (smina if available, else RDKit centroid placement),
# gates on real ligand-protein contacts, and SKIPS (does not fabricate) pairs with no contact.
# The pretrained FEP-benchmark ensemble (10x ~30MB .model + scaler .pickle) is COMMITTED in the
# repo's output/trained_models/, so a plain clone gives working inference weights.
# Self-contained /opt/venv via explicit python. No mkfs/dd/rm of existing data. Hardened: no creds in log.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== aev-plig eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="aev_plig"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver — will FORCE_CPU"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# CRITICAL packages MUST install on their own line: bundling an unavailable pkg (smina is NOT in the
# default Ubuntu repos) makes apt install NOTHING -> venv comes up WITHOUT pip -> whole run cascades.
# (That was the rc=92 failure.) python3.10-venv carries ensurepip for the DLAMI's python3.10.
apt-get install -y python3-venv python3.10-venv python3-pip git >/dev/null 2>&1 || fail "apt-core" 90
# OPTIONAL (best-effort, must NOT break the build): git-lfs (LFS .model pointers) + smina (Tier-A docking).
apt-get install -y git-lfs >/dev/null 2>&1 && git lfs install >/dev/null 2>&1 || echo "[warn] no git-lfs"
apt-get install -y smina >/dev/null 2>&1 || echo "[warn] no smina -> Tier B centroid placement"
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip
# AEV-PLIG deps (repo README): torch + torch-geometric + torch-scatter + rdkit + torchani +
# qcelemental + pandas + biopandas + scikit-learn. Pin numpy<2 (torchani/biopandas friendly).
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
$PY -m pip install -q torch_geometric "numpy<2" rdkit torchani qcelemental pandas biopandas \
    scikit-learn scipy 2>&1 | tail -3
# torch-scatter wheel matched to the installed torch (cu124); CPU fallback if the GPU wheel fails.
TORCH_VER=$($PY -c "import torch;print(torch.__version__.split('+')[0])" 2>/dev/null || echo 2.4.0)
$PY -m pip install -q torch_scatter -f "https://data.pyg.org/whl/torch-${TORCH_VER}+cu124.html" 2>&1 | tail -2 \
  || $PY -m pip install -q torch_scatter -f "https://data.pyg.org/whl/torch-${TORCH_VER}+cpu.html" 2>&1 | tail -2 \
  || echo "[warn] torch_scatter wheel install failed"
export FORCE_CPU=0
$PY -c "import torch, torch_geometric, torch_scatter, rdkit, torchani, pandas, sklearn, numpy; print('deps ok; cuda', torch.cuda.is_available())" || fail "deps" 92
$PY -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || export FORCE_CPU=1
echo "FORCE_CPU=$FORCE_CPU"
which smina && echo "[info] smina present (Tier A docking enabled)" || echo "[info] no smina -> Tier B centroid placement"

# Clone AEV-PLIG. The FEP-benchmark ensemble weights (10x ~30MB .model + .pickle scaler) are
# COMMITTED under output/trained_models/, so inference works straight from the clone.
git clone --depth 1 https://github.com/oxpig/AEV-PLIG /opt/AEV-PLIG 2>&1 | tail -2 || fail "clone" 93
( cd /opt/AEV-PLIG && git lfs pull 2>&1 | tail -2 ) || echo "[warn] git lfs pull no-op (weights likely plain files)"
ls -la /opt/AEV-PLIG/output/trained_models/ 2>&1 | head -20 || echo "[warn] trained_models dir missing"
# Verify the ensemble weights are real (>1MB), not LFS pointers; bail early if they did not materialize.
N_MODELS=$(ls /opt/AEV-PLIG/output/trained_models/model_GATv2Net_ligsim90_fep_benchmark_*.model 2>/dev/null | wc -l)
SZ0=$(stat -c%s /opt/AEV-PLIG/output/trained_models/model_GATv2Net_ligsim90_fep_benchmark_0.model 2>/dev/null || echo 0)
echo "[info] ensemble members=$N_MODELS first_size=$SZ0"
[ "$N_MODELS" -ge 1 ] && [ "$SZ0" -gt 1000000 ] || echo "[warn] FEP-benchmark weights look missing/LFS-pointer — inference will fail and the eval will record it"

aws s3 cp "s3://$BUCKET/$PREFIX/aev_plig_eval.py" /opt/aev_plig_eval.py || fail "dl-eval" 94
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 95

echo "=== run AEV-PLIG eval $(date -u) ==="
export PATH="/opt/venv/bin:$PATH"
FORCE_CPU=$FORCE_CPU PANELS=/opt/crossmodal_panels.json OUT=/root/aev_out/aev_plig_result.json \
  AEV_DIR=/opt/AEV-PLIG AEV_MODEL=model_GATv2Net_ligsim90_fep_benchmark \
  STRUCT_DIR=/opt/aev_struct WORK=/root/aev_work \
  $PY /opt/aev_plig_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/aev_out/aev_plig_result.json ] && \
  aws s3 cp /root/aev_out/aev_plig_result.json "s3://$BUCKET/$PREFIX/aev_plig_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
