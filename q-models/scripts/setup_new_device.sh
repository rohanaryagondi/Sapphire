#!/usr/bin/env bash
# ============================================================================
# setup_new_device.sh — bring the Quiver MAMMAL `models` branch up from zero on
# a fresh machine, including the LIVE local Explorer (DTI / BBBP / Tox).
#
# What this gives you, WITHOUT the 17 GB MAMMAL weights or any GPU:
#   - conda env `mammal` (Python 3.11) + all deps
#   - the per-target binder fine-tunes + de-risking models REGENERATED locally
#     (models/ is gitignored, so they must be rebuilt — this does it)
#   - the Explorer running live at http://localhost:8000
#
# Heavy/optional bits (MAMMAL 17 GB weights, AWS) are flagged and skippable.
# Run from the repo root:  bash scripts/setup_new_device.sh
# Re-runnable (idempotent-ish): skips finished steps where it can.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
PY="${PY:-python}"            # override with PY=/path/to/python if not using conda activate
echo "== Quiver MAMMAL · new-device setup =="
echo "repo: $REPO"

# ---- 1. conda env ---------------------------------------------------------
if command -v conda >/dev/null 2>&1; then
  if ! conda env list | grep -q "/mammal$\|^mammal "; then
    echo "== creating conda env 'mammal' (python 3.11) =="
    conda create -n mammal python=3.11 -y
  fi
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate mammal
  PY=python
else
  echo "!! conda not found — using PY=$PY ; a venv with Python 3.11 also works."
fi
echo "python: $($PY --version 2>&1)  ($(command -v $PY))"

# ---- 2. dependencies ------------------------------------------------------
echo "== installing deps (web layer + fine-tune extras; MAMMAL heavy stack optional) =="
$PY -m pip install -q --upgrade pip
$PY -m pip install -q -r ui/requirements.txt
$PY -m pip install -q -r requirements-finetune.txt
echo "   (skip the heavy MAMMAL stack unless you need MAMMAL-head experiments:"
echo "    pip install -r requirements.txt  +  bash scripts/download_models.sh)"

# ---- 3. regenerate the LIVE local fine-tunes (the key step) ---------------
# These pull ChEMBL / PubChem / TDC over the network and train CPU FP+GBT models.
# ~15-40 min total; ChEMBL can be flaky — the pullers cache + retry, so just re-run
# this script to fill any gaps. Models land in models/cns_pertarget + models/derisking_local.
echo "== regenerating per-target binder fine-tunes (ChEMBL+GtoPdb -> models/cns_pertarget) =="
USE_TF=0 USE_FLAX=0 $PY experiments/cns_pertarget_finetune.py || echo "!! cns_pertarget incomplete (ChEMBL flaky?) — re-run this script to fill gaps"
echo "== regenerating PubChem-qHTS channel rescues (KCNQ2 + Cav3.2) =="
USE_TF=0 USE_FLAX=0 $PY experiments/pubchem_qhts_finetune.py || echo "!! pubchem_qhts incomplete — re-run to fill gaps"
echo "== regenerating de-risking models (BBBP / hERG / DILI -> models/derisking_local) =="
USE_TF=0 USE_FLAX=0 $PY experiments/derisking_local_train.py || echo "!! derisking incomplete — re-run"

echo "== model inventory =="
echo "   cns_pertarget: $(ls models/cns_pertarget/*.joblib 2>/dev/null | wc -l | tr -d ' ') / ~19 targets"
echo "   derisking_local: $(ls models/derisking_local/*.joblib 2>/dev/null | wc -l | tr -d ' ') / 3 endpoints"

# ---- 4. smoke test --------------------------------------------------------
echo "== explorer smoke tests =="
$PY -m pytest ui/explorer/tests -q || echo "!! tests failed — check the deps above"

cat <<'EOF'

== DONE. Start the live Explorer with: ==
  EXPLORER_LOCAL_MODELS=1 USE_TF=0 USE_FLAX=0 \
    python -m uvicorn ui.explorer.backend.app:app --host 127.0.0.1 --port 8000
  -> http://localhost:8000   (DTI / BBBP / Tox tracks serve LIVE local predictions)

Next: read  SETUP_NEW_DEVICE.md  (orientation, AWS continuation, what to build next).
EOF
