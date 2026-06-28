"""Canonical schema for the `live_engine.run_live()` output — the stable contract
the front end (and the future LOKA adapter) consumes.

This dict IS the API. The schema is **additive-friendly**: object nodes do NOT set
`additionalProperties: false`, so serve.py / callers may stamp extra top-level keys
(`via`, `live`, …) without breaking validation. Required keys are the ones
`run_live` always emits; optional per-fact keys (`field`, `confidence`, `flag`) are
not required because not every fact source supplies them.

Validate with `validate_run_live(result) -> list[str]` ([] == conforms).
Stdlib-only (uses contracts.jsonschema_min). See `run_live_schema.md` for the prose.
"""
from __future__ import annotations

from . import jsonschema_min

# A dossier fact: the minimum every run_live fact carries. Sources may add
# `field` / `confidence` / `flag` — allowed (no additionalProperties:false).
# A3 (additive): `plane` is stamped by live_engine from contracts.provenance.plane_for(provenance).
# Values: "internal" (moat-real) or "external" (all other sources). Always present in run_live
# output; absent only in very old canned scenarios (treat missing plane as "external").
_FACT = {
    "type": "object",
    "required": ["value", "source", "tier", "provenance"],
    "properties": {
        "value": {"type": "string"},
        "source": {"type": "string"},
        "tier": {"type": "string"},
        "provenance": {"type": "string"},
        "plane": {"type": "string", "enum": ["internal", "external"]},
        "field": {"type": "string"},
        "confidence": {"type": "string"},
        "flag": {"type": "string", "enum": ["VETO", "DIVERGENCE", "KNOWN_UNKNOWN"]},
    },
}

_AGENT_STATUS = {
    "type": "object",
    "required": ["id", "status", "provenance"],
    "properties": {
        "id": {"type": "string"},
        "status": {"type": "string"},
        "provenance": {"type": "string"},
    },
}

# A round-1 partner verdict. Success and abstain paths share these keys; abstain
# adds `lens` / `conviction` — allowed.
_VERDICT = {
    "type": "object",
    "required": ["persona", "stance", "provenance", "status"],
    "properties": {
        "persona": {"type": "string"},
        "stance": {"type": "string"},
        "provenance": {"type": "string"},
        "status": {"type": "string"},
        "conviction": {"type": "integer"},
        "rationale": {"type": "string"},
        "fact_claims": {"type": "array"},
        "lens": {"type": "string"},
    },
}

RUN_LIVE_SCHEMA = {
    "type": "object",
    "required": [
        "query", "plan", "priors", "discover", "consult", "synthesize",
        "engagement_id", "reflection", "_via",
    ],
    "properties": {
        "query": {"type": "string"},
        "plan": {
            "type": "object",
            "required": ["deliverable", "disease", "modality", "agents", "panel"],
            "properties": {
                "deliverable": {"type": "string"},
                "disease": {"type": "string"},
                "modality": {"type": "string"},
                "agents": {"type": "array"},
                "panel": {"type": "array"},
                "class": {"type": "string"},
            },
        },
        "priors": {"type": "array"},
        "discover": {
            "type": "object",
            "required": ["dossier", "flags", "status", "agents"],
            "properties": {
                "dossier": {"type": "array", "items": _FACT},
                "flags": {
                    "type": "object",
                    "required": ["VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"],
                    "properties": {
                        "VETO": {"type": "array", "items": {"type": "string"}},
                        "DIVERGENCE": {"type": "array", "items": {"type": "string"}},
                        "KNOWN_UNKNOWNS": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "status": {"type": "string"},
                "agents": {"type": "array", "items": _AGENT_STATUS},
            },
        },
        "consult": {
            "type": "object",
            "required": ["round1"],
            "properties": {
                "round1": {"type": "array", "items": _VERDICT},
            },
        },
        "synthesize": {
            "type": "object",
            "required": ["recommendation", "confidence", "proposed_experiment", "entities"],
            "properties": {
                "recommendation": {"type": "string"},
                "confidence": {"type": "string"},
                "proposed_experiment": {"type": "string"},
                "entities": {"type": "object"},
            },
        },
        "engagement_id": {"type": "string"},
        "reflection": {
            "type": "object",
            "required": ["engagement_id", "written", "records"],
            "properties": {
                "engagement_id": {"type": "string"},
                "written": {"type": "integer"},  # count of memory records written
                "records": {"type": "array"},
            },
        },
        "_via": {"type": "string"},
    },
}


def validate_run_live(result) -> list[str]:
    """Return a list of schema-violation strings ([] == valid run_live output)."""
    return jsonschema_min.validate(result, RUN_LIVE_SCHEMA)
