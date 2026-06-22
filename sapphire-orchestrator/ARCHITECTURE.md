# Sapphire Orchestrator — Architecture

> For the consolidated end-to-end architecture see [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
> This file covers the orchestrator-specific two-execution-path design and the agent dispatch model.

## 1. Two execution paths

The orchestrator supports two modes of running the full firm pipeline:

| | **Canned path** — `orchestrator.run(sid)` | **Live harnessed path** — `live_engine.run_live(query)` |
|---|---|---|
| Evidence | pre-captured scenario JSON (`scenarios/*.json`) | dispatched live: each agent via `harness.run` |
| Agents | logic only (facts are authored) | **every agent + persona actually dispatched** |
| Moat | captured facts | **real moat DB, live** |
| Cost | $0, instant, deterministic | real backends cost tokens/time (mockable for $0 verification) |
| Used by | `run.py`, `serve.py`/Console | the harnessed live firm (verified offline; **not yet wired to front door**) |

**Keystone remaining task:** route `serve.py`/Console through `run_live` so any user question runs the full harnessed firm.

## 2. One router, four stages

```
                 ┌──────────────────────────────────────────────────────────┐
   user query ──►│  FRONT ROUTER / ORCHESTRATOR                              │
                 │  intent → convene panel → run pipeline → synthesize        │
                 └───┬──────────────────────────────────────────────────────┘
                     ▼
   ── EVIDENCE & COMPUTE TIER (facts) ─────────────────────────────────────
   ┌───────────────────────────┐   internal-first; EMET gates/boosts, never authors
   │ DISCOVER  (= cascade)      │   → ranked candidates + cited evidence
   │  internal moat → REAL      │   (Loka CNS_DFP SQLite, moat-real)
   │  → EMET live (Playwright)  │
   └───────┬───────────────────┘
           ▼  candidate(s) of interest
   ┌───────────────────────────┐   run a specialist model on the SPECIFIC pair/target
   │ VALIDATE  (Q-Models)       │   Boltz → binding, ADMET → tox, ion-channel FT → selectivity
   │ ASO tox (aso-tox agent)    │   fires when ASO sequences present (Hongkang's GBR model)
   └───────┬───────────────────┘
           ▼  evidence + computed predictions
   ── JUDGMENT TIER (opinions, grounded in the facts above) ────────────────
   ┌───────────────────────────┐   auto-convened 3–5 persona panel
   │ CONSULT  (persona panel)   │   scientific · commercial · investability · regulatory
   │  grounded verdicts + dissent│
   └───────┬───────────────────┘
           ▼
   ┌───────────────────────────┐
   │ SYNTHESIZE (router)        │   recommendation + consensus/dissent + confidence
   │                            │   + the convergent proposed experiment
   └────────────────────────────┘
```

## 3. The agent harness (22-agent registry)

Every agent + persona is dispatched through `harness/` — `run(agent_id, inputs, *, engagement_id, ctx)`:
- resolves contract from `agents.json` (22 agents)
- enforces input guardrails (`data_boundary`)
- dispatches by kind: `claude-subagent` · `qmodels-delegate` · `python` · `emet-playwright`
- validates output schema; bounded repair loop
- enforces output guardrails (`facts_only_cited`, `must_cite_dossier`, `veto_is_gate`)
- stamps provenance; writes trace record to `RohanOnly/engagements/<id>/trace.jsonl`
- fail-safe: abstain/escalate on hard failure — never fabricates

## 4. Persona auto-convening (router logic)

The router maps `(question type × disease area)` to a panel. Each lens is filled by the best-fit
archetype from [`../personas/`](../personas/):

| Lens | Picks from | Example (Nav1.8 pain) | Example (TSC2) |
|---|---|---|---|
| **scientific / translational** | Biotech CSO (disease-matched) | Xenon (ion channels) | Denali (CNS translational) |
| **commercial / competitive** | Pharma BD SVP | Lundbeck BD (CNS pain) | BioMarin BD (rare disease) |
| **investability** | Venture GP | RA Capital | Third Rock |
| **safety / regulatory** | Pharma neuroscience SVP / the [CAP-15 expert-agent](../expert-agent/) | Takeda Neuro | Takeda Neuro |

Default panel size 4 (one per lens); router may add a second CSO for cross-disease questions or drop investability for a pure internal-science query.

## 5. The persona verdict contract

Every panelist returns the same structured object so the router can compare and surface dissent:

```json
{"persona":"…","role":"…","lens":"scientific|commercial|investability|regulatory",
 "stance":"champion|conditional|skeptic|veto","conviction":1-5,
 "headline":"…","rationale":"… grounded, with citations …","top_risk":"…","ask":"…"}
```

**Grounding rule (harness-enforced):** every factual claim must cite the Discover/Validate evidence (PMIDs, genetics terms, Q-Models numbers). The persona owns *stance, priorities, and the "ask"* — not the facts.

## 6. Synthesis

The router fuses the panel into: a single **recommendation**, the **consensus**, the **dissent**
(stance/conviction spread), the **convergent gate** (a risk multiple lenses independently raised), a
**proposed experiment**, and a **confidence** split (biology vs. feasibility). When the panel can't
converge or evidence is thin, it **abstains and proposes the resolving experiment**.

## 7. Real vs. mock (current state)

| Box | Status |
|---|---|
| internal moat (Discover L1) | **REAL** — Loka CNS_DFP SQLite, `moat-real` provenance |
| EMET (Discover L2/L3) | **live** — Playwright on emet.benchsci.com, real cited PMIDs |
| Q-Models (Validate) | CPU tracks live-local; GPU **dry-run** (no real GPU eval run yet) |
| ASO tox | **live** — Hongkang's GBR model, scikit-learn==1.8.0 in subprocess |
| persona panel (Consult) | **live** LLM agents (verified offline; mocked for $0 verification) |
| run_live front door | **NOT yet wired** — serve.py/Console still use canned path |

## 8. Transparency

```bash
python trace_view.py <engagement_id>    # agent-by-agent timeline: kind · status · provenance · output
python trace_view.py <engagement_id> --full   # include full output payloads
```

Sample trace in `docs/sample-trace.txt`.

## 9. Relation to sapphire-cascade

The cascade is the Discover+Validate engine (it already produces the ranked, evidence-backed list).
The orchestrator calls it, runs Q-Models + aso-tox on the top survivor(s), then runs the persona panel
and synthesis on top. Build the cascade once; the orchestrator is the layer that makes it conversational
and adds judgment.
