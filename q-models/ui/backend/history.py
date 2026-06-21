"""Persistent prediction history (append-only JSONL).

Every successful prediction is logged here so the History tab can show past
searches — and so a fresh session can see what was run before. Server-side (not
browser localStorage) on purpose: it survives restarts and browser-cache clears,
and is one source of truth a new Claude session can read.

Storage: a JSONL file (one record per line). Path defaults to
`ui/backend/_history.jsonl` (gitignored) and is overridable via the
`MAMMAL_UI_HISTORY` env var (tests point it at a temp file).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
HISTORY_PATH = Path(
    os.environ.get("MAMMAL_UI_HISTORY", str(_REPO / "ui" / "backend" / "_history.jsonl"))
)
_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(task: str, inputs: dict, prediction: dict, badge: str, provider_name: str) -> dict:
    """Append one prediction to the log and return the stored record.

    `inputs` should be the ORIGINAL request (pre-standardization / pre-UniProt-fetch)
    so a row can be loaded back into its tab and re-run.
    """
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now_iso(),
        "task": task,
        "inputs": {k: v for k, v in inputs.items() if v is not None},
        "summary": {
            "score_kind": prediction.get("score_kind"),
            "value": prediction.get("value"),
            "pred_class": prediction.get("pred_class"),
            "units": prediction.get("units"),
            "text": (prediction.get("text") or [None])[0],
            "nearest_family": prediction.get("nearest_family"),
        },
        "badge": badge,
        "provider": provider_name,
    }
    line = json.dumps(rec)
    with _lock:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "a") as f:
            f.write(line + "\n")
    return rec


def recent(limit: int = 100, task: str | None = None) -> list[dict]:
    """Return up to `limit` most-recent records (newest first), optionally filtered by task."""
    if not HISTORY_PATH.exists():
        return []
    with _lock:
        lines = HISTORY_PATH.read_text().splitlines()
    out: list[dict] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if task and r.get("task") != task:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def count() -> int:
    if not HISTORY_PATH.exists():
        return 0
    with _lock:
        return sum(1 for ln in HISTORY_PATH.read_text().splitlines() if ln.strip())


def clear() -> None:
    with _lock:
        if HISTORY_PATH.exists():
            HISTORY_PATH.unlink()
