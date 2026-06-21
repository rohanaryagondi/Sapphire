# Sapphire Phase 5 — Design Spec
### Live EMET · Science Scenario Suite · Self-Improvement Loop · Agent Harness

**Date:** 2026-06-21 · **Branch:** `Rohan` · **Status:** design (approved in brainstorming; pending spec review)

---

## 1. Overview & goals

Phase 5 turns Sapphire from "runs end-to-end on canned evidence" into a system that **gathers real
literature evidence live, demonstrates breadth across ~10 science-geared scenarios, runs every agent
through one reliable harness, and gets measurably better over time.**

Four workstreams, built **in parallel** behind a small set of **shared contracts** settled first:

- **A — Live EMET via a Playwright skill.** Extract EMET (BenchSci) out of the cascade into a dedicated,
  reusable `emet-runner` skill the orchestrator's EMET Analyst invokes — behind an interface the coming
  EMET-MCP drops into unchanged.
- **B — Science scenario suite.** ~10 highly varied scenarios, **science-geared (≈8 science / ≈2 business)**,
  captured through the real EMET skill + Q-Models.
- **C — Self-improvement loop.** A professional, well-instrumented memory + active-learning system: Sapphire
  writes durable scientific memory, recalls it on new engagements, tracks proposed-experiment outcomes to
  fix the moat's blind spots, and drafts new skills/specs for recurring uses — improving every run.
- **D — Agent harness.** One runtime every agent runs through (declare → dispatch → validate → guard →
  stamp → trace), so the ~25 agents reliably do what we want them to do.

**Primary user is the scientist.** The business lenses stay first-class in Bucket 2, but scenario coverage,
memory, and the learning loop are oriented to scientific decisions (targets, selectivity, safety,
mechanism, translatability).

## 2. Non-goals (this phase)

- The internal moat stays **MOCK** (swap is a separate workstream; the loop is built so the swap is a
  drop-in at the recall/active-learning seam).
- The EMET-MCP itself is not built here — only the swappable interface it will satisfy.
- **Persona/model calibration** (learning signal #3) is **deferred**: calibration records are written now
  so it can be switched on later with no backfill, but no calibration scoring is surfaced this phase.
- Governance starts **tiered** (memory auto, behavior-change gated). Fully-autonomous mode is built as a
  config switch but left off.

---

## 3. Shared contracts (settle first — every workstream touches these)

Even building in parallel, three interfaces are pinned on day one so the tracks don't collide.

### 3.1 EMET result envelope (also the future MCP interface)
Reuse the existing `sapphire-cascade/emet_protocol.md` JSON contract and extend it. This **is** the shape
the EMET-MCP will return, so `emet-runner` (Playwright) and the MCP are interchangeable behind one call.

```json
{
  "candidate": "GENE_SYMBOL | PROTEIN | SMILES",
  "emet_workflow": "Drug Safety | Target Validation | Pathway Analysis | Quantitative Evidence | Database Q&A",
  "verdict": "no_go | flag | pass",
  "evidence": [ {"claim": "...", "source": "Author/Title, Venue Year", "id_or_url": "PMID/DOI/URL"} ],
  "notes": "contradiction / thin-evidence flags",
  "chat_url": "https://app.summit-prod.benchsci.com/chat/<id>",
  "captured_at": "ISO-8601",
  "provenance": "emet-live | emet-mcp"
}
```

### 3.2 Memory record schema (shared by the loop, recall, and the trace reader)
Append-only JSONL + a JSON index. Mirrors the existing global-memory pattern and the `qmodels` registry
idiom. Public-identifier-only guard enforced on write.

```json
{
  "id": "mem_<8hex>",
  "type": "fact | conclusion | experiment_proposal | experiment_outcome | divergence | persona_verdict | calibration | moat_blindspot",
  "engagement_id": "eng_<8hex>",
  "ts": "ISO-8601",
  "entities": {"genes": ["SCN11A"], "smiles": ["..."], "diseases": ["neuropathic pain"], "drugs": []},
  "payload": { "...type-specific..." },
  "provenance": "emet-live | qmodels:* | persona-judgment | synthesis | memory-recall",
  "tier": "T1|T2|T3|T4",
  "confidence": "high|med|low",
  "links": ["mem_..."],            // e.g. an outcome links to its proposal
  "supersedes": "mem_... | null"   // append-only correction, never in-place mutation
}
```

### 3.3 Provenance vocabulary (extend the existing set)
Existing: `live-local`, `gpu-async`, `gpu-disabled`, `stub`, `unavailable`, `mock`. **Add:** `emet-live`,
`emet-mcp`, `memory-recall`, `persona-judgment`, `synthesis`. Every artifact the Console renders carries one.

---

## 4. Workstream A — Live EMET via a Playwright skill (`emet-runner`)

**Decision (from brainstorming):** a **skill doc wrapping the existing protocol**, not a Python driver
(throwaway once the MCP lands) and not left inline in the cascade (not reusable by the EMET Analyst).

- **New skill:** `.claude/skills/emet-runner/SKILL.md` — wraps `sapphire-cascade/emet_protocol.md`. Input:
  a batch of literature questions on **public identifiers only**. Output: the §3.1 envelope per question.
- **Interface (MCP-swappable):** callers invoke a stable `emet.query(workflow, candidate, question)` shape.
  Today the body drives the shared Playwright browser via the MCP Playwright tools; when the EMET-MCP
  arrives, only the skill body changes — every caller and the output envelope stay identical.
- **Auth:** manual — user logs into BenchSci first; on a login screen the skill **stops and asks for
  re-auth** (never automates login, never stores credentials). Surfaced as the harness `login-required`
  escalation.
- **Tab discipline:** new tab → work → close own tab; base tab 0 always open (from `emet_protocol.md`).
- **Wire-in:** `architecture/bucket1/scientific/emet-analyst.md` gets an explicit "invoke `emet-runner`"
  procedure; the harness registers it as `kind: emet-playwright` with guardrails `public_identifiers_only`,
  `emet_tab_discipline`, `citation_required`. Every result is stamped `emet-live` and written to memory.

**Testing:** a dry/mock mode returns a canned envelope (no browser) for offline tests; a live smoke runs
one Target-Validation query on a known gene and asserts the envelope validates + a `chat_url` is captured.

---

## 5. Workstream B — Science scenario suite (~10, highly varied)

Captured through the **real** EMET skill + Q-Models where computable (moat stays mock). Stored as
`sapphire-orchestrator/scenarios/<id>.json` in the existing schema. A coverage checklist guarantees each
variety axis is hit. Target mix: **8 science / 2 business.**

| # | Scenario | Disease area | Primary variety axis | Lens highlights |
|---|---|---|---|---|
| 1 | Nav1.8 (SCN10A) non-opioid analgesic | Pain | Go/no-go target validation + **paralog selectivity** | scientific, safety |
| 2 | SCN2A epilepsy — GoF vs LoF | Epilepsy | **Mechanism direction** (inhibitor vs activator by variant) | scientific |
| 3 | KCNT1 developmental epileptic encephalopathy | Rare CNS channelopathy | **Rare disease + selectivity**, thin trial landscape | scientific |
| 4 | C9orf72 ALS | ALS | **Modality choice** (ASO vs small molecule) | scientific, commercial |
| 5 | LRRK2 Parkinson's kinase inhibitor | Parkinson's | **ADMET / peripheral safety** (lung) | scientific, regulatory |
| 6 | GBA1 Parkinson's / Gaucher | Parkinson's | **CNS exposure / BBB penetration** + biomarker | scientific |
| 7 | Novel Alzheimer's target (thin evidence) | Alzheimer's | **ABSTAIN** → proposed experiment | scientific, adversarial |
| 8 | Internal-vs-literature signal | (channelopathy) | **DIVERGENCE** (moat sees what literature can't) | scientific |
| 9 | Rare CNS therapy value story | Rare CNS | **Payer / commercial** | commercial, payer |
| 10 | Competitor-IP / prior-CRL gate | (cross-cutting) | **VETO gate** (IP + FDA memory) | regulatory, IP |

Coverage axes guaranteed: go/no-go · selectivity · mechanism · modality · ADMET/BBB · biomarker · abstain ·
divergence · payer · IP/veto. (#1 already exists as `nav1_8.json`; it is re-captured through live EMET.)

**Build approach:** a small `_build/capture_scenario.py` helper that, given a query, drives the engine +
`emet-runner` + Q-Models and writes a draft `scenarios/<id>.json` for human curation (so capture is
repeatable, not hand-authored). **Testing:** every scenario must `python run.py <id>` cleanly and pass a
schema check; the suite test asserts all 10 axes are represented.

---

## 6. Workstream C — Self-improvement loop (detailed)

The loop is the part the user wants **maximally built out**. It has six components, wired as a
**post-engagement `reflect` step** plus a **pre-engagement `recall` step**, all reading the harness trace
and writing the §3.2 memory store. Governed by a tiered policy that can later flip to autonomous.

### 6.1 Memory store — `sapphire-orchestrator/memory/`
- `store.jsonl` — append-only records (§3.2). **Never mutated in place;** corrections append with
  `supersedes`.
- `index.json` — inverted index `entity → [record ids]` (genes, canonical SMILES, diseases, drugs) +
  `proposal → outcome` link table. Rebuildable from `store.jsonl`.
- `memory.py` — `write(record)`, `recall(entities, types, k)`, `record_outcome(proposal_id, outcome)`,
  `rebuild_index()`. Stdlib only.
- **Guard on write:** the harness `data_boundary` / `public_identifiers_only` check runs on every record;
  internal Quiver traces can never enter memory. Tier-1 **auto** (per governance).

**Record types written every engagement (auto):** `conclusion` (the synthesis recommendation + confidence),
`fact` (reusable cited dossier rows, EMET/Q-Models provenance), `experiment_proposal` (the abstention/
synthesis experiment, with the blind spot it targets), `divergence` (internal-vs-literature), and
`persona_verdict` + `calibration` stubs (written now, scored later).

### 6.2 Recall — pre-engagement (learning signal #2: reuse / retrieval)
At engagement start, after scope, the orchestrator calls `memory.recall(scope.entities, ...)`:
1. **Retrieve** prior records for the scope's genes/SMILES/diseases.
2. **Rank** by entity match × recency × tier.
3. **Age & flag:** a prior `conclusion` older than a freshness window, or contradicted by new evidence, is
   injected **flagged for re-validation** (not trusted blindly). Fresh, high-tier reusable `fact`s can
   short-circuit a re-fetch (with a recorded `memory-recall` provenance and a re-validation policy the
   Research Manager controls).
4. **Inject** as `provenance: memory-recall` dossier rows: *"Prior engagement eng_X concluded SCN11A is
   the panel's only SAFE class; proposed experiment E was [outcome]."* The Research Manager treats recalled
   conclusions as priors to confirm/contradict, never as settled facts.

### 6.3 Active-learning spine — (learning signal #1, the scientific core)
This is what makes the **model** get better, not just the cache.
- Every `experiment_proposal` is recorded with: hypothesis, what it would resolve, and **the specific moat
  blind spot it targets** (e.g. *"the moat under-detected Nav1.9's persistent current"*).
- **Outcome ingest:** `record_outcome(proposal_id, {result: confirmed|refuted|partial, data, source})` —
  a CLI (`python -m memory record-outcome ...`) and a `serve.py` endpoint let the user / wet-lab feed real
  results back. The outcome links to its proposal.
- **Predicted-vs-actual surfacing:** on the next engagement touching that entity, recall surfaces
  *"we predicted X → outcome was Y."* When prediction and outcome **diverge**, the loop writes a
  `moat_blindspot` record that the **Internal Science Lead** reads on subsequent runs to adjust its
  hypothesis — closing the active-learning loop (and the natural seam where the real moat plugs in: a
  confirmed blind spot becomes a labeled example to update the latent space).
- **Improvement is measurable** (§6.6), so "gets better" is a tracked number, not a claim.

### 6.4 Gated authoring — Tier-2 (new skills/specs/scenarios for recurring uses)
The loop drafts new behavior into a **review queue**; nothing applies until approved.
- **Triggers (from the trace):** (a) a query route with **no scenario**, seen ≥ N times; (b) a recurring
  `fact_request` the dossier cannot answer → suggests a **new agent/source**; (c) a new EMET workflow
  pattern used repeatedly → suggests a **new skill** or an `emet-runner` workflow preset.
- **Output:** a proposal artifact in `sapphire-orchestrator/proposed/` — a drafted skill doc, agent spec,
  scenario, or route — each with a **rationale + trace evidence** (which engagements motivated it).
- **Review CLI:** `python -m selfimprove review` lists proposals; approve → the artifact is moved into
  place (`.claude/skills/`, `architecture/`, `scenarios/`, or the route table) and the action is logged.

### 6.5 Governance switch — `sapphire-orchestrator/selfimprove/governance.json`
```json
{ "level": "tiered",
  "auto_apply": { "memory": true, "skills": false, "specs": false, "scenarios": false, "routes": false },
  "freshness_days": 90,
  "authoring_trigger_count": 3 }
```
"Move to fully-autonomous later" = flip the `auto_apply` flags (and/or `level: "autonomous"`); no rewrite.
The `reflect` step consults this policy before applying anything.

### 6.6 Improvement metrics — making "gets better" concrete
`selfimprove/metrics.py` computes, from the trace + memory, a rolling report (`selfimprove/REPORT.md`):
- **Recall hit-rate** — % of engagements where a useful prior was surfaced.
- **Re-fetch avoided** — EMET/Q-Models calls saved by reuse.
- **Abstention trend** — abstain rate over time (should fall as memory fills).
- **Prediction accuracy** — confirmed vs refuted on proposals that have outcomes.
- **Divergence resolution** — DIVERGENCEs later confirmed by an outcome (the alpha, validated).
- **Blind-spots found / fixed** — `moat_blindspot` records opened vs resolved.

### 6.7 The `reflect` step (post-engagement, ties it together)
After `synthesize`, the loop:
1. reads the engagement trace (`RohanOnly/engagements/<id>/trace.jsonl`);
2. extracts + **writes** memory records (Tier-1 auto, guarded);
3. runs **authoring triggers** → emits Tier-2 proposals to `proposed/`;
4. updates `index.json` and the metrics report.
It is read-only on the harness and write-only on memory/proposals — a clean, testable unit.

**Testing the loop:** a **two-run sequence** — run A writes a conclusion + proposal; run B on the same
entity asserts recall injects it. Plus: `record_outcome` → next run surfaces predicted-vs-actual; a
governance test asserts a `skills` proposal is **not** auto-applied while `auto_apply.skills=false`; memory
round-trip + index-rebuild unit tests; a `data_boundary` test asserting an internal id is refused on write.

---

## 7. Workstream D — Agent harness

*(Designed in full by the parallel harness agent; summarized here, with the complete component spec in
Appendix A.)*

One runtime every agent runs through — **declare → dispatch → validate → guard → stamp → trace** — so the
~25 agents conform to their contracts, stay in policy, and fail safe. Three clean layers: the
**orchestrator** owns deterministic control flow (unchanged); the **harness** (`sapphire-orchestrator/
harness/`) owns dispatch + contract enforcement; **agents** own reasoning (their `architecture/*.md` spec
is the system prompt).

Highlights (full detail in Appendix A):
- **One registry** `harness/agents.json` (mirrors `qmodels/registry.json`): per-agent id, role, `kind`
  (`claude-subagent` / `emet-playwright` / `qmodels-delegate` / `python`), input/output JSON schema,
  `tools_allowed`, named `guardrails`, `provenance_label`, `timeout_s`, `retry`.
- **Single entry point** `harness.run(agent_id, inputs, *, engagement_id, ctx) -> AgentResult`, generalizing
  `serve.py`'s existing `claude -p --json-schema` headless call.
- **Contract enforcement:** stdlib JSON-schema validation + a **bounded repair loop** (re-prompt with the
  exact failing path); **idempotency** via `inputs_hash`; **fail-safe** — on hard failure, return a typed
  **abstain** envelope (slotted as `KNOWN_UNKNOWN`) or **escalate**, **never fabricate**.
- **Guardrails enforced mechanically** (the CLAUDE.md hard rules): `data_boundary` /
  `public_identifiers_only` (block, never silently strip), `facts_only` + `citation_required`,
  `must_cite_dossier` + empty `tools_allowed` for personas (facts-vs-judgment, defense in depth),
  `veto_is_gate`, `stamp_provenance`.
- **Observability:** append-only `RohanOnly/engagements/<id>/trace.jsonl` (reuses the `_ledger_append`
  idiom) — the audit surface **and** the self-improvement loop's input.
- **Integration is surgical:** `orchestrator.py` calls `harness.run` at each provider seam (control logic
  untouched, injectable `harness=` for tests); `serve.py`'s bespoke dispatch is replaced and its schemas
  lifted into `agents.json#/schemas`; `qmodels/client.py` unchanged (`qmodels-delegate`).
- **Stdlib-only, tested offline** with mock backends (happy path, schema-violation+repair, guardrail block,
  persona fact-invention, idempotency, escalation, schema parity).

---

## 8. Cross-cutting

### 8.1 End-to-end data flow
```
query
 └─ recall memory (signal #2)               [C]
 └─ plan / scope                            [orchestrator]
 └─ Bucket-1 dossier via harness.run(...)   [D] → EMET-live [A] + Q-Models + moat-mock + recalled priors
 └─ Bucket-2 roundtable via harness.run(...)[D] → personas (no-tools, must-cite-dossier)
 └─ synthesize                              [orchestrator]
 └─ reflect: write memory + proposals + metrics  [C], reading the trace [D]
```

### 8.2 Build sequencing
All four workstreams proceed **in parallel**, gated only by **§3 shared contracts**, which are written and
frozen first (day-one task). The harness `agents.json#/schemas` and the memory `§3.2` schema and the EMET
`§3.1` envelope are the three things every track depends on; once pinned, A/B/C/D are independent.

### 8.3 Risks & mitigations
- **EMET brittleness (UI drift / login).** → MCP-swappable interface; `login-required` escalation;
  dry/mock mode for offline tests.
- **Memory poisoning (a wrong conclusion recalled forever).** → append-only + `supersedes`; recalled
  conclusions are **priors flagged for re-validation**, never settled facts; outcomes can refute them.
- **Self-modification drift.** → tiered governance; behavior-change is gated to a human-reviewed queue;
  the autonomous switch stays off until explicitly flipped.
- **Schema duplication (serve.py vs harness).** → schemas lifted into one place (`agents.json#/schemas`),
  with a parity test against `scenarios/nav1_8.json`.

---

## 9. File manifest

**New**
- `.claude/skills/emet-runner/SKILL.md` — the EMET Playwright skill (A)
- `_build/capture_scenario.py` — repeatable scenario capture (B)
- `sapphire-orchestrator/scenarios/<9 new>.json` — the suite (B)
- `sapphire-orchestrator/memory/{store.jsonl,index.json,memory.py}` — memory store + API (C)
- `sapphire-orchestrator/selfimprove/{reflect.py,authoring.py,metrics.py,governance.json,REPORT.md}` — loop (C)
- `sapphire-orchestrator/proposed/` — Tier-2 review queue (C)
- `sapphire-orchestrator/harness/{__init__,runtime,contracts,dispatch,jsonschema_min,guardrails,errors,trace,repair}.py` + `agents.json` + `tests/` (D)
- `RohanOnly/engagements/<id>/trace.jsonl` — per-engagement traces (D)

**Changed (surgical)**
- `sapphire-orchestrator/orchestrator.py` — call `harness.run` at provider seams; `recall` pre-step;
  `reflect` post-step; injectable `harness=`.
- `sapphire-orchestrator/serve.py` — dispatch via harness; lift `RUN_SCHEMA`/`FOLLOWUP_SCHEMA` into `agents.json`.
- `architecture/bucket1/scientific/emet-analyst.md` — invoke `emet-runner`.
- `.claude/skills/sapphire/SKILL.md` — dispatch via `harness.run`; run `recall`/`reflect`.
- `CLAUDE.md` — Phase 5 status; provenance vocab; map additions.

---

## Appendix A — Agent Harness (full component spec)

The Sapphire **agent harness** is the single runtime through which every agent — the 3 control agents, the
3 scientific-core fact agents, the 13 semantic fact agents, the Bucket-2 personas, the EMET-runner, and the
self-improvement components — is invoked. Today these are dispatched ad-hoc by the `/sapphire` skill driver
and by `serve.py`'s single `_run_live()` call. The harness replaces that with one disciplined call path:
**declare → dispatch → validate → guard → stamp → trace**. It is the reliable plumbing *around* Claude
subagents; it does not re-implement their reasoning. Stdlib-only (`json`, `subprocess`, `urllib`,
`hashlib`, `pathlib`), reusing the `claude -p ... --json-schema` pattern from `serve.py`, the
provenance-stamping + `normalize()` pattern from `qmodels/adapters.py`, the registry pattern from
`qmodels/registry.json`, and the append-only JSONL ledger pattern from `qmodels/launcher.py`.

### A.1 Responsibilities & boundaries
| Layer | Owns |
|---|---|
| **Orchestrator** (`orchestrator.py`) | Deterministic control flow: triage → scope → `_activated_agents()` → seat_panel → Bucket-1 slotting (VETO/DIVERGENCE/KNOWN_UNKNOWN) → two-round spread → synthesis. Decides which agents run; never talks to a model directly. |
| **Harness** (`harness/`) | Dispatch + contract enforcement: resolve contract, build the subagent call, invoke Claude headless (or EMET/Q-Models substrate), JSON-schema-validate, run guardrails, stamp provenance, retry/repair, fail safe, write the trace. Decides no strategy; guarantees every output is well-formed, in-policy, provenanced. |
| **Agent** | Reasoning only — reads inputs, follows its `Procedure`, emits its `Output (contract)`. The `architecture/**/*.md` spec is its system prompt. |

### A.2 Agent contract — `harness/agents.json`
One registry, one entry per callable agent, mirroring `qmodels/registry.json`; each `spec` field points to
the `.md` so prose stays canonical. Fields: `id`, `role`, `spec`, `kind`
(`claude-subagent | emet-playwright | qmodels-delegate | python`), `input_schema`, `output_schema`,
`tools_allowed` (the `claude -p --allowedTools` allow-list; empty for personas), `guardrails` (named
checks), `provenance_label`, `veto_class`, `timeout_s`, `retry` (`{max_repair, on_hard_fail: abstain|escalate}`).
Shared `#/schemas` lift `serve.py`'s `RUN_SCHEMA`/`FOLLOWUP_SCHEMA` and the verdict contract so there is one
definition. Worked entries: `fda-institutional-memory` (veto-class, T1-for-veto), `emet-runner`
(emet-playwright, login-required→escalate), `company-partner` (no tools, must-cite-dossier),
`q-models-runner` (qmodels-delegate, no model call).

### A.3 Dispatch — `harness.run`
```python
def run(agent_id, inputs, *, engagement_id, ctx=None) -> AgentResult: ...
@dataclass
class AgentResult:
    agent_id: str; ok: bool; output: dict; provenance: str
    status: str            # "ok" | "abstained" | "escalated"
    error: str | None; meta: dict   # {inputs_hash, latency_ms, repairs, guardrails_run, model}
```
Dispatch by `kind`: **claude-subagent** = `spec.md` system prompt + rendered inputs, called via
`claude -p --output-format json --json-schema <output_schema> --allowedTools <tools>` (parse
`env["structured_output"]` as `serve.py` does; single-call structured output preferred); **emet-playwright**
= the EMET-runner skill wrapped with tab-discipline + login detection; **qmodels-delegate** =
`QModelsClient.call` directly (already provenance-stamped); **python** = a deterministic orchestrator step,
harnessed for the trace.

### A.4 Contract enforcement
Stdlib JSON-schema check (`harness/jsonschema_min.py`: `type/required/properties/additionalProperties:false/
enum/items/$ref`). On malformed/invalid output, a **bounded repair loop** re-prompts ≤ `max_repair` times
with the prior output + the exact failing path (e.g. `discover.dossier[2].tier: required missing`).
**Idempotency:** `inputs_hash = sha256(agent_id + canonical_json(inputs))` keys the trace + an in-engagement
cache. **Hard failure never fabricates:** return `ok=False` with `abstain` (typed `{abstained, reason,
would_need}` → slotted `KNOWN_UNKNOWN`) or `escalate` (surfaced to the human, run pauses).

### A.5 Guardrails (CLAUDE.md hard rules, mechanical) — `harness/guardrails.py`
| Guardrail | Where | Action |
|---|---|---|
| `data_boundary` / `public_identifiers_only` | pre-dispatch, inputs leaving Quiver | scan for internal-score keys / candidate-id regex / `s_internal` / EP-CRISPR fields; **block** on hit (never strip-and-proceed); allow gene symbols, SMILES, disease terms, drug/trial ids |
| `facts_only` / `citation_required` / `tier_T1_for_veto` | post-output, Bucket-1 | every fact needs `source`+`tier`; uncited dropped; a `veto` needs `tier=T1` or it downgrades to precedent |
| `veto_is_gate` | post-output, veto-class | VETO routes to `flags.VETO`; no code path may drop the candidate |
| `opinions_only_no_new_facts` / `must_cite_dossier` | post-output, personas | each claim must anchor to a `ctx["dossier"]` field id; unanchored → re-emitted as a `fact_request`. Defense-in-depth with empty `tools_allowed` |
| `stamp_provenance` | post-output, all | write `provenance_label` on the result + each row; nothing leaves unstamped |
| `emet_tab_discipline` | around EMET | new tab → work → close own tab; base tab 0 open |

### A.6 Observability — `harness/trace.py`
Append-only `RohanOnly/engagements/<id>/trace.jsonl` (reuses `_ledger_append`). One record per `run`:
`{ts, engagement_id, agent_id, kind, inputs_hash, status, provenance, latency_ms, repairs, guardrails_run,
guardrail_results, output_digest, output, model}`. Bracketed by `engagement_open` (query/plan/scope) and
`engagement_close` (spread/synthesis). Inputs stored as **hash + redacted summary** (the boundary forbids
raw internal data from leaving). This trace is the audit surface **and** the self-improvement loop's input.

### A.7 Error taxonomy — `harness/errors.py`
`malformed-output` (→ abstain/escalate after repairs), `guardrail-violation` (block/reject, record redacted
path), `timeout` (one retry if idempotent else abstain; mirrors `serve.py` `TimeoutExpired`→plan-only),
`tool-failure` (surface into repair once, else abstain that field), `login-required` (escalate immediately,
never auto-login/fabricate), `budget` (honor `SafetyRefusal`/cap from `launcher.py`; `gpu-disabled`+abstain),
`unknown-agent` (hard control error). Unifying rule: a failure becomes an honest abstain/escalate the
orchestrator already slots — never a fabricated fact.

### A.8 Integration (surgical)
`orchestrator.py`: call `harness.run(agent_id, inputs, engagement_id=…)` at each provider seam; `bucket1/
bucket2/validate/synthesize` keep their slotting/spread logic, consuming `AgentResult.output`; add injectable
`harness=`. `serve.py`: replace `_run_live`/`_follow_up` subprocess blocks with harness calls; move schemas
into `agents.json#/schemas`; `_stamp`/`_provenance_for` subsumed by `stamp_provenance`. `sapphire` skill:
"dispatch subagent" steps become `harness.run`. `emet-runner`: registered `emet-playwright`. `qmodels/
client.py`: **no change** (`qmodels-delegate`). Self-improvement loop: **reads** the trace only.

### A.9 File layout — `sapphire-orchestrator/harness/`
`__init__.py` (exports `run`, `AgentResult`, `load_registry`) · `agents.json` (registry + `#/schemas`) ·
`runtime.py` (`run` — the single entry point) · `contracts.py` (`Contract`, `AgentResult`, `resolve`,
`inputs_hash`) · `dispatch.py` (per-`kind` backends) · `jsonschema_min.py` (stdlib validator → failing
paths) · `guardrails.py` (named checks) · `errors.py` (codes + envelopes) · `trace.py` (append-only JSONL) ·
`repair.py` (repair-prompt builder) · `tests/test_harness.py`.

### A.10 Testing (offline, stdlib `unittest`, mock backends)
(1) happy path: stamped, one trace record, `repairs=0`; (2) schema violation → repair once → `repairs=1`;
non-correcting variant → `abstained` + envelope; (3) guardrail-tripping input **blocked pre-dispatch**
(backend call count 0, nothing leaked); (4) persona fact-invention → `fact_request`; (5) idempotency →
backend invoked once, second from cache; (6) EMET `login-required` → escalation (no abstain-and-continue);
(7) schema parity: `agents.json#/schemas/run` validates `scenarios/nav1_8.json` and matches `serve.py`'s
`RUN_SCHEMA`.
