#!/bin/bash
# Boltz-2 pathway-neighbor panel — overnight run.
# 23 complexes across PKM1, LDHA, mTOR-kinase, PPARA-LBD, RXRA-LBD.
# Each target gets 1 positive control + N putatives + 2 decoys.
# Tests James's hypothesis (2026-06-11 email): the DFP signature for
# QS0113172/QS0069567 may reflect pathway-level phenocopy, not direct binding.

# Hard cap: 4 h. g6e.2xlarge $2.24/hr × 4 = $8.96 worst case (cap is $15).
( sleep 14400 && shutdown -h now ) &
exec > /var/log/userdata.log 2>&1
set -x
date
echo "===== ROHAN-BOLTZ-PATHWAY USERDATA START ====="

mkdir -p /home/ubuntu
cat > /home/ubuntu/urls.json <<'URL_EOF'
__URLS_JSON__
URL_EOF
chown ubuntu:ubuntu /home/ubuntu/urls.json
python3 -c "import json; print(json.load(open('/home/ubuntu/urls.json'))['progress.log'])" > /home/ubuntu/progress_url.txt

# Background log uploader (30s cadence)
cat > /home/ubuntu/log_uploader.sh <<'LOGEOF'
#!/bin/bash
URL=$(cat /home/ubuntu/progress_url.txt)
while :; do
  cp /var/log/userdata.log /tmp/snap.log 2>/dev/null || true
  [ -s /tmp/snap.log ] && curl -fsS --retry 2 -X PUT --upload-file /tmp/snap.log "$URL" >/dev/null 2>&1
  sleep 30
done
LOGEOF
chmod +x /home/ubuntu/log_uploader.sh
nohup /home/ubuntu/log_uploader.sh >/dev/null 2>&1 &
LOG_UP_PID=$!

# apt
wait_apt() { for i in $(seq 1 90); do
  if ! sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then return 0; fi
  sleep 5
done; return 1; }
echo "=== STEP A: apt update + install python3-venv jq curl ==="
wait_apt && sudo apt-get update -y || echo "apt update warn rc=$?"
wait_apt && sudo apt-get install -y python3-venv python3-pip jq curl || echo "apt install warn rc=$?"

# Pull inputs from S3 presigned GET
echo "=== STEP B: pull inputs from S3 ==="
mkdir -p /home/ubuntu/inputs
PANEL_URL=$(python3 -c "import json; print(json.load(open('/home/ubuntu/urls.json'))['get_panel'])")
RUNNER_URL=$(python3 -c "import json; print(json.load(open('/home/ubuntu/urls.json'))['get_runner'])")
curl -fsS --retry 5 --retry-delay 5 -o /home/ubuntu/inputs/pathway_panel.json "$PANEL_URL" || echo "PANEL_DL_FAILED"
curl -fsS --retry 5 --retry-delay 5 -o /home/ubuntu/inputs/boltz_runner_multimer.py "$RUNNER_URL" || echo "RUNNER_DL_FAILED"
chown -R ubuntu:ubuntu /home/ubuntu/inputs
python3 -c "import json; d=json.load(open('/home/ubuntu/inputs/pathway_panel.json')); print(len(d), 'complexes')" || echo "PANEL_PARSE_FAILED"

# Boltz install + run
cat > /home/ubuntu/run_boltz.sh <<'SHEOF'
#!/bin/bash
set -x
export HOME=/home/ubuntu
export PATH="$HOME/.local/bin:$PATH"
export BOLTZ_CACHE=/home/ubuntu/boltz_cache
export BOLTZ_OUT=/home/ubuntu/boltz_out
export HF_HOME=/home/ubuntu/boltz_hf
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export BOLTZ_PREFLIGHT_TIMEOUT_S=5400
export BOLTZ_PAIR_TIMEOUT_S=1800
mkdir -p "$BOLTZ_CACHE" "$BOLTZ_OUT" "$HF_HOME"

nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
VENV=/home/ubuntu/boltz_venv
python3 -m venv --system-site-packages "$VENV"
source "$VENV/bin/activate"
python -m pip install --upgrade pip --timeout 600 --retries 5 2>&1 | tail -5
echo "  installing boltz (5-8 min)..."
date
python -m pip install --no-cache-dir --timeout 600 --retries 5 boltz 2>&1 | tail -20
date
which boltz || { echo "BOLTZ_BIN_MISSING"; exit 1; }
python -c "import boltz; print('boltz', getattr(boltz,'__version__','?'))"
python -c "import torch; assert torch.cuda.is_available(); print('cuda OK', torch.cuda.get_device_name(0))"

cd /home/ubuntu/inputs
python boltz_runner_multimer.py pathway_panel.json 2>&1
echo "BOLTZ_PATHWAY_DONE rc=$?"
ls -la "$BOLTZ_OUT/"
SHEOF
chmod +x /home/ubuntu/run_boltz.sh
chown ubuntu:ubuntu /home/ubuntu/run_boltz.sh

echo "=== STEP C: starting boltz runner ==="
date
sudo -H -u ubuntu bash -lc 'cd /home/ubuntu && bash run_boltz.sh' 2>&1
echo "outer runner rc=$?"
date

echo "===== UPLOADING RESULTS ====="
upload() {
  local fname=$1; local fpath=$2; local url
  url=$(python3 -c "import json; print(json.load(open('/home/ubuntu/urls.json')).get('$fname',''))")
  [ -z "$url" ] && { echo "  no PUT URL for $fname"; return; }
  [ ! -f "$fpath" ] && { echo "  missing $fpath"; return; }
  echo "  uploading $fname ($(stat -c%s "$fpath" 2>/dev/null || echo ?) bytes)"
  curl -fsS --retry 5 --retry-delay 5 -X PUT --upload-file "$fpath" "$url" && echo "    ok" || echo "    FAIL"
}
upload results.json     /home/ubuntu/boltz_out/results.json
upload infra_probe.json /home/ubuntu/boltz_out/_infra_probe.json
tar -czf /tmp/affinity_dump.tgz -C /home/ubuntu/boltz_out . 2>/dev/null || true
upload affinity_dump.tgz /tmp/affinity_dump.tgz
upload userdata.log     /var/log/userdata.log

kill $LOG_UP_PID 2>/dev/null || true
sync
echo "===== ALL DONE at $(date) — shutting down in 30s ====="
sleep 30
shutdown -h now
