# Sapphire Phase 5 — A: Live EMET via Playwright Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EMET (BenchSci) a live, harness-callable agent — a reusable `emet-runner` Playwright skill the orchestrator's EMET Analyst invokes, behind an interface the coming EMET-MCP drops into unchanged.

**Architecture:** Three pieces. (1) `.claude/skills/emet-runner/SKILL.md` — the skill doc a Claude+Playwright session follows to drive EMET per `sapphire-cascade/emet_protocol.md` and return the raw EMET *envelope* (spec §3.1). (2) `sapphire-orchestrator/emet/adapter.py` — `normalize_emet(envelope)` maps the raw envelope → the harness `findings` shape (cited T2 facts). (3) `sapphire-orchestrator/emet/handler.py` — `emet_handler` / `make_emet_handler(runner)`: the seam the harness's `emet-playwright` dispatch calls (registered via `ctx["emet_handler"]`), injectable so it's tested offline; detects a login screen and raises `HarnessEscalation("login-required")`. When the EMET-MCP lands, only `handler.py`'s default runner changes — the envelope, adapter, and callers are unchanged.

**Tech Stack:** Python 3, **stdlib only** (`json`, `subprocess`, `os`, `pathlib`, `unittest`). Imports the D harness (`harness.errors`) and P0 (`contracts`).

## Global Constraints

- **Stdlib-only Python.** No third-party deps. Branch `Rohan`; commit per task; do NOT push to main.
- **Import-by-CWD:** tests run with CWD = `sapphire-orchestrator/` (so `import emet…`, `import harness…`, `import contracts…` resolve).
- **Public identifiers only** ever cross to EMET; on a login screen, **stop and escalate** (never auto-login, never fabricate). — emet_protocol.md, spec §4.
- **EMET tiers its output T2** (curated/peer-reviewed). — emet-analyst.md.
- **EMET never emits a formal `VETO`** — it corroborates/gates via cited evidence; formal VETO (T1) is the veto-class agents' job. An EMET `no_go` → a cited contraindication fact (no flag); `flag` → `KNOWN_UNKNOWN`; `pass` → no extra flag. (This also avoids the harness `facts_only_cited` rule that a `VETO` fact must be T1.)
- **EMET envelope shape (spec §3.1):** `candidate, emet_workflow, verdict(no_go|flag|pass), evidence[{claim,source,id_or_url}], notes, chat_url, captured_at, provenance(emet-live|emet-mcp)`.
- **Harness `findings` shape (the adapter's output):** `{candidate, facts[{value,source,tier,flag?,provenance?}], provenance}` — validated by the `emet-runner` contract in `harness/agents.json`.
- **MCP-swappable:** callers depend on `make_emet_handler()` + the envelope, never on Playwright directly.

---

### Task 1: EMET envelope → findings adapter (`emet/adapter.py`)

**Files:**
- Create: `sapphire-orchestrator/emet/__init__.py`
- Create: `sapphire-orchestrator/emet/adapter.py`
- Create: `sapphire-orchestrator/emet/tests/__init__.py`
- Test: `sapphire-orchestrator/emet/tests/test_adapter.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces: `normalize_emet(envelope: dict) -> dict` — returns `{"candidate", "facts": [...], "provenance": "emet-live"}`; each evidence item → a `{value, source, tier:"T2"}` fact; verdict `flag` appends a `KNOWN_UNKNOWN` summary fact, `no_go` appends an unflagged contraindication fact, `pass` adds nothing; **never emits a `VETO` flag**.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/emet/tests/test_adapter.py
import unittest
from emet.adapter import normalize_emet
from contracts.jsonschema_min import validate
from harness.contracts import resolve

ENVELOPE = {
    "candidate": "SCN11A",
    "emet_workflow": "Target Validation",
    "verdict": "pass",
    "evidence": [
        {"claim": "GoF mutations validate analgesia", "source": "X et al, Nature 2016", "id_or_url": "PMID:26243570"},
        {"claim": "restricted peripheral expression", "source": "Y et al, 2019", "id_or_url": "PMID:31551682"},
    ],
    "notes": "",
    "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
    "captured_at": "2026-06-21T00:00:00Z",
    "provenance": "emet-live",
}

class TestAdapter(unittest.TestCase):
    def test_evidence_becomes_t2_cited_facts(self):
        out = normalize_emet(ENVELOPE)
        self.assertEqual(out["candidate"], "SCN11A")
        self.assertEqual(len(out["facts"]), 2)
        self.assertTrue(all(f["tier"] == "T2" for f in out["facts"]))
        self.assertIn("PMID:26243570", out["facts"][0]["source"])
        self.assertEqual(out["provenance"], "emet-live")

    def test_pass_adds_no_flag(self):
        out = normalize_emet(ENVELOPE)
        self.assertTrue(all("flag" not in f for f in out["facts"]))

    def test_flag_verdict_appends_known_unknown(self):
        env = dict(ENVELOPE, verdict="flag", notes="thin, conflicting reports")
        out = normalize_emet(env)
        flags = [f.get("flag") for f in out["facts"]]
        self.assertIn("KNOWN_UNKNOWN", flags)

    def test_no_go_appends_contraindication_without_veto(self):
        env = dict(ENVELOPE, verdict="no_go", notes="cardiac liability")
        out = normalize_emet(env)
        self.assertNotIn("VETO", [f.get("flag") for f in out["facts"]])      # EMET never vetoes
        self.assertTrue(any("cardiac liability" in f["value"] for f in out["facts"]))

    def test_output_validates_against_findings_schema(self):
        out = normalize_emet(ENVELOPE)
        schema = resolve("emet-runner").output_schema     # the findings schema
        self.assertEqual(validate(out, schema, schema), [])

    def test_empty_evidence_pass_is_valid(self):
        env = dict(ENVELOPE, evidence=[], verdict="pass")
        out = normalize_emet(env)
        schema = resolve("emet-runner").output_schema
        self.assertEqual(validate(out, schema, schema), [])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_adapter -v`
Expected: FAIL — `emet.adapter` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/emet/__init__.py
"""Live EMET (BenchSci) via Playwright — adapter + handler the harness calls."""
```

```python
# sapphire-orchestrator/emet/adapter.py
"""Map a raw EMET envelope (emet_protocol.md §7 / spec §3.1) to the harness `findings`
shape. EMET output is tiered T2 (curated/peer-reviewed); EMET corroborates/gates via cited
evidence and NEVER emits a formal VETO (that is the veto-class agents' T1 job)."""
from __future__ import annotations

PROVENANCE = "emet-live"


def normalize_emet(envelope: dict) -> dict:
    facts = []
    for ev in envelope.get("evidence", []) or []:
        src = (ev.get("source") or "").strip()
        idu = (ev.get("id_or_url") or "").strip()
        source = f"{src} [{idu}]".strip() if idu else src
        facts.append({"value": ev.get("claim", ""), "source": source, "tier": "T2"})

    verdict = envelope.get("verdict")
    notes = (envelope.get("notes") or "").strip()
    chat = envelope.get("chat_url", "")
    workflow = envelope.get("emet_workflow", "")
    if verdict == "flag":
        facts.append({"value": notes or f"EMET {workflow}: thin/contradictory evidence",
                      "source": chat, "tier": "T2", "flag": "KNOWN_UNKNOWN"})
    elif verdict == "no_go":
        facts.append({"value": notes or f"EMET {workflow}: contraindication / negative evidence",
                      "source": chat, "tier": "T2"})   # cited fact, NOT a VETO flag

    return {"candidate": envelope.get("candidate", ""), "facts": facts, "provenance": PROVENANCE}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_adapter -v`
Expected: PASS (6 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/emet/__init__.py sapphire-orchestrator/emet/adapter.py sapphire-orchestrator/emet/tests/__init__.py sapphire-orchestrator/emet/tests/test_adapter.py
git commit -m "A Task 1: EMET envelope -> findings adapter (T2 cited facts, no VETO)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: EMET handler — the harness seam (`emet/handler.py`)

**Files:**
- Create: `sapphire-orchestrator/emet/handler.py`
- Test: `sapphire-orchestrator/emet/tests/test_handler.py`

**Interfaces:**
- Consumes: `emet.adapter.normalize_emet`; `harness.errors` (`HarnessEscalation`, `escalate`).
- Produces:
  - `emet_handler(contract, inputs, *, runner=None) -> dict` — calls `runner(inputs)` to obtain a raw envelope; if the runner signals a login screen (`{"login_required": True}`) raises `HarnessEscalation("login-required")`; otherwise returns `normalize_emet(raw)`.
  - `make_emet_handler(runner=None) -> callable` — returns a 2-arg `(contract, inputs) -> dict` closure suitable for `ctx["emet_handler"]` (the harness `dispatch_emet` calls handlers with two args).
  - `_default_runner(inputs) -> dict` — the LIVE path: invokes Claude headless with the `emet-runner` skill + Playwright to produce an envelope. (Injectable; never called in tests.)

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/emet/tests/test_handler.py
import unittest
from emet.handler import emet_handler, make_emet_handler
from harness.errors import HarnessEscalation
from harness.contracts import Contract

C = Contract(id="emet-runner", role="", kind="emet-playwright", provenance_label="emet-live")

ENV = {"candidate": "SCN11A", "emet_workflow": "Target Validation", "verdict": "pass",
       "evidence": [{"claim": "GoF analgesia", "source": "X 2016", "id_or_url": "PMID:1"}],
       "notes": "", "chat_url": "u", "captured_at": "t", "provenance": "emet-live"}

class TestHandler(unittest.TestCase):
    def test_handler_normalizes_runner_envelope(self):
        out = emet_handler(C, {"candidate": "SCN11A", "workflow": "Target Validation"},
                           runner=lambda inp: ENV)
        self.assertEqual(out["candidate"], "SCN11A")
        self.assertEqual(out["provenance"], "emet-live")
        self.assertTrue(out["facts"])

    def test_login_required_escalates(self):
        with self.assertRaises(HarnessEscalation) as cm:
            emet_handler(C, {"candidate": "X"}, runner=lambda inp: {"login_required": True})
        self.assertEqual(cm.exception.code, "login-required")

    def test_make_emet_handler_is_two_arg(self):
        h = make_emet_handler(runner=lambda inp: ENV)
        out = h(C, {"candidate": "SCN11A"})       # 2-arg, as the harness calls it
        self.assertEqual(out["candidate"], "SCN11A")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_handler -v`
Expected: FAIL — `emet.handler` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# sapphire-orchestrator/emet/handler.py
"""The EMET seam the harness's `emet-playwright` dispatch calls. Injectable runner so it is
tested offline; the live default drives Claude+Playwright. MCP-swappable: when the EMET-MCP
lands, only `_default_runner` changes."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from harness.errors import escalate
from .adapter import normalize_emet

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_SKILL = ".claude/skills/emet-runner/SKILL.md"


def emet_handler(contract, inputs, *, runner=None) -> dict:
    run = runner or _default_runner
    raw = run(inputs)
    if isinstance(raw, dict) and raw.get("login_required"):
        raise escalate("login-required", "BenchSci login screen — please re-authenticate, then retry")
    return normalize_emet(raw)


def make_emet_handler(runner=None):
    """Return a 2-arg (contract, inputs) handler for ctx['emet_handler']."""
    def _handler(contract, inputs):
        return emet_handler(contract, inputs, runner=runner)
    return _handler


def _default_runner(inputs) -> dict:
    """LIVE path: ask Claude (with the emet-runner skill + Playwright) to drive EMET and return
    one envelope. Requires an interactive, logged-in BenchSci session. Injectable; not used in tests."""
    skill = (ROOT / _SKILL)
    prompt = (
        (skill.read_text(encoding="utf-8") if skill.exists() else "Drive EMET per emet_protocol.md.")
        + f"\n\n## QUERY INPUTS\n{json.dumps(inputs, indent=2)}\n\n"
        "Drive EMET via Playwright per the protocol. Public identifiers only. If a login screen "
        'appears, return exactly {"login_required": true}. Otherwise return ONLY the EMET envelope object.'
    )
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"emet runner (claude) exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    env = json.loads(proc.stdout)
    body = env.get("structured_output")
    if body is None:
        result = env.get("result", "")
        body = json.loads(result) if result else {}
    return body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_handler -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add sapphire-orchestrator/emet/handler.py sapphire-orchestrator/emet/tests/test_handler.py
git commit -m "A Task 2: EMET handler (harness seam) + make_emet_handler + login escalation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: The `emet-runner` skill doc (`.claude/skills/emet-runner/SKILL.md`)

**Files:**
- Create: `.claude/skills/emet-runner/SKILL.md`
- Test: `sapphire-orchestrator/emet/tests/test_skill_doc.py`

**Interfaces:**
- Consumes: nothing (a markdown skill doc + a lint test).
- Produces: the skill a Claude+Playwright session follows to drive EMET and return the envelope. The lint test asserts the file exists, has valid frontmatter (`name: emet-runner`, non-empty `description`), and contains the load-bearing protocol elements.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/emet/tests/test_skill_doc.py
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / ".claude" / "skills" / "emet-runner" / "SKILL.md"

class TestSkillDoc(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SKILL.exists(), f"missing {SKILL}")
        self.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_name_and_description(self):
        self.assertTrue(self.text.startswith("---"))
        head = self.text.split("---", 2)[1]
        self.assertIn("name: emet-runner", head)
        self.assertRegex(head, r"description:\s*\S+")

    def test_references_protocol_and_envelope(self):
        self.assertIn("emet_protocol.md", self.text)
        for key in ["candidate", "emet_workflow", "verdict", "evidence", "chat_url"]:
            self.assertIn(key, self.text)            # documents the envelope it returns

    def test_safety_rules_present(self):
        low = self.text.lower()
        self.assertIn("public identifier", low)       # public-IDs only
        self.assertIn("login", low)                   # login -> stop/escalate
        self.assertIn("login_required", self.text)    # the exact escalation signal the handler detects
        self.assertIn("tab", low)                     # tab discipline

    def test_mentions_workflows(self):
        for wf in ["Drug Safety", "Target Validation", "Pathway Analysis"]:
            self.assertIn(wf, self.text)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_skill_doc -v`
Expected: FAIL — SKILL.md missing.

- [ ] **Step 3: Write minimal implementation**

Create `.claude/skills/emet-runner/SKILL.md`:

```markdown
---
name: emet-runner
description: Drive EMET (BenchSci) live via the shared Playwright browser to answer one biomedical-evidence query and return a cited EMET envelope. Use when an agent (the EMET Analyst, a cascade gate/boost, or the orchestrator) needs published target-validation, drug-safety, pathway, or quantitative evidence on public identifiers. Wraps sapphire-cascade/emet_protocol.md; the single door to the EMET BEKG.
---

# emet-runner — drive EMET via Playwright

You are the **single door to EMET (BenchSci)**. Given one evidence query on **public identifiers only**
(gene symbol / protein / SMILES / disease term), drive the BEKG through the **shared Playwright browser**
and return one cited **EMET envelope**. The full operational protocol is
`sapphire-cascade/emet_protocol.md` — follow it exactly. This skill is the reusable, harness-callable
wrapper around it; when the EMET-MCP arrives it replaces the browser steps behind the same envelope.

## Inputs
A query object: `{candidate, workflow?, question}` — `candidate` is a public identifier; `workflow` is one
of the EMET workflows; `question` is the evidence ask. **Never** accept or transmit internal Quiver scores,
candidate ids, or functional traces — public identifiers only.

## Procedure (per `sapphire-cascade/emet_protocol.md`)
1. **Open a working tab** at `https://app.summit-prod.benchsci.com/` with `browser_tabs(action="new", ...)`.
   Confirm base tab 0 is still open. **Tab discipline:** open your own tab, work, close only your own tab;
   never leave the browser with zero tabs.
2. **If a login screen appears, STOP.** Do not attempt to log in. Return exactly `{"login_required": true}`
   so the harness escalates to the user for re-authentication.
3. Set **Thorough** mode (before attaching a workflow). Optionally select the matching **Workflow**:
   | Need | Workflow |
   |---|---|
   | safety / contraindication | Drug Safety |
   | target corroboration | Target Validation |
   | pathway / network | Pathway Analysis |
   | effect sizes | Quantitative Evidence |
   | prevalence / general | Database Q&A |
4. Type the query (**public identifiers only**), run it, and read every claim. **Cite each claim** with its
   PMID / source; uncited claims are dropped, not paraphrased. Tier EMET evidence **T2**.
5. **Close your tab**; verify base tab 0 remains.

## Output — the EMET envelope
Return ONLY this object:
```json
{
  "candidate": "GENE|PROTEIN|SMILES",
  "emet_workflow": "Drug Safety | Target Validation | Pathway Analysis | Quantitative Evidence | Database Q&A",
  "verdict": "no_go | flag | pass",
  "evidence": [{"claim": "...", "source": "Author, Venue Year", "id_or_url": "PMID/DOI/URL"}],
  "notes": "contradiction / thin-evidence flags",
  "chat_url": "https://app.summit-prod.benchsci.com/chat/<id>",
  "captured_at": "ISO-8601",
  "provenance": "emet-live"
}
```
The harness adapter normalizes this into cited T2 dossier facts. **EMET corroborates/gates — it never
issues a formal VETO** (that is the veto-class agents' job); a `no_go` is a cited contraindication.

## Rules
- Public identifiers only ever cross to EMET. Every claim cited (PMID/source) or dropped.
- Login screen → `{"login_required": true}`, never auto-login.
- One tab per query; always leave base tab 0 open.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_skill_doc -v`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/emet-runner/SKILL.md sapphire-orchestrator/emet/tests/test_skill_doc.py
git commit -m "A Task 3: emet-runner skill doc (Playwright EMET driver) + lint test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: End-to-end through the harness + wire the EMET Analyst spec

**Files:**
- Modify: `architecture/bucket1/scientific/emet-analyst.md` (add the "invoke emet-runner" procedure + provenance note)
- Test: `sapphire-orchestrator/emet/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: `harness.run`, `emet.handler.make_emet_handler`.
- Produces: proof that `harness.run("emet-runner", inputs, ctx={"emet_handler": make_emet_handler(fake)})` returns validated, `emet-live`-stamped findings, and that a login signal escalates through the harness.

- [ ] **Step 1: Write the failing test**

```python
# sapphire-orchestrator/emet/tests/test_end_to_end.py
import os
import tempfile
import unittest
from harness.runtime import run
from emet.handler import make_emet_handler

ENV = {"candidate": "SCN11A", "emet_workflow": "Target Validation", "verdict": "pass",
       "evidence": [{"claim": "GoF analgesia", "source": "X 2016", "id_or_url": "PMID:26243570"}],
       "notes": "", "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
       "captured_at": "2026-06-21T00:00:00Z", "provenance": "emet-live"}

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def test_emet_runner_through_harness_ok(self):
        ctx = {"emet_handler": make_emet_handler(runner=lambda inp: ENV)}
        r = run("emet-runner", {"candidate": "SCN11A", "workflow": "Target Validation"},
                engagement_id="eng_emet1", ctx=ctx)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.provenance, "emet-live")
        self.assertTrue(r.output["facts"])
        self.assertEqual(r.output["facts"][0]["tier"], "T2")

    def test_login_escalates_through_harness(self):
        ctx = {"emet_handler": make_emet_handler(runner=lambda inp: {"login_required": True})}
        r = run("emet-runner", {"candidate": "SCN11A"}, engagement_id="eng_emet2", ctx=ctx)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "escalated")
        self.assertEqual(r.error, "login-required")

    def test_internal_input_blocked_before_handler(self):
        called = {"n": 0}
        def runner(inp):
            called["n"] += 1
            return ENV
        ctx = {"emet_handler": make_emet_handler(runner=runner)}
        r = run("emet-runner", {"candidate": "SCN11A", "s_internal": 0.9},
                engagement_id="eng_emet3", ctx=ctx)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "guardrail-violation")
        self.assertEqual(called["n"], 0)    # data boundary blocked before EMET ran

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_end_to_end -v`
Expected: FAIL — `emet.tests.test_end_to_end` is new; it should actually PASS already if Tasks 1–3 are done (the harness + handler exist). If it fails, read the error: the most likely cause is the `emet-runner` contract's guardrails. Confirm `harness/agents.json`'s `emet-runner` lists `data_boundary` (for the third test) — it does. (No production code change expected in Step 3; this task's code change is the spec doc.)

- [ ] **Step 3: Write minimal implementation**

This task's only production change is documentation — wire the EMET Analyst spec to invoke the skill. Edit `architecture/bucket1/scientific/emet-analyst.md`: in the `## Procedure` section, change step 2 to reference the skill, and add a provenance line. Replace the existing Procedure step 2 line:

```
2. Run in **Thorough** mode; one tab per query; read and **cite** every claim (PMID / source).
```

with:

```
2. Run each query via the **`emet-runner` skill** (`.claude/skills/emet-runner/SKILL.md`) — the single,
   harness-callable Playwright driver: Thorough mode, one tab per query, cite every claim (PMID / source).
   The harness adapter normalizes the returned EMET envelope into cited **T2** dossier facts stamped
   `emet-live`; a login screen escalates (`login-required`) rather than guessing.
```

(If the end-to-end test already passed in Step 2, this doc edit is the whole deliverable — then re-run to confirm nothing regressed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sapphire-orchestrator && python -m unittest emet.tests.test_end_to_end -v`
Expected: PASS (3 tests OK).
Then the whole EMET + harness suite: `cd sapphire-orchestrator && python -m unittest discover -s emet/tests && python -m unittest discover -s harness/tests`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add architecture/bucket1/scientific/emet-analyst.md sapphire-orchestrator/emet/tests/test_end_to_end.py
git commit -m "A Task 4: EMET live end-to-end through the harness + wire EMET Analyst spec

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (§4):** the `emet-runner` skill doc → Task 3; wraps `emet_protocol.md`, public-IDs only, login→escalate, tab discipline, returns the §3.1 envelope. MCP-swappable interface (`make_emet_handler` + envelope) → Tasks 2/4. Adapter to harness `findings` → Task 1. Wire-in to `emet-analyst.md` + harness `emet-playwright` seam + `emet-live` stamping + memory (memory write is workstream C's job; the trace already records it) → Task 4. Dry/offline test mode (injectable runner) → Tasks 2/4.

**Placeholder scan:** No TBD/TODO; complete code/tests in every step. (Task 4 Step 2 notes the test may pass pre-edit because the harness already supports the seam — that is expected, not a placeholder; Step 3's doc edit is the deliverable.)

**Type consistency:** `normalize_emet(envelope) -> dict` (Task 1) consumed by `emet_handler` (Task 2). `make_emet_handler(runner)` returns the 2-arg `(contract, inputs)` callable the harness `dispatch_emet` requires (Task 2), used in Task 4's `ctx["emet_handler"]`. The adapter's output validates against `resolve("emet-runner").output_schema` (the `findings` schema) — asserted in Tasks 1 and 4. `HarnessEscalation("login-required")` (Task 2) surfaces as `AgentResult(status="escalated", error="login-required")` (Task 4), matching the D runtime's escalation path.

**Note for C (next workstream):** the self-improvement loop reads the trace row the harness writes for each `emet-runner` call (provenance `emet-live`) and writes the cited facts to memory.
