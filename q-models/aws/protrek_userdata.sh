#!/bin/bash
# ProTrek-650M Track-1 (protein family clustering) eval on the 40-gene CRISPR-N panel.
# HYPOTHESIS: ProTrek's tri-modal contrastive training (protein seq <-> structure <-> TEXT)
# gives the protein repr a *function* axis that pure-sequence encoders lack -> should help the
# FUNCTION-DEFINED families (e3_ligase, nuclear_receptor) where ESM-2/MAMMAL plateau (~0.5).
# Metric: NN same-family recall on ProTrek's final function-aligned protein repr (raw +
# mean-centered), EXACT same panel + protocol as the ESM/Ankh/ProtST Track-1 ladder. Optional
# secondary: text-anchored family assignment via get_text_repr (unique to a tri-modal model).
#
# SEQUENCE-ONLY path: the eval calls ONLY model.get_protein_repr([seq]) + model.get_text_repr.
# NO Foldseek binary, NO structure folding. The HF weights bundle a foldseek STRUCTURE-ENCODER
# subfolder (weights only) which the constructor builds but the eval never invokes.
# Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
#
# TOOLCHAIN — follows ProTrek's OWN requirements.txt (the repo loader is tightly coupled to
# these versions; do NOT bump to the cu124/torch2.6 stack used by the DTI evals):
#   torch==2.0.1 (+ torchvision/torchaudio) cu118 -- ProTrek pin; cu118 wheel is g5-compatible.
#   transformers==4.28.0  -- ProTrek pin; loads the bundled ESM-2-650M + PubMedBERT sub-encoders.
#                            ProTrek_650M.pt is a torch.save checkpoint loaded by the repo's own
#                            loader (NOT the transformers .bin torch.load gate), so torch 2.0.1
#                            is fine here.
#   pytorch-lightning==2.1.3 torchmetrics==0.9.3 -- repo deps imported at construction time.
#   biopython easydict lmdb pyspellchecker multiprocess tabulate -- ProTrek repo deps.
#   sentencepiece -- PubMedBERT/ESM tokenizers.
#   scikit-learn scipy numpy -- the NN-recall metric + array math.
#   huggingface_hub -- pull westlake-repl/ProTrek_650M weights (~3.64 GB checkpoint + encoders).
# Clones github.com/westlake-repl/ProTrek (MIT). No mkfs/dd/rm of existing data.
# Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== protrek track-1 start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="protrek"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# 3.64 GB checkpoint download + deps install + embedding 40 proteins (fast on GPU). The big
# variable is the HF download -> generous watchdog.
( sleep 6000; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; python3-venv (meta) alone did NOT
# pull it on a prior run, so `python3 -m venv` came up WITHOUT pip -> No module named pip/numpy
# cascade. Install python3.10-venv on its OWN line; ensurepip + the pip-version guard below are
# MANDATORY.
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# ProTrek's pinned stack. torch==2.0.1 cu118 (g5-compatible) FIRST.
$PY -m pip install -q torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118 2>&1 | tail -2
# ProTrek repo deps (verbatim from its requirements.txt) + tokenizer/metric stack.
$PY -m pip install -q "transformers==4.28.0" "pytorch-lightning==2.1.3" "torchmetrics==0.9.3" \
    "scikit-learn==1.4.0" "biopython==1.83" "easydict==1.13" "lmdb==1.4.1" \
    "tabulate==0.9.0" "pyspellchecker==0.8.2" multiprocess sentencepiece \
    "faiss-cpu==1.7.4" pandas tqdm huggingface_hub scipy numpy 2>&1 | tail -3
# ^ FIX #1 faiss-cpu + FIX #2 pandas/tqdm (2026-06-15): ProTrek's model module imports faiss
# (retrieval index) AND pandas at load even on the get_protein_repr-only path, but neither is
# in the repo's requirements.txt (the repo under-specifies) -> two sequential rc=92 'No module'
# failures. faiss-cpu pinned 1.7.4 for the torch-2.0.1/py3.10/numpy<2 stack; pandas+tqdm are the
# other unlisted runtime imports. This is the final toolchain fix (<=2-fix cap); bank if it cascades.

# FAIL-FAST gate: ProTrek's model class must import + CUDA must be present (the whole eval is
# pointless without the GPU). Clone first so the import can resolve.
git clone --depth 1 https://github.com/westlake-repl/ProTrek /opt/ProTrek 2>&1 | tail -2 || fail "clone-protrek" 93
ls /opt/ProTrek/model/ProTrek/ || echo "[warn] ProTrek model dir not where expected"

$PY - <<'PYCHK' || fail "deps" 92
import os, sys
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")
import numpy, torch, transformers, sklearn, scipy
sys.path.insert(0, "/opt/ProTrek")
from model.ProTrek.protrek_trimodal_model import ProTrekTrimodalModel
assert torch.cuda.is_available(), "CUDA required for ProTrek eval"
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "sklearn", sklearn.__version__,
      "cuda", torch.cuda.is_available(),
      "gpu", torch.cuda.get_device_name(0))
print("ProTrekTrimodalModel import OK")
PYCHK

# Download the ProTrek-650M weights (~3.64 GB .pt + the esm2/PubMedBERT/foldseek encoder
# subfolders) into the repo's expected weights/ layout. SEQUENCE path only: we never run the
# Foldseek binary; the foldseek subfolder is just the structure-ENCODER weights the constructor
# loads. huggingface-cli is installed by huggingface_hub above.
mkdir -p /opt/ProTrek/weights
/opt/venv/bin/huggingface-cli download westlake-repl/ProTrek_650M \
    --local-dir /opt/ProTrek/weights/ProTrek_650M --local-dir-use-symlinks False 2>&1 | tail -5 \
    || fail "dl-weights" 94
ls -la /opt/ProTrek/weights/ProTrek_650M/ || fail "weights-missing" 94
[ -f /opt/ProTrek/weights/ProTrek_650M/ProTrek_650M.pt ] || fail "ckpt-missing" 94

# Stage the eval + the panel/sequence data from S3 (the launcher uploads them to
# s3://$BUCKET/$PREFIX/). The panel + sequence cache are the EXACT files the ESM/Ankh/ProtST
# Track-1 evals use, so numbers are best-vs-best comparable.
aws s3 cp "s3://$BUCKET/$PREFIX/protrek_eval.py" /opt/protrek_eval.py || fail "dl-eval" 95
aws s3 cp "s3://$BUCKET/$PREFIX/compare_esm2_650m.json" /opt/compare_esm2_650m.json || fail "dl-panel" 95
aws s3 cp "s3://$BUCKET/$PREFIX/_uniprot_cache.json" /opt/_uniprot_cache.json || fail "dl-cache" 95

echo "=== run protrek track-1 $(date -u) ==="
export USE_TF=0 USE_FLAX=0
OUT=/opt/protrek_result.json \
  PROTREK_DIR=/opt/ProTrek \
  PROTREK_WEIGHTS=/opt/ProTrek/weights/ProTrek_650M \
  $PY /opt/protrek_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /opt/protrek_result.json ] && \
  aws s3 cp /opt/protrek_result.json "s3://$BUCKET/$PREFIX/protrek_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
