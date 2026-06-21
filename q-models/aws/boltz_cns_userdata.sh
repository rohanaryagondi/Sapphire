#!/bin/bash
# Boltz-2 CO-FOLDING on the HARD CNS ion channels where SEQUENCE-DTI is at chance
# (Cav1.2 / NMDA-NR1 / Nav1.5) + Nav1.8 positive control. Per-target binder-vs-decoy
# AUROC on Boltz affinity vs the seq-DTI baselines from cns_dti_characterization.md.
#
# TOOLCHAIN (the proven Boltz-2 stack — docs/boltz_handoff/README.md sec 4.1 + sec 5,
# AWS_INFRASTRUCTURE.md, baselines/boltz.py header):
#   pip install boltz                  -- the AF3-class co-fold + affinity model itself.
#   cuequivariance-torch==0.10.0       -- wrapper Boltz imports for triangle ops.
#   cuequivariance-ops-cu13-torch      -- THE CRITICAL CUDA-kernel package. Boltz crashes
#       (then cu12 fallback)              with ModuleNotFoundError: cuequivariance_ops_torch
#                                         on certain pair sizes if ONLY the wrapper is
#                                         installed. AMI ships CUDA 13 -> cu13 first, cu12
#                                         fallback (the two CUDA builds; see gotcha #1).
#       NOTE: aws/boltz_runner.py does NOT pass `--no_kernels`, so the kernel package IS
#       required here (the `--no_kernels` shortcut in AWS_INFRASTRUCTURE applies only to
#       the boltz branch's multimer runner, which we are NOT using). We verify the exact
#       import Boltz hits at runtime and FALL BACK to cu12, then to a `--no_kernels`-style
#       env nudge, rather than silently shipping a broken kernel path.
#   chembl_webresource_client + rdkit  -- on-instance ChEMBL actives/inactives pull +
#                                         property-matched decoys (this eval).
#   PyYAML                             -- boltz_runner.py writes the per-complex YAML via
#                                         yaml.safe_dump (escapes SMILES quotes safely).
# Boltz weights (~10 GB) + ColabFold MSA (--use_msa_server) download on first complex;
# the runner's 3600 s preflight covers the cold path. Per-complex 600 s cap SKIPS an
# OOM/hung ~2000-aa channel instead of sinking the run.
#
# Self-contained venv with --system-site-packages (so the AMI's CUDA-prebuilt torch is
# reused; plain venv would force a multi-GB torch reinstall). EXPLICIT python path
# (conda-activate fails in userdata). No mkfs/dd/rm of existing data. Creds never traced
# or logged. Self-terminates; watchdog 7200 s (Boltz is slow).
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== boltz cns eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="boltz_cns"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# Boltz is SLOW (minutes/complex; cold ~10 GB weights + MSA queue; ~2000-aa channels).
# Watchdog 7200 s (2 h) — generous per the spec.
( sleep 7200; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10. Install it on its OWN
# line; ensurepip + the pip-version guard below are MANDATORY (prior runs that skipped
# this came up WITHOUT pip -> No module named pip/numpy cascade).
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
# --system-site-packages so the AMI's CUDA-prebuilt torch is visible to Boltz (handoff
# sec 4.1). Plain `python -m venv` would force a fresh multi-GB torch install.
python3 -m venv --system-site-packages /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# --- Boltz-2 + the CRITICAL cuequivariance kernel package (handoff sec 4.1 / gotcha #1) ---
$PY -m pip install -q boltz 2>&1 | tail -2 || fail "pip-boltz" 92
$PY -m pip install -q "cuequivariance-torch==0.10.0" 2>&1 | tail -1 || echo "[warn] cuequivariance-torch pin failed; trying unpinned"
# THE kernels. AMI is CUDA 13 -> cu13 first; cu12 fallback (the two real CUDA builds).
$PY -m pip install -q cuequivariance-ops-cu13-torch 2>&1 | tail -1 \
  || $PY -m pip install -q cuequivariance-ops-cu12-torch 2>&1 | tail -1 \
  || echo "[warn] BOTH cuequivariance-ops CUDA builds failed to install"
# Verify the EXACT import path Boltz hits at runtime (handoff sec 4.1). Non-fatal:
# record whether kernels resolved so the result JSON / log shows it; Boltz may still
# run small pair sizes without them, and the runner classifies any kernel crash.
$PY - <<'PYK' || echo "[warn] cuequivariance kernel import FAILED — Boltz may crash on large pair sizes (~2000-aa channels). See gotcha #1."
from cuequivariance_torch.primitives.triangle import triangle_multiplicative_update
print("cuequivariance kernel import OK")
PYK

# --- This eval's data deps: ChEMBL client + rdkit + numpy + PyYAML (runner YAML) ---
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "rdkit==2022.9.5" chembl_webresource_client requests pyyaml 2>&1 | tail -2 || fail "pip-data" 92
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: Boltz CLI present + torch sees CUDA + data deps import.
which boltz || fail "no-boltz-bin" 92
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, rdkit, yaml, requests
from rdkit import Chem
from chembl_webresource_client.new_client import new_client
import importlib.metadata as im
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__,
      "boltz", im.version("boltz"))
assert torch.cuda.is_available(), "torch.cuda.is_available() is False"
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# Stage the eval + the runner it reuses VERBATIM. The launcher uploads BOTH to
# s3://$BUCKET/$PREFIX/ (boltz_cns_eval.py + boltz_runner.py from aws/).
aws s3 cp "s3://$BUCKET/$PREFIX/boltz_cns_eval.py" /opt/boltz_cns_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/boltz_runner.py"   /opt/boltz_runner.py   || fail "dl-runner" 95

echo "=== run boltz cns eval $(date -u) ==="
export USE_TF=0 USE_FLAX=0
# Local disk paths for the Boltz cache + runner output (no EBS dependency: the cold
# ~10 GB weight download fits the 150 GB root the launcher requests). The eval maps
# these onto boltz_runner.py's exact BOLTZ_OUT / BOLTZ_CACHE / *_TIMEOUT_S interface.
mkdir -p /root/boltz_cache /root/boltz_out /root/boltzcns_out
BOLTZ_RUNNER=/opt/boltz_runner.py \
  BOLTZ_CACHE=/root/boltz_cache BOLTZ_OUT=/root/boltz_out \
  PAIR_TIMEOUT_S=600 PREFLIGHT_TIMEOUT_S=3600 \
  OUT=/root/boltzcns_out/boltz_cns_result.json $PY /opt/boltz_cns_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="

# Upload the consolidated result, plus the runner's raw results.json for forensics.
[ -f /root/boltzcns_out/boltz_cns_result.json ] && \
  aws s3 cp /root/boltzcns_out/boltz_cns_result.json "s3://$BUCKET/$PREFIX/boltz_cns_result.json" || echo "[warn] no result file"
[ -f /root/boltz_out/results.json ] && \
  aws s3 cp /root/boltz_out/results.json "s3://$BUCKET/$PREFIX/runner_results.json" || echo "[warn] no runner results.json"
[ -f /root/boltz_out/_infra_probe.json ] && \
  aws s3 cp /root/boltz_out/_infra_probe.json "s3://$BUCKET/$PREFIX/infra_probe.json" || true
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
