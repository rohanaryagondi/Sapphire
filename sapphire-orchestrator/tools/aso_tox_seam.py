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
import re
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
# Sequence validation
# ---------------------------------------------------------------------------
# A valid ASO sequence is non-empty and consists solely of A/T/G/C characters
# (case-insensitive).  We normalise to uppercase before validating and before
# passing to predict.py (the GBR model was trained on uppercase ATGC strings).
# Callers that pass lowercase atgc are accepted — we uppercase silently so that
# the model receives the same encoding regardless of caller case conventions.
# Sequences with any non-ATGC character (digits, X, Y, Z, spaces, etc.) are
# rejected and recorded in the returned invalid_sequences list; they are NEVER
# passed to the model.
_VALID_SEQUENCE_RE = re.compile(r'^[ATGC]+$')


def _validate_sequences(sequences: list[str]) -> tuple[list[str], list[str]]:
    """
    Partition sequences into (valid, invalid).

    Normalisation: each sequence is stripped and uppercased before the ATGC
    check.  A non-empty sequence that passes the check is returned in uppercase
    form so the model always receives the canonical encoding.

    Returns:
        valid    — list of uppercased sequences that consist solely of A/T/G/C.
        invalid  — list of original (pre-normalisation) sequences that were
                   rejected, preserved as-is for honest error reporting.
    """
    valid: list[str] = []
    invalid: list[str] = []
    for seq in sequences:
        normed = seq.strip().upper()
        if normed and _VALID_SEQUENCE_RE.match(normed):
            valid.append(normed)
        else:
            invalid.append(seq)  # keep original for honest reporting
    return valid, invalid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict(sequences: list[str]) -> dict:
    """
    Run predict.py on the given sequences list via subprocess.

    Sequences are validated before scoring.  Any sequence containing
    non-ATGC characters (garbage DNA, gene symbols, etc.) is rejected and
    recorded in the returned ``invalid_sequences`` list — it is never passed
    to the GBR model.  Only the valid portion is scored.

    Returns parsed JSON dict.  On any failure returns an error envelope — never raises.
    The returned dict always carries:
        predictions       — list of per-sequence result dicts (only valid seqs)
        provenance        — "aso-tox"
        invalid_sequences — list of rejected input sequences (may be empty)
    """
    if not sequences:
        return {"predictions": [], "provenance": "aso-tox", "invalid_sequences": []}

    valid, invalid = _validate_sequences(sequences)

    if not valid:
        # All sequences were garbage — return honestly with no predictions.
        return {
            "predictions": [],
            "provenance": "aso-tox",
            "invalid_sequences": invalid,
        }

    payload = json.dumps({"sequences": valid})
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
                "invalid_sequences": invalid,
            }
        parsed = json.loads(result.stdout)
        # Merge invalid_sequences into the parsed result (predict.py doesn't know about them).
        parsed.setdefault("invalid_sequences", [])
        parsed["invalid_sequences"] = invalid + parsed["invalid_sequences"]
        return parsed
    except FileNotFoundError as exc:
        return {
            "predictions": [],
            "error": f"predict.py not found: {exc}",
            "provenance": "aso-tox",
            "invalid_sequences": invalid,
        }
    except subprocess.TimeoutExpired:
        return {
            "predictions": [],
            "error": "predict.py timed out",
            "provenance": "aso-tox",
            "invalid_sequences": invalid,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "predictions": [],
            "error": str(exc),
            "provenance": "aso-tox",
            "invalid_sequences": invalid,
        }


def predict_findings(inputs: dict) -> dict:
    """
    Harness-compatible findings dict.  Reads sequences from inputs; validates each
    sequence before scoring; returns one T2 fact per valid sequence.

    Invalid sequences (non-ATGC characters) are NOT scored — they are surfaced in
    ``invalid_sequences`` on the returned dict so the caller sees what was rejected
    rather than receiving silently fabricated facts.  This upholds CONVENTIONS §3
    (never fabricate; degrade honestly).

    If no sequences present returns facts=[] (honest empty — this tool only
    contributes when ASO sequences are available, i.e. downstream of the Design tool).
    """
    candidate = inputs.get("candidate", "")
    sequences: list[str] = (
        inputs.get("sequences")
        or inputs.get("aso_sequences")
        or []
    )

    if not sequences:
        return {"candidate": candidate, "facts": [], "provenance": "aso-tox", "invalid_sequences": []}

    raw = predict(sequences)

    invalid_seqs = raw.get("invalid_sequences", [])

    if raw.get("error"):
        return {
            "candidate": candidate,
            "facts": [],
            "error": raw["error"],
            "provenance": "aso-tox",
            "invalid_sequences": invalid_seqs,
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

    # Always emit invalid_sequences (consistent with predict()'s contract) so callers
    # — including the future ASO-Design tool — can rely on the key being present.
    return {
        "candidate": candidate,
        "facts": facts,
        "provenance": "aso-tox",
        "invalid_sequences": invalid_seqs,
    }
