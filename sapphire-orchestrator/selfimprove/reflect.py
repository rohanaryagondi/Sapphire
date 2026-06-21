"""Post-engagement reflect (spec §6.7): read the harness trace, write durable memory
(Tier-1 auto). Read-only on the trace; write-only on memory (which enforces the boundary)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from memory import blank_entities, write

_DEFAULT_ENG = Path(__file__).resolve().parents[2] / "RohanOnly" / "engagements"


def _trace_path(engagement_id: str) -> Path:
    base = Path(os.environ.get("SAPPHIRE_ENGAGEMENTS_DIR", str(_DEFAULT_ENG)))
    return base / engagement_id / "trace.jsonl"


def _rows(engagement_id: str) -> list:
    p = _trace_path(engagement_id)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def reflect(engagement_id: str) -> dict:
    rows = _rows(engagement_id)
    fallback = blank_entities()
    for row in rows:
        if row.get("type") == "engagement_open":
            pe = (row.get("plan") or {}).get("entities")
            if isinstance(pe, dict):
                for k in fallback:
                    fallback[k] = sorted(set(fallback[k]) | set(pe.get(k, [])))
        out = row.get("output")
        if isinstance(out, dict) and out.get("candidate"):
            fallback["genes"] = sorted(set(fallback["genes"]) | {out["candidate"]})

    def _has_entities(e):
        return bool(e) and any(e.get(k) for k in ("genes", "smiles", "diseases", "drugs"))

    written = []
    for row in rows:
        if row.get("type") == "engagement_close":
            syn = row.get("synthesis", {}) or {}
            ents = syn.get("entities") if _has_entities(syn.get("entities")) else fallback
            written.append(write({
                "type": "conclusion", "engagement_id": engagement_id, "entities": ents,
                "provenance": "synthesis",
                "payload": {"recommendation": syn.get("recommendation", ""),
                            "confidence": syn.get("confidence", "")},
            }))
            if syn.get("proposed_experiment"):
                written.append(write({
                    "type": "experiment_proposal", "engagement_id": engagement_id, "entities": ents,
                    "provenance": "synthesis",
                    "payload": {"experiment": syn["proposed_experiment"]},
                }))
            continue

        out = row.get("output")
        if isinstance(out, dict) and out.get("facts"):
            # prefer a full entity set carried on the row; fall back to the single candidate gene
            if _has_entities(row.get("entities")):
                ents = row["entities"]
            else:
                candidate = out.get("candidate", "")
                ents = blank_entities()
                if candidate:
                    ents["genes"] = [candidate]
            for f in out["facts"]:
                rtype = "divergence" if f.get("flag") == "DIVERGENCE" else "fact"
                written.append(write({
                    "type": rtype, "engagement_id": engagement_id, "entities": ents,
                    "provenance": row.get("provenance", "synthesis"),
                    "tier": f.get("tier", "T3"),
                    "payload": {"value": f.get("value", ""), "source": f.get("source", "")},
                }))
    return {"engagement_id": engagement_id, "written": len(written), "records": written}
