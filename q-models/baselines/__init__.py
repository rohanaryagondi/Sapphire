"""baselines — challenger models (ConPLex, Boltz-2) evaluated head-to-head against
MAMMAL on Quiver's own DTI / binder-triage test sets.

Sibling of `mammal_quiver/`, deliberately kept separate so the validated MAMMAL
stack is never touched. The governing rule lives in `common.py`: we compare only
RANK-derived statistics across models (never raw pKd vs probability vs affinity).

TensorFlow deadlock workaround (same as mammal_quiver): some of these scripts
import transformers transitively; disable the TF/Flax backends at import so the
macOS `transformers` import does not deadlock.
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

__all__ = ["common", "conplex", "boltz"]
