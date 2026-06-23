# Task Brief — Quantitative-fact seams (hard numbers alongside EMET)

**Owner: `hayes`** · Tier: **Feature** (ships as several Standard-tier PRs) · Assigned 2026-06-23.
This brief is self-contained: it is everything your Claude needs to build this correctly. Read it fully, then
follow `dev/CONTRIBUTOR_RULES.md` and `dev/METHODOLOGY.md`. When stuck, use `dev/HELP.md` (don't guess on the
harness/contracts — ask).

---

## Goal
Give Sapphire's Bucket 1 a set of **structured quantitative fact sources** that EMET (an LLM knowledge source)
can only paraphrase. EMET tells us *what the literature says*; these seams return *the actual number* — genetic
constraint, tissue expression, protein domains, enrichment statistics. Each is a Bucket-1 fact agent built in
the **exact pattern of the existing `aso-tox` seam**, emitting cited, provenance-stamped facts that complement
EMET's narrative (and let the Research Manager flag number-vs-narrative `DIVERGENCE`).

**This is a feed/integration task — not science.** You are wrapping public REST/GraphQL APIs as fact seams.
Do not invent scoring; report what the API returns.

## Scope — exactly four seams, in this order (clean public APIs, no keys)
| # | Seam id | Source | Endpoint (public, no key) | The fact it emits |
|---|---|---|---|---|
| 1 (pilot) | `gnomad-constraint` | gnomAD | GraphQL `https://gnomad.broadinstitute.org/api` | gene LoF-intolerance: pLI, LOEUF, mis-z |
| 2 | `gtex-expression` | GTEx | REST `https://gtexportal.org/api/v2/` | tissue expression (median TPM); CNS selectivity |
| 3 | `interpro-domains` | InterPro (EBI) | REST `https://www.ebi.ac.uk/interpro/api/` | protein domain/family annotations |
| 4 | `geneset-enrichment` | g:Profiler | REST `https://biit.cs.ut.ee/gprofiler/api/gost/profile/` | top enriched GO/pathway terms for a gene set |

**Out of scope** (do NOT build): DepMap, AlphaMissense, Foldseek (bulk-data / job-based — a later batch); the
ToolUniverse runtime/MCP/embedding model (we reimplement a handful of wrappers as our own seams, we do NOT
adopt the system); Slurm/HPC (we don't use it); any EMET change.

## Sequencing — pilot-gate (mandatory)
1. **PR-A: `gnomad-constraint` only.** ✅ **MERGED (PR #6, 2026-06-23).** Approved + Gate-5 verified.
2. **PR-B, C, D:** each remaining seam as its own Standard-tier PR, reusing the merged pilot as the template.
One seam per PR; small PRs, full gates each. **Next: GTEx (PR-B).**

> **✅ Use `sapphire-orchestrator/tools/gnomad_constraint_seam.py` as your template** — copy its `_fetch`
> network-boundary indirection, the `findings()` structure, the three honest-degradation branches
> (no-target / not-found-honest-empty / backend-error-envelope), and the `_build_fact` / `_num` helpers
> (`_num` guards against bool-as-number). Copy the gnomAD `agents.json` block (schema lists `error`;
> `additionalProperties:false`; includes `data_boundary`). Two refinements the pilot review surfaced — apply
> to every new seam:
> - **Version the source label.** Don't hard-code a dataset version in the provenance `source` string unless
>   the query pins it. Either pin the dataset/release in the request, or use a version-agnostic label + a
>   `# version: <X> at authoring` comment (gnomAD used `"gnomAD v4 constraint (GraphQL)"` — fine, but the
>   query doesn't pin v4; just be deliberate).
> - **No silent field drift.** If you fetch a metric, surface it in the fact (or comment why you omit it).
>   The pilot omits gnomAD's `syn_z` (not used in the fact) — that's fine, just don't leave it ambiguous.

---

## Read first (the pattern you are copying)
- `tools/aso_tox/` + `sapphire-orchestrator/tools/aso_tox_seam.py` — **the seam pattern.** Note: `predict_findings(inputs) -> dict` returns `{"candidate", "facts": [...], "provenance": "...", "invalid_sequences": [...]}`; honest-empty when no input; never raises.
- `sapphire-orchestrator/harness/agents.json` — the `aso-tox` entry. **Copy its shape.** Note the `output_schema` lists EVERY field the seam can emit with `additionalProperties:false` (see the lesson below).
- `sapphire-orchestrator/live_engine.py` — the `_BUCKET1_AGENTS` list and, inside `run_live`, the block that wires `ctx["python_fns"]["aso-tox"] = aso_tox_seam.predict_findings` (search for `python_fns` to find it — currently ~line 185-190). You add your agent id to the list + the **same kind of** wiring block. Note: aso-tox's entry point is named `predict_findings`; **your seam's entry point is `findings()`** (see the template), so your wiring call is `<name>_seam.findings`.
- `sapphire-orchestrator/contracts/provenance.py` — the allowed provenance-label set. You add new labels.
- `sapphire-orchestrator/tests/test_live_engine.py` — the offline-mock `ctx` pattern + the aso-tox tests (`TestAsoSequenceWiring`). Copy this test approach.
- `dev/CONVENTIONS.md` (§2 stdlib-only, §3 data-honesty/provenance/data-boundary, §6 tests) and `dev/GATES.md`.

## ⚠️ The two lessons from aso-tox (do not repeat these)
1. **Schema completeness.** The harness validates each agent's output against its `output_schema`, which has
   `additionalProperties:false`. If your seam ever returns a field not in the schema (e.g. `error`, or an extra
   data field), the harness **silently rejects the output → the agent abstains → your facts are dropped.** So
   the schema must list `candidate`, `facts`, `provenance`, `error`, and any extra field you emit. Prove facts
   land **through `run_live`**, not just via a unit test on the seam.
2. **Gate 5 is non-negotiable.** "A unit test passed" ≠ "it works." You must show a fact with your provenance
   landing in `discover["dossier"]` from a real `run_live(...)` call.

---

## The seam template (build each seam exactly like this)

**1. Seam module — `sapphire-orchestrator/tools/<name>_seam.py` (stdlib ONLY: `urllib.request`, `json`).**
```python
"""<name>_seam.py — stdlib-only Sapphire seam for <SOURCE>.
Public identifiers only leave Quiver (CONVENTIONS §3). Provenance: <label>.
API contract reference: ToolUniverse's <tool>.py (Apache-2.0) — reimplemented, not vendored.
"""
from __future__ import annotations
import json, urllib.request, urllib.error

_ENDPOINT = "https://..."
_TIMEOUT = 30

def _fetch(payload_or_url):
    """Single HTTP indirection so tests can monkeypatch the network at the seam boundary."""
    # urllib GET or POST; return parsed JSON. Raise on transport error (caller catches).
    ...

def findings(inputs: dict) -> dict:
    target = inputs.get("candidate") or inputs.get("target") or ""
    if not target:
        return {"candidate": target, "facts": [], "provenance": "<label>"}
    try:
        raw = _fetch(...)            # public identifier only (gene symbol / UniProt acc / gene list)
    except Exception as exc:         # degrade honestly — NEVER raise into the engine
        return {"candidate": target, "facts": [], "error": str(exc), "provenance": "<label>"}
    facts = [ {"value": "<human-readable number+unit>", "source": "<SOURCE> (<accessor>)", "tier": "T2"} ]
    return {"candidate": target, "facts": facts, "provenance": "<label>"}
```
- Honest-empty when no target; honest error envelope on failure; never raise.
- Facts: `value` (the number, with units + interpretation), `source`, `tier`. Tier measured/curated data
  **T1/T2** (higher than LLM narrative). Mark predictions as predictions in `value` text.

**2. Provenance — add the label to `contracts/provenance.py`** (`gnomad`, `gtex`, `interpro`, `gprofiler`).

**3. Harness agent — add to `harness/agents.json`** (copy the `aso-tox` block):
- `id`, `kind: "python"`, `provenance_label`, `guardrails: ["facts_only_cited", "stamp_provenance", "data_boundary"]`
  — **note:** the aso-tox agent you're copying has only `["facts_only_cited", "stamp_provenance"]` (its sequences arrive pre-validated via an internal channel). **Your seams take gene symbols/IDs straight from the query and call public APIs, so they MUST add `data_boundary`** — don't drop it when copying the aso-tox block.
  `timeout_s`, `output_schema` with `properties` = `candidate, facts(items: value/source/tier[/flag/provenance]), provenance, error` and `additionalProperties:false`, `required: ["candidate","facts"]`.

**4. Engine wiring — `live_engine.py`:** add the id to `_BUCKET1_AGENTS`, and add a wiring block mirroring aso-tox:
```python
if "<name>" not in ctx["python_fns"]:
    ctx["python_fns"]["<name>"] = <name>_seam.findings
```
(Import the seam at top, like `from tools import aso_tox_seam`.) The agent fires when a target gene/identifier
is present in `bucket1_inputs` — same gating shape as aso-tox firing on sequences.

**5. Tests — offline/$0:**
- `tests/test_<name>_seam.py`: monkeypatch `_fetch` to return a recorded fixture payload; assert the seam parses
  it into the right fact(s); assert honest-empty (no target) and error path (no raise).
- Extend `tests/test_live_engine.py`: with `_fetch` patched, call `run_live("... <gene> ...", ctx=<offline mocks>)`
  and assert ≥1 fact with your provenance lands in `discover["dossier"]` AND the agent status is `ok`.
- One clearly-`skipTest`-guarded live integration test may hit the real public API ($0) — skip cleanly if offline.

---

## Worked example — the pilot (`gnomad-constraint`)
- **Endpoint:** POST GraphQL to `https://gnomad.broadinstitute.org/api`.
- **Query:** `{ gene(gene_symbol: "TSC2", reference_genome: GRCh38) { gnomad_constraint { pli oe_lof oe_lof_upper mis_z syn_z } } }`
  (LOEUF = `oe_lof_upper`). Send `{"query": "...", "variables": {...}}` as JSON via `urllib.request.Request(..., method="POST")` with `Content-Type: application/json`.
- **Parse:** `data.gene.gnomad_constraint` → `pli`, `oe_lof_upper` (LOEUF), `mis_z`. Handle `null` (gene not found / no constraint) → honest-empty.
- **Fact (example):** `{"value": "TSC2 gnomAD constraint: pLI 0.99, LOEUF 0.21 (loss-of-function intolerant)", "source": "gnomAD v4 constraint (GraphQL)", "tier": "T1"}` — provenance `gnomad`.
- Interpretation guidance in the value text: pLI ≥ 0.9 or LOEUF < 0.35 → "LoF-intolerant"; else state the values plainly. Don't over-claim.

## Definition of Done (per seam)
- [ ] Stdlib-only seam (`urllib`+`json`); no third-party import in the engine path (Gate 4 grep).
- [ ] Provenance label added to `contracts/provenance.py`; harness agent + complete `output_schema`; wired into `_BUCKET1_AGENTS` + `python_fns`.
- [ ] Sends **public identifiers only**; `data_boundary` guardrail on the agent; no internal IDs (`QS\d+`) leave.
- [ ] Honest-empty (no target) + honest error (API down) — never raises, never fabricates a number.
- [ ] Offline tests green; full suite green.
- [ ] **Gate 5:** a fact with your provenance shown landing in `discover["dossier"]` via a real `run_live(...)`.
- [ ] PR uses the template, fills the gate-evidence checklist; report in `dev/reports/hayes/<seam>-report.md`.

## Definition of Done (whole task)
- [ ] All four seams merged (gnomAD pilot first, then the rest, one PR each).
- [ ] `status/tools.md` updated to list the new live quantitative sources with provenance + tier.
- [ ] Workboard rows moved to `merged` as each lands; ledger entries written by the approver at merge.
