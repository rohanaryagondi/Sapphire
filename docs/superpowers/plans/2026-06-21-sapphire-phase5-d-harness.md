# Sapphire Phase 5 — D: Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sapphire-orchestrator/harness/` — the single runtime every Sapphire agent runs through (declare → dispatch → validate → guard → stamp → trace), so agents conform to their contracts, stay in policy, and fail safe.

**Architecture:** A stdlib-only package. `harness.run(agent_id, inputs, *, engagement_id, ctx)` resolves a contract from `agents.json`, dispatches by `kind` (`python` / `qmodels-delegate` / `claude-subagent` / `emet-playwright`), validates output against its JSON schema (P0's `contracts.jsonschema_min`), runs named guardrails, repairs malformed output up to a bound, stamps provenance, appends a trace record, and returns a typed `AgentResult` — or a fail-safe abstain/escalate that NEVER fabricates. Dispatch backends are injectable so the whole package is tested offline (no live `claude`, no AWS). Imports P0: `contracts.jsonschema_min.validate`, `contracts.provenance.is_valid_provenance`.

**Tech Stack:** Python 3, **stdlib only** (`json`, `subprocess`, `hashlib`, `pathlib`, `dataclasses`, `re`, `datetime`, `unittest`).

## Global Constraints

- **Stdlib-only Python.** No third-party deps. — spec §1/§7.
- **Branch `Rohan`.** Commit per task. Do NOT push to main.
- **Import-by-CWD:** all tests run with CWD = `sapphire-orchestrator/` so `import harness…` and `import contracts…` resolve (mirrors `qmodels`).
- **Fail-safe, never fabricate:** on hard failure the harness returns a typed abstain envelope (`{"abstained": true, "reason": <code>, "would_need": <str>}`) or escalates — it never invents output. — spec §A.4/§A.7.
- **Guardrails are mechanical, not advisory.** `data_boundary`/`public_identifiers_only` BLOCK (never strip-and-proceed). Personas get empty `tools_allowed` AND `must_cite_dossier`. Every output is stamped via `stamp_provenance`. — spec §A.5.
- **Provenance vocabulary** comes from `contracts.provenance` (P0); stamped labels must satisfy `is_valid_provenance`. — spec §3.3.
- **Teardown/dispatch by contract only:** an agent not in `agents.json` is `unknown-agent` (a control error), never guessed. — spec §A.7.
- **Trace is append-only JSONL** at `RohanOnly/engagements/<id>/trace.jsonl` (override dir via env `SAPPHIRE_ENGAGEMENTS_DIR` for tests). — spec §A.6.

---

### Task 1: Core types + hashing (`harness/contracts.py`)

**Files:**
- Create: `sapphire-orchestrator/harness/__init__.py`
- Create: `sapphire-orchestrator/harness/contracts.py`
- Create: `sapphire-orchestrator/harness/tests/__init__.py`
- Test: `sapphire-orchestrator/harness/tests/test_contracts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Contract` dataclass (fields: `id, role, kind, spec, input_schema, output_schema, tools_allowed, guardrails, provenance_label, timeout_s, max_repair, on_hard_fail, veto_class, param`); `AgentResult` dataclass (`agent_id, ok, output, provenance, status, error, meta`); `canonical_json(obj) -> str`; `inputs_hash(agent_id, inputs) -> str` (returns `"sha256:<hex>"`).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_contracts.py
import unittest
from harness.contracts import Contract, AgentResult, canonical_json, inputs_hash

class TestContracts(unittest.TestCase):
    def test_contract_defaults(self):
        c = Contract(id="x", role="r", kind="python")
        self.assertEqual(c.tools_allowed, [])
        self.assertEqual(c.guardrails, [])
        self.assertEqual(c.max_repair, 2)
        self.assertEqual(c.on_hard_fail, "abstain")
        self.assertFalse(c.veto_class)

    def test_two_contracts_dont_share_mutable_defaults(self):
        a = Contract(id="a", role="", kind="python")
        b = Contract(id="b", role="", kind="python")
        a.tools_allowed.append("WebSearch")
        self.assertEqual(b.tools_allowed, [])  # no shared list

    def test_agent_result_shape(self):
        r = AgentResult(agent_id="x", ok=True, output={"a": 1}, provenance="synthesis", status="ok")
        self.assertIsNone(r.error)
        self.assertEqual(r.meta, {})

    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), canonical_json({"a": 2, "b": 1}))

    def test_inputs_hash_stable_and_prefixed(self):
        h1 = inputs_hash("agent", {"x": 1, "y": 2})
        h2 = inputs_hash("agent", {"y": 2, "x": 1})
        self.assertEqual(h1, h2)               # key order irrelevant
        self.assertTrue(h1.startswith("sha256:"))
        self.assertNotEqual(h1, inputs_hash("other", {"x": 1, "y": 2}))  # id participates

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_contracts -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.contracts'`.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/__init__.py
"""The Sapphire agent harness: one runtime every agent runs through."""
```

```python
# sapphire-orchestrator/harness/contracts.py
"""Core harness types + input hashing (spec §A.2/§A.3)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class Contract:
    id: str
    role: str
    kind: str                       # python | qmodels-delegate | claude-subagent | emet-playwright
    spec: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    tools_allowed: list = field(default_factory=list)
    guardrails: list = field(default_factory=list)
    provenance_label: str = "synthesis"
    timeout_s: int = 120
    max_repair: int = 2
    on_hard_fail: str = "abstain"    # abstain | escalate
    veto_class: bool = False
    param: str | None = None


@dataclass
class AgentResult:
    agent_id: str
    ok: bool
    output: dict
    provenance: str
    status: str                      # ok | abstained | escalated
    error: str | None = None
    meta: dict = field(default_factory=dict)


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def inputs_hash(agent_id: str, inputs) -> str:
    digest = hashlib.sha256((agent_id + "\n" + canonical_json(inputs)).encode("utf-8")).hexdigest()
    return "sha256:" + digest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_contracts -v`
Expected: PASS (5 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/__init__.py sapphire-orchestrator/harness/contracts.py sapphire-orchestrator/harness/tests/__init__.py sapphire-orchestrator/harness/tests/test_contracts.py
git commit -m "D Task 1: harness core types + input hashing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Agent registry (`harness/agents.json` + `load_registry`/`resolve`)

**Files:**
- Create: `sapphire-orchestrator/harness/agents.json`
- Modify: `sapphire-orchestrator/harness/contracts.py` (add `load_registry`, `resolve`)
- Test: `sapphire-orchestrator/harness/tests/test_registry.py`

**Interfaces:**
- Consumes: `Contract` (Task 1).
- Produces: `load_registry(path=None) -> dict`; `resolve(agent_id, registry=None) -> Contract` (raises `KeyError(agent_id)` if absent; inlines a top-level `{"$ref": "#/schemas/X"}` `output_schema`/`input_schema` to the concrete self-contained schema dict; maps `retry: {max_repair, on_hard_fail}` onto the Contract).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_registry.py
import unittest
from harness.contracts import load_registry, resolve, Contract

class TestRegistry(unittest.TestCase):
    def test_registry_loads(self):
        reg = load_registry()
        self.assertIn("agents", reg)
        self.assertIn("schemas", reg)

    def test_known_agents_present(self):
        ids = {a["id"] for a in load_registry()["agents"]}
        for needed in ["company-partner", "q-models-runner", "emet-runner", "fda-institutional-memory"]:
            self.assertIn(needed, ids)

    def test_resolve_returns_contract_with_retry_mapped(self):
        c = resolve("company-partner")
        self.assertIsInstance(c, Contract)
        self.assertEqual(c.kind, "claude-subagent")
        self.assertEqual(c.tools_allowed, [])           # personas get no tools
        self.assertIn("must_cite_dossier", c.guardrails)
        self.assertIsInstance(c.max_repair, int)

    def test_resolve_inlines_schema_ref(self):
        c = resolve("company-partner")
        # output_schema must be the concrete verdict schema dict, not a {"$ref": ...}
        self.assertNotIn("$ref", c.output_schema)
        self.assertEqual(c.output_schema.get("type"), "object")

    def test_unknown_agent_raises_keyerror(self):
        with self.assertRaises(KeyError):
            resolve("no-such-agent")

    def test_veto_class_flag(self):
        self.assertTrue(resolve("fda-institutional-memory").veto_class)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_registry -v`
Expected: FAIL — `agents.json` missing / `load_registry` not defined.

- [ ] **Step 3: Write minimal implementation**

```json
// sapphire-orchestrator/harness/agents.json
{
  "_meta": {
    "title": "Sapphire agent registry — the contracts the harness enforces",
    "purpose": "One entry per callable agent. 'spec' points to the architecture/*.md (reasoning); the rest is the machine envelope the harness checks. Mirrors qmodels/registry.json.",
    "honesty": "provenance + guardrails are enforced mechanically, not by trust."
  },
  "schemas": {
    "verdict": {
      "type": "object",
      "additionalProperties": false,
      "required": ["persona", "stance", "conviction", "rationale", "fact_claims"],
      "properties": {
        "persona": {"type": "string"},
        "stance": {"type": "string", "enum": ["pass", "conditional", "hold", "no_go"]},
        "conviction": {"type": "integer"},
        "rationale": {"type": "string"},
        "top_risk": {"type": "string"},
        "ask": {"type": "string"},
        "fact_claims": {"type": "array", "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["claim", "cite"],
          "properties": {"claim": {"type": "string"}, "cite": {"type": "string"}}
        }},
        "fact_requests": {"type": "array", "items": {"type": "string"}},
        "provenance": {"type": "string"}
      }
    },
    "findings": {
      "type": "object",
      "additionalProperties": false,
      "required": ["candidate", "facts"],
      "properties": {
        "candidate": {"type": "string"},
        "facts": {"type": "array", "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["value", "source", "tier"],
          "properties": {
            "value": {"type": "string"},
            "source": {"type": "string"},
            "tier": {"type": "string", "enum": ["T1", "T2", "T3", "T4"]},
            "flag": {"type": "string", "enum": ["VETO", "DIVERGENCE", "KNOWN_UNKNOWN"]}
          }
        }},
        "provenance": {"type": "string"}
      }
    }
  },
  "agents": [
    {
      "id": "company-partner",
      "role": "Bucket2 persona — verdict on the dossier through a company mandate",
      "spec": "architecture/bucket2/company-partner-template.md",
      "kind": "claude-subagent",
      "param": "persona_file",
      "output_schema": {"$ref": "#/schemas/verdict"},
      "tools_allowed": [],
      "guardrails": ["must_cite_dossier", "veto_is_gate", "stamp_provenance"],
      "provenance_label": "persona-judgment",
      "timeout_s": 120,
      "retry": {"max_repair": 2, "on_hard_fail": "abstain"}
    },
    {
      "id": "fda-institutional-memory",
      "role": "Bucket1 semantic veto-class — FDA precedent + dispositive veto",
      "spec": "architecture/bucket1/semantic/fda-institutional-memory.md",
      "kind": "claude-subagent",
      "output_schema": {"$ref": "#/schemas/findings"},
      "tools_allowed": ["WebSearch", "WebFetch"],
      "guardrails": ["data_boundary", "facts_only_cited", "veto_is_gate", "stamp_provenance"],
      "provenance_label": "fda-primary",
      "veto_class": true,
      "timeout_s": 180,
      "retry": {"max_repair": 2, "on_hard_fail": "abstain"}
    },
    {
      "id": "emet-runner",
      "role": "EMET (BenchSci) driver via Playwright — the single door to the BEKG",
      "spec": "architecture/bucket1/scientific/emet-analyst.md",
      "kind": "emet-playwright",
      "output_schema": {"$ref": "#/schemas/findings"},
      "tools_allowed": ["mcp__playwright"],
      "guardrails": ["data_boundary", "public_identifiers_only", "facts_only_cited", "emet_tab_discipline", "stamp_provenance"],
      "provenance_label": "emet-live",
      "timeout_s": 300,
      "retry": {"max_repair": 1, "on_hard_fail": "escalate"}
    },
    {
      "id": "q-models-runner",
      "role": "Bucket1 — runs a Q-Models tool on a named pair (delegates to QModelsClient)",
      "spec": "architecture/bucket1/scientific/q-models-runner.md",
      "kind": "qmodels-delegate",
      "tools_allowed": ["qmodels"],
      "guardrails": ["data_boundary", "public_identifiers_only", "stamp_provenance"],
      "provenance_label": "qmodels",
      "timeout_s": 60,
      "retry": {"max_repair": 0, "on_hard_fail": "abstain"}
    }
  ]
}
```

Append to `sapphire-orchestrator/harness/contracts.py`:

```python
from pathlib import Path

_REG_PATH = Path(__file__).resolve().parent / "agents.json"


def load_registry(path=None) -> dict:
    p = Path(path) if path else _REG_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _inline_ref(node, registry):
    """Resolve a top-level {'$ref': '#/schemas/X'} to its concrete (self-contained) schema dict."""
    if isinstance(node, dict) and set(node.keys()) == {"$ref"}:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref!r}")
        cur = registry
        for part in ref[2:].split("/"):
            cur = cur[part]
        return cur
    return node


def resolve(agent_id: str, registry=None) -> Contract:
    reg = registry if registry is not None else load_registry()
    entry = next((a for a in reg.get("agents", []) if a["id"] == agent_id), None)
    if entry is None:
        raise KeyError(agent_id)
    retry = entry.get("retry", {})
    return Contract(
        id=entry["id"],
        role=entry.get("role", ""),
        kind=entry["kind"],
        spec=entry.get("spec"),
        input_schema=_inline_ref(entry.get("input_schema"), reg),
        output_schema=_inline_ref(entry.get("output_schema"), reg),
        tools_allowed=list(entry.get("tools_allowed", [])),
        guardrails=list(entry.get("guardrails", [])),
        provenance_label=entry.get("provenance_label", "synthesis"),
        timeout_s=entry.get("timeout_s", 120),
        max_repair=retry.get("max_repair", 2),
        on_hard_fail=retry.get("on_hard_fail", "abstain"),
        veto_class=entry.get("veto_class", False),
        param=entry.get("param"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_registry -v`
Expected: PASS (6 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/agents.json sapphire-orchestrator/harness/contracts.py sapphire-orchestrator/harness/tests/test_registry.py
git commit -m "D Task 2: agent registry + resolve() (contracts from agents.json)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Error taxonomy + envelopes (`harness/errors.py`)

**Files:**
- Create: `sapphire-orchestrator/harness/errors.py`
- Test: `sapphire-orchestrator/harness/tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HARNESS_ERRORS: frozenset[str]`; `HarnessEscalation(Exception)` (attrs `.code`, `.detail`); `abstain_envelope(code, would_need) -> dict`; `escalate(code, detail="") -> HarnessEscalation`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_errors.py
import unittest
from harness.errors import HARNESS_ERRORS, HarnessEscalation, abstain_envelope, escalate

class TestErrors(unittest.TestCase):
    def test_codes_present(self):
        for c in ["malformed-output", "guardrail-violation", "timeout",
                  "tool-failure", "login-required", "budget", "unknown-agent"]:
            self.assertIn(c, HARNESS_ERRORS)

    def test_abstain_envelope_shape(self):
        env = abstain_envelope("malformed-output", "a valid dossier row")
        self.assertTrue(env["abstained"])
        self.assertEqual(env["reason"], "malformed-output")
        self.assertEqual(env["would_need"], "a valid dossier row")

    def test_escalate_builds_exception(self):
        ex = escalate("login-required", "BenchSci login screen")
        self.assertIsInstance(ex, HarnessEscalation)
        self.assertEqual(ex.code, "login-required")
        self.assertIn("BenchSci", ex.detail)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_errors -v`
Expected: FAIL — `harness.errors` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/errors.py
"""Harness error taxonomy + fail-safe envelopes (spec §A.7). A failure becomes
an honest abstain/escalate the orchestrator already slots — never a fabricated fact."""
from __future__ import annotations

HARNESS_ERRORS = frozenset({
    "malformed-output", "guardrail-violation", "timeout",
    "tool-failure", "login-required", "budget", "unknown-agent",
})


class HarnessEscalation(Exception):
    """Raised/returned when a run must pause for a human (e.g. EMET login). Never swallowed."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def abstain_envelope(code: str, would_need: str) -> dict:
    return {"abstained": True, "reason": code, "would_need": would_need}


def escalate(code: str, detail: str = "") -> HarnessEscalation:
    return HarnessEscalation(code, detail)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_errors -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/errors.py sapphire-orchestrator/harness/tests/test_errors.py
git commit -m "D Task 3: harness error taxonomy + abstain/escalate envelopes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Append-only trace (`harness/trace.py`)

**Files:**
- Create: `sapphire-orchestrator/harness/trace.py`
- Test: `sapphire-orchestrator/harness/tests/test_trace.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `open_engagement(engagement_id, plan) -> None`; `record(engagement_id, event: dict) -> None`; `close_engagement(engagement_id, synthesis) -> None`; `trace_path(engagement_id) -> Path`. Writes one JSON object per line to `<dir>/<engagement_id>/trace.jsonl`, `<dir>` = `SAPPHIRE_ENGAGEMENTS_DIR` env or `RohanOnly/engagements`. Every line carries an ISO-8601 `ts`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_trace.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from harness import trace

class TestTrace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def _lines(self, eid):
        return [json.loads(l) for l in trace.trace_path(eid).read_text().splitlines()]

    def test_open_record_close_appends_in_order(self):
        eid = "eng_test1"
        trace.open_engagement(eid, {"query": "q"})
        trace.record(eid, {"agent_id": "a", "status": "ok"})
        trace.close_engagement(eid, {"recommendation": "advance"})
        rows = self._lines(eid)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["type"], "engagement_open")
        self.assertEqual(rows[1]["agent_id"], "a")
        self.assertEqual(rows[2]["type"], "engagement_close")

    def test_every_line_has_ts(self):
        eid = "eng_test2"
        trace.record(eid, {"agent_id": "a"})
        trace.record(eid, {"agent_id": "b"})
        for row in self._lines(eid):
            self.assertIn("ts", row)

    def test_append_only_never_truncates(self):
        eid = "eng_test3"
        trace.record(eid, {"n": 1})
        trace.record(eid, {"n": 2})
        self.assertEqual([r["n"] for r in self._lines(eid)], [1, 2])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_trace -v`
Expected: FAIL — `harness.trace` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/trace.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_trace -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/trace.py sapphire-orchestrator/harness/tests/test_trace.py
git commit -m "D Task 4: append-only per-engagement trace writer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Input guardrails (`harness/guardrails.py` — data boundary)

**Files:**
- Create: `sapphire-orchestrator/harness/guardrails.py`
- Test: `sapphire-orchestrator/harness/tests/test_guardrails_input.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Violation` dataclass (`guardrail, detail, path`); `data_boundary(inputs) -> list[Violation]`; `public_identifiers_only(inputs) -> list[Violation]`. Both BLOCK (return violations) when a serialized input carries an internal Quiver key or pattern; empty list = clean.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_guardrails_input.py
import unittest
from harness.guardrails import Violation, data_boundary, public_identifiers_only

class TestInputGuards(unittest.TestCase):
    def test_clean_public_inputs_pass(self):
        clean = {"gene": "SCN11A", "smiles": "CC(=O)O", "disease": "neuropathic pain"}
        self.assertEqual(data_boundary(clean), [])
        self.assertEqual(public_identifiers_only(clean), [])

    def test_internal_score_key_blocked(self):
        v = data_boundary({"gene": "SCN11A", "s_internal": 0.89})
        self.assertTrue(v)
        self.assertEqual(v[0].guardrail, "data_boundary")

    def test_internal_candidate_id_pattern_blocked(self):
        v = data_boundary({"note": "candidate QS00123 ranked first"})
        self.assertTrue(v)

    def test_nested_internal_key_blocked(self):
        v = data_boundary({"payload": {"deep": {"latent_vector": [0.1, 0.2]}}})
        self.assertTrue(v)

    def test_public_identifiers_only_relabels(self):
        v = public_identifiers_only({"s_internal": 1})
        self.assertEqual(v[0].guardrail, "public_identifiers_only")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_guardrails_input -v`
Expected: FAIL — `harness.guardrails` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/guardrails.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_guardrails_input -v`
Expected: PASS (5 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/guardrails.py sapphire-orchestrator/harness/tests/test_guardrails_input.py
git commit -m "D Task 5: input guardrails (data boundary, public-identifiers-only)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Output guardrails (`harness/guardrails.py` — facts, veto, citations, stamp)

**Files:**
- Modify: `sapphire-orchestrator/harness/guardrails.py` (append output guards)
- Test: `sapphire-orchestrator/harness/tests/test_guardrails_output.py`

**Interfaces:**
- Consumes: `Violation` (Task 5), `contracts.provenance.is_valid_provenance`.
- Produces (each `(contract, output, ctx) -> list[Violation]` unless noted):
  - `facts_only_cited(contract, output, ctx)` — every row in `output["facts"]` needs non-empty `source` + a `tier`; a row with `flag == "VETO"` must have `tier == "T1"` (else a violation, folding in `tier_T1_for_veto`).
  - `must_cite_dossier(contract, output, ctx)` — every item in `output["fact_claims"]` must have a `cite` present in `ctx["dossier_fields"]` (a set/list of valid field ids); unanchored claims violate.
  - `veto_is_gate(contract, output, ctx)` — if `output` marks a veto (`stance == "no_go"` or any fact `flag == "VETO"`) it must not also set `output.get("action") == "drop"` (a veto is a surfaced gate, never a silent kill).
  - `emet_tab_discipline(contract, output, ctx)` — an emet output must carry a non-empty `provenance`/evidence trail; minimally a violation if `output` lacks `facts`.
  - `stamp_provenance(contract, output) -> dict` — returns a copy of `output` with `provenance` set to `contract.provenance_label` (and stamped onto each `facts` row if present). Raises nothing; the only transform guard.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_guardrails_output.py
import unittest
from harness.contracts import Contract
from harness.guardrails import (facts_only_cited, must_cite_dossier, veto_is_gate,
                                emet_tab_discipline, stamp_provenance)

C = Contract(id="x", role="", kind="claude-subagent", provenance_label="emet-live")

class TestOutputGuards(unittest.TestCase):
    def test_facts_uncited_row_violates(self):
        out = {"facts": [{"value": "GoF", "source": "", "tier": "T2"}]}
        self.assertTrue(facts_only_cited(C, out, {}))

    def test_facts_cited_row_passes(self):
        out = {"facts": [{"value": "GoF", "source": "PMID:1", "tier": "T2"}]}
        self.assertEqual(facts_only_cited(C, out, {}), [])

    def test_veto_must_be_tier_t1(self):
        out = {"facts": [{"value": "prior CRL", "source": "PMID:9", "tier": "T2", "flag": "VETO"}]}
        self.assertTrue(facts_only_cited(C, out, {}))   # VETO at T2 → violation

    def test_must_cite_dossier_unanchored_violates(self):
        out = {"fact_claims": [{"claim": "Nav1.5 risk", "cite": "Z9"}]}
        self.assertTrue(must_cite_dossier(C, out, {"dossier_fields": ["B1", "C3"]}))

    def test_must_cite_dossier_anchored_passes(self):
        out = {"fact_claims": [{"claim": "Nav1.5 risk", "cite": "C3"}]}
        self.assertEqual(must_cite_dossier(C, out, {"dossier_fields": ["B1", "C3"]}), [])

    def test_veto_is_gate_blocks_silent_drop(self):
        out = {"stance": "no_go", "action": "drop"}
        self.assertTrue(veto_is_gate(C, out, {}))

    def test_veto_is_gate_surfaced_ok(self):
        out = {"stance": "no_go", "action": "surface"}
        self.assertEqual(veto_is_gate(C, out, {}), [])

    def test_emet_tab_discipline_requires_facts(self):
        self.assertTrue(emet_tab_discipline(C, {"candidate": "SCN11A"}, {}))
        self.assertEqual(emet_tab_discipline(C, {"candidate": "SCN11A", "facts": []}, {}), [])

    def test_stamp_provenance_sets_label(self):
        out = stamp_provenance(C, {"facts": [{"value": "x", "source": "s", "tier": "T1"}]})
        self.assertEqual(out["provenance"], "emet-live")
        self.assertEqual(out["facts"][0]["provenance"], "emet-live")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_guardrails_output -v`
Expected: FAIL — output guard functions not defined.

- [ ] **Step 3: Write minimal implementation**

Append to `sapphire-orchestrator/harness/guardrails.py`:

```python
import copy


def facts_only_cited(contract, output, ctx) -> list:
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
    valid = set(ctx.get("dossier_fields", []) or [])
    viols = []
    for i, claim in enumerate(output.get("fact_claims", []) or []):
        cite = claim.get("cite")
        if cite not in valid:
            viols.append(Violation("must_cite_dossier", f"claim cites unknown dossier field {cite!r}", f"fact_claims[{i}]"))
    return viols


def veto_is_gate(contract, output, ctx) -> list:
    is_veto = output.get("stance") == "no_go" or any(
        (row.get("flag") == "VETO") for row in (output.get("facts", []) or [])
    )
    if is_veto and output.get("action") == "drop":
        return [Violation("veto_is_gate", "veto must be surfaced as a gate, not a silent drop", "action")]
    return []


def emet_tab_discipline(contract, output, ctx) -> list:
    if "facts" not in output:
        return [Violation("emet_tab_discipline", "emet output carries no evidence trail (no facts)", "facts")]
    return []


def stamp_provenance(contract, output) -> dict:
    out = copy.deepcopy(output)
    out["provenance"] = contract.provenance_label
    for row in out.get("facts", []) or []:
        row["provenance"] = contract.provenance_label
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_guardrails_output -v`
Expected: PASS (9 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/guardrails.py sapphire-orchestrator/harness/tests/test_guardrails_output.py
git commit -m "D Task 6: output guardrails (facts-cited+veto-tier, must-cite-dossier, veto-is-gate, stamp)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Repair-prompt builder (`harness/repair.py`)

**Files:**
- Create: `sapphire-orchestrator/harness/repair.py`
- Test: `sapphire-orchestrator/harness/tests/test_repair.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `repair_prompt(prior_output, errors: list[str]) -> str` — a surgical re-prompt embedding the prior output + the exact failing paths and asking for the corrected object only.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_repair.py
import unittest
from harness.repair import repair_prompt

class TestRepair(unittest.TestCase):
    def test_includes_errors_and_prior(self):
        p = repair_prompt({"facts": []}, ["$.candidate: required field missing"])
        self.assertIn("$.candidate: required field missing", p)
        self.assertIn("facts", p)
        self.assertIn("corrected", p.lower())

    def test_handles_no_prior(self):
        p = repair_prompt(None, ["tool-failure: web fetch 500"])
        self.assertIn("tool-failure: web fetch 500", p)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_repair -v`
Expected: FAIL — `harness.repair` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/repair.py
"""Bounded-repair re-prompt builder (spec §A.4). Surgical: prior output + exact
failing paths + 'return the corrected object only'."""
from __future__ import annotations

import json


def repair_prompt(prior_output, errors) -> str:
    prior = json.dumps(prior_output, indent=2) if prior_output is not None else "(no prior output)"
    problems = "\n".join(f"  - {e}" for e in (errors or []))
    return (
        "Your previous output did not satisfy its contract. Fix exactly these problems:\n"
        f"{problems}\n\n"
        "Your previous output was:\n"
        f"{prior}\n\n"
        "Return ONLY the corrected structured object (the JSON schema is enforced). "
        "Do not add commentary."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_repair -v`
Expected: PASS (2 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/repair.py sapphire-orchestrator/harness/tests/test_repair.py
git commit -m "D Task 7: bounded-repair re-prompt builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Dispatch backends (`harness/dispatch.py`)

**Files:**
- Create: `sapphire-orchestrator/harness/dispatch.py`
- Test: `sapphire-orchestrator/harness/tests/test_dispatch.py`

**Interfaces:**
- Consumes: `Contract` (Task 1), `HarnessEscalation` (Task 3).
- Produces:
  - `build_prompt(contract, inputs) -> str` (spec body + inputs block).
  - `dispatch_claude(contract, inputs, runner=None) -> dict` — builds `[CLAUDE_BIN, "-p", prompt, "--output-format","json","--json-schema", <schema>, "--allowedTools", ",".join(tools)]`, calls `runner(cmd)` (default `subprocess.run(..., cwd=ROOT, timeout=contract.timeout_s)`), parses `json.loads(stdout)` then `env.get("structured_output") or json.loads(env["result"])`. Mirrors `serve.py:_run_live`.
  - `dispatch_qmodels(contract, inputs, client=None) -> dict` — `client.call(inputs.get("tool_id", contract.id), inputs.get("inputs", inputs))`.
  - `dispatch_python(contract, inputs, fn) -> dict` — `fn(inputs)`.
  - `dispatch_emet(contract, inputs, handler) -> dict` — `handler(contract, inputs)` (handler registered by workstream A; default absent → `RuntimeError`).
  - `dispatch(contract, inputs, ctx=None) -> dict` — selects a backend by `contract.kind`, pulling injectables from `ctx` (`runner`, `qmodels_client`, `python_fns`, `emet_handler`).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_dispatch.py
import json
import unittest
from types import SimpleNamespace
from harness.contracts import Contract
from harness import dispatch as D

def fake_runner(stdout, returncode=0, stderr=""):
    return lambda cmd: SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)

class TestDispatch(unittest.TestCase):
    def test_build_prompt_includes_inputs(self):
        c = Contract(id="x", role="", kind="claude-subagent", spec=None)
        p = D.build_prompt(c, {"gene": "SCN11A"})
        self.assertIn("SCN11A", p)
        self.assertIn("structured object", p.lower())

    def test_dispatch_claude_parses_structured_output(self):
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"facts": [], "ok": True}})
        out = D.dispatch_claude(c, {"q": 1}, runner=fake_runner(env))
        self.assertEqual(out, {"facts": [], "ok": True})

    def test_dispatch_claude_falls_back_to_result(self):
        c = Contract(id="x", role="", kind="claude-subagent")
        env = json.dumps({"result": json.dumps({"v": 2})})
        out = D.dispatch_claude(c, {}, runner=fake_runner(env))
        self.assertEqual(out, {"v": 2})

    def test_dispatch_claude_nonzero_raises(self):
        c = Contract(id="x", role="", kind="claude-subagent")
        with self.assertRaises(RuntimeError):
            D.dispatch_claude(c, {}, runner=fake_runner("", returncode=1, stderr="boom"))

    def test_dispatch_qmodels_delegates(self):
        c = Contract(id="q-models-runner", role="", kind="qmodels-delegate")
        client = SimpleNamespace(call=lambda tool, inp: {"tool_id": tool, "out": "p=0.5"})
        out = D.dispatch_qmodels(c, {"tool_id": "bbbp", "inputs": {"smiles": "CCO"}}, client=client)
        self.assertEqual(out["tool_id"], "bbbp")

    def test_dispatch_python_calls_fn(self):
        c = Contract(id="step", role="", kind="python")
        out = D.dispatch_python(c, {"n": 2}, fn=lambda i: {"doubled": i["n"] * 2})
        self.assertEqual(out["doubled"], 4)

    def test_dispatch_routes_by_kind(self):
        c = Contract(id="step", role="", kind="python")
        out = D.dispatch(c, {"n": 3}, ctx={"python_fns": {"step": lambda i: {"v": i["n"]}}})
        self.assertEqual(out["v"], 3)

    def test_dispatch_emet_without_handler_errors(self):
        c = Contract(id="emet-runner", role="", kind="emet-playwright")
        with self.assertRaises(RuntimeError):
            D.dispatch(c, {"candidate": "SCN11A"}, ctx={})

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_dispatch -v`
Expected: FAIL — `harness.dispatch` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/dispatch.py
"""Per-kind dispatch backends (spec §A.3). All backends are injectable so the
harness is tested offline (no live claude, no AWS). dispatch_claude mirrors
serve.py:_run_live's `claude -p --json-schema` invocation + parsing."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .errors import HarnessEscalation  # noqa: F401  (re-exported for handlers)

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def _read_spec(spec) -> str:
    if not spec:
        return ""
    p = ROOT / spec
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(contract, inputs) -> str:
    return (
        f"{_read_spec(contract.spec)}\n\n"
        f"## INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Return ONLY the structured object (the JSON schema is enforced). Do not add commentary."
    )


def dispatch_claude(contract, inputs, runner=None) -> dict:
    cmd = [
        CLAUDE_BIN, "-p", build_prompt(contract, inputs),
        "--output-format", "json",
        "--json-schema", json.dumps(contract.output_schema or {}),
        "--allowedTools", ",".join(contract.tools_allowed),
    ]
    if runner is None:
        def runner(cmd):
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=contract.timeout_s, cwd=str(ROOT))
    proc = runner(cmd)
    if getattr(proc, "returncode", 0) != 0:
        raise RuntimeError(f"claude exited {getattr(proc, 'returncode', '?')}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body


def dispatch_qmodels(contract, inputs, client=None) -> dict:
    if client is None:
        from qmodels.client import QModelsClient
        client = QModelsClient()
    tool_id = inputs.get("tool_id", contract.id)
    payload = inputs.get("inputs", inputs)
    return client.call(tool_id, payload)


def dispatch_python(contract, inputs, fn) -> dict:
    if fn is None:
        raise RuntimeError(f"no python fn registered for {contract.id}")
    return fn(inputs)


def dispatch_emet(contract, inputs, handler) -> dict:
    if handler is None:
        raise RuntimeError("emet handler not registered (workstream A wires emet-runner)")
    return handler(contract, inputs)


def dispatch(contract, inputs, ctx=None) -> dict:
    ctx = ctx or {}
    kind = contract.kind
    if kind == "claude-subagent":
        return dispatch_claude(contract, inputs, runner=ctx.get("runner"))
    if kind == "qmodels-delegate":
        return dispatch_qmodels(contract, inputs, client=ctx.get("qmodels_client"))
    if kind == "python":
        fn = (ctx.get("python_fns") or {}).get(contract.id) or ctx.get("python_fn")
        return dispatch_python(contract, inputs, fn)
    if kind == "emet-playwright":
        return dispatch_emet(contract, inputs, ctx.get("emet_handler"))
    raise RuntimeError(f"unknown dispatch kind {kind!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_dispatch -v`
Expected: PASS (8 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/harness/dispatch.py sapphire-orchestrator/harness/tests/test_dispatch.py
git commit -m "D Task 8: per-kind dispatch backends (claude/qmodels/python/emet), injectable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Runtime capstone (`harness/runtime.py` + `__init__` exports)

**Files:**
- Create: `sapphire-orchestrator/harness/runtime.py`
- Modify: `sapphire-orchestrator/harness/__init__.py` (export `run`, `AgentResult`, `load_registry`, `resolve`)
- Test: `sapphire-orchestrator/harness/tests/test_runtime.py`

**Interfaces:**
- Consumes: everything above + `contracts.jsonschema_min.validate`.
- Produces: `run(agent_id, inputs, *, engagement_id, ctx=None, registry=None, dispatch_fn=None) -> AgentResult`. Behavior: resolve contract (unknown → `AgentResult(ok=False, status="escalated", error="unknown-agent")`); idempotency cache on `inputs_hash` in `ctx["_cache"]`; run input guards (a violation → blocked pre-dispatch, `ok=False`, `error="guardrail-violation"`, backend NOT called); dispatch (default `dispatch.dispatch`, override via `dispatch_fn`); validate output against schema + output guards; on errors repair up to `max_repair`; on exhaustion → fail-safe per `on_hard_fail` (`abstain` envelope or escalated); on `HarnessEscalation` from dispatch → `ok=False, status="escalated"`; on success stamp provenance, set `meta` (`inputs_hash, latency_ms, repairs, guardrails_run`), append a trace `record`. Never fabricates.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/harness/tests/test_runtime.py
import os
import tempfile
import unittest
from harness.runtime import run
from harness.errors import HarnessEscalation

OUT_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["candidate", "facts"],
              "properties": {"candidate": {"type": "string"},
                             "facts": {"type": "array", "items": {"type": "object"}},
                             "provenance": {"type": "string"}}}

def reg(guardrails=None, max_repair=1, on_hard_fail="abstain"):
    return {"schemas": {}, "agents": [{
        "id": "t", "role": "", "kind": "python", "output_schema": OUT_SCHEMA,
        "guardrails": guardrails or ["stamp_provenance"], "provenance_label": "synthesis",
        "retry": {"max_repair": max_repair, "on_hard_fail": on_hard_fail}}]}

class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def test_happy_path_stamps_and_traces(self):
        ctx = {"python_fns": {"t": lambda i: {"candidate": "SCN11A", "facts": []}}}
        r = run("t", {"gene": "SCN11A"}, engagement_id="eng1", ctx=ctx, registry=reg())
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.output["provenance"], "synthesis")
        self.assertEqual(r.meta["repairs"], 0)
        # trace written
        from harness import trace
        self.assertTrue(trace.trace_path("eng1").exists())

    def test_schema_violation_repairs_then_abstains(self):
        calls = {"n": 0}
        def bad(i):
            calls["n"] += 1
            return {"candidate": "SCN11A"}   # missing 'facts' → always invalid
        ctx = {"python_fns": {"t": bad}}
        r = run("t", {"g": 1}, engagement_id="eng2", ctx=ctx, registry=reg(max_repair=1))
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "abstained")
        self.assertTrue(r.output["abstained"])
        self.assertEqual(r.error, "malformed-output")
        self.assertEqual(calls["n"], 2)      # initial + 1 repair

    def test_input_guard_blocks_pre_dispatch(self):
        called = {"n": 0}
        def fn(i):
            called["n"] += 1
            return {"candidate": "x", "facts": []}
        ctx = {"python_fns": {"t": fn}}
        r = run("t", {"s_internal": 0.9}, engagement_id="eng3", ctx=ctx,
                registry=reg(guardrails=["data_boundary", "stamp_provenance"]))
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "guardrail-violation")
        self.assertEqual(called["n"], 0)     # backend never called — nothing leaked

    def test_idempotency_cache_dispatches_once(self):
        calls = {"n": 0}
        def fn(i):
            calls["n"] += 1
            return {"candidate": "x", "facts": []}
        ctx = {"python_fns": {"t": fn}}
        run("t", {"g": 1}, engagement_id="eng4", ctx=ctx, registry=reg())
        run("t", {"g": 1}, engagement_id="eng4", ctx=ctx, registry=reg())
        self.assertEqual(calls["n"], 1)      # second served from cache

    def test_unknown_agent(self):
        r = run("nope", {}, engagement_id="eng5", registry={"schemas": {}, "agents": []})
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "unknown-agent")

    def test_escalation_from_dispatch(self):
        def boom(contract, inputs, ctx):
            raise HarnessEscalation("login-required", "BenchSci login")
        r = run("t", {"g": 1}, engagement_id="eng6", ctx={}, registry=reg(), dispatch_fn=boom)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "escalated")
        self.assertEqual(r.error, "login-required")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_runtime -v`
Expected: FAIL — `harness.runtime` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/harness/runtime.py
"""The single entry point: resolve -> guard(inputs) -> dispatch -> validate+guard(output)
-> repair -> stamp -> trace -> AgentResult. Fail-safe; never fabricates (spec §A.3/§A.4)."""
from __future__ import annotations

import time

from contracts.jsonschema_min import validate

from . import dispatch as _dispatch
from . import guardrails as G
from . import trace as T
from .contracts import AgentResult, inputs_hash, resolve
from .errors import HarnessEscalation, abstain_envelope
from .repair import repair_prompt

_INPUT_GUARDS = {"data_boundary": G.data_boundary, "public_identifiers_only": G.public_identifiers_only}
_OUTPUT_GUARDS = {
    "facts_only_cited": G.facts_only_cited,
    "must_cite_dossier": G.must_cite_dossier,
    "veto_is_gate": G.veto_is_gate,
    "emet_tab_discipline": G.emet_tab_discipline,
}


def _validate_output(contract, out, ctx) -> list:
    errs = []
    if contract.output_schema:
        errs += validate(out, contract.output_schema, contract.output_schema)
    for gname in contract.guardrails:
        fn = _OUTPUT_GUARDS.get(gname)
        if fn:
            errs += [f"{v.guardrail}: {v.detail}" for v in fn(contract, out, ctx)]
    return errs


def _finish(contract, result, engagement_id, t0, repairs, guardrails_run, ihash, cache):
    result.meta = {"inputs_hash": ihash, "latency_ms": int((time.time() - t0) * 1000),
                   "repairs": repairs, "guardrails_run": guardrails_run}
    T.record(engagement_id, {"agent_id": contract.id, "kind": contract.kind,
                             "inputs_hash": ihash, "status": result.status,
                             "provenance": result.provenance, "error": result.error,
                             "repairs": repairs, "guardrails_run": guardrails_run,
                             "output": result.output})
    cache[ihash] = result
    return result


def run(agent_id, inputs, *, engagement_id, ctx=None, registry=None, dispatch_fn=None) -> AgentResult:
    ctx = ctx if ctx is not None else {}
    t0 = time.time()
    try:
        contract = resolve(agent_id, registry)
    except KeyError:
        return AgentResult(agent_id, False, abstain_envelope("unknown-agent", "a registered agent id"),
                           "synthesis", "escalated", "unknown-agent",
                           {"inputs_hash": None, "latency_ms": 0, "repairs": 0, "guardrails_run": []})

    ihash = inputs_hash(contract.id, inputs)
    cache = ctx.setdefault("_cache", {})
    if ihash in cache:
        return cache[ihash]

    guardrails_run = []

    # 1. input guards — BLOCK pre-dispatch
    for gname in contract.guardrails:
        gfn = _INPUT_GUARDS.get(gname)
        if gfn:
            guardrails_run.append(gname)
            if gfn(inputs):
                res = AgentResult(contract.id, False,
                                  abstain_envelope("guardrail-violation", f"{gname} clean inputs"),
                                  contract.provenance_label, "abstained", "guardrail-violation")
                return _finish(contract, res, engagement_id, t0, 0, guardrails_run, ihash, cache)

    disp = dispatch_fn or _dispatch.dispatch

    # 2. dispatch + validate + repair loop
    out, errs = None, []
    for attempt in range(contract.max_repair + 1):
        call_inputs = inputs if attempt == 0 else {**inputs, "_repair": repair_prompt(out, errs)}
        try:
            out = disp(contract, call_inputs, ctx)
        except HarnessEscalation as ex:
            res = AgentResult(contract.id, False, abstain_envelope(ex.code, ex.detail),
                              contract.provenance_label, "escalated", ex.code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)
        except Exception as ex:
            code = "timeout" if ex.__class__.__name__ == "TimeoutExpired" else "tool-failure"
            errs = [f"{code}: {ex}"]
            if attempt < contract.max_repair:
                out = None
                continue
            status = "escalated" if contract.on_hard_fail == "escalate" else "abstained"
            res = AgentResult(contract.id, False, abstain_envelope(code, "a working backend"),
                              contract.provenance_label, status, code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)

        errs = _validate_output(contract, out, ctx)
        if not errs:
            break
        if attempt >= contract.max_repair:
            code = "guardrail-violation" if any(":" in e and e.split(":")[0] in _OUTPUT_GUARDS for e in errs) else "malformed-output"
            status = "escalated" if contract.on_hard_fail == "escalate" else "abstained"
            res = AgentResult(contract.id, False, abstain_envelope(code, "; ".join(errs[:3])),
                              contract.provenance_label, status, code)
            return _finish(contract, res, engagement_id, t0, attempt, guardrails_run, ihash, cache)

    repairs = attempt

    # 3. success — stamp provenance, record guardrails that ran
    for gname in contract.guardrails:
        if gname in _OUTPUT_GUARDS and gname not in guardrails_run:
            guardrails_run.append(gname)
    if "stamp_provenance" in contract.guardrails:
        out = G.stamp_provenance(contract, out)
        guardrails_run.append("stamp_provenance")
    provenance = out.get("provenance", contract.provenance_label)
    res = AgentResult(contract.id, True, out, provenance, "ok", None)
    return _finish(contract, res, engagement_id, t0, repairs, guardrails_run, ihash, cache)
```

Replace `sapphire-orchestrator/harness/__init__.py` contents:

```python
# sapphire-orchestrator/harness/__init__.py
"""The Sapphire agent harness: one runtime every agent runs through."""
from .contracts import AgentResult, Contract, load_registry, resolve
from .runtime import run

__all__ = ["run", "AgentResult", "Contract", "load_registry", "resolve"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest harness.tests.test_runtime -v`
Expected: PASS (6 tests OK).

- [ ] **Step 5: Run the whole harness suite + commit**

Run: `cd sapphire-orchestrator && python -m unittest discover -s harness/tests -v`
Expected: PASS (all harness tests green across the 9 test modules).

```bash
git add sapphire-orchestrator/harness/runtime.py sapphire-orchestrator/harness/__init__.py sapphire-orchestrator/harness/tests/test_runtime.py
git commit -m "D Task 9: runtime capstone — run() with guards, repair, fail-safe, trace

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Appendix A):** A.1 boundaries → the package is dispatch-only, orchestrator/agents untouched (integration deferred, see note). A.2 registry/contract → Tasks 1–2 (`agents.json`, `Contract`, `resolve`). A.3 dispatch/`run`/`AgentResult` → Tasks 1, 8, 9. A.4 schema validate + bounded repair + idempotency + fail-safe → Task 9 (+ P0 validator, Task 7 repair). A.5 guardrails → Tasks 5–6 (data_boundary, public_identifiers_only, facts_only_cited incl. tier_T1_for_veto, must_cite_dossier, veto_is_gate, emet_tab_discipline, stamp_provenance). A.6 trace → Task 4. A.7 error taxonomy → Task 3 + mapped in Task 9. A.9 file layout → all files created (`jsonschema_min` lives in `contracts/` per P0, imported here — intentional). A.10 tests → the seven scenarios map to Task 9's tests (happy, schema-violation+repair→abstain, input-guard block, idempotency, unknown-agent, escalation) + Task 6 persona must-cite.

**Deferred (out of scope for D, by design — keeps the running engine stable):** A.8 integration (rewiring `orchestrator.py`/`serve.py` to call `harness.run`, lifting `RUN_SCHEMA`/`FOLLOWUP_SCHEMA` into `agents.json`). This is delicate surgery on working code; it is scheduled as an explicit integration step after workstreams A and C land (it needs the EMET handler from A and is exercised end-to-end by workstream B). Noted here so it is not silently dropped.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows complete tests with concrete assertions.

**Type consistency:** `Contract`/`AgentResult` fields (Task 1) are consumed unchanged in Tasks 2/8/9. `resolve` signature (Task 2) used in Task 9. `Violation` + guard signatures `(contract, output, ctx) -> list` (Tasks 5–6) match `_OUTPUT_GUARDS`/`_INPUT_GUARDS` usage in Task 9. `dispatch(contract, inputs, ctx)` (Task 8) matches the `dispatch_fn` contract and the `boom(contract, inputs, ctx)` test in Task 9. `stamp_provenance(contract, output)` (Task 6, two-arg transform) is called as such in Task 9. `repair_prompt(prior, errors)` (Task 7) matches Task 9's call. `trace.record`/`trace_path` (Task 4) match Task 9 + tests.

**Note for downstream (A/C):** workstream A registers an `emet_handler` into `ctx` (or a module-level registry) so `dispatch_emet` resolves; workstream C reads `RohanOnly/engagements/<id>/trace.jsonl` (Task 4 format) and consumes `AgentResult`.
