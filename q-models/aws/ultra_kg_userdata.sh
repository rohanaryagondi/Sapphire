#!/bin/bash
# ULTRA Track-6 KG characterization (overnight). Self-contained venv. ULTRA is pure PyTorch-Geometric
# (no .bin torch.load<2.6 gate), MIT license, 168k params -> CPU/small-GPU fine. The one fragile dep is
# torch-scatter (must match torch+cuda exactly): we pin torch 2.4.0+cu124 and pull torch-scatter/sparse
# from the matching PyG wheel index, with a FORCE_CPU fallback so a GPU/wheel mismatch still banks results.
# No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== ultra kg characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="ultra_kg"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver — ULTRA (168k params) runs fine on CPU; will FORCE_CPU"
export DEBIAN_FRONTEND=noninteractive
# ninja-build + build-essential: ULTRA's rspmm layer JIT-compiles a C++/CUDA extension via
# torch.utils.cpp_extension, which needs the `ninja` BINARY on PATH (pip's ninja in /opt/venv/bin is
# not on the default PATH at run time -> "Ninja is required to load C++ extensions") and g++/nvcc.
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git ninja-build build-essential >/dev/null 2>&1
which ninja && ninja --version || echo "[warn] system ninja missing"
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip

# torch 2.4.0 cu124 (PyG scatter/sparse wheels exist for this exact build). numpy<2 (ABI safety).
$PY -m pip install -q torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
$PY -m pip install -q torch_geometric "numpy<2" scikit-learn scipy pyyaml easydict pandas ninja 2>&1 | tail -2
# torch-scatter / torch-sparse from the PyG wheel index keyed to torch-2.4.0+cu124.
$PY -m pip install -q torch_scatter torch_sparse \
    -f https://data.pyg.org/whl/torch-2.4.0+cu124.html 2>&1 | tail -2 || echo "[warn] cu124 scatter wheels failed"

# Verify the toolchain; if CUDA scatter is broken, retry CPU scatter wheels and force CPU at runtime.
export FORCE_CPU=0
if ! $PY -c "import torch, torch_scatter, torch_geometric; print('cuda', torch.cuda.is_available())"; then
  echo "[warn] falling back to CPU torch-scatter wheels"
  $PY -m pip install -q torch_scatter torch_sparse -f https://data.pyg.org/whl/torch-2.4.0+cpu.html 2>&1 | tail -2
  export FORCE_CPU=1
fi
$PY -c "import torch, torch_scatter, torch_sparse, torch_geometric, sklearn, scipy, numpy; print('deps ok')" || fail "deps" 92
# If GPU absent entirely, force CPU.
$PY -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || export FORCE_CPU=1
echo "FORCE_CPU=$FORCE_CPU"

# Clone ULTRA (MIT) — provides ultra.models.Ultra, ultra.tasks, ultra.datasets.Hetionet + ckpts/*.pth.
git clone --depth 1 https://github.com/DeepGraphLearning/ULTRA /opt/ULTRA 2>&1 | tail -2 || fail "clone" 93
ls -la /opt/ULTRA/ckpts || echo "[warn] no ckpts dir in clone"
# If repo did not ship the checkpoint, fetch the HF mirror (mgalkin/ultra_4g, MIT).
if [ ! -f /opt/ULTRA/ckpts/ultra_4g.pth ]; then
  echo "[info] ultra_4g.pth not in clone; fetching HF mirror"
  $PY -m pip install -q "huggingface_hub>=0.24" 2>&1 | tail -1
  mkdir -p /opt/ULTRA/ckpts
  $PY -c "from huggingface_hub import hf_hub_download; import shutil; p=hf_hub_download('mgalkin/ultra_4g','ultra_4g.pth'); shutil.copy(p,'/opt/ULTRA/ckpts/ultra_4g.pth')" 2>&1 | tail -2 || echo "[warn] HF ckpt fetch failed"
fi

aws s3 cp "s3://$BUCKET/$PREFIX/ultra_kg_eval.py" /opt/ultra_kg_eval.py || fail "dl-eval" 94
mkdir -p /opt/kg-datasets

echo "=== run ULTRA characterization $(date -u) ==="
# Put pip's ninja on PATH too (belt+suspenders with the apt ninja-build) and point at the CUDA toolkit
# so torch can build the rspmm CUDA kernel. The DLAMI ships /usr/local/cuda.
export PATH="/opt/venv/bin:$PATH"
[ -d /usr/local/cuda ] && export CUDA_HOME=/usr/local/cuda
FORCE_CPU=$FORCE_CPU OUT=/root/ultra_out/ultra_kg_result.json \
  ULTRA_DIR=/opt/ULTRA ULTRA_CKPT=/opt/ULTRA/ckpts/ultra_4g.pth ULTRA_DATA_ROOT=/opt/kg-datasets \
  $PY /opt/ultra_kg_eval.py
RC=$?
# HEDGE (one launch, both paths): if the GPU rspmm build still failed (ninja/nvcc/CUDA-version), the
# eval banks per-section "rspmm"/"Ninja"/"cpp_extension" errors at rc=0. Detect that and retry on CPU —
# torch sees no GPU (CUDA_VISIBLE_DEVICES="") so rspmm compiles its CPU variant with g++ only (no nvcc).
# ULTRA is 168k params; the bounded per-target query set finishes well inside the watchdog.
if grep -qiE "rspmm|Ninja is required|cpp_extension|Expected all tensors" /root/ultra_out/ultra_kg_result.json 2>/dev/null; then
  echo "=== [retry] CUDA rspmm build failed -> forcing CPU rspmm (g++ only) $(date -u) ==="
  CUDA_VISIBLE_DEVICES="" FORCE_CPU=1 OUT=/root/ultra_out/ultra_kg_result.json \
    ULTRA_DIR=/opt/ULTRA ULTRA_CKPT=/opt/ULTRA/ckpts/ultra_4g.pth ULTRA_DATA_ROOT=/opt/kg-datasets \
    $PY /opt/ultra_kg_eval.py
  RC=$?
fi
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ultra_out/ultra_kg_result.json ] && \
  aws s3 cp /root/ultra_out/ultra_kg_result.json "s3://$BUCKET/$PREFIX/ultra_kg_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
