#!/bin/bash
# Boltz-2 fair structural retest — PKM2 dimer + PPARD-LBD vs Ben's TSC2-decon
# compounds. Bouchet Claude built the panel + multimer runner; Bouchet GPU is
# jammed, so this runs on AWS g6e.xlarge (L40S 48 GB) instead.
#
# Strategy (from results/aws_eval/boltz_pkm2_ppard/HANDOFF.md):
#   - PPARD-LBD ×8 (231 aa, tiny): 1 positive (GSK 3787) + 2 putatives + 5 negs
#   - PKM2 dimer ×7 (1062 aa total, needs >32 GB GPU mem): 1 positive (Dasa-58)
#     + 1 putative + 5 negs
#   - Calibration gate: read positive-vs-negative margin BEFORE the putatives.
#
# Skipping cuequivariance-ops install entirely — multimer runner uses
# --no_kernels so the CUDA kernels are bypassed. cuequivariance-torch
# (the high-level package) gets pulled in by `pip install boltz`.
#
# This file is the TEMPLATE; the literal launched copy at
# /tmp/userdata_filled.sh has the __PUT_URLS_JSON__ slot replaced with a
# JSON blob of presigned PUT URLs for the S3 output bucket.

# Hard ceiling: 4 h. g6e.xlarge $1.86/hr × 4 = $7.44 worst case (cap is $10).
( sleep 14400 && shutdown -h now ) &
exec > /var/log/userdata.log 2>&1
set -x
date
echo "===== ROHAN-BOLTZ-PKM2-PPARD-FAIRRETEST USERDATA START ====="

# ----- Read injected PUT URLs from the templated heredoc -----
mkdir -p /home/ubuntu
cat > /home/ubuntu/put_urls.json <<'PUT_EOF'
__PUT_URLS_JSON__
PUT_EOF
chown ubuntu:ubuntu /home/ubuntu/put_urls.json

# ----- Wait for apt to settle, install minimal deps -----
wait_apt() {
  for i in $(seq 1 90); do
    if ! sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then return 0; fi
    sleep 5
  done
  return 1
}
wait_apt && sudo apt-get update -y
wait_apt && sudo apt-get install -y python3-venv python3-pip git jq curl

# ----- Clone the boltz branch -----
cd /home/ubuntu
sudo -u ubuntu git clone --depth 1 -b boltz https://github.com/rohanaryagondi/Q-Mammal.git \
  || { echo "GIT_CLONE_FAILED"; sleep 30; shutdown -h now; exit 1; }
cd Q-Mammal
git rev-parse HEAD
ls results/aws_eval/boltz_pkm2_ppard/
PANEL=/home/ubuntu/Q-Mammal/results/aws_eval/boltz_pkm2_ppard/fair_retest_panel.json
RUNNER=/home/ubuntu/Q-Mammal/results/aws_eval/boltz_pkm2_ppard/scripts/boltz_runner_multimer.py
python3 -c "import json; d=json.load(open('$PANEL')); print(len(d), 'complexes')" \
  || { echo "PANEL_PARSE_FAILED"; shutdown -h now; exit 1; }
python3 -c "import ast; ast.parse(open('$RUNNER').read())" \
  || { echo "RUNNER_PARSE_FAILED"; shutdown -h now; exit 1; }

# ----- Install Boltz in a venv (--system-site-packages keeps DL-AMI torch) -----
cat > /home/ubuntu/run_boltz.sh <<'SHEOF'
#!/bin/bash
set -eo pipefail
export HOME=/home/ubuntu
export PATH="$HOME/.local/bin:$PATH"
export BOLTZ_CACHE=/home/ubuntu/boltz_cache
export BOLTZ_OUT=/home/ubuntu/boltz_out
export HF_HOME=/home/ubuntu/boltz_hf
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
# Longer preflight — cold weight DL (~10 GB) + cold MSA queue on a fresh instance
export BOLTZ_PREFLIGHT_TIMEOUT_S=5400      # 90 min
export BOLTZ_PAIR_TIMEOUT_S=1800           # 30 min per complex (dimer is slow)
mkdir -p "$BOLTZ_CACHE" "$BOLTZ_OUT" "$HF_HOME"

echo "=== [1] venv on root disk (--system-site-packages for DL-AMI torch) ==="
VENV=/home/ubuntu/boltz_venv
python3 -m venv --system-site-packages "$VENV"
source "$VENV/bin/activate"

echo "=== [2] install boltz (no cuequivariance-ops — multimer runner uses --no_kernels) ==="
python -m pip install --upgrade pip --timeout 600 --retries 5
python -m pip install --no-cache-dir --timeout 600 --retries 5 boltz
python -m pip cache purge 2>/dev/null || true

echo "=== [3] sanity ==="
which boltz || { echo "BOLTZ_BIN_MISSING"; exit 1; }
python -c "import boltz; print('boltz', getattr(boltz,'__version__','?'))"
python -c "import torch; assert torch.cuda.is_available(); print('cuda', torch.cuda.get_device_name(0), torch.version.cuda)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "=== [4] run fair_retest_panel.json ==="
# Runner inlines --no_kernels and reads n_chains from each complex for the dimer
cd /home/ubuntu/Q-Mammal
python results/aws_eval/boltz_pkm2_ppard/scripts/boltz_runner_multimer.py \
  results/aws_eval/boltz_pkm2_ppard/fair_retest_panel.json
echo "BOLTZ_FAIRRETEST_COMPLETE"
ls -la "$BOLTZ_OUT/"
SHEOF
chmod +x /home/ubuntu/run_boltz.sh
chown ubuntu:ubuntu /home/ubuntu/run_boltz.sh

echo "===== STARTING BOLTZ at $(date) ====="
if ! sudo -H -u ubuntu bash -lc 'cd /home/ubuntu && bash run_boltz.sh' \
     > >(tee /home/ubuntu/boltz_runner.log) 2>&1; then
  echo "===== BOLTZ FAILED ====="
fi

# ----- Upload results to S3 via presigned PUT -----
echo "===== UPLOADING RESULTS to S3 ====="
upload_one() {
  local fname=$1; local fpath=$2; local url
  url=$(jq -r ".[\"$fname\"] // empty" /home/ubuntu/put_urls.json)
  [ -z "$url" ] && { echo "  no PUT URL for $fname"; return; }
  [ ! -f "$fpath" ] && { echo "  missing $fpath"; return; }
  echo "  uploading $fname ($(stat -c%s "$fpath" 2>/dev/null || echo ?) bytes)"
  curl -fsS --retry 5 --retry-delay 5 -X PUT --upload-file "$fpath" "$url" \
    && echo "    ok" || echo "    FAIL"
}
upload_one results.json     /home/ubuntu/boltz_out/results.json
upload_one infra_probe.json /home/ubuntu/boltz_out/_infra_probe.json
upload_one userdata.log     /var/log/userdata.log
tar -czf /tmp/affinity_dump.tgz -C /home/ubuntu/boltz_out . 2>/dev/null || true
upload_one affinity_dump.tgz /tmp/affinity_dump.tgz

sync
echo "===== ALL DONE at $(date) — shutting down ====="
sleep 15
shutdown -h now
