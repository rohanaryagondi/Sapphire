# Sapphire — Consolidated Architecture

How the whole system fits together, end to end. Companion to the [docs hub](README.md) and
[`CLAUDE.md`](../CLAUDE.md). This is the single place to understand the moving parts and the seams.

---

## 1. The firm (control + two buckets)

Sapphire is modeled as a research firm. The **orchestrator** is the engine that enforces the process;
Claude is the reasoning at each box.

```
        ┌──────────────────────── CONTROL (Engagement Lead) ────────────────────────┐
 query ─▶ triage → scope → engagement plan (seat the panel, pick activated agents)    │
        └───────────────────────────────────┬────────────────────────────────────────┘
                                             ▼
        ┌──────────────── BUCKET 1 · FACTS (junior analysts) ────────────────┐
        │  Internal moat (MOCK)  ·  EMET (live)  ·  Q-Models  ·  13 semantic  │
        │  → cited fact DOSSIER; Research Manager runs completeness /          │
        │    contradiction / VETO / DIVERGENCE / KNOWN_UNKNOWN rules           │
        └───────────────────────────────────┬────────────────────────────────┘
                                             ▼
        ┌──────────────── BUCKET 2 · DELIBERATION (partners) ────────────────┐
        │  roundtable: independent verdicts → moderated rebuttal → SPREAD     │
        │  (company personas + institutional archetypes; no forced consensus) │
        └───────────────────────────────────┬────────────────────────────────┘
                                             ▼
                       SYNTHESIZE (Engagement Lead): facts + how each player reacted
```

Specs for every agent live in `architecture/` (control · bucket1/scientific · bucket1/semantic · bucket2).

---

## 2. Phase-5 plumbing (what makes the firm reliable, live, and self-improving)

Phase 5 added five layers *under* the firm. They share one set of contracts and run every agent through
one harness; an engagement wrapper threads the self-improvement loop around a run.

```
                         ┌─────────────────── contracts/ (P0) ───────────────────┐
                         │  jsonschema_min (validator) · provenance vocab ·        │
                         │  EMET-envelope + memory-record schemas                  │
                         └───────────┬───────────────────────────┬───────────────┘
                                     │ imported by               │ imported by
                    ┌────────────────▼─────────────┐   ┌─────────▼───────────────┐
   engagement.py    │        harness/  (D)         │   │  memory/ + selfimprove/ │
   (recall→trace→   │  run(agent_id, inputs)       │   │        (C)              │
    reflect)  ──────▶  declare→dispatch→validate→  │   │  write/recall/          │
        │            │  guard→stamp→TRACE           │   │  record_outcome ·       │
        │            │  dispatch by kind:           │   │  reflect · governance · │
        │            │   claude · qmodels · python ·│   │  authoring · metrics    │
        │            │   emet-playwright ───────────┼──▶│  (reads the TRACE)      │
        │            └──────────────┬───────────────┘   └─────────────────────────┘
        │                           │ emet seam
        │                  ┌────────▼─────────┐
        │                  │  emet/ (A)        │  ← .claude/skills/emet-runner (Playwright)
        │                  │  handler+adapter  │     live: emet.benchsci.com
        ▼                  └──────────────────┘
   scenarios/ (B): manifest (10-axis variety) + capture.py + 2 captured + 8 stubs
```

---

## 3. Shared contracts — `sapphire-orchestrator/contracts/`  (P0, 22 tests)
The single definitions every layer imports, so nothing drifts.
- `jsonschema_min.py` — a stdlib JSON-Schema validator (`validate(instance, schema, root) -> [errors]`)
  over the subset we use (type incl. list-of-types, required, properties, additionalProperties:false,
  enum, items, $ref). No third-party deps.
- `provenance.py` — the canonical provenance vocabulary (`emet-live`, `gpu-async`, `live-local`, `stub`,
  `memory-recall`, `synthesis`, … + `qmodels:<tool>`) and `is_valid_provenance`.
- `schemas.py` — `EMET_ENVELOPE_SCHEMA` (§3.1), `MEMORY_RECORD_SCHEMA` (§3.2), `MEMORY_RECORD_TYPES`.

## 4. The agent harness — `sapphire-orchestrator/harness/`  (D, 51 tests)
**One runtime every agent runs through.** The orchestrator decides *which* agents run; the harness
guarantees every output is well-formed, in-policy, provenanced, traced — or a fail-safe abstain/escalate.

`run(agent_id, inputs, *, engagement_id, ctx) -> AgentResult`:
1. **resolve** the contract from `agents.json` (unknown id → `unknown-agent`).
2. **idempotency** — cache on `inputs_hash` within an engagement.
3. **input guards** — `data_boundary` / `public_identifiers_only` BLOCK *before dispatch* (never strip).
4. **dispatch by kind** — `claude-subagent` (headless `claude -p --json-schema`) · `qmodels-delegate`
   (the real QModelsClient) · `python` (a deterministic step) · `emet-playwright` (the EMET seam).
5. **validate** output against its JSON schema; **bounded repair** loop on failure (re-prompt with the
   exact failing path).
6. **output guards** — `facts_only_cited` (+ veto-must-be-T1), `must_cite_dossier` (personas),
   `veto_is_gate`, `emet_tab_discipline`; then `stamp_provenance`.
7. **fail-safe** — on hard failure return a typed abstain envelope (slotted as `KNOWN_UNKNOWN`) or
   escalate; **never fabricate**.
8. **trace** — append one record to `RohanOnly/engagements/<id>/trace.jsonl` (the audit surface *and*
   the self-improvement loop's input).

Contracts live in `harness/agents.json` (per agent: id, role, `kind`, input/output schema, `tools_allowed`
— empty for personas, `guardrails`, `provenance_label`, `timeout_s`, `retry`).

## 5. Live EMET — `sapphire-orchestrator/emet/` + `.claude/skills/emet-runner/`  (A, 18 tests)
EMET (BenchSci) as a harness-callable agent.
- **Skill** (`emet-runner/SKILL.md`) — a Claude+Playwright session drives `emet.benchsci.com` per
  `sapphire-cascade/emet_protocol.md`, returns the raw **EMET envelope** (`candidate, emet_workflow,
  verdict, evidence[], notes, chat_url, captured_at, provenance`).
- **handler** (`handler.py`) — `make_emet_handler(runner)` is the `ctx["emet_handler"]` the harness
  `emet-playwright` dispatch calls; **MCP-swappable** (when the EMET-MCP lands, only the runner changes);
  login screen → `HarnessEscalation("login-required")`.
- **adapter** (`adapter.py`) — `normalize_emet(envelope)` → cited **T2** dossier facts. **EMET never
  emits a formal VETO** (a `no_go` is a cited contraindication; veto is the veto-class agents' T1 job).
- Live catalogue (9 workflows / 22 capabilities / ~70 sources) in `sapphire-cascade/emet_capabilities.md`.

## 6. Self-improvement loop — `memory/` + `selfimprove/`  (C, 34 tests)
- **memory/** — append-only, **public-identifiers-only** (every write runs the harness `data_boundary`
  and refuses internal Quiver data), schema-valid. `write` · `recall` (entity-overlap + recency) ·
  `record_outcome` (a *refuted* outcome opens a `moat_blindspot` linked to proposal+outcome) ·
  `rebuild_index`. Data under `RohanOnly/memory/` (env-overridable).
- **selfimprove/** — `governance.py` (the **tiered switch**: memory auto-applies; skills/specs/scenarios/
  routes gated to `proposed/` for human approval — flip flags in `governance.json` to go autonomous) ·
  `reflect.py` (post-engagement: trace → memory) · `authoring.py` (Tier-2 drafts to `proposed/`) ·
  `metrics.py` → `selfimprove/REPORT.md` (prediction accuracy, blind spots) · `cli.py` (`record-outcome`).

## 7. Integration — `engagement.py`  (B, 12 tests; integration verified live)
`run_engagement(sid_or_query)` wraps the existing `Orchestrator` **additively** (orchestrator.py
untouched): derive entities → `recall` priors (`run["priors"]`) → harness **trace** (open → a dossier
agent-row → close with synthesis carrying entities) → `reflect` to memory (`run["reflection"]`). This is
how the loop runs end-to-end on real engagements (verified: one run wrote 10 recallable records).
Scenario suite: `scenarios/manifest.json` (10 variety axes), `capture.py` (repeatable draft capture),
2 captured (`nav1_8`, `tsc2`) + 8 honest stubs.

---

## 8. Control vs data flow (end to end)
```
query
 └─ engagement.run_engagement
     ├─ extract_entities → memory.recall(entities)         # priors in (provenance: memory-recall)
     ├─ orchestrator.run(...)                               # triage→scope→plan
     │   ├─ Bucket-1: harness.run(emet-runner|q-models|…)   # facts, guard-checked, stamped, traced
     │   └─ Bucket-2: harness.run(company-partner …)        # verdicts (no tools, must-cite-dossier)
     ├─ synthesize                                          # recommendation + spread
     └─ reflect(engagement_id)                              # trace → memory (conclusions/facts/proposals)
                                                            #         (Tier-1 auto; gated authoring → proposed/)
later:  selfimprove record-outcome  → experiment_outcome (+ moat_blindspot if refuted) → next recall surfaces it
```

## 9. Provenance & honesty
Every rendered artifact carries a provenance label (`emet-live` · `qmodels:<tool>`/`live-local`/`gpu-*` ·
`memory-recall` · `persona-judgment` · `synthesis` · `stub`/`mock`). Nothing is silently mocked. **Still
mock/stub:** the internal moat (synthetic), 8 of 10 scenarios (honest `stub`, captured live — never
fabricated), some Q-Models tracks (`stub`/`eval` in the registry). The legacy engine still serves canned
evidence per agent-seam — the harness is proven and callable; the per-seam rewiring is Phase 6.

## 10. Safety model (enforced mechanically by the harness)
- **Data boundary:** internal scores / candidate IDs (`QS…`) / EP-CRISPR / functional traces can never
  reach EMET/web/Q-Models or memory — guards BLOCK before dispatch/write (key + value-side patterns).
- **Facts vs judgment:** personas get empty `tools_allowed` *and* `must_cite_dossier` (defense in depth).
- **Veto = gate:** a veto routes to `flags.VETO`, never a silent kill.
- **Self-modification gated:** the loop writes memory automatically but cannot change its own behavior
  (skills/specs/routes) without a human approving the `proposed/` draft.
- **Never fabricate:** every failure path is a typed abstain/escalate.

## 11. Test surface (~137 tests, stdlib only, offline)
`contracts` 22 · `harness` 51 · `emet` 18 · `memory` 14 · `selfimprove` 20 · top-level `tests` 12 (engagement
+ scenarios + capture). Run:
`cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove; do python -m unittest discover -s $s/tests; done && python -m unittest discover -s tests`

## 12. Extension points (Phase 6)
1. Rewire each orchestrator agent-seam through `harness.run` (replace canned evidence).
2. Capture the 8 stub scenarios live (`python _build/capture_scenario.py "<query>"`).
3. Wire remaining Q-Models `stub`/`eval` tracks; wire `qmodels_fn` into the live capture wrapper.
4. Swap the mock moat for the real Quiver latent space (a confirmed `moat_blindspot` is the labeled example).
5. Console: surface priors + the metrics report; optionally flip governance toward autonomous.
