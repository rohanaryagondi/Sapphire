#!/bin/bash
# CNS-NEW-MODELS DTI benchmark: DTIAM (Nat. Commun. 2025) on the 19-target CNS panel.
# DTIAM = BerMol drug tower (self-supervised on 1.6M ChEMBL compounds) + ESM-2 protein
# tower. Scored as a per-target FEW-SHOT scaffold-split probe over the feature towers,
# head-to-head vs the zero-shot BALM/PLAPT reference (ion_channel 0.50/0.50 = CHANCE).
# Data pulled on-instance from ChEMBL (chembl_webresource_client) + UniProt REST.
# Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
#
# TOOLCHAIN (proven pairing carried over from aws/cns_dti_benchmark_userdata.sh):
#   torch>=2.6 cu124  -- ESM-2 ships pytorch_model.bin; transformers>=4.45 blocks torch.load
#                        on .bin unless torch>=2.6 (CVE-2025-32434). g5 = cu124-compatible.
#   transformers>=4.45 + accelerate + safetensors -- ESM-2 (EsmModel) protein tower.
#   fair-esm          -- DTIAM's documented protein-embedding dep (kept for repo imports).
#   rdkit==2022.9.5   -- SMILES sanity + Murcko scaffolds + DUD-E-style decoys (numpy<2 ABI pin).
#   chembl_webresource_client -- on-instance ChEMBL actives/inactives pull.
#   scikit-learn/scipy -- the scaffold-grouped logistic probe + AUROC.
#   gdown             -- pull DTIAM's released BerMolModel_base.pkl from Google Drive.
#   numpy<2, requests, pandas, tqdm, pyyaml -- repo + client deps.
#   LESSON: transformers>=4.42 needs torch>=2.2; here torch>=2.6 pairs with transformers>=4.45.
# Clones github.com/CSUBioGroup/DTIAM (Apache-2.0). BerMol weights are best-effort: if the
# Google-Drive pull fails, the eval transparently falls back to a Morgan-FP drug featurization
# and RECORDS drug_backend in the result (never a silent swap).
# No mkfs/dd/rm of existing data. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== cns new-models benchmark start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="cns_new_models"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# 19 targets x ~30-180 pairs x (ESM-2 650M embed + BerMol embed + scaffold-CV probe) -> generous watchdog.
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
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

# numpy<2 FIRST (rdkit 2022.9.5 C-ext ABI). torch>=2.6 cu124 (transformers torch.load gate
# for the ESM-2 .bin checkpoint the protein tower pulls from HuggingFace).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -1
# transformers>=4.45 (ESM-2/EsmModel) + fair-esm (DTIAM repo dep) + ChEMBL client + probe stack.
$PY -m pip install -q "transformers>=4.45" "huggingface_hub>=0.24" accelerate safetensors \
    fair-esm "rdkit==2022.9.5" scikit-learn scipy pandas tqdm requests pyyaml gdown \
    chembl_webresource_client 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: protein-tower + probe + ChEMBL client deps must import.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, sklearn, scipy, rdkit, requests
from transformers import AutoTokenizer, AutoModel
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from chembl_webresource_client.new_client import new_client
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "sklearn", sklearn.__version__,
      "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# Clone the DTIAM repo on-instance (Apache-2.0). BerMol drug encoder lives in code/BerMol/.
git clone --depth 1 https://github.com/CSUBioGroup/DTIAM /opt/DTIAM 2>&1 | tail -2 || fail "clone-dtiam" 93
ls /opt/DTIAM/code/ || echo "[warn] DTIAM code/ not where expected"

# Best-effort pull of the released BerMol weights (Google Drive). If this fails the eval
# falls back to a Morgan-FP drug vector and records drug_backend=morgan_fp_fallback -- so a
# missing-weights case still produces an honest, non-silent result rather than a hard fail.
mkdir -p /opt/weights
$PY -m gdown "https://drive.google.com/uc?id=1ZW-PQXE4FvWHx77hkUA-JsqyJUb6B-NQ" \
    -O /opt/weights/BerMolModel_base.pkl 2>&1 | tail -3 || echo "[warn] BerMol gdown failed; Morgan fallback will engage"
ls -la /opt/weights/ || echo "[warn] /opt/weights empty"

# Stage the eval from S3 (the launcher uploads it to s3://$BUCKET/$PREFIX/). The panel is
# defined IN the eval; data is fetched on-instance.
aws s3 cp "s3://$BUCKET/$PREFIX/cns_new_models_eval.py" /opt/cns_new_models_eval.py || fail "dl-eval" 95

echo "=== run cns new-models benchmark $(date -u) ==="
export USE_TF=0 USE_FLAX=0
DTIAM_DIR=/opt/DTIAM BERMOL_CKPT=/opt/weights/BerMolModel_base.pkl \
  ESM2_MODEL=facebook/esm2_t33_650M_UR50D \
  OUT=/root/cnsnew_out/cns_new_models_result.json $PY /opt/cns_new_models_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/cnsnew_out/cns_new_models_result.json ] && \
  aws s3 cp /root/cnsnew_out/cns_new_models_result.json "s3://$BUCKET/$PREFIX/cns_new_models_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
