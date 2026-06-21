#!/bin/bash
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#SBATCH -J boltz_run
#SBATCH -o /nfs/roberts/scratch/pi_mg269/rag88/QVR/projects/Sapphire/boltz_run/logs/run_%j.out
#SBATCH -e /nfs/roberts/scratch/pi_mg269/rag88/QVR/projects/Sapphire/boltz_run/logs/run_%j.err
set -uo pipefail

# args: $1 = path to complexes json   $2 = output subdir name under boltz_run/
DATA="${1:?need data json path}"
OUTSUB="${2:?need output subdir}"

BASE=/nfs/roberts/scratch/pi_mg269/rag88/QVR/projects/Sapphire/boltz_run
REPO=/nfs/roberts/scratch/pi_mg269/rag88/QVR/projects/Sapphire/Q-Mammal
export BOLTZ_CACHE=$BASE/cache
export HF_HOME=$BASE/hf
export BOLTZ_OUT=$BASE/$OUTSUB
export TMPDIR=$BASE/tmp
# First-complex budget: cold weights (~10GB) + cold ColabFold MSA queue can be slow.
export BOLTZ_PREFLIGHT_TIMEOUT_S=${BOLTZ_PREFLIGHT_TIMEOUT_S:-7200}   # 2h
export BOLTZ_PAIR_TIMEOUT_S=${BOLTZ_PAIR_TIMEOUT_S:-3600}             # 1h subsequent (big Nav proteins)
mkdir -p "$BOLTZ_OUT" "$TMPDIR"

echo "=== node=$(hostname)  data=$DATA  out=$BOLTZ_OUT ==="; date
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
source "${VENV:-$BASE/venv_cu128}/bin/activate"
echo "python=$(which python)  boltz=$(which boltz)"
python -c "import torch;print('torch',torch.__version__,'cuda?',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

RUNNER=${RUNNER:-$BASE/boltz_runner_nokernels.py}
echo "runner=$RUNNER"
python "$RUNNER" "$DATA"
echo "=== RUN_EXIT=$? ==="; date
echo "=== results.json head ==="
python -c "import json;d=json.load(open('$BOLTZ_OUT/results.json'));print('complexes:',len(d.get('complexes',[])));[print(' ',r['name'],'rc',r['rc'],'prob',r.get('prob_binder'),'t',r.get('elapsed_s')) for r in d.get('complexes',[])]" 2>&1 || echo "(no results.json yet)"
