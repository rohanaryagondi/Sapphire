#!/bin/bash
# DTI Nav-generalization cross-check (overnight Phase 3) — GatorAffinity. Self-contained venv.
# FRAGILE NEW TOOLCHAIN: torch 2.1.1+cu118 + torch_scatter/torch_cluster (cu118 wheels) + e3nn==0.5.1
# (NOT >0.5.4) + rdkit-pypi 2022.9.5 + openbabel-wheel + biotite/biopython + atom3d, numpy<2.
# ATOMICA backbone (HF ada-f/ATOMICA) + GatorAffinity ckpt (CC BY-NC-SA, non-commercial) cached to S3.
# Because the toolchain is fragile, deps + checkpoints are checked with EXPLICIT fail-fast gates
# (the main agent enforces a <=2 relaunch cap — abandon + bank rather than burn budget). NON-COMMERCIAL
# RESEARCH. No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== dti generalization (GatorAffinity) start: $(date -u) ==="
set +x  # SECURITY: do not echo creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="dti_generalization"
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
PYV=$($PY -c "import sys;print(f'cp{sys.version_info.major}{sys.version_info.minor}')")
echo "python tag: $PYV"

# --- GatorAffinity deps, from the repo's environment.sh (adapted to a venv; conda-activate fails in userdata) ---
# numpy pinned <2 (rdkit/atom3d C-ext ABI). torch 2.1.1+cu118 is the combo the geometric wheels match.
$PY -m pip install -q "numpy==1.26.4" 2>&1 | tail -1
$PY -m pip install -q torch==2.1.1+cu118 --extra-index-url https://download.pytorch.org/whl/cu118 2>&1 | tail -1
# torch_scatter / torch_cluster from the matching PyG wheel index for torch-2.1.1+cu118.
$PY -m pip install -q torch_scatter torch_cluster -f https://data.pyg.org/whl/torch-2.1.1+cu118.html 2>&1 | tail -2
# e3nn PINNED 0.5.1 (repo note: possibly incompatible with >0.5.4). Plus the rest of environment.sh.
$PY -m pip install -q "e3nn==0.5.1" "rdkit-pypi==2022.9.5" "openbabel-wheel==3.1.1.20" \
    "biopython==1.84" "biotite==0.40.0" atom3d "scipy==1.13.1" scikit-learn pandas orjson \
    "huggingface_hub>=0.24" 2>&1 | tail -4
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: ensure nothing dragged numpy to 2.x

# FAIL-FAST deps gate (fragile toolchain — abandon cleanly rather than half-run).
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, e3nn, rdkit, scipy, sklearn
import torch_scatter, torch_cluster
from rdkit.Chem import AllChem
try:
    import openbabel  # openbabel-wheel
except Exception as e:
    print("[warn] openbabel import:", e)
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "e3nn", e3nn.__version__, "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit/atom3d C-ext ABI"
PYCHK

git clone --depth 1 https://github.com/AIDD-LiLab/GatorAffinity /opt/GatorAffinity 2>&1 | tail -2 || fail "clone" 93

# --- Checkpoints (cache to S3 so a relaunch skips the slow HF/repo download) ---
mkdir -p /opt/GatorAffinity/model_checkpoints
CKPT="/opt/GatorAffinity/model_checkpoints/Kd+Ki+IC50_experimental_fine_tuning.ckpt"
if aws s3 cp "s3://$BUCKET/$PREFIX/gator_ckpt.ckpt" "$CKPT" 2>/dev/null && [ -s "$CKPT" ]; then
  echo "gator ckpt from S3 cache"
else
  # The fine-tuning ckpt ships in the repo's model_checkpoints/ via git-lfs OR needs HF download.
  ( cd /opt/GatorAffinity && git lfs install 2>/dev/null; git lfs pull 2>&1 | tail -3 ) || true
  [ -s "$CKPT" ] || $PY - <<'PYDL'
import os
from huggingface_hub import hf_hub_download, snapshot_download
# GatorAffinity README: checkpoints under model_checkpoints/; if hosted on HF the repo id is
# AIDD-LiLab/GatorAffinity — best-effort, allowed to fail (then fail-gate below abandons cleanly).
for rid in ("AIDD-LiLab/GatorAffinity",):
    try:
        snapshot_download(repo_id=rid, allow_patterns=["*.ckpt", "model_checkpoints/*"],
                          local_dir="/opt/GatorAffinity/_hf_ckpt")
    except Exception as e:
        print("[warn] HF ckpt download:", e)
PYDL
  # locate whatever fine-tuning ckpt landed
  FOUND=$(find /opt/GatorAffinity -name "*experimental_fine_tuning*.ckpt" 2>/dev/null | head -1)
  [ -n "$FOUND" ] && cp "$FOUND" "$CKPT" 2>/dev/null || true
  [ -s "$CKPT" ] && aws s3 cp "$CKPT" "s3://$BUCKET/$PREFIX/gator_ckpt.ckpt" >/dev/null 2>&1 || true
fi
[ -s "$CKPT" ] || fail "no-gator-ckpt" 94
echo "gator ckpt: $CKPT ($(stat -c%s "$CKPT" 2>/dev/null || echo '?') bytes)"

# ATOMICA backbone (HF ada-f/ATOMICA, path ATOMICA_checkpoints/pretrain). Cache to S3.
mkdir -p /opt/atomica
if aws s3 cp "s3://$BUCKET/$PREFIX/atomica.tar" /tmp/atomica.tar 2>/dev/null && [ -s /tmp/atomica.tar ]; then
  tar -xf /tmp/atomica.tar -C /opt/atomica && echo "ATOMICA from S3 cache"
else
  $PY - <<'PYDL2' || echo "[warn] ATOMICA download failed (GatorAffinity may bundle/locate it itself)"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="ada-f/ATOMICA", allow_patterns=["ATOMICA_checkpoints/pretrain/*", "*.ckpt", "*.json"],
                  local_dir="/opt/atomica")
print("ATOMICA downloaded")
PYDL2
  ( cd /opt/atomica && tar -cf /tmp/atomica.tar . ) 2>/dev/null && aws s3 cp /tmp/atomica.tar "s3://$BUCKET/$PREFIX/atomica.tar" >/dev/null 2>&1 || true
fi
echo "ATOMICA dir contents:"; ls -R /opt/atomica 2>/dev/null | head -20

aws s3 cp "s3://$BUCKET/$PREFIX/dti_generalization.py" /opt/dti_generalization.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 96

echo "=== run GatorAffinity Nav-generalization eval $(date -u) ==="
PANELS=/opt/crossmodal_panels.json GATOR_DIR=/opt/GatorAffinity GATOR_CKPT="$CKPT" \
  OUT=/root/dti_gen_out/dti_generalization_result.json $PY /opt/dti_generalization.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/dti_gen_out/dti_generalization_result.json ] && \
  aws s3 cp /root/dti_gen_out/dti_generalization_result.json "s3://$BUCKET/$PREFIX/dti_generalization_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
