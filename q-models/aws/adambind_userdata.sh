#!/bin/bash
# AdaMBind few-shot DTI characterization (overnight, unattended). Self-contained venv.
# TOOLCHAIN: torch 2.3.1+cu121 (AdaMBind README) + torch_geometric + torch_scatter/torch_cluster
# (cu121 PyG wheels — model/gat_gcn.py does `from torch_scatter import scatter_add`) + rdkit==2022.9.5
# + networkx + numpy<2 (rdkit C-ext ABI) + pytdc (base meta-training set: BindingDB_Kd) + scikit-learn.
# AdaMBind ships NO weights and NO license (=> all-rights-reserved; eval/research only). We meta-train a
# small base learner on-instance, then do k-shot adaptation on the Quiver panels. conda-activate fails in
# userdata -> EXPLICIT /opt/venv/bin/python. FRAGILE PyG wheels -> fail-fast deps gate. No mkfs/dd/rm.
# Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== adambind characterization start: $(date -u) ==="
set +x  # SECURITY: do not echo creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="adambind"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git wget >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip

# numpy pinned <2 FIRST (rdkit 2022.9.5 C-ext ABI); torch 2.3.1+cu121 = the combo the PyG wheels match.
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q torch==2.3.1 --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1
# PyG core + companion C-ext wheels (torch_scatter/torch_cluster) from the matching wheel index.
$PY -m pip install -q torch_geometric 2>&1 | tail -1
$PY -m pip install -q torch_scatter torch_cluster -f https://data.pyg.org/whl/torch-2.3.1+cu121.html 2>&1 | tail -2
$PY -m pip install -q "rdkit==2022.9.5" networkx scikit-learn scipy pandas pytdc "huggingface_hub>=0.24" 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: ensure nothing dragged numpy to 2.x

# FAIL-FAST deps gate (fragile PyG C-ext wheels — abandon cleanly rather than half-run).
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, rdkit, sklearn, networkx, pandas
import torch_geometric
from torch_scatter import scatter_add
from torch_geometric.loader import DataLoader
from rdkit import Chem
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "pyg", torch_geometric.__version__, "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

git clone --depth 1 https://github.com/Moohyun-w/AdaMBind /opt/AdaMBind 2>&1 | tail -2 || fail "clone" 93
aws s3 cp "s3://$BUCKET/$PREFIX/adambind_eval.py" /opt/adambind_eval.py || fail "dl-eval" 94
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 95

echo "=== run AdaMBind few-shot characterization $(date -u) ==="
PANELS=/opt/crossmodal_panels.json ADAMBIND_DIR=/opt/AdaMBind WORK=/root/adambind_work \
  OUT=/root/adambind_out/adambind_result.json $PY /opt/adambind_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/adambind_out/adambind_result.json ] && \
  aws s3 cp /root/adambind_out/adambind_result.json "s3://$BUCKET/$PREFIX/adambind_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
