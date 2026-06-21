#!/bin/bash
# RE-TEST of previously-rejected DTI models (ConPLex pretrained + DrugBAN on-instance-trained;
# PerceiverCPI documented-skip in the eval) on the SAME 19-target CNS panel as
# aws/cns_dti_benchmark_userdata.sh. Per-target binder-vs-decoy AUROC -> per-FAMILY aggregate,
# head-to-head vs BALM/PLAPT. Data pulled on-instance from ChEMBL + UniProt REST. Both models
# run from protein SEQUENCE + ligand SMILES (no 3D structure).
# Self-contained /opt/venv via EXPLICIT python (conda-activate fails in userdata).
# TOOLCHAIN (union of ConPLex + DrugBAN; PerceiverCPI deliberately NOT installed — incompatible
#   torch 1.7.1/py3.9 pin, documented-skip in the eval):
#   torch 2.1.0+cu121  -- the highest torch the DGL cu121 wheels support (DGL drug-graph backend
#                         for DrugBAN); ConPLex (ProtBert+Morgan) runs fine on 2.1.
#   dgl + dgllife      -- DrugBAN's molecular-graph featurizer (smiles_to_bigraph +
#                         CanonicalAtom/BondFeaturizer); cu121 wheel index pinned to torch 2.1.
#   transformers       -- ConPLex ProtBert (Rostlab/prot_bert) protein featurizer.
#   conplex-dti        -- ConPLex package (conplex_dti.featurizer/.model.architectures); we call
#                         the clean predict path IN-PROCESS, never the tdc/wandb/lightning CLI.
#   rdkit==2022.9.5    -- SMILES sanity + DUD-E-style property-matched decoys (numpy<2 ABI pin);
#                         also ConPLex's own pin.
#   chembl_webresource_client -- on-instance ChEMBL actives/inactives pull (this benchmark).
#   numpy<2, yacs, prettytable, scikit-learn, scipy, pandas -- DrugBAN config (yacs) + metrics.
# Clones ConPLex (samsledje/ConPLex) + DrugBAN (peizhenbai/DrugBAN, ships the BindingDB random
# split DrugBAN trains on). No mkfs/dd/rm of existing data. Hardened: no creds in log.
# Self-terminates; watchdog.
exec > >(tee -a /var/log/job.log) 2>&1
echo "=== cns rejected dti re-test start: $(date -u) ==="
set +x  # SECURITY: never trace creds
export AWS_ACCESS_KEY_ID="__AKID__"
export AWS_SECRET_ACCESS_KEY="__SECRET__"
export AWS_DEFAULT_REGION="us-east-1"
set -x
BUCKET="rohan-mammal-bootstrap-20260610-213029"; PREFIX="cns_rejected_dti"
IID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id || echo unknown)
upload_log() { sed -E 's/(AKIA[A-Z0-9]{16}|AWS_SECRET_ACCESS_KEY=\S+|hf_[A-Za-z0-9]+)/REDACTED/g' /var/log/job.log > /tmp/j.log 2>/dev/null; aws s3 cp /tmp/j.log "s3://$BUCKET/$PREFIX/run.log" >/dev/null 2>&1 || true; }
fail() { echo "FAIL $1"; echo "rc=$2 iid=$IID note=$1" > /opt/DONE; aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"; upload_log; shutdown -h now; }
# 19 targets x ~30-180 pairs x ConPLex + a bounded DrugBAN on-instance train -> generous watchdog.
( sleep 5400; echo "WATCHDOG $(date -u)"; upload_log; shutdown -h now ) &
( while true; do sleep 60; upload_log; done ) &

nvidia-smi || fail "no-driver" 90
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1
# python3.10-venv carries ensurepip for the DLAMI python3.10; the meta python3-venv alone did NOT
# pull it on a prior run (No module named pip cascade). Install python3.10-venv on its OWN line;
# ensurepip + the pip-version guard below are MANDATORY.
apt-get install -y python3-pip git wget >/dev/null 2>&1 || fail "apt-core" 90
apt-get install -y python3.10-venv >/dev/null 2>&1 || fail "apt-venv" 90
python3 -m venv /opt/venv || fail "venv" 91
PY=/opt/venv/bin/python
$PY -m ensurepip --upgrade >/dev/null 2>&1 || true   # belt+suspenders if venv skipped pip
$PY -m pip --version || fail "no-pip-in-venv" 91
$PY -m pip install -q --upgrade pip

# numpy<2 FIRST (rdkit 2022.9.5 C-ext ABI). torch 2.1.0+cu121 = the highest torch the DGL cu121
# wheels support (DrugBAN drug-graph backend); ConPLex ProtBert+Morgan also runs on it.
$PY -m pip install -q "numpy<2" 2>&1 | tail -1
$PY -m pip install -q torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -1
# torchdata<0.8 still ships torchdata.datapipes, which DGL imports at load (removed in torchdata>=0.8 ->
# "No module named torchdata.datapipes" rc=92). Pin 0.7.1 (pairs with torch 2.1) BEFORE installing dgl.
$PY -m pip install -q "torchdata==0.7.1" 2>&1 | tail -1
# DGL drug-graph backend + dgllife featurizers, from the matching cu121 wheel index for torch 2.1.
$PY -m pip install -q dgl -f https://data.dgl.ai/wheels/cu121/repo.html 2>&1 | tail -2
$PY -m pip install -q dgllife 2>&1 | tail -1
# ConPLex package (predict-path modules) + ProtBert via transformers + ChEMBL client + DrugBAN
# config/metric deps (yacs/prettytable). conplex-dti drags pytorch_lightning/wandb/tdc but we
# never import the CLI, so they're inert at runtime.
# transformers PINNED <4.41: torch is 2.1.0 (for dgl cu121 wheels DrugBAN needs); transformers>=4.42 drops
# torch<2.2 support + calls torch.utils._pytree.register_pytree_node (absent in 2.1) -> rc=92 import fail.
$PY -m pip install -q conplex-dti "transformers==4.36.2" "huggingface_hub<0.26" "tokenizers<0.16" fair-esm \
    "rdkit==2022.9.5" scikit-learn scipy pandas tqdm requests yacs prettytable \
    chembl_webresource_client 2>&1 | tail -3
$PY -m pip install -q "numpy<2" 2>&1 | tail -1   # force-pin: nothing dragged numpy to 2.x

# FAIL-FAST gate: ConPLex predict-path + DrugBAN graph backend + ChEMBL client must all import.
$PY - <<'PYCHK' || fail "deps" 92
import numpy, torch, transformers, rdkit, sklearn, scipy, pandas, yacs, requests
import dgl, dgllife
from dgllife.utils import smiles_to_bigraph, CanonicalAtomFeaturizer, CanonicalBondFeaturizer
from conplex_dti.featurizer import MorganFeaturizer, ProtBertFeaturizer
from conplex_dti.model.architectures import SimpleCoembeddingNoSigmoid
from rdkit import Chem
from chembl_webresource_client.new_client import new_client
print("deps ok; numpy", numpy.__version__, "torch", torch.__version__,
      "transformers", transformers.__version__, "dgl", dgl.__version__,
      "cuda", torch.cuda.is_available(), "rdkit", rdkit.__version__)
assert numpy.__version__.startswith("1."), "numpy must be <2 for rdkit C-ext ABI"
PYCHK

# Clone BOTH model repos on-instance.
# ConPLex: predict-path modules (conplex_dti.*); pretrained BindingDB checkpoint curl'd by the eval.
git clone --depth 1 https://github.com/samsledje/ConPLex /opt/ConPLex 2>&1 | tail -2 || fail "clone-conplex" 93
ls /opt/ConPLex/conplex_dti/ || echo "[warn] ConPLex package layout not where expected"
# DrugBAN: ships configs/DrugBAN.yaml + datasets/bindingdb/random/{train,val}.csv (the eval trains
# a bounded DrugBAN on this on-instance, since the repo ships NO pretrained checkpoint).
git clone --depth 1 https://github.com/peizhenbai/DrugBAN /opt/DrugBAN 2>&1 | tail -2 || fail "clone-drugban" 94
ls /opt/DrugBAN/datasets/bindingdb/random/ || echo "[warn] DrugBAN BindingDB random split missing"

# Stage the eval from S3 (the launcher uploads it to s3://$BUCKET/$PREFIX/). The 19-target panel
# is defined IN the eval script (no separate panel file); data is fetched on-instance from ChEMBL.
aws s3 cp "s3://$BUCKET/$PREFIX/cns_rejected_dti_eval.py" /opt/cns_rejected_dti_eval.py || fail "dl-eval" 95

echo "=== run cns rejected dti re-test $(date -u) ==="
export USE_TF=0 USE_FLAX=0
CONPLEX_DIR=/opt/ConPLex DRUGBAN_DIR=/opt/DrugBAN WORK=/root/rej_work \
  OUT=/root/rej_out/cns_rejected_dti_result.json $PY /opt/cns_rejected_dti_eval.py
RC=$?
echo "=== run done rc=$RC $(date -u) ==="
[ -f /root/rej_out/cns_rejected_dti_result.json ] && \
  aws s3 cp /root/rej_out/cns_rejected_dti_result.json "s3://$BUCKET/$PREFIX/cns_rejected_dti_result.json" || echo "[warn] no result file"
echo "rc=$RC iid=$IID done=$(date -u)" > /opt/DONE
aws s3 cp /opt/DONE "s3://$BUCKET/$PREFIX/DONE"
upload_log
shutdown -h now
