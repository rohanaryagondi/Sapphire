#!/bin/bash
# ATOMICA Nav1.8 binder-vs-decoy eval (CANDIDATE NEW TRACK: structural interaction embedding).
# Decisive question: does ATOMICA's interface embedding carry CNS binder signal BEYOND
# Boltz-2's own affinity readout? Two-stage, TWO ISOLATED ENVS (torch builds must not mix):
#
#   STAGE A — Boltz-2 co-fold (Nav1.8 + each ligand SMILES -> PDB complex). Reuses the
#     PROVEN Boltz stack from aws/boltz_cns_userdata.sh VERBATIM:
#       pip install boltz
#       cuequivariance-torch==0.10.0          (the triangle-ops wrapper Boltz imports)
#       cuequivariance-ops-cu13-torch         (THE CUDA kernels; cu12 fallback. Boltz
#                                              crashes ModuleNotFoundError cuequivariance_ops_torch
#                                              on large pair sizes without this — gotcha #1)
#     Boltz weights (~10 GB) + ColabFold MSA download on first complex; the eval's 3600 s
#     preflight covers the cold path, 900 s/complex after. Boltz venv = --system-site-packages
#     so the AMI's CUDA-prebuilt torch is reused (NOT a fresh multi-GB torch install).
#
#   STAGE B — ATOMICA embed, in ITS OWN conda/mamba env (torch==2.1.1, torch-scatter,
#     torch-cluster +cu118; rdkit-pypi, openbabel-wheel, e3nn — per ATOMICA pyproject.toml).
#     The eval shells out to $ATOMICA_PY so ATOMICA's torch 2.1.1 NEVER shares a process
#     with Boltz's torch. Structures pass between stages as FILES (PDB + a CSV index).
#     Weights pulled from HF: `hf download ada-f/ATOMICA --include ATOMICA_checkpoints/pretrain/**`.
#
# DL AMI gotchas honored (memory: aws-dlami-userdata-gotchas): conda-activate fails in
# userdata -> EXPLICIT python paths; EBS is AZ-locked (we use the 100 GB gp3 root, no EBS).
# Creds never traced/logged; sed-replaced __AKID__/__SECRET__ then shred'd. Self-terminates;
# watchdog 9000 s (folding 11 complexes + ATOMICA embed is the slowest job in this repo).
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== atomica nav18 eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="atomica_nav18"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# Slowest job in the repo: 11 Boltz co-folds (~10 GB cold weights + MSA queue) THEN a
# second-env ATOMICA process+embed. Watchdog 9000 s (2.5 h).
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90

# ======================================================================== STAGE A env
# Boltz venv with --system-site-packages (reuse AMI CUDA-prebuilt torch). EXPLICIT path.
python3 -m venv --system-site-packages /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

$PY -m pip install -q boltz 2>&1 | tail -2 || fail "pip-boltz" 92
$PY -m pip install -q "cuequivariance-torch==0.10.0" 2>&1 | tail -1 || echo "[warn] cuequivariance-torch pin failed; trying unpinned"
# THE kernels (gotcha #1). AMI is CUDA 13 -> cu13 first; cu12 fallback (the two real builds).
$PY -m pip install -q cuequivariance-ops-cu13-torch 2>&1 | tail -1 \
  || $PY -m pip install -q cuequivariance-ops-cu12-torch 2>&1 | tail -1 \
  || echo "[warn] BOTH cuequivariance-ops CUDA builds failed to install"
$PY - <<'PYK' || echo "[warn] cuequivariance kernel import FAILED — Boltz may crash on large pair sizes (Nav1.8 ~1956 aa). See gotcha #1."
from cuequivariance_torch.primitives.triangle import triangle_multiplicative_update
print("cuequivariance kernel import OK")
PYK

# Boltz-side data deps: numpy<2 (rdkit C-ext ABI), pyyaml (YAML emit), gemmi (CIF->PDB
# fallback if Boltz ever emits cif), sklearn/scipy (metrics run in THIS venv).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q pyyaml gemmi pandas pyarrow scikit-learn scipy 2>&1 | tail -2 || fail "pip-data" 92
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin

[ -x /opt/venv/bin/boltz ] || fail "no-boltz-bin" 92   # boltz CLI is in the venv, not global PATH
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, yaml, pandas, sklearn
import importlib.metadata as im
print("boltz-env ok; numpy", numpy.__version__, "torch", torch.__version__,
      "cuda", torch.cuda.is_available(), "boltz", im.version("boltz"))
assert torch.cuda.is_available(), "torch.cuda.is_available() is False"
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# ======================================================================== STAGE B env
# ATOMICA in its OWN env (torch 2.1.1 +cu118). Use Miniconda/mamba per ATOMICA's own
# install_atomica_conda.sh; if conda absent on the AMI we bootstrap Miniforge. EXPLICIT
# env path (no `conda activate` in userdata). ATOMICA needs torch==2.1.1 + PyG cu118
# wheels (torch-scatter/torch-cluster from the pyg find-links) + e3nn + rdkit-pypi +
# openbabel-wheel + biotite + the rest of pyproject.toml.
ATOMICA_ENV=/opt/atomica-env
ATOMICA_PY=$ATOMICA_ENV/bin/python
if ! command -v conda >/dev/null 2>&1 && [ ! -x /opt/conda/bin/conda ]; then
  wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda || fail "miniforge" 93
fi
CONDA=/opt/conda/bin/conda
[ -x "$CONDA" ] || CONDA=$(command -v conda)
"$CONDA" create -y -p $ATOMICA_ENV python=3.11 >/dev/null 2>&1 || fail "atomica-env-create" 93
$ATOMICA_PY -m pip install -q --upgrade pip
# torch 2.1.1 + cu118 (matches ATOMICA pyproject pin) from the cu118 index.
$ATOMICA_PY -m pip install -q torch==2.1.1 --index-url https://download.pytorch.org/whl/cu118 2>&1 | tail -1 || fail "atomica-torch" 93
# PyG geometric deps from the matching find-links (per ATOMICA install_atomica_conda.sh).
$ATOMICA_PY -m pip install -q torch-scatter==2.1.2 torch-cluster==1.6.3 \
  --find-links https://pytorch-geometric.com/whl/torch-2.1.1+cu118.html 2>&1 | tail -2 || fail "atomica-pyg" 93

# Clone ATOMICA + pip install -e . (pulls remaining pyproject deps: e3nn, rdkit-pypi,
# openbabel-wheel, biotite, pandas, pyarrow, scikit-learn, etc.).
git clone --depth 1 https://github.com/mims-harvard/ATOMICA.git /opt/ATOMICA 2>&1 | tail -1 || fail "git-atomica" 94
$ATOMICA_PY -m pip install -q -e /opt/ATOMICA 2>&1 | tail -3 || fail "pip-atomica" 94
# huggingface_hub for the weights pull.
$ATOMICA_PY -m pip install -q "huggingface_hub[cli]" 2>&1 | tail -1 || fail "pip-hf" 94

# Pretrained checkpoints from HF (pretrain config + weights only). hf CLI ships with the hub pkg.
$ATOMICA_ENV/bin/hf download ada-f/ATOMICA --repo-type model \
  --local-dir /opt/ATOMICA/checkpoints --include "ATOMICA_checkpoints/pretrain/**" 2>&1 | tail -3 \
  || $ATOMICA_PY -m huggingface_hub.commands.huggingface_cli download ada-f/ATOMICA --repo-type model \
       --local-dir /opt/ATOMICA/checkpoints --include "ATOMICA_checkpoints/pretrain/**" 2>&1 | tail -3 \
  || fail "hf-download" 94

# Locate the pretrain config + weights (filenames per tutorials/1_get_embeddings README).
ATOMICA_CFG=$(find /opt/ATOMICA/checkpoints -name "*model_config.json" -path "*pretrain*" | head -1)
ATOMICA_WTS=$(find /opt/ATOMICA/checkpoints -name "*model_weights.pt" -path "*pretrain*" | head -1)
echo "ATOMICA cfg=$ATOMICA_CFG wts=$ATOMICA_WTS"
[ -n "$ATOMICA_CFG" ] && [ -n "$ATOMICA_WTS" ] || fail "atomica-ckpt-missing" 94

# FAIL-FAST gate for the ATOMICA env: import + torch CUDA + the embed entrypoint exists.
$ATOMICA_PY - <<'PYCHK2' || fail "atomica-deps" 94
import torch, atomica
from atomica.get_embeddings import cli
from atomica.data import process_pdbs
print("atomica-env ok; torch", torch.__version__, "cuda", torch.cuda.is_available())
assert torch.cuda.is_available(), "atomica env: torch.cuda.is_available() is False"
PYCHK2

# ============================================================================ stage in
# Launcher uploads BOTH the eval + the panel to s3://$BUCKET/$PREFIX/.
aws s3 cp "s3://$BUCKET/$PREFIX/atomica_nav18_eval.py" /opt/atomica_nav18_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panel" 95

echo "=== run atomica nav18 eval $(date -u) ==="
export USE_TF=0 USE_FLAX=0
mkdir -p /root/boltz_cache /root/boltz_out /root/atomica_nav18_work
# The eval orchestrates BOTH envs: it runs `boltz` from the boltz venv (on PATH via
# $PY's bin) and shells out to $ATOMICA_PY for the ATOMICA process+embed steps.
PATH="/opt/venv/bin:$PATH" \
PANEL=/opt/crossmodal_panels.json PANEL_KEY=nav18 \
  BOLTZ_BIN=/opt/venv/bin/boltz BOLTZ_CACHE=/root/boltz_cache BOLTZ_OUT=/root/boltz_out \
  PREFLIGHT_TIMEOUT_S=3600 PAIR_TIMEOUT_S=900 BOLTZ_SAMPLING_STEPS=100 \
  ATOMICA_PY=$ATOMICA_PY ATOMICA_DIR=/opt/ATOMICA \
  ATOMICA_MODEL_CONFIG="$ATOMICA_CFG" ATOMICA_MODEL_WEIGHTS="$ATOMICA_WTS" \
  ATOMICA_EMBED_TIMEOUT_S=1800 \
  WORK=/root/atomica_nav18_work \
  OUT=/tmp/atomica_nav18_result.json \
  $PY /opt/atomica_nav18_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="

# Upload the result + the boltz/atomica logs for forensics.
[ -f /tmp/atomica_nav18_result.json ] && \
  aws s3 cp /tmp/atomica_nav18_result.json "s3://$BUCKET/$PREFIX/atomica_nav18_result.json" || echo "[warn] no result file"
[ -f /root/atomica_nav18_work/atomica_process.log ] && \
  aws s3 cp /root/atomica_nav18_work/atomica_process.log "s3://$BUCKET/$PREFIX/atomica_process.log" || true
[ -f /root/atomica_nav18_work/atomica_embed.log ] && \
  aws s3 cp /root/atomica_nav18_work/atomica_embed.log "s3://$BUCKET/$PREFIX/atomica_embed.log" || true
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
