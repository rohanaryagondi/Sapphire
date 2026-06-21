#!/bin/bash
# MapLight held-out BBB validation on B3DB (Track-4 follow-up). Self-contained venv at /opt/venv via
# EXPLICIT python path (conda-activate does NOT work in userdata). MapLight=MIT, B3DB=CC0.
# No chemprop needed -> python3.10 is fine (simpler than Phase 1). torch>=2.6 cu124 for MolFormer-XL.
# numpy<2 pinned (rdkit==2022.9.5 C-ext ABI). No mkfs/dd/rm. Creds redacted from log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== maplight b3db held-out validation start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="maplight_b3db"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver (CPU fallback: MapLight CatBoost on CPU; MolFormer-XL embed on CPU)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# No chemprop here -> the DLAMI default python3 (3.10) is fine. Install venv tooling; fall back gracefully.
apt-get install -y python3-venv python3-pip git curl >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -c "import sys; print('venv python', sys.version.split()[0])"
# torch cu124 first (for MolFormer-XL).
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
# CORE deps (MUST succeed): MapLight (catboost+rdkit), MolFormer-XL (transformers), datasets, B3DB fetch.
# numpy<2 for rdkit ABI.
$PY -m pip install -q catboost "rdkit==2022.9.5" "numpy<2" pandas scikit-learn pytdc requests \
    "transformers==4.48.1" protobuf sentencepiece 2>&1 | tail -3
# deps GATE: all core deps must import (MolFormer-XL + MapLight featurizer paths included).
$PY -c "import torch, catboost, sklearn, rdkit, tdc, pandas, requests, numpy, transformers; from rdkit.Avalon.pyAvalonTools import GetAvalonCountFP; from rdkit.Chem import rdReducedGraphs; from rdkit.Chem.rdMolDescriptors import GetHashedMorganFingerprint; print('core deps ok; cuda', torch.cuda.is_available(), 'numpy', numpy.__version__, 'transformers', transformers.__version__)" || fail "deps" 92

# Pre-fetch B3DB classification TSV (the eval also downloads it; this is a backup so a flaky GitHub
# fetch during the run still has a local copy at /root/B3DB_classification.tsv).
B3DB_URL="https://raw.githubusercontent.com/theochem/B3DB/main/B3DB/B3DB_classification.tsv"
curl -fsSL "$B3DB_URL" -o /root/B3DB_classification.tsv \
  && echo "[ok] B3DB pre-fetched ($(wc -l < /root/B3DB_classification.tsv) lines)" \
  || echo "[warn] B3DB pre-fetch failed -> eval will fetch from URL"

# Stage the eval (the launcher uploads it to s3://$BUCKET/$PREFIX/maplight_b3db_eval.py).
aws s3 cp "s3://$BUCKET/$PREFIX/maplight_b3db_eval.py" /opt/maplight_b3db_eval.py || fail "dl-eval" 94

echo "=== run maplight b3db held-out validation $(date -u) ==="
OUT=/root/ml_out/maplight_b3db_result.json SEED=1 B3DB_LOCAL=/root/B3DB_classification.tsv \
  $PY /opt/maplight_b3db_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ml_out/maplight_b3db_result.json ] && \
  aws s3 cp /root/ml_out/maplight_b3db_result.json "s3://$BUCKET/$PREFIX/maplight_b3db_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
