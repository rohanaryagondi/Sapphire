# Sapphire Phase 5 — C: Self-Improvement Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Sapphire durable scientific memory + an active-learning loop: it writes cited conclusions/facts/proposed-experiments to memory, recalls them on new engagements, ingests real outcomes to find and fix the moat's blind spots, drafts new behavior into a human-reviewed queue, and tracks whether it is getting better — all under a tiered governance switch.

**Architecture:** Two stdlib-only packages. `sapphire-orchestrator/memory/` is the append-only record store (write/recall/record_outcome) guarded so internal Quiver data can never enter; records follow P0's `MEMORY_RECORD_SCHEMA`. `sapphire-orchestrator/selfimprove/` is the loop: `governance.py` (the tiered auto-apply switch), `reflect.py` (post-engagement: read the harness trace → write memory), `authoring.py` (Tier-2: draft new skills/specs/scenarios into `proposed/`), `metrics.py` (is-it-getting-better report). Data lives under `RohanOnly/memory/` and `sapphire-orchestrator/proposed/` (both env-overridable for tests); the harness trace it reads lives at `RohanOnly/engagements/<id>/trace.jsonl`.

**Tech Stack:** Python 3, **stdlib only** (`json`, `os`, `hashlib`, `datetime`, `pathlib`, `unittest`). Imports P0 (`contracts.schemas`, `contracts.jsonschema_min`) and D (`harness.guardrails.data_boundary`, `harness.trace`).

## Global Constraints

- **Stdlib-only Python.** No third-party deps. Branch `Rohan`; commit per task; do NOT push to main.
- **Import-by-CWD:** tests run with CWD = `sapphire-orchestrator/` (so `import memory`, `import selfimprove`, `import contracts`, `import harness` resolve).
- **Append-only memory; never mutate in place.** Corrections append a new record with `supersedes`. — spec §3.2/§6.1.
- **Public identifiers only in memory.** Every `write` runs `harness.guardrails.data_boundary` on the whole record and REFUSES on any violation — internal Quiver scores/ids can never enter memory. — spec §6.1.
- **Records follow P0 `MEMORY_RECORD_SCHEMA`** (types: fact, conclusion, experiment_proposal, experiment_outcome, divergence, persona_verdict, calibration, moat_blindspot). Every `write` validates; an invalid record refuses.
- **Tiered governance (default):** `auto_apply.memory=true`; skills/specs/scenarios/routes=false (drafted to `proposed/` for human approval). Flipping flags = the path to fully-autonomous later. — spec §6.5.
- **Recalled conclusions are priors flagged for re-validation, never settled facts.** — spec §6.2.
- **Env overrides (tests):** `SAPPHIRE_MEMORY_DIR` (memory data dir), `SAPPHIRE_ENGAGEMENTS_DIR` (trace dir, shared with the harness), `SAPPHIRE_PROPOSED_DIR` (authoring queue).

---

### Task 1: Memory store core — write / read / index / boundary (`memory/memory.py`)

**Files:**
- Create: `sapphire-orchestrator/memory/__init__.py`
- Create: `sapphire-orchestrator/memory/memory.py`
- Create: `sapphire-orchestrator/memory/tests/__init__.py`
- Test: `sapphire-orchestrator/memory/tests/test_store.py`

**Interfaces:**
- Consumes: `contracts.schemas` (`MEMORY_RECORD_SCHEMA`, `MEMORY_RECORD_TYPES`), `contracts.jsonschema_min.validate`, `harness.guardrails.data_boundary`.
- Produces: `MemoryRefusal(Exception)`; `write(record: dict) -> dict` (fills defaults + id + ts, runs data_boundary then schema validate, appends to `store.jsonl`, returns the stored record); `read_all() -> list[dict]`; `rebuild_index() -> dict` (entity → [ids], written to `index.json`); `_blank_entities() -> dict`. `__init__.py` re-exports these.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/memory/tests/test_store.py
import os
import tempfile
import unittest
from memory import write, read_all, rebuild_index, MemoryRefusal

def rec(**kw):
    base = {"type": "conclusion", "engagement_id": "eng1",
            "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["neuropathic pain"], "drugs": []},
            "payload": {"recommendation": "advance to de-risking"}}
    base.update(kw)
    return base

class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_write_fills_id_ts_and_roundtrips(self):
        out = write(rec())
        self.assertTrue(out["id"].startswith("mem_"))
        self.assertIn("ts", out)
        allr = read_all()
        self.assertEqual(len(allr), 1)
        self.assertEqual(allr[0]["payload"]["recommendation"], "advance to de-risking")

    def test_append_only(self):
        write(rec(payload={"recommendation": "a"}))
        write(rec(payload={"recommendation": "b"}))
        self.assertEqual([r["payload"]["recommendation"] for r in read_all()], ["a", "b"])

    def test_bad_type_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(type="gossip"))

    def test_internal_data_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(payload={"s_internal": 0.9}))      # data boundary blocks internal scores

    def test_schema_invalid_refused(self):
        with self.assertRaises(MemoryRefusal):
            write(rec(tier="T9"))                          # tier not in T1..T4

    def test_rebuild_index_maps_entities(self):
        write(rec())
        idx = rebuild_index()
        self.assertIn("SCN11A", idx)
        self.assertEqual(len(idx["SCN11A"]), 1)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_store -v`
Expected: FAIL — `memory` package / functions not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/memory/__init__.py
"""Sapphire durable memory — append-only, public-identifiers-only record store."""
from .memory import (MemoryRefusal, write, read_all, recall, record_outcome,
                     rebuild_index, blank_entities)

__all__ = ["MemoryRefusal", "write", "read_all", "recall", "record_outcome",
           "rebuild_index", "blank_entities"]
```

```python
# sapphire-orchestrator/memory/memory.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_store -v`
Expected: PASS (6 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/memory/__init__.py sapphire-orchestrator/memory/memory.py sapphire-orchestrator/memory/tests/__init__.py sapphire-orchestrator/memory/tests/test_store.py
git commit -m "C Task 1: append-only memory store (write/read/index, boundary + schema guarded)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Recall (`memory.recall`)

**Files:**
- Modify: `sapphire-orchestrator/memory/memory.py` (replace the `recall` placeholder)
- Test: `sapphire-orchestrator/memory/tests/test_recall.py`

**Interfaces:**
- Consumes: `read_all` (Task 1).
- Produces: `recall(entities, types=None, k=5) -> list[dict]` — `entities` is a dict (`{"genes":[...], ...}`) or a flat list of identifier strings; returns records sharing ≥1 entity, ranked by entity-overlap count then recency (`ts`), capped at `k`; optional `types` filter.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/memory/tests/test_recall.py
import os
import tempfile
import unittest
from memory import write, recall, blank_entities

def rec(gene, **kw):
    ents = blank_entities(); ents["genes"] = [gene]
    base = {"type": "conclusion", "engagement_id": "e", "entities": ents,
            "payload": {"recommendation": f"about {gene}"}}
    base.update(kw)
    return base

class TestRecall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_recall_by_gene_filters(self):
        write(rec("SCN11A"))
        write(rec("KCNT1"))
        out = recall({"genes": ["SCN11A"]})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["entities"]["genes"], ["SCN11A"])

    def test_recall_accepts_flat_list(self):
        write(rec("SCN11A"))
        self.assertEqual(len(recall(["SCN11A"])), 1)

    def test_recall_ranks_by_overlap(self):
        ents = blank_entities(); ents["genes"] = ["SCN11A", "SCN10A"]
        write({"type": "conclusion", "entities": ents, "payload": {"recommendation": "two-gene"}})
        write(rec("SCN11A"))
        out = recall({"genes": ["SCN11A", "SCN10A"]})
        self.assertEqual(out[0]["payload"]["recommendation"], "two-gene")  # 2 overlaps ranks first

    def test_types_filter(self):
        write(rec("SCN11A", type="conclusion"))
        write(rec("SCN11A", type="fact", payload={"value": "x", "source": "PMID:1"}))
        self.assertTrue(all(r["type"] == "fact" for r in recall({"genes": ["SCN11A"]}, types=["fact"])))

    def test_no_match_empty(self):
        write(rec("SCN11A"))
        self.assertEqual(recall({"genes": ["TRPV1"]}), [])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_recall -v`
Expected: FAIL — `recall` raises `NotImplementedError`.

- [ ] **Step 3: Write minimal implementation**

Replace the `recall` placeholder in `sapphire-orchestrator/memory/memory.py` with:

```python
def recall(entities, types=None, k=5) -> list:
    if isinstance(entities, dict):
        wanted = {v for vals in entities.values() for v in vals}
    else:
        wanted = set(entities)
    scored = []
    for r in read_all():
        if types and r.get("type") not in types:
            continue
        rec_ents = {v for vals in r.get("entities", {}).values() for v in vals}
        overlap = len(wanted & rec_ents)
        if overlap:
            scored.append((overlap, r.get("ts", ""), r))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [r for _, _, r in scored[:k]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_recall -v`
Expected: PASS (5 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/memory/memory.py sapphire-orchestrator/memory/tests/test_recall.py
git commit -m "C Task 2: memory recall (entity-overlap + recency ranking)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Active-learning — outcomes + blind spots (`memory.record_outcome`)

**Files:**
- Modify: `sapphire-orchestrator/memory/memory.py` (replace the `record_outcome` placeholder + add `_entities_of`)
- Test: `sapphire-orchestrator/memory/tests/test_outcome.py`

**Interfaces:**
- Consumes: `write`, `read_all`, `blank_entities`.
- Produces: `record_outcome(proposal_id, outcome, engagement_id="") -> dict` — appends an `experiment_outcome` linked to its proposal (inheriting the proposal's entities); if `outcome["result"] == "refuted"`, ALSO writes a linked `moat_blindspot` (the active-learning signal the Internal Science Lead later reads). `outcome` = `{"result": "confirmed|refuted|partial", "data": str, "source": str}`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/memory/tests/test_outcome.py
import os
import tempfile
import unittest
from memory import write, read_all, record_outcome, blank_entities

def proposal(gene="SCN11A"):
    ents = blank_entities(); ents["genes"] = [gene]
    return write({"type": "experiment_proposal", "engagement_id": "e", "entities": ents,
                  "payload": {"experiment": "resolve Nav1.9 persistent current"}})

class TestOutcome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_confirmed_outcome_links_no_blindspot(self):
        p = proposal()
        o = record_outcome(p["id"], {"result": "confirmed", "data": "assay resolved it", "source": "wetlab"})
        self.assertEqual(o["type"], "experiment_outcome")
        self.assertIn(p["id"], o["links"])
        self.assertEqual(o["entities"]["genes"], ["SCN11A"])    # inherited from proposal
        self.assertEqual([r["type"] for r in read_all()].count("moat_blindspot"), 0)

    def test_refuted_outcome_opens_blindspot(self):
        p = proposal()
        record_outcome(p["id"], {"result": "refuted", "data": "moat missed the persistent current", "source": "wetlab"})
        types = [r["type"] for r in read_all()]
        self.assertIn("moat_blindspot", types)
        bs = next(r for r in read_all() if r["type"] == "moat_blindspot")
        self.assertIn(p["id"], bs["links"])
        self.assertEqual(bs["entities"]["genes"], ["SCN11A"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_outcome -v`
Expected: FAIL — `record_outcome` raises `NotImplementedError`.

- [ ] **Step 3: Write minimal implementation**

Replace the `record_outcome` placeholder in `sapphire-orchestrator/memory/memory.py` with:

```python
def _entities_of(proposal_id: str) -> dict:
    for r in read_all():
        if r.get("id") == proposal_id:
            return r.get("entities", blank_entities())
    return blank_entities()


def record_outcome(proposal_id: str, outcome: dict, engagement_id: str = "") -> dict:
    ents = _entities_of(proposal_id)
    out = write({
        "type": "experiment_outcome", "engagement_id": engagement_id, "entities": ents,
        "links": [proposal_id],
        "payload": {"proposal_id": proposal_id, "result": outcome.get("result"),
                    "data": outcome.get("data", ""), "source": outcome.get("source", "")},
    })
    if outcome.get("result") == "refuted":
        write({
            "type": "moat_blindspot", "engagement_id": engagement_id, "entities": ents,
            "links": [proposal_id, out["id"]],
            "payload": {"proposal_id": proposal_id,
                        "note": outcome.get("data") or "prediction refuted by outcome"},
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest memory.tests.test_outcome -v`
Expected: PASS (2 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/memory/memory.py sapphire-orchestrator/memory/tests/test_outcome.py
git commit -m "C Task 3: active-learning outcomes + moat-blindspot on refutation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Governance switch (`selfimprove/governance.py`)

**Files:**
- Create: `sapphire-orchestrator/selfimprove/__init__.py`
- Create: `sapphire-orchestrator/selfimprove/governance.json`
- Create: `sapphire-orchestrator/selfimprove/governance.py`
- Create: `sapphire-orchestrator/selfimprove/tests/__init__.py`
- Test: `sapphire-orchestrator/selfimprove/tests/test_governance.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_policy(path=None) -> dict`; `may_auto_apply(artifact_type, policy=None) -> bool`; `trigger_count(policy=None) -> int`; `freshness_days(policy=None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/selfimprove/tests/test_governance.py
import unittest
from selfimprove.governance import load_policy, may_auto_apply, trigger_count, freshness_days

class TestGovernance(unittest.TestCase):
    def test_default_is_tiered(self):
        self.assertEqual(load_policy()["level"], "tiered")

    def test_memory_auto_applies(self):
        self.assertTrue(may_auto_apply("memory"))

    def test_behavior_change_gated(self):
        for a in ["skills", "specs", "scenarios", "routes"]:
            self.assertFalse(may_auto_apply(a))

    def test_unknown_artifact_defaults_false(self):
        self.assertFalse(may_auto_apply("nuclear_codes"))

    def test_thresholds(self):
        self.assertEqual(trigger_count(), 3)
        self.assertEqual(freshness_days(), 90)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_governance -v`
Expected: FAIL — `selfimprove.governance` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/selfimprove/__init__.py
"""Sapphire self-improvement loop: governance, reflect, authoring, metrics."""
```

```json
// sapphire-orchestrator/selfimprove/governance.json  (WRITE WITHOUT THIS COMMENT LINE — JSON has no comments)
{
  "level": "tiered",
  "auto_apply": {"memory": true, "skills": false, "specs": false, "scenarios": false, "routes": false},
  "freshness_days": 90,
  "authoring_trigger_count": 3
}
```

```python
# sapphire-orchestrator/selfimprove/governance.py
"""The tiered governance switch (spec §6.5). Default: memory auto-applies; behavior-change
(skills/specs/scenarios/routes) is gated to the proposed/ queue for human approval. Moving to
fully-autonomous later = flip these flags — no code change."""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent / "governance.json"


def load_policy(path=None) -> dict:
    p = Path(path) if path else Path(os.environ.get("SAPPHIRE_GOVERNANCE", str(_DEFAULT)))
    return json.loads(p.read_text(encoding="utf-8"))


def may_auto_apply(artifact_type: str, policy=None) -> bool:
    pol = policy if policy is not None else load_policy()
    return bool(pol.get("auto_apply", {}).get(artifact_type, False))


def trigger_count(policy=None) -> int:
    pol = policy if policy is not None else load_policy()
    return int(pol.get("authoring_trigger_count", 3))


def freshness_days(policy=None) -> int:
    pol = policy if policy is not None else load_policy()
    return int(pol.get("freshness_days", 90))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_governance -v`
Expected: PASS (5 tests OK). Also verify JSON validity: `python -c "import json; json.load(open('selfimprove/governance.json'))"`.

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/selfimprove/__init__.py sapphire-orchestrator/selfimprove/governance.json sapphire-orchestrator/selfimprove/governance.py sapphire-orchestrator/selfimprove/tests/__init__.py sapphire-orchestrator/selfimprove/tests/test_governance.py
git commit -m "C Task 4: tiered governance switch (memory auto; behavior-change gated)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Reflect step — trace → memory (`selfimprove/reflect.py`)

**Files:**
- Create: `sapphire-orchestrator/selfimprove/reflect.py`
- Test: `sapphire-orchestrator/selfimprove/tests/test_reflect.py`

**Interfaces:**
- Consumes: `memory.write`, `memory.blank_entities`; the harness trace JSONL at `RohanOnly/engagements/<id>/trace.jsonl` (`SAPPHIRE_ENGAGEMENTS_DIR` override).
- Produces: `reflect(engagement_id) -> dict` — reads the engagement's trace; for an `engagement_close` row writes a `conclusion` (and an `experiment_proposal` if `synthesis.proposed_experiment` is present); for any agent row whose `output` has `facts`, writes each as a `fact` record (a fact flagged `DIVERGENCE` becomes a `divergence` record), carrying the candidate as a gene entity and the row's `provenance`. Returns `{"engagement_id", "written": <count>, "records": [...]}`. All writes go through `memory.write` (so the data boundary + schema are enforced).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/selfimprove/tests/test_reflect.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from selfimprove.reflect import reflect
from memory import read_all, recall

class TestReflect(unittest.TestCase):
    def setUp(self):
        self.eng = tempfile.mkdtemp()
        self.mem = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.mem
        d = Path(self.eng) / "engX"
        d.mkdir(parents=True, exist_ok=True)
        rows = [
            {"type": "engagement_open", "engagement_id": "engX", "plan": {"query": "Nav1.9?"}},
            {"engagement_id": "engX", "agent_id": "emet-runner", "provenance": "emet-live",
             "output": {"candidate": "SCN11A",
                        "facts": [{"value": "GoF analgesia", "source": "PMID:1", "tier": "T2"},
                                  {"value": "moat-vs-lit gap", "source": "PMID:2", "tier": "T2", "flag": "DIVERGENCE"}]}},
            {"type": "engagement_close", "engagement_id": "engX",
             "synthesis": {"recommendation": "advance to de-risking", "confidence": "conditional",
                           "proposed_experiment": "resolve Nav1.9 persistent current",
                           "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["pain"], "drugs": []}}},
        ]
        (d / "trace.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_reflect_writes_conclusion_proposal_and_facts(self):
        summary = reflect("engX")
        self.assertGreaterEqual(summary["written"], 4)   # conclusion + proposal + 2 facts
        types = [r["type"] for r in read_all()]
        self.assertIn("conclusion", types)
        self.assertIn("experiment_proposal", types)
        self.assertIn("fact", types)
        self.assertIn("divergence", types)               # the DIVERGENCE-flagged fact

    def test_reflected_memory_is_recallable(self):
        reflect("engX")
        hits = recall({"genes": ["SCN11A"]})
        self.assertTrue(any(r["type"] == "conclusion" for r in hits))

    def test_missing_trace_is_empty_not_error(self):
        self.assertEqual(reflect("no_such_engagement")["written"], 0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_reflect -v`
Expected: FAIL — `selfimprove.reflect` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/selfimprove/reflect.py
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
    written = []
    for row in _rows(engagement_id):
        if row.get("type") == "engagement_close":
            syn = row.get("synthesis", {}) or {}
            ents = syn.get("entities") or blank_entities()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_reflect -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/selfimprove/reflect.py sapphire-orchestrator/selfimprove/tests/test_reflect.py
git commit -m "C Task 5: reflect step — harness trace -> durable memory (Tier-1 auto)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Gated authoring (`selfimprove/authoring.py`)

**Files:**
- Create: `sapphire-orchestrator/selfimprove/authoring.py`
- Test: `sapphire-orchestrator/selfimprove/tests/test_authoring.py`

**Interfaces:**
- Consumes: `selfimprove.governance` (`load_policy`, `may_auto_apply`, `trigger_count`).
- Produces: `propose(artifact_type, name, content, rationale, policy=None) -> dict` (writes a proposal JSON to `proposed/`, `auto_applied` per governance — `False` under the tiered default); `propose_from_routes(route_counts: dict, policy=None) -> list[dict]` (for each route seen ≥ `trigger_count` with no scenario, drafts a `scenarios` proposal). `SAPPHIRE_PROPOSED_DIR` override.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/selfimprove/tests/test_authoring.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from selfimprove.authoring import propose, propose_from_routes

class TestAuthoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_PROPOSED_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_PROPOSED_DIR", None)

    def test_propose_writes_gated_artifact(self):
        p = propose("skills", "kcnt1-runner", "# draft skill", "needed for KCNT1 queries")
        self.assertFalse(p["auto_applied"])               # tiered: skills are gated
        files = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["rationale"], "needed for KCNT1 queries")

    def test_routes_at_threshold_proposed(self):
        out = propose_from_routes({"als_modality": 3, "rare_cns": 1})
        names = [p["name"] for p in out]
        self.assertIn("als_modality", names)              # 3 >= trigger_count
        self.assertNotIn("rare_cns", names)               # 1 < trigger_count

    def test_proposals_default_not_auto_applied(self):
        out = propose_from_routes({"als_modality": 5})
        self.assertTrue(all(p["auto_applied"] is False for p in out))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_authoring -v`
Expected: FAIL — `selfimprove.authoring` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/selfimprove/authoring.py
"""Tier-2 gated authoring (spec §6.4): draft new behavior (skills/specs/scenarios/routes)
into the proposed/ review queue. Nothing is applied unless governance allows it (the tiered
default gates all behavior-change for human approval)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .governance import load_policy, may_auto_apply, trigger_count

_DEFAULT_PROPOSED = Path(__file__).resolve().parents[1] / "proposed"


def _dir() -> Path:
    d = Path(os.environ.get("SAPPHIRE_PROPOSED_DIR", str(_DEFAULT_PROPOSED)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", s.lower()).strip("-") or "item"


def propose(artifact_type: str, name: str, content: str, rationale: str, policy=None) -> dict:
    pol = policy if policy is not None else load_policy()
    proposal = {
        "artifact_type": artifact_type, "name": name, "content": content,
        "rationale": rationale, "auto_applied": may_auto_apply(artifact_type, pol),
    }
    (_dir() / f"{artifact_type}-{_slug(name)}.json").write_text(
        json.dumps(proposal, indent=2), encoding="utf-8")
    return proposal


def propose_from_routes(route_counts: dict, policy=None) -> list:
    pol = policy if policy is not None else load_policy()
    threshold = trigger_count(pol)
    out = []
    for route, count in route_counts.items():
        if count >= threshold:
            out.append(propose("scenarios", route,
                               f"# TODO: capture a scenario for route '{route}'",
                               f"seen {count}x with no scenario", pol))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_authoring -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/selfimprove/authoring.py sapphire-orchestrator/selfimprove/tests/test_authoring.py
git commit -m "C Task 6: Tier-2 gated authoring (drafts to proposed/, governance-gated)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Improvement metrics + report (`selfimprove/metrics.py`)

**Files:**
- Create: `sapphire-orchestrator/selfimprove/metrics.py`
- Test: `sapphire-orchestrator/selfimprove/tests/test_metrics.py`

**Interfaces:**
- Consumes: `memory.read_all`.
- Produces: `compute_metrics() -> dict` (`records`, `by_type`, `proposals`, `outcomes`, `prediction_accuracy` = confirmed/(confirmed+refuted) or `None`, `blindspots`); `write_report(path=None) -> dict` (renders a Markdown report to `<memory dir>/REPORT.md` or `path`, returns the metrics).

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/selfimprove/tests/test_metrics.py
import os
import tempfile
import unittest
from pathlib import Path
from memory import write, record_outcome, blank_entities
from selfimprove.metrics import compute_metrics, write_report

def proposal():
    ents = blank_entities(); ents["genes"] = ["SCN11A"]
    return write({"type": "experiment_proposal", "entities": ents, "payload": {"experiment": "x"}})

class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_prediction_accuracy_and_blindspots(self):
        p1 = proposal(); p2 = proposal()
        record_outcome(p1["id"], {"result": "confirmed", "data": "", "source": "w"})
        record_outcome(p2["id"], {"result": "refuted", "data": "missed it", "source": "w"})
        m = compute_metrics()
        self.assertEqual(m["proposals"], 2)
        self.assertEqual(m["outcomes"], 2)
        self.assertAlmostEqual(m["prediction_accuracy"], 0.5)
        self.assertEqual(m["blindspots"], 1)               # the refuted one opened a blindspot

    def test_accuracy_none_when_no_outcomes(self):
        proposal()
        self.assertIsNone(compute_metrics()["prediction_accuracy"])

    def test_write_report_creates_markdown(self):
        proposal()
        write_report()
        self.assertTrue((Path(self.tmp) / "REPORT.md").exists())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_metrics -v`
Expected: FAIL — `selfimprove.metrics` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/selfimprove/metrics.py
"""Improvement metrics (spec §6.6): make 'gets better' a tracked number, not a claim."""
from __future__ import annotations

import os
from pathlib import Path

from memory import read_all
from memory.memory import _dir as _memory_dir   # reuse the configured memory dir


def compute_metrics() -> dict:
    recs = read_all()
    by_type: dict = {}
    for r in recs:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    outcomes = [r for r in recs if r["type"] == "experiment_outcome"]
    confirmed = sum(1 for o in outcomes if o["payload"].get("result") == "confirmed")
    refuted = sum(1 for o in outcomes if o["payload"].get("result") == "refuted")
    accuracy = (confirmed / (confirmed + refuted)) if (confirmed + refuted) else None
    return {
        "records": len(recs), "by_type": by_type,
        "proposals": by_type.get("experiment_proposal", 0),
        "outcomes": len(outcomes),
        "prediction_accuracy": accuracy,
        "blindspots": by_type.get("moat_blindspot", 0),
    }


def write_report(path=None) -> dict:
    m = compute_metrics()
    acc = "n/a" if m["prediction_accuracy"] is None else f"{m['prediction_accuracy']:.0%}"
    lines = [
        "# Sapphire Self-Improvement — metrics", "",
        f"- memory records: {m['records']}",
        f"- experiment proposals: {m['proposals']}",
        f"- outcomes ingested: {m['outcomes']}",
        f"- prediction accuracy (confirmed / confirmed+refuted): {acc}",
        f"- moat blind spots opened: {m['blindspots']}", "",
        "## records by type",
    ] + [f"- {t}: {n}" for t, n in sorted(m["by_type"].items())]
    out = Path(path) if path else (_memory_dir() / "REPORT.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_metrics -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Run the whole C suite + commit**

Run: `cd sapphire-orchestrator && python -m unittest discover -s memory/tests && python -m unittest discover -s selfimprove/tests`
Expected: all green.

```bash
git add sapphire-orchestrator/selfimprove/metrics.py sapphire-orchestrator/selfimprove/tests/test_metrics.py
git commit -m "C Task 7: improvement metrics + REPORT.md (prediction accuracy, blind spots)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (§6):** §6.1 memory store (append-only, boundary-guarded, schema-valid) → Tasks 1, plus `store.jsonl`/`index.json`. §6.2 recall (entity-ranked priors) → Task 2; "priors flagged for re-validation" is the consumer's (orchestrator integration) responsibility — recall returns them tagged by type/recency. §6.3 active-learning spine (record_outcome → moat_blindspot) → Task 3. §6.4 gated authoring → Task 6. §6.5 governance switch → Task 4. §6.6 metrics → Task 7. §6.7 reflect (trace → memory) → Task 5.

**Deferred to integration (noted, not dropped):** wiring `reflect()`/`recall()` into `orchestrator.py`'s engagement lifecycle and exposing `record_outcome` via a CLI / `serve.py` endpoint (spec §6.3) happen in the integration step alongside workstream B — they need the orchestrator's live engagement loop. The loop's units are all built and independently tested here.

**Placeholder scan:** No TBD/TODO. The `recall`/`record_outcome` placeholders in Task 1 are explicitly replaced in Tasks 2/3 (a deliberate incremental build of one module), not left dangling. `governance.json` carries a `//` note ONLY in the plan with an explicit instruction to omit it (JSON has no comments).

**Type consistency:** `write(record) -> dict`, `read_all() -> list`, `blank_entities() -> dict`, `recall(entities, types, k) -> list`, `record_outcome(proposal_id, outcome, engagement_id) -> dict` are defined in Tasks 1–3 and consumed unchanged by `reflect` (Task 5) and `metrics` (Task 7). `MemoryRefusal` raised by `write` is the boundary/schema gate. `may_auto_apply`/`trigger_count` (Task 4) consumed by `authoring` (Task 6). `compute_metrics()` keys match the test assertions. The memory record shape matches P0's `MEMORY_RECORD_SCHEMA` (validated inside `write`).

**Note for integration/B:** the orchestrator calls `recall(scope.entities)` at engagement start (inject as `memory-recall` priors) and `reflect(engagement_id)` after synthesize; `record_outcome` is exposed for wet-lab feedback. The harness already writes the trace `reflect` consumes.
