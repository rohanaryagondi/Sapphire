#!/bin/bash
# CardioGenAI tri-channel cardiac characterization (Track 5 tox, overnight AWS). Self-contained venv
# (conda-activate does NOT work in userdata -> EXPLICIT /opt/venv/bin/python). MIT license.
# PROVEN CardioGenAI toolchain: pytorch 2.1.0 cu121 + torch-geometric 2.4.0 + rdkit 2023.03.3 (numpy<2).
# NOTE on torch version: CardioGenAI ships PLAIN torch.save state-dicts (.pt, with training metadata),
#   NOT HF .bin -> the "torch>=2.6 for .bin" rule does NOT apply. We pin torch 2.1.x (cu121) so torch.load
#   defaults to weights_only=False and loads these metadata-bearing dicts (torch>=2.6 would flip the default
#   to weights_only=True and FAIL on them). No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== cardiogenai characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="cardiogenai"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
# torch 2.1.0 + cu121 (CardioGenAI's pinned stack; loads its plain-dict .pt state dicts with weights_only=False default).
$PY -m pip install -q torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1 || fail "torch" 92
# torch-geometric (pyg) 2.4.0 + its cu121 sparse/scatter ops, built against torch 2.1.0.
$PY -m pip install -q torch-geometric==2.4.0 2>&1 | tail -1
$PY -m pip install -q pyg-lib torch-scatter torch-sparse torch-cluster \
    -f https://data.pyg.org/whl/torch-2.1.0+cu121.html 2>&1 | tail -2 || echo "[warn] pyg-ext wheels (eval guards graph-feature failures)"
# rest of CardioGenAI deps + our eval deps. numpy<2 is implied by rdkit 2023.03.3 but pin explicitly.
$PY -m pip install -q "rdkit==2023.3.3" "numpy<2" pandas scikit-learn transformers h5py \
    tqdm gdown pyyaml PyTDC 2>&1 | tail -3 || fail "deps" 93
# CardioGenAI's src/Discriminator.py does `from openbabel import openbabel, pybel`. openbabel-wheel is a
# prebuilt manylinux wheel that ships exactly that module (no system libopenbabel / swig compile needed).
$PY -m pip install -q openbabel-wheel 2>&1 | tail -2 || $PY -m pip install -q openbabel 2>&1 | tail -2 || echo "[warn] openbabel install failed"
$PY -c "import torch,torch_geometric,rdkit,numpy,pandas,transformers,gdown,tdc; from rdkit.Chem import AllChem; from openbabel import openbabel, pybel; print('deps ok; torch',torch.__version__,'cuda',torch.cuda.is_available(),'np',numpy.__version__,'obabel ok')" || fail "deps-import" 94

# Clone CardioGenAI (MIT). Discriminative .pt heads + bidirectional transformer params are COMMITTED.
git clone --depth 1 https://github.com/gregory-kyro/CardioGenAI /opt/CardioGenAI 2>&1 | tail -2 || fail "clone" 95
# Verify the committed discriminative checkpoints are present (the whole point of choosing this repo).
ls -la /opt/CardioGenAI/model_parameters/discriminative_model_parameters/ || fail "no-disc-weights" 96
ls -la /opt/CardioGenAI/model_parameters/transformer_model_parameters/ || echo "[warn] no bidir transformer dir"

# The ONE required download: prepared_transformer_data.csv (full ~5M SMILES) -> rebuilds the data-dependent
# char-vocab the trained transformer embeddings are tied to. gdown by file id (verified from README).
mkdir -p /opt/CardioGenAI/data/prepared_transformer_datasets
$PY -m gdown "1l2Osk7zFj4rTyrjAi7EJ1GMrsYMbcRHI" -O /opt/CardioGenAI/data/prepared_transformer_datasets/prepared_transformer_data.csv 2>&1 | tail -3
# fallback to the fuzzy url form if the bare-id form hits a redirect/quota
if [ ! -s /opt/CardioGenAI/data/prepared_transformer_datasets/prepared_transformer_data.csv ]; then
  $PY -m gdown --fuzzy "https://drive.google.com/file/d/1l2Osk7zFj4rTyrjAi7EJ1GMrsYMbcRHI/view?usp=drive_link" \
    -O /opt/CardioGenAI/data/prepared_transformer_datasets/prepared_transformer_data.csv 2>&1 | tail -3 || true
fi
ls -la /opt/CardioGenAI/data/prepared_transformer_datasets/ || true
[ -s /opt/CardioGenAI/data/prepared_transformer_datasets/prepared_transformer_data.csv ] || echo "[warn] transformer CSV missing -> transformer-feature path will fail; eval sections are guarded"

aws s3 cp "s3://$BUCKET/$PREFIX/cardiogenai_eval.py" /opt/cardiogenai_eval.py || fail "dl-eval" 97
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 98

echo "=== run CardioGenAI characterization $(date -u) ==="
PANELS=/opt/crossmodal_panels.json OUT=/root/cardiogenai_out/cardiogenai_result.json \
  CG_DIR=/opt/CardioGenAI $PY /opt/cardiogenai_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/cardiogenai_out/cardiogenai_result.json ] && \
  aws s3 cp /root/cardiogenai_out/cardiogenai_result.json "s3://$BUCKET/$PREFIX/cardiogenai_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
