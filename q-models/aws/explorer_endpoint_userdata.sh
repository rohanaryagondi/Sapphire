#!/bin/bash
# Quiver Explorer GPU inference endpoint — boots the FastAPI model server.
# Injected by launch_explorer_endpoint.py: __BUCKET__ __PREFIX__ __MAXMIN__
# Self-contained venv (DLAMI for the driver; our own pip torch for reliability).
# No mkfs/dd/rm of existing data. Hard max-lifetime watchdog protects the budget.
exec > >(tee -a /var/log/explorer.log) 2>&1
echo "=== explorer endpoint start: $(date -u) ==="
BUCKET="__BUCKET__"; PREFIX="__PREFIX__"; MAXMIN="__MAXMIN__"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)

# Budget backstop: hard self-terminate after MAXMIN minutes no matter what, so a
# forgotten endpoint can't run up the bill. (Instance shutdown-behavior=terminate.)
( sleep $((MAXMIN*60)); echo "MAX-LIFETIME WATCHDOG $(date -u)"; shutdown -h now ) &

nvidia-smi || { echo "no GPU driver"; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1; apt-get install -y python3-venv python3-pip git >/dev/null 2>&1
python3 -m venv /opt/venv
PY=/opt/venv/bin/python
$PY -m pip install -q --upgrade pip
# torch (cu121 for the DLAMI driver), the web layer, and the model stack.
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1
$PY -m pip install -q fastapi "uvicorn[standard]" pydantic \
    "transformers>=4.45" accelerate "huggingface_hub>=0.24" \
    numpy scikit-learn joblib sentencepiece rdkit-pypi 2>&1 | tail -2
$PY -c "import torch,fastapi,transformers,sklearn,rdkit; print('deps ok; cuda', torch.cuda.is_available())"

# Bring the server code + (optional) trained artifacts down from our bucket.
mkdir -p /opt/explorer/artifacts
# The server + helpers (committed in the repo's aws/ dir) are uploaded to S3 by the
# operator before launch, e.g.:
#   aws s3 cp aws/explorer_inference_server.py s3://$BUCKET/$PREFIX/
#   aws s3 cp aws/boltz_runner.py              s3://$BUCKET/$PREFIX/
#   aws s3 cp -r artifacts/                     s3://$BUCKET/$PREFIX/artifacts/   (probes, ref lib)
aws s3 cp "s3://$BUCKET/$PREFIX/explorer_inference_server.py" /opt/explorer/ 2>&1 | tail -1
aws s3 cp "s3://$BUCKET/$PREFIX/boltz_runner.py" /opt/explorer/ 2>/dev/null || echo "[warn] boltz_runner not staged (DTI/structure/selectivity will 503)"
aws s3 cp --recursive "s3://$BUCKET/$PREFIX/artifacts/" /opt/explorer/artifacts/ 2>/dev/null || echo "[info] no artifacts staged (probe-backed endpoints will report 'probe missing')"

# PROTON KG (Track 6) — optional; clone + download if Track 6 is wanted.
if [ "${EXPLORER_WITH_PROTON:-0}" = "1" ]; then
  git clone --depth 1 https://github.com/mims-harvard/PROTON /opt/PROTON 2>&1 | tail -1
fi

export USE_TF=0 USE_FLAX=0 EXPLORER_ARTIFACTS=/opt/explorer/artifacts PROTON_DIR=/opt/PROTON
cd /opt/explorer
echo "=== starting inference server on :8080 $(date -u) ==="
# Foreground under nohup so the instance stays up serving until the watchdog or
# an operator terminates it. Health: GET http://<dns>:8080/health
nohup $PY -m uvicorn explorer_inference_server:app --host 0.0.0.0 --port 8080 \
    >> /var/log/explorer.log 2>&1 &
sleep 8
curl -s http://127.0.0.1:8080/health || echo "[warn] server not yet healthy; check /var/log/explorer.log"
echo "=== endpoint ready (or starting). Set EXPLORER_AWS_ENDPOINT=http://<public-dns>:8080/predict ==="
# Keep userdata alive so the script's background server isn't reaped at boot-script exit.
wait
