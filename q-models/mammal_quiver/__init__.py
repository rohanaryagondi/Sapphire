"""mammal_quiver — thin wrappers around IBM's MAMMAL foundation model for the
Quiver exploration (DTI binding, compound/protein embeddings, reference data).

IMPORTANT — TensorFlow deadlock workaround:
    On macOS, `transformers` auto-imports the installed TensorFlow, which
    deadlocks at import (`[mutex.cc:452] RAW: Lock blocking`). MAMMAL inference
    is pure PyTorch, so TF is never needed. We disable the TF/Flax backends
    HERE, at package import, BEFORE anything pulls in transformers/mammal.
    Any ad-hoc REPL that does not import this package first must export
    `USE_TF=0` (and `USE_FLAX=0`) manually.
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

__all__ = ["dti", "embed", "sequences"]
