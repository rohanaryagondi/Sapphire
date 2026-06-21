#!/bin/bash
# LigUnity (Patterns 2025; IDEA-XL) on Track 2 / binder triage — 19-target CNS panel,
# head-to-head vs the BALM/PLAPT sequence baselines. g5.xlarge.
#
# CHECKPOINT / PATH (the STEP-0 determination; see header of aws/ligunity_eval.py):
#   We use fengb/LigUnity_protein_ranking — its pocket_forward() encodes the protein PURELY from
#   the UniProt SEQUENCE via ESM2-35M and DISCARDS the 3D pocket tensors -> POCKET-FREE, the same
#   input class (sequence+SMILES) as BALM/PLAPT. The pocket_ranking checkpoint is POSE-GATED
#   (consumes a Uni-Mol 3D pocket) and is NOT used (same failure mode as DrugCLIP/AEV-PLIG on our
#   no-holo targets). test_demo still loads a pocket lmdb for batch shape; the eval feeds a tiny
#   placeholder pocket the model never reads.
#
# TOOLCHAIN (the Uni-Core/Uni-Mol stack — KNOWN INSTALL TRAP; recipe proven on the DrugCLIP run,
# aws/drugclip_crossmodal_userdata.sh):
#   torch==2.0.0 cu118        -- the exact combo Uni-Core publishes matching wheels for.
#   Uni-Core 0.0.1+cu118torch2.0.0  -- DrugCLIP/LigUnity framework (unicore-train, checkpoint_utils).
#                                NOTE: under release TAG 0.0.3 the wheel FILENAME is version 0.0.1
#                                (tag != file version). Check pip's OWN exit, fall back to source build.
#   rdkit==2022.9.5 + numpy<2 -- C-ext ABI pin; numpy 2.x segfaults rdkit/unicore on import.
#   transformers + huggingface_hub -- ESM2-35M (esm2_t12_35M_UR50D) protein tower the model loads.
#   lmdb                      -- LigUnity reads ligand/pocket data as Uni-Mol LMDBs.
#   ml_collections, tensorboardX, ipython -- repo/unicore import-time deps (ipython: DrugCLIP-style
#                                leftover debug import in the task module; harmless once present).
#   chembl_webresource_client + requests -- on-instance ChEMBL actives/inactives + UniProt seq pull.
#   scikit-learn, scipy, pandas, tqdm, pyyaml -- panel build + AUROC.
# No mkfs/dd/rm of existing data. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== ligunity eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="ligunity"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# 19 targets x ~30-180 pairs x (Uni-Mol conformer + ESM2 seq encode) + an 8-iter Uni-Core build
# fallback risk -> generous watchdog.
( sleep 6000; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; the meta python3-venv alone did NOT
# pull it on a prior run -> `python3 -m venv` came up WITHOUT pip. Install python3.10-venv on its
# OWN line; ensurepip + the pip-version guard below are MANDATORY.
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip
PYV=$($PY -c "import sys;print(f'cp{sys.version_info.major}{sys.version_info.minor}')")
echo "python tag: $PYV"

# torch 2.0.0 cu118 FIRST — the combo Uni-Core publishes matching wheels for.
$PY -m pip install -q torch==2.0.0 --index-url https://download.pytorch.org/whl/cu118 2>&1 | tail -1
# Uni-Core from the matching release wheel (tag 0.0.3 -> file version 0.0.1). Check pip's own exit
# (not a piped tail's), then fall back to a source build.
UCWHL="https://github.com/dptech-corp/Uni-Core/releases/download/0.0.3/unicore-0.0.1+cu118torch2.0.0-${PYV}-${PYV}-linux_x86_64.whl"
if ! $PY -m pip install -q "$UCWHL"; then
  echo "[warn] unicore wheel install failed; building from source"
  git clone --depth 1 https://github.com/dptech-corp/Uni-Core /opt/Uni-Core 2>&1 | tail -1
  $PY -m pip install -q /opt/Uni-Core 2>&1 | tail -5
fi
# numpy<2 PIN (rdkit 2022.9.5 + unicore C-ext ABI). transformers/hf for the ESM2-35M protein tower.
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "transformers>=4.30,<4.46" "huggingface_hub>=0.24" \
    "rdkit==2022.9.5" lmdb scikit-learn scipy pandas tqdm pyyaml requests \
    ml_collections tensorboardX ipython gdown chembl_webresource_client 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# Clone LigUnity (Apache-2.0). The eval imports unimol/ from here and patches the ESM abs-path.
git clone --depth 1 https://github.com/IDEA-XL/LigUnity /opt/LigUnity 2>&1 | tail -2 || fail "clone-ligunity" 93
ls /opt/LigUnity/unimol/ /opt/LigUnity/vocab/ || echo "[warn] LigUnity layout unexpected"

# Pre-pull the ESM2-35M protein tower (the eval patches protein_ranking.py to this HF id).
export HF_HOME=/opt/hf_cache
$PY - <<'PYHF' || echo "[warn] ESM2-35M prefetch failed; model load will retry online"
import os
os.environ.setdefault("USE_TF","0"); os.environ.setdefault("USE_FLAX","0")
from transformers import AutoTokenizer, AutoModelForMaskedLM
m="facebook/esm2_t12_35M_UR50D"
AutoTokenizer.from_pretrained(m); AutoModelForMaskedLM.from_pretrained(m)
print("esm2-35M cached")
PYHF

# Checkpoint: clone fengb/LigUnity_protein_ranking from HF. Cache to S3 so reruns skip HF entirely.
mkdir -p /opt/ligunity_ckpt/protein_ranking
CKPT=/opt/ligunity_ckpt/protein_ranking/checkpoint.pt
# FIX #2 (2026-06-15): the S3-cache check must require a REAL binary (>1 MB). Run-1's old code
# cached the 134-byte LFS POINTER to S3, so the relaunch pulled the poisoned pointer from cache and
# short-circuited the fix#1 snapshot_download. Reject any cached file <1 MB so we re-download.
if aws s3 cp "s3://$BUCKET/$PREFIX/protein_ranking_checkpoint.pt" "$CKPT" 2>/dev/null && [ "$(stat -c%s "$CKPT" 2>/dev/null || echo 0)" -gt 1000000 ]; then
  echo "checkpoint from S3 cache ($(stat -c%s "$CKPT") bytes)"
else
  # FIX #1 (2026-06-15): a `git clone` of the HF repo yields a git-LFS POINTER .pt (~130-byte text
  # starting 'version https://git-lfs...') and git-lfs wasn't installed, so unicore load_checkpoint
  # got '_pickle.UnpicklingError: invalid load key, v'. Use the HF API snapshot_download as the
  # PRIMARY path (pulls the REAL LFS binary server-side, no git-lfs needed) + reject any .pt < 1 MB.
  $PY - <<'PYDL' || echo "[warn] hf snapshot_download failed"
import glob, os, shutil
from huggingface_hub import snapshot_download
d = snapshot_download("fengb/LigUnity_protein_ranking")
pts = [p for p in glob.glob(os.path.join(d, "**", "*.pt"), recursive=True) if os.path.getsize(p) > 1_000_000]
pts.sort(key=os.path.getsize, reverse=True)
if pts:
    os.makedirs("/opt/ligunity_ckpt/protein_ranking", exist_ok=True)
    shutil.copy(pts[0], "/opt/ligunity_ckpt/protein_ranking/checkpoint.pt")
    print("checkpoint via snapshot:", pts[0], os.path.getsize(pts[0]), "bytes")
else:
    print("[warn] no real (>1MB) .pt in snapshot")
PYDL
  if [ -s "$CKPT" ] && [ "$(stat -c%s "$CKPT" 2>/dev/null || echo 0)" -gt 1000000 ]; then
    aws s3 cp "$CKPT" "s3://$BUCKET/$PREFIX/protein_ranking_checkpoint.pt" >/dev/null 2>&1 || true
  else
    echo "[warn] checkpoint missing/pointer-sized after snapshot_download"
  fi
fi
[ -s "$CKPT" ] || fail "no-checkpoint" 94
echo "checkpoint: $CKPT ($(stat -c%s "$CKPT" 2>/dev/null || echo '?') bytes)"

# Stage the eval from S3 BEFORE the gate so the smoke test can drive the real LigUnity loader.
# (Panel is defined in the eval; ChEMBL/UniProt data fetched on-instance with per-target timeouts.)
aws s3 cp "s3://$BUCKET/$PREFIX/ligunity_eval.py" /opt/ligunity_eval.py || fail "dl-eval" 95

# FAIL-FAST gate: deps import + unicore + the LigUnity model build + checkpoint load + a 1-pair
# smoke score (sequence protein vs a benzene-ish conformer). If any of this fails, we bail before
# the 19-target loop instead of discovering it 20 minutes in.
export USE_TF=0 USE_FLAX=0
LIGUNITY_DIR=/opt/LigUnity LIGUNITY_CKPT="$CKPT" LIGUNITY_ARCH=protein_ranking \
LIGUNITY_ESM=facebook/esm2_t12_35M_UR50D HF_HOME=/opt/hf_cache \
$PY - <<'PYCHK' || fail "deps-or-smoke" 92
import os, sys
os.environ.setdefault("USE_TF","0"); os.environ.setdefault("USE_FLAX","0")
import numpy, torch, transformers, rdkit, lmdb, sklearn, requests
from rdkit import Chem
from rdkit.Chem import AllChem
from chembl_webresource_client.new_client import new_client
import unicore
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit/unicore C-ext ABI"
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "cuda", torch.cuda.is_available(),
      "rdkit", rdkit.__version__, "unicore", getattr(unicore, "__version__", "?"))
# Build the model the same way the eval does, then a 1-pair smoke score (drives the REAL loader).
import importlib.util
spec = importlib.util.spec_from_file_location("ligeval", "/opt/ligunity_eval.py")
lig = importlib.util.module_from_spec(spec); spec.loader.exec_module(lig)
L = lig.LigUnity()
assert L.is_sequence_path, "expected the pocket-free protein_ranking (sequence) path"
seq = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKR"
scores, labels, smis = L.score_target(seq, "SMOKE", ["c1ccccc1", "CCO"], ["O=C(O)c1ccccc1"])
assert len(scores) >= 2, f"smoke produced too few scores: {scores}"
print("smoke ok; scores", [round(s,4) for s in scores], "labels", labels)
PYCHK

echo "=== run ligunity eval $(date -u) ==="
export USE_TF=0 USE_FLAX=0
LIGUNITY_DIR=/opt/LigUnity LIGUNITY_CKPT="$CKPT" LIGUNITY_ARCH=protein_ranking \
  LIGUNITY_ESM=facebook/esm2_t12_35M_UR50D HF_HOME=/opt/hf_cache \
  OUT=/root/ligunity_out/ligunity_result.json $PY /opt/ligunity_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ligunity_out/ligunity_result.json ] && \
  aws s3 cp /root/ligunity_out/ligunity_result.json "s3://$BUCKET/$PREFIX/ligunity_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
