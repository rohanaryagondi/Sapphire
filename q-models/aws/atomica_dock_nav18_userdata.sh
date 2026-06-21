#!/bin/bash
# ATOMICA Nav1.8 binder-vs-decoy eval via FAST DOCKING (NO Boltz). g5.xlarge / DL AMI.
#
# Replaces the Boltz-based atomica_nav18_userdata.sh, whose Boltz/cuequivariance half
# was hard-blocked by the CUDA-13 toolchain on the current AWS DL AMI (see
# results/atomica_nav18_characterization.md). Option (c): dock the panel ligands into a
# REAL human Nav1.8 cryo-EM receptor (PDB 7WFR, A-803467/95T bound) with smina, then
# ATOMICA-embed the docked complexes. NO Boltz, NO cuequivariance, NO venv-with-boltz.
#
# TWO TOOLCHAINS:
#   DOCKING  — smina (static linux binary, AutoDock-Vina-based, CPU; no compile) + obabel
#     (OpenBabel, system apt pkg) for SMILES->3D->PDBQT and pose->PDB.
#   ATOMICA  — its OWN conda env (torch==2.1.1 +cu118, torch-scatter/cluster, e3nn,
#     rdkit-pypi, openbabel-wheel). This section is COPIED VERBATIM from the proven
#     atomica_nav18_userdata.sh STAGE B — that install half WORKED (env built, HF
#     checkpoints ada-f/ATOMICA downloaded + located, deps import OK).
#
# DL AMI gotchas honored (memory: aws-dlami-userdata-gotchas): conda-activate fails in
# userdata -> EXPLICIT python paths; EBS is AZ-locked (we use the 100 GB gp3 root, no
# EBS). Creds never traced/logged; sed-replaced __AKID__/__SECRET__. Self-terminates;
# TIGHT watchdog: sleep 3600 (60 min hard cap -> ~$1).
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== atomica DOCK nav18 eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="atomica_dock_nav18"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# TIGHT watchdog: docking 11 small molecules on CPU + ATOMICA embed is fast; 60 min hard
# cap keeps spend ~$1 on a g5.xlarge even if something hangs.
( sleep 3600; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
apt-get install -y python3-pip git wget curl openbabel >/dev/null 2>&1 || fail "apt-core" 90

# ======================================================================== DOCKING tools
# smina static linux binary (no compile). Try the canonical sourceforge release; the
# binary is self-contained. obabel comes from apt (installed above).
mkdir -p /opt/smina
wget -q "https://sourceforge.net/projects/smina/files/smina.static/download" -O /opt/smina/smina \
  || wget -q "https://downloads.sourceforge.net/project/smina/smina.static" -O /opt/smina/smina \
  || fail "dl-smina" 91
chmod +x /opt/smina/smina
/opt/smina/smina --version 2>&1 | head -2 || fail "smina-exec" 91
command -v obabel >/dev/null 2>&1 || fail "no-obabel" 91
obabel -V 2>&1 | head -1 || true

# ======================================================================== ATOMICA env
# COPIED VERBATIM from the proven atomica_nav18_userdata.sh STAGE B (this half worked).
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
# metrics + parquet libs (the eval runs sklearn/pandas in the ATOMICA env? No — the eval
# runs under the ATOMICA env interpreter; ensure numpy/sklearn/pandas/pyarrow present).
$ATOMICA_PY -m pip install -q numpy scikit-learn pandas pyarrow 2>&1 | tail -1 || fail "pip-metrics" 94

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
aws s3 cp "s3://$BUCKET/$PREFIX/atomica_dock_nav18_eval.py" /opt/atomica_dock_nav18_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panel" 95

echo "=== run atomica DOCK nav18 eval $(date -u) ==="
export USE_TF=0 USE_FLAX=0
mkdir -p /root/atomica_dock_nav18_work
# The eval runs UNDER the ATOMICA env interpreter (it needs numpy/sklearn/pandas there)
# and shells out to the same $ATOMICA_PY for process_pdbs/get_embeddings, plus calls the
# smina binary + obabel on PATH. Single env: no Boltz, no second torch build.
SMINA_BIN=/opt/smina/smina OBABEL_BIN=$(command -v obabel) \
  RECEPTOR_PDB_ID=7WFR REF_LIG_CODE=95T KEEP_CHAIN=A \
  SMINA_EXHAUSTIVENESS=4 SMINA_AUTOBOX_ADD=6 SMINA_CPU=4 \
  DOCK_TIMEOUT_S=600 PREP_TIMEOUT_S=600 \
  PANEL=/opt/crossmodal_panels.json PANEL_KEY=nav18 \
  ATOMICA_PY=$ATOMICA_PY ATOMICA_DIR=/opt/ATOMICA \
  ATOMICA_MODEL_CONFIG="$ATOMICA_CFG" ATOMICA_MODEL_WEIGHTS="$ATOMICA_WTS" \
  ATOMICA_EMBED_TIMEOUT_S=1800 \
  WORK=/root/atomica_dock_nav18_work \
  OUT=/tmp/atomica_dock_nav18_result.json \
  $ATOMICA_PY /opt/atomica_dock_nav18_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="

# Upload the result + the docking/atomica logs for forensics.
[ -f /tmp/atomica_dock_nav18_result.json ] && \
  aws s3 cp /tmp/atomica_dock_nav18_result.json "s3://$BUCKET/$PREFIX/atomica_dock_nav18_result.json" || echo "[warn] no result file"
[ -f /root/atomica_dock_nav18_work/atomica_process.log ] && \
  aws s3 cp /root/atomica_dock_nav18_work/atomica_process.log "s3://$BUCKET/$PREFIX/atomica_process.log" || true
[ -f /root/atomica_dock_nav18_work/atomica_embed.log ] && \
  aws s3 cp /root/atomica_dock_nav18_work/atomica_embed.log "s3://$BUCKET/$PREFIX/atomica_embed.log" || true
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
