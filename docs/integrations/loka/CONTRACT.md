# LOKA ↔ Sapphire — Wire Contract & Render Mapping

*The concrete interface LOKA calls and how to render what comes back. Authoritative shape:
[`../../../sapphire-orchestrator/contracts/run_live_schema.md`](../../../sapphire-orchestrator/contracts/run_live_schema.md)
(the single source of truth — this doc references it, does not fork it). Plan: [`INTEGRATION_PLAN.md`](INTEGRATION_PLAN.md).*

---

## 1. The call

LOKA reaches Sapphire over **one HTTP call** to the already-shipped bridge (`serve.py`, K1):

```
GET  /api/run?q=<url-encoded query>
        # optional: &mode=canned  ($0 pre-captured scenario)  |  &mode=claude  (headless reconstruction)
        # default (no mode): the REAL harnessed firm, via=engine-live
```

- **Request:** the user's natural-language query as `q`. **Public identifiers only** in anything forwarded to
  external evidence (the firm enforces this internally; LOKA must not smuggle internal IDs into `q` expecting
  them to be safe downstream — see [`OPEN-QUESTIONS.md` Q1](OPEN-QUESTIONS.md)).
- **Response:** `application/json` — the documented `run_live` dict **plus** two HTTP stamps: `via`
  (`engine-live` default) and `live` (bool). `run_live` is designed **not to raise** — a down backend yields an
  honest abstain, not a 500.
- **Latency:** a real harnessed run is **slow** (multi-agent, possibly live EMET). Treat it as a batch job:
  show a `cl.Step` spinner; consider a client timeout ≥ a few minutes; there is **no token stream**.

A future `POST` variant (body: `{query, options}`) can be added additively if LOKA needs structured options;
not required for v1.

## 2. The response shape (top level)

From `run_live_schema.md` — **additive-only**, never rename/drop a key:

| Key | Type | Render priority |
|---|---|---|
| `query` | str | echo (header) |
| `plan` | object | optional — show as a collapsed "how the firm scoped this" step |
| `priors` | object | optional — recalled memory; low priority |
| `discover` | object | **primary** — the cited fact dossier (see §3) |
| `consult` | object | **primary** — `round1` (+ `round2` when present) partner verdicts (see §3) |
| `synthesize` | object | **primary** — `recommendation`, `confidence`, `proposed_experiment`, `entities` |
| `engagement_id` | str | footer — the trace key (`eng_…`); surface for auditability |
| `reflection` | object | optional — memory written; low priority |
| `_via` | str | always `"harness-live"` (engine marker) |
| `via` / `live` | str / bool | HTTP stamps — `via=engine-live`, `live=true` for a real run |

## 3. Render mapping (→ Chainlit elements)

Reuse LOKA's existing `_create_*_table` pattern (`src/agent/agent.py:146-340`).

### `discover.dossier` — the fact bucket
```
discover = { "dossier": [fact, …],
             "flags": {"VETO":[str], "DIVERGENCE":[str], "KNOWN_UNKNOWNS":[str]},
             "status": "complete" | "complete-with-known-unknowns",
             "agents": [{id, status, provenance}, …] }
```
Each **fact** carries `value, source, tier, provenance` and MAY carry `field, confidence, flag`.

| Field | Render as |
|---|---|
| dossier (list) | a `cl.Dataframe`: columns **value · field · tier · provenance · source · flag** |
| `tier` | chip — **T1** primary / **T2** secondary (color by tier) |
| `provenance` | chip — `moat-real`, `emet-live`, `aso-tox`, `gnomad`, `corpus`, … (verbatim; never relabel) |
| `flags.VETO` | a distinct **⛔ VETO** callout block (these are gates the roundtable adjudicates, not kills) |
| `flags.DIVERGENCE` | a **⚠ DIVERGENCE** block ("internal vs external — surfaced, not reconciled; often the alpha") |
| `flags.KNOWN_UNKNOWNS` | a muted "still-open" list |
| `agents` (abstained) | a small "who couldn't answer" note (honesty: show degraded agents, don't hide them) |

### `consult.round1` / `round2` — the roundtable (the spread is the product)
Each **verdict** carries `persona, stance, provenance, status`; success adds `conviction, rationale, fact_claims`;
abstain adds `lens`.

| Field | Render as |
|---|---|
| per verdict | a `cl.Step` or card titled **persona** |
| `stance` + `conviction` | headline (e.g. "Cautious · 0.6") — **do NOT collapse to a consensus** |
| `rationale` | body text |
| `fact_claims` | citations back into the dossier (personas never invent facts) |
| round1 → round2 | show as a **rebuttal progression** (round2 reacts to round1) when `round2` present |

### `synthesize`
`recommendation` (headline) · `confidence` (chip) · `proposed_experiment` (callout — hands off to the
Experiment-Design tool) · `entities` (tags). This is "the facts + how each player reacted," not a verdict.

## 4. Routing (when LOKA calls Sapphire vs. its own tools)

LOKA keeps its fast tools for simple lookups; route to Sapphire when the query is **deliberative / CNS-decision /
multi-source**. Suggested triggers:
- Explicit user affordance: a "Deep analysis (convene the firm)" toggle/button.
- Heuristic: questions asking for a *judgment/recommendation/risk* ("should we…", "is X a viable…", "what would
  regulators/payers think"), or that name a CNS program/target needing the dossier+roundtable.
- Default simple factual lookups (one gene/protein/pathway/perturbation match) → LOKA's existing tools.

Keep the routing **explicit and logged** so it can be tuned from usage; never silently swallow a complex query
into a single fast tool call.

## 5. Stability & versioning

- The contract is **additive-only** (`run_live_schema.md` §Stability). New keys are safe; LOKA must ignore
  unknown keys rather than break.
- Any change to the shape updates `run_live_schema.{md,py}` **together** and must keep the conformance tests green
  (`contracts/tests/test_run_live_schema.py`, `tests/test_serve_run_live.py::TestRealRunLiveConformsToContract`).
- LOKA should pin to "the run_live contract vX" in its bridge and assert `via`/`live` to know it hit the real path.
