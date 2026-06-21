#!/usr/bin/env bash
# On-instance setup for the MAMMAL fine-tune pilot. Run in tmux; logs to setup.log.
set -euxo pipefail
source /opt/pytorch/bin/activate
export HF_HOME=/mnt/rohan/mammal_ft/hf_cache USE_TF=0 USE_FLAX=0
WORK=/mnt/rohan/mammal_ft
cd "$WORK"

nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python -c "import torch;print('PRE torch',torch.__version__,'cuda',torch.cuda.is_available())"

# clone upstream MAMMAL onto the persistent volume
[ -d biomed-multi-alignment ] || git clone --depth 1 https://github.com/BiomedSciAI/biomed-multi-alignment.git
cd biomed-multi-alignment

# install mammal + deps. --no-build-isolation keeps the DLAMI torch 2.7 in place.
pip install -e . 2>&1 | tail -12
pip install -q PyTDC rdkit pytorch-lightning hydra-core 2>&1 | tail -6

# CRITICAL guard: confirm the DLAMI torch + CUDA survived the install (mammal must not downgrade it)
python -c "import torch;print('POST torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))"

# warm the base checkpoint to the volume HF cache (~1.8GB)
python - <<'PY'
import os; os.environ["USE_TF"]="0"; os.environ["USE_FLAX"]="0"
from mammal.model import Mammal
m = Mammal.from_pretrained("ibm/biomed.omics.bl.sm.ma-ted-458m")
print("base params:", sum(p.numel() for p in m.parameters()))
PY

echo "=== examples (our fine-tune templates) ==="
ls mammal/examples
echo "=== carcinogenicity example files (binary-classifier template to adapt for BBBP + PGK2) ==="
find mammal/examples/carcinogenicity -type f
echo "=== SETUP_DONE ==="
