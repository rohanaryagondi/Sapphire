#!/bin/bash
# MissION ion-channel GoF/LoF characterization (Quiver variant-effect, overnight AWS). Self-contained venv
# (conda-activate does NOT work in userdata -> EXPLICIT /opt/venv/bin/python).
#
# RESEARCH NOTE (drives the toolchain): MissION (medRxiv 2025.10.16.25337735) ships NO public GitHub repo
#   and NO downloadable checkpoint -- it is reachable only through the web portal
#   www.synaptica.nl/variant-interpreter (no batch API). So there is NOTHING to git-clone or torch.load for
#   MissION itself. The eval is built around the paper's OWN reference model, funNCion
#   (https://github.com/heyhen/funNCion, Apache-2.0), which ships the real labelled GoF/LoF ion-channel
#   variant tables (SupplementaryTable_S1, 1008 functional GoF/LoF variants across SCN/Nav + CACNA1 -- exactly
#   Quiver's channels), and scores those variants with a generic-pLM baseline (ESM-2 650M masked-marginal LLR
#   via transformers). The MissION section is attempted-but-guarded inside the eval; absent a local artifact it
#   SKIPs cleanly (no fabricated numbers).
#
# TORCH version: funNCion data are plain TSV (no checkpoint to load); ESM-2 650M is loaded from HuggingFace via
#   transformers (.safetensors). No pinned-torch trap from MissION (no weights exist). We install a modern
#   torch>=2.6 cu124 (matches the safetensors ESM-2 load; weights_only default is irrelevant for safetensors).
# No mkfs/dd/rm. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== mission (ion-channel GoF/LoF) characterization start: $(date -u) ==="
set +x
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="mission"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
( sleep 4200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || echo "[warn] no GPU driver -> will FORCE_CPU (ESM-2 650M masked-marginal runs on CPU, just slower)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git >/dev/null 2>&1
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
# modern torch cu124 (loads ESM-2 650M safetensors via transformers). If GPU absent -> FORCE_CPU later.
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1 || fail "torch" 92
# CORE deps (MUST succeed): transformers for ESM-2 + numpy<2 + the usual. (fair-esm not needed -- we load
# ESM-2 through transformers AutoModelForMaskedLM, which is the verified path in the eval.)
$PY -m pip install -q "transformers>=4.40" "numpy<2" scikit-learn scipy pandas tokenizers safetensors \
    huggingface_hub 2>&1 | tail -3 || fail "deps" 93
# deps GATE = the eval's hard requirements (torch + transformers + numpy). MissION/funNCion need nothing else.
$PY -c "import torch, transformers, numpy, sklearn; from transformers import AutoModelForMaskedLM, AutoTokenizer; print('deps ok; torch',torch.__version__,'cuda',torch.cuda.is_available(),'np',numpy.__version__,'tfm',transformers.__version__)" || fail "deps-import" 94
export FORCE_CPU=0
$PY -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || export FORCE_CPU=1
echo "FORCE_CPU=$FORCE_CPU"

# "git clone MissION on-instance" -> MissION has no repo; clone funNCion (the eval's actual data substrate)
# so the variant TSV is present locally (the eval also has a raw.githubusercontent fallback for DATA_URL).
git clone --depth 1 https://github.com/heyhen/funNCion /opt/funNCion 2>&1 | tail -2 || echo "[warn] funNCion clone failed -> eval falls back to DATA_URL fetch"
ls -la /opt/funNCion/SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt 2>/dev/null || echo "[warn] S1 TSV not at expected path -> eval will fetch DATA_URL"

# Optional: a local MissION artifact, IF a launcher ever stages one to S3 (none public today). Best-effort.
mkdir -p /opt/mission_artifact
aws s3 cp "s3://$BUCKET/$PREFIX/mission_artifact/" /opt/mission_artifact/ --recursive 2>/dev/null && \
  ls -la /opt/mission_artifact/ || echo "[info] no MissION artifact staged in S3 -> MissION section will SKIP (expected; no public weights)"

aws s3 cp "s3://$BUCKET/$PREFIX/mission_eval.py" /opt/mission_eval.py || fail "dl-eval" 97

echo "=== run mission characterization $(date -u) ==="
# DATA_TSV points at the cloned funNCion table; DATA_URL is the fallback the eval uses if that's absent.
# MISSION_DIR is set only if an artifact was staged (dir non-empty); otherwise left empty -> clean SKIP.
MDIR=""
[ -n "$(ls -A /opt/mission_artifact 2>/dev/null)" ] && MDIR=/opt/mission_artifact
FORCE_CPU=$FORCE_CPU OUT=/root/mission_out/mission_result.json \
  DATA_TSV=/opt/funNCion/SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt \
  ESM2_MODEL=facebook/esm2_t33_650M_UR50D \
  MISSION_DIR="$MDIR" \
  $PY /opt/mission_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/mission_out/mission_result.json ] && \
  aws s3 cp /root/mission_out/mission_result.json "s3://$BUCKET/$PREFIX/mission_result.json" || echo "[warn] no result"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
