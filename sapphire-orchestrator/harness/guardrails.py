"""Mechanical guardrails enforcing the CLAUDE.md hard rules (spec §A.5).
Input guards BLOCK (return violations) — they never strip-and-proceed.

Data boundary — two layers at DIFFERENT stages (not one wrapping the other):
  * RUNTIME ENFORCER (this module, `data_boundary()`): scans an agent's *inputs* for
    internal key names (`_INTERNAL_KEYS`) and internal identifier patterns
    (`_FORBIDDEN_PATTERNS`). This is what actually blocks a dispatch. It is shared by
    the external-fetch agent guards AND the public-only memory subsystem, so it
    deliberately keys on raw internal data (ids/scores/traces), NOT on a fact's
    `provenance` label — blanket-blocking every `provenance=moat-real` dict here would
    wrongly refuse the legitimate internal-data-in-memory / internal-data-to-reasoning
    flows the data-boundary rule explicitly permits.
  * CLASSIFICATION LAYER (`contracts.provenance`: `plane_for` / `is_boundary_violation`):
    a higher-level view used to tag dossier facts with their plane (internal/external)
    for the contract + UI, and to reason about routing. It expresses the rule; it is not
    a second runtime gate. The two are complementary, kept separate on purpose.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass


@dataclass
class Violation:
    guardrail: str
    detail: str
    path: str = ""


# Internal-only keys that must never leave Quiver to EMET / web / Q-Models.
_INTERNAL_KEYS = frozenset({
    "s_internal", "internal_score", "ep_crispr", "latent_vector",
    "functional_traces", "candidate_id", "crispr_score",
})
# Patterns of internal identifiers/fields (defense in depth over key names).
_FORBIDDEN_PATTERNS = [
    re.compile(r"\bQS\d{3,}\b"),              # internal candidate ids e.g. QS00123
    re.compile(r"s_internal"),
    re.compile(r"latent[_-]?vector"),
    re.compile(r"functional[_-]?trace"),
    re.compile(r"\bep[_-]?crispr\b", re.IGNORECASE),
]
# Every internal key is ALSO a value-side pattern, so an internal term embedded in a
# string value (not just used as a key) is blocked too. Word-boundary, escaped.
_FORBIDDEN_PATTERNS += [re.compile(r"\b" + re.escape(k) + r"\b") for k in sorted(_INTERNAL_KEYS)]


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def data_boundary(inputs) -> "list[Violation]":
    viols = []
    # Internal key names anywhere in the (possibly nested) inputs.
    for key in _walk_keys(inputs):
        if isinstance(key, str) and key in _INTERNAL_KEYS:
            viols.append(Violation("data_boundary", f"internal key present: {key}", key))
    # Internal identifier patterns anywhere in the serialized payload (key OR value).
    blob = json.dumps(inputs, ensure_ascii=False)
    for pat in _FORBIDDEN_PATTERNS:
        if pat.search(blob):
            viols.append(Violation("data_boundary", f"forbidden pattern: {pat.pattern}", "<redacted>"))
    return viols


def public_identifiers_only(inputs) -> "list[Violation]":
    # Stricter complement: same blocklist, reported under its own guardrail name.
    return [Violation("public_identifiers_only", v.detail, v.path) for v in data_boundary(inputs)]


def facts_only_cited(contract, output, ctx) -> list:
    """Every row in output["facts"] needs non-empty source + a tier.
    A row with flag == "VETO" must have tier == "T1" (else a violation)."""
    viols = []
    for i, row in enumerate(output.get("facts", []) or []):
        if not (row.get("source") or "").strip():
            viols.append(Violation("facts_only_cited", "fact row missing source", f"facts[{i}]"))
        if not row.get("tier"):
            viols.append(Violation("facts_only_cited", "fact row missing tier", f"facts[{i}]"))
        if row.get("flag") == "VETO" and row.get("tier") != "T1":
            viols.append(Violation("facts_only_cited", "VETO fact must be tier T1", f"facts[{i}]"))
    return viols


def must_cite_dossier(contract, output, ctx) -> list:
    """Every item in output["fact_claims"] must have a cite present in ctx["dossier_fields"]."""
    valid = set(ctx.get("dossier_fields", []) or [])
    viols = []
    for i, claim in enumerate(output.get("fact_claims", []) or []):
        cite = claim.get("cite")
        if cite not in valid:
            viols.append(Violation("must_cite_dossier", f"claim cites unknown dossier field {cite!r}", f"fact_claims[{i}]"))
    return viols


def veto_is_gate(contract, output, ctx) -> list:
    """If output marks a veto (stance == "no_go" or any fact flag == "VETO")
    it must not also set output.get("action") == "drop" (veto is a surfaced gate, never silent kill)."""
    is_veto = output.get("stance") == "no_go" or any(
        (row.get("flag") == "VETO") for row in (output.get("facts", []) or [])
    )
    if is_veto and output.get("action") == "drop":
        return [Violation("veto_is_gate", "veto must be surfaced as a gate, not a silent drop", "action")]
    return []


def emet_tab_discipline(contract, output, ctx) -> list:
    """An emet output must carry a non-empty provenance/evidence trail;
    minimally a violation if output lacks facts."""
    if "facts" not in output:
        return [Violation("emet_tab_discipline", "emet output carries no evidence trail (no facts)", "facts")]
    return []


def stamp_provenance(contract, output) -> dict:
    """Returns a copy of output with provenance set to contract.provenance_label
    (and stamped onto each facts row if present). Raises nothing; the only transform guard."""
    out = copy.deepcopy(output)
    out["provenance"] = contract.provenance_label
    for row in out.get("facts", []) or []:
        row["provenance"] = contract.provenance_label
    return out
