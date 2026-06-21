"""Mechanical guardrails enforcing the CLAUDE.md hard rules (spec §A.5).
Input guards BLOCK (return violations) — they never strip-and-proceed."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class Violation:
    guardrail: str
    detail: str
    path: str = ""


# Internal-only keys that must never leave Quiver to EMET / web / Q-Models.
_INTERNAL_KEYS = {
    "s_internal", "internal_score", "ep_crispr", "latent_vector",
    "functional_traces", "candidate_id", "crispr_score",
}
# Patterns of internal identifiers/fields (defense in depth over key names).
_FORBIDDEN_PATTERNS = [
    re.compile(r"\bQS\d{3,}\b"),              # internal candidate ids e.g. QS00123
    re.compile(r"s_internal"),
    re.compile(r"latent[_-]?vector"),
    re.compile(r"functional[_-]?trace"),
    re.compile(r"\bep[_-]?crispr\b", re.IGNORECASE),
]


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def data_boundary(inputs) -> list:
    viols = []
    for key in _walk_keys(inputs):
        if isinstance(key, str) and key in _INTERNAL_KEYS:
            viols.append(Violation("data_boundary", f"internal key present: {key}", key))
    blob = json.dumps(inputs, ensure_ascii=False)
    for pat in _FORBIDDEN_PATTERNS:
        if pat.search(blob):
            viols.append(Violation("data_boundary", f"forbidden pattern: {pat.pattern}", "<redacted>"))
    return viols


def public_identifiers_only(inputs) -> list:
    # Stricter complement: same blocklist, reported under its own guardrail name.
    return [Violation("public_identifiers_only", v.detail, v.path) for v in data_boundary(inputs)]
