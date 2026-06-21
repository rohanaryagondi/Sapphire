"""Persistent prediction history (append-only JSONL) — ported for the Explorer.

Every successful prediction (single or batch) is logged here so the History tab
can show past runs — and so a fresh session can see what was run before.
Server-side (not browser localStorage) on purpose: it survives restarts and
browser-cache clears, and is one source of truth a new session can read.

Storage: a JSONL file (one record per line). Path defaults to
`ui/explorer/backend/_history.jsonl` (gitignored) and is overridable via the
`EXPLORER_HISTORY` env var (tests point it at a temp file). The path is resolved
at call time so a test can set the env var before the first write.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / "_history.jsonl"
_lock = threading.Lock()


def _history_path() -> Path:
    return Path(os.environ.get("EXPLORER_HISTORY", str(_DEFAULT_PATH)))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summarize(prediction: dict) -> dict:
    """Pull a compact, score_kind-agnostic summary out of any track prediction.

    Tracks emit different prediction shapes (probability/affinity/embedding/
    ranking/panel/...). We keep whichever common fields are present so the
    History row can show a one-line gist without the frontend special-casing
    every kind.
    """
    p = prediction or {}
    shortlist = p.get("shortlist") or []
    ranking = p.get("ranking") or []
    return {
        "score_kind": p.get("score_kind"),
        "value": p.get("value"),
        "units": p.get("units"),
        "call": p.get("call") or p.get("binder_call"),
        "nearest_family": p.get("nearest_family"),
        "confidence": p.get("confidence"),
        "affinity": p.get("affinity"),
        "rank_percentile": p.get("rank_percentile"),
        "top": (
            (shortlist[0].get("drug") if shortlist else None)
            or (ranking[0].get("target") if ranking else None)
        ),
    }


def append(
    track: str,
    inputs: dict,
    prediction: dict,
    badge: str,
    model: str,
    stubbed: bool,
    label: str | None = None,
) -> dict:
    """Append one run to the log and return the stored record.

    `inputs` should be the ORIGINAL request so a row can be loaded back into its
    tab and re-run. `badge` is the track's verdict badge id; `model` is the
    best-model name; `stubbed` flags demo-mode runs.
    """
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now_iso(),
        "track": track,
        "label": label,
        "inputs": {k: v for k, v in (inputs or {}).items() if v is not None},
        "summary": _summarize(prediction),
        "badge": badge,
        "model": model,
        "stubbed": bool(stubbed),
    }
    line = json.dumps(rec)
    path = _history_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return rec


def recent(limit: int = 100, track: str | None = None) -> list[dict]:
    """Up to `limit` most-recent records (newest first), optionally by track."""
    path = _history_path()
    if not path.exists():
        return []
    with _lock:
        lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if track and r.get("track") != track:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def count() -> int:
    path = _history_path()
    if not path.exists():
        return 0
    with _lock:
        return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def clear() -> None:
    path = _history_path()
    with _lock:
        if path.exists():
            path.unlink()
