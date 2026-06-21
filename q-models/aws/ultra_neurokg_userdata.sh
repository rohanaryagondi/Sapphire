#!/bin/bash
# ULTRA on NeuroKG (PrimeKG + Quiver neuro augmentation) — same-substrate head-to-head vs PROTON.
# Self-contained venv. Same proven ULTRA toolchain as ultra_kg_userdata.sh (torch 2.4.0+cu124, PyG
# scatter/sparse, ninja-build for the rspmm CUDA kernel, GPU->CPU rspmm hedge). Extra: pandas + the
# NeuroKG CSVs (nodes.csv + edges.csv.zip) fetched from S3 and unzipped. Bigger graph -> 7200s watchdog.
# No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== ultra NeuroKG characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="ultra_neurokg"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 7200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver — will FORCE_CPU"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git ninja-build build-essential unzip >/dev/null 2>&1
which ninja && ninja --version || echo "[warn] system ninja missing"
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -m pip install -q torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
$PY -m pip install -q torch_geometric "numpy<2" scikit-learn scipy pyyaml easydict pandas ninja 2>&1 | tail -2
$PY -m pip install -q torch_scatter torch_sparse \
    -f https://data.pyg.org/whl/torch-2.4.0+cu124.html 2>&1 | tail -2 || echo "[warn] cu124 scatter wheels failed"
export FORCE_CPU=0
if ! $PY -c "import torch, torch_scatter, torch_geometric; print('cuda', torch.cuda.is_available())"; then
  echo "[warn] falling back to CPU torch-scatter wheels"
  $PY -m pip install -q torch_scatter torch_sparse -f https://data.pyg.org/whl/torch-2.4.0+cpu.html 2>&1 | tail -2
  export FORCE_CPU=1
fi
$PY -c "import torch, torch_scatter, torch_sparse, torch_geometric, sklearn, pandas, numpy; print('deps ok')" || fail "deps" 92
$PY -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || export FORCE_CPU=1
echo "FORCE_CPU=$FORCE_CPU"

# Clone ULTRA + checkpoint (same as Hetionet run).
git clone --depth 1 https://github.com/DeepGraphLearning/ULTRA /opt/ULTRA 2>&1 | tail -2 || fail "clone" 93
if [ ! -f /opt/ULTRA/ckpts/ultra_4g.pth ]; then
  $PY -m pip install -q "huggingface_hub>=0.24" 2>&1 | tail -1
  mkdir -p /opt/ULTRA/ckpts
  $PY -c "from huggingface_hub import hf_hub_download; import shutil; p=hf_hub_download('mgalkin/ultra_4g','ultra_4g.pth'); shutil.copy(p,'/opt/ULTRA/ckpts/ultra_4g.pth')" 2>&1 | tail -2 || echo "[warn] HF ckpt fetch failed"
fi

# NeuroKG source CSVs (uploaded to S3 by the launcher).
mkdir -p /opt/neurokg
aws s3 cp "s3://$BUCKET/neurokg_src/nodes.csv" /opt/neurokg/nodes.csv || fail "dl-nodes" 95
aws s3 cp "s3://$BUCKET/neurokg_src/edges.csv.zip" /opt/neurokg/edges.csv.zip || fail "dl-edges" 96
( cd /opt/neurokg && unzip -o edges.csv.zip >/dev/null 2>&1 ) || fail "unzip-edges" 97
ls -la /opt/neurokg/
aws s3 cp "s3://$BUCKET/$PREFIX/ultra_neurokg_eval.py" /opt/ultra_neurokg_eval.py || fail "dl-eval" 98

echo "=== run ULTRA NeuroKG characterization $(date -u) ==="
export PATH="/opt/venv/bin:$PATH"
[ -d /usr/local/cuda ] && export CUDA_HOME=/usr/local/cuda
FORCE_CPU=$FORCE_CPU OUT=/root/ultra_out/ultra_neurokg_result.json \
  ULTRA_DIR=/opt/ULTRA ULTRA_CKPT=/opt/ULTRA/ckpts/ultra_4g.pth \
  NODES_CSV=/opt/neurokg/nodes.csv EDGES_CSV=/opt/neurokg/edges.csv \
  $PY /opt/ultra_neurokg_eval.py
RC=$?
# HEDGE: if the GPU rspmm build failed OR the forward OOMed on the ~8M-edge graph, retry on CPU
# (CUDA_VISIBLE_DEVICES="" -> CPU rspmm with g++, no nvcc, no GPU-memory ceiling).
if grep -qiE "rspmm|Ninja is required|cpp_extension|out of memory|CUDA error|Expected all tensors" /root/ultra_out/ultra_neurokg_result.json 2>/dev/null; then
  echo "=== [retry] GPU build/OOM -> forcing CPU $(date -u) ==="
  CUDA_VISIBLE_DEVICES="" FORCE_CPU=1 OUT=/root/ultra_out/ultra_neurokg_result.json \
    ULTRA_DIR=/opt/ULTRA ULTRA_CKPT=/opt/ULTRA/ckpts/ultra_4g.pth \
    NODES_CSV=/opt/neurokg/nodes.csv EDGES_CSV=/opt/neurokg/edges.csv \
    $PY /opt/ultra_neurokg_eval.py
  RC=$?
fi
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ultra_out/ultra_neurokg_result.json ] && \
  aws s3 cp /root/ultra_out/ultra_neurokg_result.json "s3://$BUCKET/$PREFIX/ultra_neurokg_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
