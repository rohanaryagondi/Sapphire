"""
aso_tox_seam.py — stdlib-only Sapphire seam for the ASO acute-toxicity delegate.

The Sapphire orchestrator runtime is stdlib-only.  sklearn/numpy/joblib live in the
predict.py subprocess.  This module shells out to that script and parses stdout JSON.
No third-party imports here.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

# ---------------------------------------------------------------------------
# Path resolution — robust regardless of CWD
# ---------------------------------------------------------------------------
_THIS_FILE = pathlib.Path(os.path.abspath(__file__))
# sapphire-orchestrator/tools/aso_tox_seam.py  →  repo root is two levels up
_REPO_ROOT = _THIS_FILE.parent.parent.parent
_PREDICT_PY = _REPO_ROOT / "tools" / "aso_tox" / "predict.py"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict(sequences: list[str]) -> dict:
    """
    Run predict.py on the given sequences list via subprocess.
    Returns parsed JSON dict.  On any failure returns an error envelope — never raises.
    """
    if not sequences:
        return {"predictions": [], "provenance": "aso-tox"}

    payload = json.dumps({"sequences": sequences})
    try:
        result = subprocess.run(
            [sys.executable, str(_PREDICT_PY), "--json"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {
                "predictions": [],
                "error": result.stderr.strip() or f"predict.py exited {result.returncode}",
                "provenance": "aso-tox",
            }
        return json.loads(result.stdout)
    except FileNotFoundError as exc:
        return {"predictions": [], "error": f"predict.py not found: {exc}", "provenance": "aso-tox"}
    except subprocess.TimeoutExpired:
        return {"predictions": [], "error": "predict.py timed out", "provenance": "aso-tox"}
    except Exception as exc:  # noqa: BLE001
        return {"predictions": [], "error": str(exc), "provenance": "aso-tox"}


def predict_findings(inputs: dict) -> dict:
    """
    Harness-compatible findings dict.  Reads sequences from inputs; returns one T2 fact
    per sequence.  If no sequences present returns facts=[] (honest empty — this tool
    only contributes when ASO sequences are available, i.e. downstream of the Design tool).
    """
    candidate = inputs.get("candidate", "")
    sequences: list[str] = (
        inputs.get("sequences")
        or inputs.get("aso_sequences")
        or []
    )

    if not sequences:
        return {"candidate": candidate, "facts": [], "provenance": "aso-tox"}

    raw = predict(sequences)

    if raw.get("error"):
        return {
            "candidate": candidate,
            "facts": [],
            "error": raw["error"],
            "provenance": "aso-tox",
        }

    facts = []
    for pred in raw.get("predictions", []):
        seq = pred.get("sequence", "")
        gbr = pred.get("gbr_predict_toxscore", 0.0)
        hag = pred.get("hagedorn_predict_toxscore", 0.0)
        label = pred.get("tox_label", "Unknown")
        facts.append({
            "value": f"ASO {seq}: GBR tox {gbr:.3f} ({label}); Hagedorn {hag:.1f}",
            "source": "Quiver ASO acute-tox model (GBR)",
            "tier": "T2",
        })

    return {"candidate": candidate, "facts": facts, "provenance": "aso-tox"}
