#!/usr/bin/env bash
# ============================================================================
# serve_local.sh — stand up the vendored Q-Models Explorer backend (the CPU
# tool endpoint the orchestrator's local-cpu tier calls) in an ISOLATED venv.
#
# SAFETY: this deliberately does NOT use the shared `mammal` conda env (which may
# belong to another project). It builds its own venv at .qm-venv. It never touches
# AWS. Stub mode by default; live-local if the joblibs in q-models/models/ exist.
#
#   bash sapphire-orchestrator/qmodels/serve_local.sh [PORT]   # default 8000
# ============================================================================
set -euo pipefail
PORT="${1:-8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
QM="$REPO/q-models"
VENV="$REPO/.qm-venv"

[ -d "$QM" ] || { echo "!! q-models/ not found at $QM"; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then
  echo "== creating isolated venv at $VENV =="
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.5" "markdown>=3.4" "httpx>=0.27"
fi

# EXPLORER_LOCAL_MODELS=1 turns on live-local DTI/BBBP/Tox IF the joblibs exist
# (q-models/models/cns_pertarget + derisking_local). Absent → graceful stub mode.
export EXPLORER_LOCAL_MODELS=1 USE_TF=0 USE_FLAX=0
echo "== serving vendored Explorer on http://127.0.0.1:$PORT (stub unless q-models/models/ present) =="
cd "$QM"
exec env PYTHONPATH=. "$VENV/bin/python" -m uvicorn ui.explorer.backend.app:app --host 127.0.0.1 --port "$PORT"
