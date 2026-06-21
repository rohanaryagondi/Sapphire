# Sapphire Phase 5 — B + Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the self-improvement loop into the real engine (trace + recall + reflect around every engagement), expose the active-learning feedback path (a `record-outcome` CLI), and stand up the science-geared scenario suite (a 10-scenario variety manifest + schema/coverage validation + a repeatable live-capture helper).

**Architecture:** Additive, low-risk. A new `engagement.py` runs an engagement: it executes the existing `Orchestrator` engine, brackets it with the D harness trace (`open_engagement`/`close_engagement`), calls `recall` at the start (priors in) and `reflect` after (memory out) — so the C loop runs end-to-end on the live engine WITHOUT a risky per-agent rewrite of the working demo. Entities are extracted from the engagement and attached to the close-synthesis so reflected conclusions are recallable. A small `selfimprove/cli.py` exposes `record-outcome`. The scenario suite is a `scenarios/manifest.json` variety matrix + a validation test + a `capture.py` draft helper (injectable, offline-tested); the 8 not-yet-captured scenarios are captured live via the helper (needs a BenchSci session) — never fabricated.

**Tech Stack:** Python 3, **stdlib only** (`json`, `os`, `re`, `hashlib`, `argparse`, `pathlib`, `unittest`). Imports the engine (`orchestrator`), harness (`harness.trace`), memory (`memory`), loop (`selfimprove`).

## Global Constraints

- **Stdlib-only Python.** No third-party deps. Branch `Rohan`; commit per task; do NOT push to main.
- **Import-by-CWD:** tests run with CWD = `sapphire-orchestrator/`.
- **Additive integration:** do NOT rewrite `orchestrator.py`'s control flow or the per-agent evidence path; `engagement.py` wraps the engine. The legacy engine must keep working unchanged (`run.py nav1_8` still passes).
- **No fabricated science.** New scenarios are captured live via the helper or left as honestly-marked `stub` in the manifest. Never invent PMIDs/evidence.
- **Memory writes stay guarded.** All loop writes go through `memory.write`/`reflect` (public-identifiers-only, schema-valid) — unchanged from workstream C.
- **Env overrides (tests):** `SAPPHIRE_ENGAGEMENTS_DIR`, `SAPPHIRE_MEMORY_DIR` (both as in C/D).

---

### Task 1: Engagement runner — trace + recall + reflect on the live engine (`engagement.py`)

**Files:**
- Create: `sapphire-orchestrator/engagement.py`
- Create: `sapphire-orchestrator/tests/__init__.py`
- Test: `sapphire-orchestrator/tests/test_engagement.py`

**Interfaces:**
- Consumes: `orchestrator.Orchestrator`, `harness.trace`, `memory.recall`, `selfimprove.reflect.reflect`.
- Produces: `extract_entities(text) -> dict` (gene-symbol regex → `{"genes",...}`); `run_engagement(sid_or_query, *, engine=None, do_reflect=True) -> dict` — runs the engine, derives entities, recalls priors (`run["priors"]`), writes a harness trace (open + a dossier agent-row whose `output.facts` are the discover dossier rows + close with synthesis carrying `entities`), runs `reflect` (`run["reflection"]`), returns the enriched run with `run["engagement_id"]`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/tests/test_engagement.py
import os
import tempfile
import unittest
from engagement import extract_entities, run_engagement
from memory import recall

class FakeEngine:
    """Stand-in for Orchestrator.run — returns a crafted run with a gene + dossier + synthesis."""
    def run(self, sid):
        return {
            "id": sid, "title": "Nav1.9 pain", "query": "Is SCN11A a viable analgesic target?",
            "headline": "SCN11A / Nav1.9", "plan": {"disease": "neuropathic pain"},
            "discover": {"dossier": [
                {"field": "B1", "value": "GoF Mendelian", "source": "PMID:26243570", "tier": "T2"},
                {"field": "C3", "value": "moat-vs-lit gap", "source": "PMID:2", "tier": "T2", "flag": "DIVERGENCE"},
            ], "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}},
            "validate": {"runs": []},
            "consult": {"round1": [], "round2": [], "spread": {}},
            "synthesize": {"recommendation": "advance to de-risking", "confidence": "conditional",
                           "proposed_experiment": "resolve Nav1.9 persistent current"},
        }

class TestEngagement(unittest.TestCase):
    def setUp(self):
        self.eng = tempfile.mkdtemp(); self.mem = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.mem

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_extract_entities_finds_genes(self):
        e = extract_entities("SCN11A gain-of-function and KCNT1 in epilepsy")
        self.assertIn("SCN11A", e["genes"])
        self.assertIn("KCNT1", e["genes"])

    def test_run_engagement_writes_recallable_memory(self):
        run = run_engagement("nav1_8", engine=FakeEngine())
        self.assertIn("engagement_id", run)
        self.assertGreaterEqual(run["reflection"]["written"], 1)
        hits = recall({"genes": ["SCN11A"]})
        self.assertTrue(any(r["type"] == "conclusion" for r in hits))
        self.assertTrue(any(r["type"] == "divergence" for r in hits))   # the DIVERGENCE dossier row

    def test_second_engagement_recalls_prior(self):
        run_engagement("nav1_8", engine=FakeEngine())
        run2 = run_engagement("nav1_8", engine=FakeEngine())
        self.assertTrue(run2["priors"])     # priors surfaced from the first engagement

    def test_real_engine_smoke(self):
        # the real Orchestrator must run end-to-end through the wrapper without error
        run = run_engagement("nav1_8")
        self.assertIn("engagement_id", run)
        self.assertIn("synthesize", run)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_engagement -v`
Expected: FAIL — `engagement` module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/tests/__init__.py
# (empty — marks the package)
```

```python
# sapphire-orchestrator/engagement.py
"""Run a Sapphire engagement on the live engine, bracketed by the harness trace and the
self-improvement loop (recall priors in, reflect memory out). Additive: wraps Orchestrator,
does not modify it. This is where the Phase-5 loop runs end-to-end on real engagements."""
from __future__ import annotations

import hashlib
import re

from harness import trace
from memory import recall
from selfimprove.reflect import reflect as _reflect

_GENE_RE = re.compile(r"\b[A-Z]{2,4}[0-9]{1,3}[A-Z]?\b")   # SCN11A, SCN2A, KCNT1, LRRK2, GBA1


def extract_entities(text: str) -> dict:
    genes = sorted(set(_GENE_RE.findall(text or "")))
    return {"genes": genes, "smiles": [], "diseases": [], "drugs": []}


def _eid(key: str) -> str:
    return "eng_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def run_engagement(sid_or_query: str, *, engine=None, do_reflect: bool = True) -> dict:
    if engine is None:
        from orchestrator import Orchestrator
        engine = Orchestrator()
    try:
        run = engine.run(sid_or_query)
    except ValueError:
        run = engine.run_query(sid_or_query)

    ents = extract_entities(f"{run.get('query','')} {run.get('headline','')} {run.get('title','')}")
    disease = (run.get("plan", {}) or {}).get("disease")
    if disease and disease != "general CNS":
        ents["diseases"] = [disease]

    eid = _eid(str(run.get("id") or sid_or_query))
    run["engagement_id"] = eid
    run["priors"] = recall(ents) if (ents["genes"] or ents["diseases"]) else []

    trace.open_engagement(eid, run.get("plan", {}) or {})
    facts = []
    for row in (run.get("discover", {}) or {}).get("dossier", []) or []:
        fact = {"value": row.get("value", ""), "source": row.get("source", ""), "tier": row.get("tier", "T3")}
        if row.get("flag"):
            fact["flag"] = row["flag"]
        facts.append(fact)
    if facts:
        primary = ents["genes"][0] if ents["genes"] else ""
        trace.record(eid, {"agent_id": "dossier", "provenance": "synthesis",
                           "output": {"candidate": primary, "facts": facts}})
    syn = dict(run.get("synthesize", {}) or {})
    syn["entities"] = ents
    trace.close_engagement(eid, syn)

    run["reflection"] = _reflect(eid) if do_reflect else None
    return run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_engagement -v`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/engagement.py sapphire-orchestrator/tests/__init__.py sapphire-orchestrator/tests/test_engagement.py
git commit -m "B+I Task 1: engagement runner — trace + recall + reflect on the live engine

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Active-learning feedback CLI (`selfimprove/cli.py`)

**Files:**
- Create: `sapphire-orchestrator/selfimprove/cli.py`
- Create: `sapphire-orchestrator/selfimprove/__main__.py`
- Test: `sapphire-orchestrator/selfimprove/tests/test_cli.py`

**Interfaces:**
- Consumes: `memory.record_outcome`, `selfimprove.metrics.write_report`.
- Produces: `main(argv) -> int` — `record-outcome <proposal_id> <result> [--data D] [--source S] [--engagement E]` ingests a wet-lab/real outcome (prints the new record id; returns 0); `report` writes the metrics report (returns 0); unknown/missing command returns non-zero. `__main__.py` calls `sys.exit(main(sys.argv[1:]))`.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/selfimprove/tests/test_cli.py
import os
import tempfile
import unittest
from selfimprove.cli import main
from memory import write, read_all, blank_entities

class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _proposal(self):
        ents = blank_entities(); ents["genes"] = ["SCN11A"]
        return write({"type": "experiment_proposal", "entities": ents, "payload": {"experiment": "x"}})

    def test_record_outcome_writes(self):
        p = self._proposal()
        rc = main(["record-outcome", p["id"], "confirmed", "--data", "assay ok", "--source", "wetlab"])
        self.assertEqual(rc, 0)
        self.assertTrue(any(r["type"] == "experiment_outcome" for r in read_all()))

    def test_record_outcome_refuted_opens_blindspot(self):
        p = self._proposal()
        main(["record-outcome", p["id"], "refuted", "--data", "missed it"])
        self.assertTrue(any(r["type"] == "moat_blindspot" for r in read_all()))

    def test_report_command(self):
        self.assertEqual(main(["report"]), 0)

    def test_unknown_command_nonzero(self):
        self.assertNotEqual(main(["frobnicate"]), 0)

    def test_missing_args_nonzero(self):
        self.assertNotEqual(main(["record-outcome"]), 0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_cli -v`
Expected: FAIL — `selfimprove.cli` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/selfimprove/cli.py
"""CLI for the active-learning feedback path (spec §6.3): ingest a real/wet-lab outcome for a
proposed experiment, or write the metrics report."""
from __future__ import annotations

import argparse

from memory import record_outcome
from .metrics import write_report


def main(argv) -> int:
    parser = argparse.ArgumentParser(prog="selfimprove", description="Sapphire self-improvement loop CLI")
    sub = parser.add_subparsers(dest="cmd")

    ro = sub.add_parser("record-outcome", help="ingest an outcome for a proposed experiment")
    ro.add_argument("proposal_id")
    ro.add_argument("result", choices=["confirmed", "refuted", "partial"])
    ro.add_argument("--data", default="")
    ro.add_argument("--source", default="")
    ro.add_argument("--engagement", default="")

    sub.add_parser("report", help="write the improvement metrics report")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2     # argparse already printed the error (missing/invalid args)

    if args.cmd == "record-outcome":
        rec = record_outcome(args.proposal_id,
                             {"result": args.result, "data": args.data, "source": args.source},
                             engagement_id=args.engagement)
        print(rec["id"])
        return 0
    if args.cmd == "report":
        m = write_report()
        print(f"records={m['records']} accuracy={m['prediction_accuracy']} blindspots={m['blindspots']}")
        return 0

    parser.print_help()
    return 2
```

```python
# sapphire-orchestrator/selfimprove/__main__.py
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest selfimprove.tests.test_cli -v`
Expected: PASS (5 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/selfimprove/cli.py sapphire-orchestrator/selfimprove/__main__.py sapphire-orchestrator/selfimprove/tests/test_cli.py
git commit -m "B+I Task 2: record-outcome CLI (active-learning feedback path)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Science scenario suite — manifest + validation (`scenarios/manifest.json`)

**Files:**
- Create: `sapphire-orchestrator/scenarios/manifest.json`
- Test: `sapphire-orchestrator/tests/test_scenarios.py`

**Interfaces:**
- Consumes: the existing `scenarios/*.json` + the manifest.
- Produces: `manifest.json` — the 10-scenario variety matrix (id, title, disease, variety_axis, status `captured|stub`). The test validates every captured scenario JSON against the required-keys contract and asserts the manifest covers all variety axes + the captured scenarios actually exist on disk.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/tests/test_scenarios.py
import json
import unittest
from pathlib import Path

SCN_DIR = Path(__file__).resolve().parents[1] / "scenarios"
MANIFEST = SCN_DIR / "manifest.json"
REQUIRED_KEYS = {"id", "title", "query", "headline", "discover", "validate", "panel", "rebuttal", "synthesize"}
AXES = {"go_no_go", "selectivity", "mechanism", "modality", "admet_bbb",
        "biomarker", "abstain", "divergence", "payer", "ip_veto"}

class TestScenarios(unittest.TestCase):
    def test_manifest_exists_and_has_ten(self):
        m = json.loads(MANIFEST.read_text())
        self.assertGreaterEqual(len(m["scenarios"]), 10)

    def test_manifest_covers_all_variety_axes(self):
        m = json.loads(MANIFEST.read_text())
        covered = {s["variety_axis"] for s in m["scenarios"]}
        self.assertTrue(AXES.issubset(covered), f"missing axes: {AXES - covered}")

    def test_captured_scenarios_exist_and_validate(self):
        m = json.loads(MANIFEST.read_text())
        captured = [s for s in m["scenarios"] if s["status"] == "captured"]
        self.assertGreaterEqual(len(captured), 2)   # nav1_8 + tsc2 ship today
        for s in captured:
            f = SCN_DIR / f"{s['id']}.json"
            self.assertTrue(f.exists(), f"captured scenario file missing: {f}")
            data = json.loads(f.read_text())
            self.assertTrue(REQUIRED_KEYS.issubset(data.keys()),
                            f"{s['id']} missing keys: {REQUIRED_KEYS - set(data.keys())}")

    def test_every_scenario_has_status(self):
        m = json.loads(MANIFEST.read_text())
        for s in m["scenarios"]:
            self.assertIn(s["status"], ("captured", "stub"))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_scenarios -v`
Expected: FAIL — `manifest.json` missing.

- [ ] **Step 3: Write minimal implementation**

First confirm the two shipped scenario ids and that they carry `REQUIRED_KEYS`:
Run `cd sapphire-orchestrator && python -c "import json,glob; [print(f, sorted(json.load(open(f)).keys())) for f in glob.glob('scenarios/*.json')]"`.
If a shipped scenario is missing one of `panel`/`rebuttal` (older shape), keep the test's `REQUIRED_KEYS` aligned to what the engine actually reads — adjust `REQUIRED_KEYS` to the intersection the engine relies on (`id,title,query,headline,discover,validate,synthesize`) and the panel/rebuttal pair only if both shipped files have them. (Do this BEFORE writing the manifest so the test reflects reality.)

Create `sapphire-orchestrator/scenarios/manifest.json` (mark the two shipped ones `captured`; the eight new ones `stub` — captured live via `capture.py`, never fabricated):

```json
{
  "_meta": {
    "title": "Sapphire science-geared scenario suite (spec §5)",
    "note": "captured = full cited dossier shipped; stub = capture live via capture.py with a BenchSci session (not fabricated).",
    "primary_user": "science"
  },
  "scenarios": [
    {"id": "nav1_8", "title": "Nav1.8/Nav1.9 non-opioid analgesic", "disease": "pain", "variety_axis": "go_no_go", "status": "captured"},
    {"id": "tsc2", "title": "TSC2 / mTOR", "disease": "epilepsy/TSC", "variety_axis": "selectivity", "status": "captured"},
    {"id": "scn2a_epilepsy", "title": "SCN2A epilepsy — GoF vs LoF", "disease": "epilepsy", "variety_axis": "mechanism", "status": "stub"},
    {"id": "c9orf72_als", "title": "C9orf72 ALS — ASO vs small molecule", "disease": "ALS", "variety_axis": "modality", "status": "stub"},
    {"id": "lrrk2_pd", "title": "LRRK2 Parkinson's kinase inhibitor", "disease": "Parkinson's", "variety_axis": "admet_bbb", "status": "stub"},
    {"id": "gba1_pd", "title": "GBA1 Parkinson's / Gaucher", "disease": "Parkinson's", "variety_axis": "biomarker", "status": "stub"},
    {"id": "kcnt1_dee", "title": "KCNT1 developmental epileptic encephalopathy", "disease": "rare CNS", "variety_axis": "selectivity", "status": "stub"},
    {"id": "novel_ad_target", "title": "Novel Alzheimer's target (thin evidence)", "disease": "Alzheimer's", "variety_axis": "abstain", "status": "stub"},
    {"id": "moat_divergence", "title": "Internal-vs-literature signal", "disease": "channelopathy", "variety_axis": "divergence", "status": "stub"},
    {"id": "rare_cns_payer", "title": "Rare CNS therapy value story", "disease": "rare CNS", "variety_axis": "payer", "status": "stub"},
    {"id": "competitor_ip_gate", "title": "Competitor-IP / prior-CRL gate", "disease": "cross-cutting", "variety_axis": "ip_veto", "status": "stub"}
  ]
}
```

(Note: this lists 11 entries so all 10 axes are covered with two `selectivity` scenarios — adjust to exactly your preferred 10 if desired; the test requires ≥10 and all axes covered.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_scenarios -v`
Expected: PASS (4 tests OK). If `test_captured_scenarios_exist_and_validate` fails on a key, reconcile `REQUIRED_KEYS` to the shipped files (Step 3) and re-run.

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/scenarios/manifest.json sapphire-orchestrator/tests/test_scenarios.py
git commit -m "B+I Task 3: science scenario suite manifest + validation (10 axes, honest capture status)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Repeatable scenario capture helper (`capture.py`)

**Files:**
- Create: `sapphire-orchestrator/capture.py`
- Create: `_build/capture_scenario.py` (thin CLI wrapper)
- Test: `sapphire-orchestrator/tests/test_capture.py`

**Interfaces:**
- Consumes: injected `plan_fn`, `emet_fn`, `qmodels_fn` (so it is offline-testable); writes drafts to `scenarios/drafts/`.
- Produces: `draft_scenario(query, *, plan_fn, emet_fn=None, qmodels_fn=None) -> dict` — assembles a DRAFT scenario dict (plan + EMET-captured discover facts + Q-Models validate runs + empty panel/rebuttal/synthesize scaffold) for human curation; `write_draft(draft) -> Path` writes `scenarios/drafts/<id>.json`. The thin `_build/capture_scenario.py` wires the live `plan`/`emet-runner`/`qmodels` functions. `SAPPHIRE_DRAFTS_DIR` override.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/tests/test_capture.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from capture import draft_scenario, write_draft

def fake_plan(query):
    return {"id": "scn2a_epilepsy", "title": "SCN2A epilepsy", "query": query,
            "headline": "SCN2A", "disease": "epilepsy", "modality": "small molecule"}

def fake_emet(query):
    return {"candidate": "SCN2A", "facts": [
        {"value": "GoF early-onset; LoF later-onset", "source": "PMID:111 [PMID:111]", "tier": "T2"}]}

def fake_qmodels(query):
    return [{"model": "Boltz-2", "out": "pKd 7.1", "provenance": "stub"}]

class TestCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_DRAFTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_DRAFTS_DIR", None)

    def test_draft_assembles_from_parts(self):
        d = draft_scenario("Is SCN2A druggable?", plan_fn=fake_plan, emet_fn=fake_emet, qmodels_fn=fake_qmodels)
        self.assertEqual(d["id"], "scn2a_epilepsy")
        self.assertEqual(d["query"], "Is SCN2A druggable?")
        self.assertTrue(d["discover"]["dossier"])          # EMET facts present
        self.assertTrue(d["validate"]["runs"])             # Q-Models runs present
        self.assertEqual(d["_status"], "draft")            # clearly marked unfinished

    def test_draft_without_optional_sources(self):
        d = draft_scenario("q", plan_fn=fake_plan)         # no emet/qmodels
        self.assertEqual(d["discover"]["dossier"], [])
        self.assertEqual(d["validate"]["runs"], [])

    def test_write_draft_to_drafts_dir(self):
        d = draft_scenario("q", plan_fn=fake_plan)
        p = write_draft(d)
        self.assertTrue(p.exists())
        self.assertEqual(json.loads(p.read_text())["id"], "scn2a_epilepsy")
        self.assertIn("drafts", str(p))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_capture -v`
Expected: FAIL — `capture` module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/capture.py
"""Repeatable scenario capture (spec §5): assemble a DRAFT scenario from the planner + a live
EMET pass + Q-Models, for human curation. Injectable sources so it is offline-testable; the live
wiring lives in _build/capture_scenario.py. Drafts are clearly marked unfinished — never a
fabricated final scenario."""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_DRAFTS = Path(__file__).resolve().parent / "scenarios" / "drafts"


def _drafts_dir() -> Path:
    d = Path(os.environ.get("SAPPHIRE_DRAFTS_DIR", str(_DEFAULT_DRAFTS)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def draft_scenario(query, *, plan_fn, emet_fn=None, qmodels_fn=None) -> dict:
    plan = plan_fn(query)
    findings = emet_fn(query) if emet_fn else {"candidate": "", "facts": []}
    runs = qmodels_fn(query) if qmodels_fn else []
    dossier = [{"field": "?", "value": f["value"], "source": f["source"],
                "tier": f.get("tier", "T2"), **({"flag": f["flag"]} if f.get("flag") else {})}
               for f in findings.get("facts", [])]
    return {
        "id": plan["id"], "title": plan["title"], "query": query,
        "headline": plan.get("headline", ""),
        "discover": {"source": "EMET (live) + internal moat (mock)", "dossier": dossier,
                     "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}, "status": "draft"},
        "validate": {"source": "Q-Models", "runs": runs, "mock": False},
        "panel": [], "rebuttal": [],
        "synthesize": {"recommendation": "", "confidence": "", "proposed_experiment": ""},
        "_status": "draft",
        "_todo": "human curation: tier/cite facts, seat panel, write synthesis; then drop _status and move to scenarios/",
    }


def write_draft(draft) -> Path:
    p = _drafts_dir() / f"{draft['id']}.json"
    p.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return p
```

```python
# _build/capture_scenario.py
"""Live scenario capture CLI: python _build/capture_scenario.py "<query>"
Drives the real planner + emet-runner (needs a logged-in BenchSci session) + Q-Models,
and writes a DRAFT to scenarios/drafts/ for human curation. Never writes a final scenario."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sapphire-orchestrator"))

from capture import draft_scenario, write_draft       # noqa: E402
from orchestrator import Orchestrator                 # noqa: E402
from emet.handler import make_emet_handler            # noqa: E402
from harness.contracts import resolve                 # noqa: E402


def _plan_fn(query):
    eng = Orchestrator()
    tri = eng.triage(query)
    return {"id": (tri.get("disease") or "new_scenario"), "title": tri.get("disease_label", "New scenario"),
            "headline": "", "query": query}


def _emet_fn(query):
    handler = make_emet_handler()                      # live Playwright runner
    return handler(resolve("emet-runner"), {"candidate": query, "question": query})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python _build/capture_scenario.py "<query>"'); sys.exit(2)
    q = sys.argv[1]
    draft = draft_scenario(q, plan_fn=_plan_fn, emet_fn=_emet_fn)
    path = write_draft(draft)
    print(f"draft written: {path} (curate it, then move to scenarios/)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest tests.test_capture -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Run the whole Phase-5 surface + commit**

Run: `cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove tests; do python -m unittest discover -s $s/tests 2>/dev/null || python -m unittest discover -s $s; done` — and explicitly `python -m unittest discover -s tests` for the top-level package.
Expected: all green.

```bash
git add sapphire-orchestrator/capture.py _build/capture_scenario.py sapphire-orchestrator/tests/test_capture.py
git commit -m "B+I Task 4: repeatable scenario capture helper (injectable, draft-only)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** §5 scenario suite → Task 3 (manifest + validation, 10 axes, honest capture status) + Task 4 (repeatable capture helper). §6.2/§6.7 recall+reflect wired into a live engagement + §6 loop running end-to-end → Task 1. §6.3 active-learning feedback exposed → Task 2 CLI. The C-review carried item (synthesize must emit entities so conclusions are recallable) → Task 1 attaches extracted `entities` to the close-synthesis (engine left unmodified).

**Honest scope (stated, not hidden):** the 8 new scenarios are `stub` in the manifest and captured live via `capture.py` (needs a BenchSci session) — NOT fabricated. Full per-agent rewiring of the legacy engine to `harness.run` is deliberately NOT done here (it would destabilize the working demo); the loop is wired around engagements additively, and EMET/harness are already callable + unit-proven. This is noted for a future hardening pass.

**Placeholder scan:** No TBD/TODO in code. Task 3 Step 3 instructs reconciling `REQUIRED_KEYS` to the actually-shipped scenario shape BEFORE writing the manifest (a real verification step, not a placeholder). `capture.py` drafts carry an explicit `_status: draft` + `_todo` so a draft can never be mistaken for a finished scenario.

**Type consistency:** `run_engagement(sid_or_query, *, engine=None, do_reflect=True) -> dict` and `extract_entities(text) -> dict` (Task 1) match their tests. `main(argv) -> int` (Task 2) matches the CLI tests + `__main__`. `draft_scenario(query, *, plan_fn, emet_fn, qmodels_fn) -> dict` / `write_draft(draft) -> Path` (Task 4) match their tests. `emet_fn` returns the harness `findings` shape (candidate+facts), exactly what `make_emet_handler()` produces (workstream A) — so the live capture wiring is consistent.

**Note:** Task 1's trace agent-row bridges the canned dossier into `reflect`; all writes still go through `memory.write`, so the data boundary holds even for engine-sourced facts.
