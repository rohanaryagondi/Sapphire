# Sapphire Phase 5 — P0: Shared Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three shared contracts (a stdlib JSON-Schema validator, the provenance vocabulary, and the canonical EMET-envelope + memory-record schemas) that all four Phase-5 workstreams import, so the parallel tracks bind to one definition instead of drifting.

**Architecture:** A small, dependency-free `sapphire-orchestrator/contracts/` package. `jsonschema_min.py` is a stdlib validator over the exact schema subset the repo uses (`type/required/properties/additionalProperties/enum/items/$ref`). `provenance.py` is the canonical provenance vocabulary + a checker. `schemas.py` holds the EMET-envelope and memory-record JSON schemas as Python dicts. The harness, the memory store, and the EMET skill all import from here. This package is relocated-and-shared from the spec's original `harness/jsonschema_min.py` placement so memory/EMET can use the validator without importing the harness.

**Tech Stack:** Python 3, **stdlib only** (`json`, `pathlib`, `unittest`). No third-party dependencies.

## Global Constraints

- **Stdlib-only Python.** No new dependencies (matches `qmodels/` style). — copied from spec §1/§7.
- **Branch `Rohan`.** Commit per task. Do NOT push to main.
- **Provenance vocabulary (exact):** `emet-live`, `emet-mcp`, `memory-recall`, `persona-judgment`, `synthesis`, `live-local`, `gpu-async`, `gpu-disabled`, `stub`, `unavailable`, `mock`, plus `qmodels:<tool>` prefixed values. — spec §3.3.
- **Data boundary:** public identifiers only ever leave Quiver (gene symbols, SMILES, disease terms, drug/trial ids); internal scores/ids never enter shared artifacts. — spec §3.2, CLAUDE.md.
- **Memory records are append-only;** corrections append with `supersedes`, never mutate in place. — spec §3.2.

---

### Task 1: Stdlib JSON-Schema validator (`jsonschema_min`)

**Files:**
- Create: `sapphire-orchestrator/contracts/__init__.py`
- Create: `sapphire-orchestrator/contracts/jsonschema_min.py`
- Test: `sapphire-orchestrator/contracts/tests/test_jsonschema_min.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `validate(instance, schema, root=None, path="$") -> list[str]` — returns a list of human-readable error paths; empty list means valid. Used by the harness (`harness/runtime.py`), the memory store, and the EMET skill tests.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/contracts/tests/test_jsonschema_min.py
import unittest
from contracts.jsonschema_min import validate

OBJ = {
    "type": "object",
    "required": ["name", "n"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "n": {"type": "integer"},
        "kind": {"type": "string", "enum": ["a", "b"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}

class TestValidate(unittest.TestCase):
    def test_valid_object_passes(self):
        self.assertEqual(validate({"name": "x", "n": 3, "kind": "a", "tags": ["t"]}, OBJ), [])

    def test_missing_required_reports_path(self):
        errs = validate({"name": "x"}, OBJ)
        self.assertTrue(any("$.n: required field missing" == e for e in errs))

    def test_wrong_type_reports_and_stops_cascade(self):
        errs = validate({"name": "x", "n": "three"}, OBJ)
        self.assertTrue(any("$.n:" in e and "expected type" in e for e in errs))

    def test_bool_is_not_integer(self):
        errs = validate({"name": "x", "n": True}, OBJ)
        self.assertTrue(any("$.n:" in e for e in errs))

    def test_additional_property_rejected(self):
        errs = validate({"name": "x", "n": 1, "extra": 9}, OBJ)
        self.assertTrue(any("$.extra: additional property not allowed" == e for e in errs))

    def test_enum_violation(self):
        errs = validate({"name": "x", "n": 1, "kind": "z"}, OBJ)
        self.assertTrue(any("$.kind:" in e and "enum" in e for e in errs))

    def test_array_items_path(self):
        errs = validate({"name": "x", "n": 1, "tags": ["ok", 5]}, OBJ)
        self.assertTrue(any("$.tags[1]:" in e for e in errs))

    def test_ref_resolves_against_root(self):
        root = {"schemas": {"leaf": {"type": "string"}},
                "type": "object", "properties": {"v": {"$ref": "#/schemas/leaf"}},
                "required": ["v"], "additionalProperties": False}
        self.assertEqual(validate({"v": "s"}, root), [])
        self.assertTrue(validate({"v": 1}, root))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_jsonschema_min -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'contracts.jsonschema_min'`.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/contracts/__init__.py
# (empty — marks the package)
```

```python
# sapphire-orchestrator/contracts/jsonschema_min.py
"""A stdlib JSON-Schema validator over the subset Sapphire's contracts use:
type, required, properties, additionalProperties:false, enum, items, $ref.
validate(...) returns a list of error-path strings ([] == valid)."""
from __future__ import annotations

_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


def _resolve(ref: str, root: dict):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r} (only #/ local refs)")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance, schema, root=None, path="$") -> list[str]:
    if root is None:
        root = schema
    if "$ref" in schema:
        schema = _resolve(schema["$ref"], root)
    errors: list[str] = []

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = False
        for tt in types:
            py = _TYPES[tt]
            if tt in ("integer", "number") and isinstance(instance, bool):
                continue  # bool is a subclass of int; never a number here
            if isinstance(instance, py):
                ok = True
                break
        if not ok:
            errors.append(f"{path}: expected type {t}, got {type(instance).__name__}")
            return errors  # type wrong → don't cascade into children

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if schema.get("type") == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}.{req}: required field missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in instance:
                if k not in props:
                    errors.append(f"{path}.{k}: additional property not allowed")
        for k, subschema in props.items():
            if k in instance:
                errors += validate(instance[k], subschema, root, f"{path}.{k}")

    if schema.get("type") == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errors += validate(item, item_schema, root, f"{path}[{i}]")

    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_jsonschema_min -v`
Expected: PASS (8 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/contracts/__init__.py sapphire-orchestrator/contracts/jsonschema_min.py sapphire-orchestrator/contracts/tests/test_jsonschema_min.py
git commit -m "P0 Task 1: stdlib JSON-Schema validator (jsonschema_min)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Provenance vocabulary (`provenance`)

**Files:**
- Create: `sapphire-orchestrator/contracts/provenance.py`
- Test: `sapphire-orchestrator/contracts/tests/test_provenance.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PROVENANCE: frozenset[str]` (the fixed labels) and `is_valid_provenance(p) -> bool` (accepts a fixed label or any `qmodels:<tool>` value). Used by the harness `stamp_provenance` guardrail and the memory store.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/contracts/tests/test_provenance.py
import unittest
from contracts.provenance import PROVENANCE, is_valid_provenance

class TestProvenance(unittest.TestCase):
    def test_fixed_labels_present(self):
        for label in ["emet-live", "emet-mcp", "memory-recall", "persona-judgment",
                      "synthesis", "live-local", "gpu-async", "gpu-disabled",
                      "stub", "unavailable", "mock"]:
            self.assertIn(label, PROVENANCE)

    def test_fixed_label_valid(self):
        self.assertTrue(is_valid_provenance("emet-live"))

    def test_qmodels_prefixed_valid(self):
        self.assertTrue(is_valid_provenance("qmodels:boltz2"))

    def test_unknown_invalid(self):
        self.assertFalse(is_valid_provenance("made-up"))

    def test_non_string_invalid(self):
        self.assertFalse(is_valid_provenance(None))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_provenance -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'contracts.provenance'`.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/contracts/provenance.py
"""The canonical Sapphire provenance vocabulary (spec §3.3). Every artifact the
Console renders carries one of these; nothing is silently mocked."""
from __future__ import annotations

PROVENANCE = frozenset({
    # Phase 5 additions
    "emet-live", "emet-mcp", "memory-recall", "persona-judgment", "synthesis",
    # existing
    "live-local", "gpu-async", "gpu-disabled", "stub", "unavailable", "mock",
})


def is_valid_provenance(p) -> bool:
    if not isinstance(p, str):
        return False
    return p in PROVENANCE or p.startswith("qmodels:")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_provenance -v`
Expected: PASS (5 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/contracts/provenance.py sapphire-orchestrator/contracts/tests/test_provenance.py
git commit -m "P0 Task 2: canonical provenance vocabulary + checker

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Canonical schemas (EMET envelope + memory record)

**Files:**
- Create: `sapphire-orchestrator/contracts/schemas.py`
- Test: `sapphire-orchestrator/contracts/tests/test_schemas.py`

**Interfaces:**
- Consumes: `contracts.jsonschema_min.validate`, `contracts.provenance.is_valid_provenance`.
- Produces: `EMET_ENVELOPE_SCHEMA: dict` and `MEMORY_RECORD_SCHEMA: dict` (JSON-Schema dicts per spec §3.1 / §3.2), plus `MEMORY_RECORD_TYPES: frozenset[str]`. Imported by the EMET skill (output validation) and the memory store (`memory.write`).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/contracts/tests/test_schemas.py
import unittest
from contracts.jsonschema_min import validate
from contracts.schemas import EMET_ENVELOPE_SCHEMA, MEMORY_RECORD_SCHEMA, MEMORY_RECORD_TYPES
from contracts.provenance import is_valid_provenance

VALID_EMET = {
    "candidate": "SCN11A",
    "emet_workflow": "Target Validation",
    "verdict": "pass",
    "evidence": [{"claim": "GoF validates analgesia", "source": "X et al, Nature 2016", "id_or_url": "PMID:26243570"}],
    "notes": "",
    "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
    "captured_at": "2026-06-21T00:00:00Z",
    "provenance": "emet-live",
}

VALID_MEMORY = {
    "id": "mem_12ab34cd",
    "type": "conclusion",
    "engagement_id": "eng_99ff00aa",
    "ts": "2026-06-21T00:00:00Z",
    "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["neuropathic pain"], "drugs": []},
    "payload": {"recommendation": "advance to cardiac-selectivity de-risking", "confidence": "conditional"},
    "provenance": "synthesis",
    "tier": "T2",
    "confidence": "high",
    "links": [],
    "supersedes": None,
}

class TestSchemas(unittest.TestCase):
    def test_valid_emet_envelope(self):
        self.assertEqual(validate(VALID_EMET, EMET_ENVELOPE_SCHEMA), [])

    def test_emet_bad_verdict_enum_caught(self):
        bad = dict(VALID_EMET, verdict="maybe")
        self.assertTrue(validate(bad, EMET_ENVELOPE_SCHEMA))

    def test_emet_missing_evidence_caught(self):
        bad = {k: v for k, v in VALID_EMET.items() if k != "evidence"}
        self.assertTrue(any("evidence: required" in e for e in validate(bad, EMET_ENVELOPE_SCHEMA)))

    def test_valid_memory_record(self):
        self.assertEqual(validate(VALID_MEMORY, MEMORY_RECORD_SCHEMA), [])

    def test_memory_bad_type_enum_caught(self):
        bad = dict(VALID_MEMORY, type="gossip")
        self.assertTrue(validate(bad, MEMORY_RECORD_SCHEMA))

    def test_memory_types_cover_spec(self):
        for t in ["fact", "conclusion", "experiment_proposal", "experiment_outcome",
                  "divergence", "persona_verdict", "calibration", "moat_blindspot"]:
            self.assertIn(t, MEMORY_RECORD_TYPES)

    def test_provenances_in_examples_are_valid(self):
        self.assertTrue(is_valid_provenance(VALID_EMET["provenance"]))
        self.assertTrue(is_valid_provenance(VALID_MEMORY["provenance"]))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_schemas -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'contracts.schemas'`.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/contracts/schemas.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest contracts.tests.test_schemas -v`
Expected: PASS (7 tests OK).

- [ ] **Step 5: Run the whole contracts package + commit**

Run: `cd sapphire-orchestrator && python -m unittest discover -s contracts/tests -v`
Expected: PASS (20 tests OK across all three modules).

```bash
git add sapphire-orchestrator/contracts/schemas.py sapphire-orchestrator/contracts/tests/test_schemas.py
git commit -m "P0 Task 3: canonical EMET-envelope + memory-record schemas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (P0 portion of §3):** §3.1 EMET envelope → Task 3 (`EMET_ENVELOPE_SCHEMA`). §3.2 memory record → Task 3 (`MEMORY_RECORD_SCHEMA`, append-only `supersedes` field present). §3.3 provenance vocab → Task 2. The stdlib validator the spec assigns to the harness (Appendix A.4) → Task 1, relocated to `contracts/` so memory/EMET share it (noted in Architecture). No P0 requirement is unaddressed.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows complete tests with concrete assertions. Clean.

**Type consistency:** `validate(instance, schema, root=None, path="$") -> list[str]` is defined once (Task 1) and consumed unchanged in Task 3's tests. `is_valid_provenance` / `PROVENANCE` (Task 2) are consumed unchanged in Task 3. `EMET_ENVELOPE_SCHEMA`, `MEMORY_RECORD_SCHEMA`, `MEMORY_RECORD_TYPES` names are consistent between Task 3's implementation and tests. Downstream plans (D/A/C) import these exact names.

**Note for downstream plans:** tests run with CWD = `sapphire-orchestrator/` so `import contracts...` resolves (matches how `qmodels` is imported in-repo). The harness's `jsonschema_min` references in spec Appendix A.4/A.9 resolve to `contracts.jsonschema_min`.
