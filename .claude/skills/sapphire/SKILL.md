---
name: sapphire
description: Run the full Sapphire Orchestrator end-to-end on a question — the two-bucket "firm" (Engagement Lead → Bucket 1 fact dossier → Bucket 2 persona roundtable → synthesis). Use when asked to run Sapphire, answer a CNS target/diligence/trial question through the orchestrator, convene the persona panel, or produce a recommendation with consensus/dissent + a proposed experiment. For the evidence engine alone (internal→gate→boost ranking) use sapphire-cascade instead.
---

# Sapphire Orchestrator — end-to-end driver

Runs the firm defined in `sapphire-orchestrator/AGENTS.md`. The control flow, dossier rules, panel
seating, and synthesis are the engine in `sapphire-orchestrator/orchestrator.py`; this skill is the
**conversational front face** that drives it and fills the live seams (EMET, personas) for a real query.

## Two ways to run

**A. A shipped scenario (deterministic, fast):** `nav1_8` or `tsc2`.
```
python sapphire-orchestrator/run.py nav1_8        # full run: plan → dossier → roundtable → synthesis
python sapphire-orchestrator/run.py "free text"   # routes to a scenario, or prints a live plan
```
Use this for a reproducible demo. It prints exactly what the site Console animates.

**B. A novel query (live):** drive the four stages yourself, using the engine for the deterministic
control logic and live agents for the facts/judgment:

1. **PLAN (engine).** `from orchestrator import ENGINE; ENGINE.plan_only(query)` → the engagement plan
   (deliverable, scoped dossier fields, activated agents, seated panel). Show it first.
2. **DISCOVER (live).** Run the evidence engine via the **`sapphire-cascade`** skill (internal moat →
   EMET gate → EMET boost) over the real query — public identifiers only — to get the ranked candidate
   + cited EMET facts. Slot them into the dossier per `dossier_schema.md`; mark VETO / DIVERGENCE /
   KNOWN-UNKNOWN exactly as the Research Manager rules require.
3. **VALIDATE (mock today).** Apply the Q-Models contract from `qmodels/catalog.json` to the top
   candidate (binding / selectivity / ADMET). Label outputs MOCK (prod = AWS launch, same contract).
4. **CONSULT (live).** Seat the panel from the plan. Dispatch **one subagent per partner**, each
   loading its persona file from `personas/` (via `agents/partners/company-partner-template.md`) +
   the institutional archetypes in `agents/partners/institutional/`. Round 1: independent verdict
   objects (the verdict contract). Round 2: show each the others' verdicts → revise/hold with reason.
   Always seat the Red-Team. Partners cite the dossier; never invent facts (route fact-requests back).
5. **SYNTHESIZE (you, as Engagement Lead).** Recommendation + consensus + dissent + the convergent
   gate + a proposed experiment + a confidence split (biology vs feasibility). No forced consensus.

## Hard rules (from CLAUDE.md — non-negotiable)
- **Data boundary:** internal EP/CRISPR data + scores never leave to EMET / web / Q-Models. Public
  identifiers only.
- **Facts vs judgment:** Bucket 1 = cited facts; Bucket 2 = opinions grounded in those facts.
- **Surface, don't bury:** VETO gates and internal↔external DIVERGENCE always appear in the output.
- **Abstain honestly:** thin/contradictory evidence → abstain and propose the resolving experiment.
- **Label fidelity:** EMET live, personas live, Q-Models MOCK, internal moat MOCK.

## After a live run
If the query is reusable, capture it as a new `scenarios/<id>.json` (same shape as nav1_8/tsc2:
discover/validate/panel/facts/rebuttal/synthesize), add the id to `SCENARIOS` in `orchestrator.py`,
and run `python _build/build_orch_data.py` so the site Console picks it up.
```
