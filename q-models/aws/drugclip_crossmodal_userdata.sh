#!/bin/bash
# DrugCLIP cross-modal eval (pocket<->molecule). Self-contained venv. Uni-Core framework +
# rdkit 2022.9.5 + GDrive checkpoint. NON-COMMERCIAL RESEARCH. No mkfs/dd/rm. Hardened: no creds in log.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== drugclip crossmodal start: $(date -u) ==="
set +x  # SECURITY
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="drugclip_crossmodal"
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
# torch 2.0.0 cu118 — the combo Uni-Core publishes matching wheels for.
$PY -m pip install -q torch==2.0.0 --index-url https://download.pytorch.org/whl/cu118 2>&1 | tail -1
# Uni-Core (DrugCLIP's framework) from the matching release wheel. NOTE: under tag 0.0.3 the
# wheel FILENAME is version 0.0.1 (tag != file version). Check pip's own exit (not a piped tail's),
# then fall back to source build if the wheel install fails.
UCWHL="https://github.com/dptech-corp/Uni-Core/releases/download/0.0.3/unicore-0.0.1+cu118torch2.0.0-${PYV}-${PYV}-linux_x86_64.whl"
if ! $PY -m pip install -q "$UCWHL"; then
  echo "[warn] unicore wheel install failed; building from source"
  git clone --depth 1 https://github.com/dptech-corp/Uni-Core /opt/Uni-Core 2>&1 | tail -1
  $PY -m pip install -q /opt/Uni-Core 2>&1 | tail -5
fi
# PIN numpy<2: rdkit==2022.9.5 + unicore(torch2.0.0) are built against NumPy 1.x; NumPy 2.x
# breaks their C-ext ABI ('_ARRAY_API not found' -> segfault on `import rdkit.Chem.AllChem`).
# ipython: DrugCLIP's unimol/tasks/drugclip.py has a leftover `from IPython import embed` debug
# import at module top, so the task fails to register without it.
$PY -m pip install -q "rdkit==2022.9.5" lmdb scikit-learn "numpy<2" pandas gdown ml_collections tensorboardX ipython 2>&1 | tail -2
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: ensure nothing upgraded numpy back to 2.x
$PY -c "import numpy,torch,unicore,rdkit,lmdb,sklearn; from rdkit.Chem import AllChem; print('deps ok; numpy', numpy.__version__, 'cuda', torch.cuda.is_available(), 'rdkit', rdkit.__version__)" || fail "deps" 92

git clone --depth 1 https://github.com/bowen-gao/DrugCLIP /opt/DrugCLIP 2>&1 | tail -2 || fail "clone" 93

# Checkpoint: download ONLY checkpoint_best.pt by its direct file id (in the GDrive 'retrieval/'
# subfolder). gdown --folder pulled multi-GB dataset zips (dude/pcba/pdbbind) and was slow+flaky;
# the single-file id is fast + reliable. Cache to S3 so reruns skip GDrive entirely.
mkdir -p /opt/drugclip_ckpt; CKPT=/opt/drugclip_ckpt/checkpoint_best.pt
if aws s3 cp "s3://$BUCKET/$PREFIX/checkpoint_best.pt" "$CKPT" 2>/dev/null && [ -s "$CKPT" ]; then
  echo "checkpoint from S3 cache"
else
  $PY -m gdown 1i87thnbNk8qeLF_tLx_BzelTukWbHaTR -O "$CKPT" 2>&1 | tail -3
  [ -s "$CKPT" ] && aws s3 cp "$CKPT" "s3://$BUCKET/$PREFIX/checkpoint_best.pt" >/dev/null 2>&1 || true
fi
[ -s "$CKPT" ] || fail "no-checkpoint" 94
echo "checkpoint: $CKPT ($(stat -c%s "$CKPT" 2>/dev/null || echo '?') bytes)"

aws s3 cp "s3://$BUCKET/$PREFIX/drugclip_crossmodal_eval.py" /opt/drugclip_crossmodal_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/drugclip_pocket_prep.py" /opt/drugclip_pocket_prep.py || fail "dl-prep" 96
aws s3 cp "s3://$BUCKET/$PREFIX/crossmodal_panels.json" /opt/crossmodal_panels.json || fail "dl-panels" 97

echo "=== prep pockets (AlphaFold + literature site) $(date -u) ==="
$PY /opt/drugclip_pocket_prep.py --mode residues --out /opt/drugclip_pockets 2>&1 | tail -10

echo "=== run DrugCLIP eval $(date -u) ==="
PANELS=/opt/crossmodal_panels.json POCKET_MANIFEST=/opt/drugclip_pockets/pocket_manifest.json \
  POCKET_DIR=/opt/drugclip_pockets DRUGCLIP_DIR=/opt/DrugCLIP DRUGCLIP_CKPT="$CKPT" \
  OUT=/root/drugclip_out/drugclip_crossmodal_result.json $PY /opt/drugclip_crossmodal_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/drugclip_out/drugclip_crossmodal_result.json ] && \
  aws s3 cp /root/drugclip_out/drugclip_crossmodal_result.json "s3://$BUCKET/$PREFIX/drugclip_crossmodal_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
