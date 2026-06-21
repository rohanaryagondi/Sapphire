#!/bin/bash
# CToxPred2 (issararab/CToxPred2, JCIM 2024) — Track-5 cardiac/ion-channel toxicity eval.
# CToxPred2 = the only verified-downloadable model EXPLICITLY trained on ion-channel blockade:
# a MULTITASK ligand-only classifier with separate pretrained heads for hERG / Nav1.5 / Cav1.2
# (SMILES -> per-channel block probability). We score its hERG head head-to-head vs our Track-5
# winner (MapLight / Morgan-FP+XGBoost, AUROC 0.889 / far-OOD 0.809) on the SAME TDC hERG_Karim
# scaffold split, plus a Nav1.5/Cav1.2 ChEMBL blocker-vs-decoy bonus. CPU work; g5.xlarge is fine.
# Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
#
# TOOLCHAIN (from the repo's own install.sh, adapted to a pip-only venv on the DLAMI):
#   numpy<2           -- rdkit + mordred + scikit-learn C-ext ABI (repo pins numpy==1.23.5).
#   torch (cpu)       -- the SL deep heads (hERGClassifier/Nav15/Cav12 are tiny MLP state_dicts;
#                        repo used torch==1.12.1, but a modern CPU wheel loads the .model dicts).
#   scikit-learn      -- the SSL random-forest heads + the pickled preprocessing pipelines.
#                        Pin near the repo's 1.3.1 so the joblib RF/pipeline unpickles cleanly
#                        (sklearn pickles are version-fragile -> InconsistentVersionWarning/errors).
#   rdkit-pypi        -- SMILES parse + Morgan FPs for the applicability-domain bands.
#   mordred           -- the repo's 2D descriptor featurizer (compute_descriptor_features).
#   PyBioMed          -- the repo's ECFP2(1024)+PubChem(881)=1905 fingerprint featurizer
#                        (compute_fingerprint_features); installed from the gadsbyfly fork the
#                        repo pins. networkx<3 (PyBioMed uses removed nx APIs).
#   MolVS, openbabel/pybel -- repo deps (molvs Standardizer is imported by notebooks/nutils.py).
#   scipy, pandas<2.1 -- pipeline/descriptor deps.
#   PyTDC             -- TDC hERG_Karim (random + scaffold split) — the SAME hERG benchmark
#                        MapLight/FP-XGBoost were judged on.
#   chembl_webresource_client -- on-instance ChEMBL pull for the Nav1.5/Cav1.2 bonus panel.
# WEIGHTS: ship in-repo as .rar (model_weights.rar / decriptors_preprocessing.rar /
#   random_forest.rar) under CToxPred2/models/ — decompressed below with unar (apt unar).
# TRUST NOTE: the joblib/.model artifacts are the model AUTHORS' official pretrained weights from
#   the canonical GitHub repo (cloned here) — not arbitrary user input; loading them is the
#   intended, documented way to run CToxPred2.
# No mkfs/dd/rm of existing data. Hardened: no creds in log. Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== ctoxpred2 eval start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="ctoxpred2"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# hERG_Karim (~13k mols x PyBioMed FP + Mordred 2D descriptors) + Nav/Cav ChEMBL pull + (optional)
# 100-pass MC-dropout if the RF backend falls back -> generous watchdog.
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI's python3.10; python3-venv (meta) alone did NOT
# pull it on a prior run, so `python3 -m venv` came up WITHOUT pip -> No module named pip/numpy
# cascade. Install python3.10-venv on its OWN line; ensurepip + the pip-version guard below are
# MANDATORY. unar/unrar decompress the repo's shipped .rar weight archives; openbabel for pybel.
# git-lfs (FIX #2, 2026-06-15): the .rar weight archives are stored as git-LFS objects, so a plain
# `git clone` fetched ~130-byte POINTER stubs -> unar "extraction failed" -> truncated joblib/.pt
# ("EOF reading array data" / "PytorchStreamReader failed finding central directory"). Install
# git-lfs so we can pull the REAL .rar blobs after cloning.
apt-get install -y python3-pip git git-lfs wget unar openbabel libopenbabel-dev >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (rdkit/mordred/sklearn C-ext ABI; repo pins numpy==1.23.5). torch CPU wheel
# (the SL heads are tiny MLP state_dicts; no GPU needed).
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -1
# Pin scikit-learn near the repo's 1.3.1 so the joblib RF + preprocessing pipelines unpickle.
$PY -m pip install -q "scikit-learn==1.3.1" "scipy==1.11.4" "pandas<2.1" \
    "rdkit-pypi" "mordred==1.2.0" "networkx<3" "MolVS==0.1.1" openbabel \
    PyTDC chembl_webresource_client requests tqdm 2>&1 | tail -3
# PyBioMed (the repo's fingerprint featurizer) from the gadsbyfly fork the repo pins.
$PY -m pip install -q "git+https://github.com/gadsbyfly/PyBioMed" 2>&1 | tail -2
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# Clone CToxPred2 (the canonical repo; weights ship inside as .rar archives stored via git-LFS).
git lfs install >/dev/null 2>&1 || true
git clone --depth 1 https://github.com/issararab/CToxPred2 /opt/CToxPred2 2>&1 | tail -2 || fail "clone" 93
# FIX #2: pull the REAL .rar LFS blobs (the shallow clone fetched pointer stubs). Verify they are
# now real archives (>1 KB) before unar; a pointer is ~130 bytes.
( cd /opt/CToxPred2 && git lfs pull 2>&1 | tail -3 ) || echo "[warn] git lfs pull failed"
ls -la /opt/CToxPred2/CToxPred2/models/*.rar 2>/dev/null || echo "[warn] no .rar after lfs pull"

# Decompress the shipped weight archives in place (unar extracts into models/ subdirs:
# model_weights/, decriptors_preprocessing/, random_forest/).
MODELS=/opt/CToxPred2/CToxPred2/models
for rar in "$MODELS"/*.rar; do
  [ -e "$rar" ] || continue
  echo "[unar] $rar"
  unar -force-overwrite -output-directory "$MODELS" "$rar" 2>&1 | tail -2 || echo "[warn] unar $rar failed"
done
ls -R "$MODELS" 2>/dev/null | head -60 || echo "[warn] models tree empty after unar"

# FAIL-FAST gate: import the repo's featurizers + classes, decompressed weights present, and a
# 1-SMILES smoke predict produces a per-channel P(positive class) via the eval's own wrapper.
aws s3 cp "s3://$BUCKET/$PREFIX/ctoxpred2_eval.py" /opt/ctoxpred2_eval.py || fail "dl-eval" 95

export USE_TF=0 USE_FLAX=0
CTOX_DIR=/opt/CToxPred2 $PY - <<'PYCHK' || fail "deps" 92
import os, sys, numpy, torch, sklearn, scipy, rdkit
print("base deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "sklearn", sklearn.__version__, "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for the rdkit/mordred/sklearn C-exts"
# repo featurizers + classes import
src = "/opt/CToxPred2/CToxPred2"; nb = "/opt/CToxPred2/notebooks"
for d in (src, nb):
    sys.path.insert(0, d)
from utils import compute_fingerprint_features, compute_descriptor_features
import pairwise_correlation  # CorrelationThreshold (pickled-pipeline unpickle dep)
from hERG_model import hERGClassifier
from nav15_model import Nav15Classifier
from cav12_model import Cav12Classifier
import mordred, PyBioMed  # noqa
print("repo imports ok")
# weights present after decompression
import os
mr = os.path.join(src, "models")
for sub in ["model_weights", "random_forest", "decriptors_preprocessing"]:
    print("present:", sub, os.path.isdir(os.path.join(mr, sub)))
# 1-SMILES smoke predict through the eval's wrapper (loads weights + featurizes + scores).
sys.path.insert(0, "/opt")
import ctoxpred2_eval as E
m = E.CToxPred2()
meta, probs, used = m.predict_proba(["CC(=O)Oc1ccccc1C(=O)O"], os.environ.get("BACKEND", "auto"))
print("smoke backend:", used, "meta_kept:", meta.get("n_kept"), "fail:", meta.get("n_failures"))
assert probs is not None and "hERG" in probs, f"smoke predict produced no hERG prob: {meta}"
print("smoke hERG P(block):", float(probs["hERG"][0]),
      "Nav1.5:", float(probs["Nav1.5"][0]), "Cav1.2:", float(probs["Cav1.2"][0]))
PYCHK

echo "=== run ctoxpred2 eval $(date -u) ==="
# BACKEND=auto: prefer the deterministic SSL random-forest predict_proba; fall back to the
# SL deep MC-dropout heads if the RF joblib unpickle fails on the sklearn version.
CTOX_DIR=/opt/CToxPred2 BACKEND=auto \
  OUT=/root/ctox_out/ctoxpred2_result.json $PY /opt/ctoxpred2_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/ctox_out/ctoxpred2_result.json ] && \
  aws s3 cp /root/ctox_out/ctoxpred2_result.json "s3://$BUCKET/$PREFIX/ctoxpred2_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
