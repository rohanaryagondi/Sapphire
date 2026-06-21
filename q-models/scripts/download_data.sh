#!/usr/bin/env bash
# Re-fetch the large / gitignored datasets. The small curated test sets (data/wdr91, data/pgk2)
# are committed in the repo; this script only fetches what we deliberately keep OUT of git.
#
# Most of this is ALSO auto-downloaded the first time you run the relevant experiment, so this
# script is a convenience / pre-fetch. Run from repo root with the `mammal` env active.
set -euo pipefail
cd "$(dirname "$0")/.."
export USE_TF=0 USE_FLAX=0
PY="${PYTHON:-python}"

echo "=== DeepSol protein-solubility data (Zenodo 1162886) -> data/solubility/ ==="
$PY - <<'PY'
from mammal.examples.protein_solubility.pl_data_module import load_datasets
ds = load_datasets("data/solubility")
print("solubility folds:", {k: len(v) for k, v in ds.items()})
PY

echo "=== TDC datasets (auto-cached by PyTDC): BindingDB_Kd + TCREpitopeBinding/weber ==="
$PY - <<'PY'
from tdc.multi_pred import DTI, TCREpitopeBinding
DTI(name="BindingDB_Kd")                 # -> data/bindingdb_kd.tab
TCREpitopeBinding(name="weber")          # -> data/weber.tab
print("TDC datasets fetched")
PY

echo "Done. (data/bindingdb_kd.tab, data/weber.tab, data/solubility/ are gitignored by design.)"
