"""Track registry — the single in-process view of `tracks.json`.

`tracks.json` is the DATA CONTRACT (generated deterministically from the
canonical scorecard). This module loads it ONCE at import and exposes typed
accessors so nothing else in the backend has to re-read or re-parse the file:

    meta()            -> the `_meta` block (title/subtitle/banner/badges)
    badges()          -> the badge dictionary {id -> {label, emoji, desc}}
    resolve_badge(id) -> one badge dict (label/emoji/desc), with a safe fallback
    all_tracks()      -> the full ordered list of track dicts
    get_track(id)     -> one track dict (raises KeyError on unknown id)
    track_ids()       -> ordered list of track ids
    batch_tracks()    -> ids of tracks that declare a `batch` key

The registry never mutates the loaded data; callers that need to strip or
reshape (e.g. drop the heavy `stub_prediction` for the list endpoint) copy
first. `get_track` returns the live dict on purpose — `inference.run_inference`
reads `stub_prediction`/`informational`/`aws_model_key` straight off it.
"""

from __future__ import annotations

import json
from pathlib import Path

# tracks.json lives one directory up from this package (ui/explorer/tracks.json).
TRACKS_PATH = Path(__file__).resolve().parents[1] / "tracks.json"

with open(TRACKS_PATH, encoding="utf-8") as _f:
    _DATA: dict = json.load(_f)

_META: dict = _DATA.get("_meta", {})
_TRACKS: list[dict] = _DATA.get("tracks", [])
# id -> track, preserving the order tracks.json was authored in (track `n` order).
_BY_ID: dict[str, dict] = {t["id"]: t for t in _TRACKS}

# Fallback badge so a typo in a track's `badge` field never 500s a response.
_UNKNOWN_BADGE = {"label": "Unknown", "emoji": "•", "desc": "No badge metadata."}


def meta() -> dict:
    """The `_meta` block: title, subtitle, banner, generated_from, badges."""
    return _META


def badges() -> dict:
    """Badge metadata keyed by badge id (reliable/caution/split/...)."""
    return _META.get("badges", {})


def resolve_badge(badge_id: str | None) -> dict:
    """Resolve a track's `badge` id to its {label, emoji, desc} dict.

    Returns a copy (with the resolved `badge` id attached) so callers can hand
    it straight into a response without mutating the registry.
    """
    info = badges().get(badge_id or "", _UNKNOWN_BADGE)
    return {"badge": badge_id, **info}


def all_tracks() -> list[dict]:
    """The full ordered list of track dicts (the live objects from tracks.json)."""
    return _TRACKS


def track_ids() -> list[str]:
    """Ordered track ids."""
    return [t["id"] for t in _TRACKS]


def get_track(track_id: str) -> dict:
    """One track dict by id. Raises KeyError if the id is unknown."""
    return _BY_ID[track_id]


def has_track(track_id: str) -> bool:
    return track_id in _BY_ID


def batch_tracks() -> list[str]:
    """Ids of tracks that declare a `batch` key (currently bbbp, toxicity)."""
    return [t["id"] for t in _TRACKS if "batch" in t]


def is_batchable(track_id: str) -> bool:
    return track_id in _BY_ID and "batch" in _BY_ID[track_id]
