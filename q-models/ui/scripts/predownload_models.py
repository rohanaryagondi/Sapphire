"""Verify the local MAMMAL checkpoints are present (and optionally warm-load them).

The checkpoints already ship locally under `models/`, so this script's job is
verification, not download: it confirms each task's dir has `model.safetensors`
and a `tokenizer/` subdir, and with `--warm` pulls every task's model into memory
once to remove first-request latency. It reuses `mammal_runner.TASKS` /
`get_base_model` so it can never drift from the real load paths.

    python ui/scripts/predownload_models.py            # check presence
    python ui/scripts/predownload_models.py --warm     # check + load all models into RAM/MPS
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ui.backend import mammal_runner as mr  # noqa: E402

# task label -> local checkpoint dir(s) it needs under models/
REQUIRED: dict[str, list[str]] = {
    "dti": ["dti_bindingdb_pkd_peer"],
    "bbbp": ["moleculenet_bbbp"],
    "clintox_tox": ["moleculenet_clintox_tox"],
    "clintox_fda": ["moleculenet_clintox_fda"],
    "solubility": ["protein_solubility"],
    "tcr": ["tcr_epitope_bind"],
    "ppi / generation / embeddings": ["base_458m"],
}


def check() -> bool:
    print(f"Checking local checkpoints under {mr.MODELS}\n")
    ok = True
    for task, dirs in REQUIRED.items():
        for d in dirs:
            p = mr.MODELS / d
            has_w = (p / "model.safetensors").exists()
            has_t = (p / "tokenizer").is_dir()
            good = has_w and has_t
            ok = ok and good
            print(f"  {'✓' if good else '✗'}  {task:32s} {d:24s} "
                  f"safetensors={has_w} tokenizer={has_t}")
    return ok


def warm() -> None:
    print("\nWarming models into memory (loads several GB; first time is slow)…")
    for slug, spec in mr.TASKS.items():
        for prov in spec.providers:
            print(f"  warming {slug:14s} :: {prov.name}", flush=True)
            prov._ensure()
    print("  warming base_458m (ppi / generation / embeddings)", flush=True)
    mr.get_base_model()
    print("Done — models cached for this process.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warm", action="store_true", help="load every model into memory after checking")
    args = ap.parse_args()

    present = check()
    if not present:
        print("\n✗ Missing checkpoint(s). They live on the AWS volume / HF hub — see "
              "models/ notes in CLAUDE.md and aws/RETRIEVE.md.")
        sys.exit(1)
    print("\n✓ All required checkpoints present.")
    if args.warm:
        warm()


if __name__ == "__main__":
    main()
