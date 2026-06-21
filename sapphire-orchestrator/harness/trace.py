"""Append-only per-engagement trace (spec §A.6). Reuses the launcher.py ledger idiom:
one JSON object per line, each stamped with an ISO-8601 ts. The audit surface AND the
self-improvement loop's input. Dir override via SAPPHIRE_ENGAGEMENTS_DIR (tests)."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "RohanOnly" / "engagements"


def _base_dir() -> Path:
    return Path(os.environ.get("SAPPHIRE_ENGAGEMENTS_DIR", str(_DEFAULT_DIR)))


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def trace_path(engagement_id: str) -> Path:
    d = _base_dir() / engagement_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "trace.jsonl"


def _append(engagement_id: str, event: dict) -> None:
    with open(trace_path(engagement_id), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), **event}) + "\n")


def open_engagement(engagement_id: str, plan: dict) -> None:
    _append(engagement_id, {"type": "engagement_open", "engagement_id": engagement_id, "plan": plan})


def record(engagement_id: str, event: dict) -> None:
    _append(engagement_id, {"engagement_id": engagement_id, **event})


def close_engagement(engagement_id: str, synthesis: dict) -> None:
    _append(engagement_id, {"type": "engagement_close", "engagement_id": engagement_id, "synthesis": synthesis})
