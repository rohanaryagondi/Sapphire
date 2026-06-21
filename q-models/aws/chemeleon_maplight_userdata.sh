#!/bin/bash
# CheMeleon + MapLight Track-4 ADMET characterization (overnight). Self-contained venv at /opt/venv via
# EXPLICIT python path (conda-activate does NOT work in userdata). CheMeleon=CC0, MapLight=MIT.
# torch>=2.6 cu124 (CheMeleon ships a .pt; weights_only load -- safe either way, install new torch anyway).
# numpy<2 pinned (rdkit==2022.9.5 C-ext ABI). No mkfs/dd/rm. Creds redacted from log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== chemeleon+maplight characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="chemeleon_maplight"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver (CPU fallback: CheMeleon featurize + CatBoost both run on CPU)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# chemprop 2.x (CheMeleon's API) requires Python>=3.11; the DLAMI default python3 is 3.10 (pip then only
# offers chemprop<=1.6.1 -> CheMeleon unloadable). Install 3.11 for the venv; fall back to 3.10 if absent.
apt-get install -y python3.11 python3.11-venv python3-pip git >/dev/null 2>&1
python3.11 -m venv /opt/venv 2>/dev/null || python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -c "import sys; print('venv python', sys.version.split()[0])"
# torch cu124 first (pins the build CheMeleon's .pt loads against).
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
# CORE deps (MUST succeed): MapLight (catboost+rdkit) + datasets + MolFormer baseline. numpy<2 for rdkit ABI.
$PY -m pip install -q catboost pytdc scikit-learn scipy "numpy<2" pandas "rdkit==2022.9.5" \
    "transformers==4.48.1" protobuf sentencepiece 2>&1 | tail -3
# CheMeleon (BEST-EFFORT, isolated): chemprop 2.x. If it can't install (py<3.11), the eval's try/except
# skips CheMeleon and MapLight + MolFormer baseline still bank a full result.
$PY -m pip install -q "chemprop>=2.2" 2>&1 | tail -2 || echo "[warn] chemprop install failed -> CheMeleon skipped"
# deps GATE = CORE only (chemprop/CheMeleon is optional + guarded inside the eval).
$PY -c "import torch, catboost, sklearn, rdkit, tdc, numpy; from rdkit.Avalon.pyAvalonTools import GetAvalonCountFP; from rdkit.Chem import rdReducedGraphs; print('core deps ok; cuda', torch.cuda.is_available(), 'numpy', numpy.__version__)" || fail "deps" 92
$PY -c "import chemprop; print('chemprop', chemprop.__version__)" 2>/dev/null || echo "[info] chemprop absent -> CheMeleon skipped; MapLight + MolFormer proceed"

aws s3 cp "s3://$BUCKET/$PREFIX/chemeleon_maplight_eval.py" /opt/chemeleon_maplight_eval.py || fail "dl-eval" 94

echo "=== run chemeleon+maplight characterization $(date -u) ==="
OUT=/root/cm_out/chemeleon_maplight_result.json SEED=1 \
  $PY /opt/chemeleon_maplight_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/cm_out/chemeleon_maplight_result.json ] && \
  aws s3 cp /root/cm_out/chemeleon_maplight_result.json "s3://$BUCKET/$PREFIX/chemeleon_maplight_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
