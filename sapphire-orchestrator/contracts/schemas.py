"""Canonical shared schemas (spec §3.1 EMET envelope, §3.2 memory record).
JSON-Schema dicts validated by contracts.jsonschema_min."""
from __future__ import annotations

EMET_ENVELOPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidate", "emet_workflow", "verdict", "evidence", "notes",
                 "chat_url", "captured_at", "provenance"],
    "properties": {
        "candidate": {"type": "string"},
        "emet_workflow": {"type": "string", "enum": [
            "Drug Safety", "Target Validation", "Pathway Analysis",
            "Quantitative Evidence", "Database Q&A"]},
        "verdict": {"type": "string", "enum": ["no_go", "flag", "pass"]},
        "evidence": {"type": "array", "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["claim", "source", "id_or_url"],
            "properties": {
                "claim": {"type": "string"},
                "source": {"type": "string"},
                "id_or_url": {"type": "string"},
            },
        }},
        "notes": {"type": "string"},
        "chat_url": {"type": "string"},
        "captured_at": {"type": "string"},
        "provenance": {"type": "string", "enum": ["emet-live", "emet-mcp"]},
    },
}

MEMORY_RECORD_TYPES = frozenset({
    "fact", "conclusion", "experiment_proposal", "experiment_outcome",
    "divergence", "persona_verdict", "calibration", "moat_blindspot",
})

MEMORY_RECORD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "type", "engagement_id", "ts", "entities", "payload",
                 "provenance", "tier", "confidence", "links", "supersedes"],
    "properties": {
        "id": {"type": "string"},
        "type": {"type": "string", "enum": sorted(MEMORY_RECORD_TYPES)},
        "engagement_id": {"type": "string"},
        "ts": {"type": "string"},
        "entities": {
            "type": "object",
            "additionalProperties": False,
            "required": ["genes", "smiles", "diseases", "drugs"],
            "properties": {
                "genes": {"type": "array", "items": {"type": "string"}},
                "smiles": {"type": "array", "items": {"type": "string"}},
                "diseases": {"type": "array", "items": {"type": "string"}},
                "drugs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "payload": {"type": "object"},
        "provenance": {"type": "string"},
        "tier": {"type": "string", "enum": ["T1", "T2", "T3", "T4"]},
        "confidence": {"type": "string", "enum": ["high", "med", "low"]},
        "links": {"type": "array", "items": {"type": "string"}},
        "supersedes": {"type": ["string", "null"]},
    },
}
