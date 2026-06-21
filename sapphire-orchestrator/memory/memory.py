"""Append-only memory store (spec §3.2/§6.1). Every write is public-identifiers-only
(harness data_boundary) and schema-valid (MEMORY_RECORD_SCHEMA). Never mutates in place."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path

from contracts.jsonschema_min import validate
from contracts.schemas import MEMORY_RECORD_SCHEMA, MEMORY_RECORD_TYPES
from harness.guardrails import data_boundary

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "RohanOnly" / "memory"


class MemoryRefusal(Exception):
    """Raised when a record would violate the boundary or schema. Never written."""


def _dir() -> Path:
    d = Path(os.environ.get("SAPPHIRE_MEMORY_DIR", str(_DEFAULT_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store() -> Path:
    return _dir() / "store.jsonl"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def blank_entities() -> dict:
    return {"genes": [], "smiles": [], "diseases": [], "drugs": []}


def _gen_id(record: dict) -> str:
    raw = json.dumps(record.get("payload", {}), sort_keys=True) + record.get("ts", "") + record.get("type", "")
    return "mem_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def write(record: dict) -> dict:
    rec = dict(record)
    rec.setdefault("ts", _now())
    rec.setdefault("engagement_id", "")
    rec.setdefault("entities", blank_entities())
    rec.setdefault("payload", {})
    rec.setdefault("provenance", "synthesis")
    rec.setdefault("tier", "T3")
    rec.setdefault("confidence", "med")
    rec.setdefault("links", [])
    rec.setdefault("supersedes", None)
    rec.setdefault("id", _gen_id(rec))

    if rec.get("type") not in MEMORY_RECORD_TYPES:
        raise MemoryRefusal(f"unknown record type {rec.get('type')!r}")
    viol = data_boundary(rec)
    if viol:
        raise MemoryRefusal(f"data boundary: {viol[0].detail}")
    errs = validate(rec, MEMORY_RECORD_SCHEMA, MEMORY_RECORD_SCHEMA)
    if errs:
        raise MemoryRefusal(f"schema: {errs[0]}")

    with open(_store(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read_all() -> list:
    p = _store()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def rebuild_index() -> dict:
    idx: dict = {}
    for r in read_all():
        for vals in r.get("entities", {}).values():
            for v in vals:
                idx.setdefault(v, []).append(r["id"])
    (_dir() / "index.json").write_text(json.dumps(idx, indent=2), encoding="utf-8")
    return idx


# recall + record_outcome are added in Tasks 2 and 3.
def recall(*a, **k):  # placeholder replaced in Task 2
    raise NotImplementedError


def record_outcome(*a, **k):  # placeholder replaced in Task 3
    raise NotImplementedError
