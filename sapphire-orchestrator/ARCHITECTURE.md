# Sapphire Orchestrator — Architecture

## 1. One router, four stages

```
                 ┌──────────────────────────────────────────────────────────┐
   user query ──►│  FRONT ROUTER / ORCHESTRATOR                              │
                 │  intent → convene panel → run pipeline → synthesize        │
                 └───┬──────────────────────────────────────────────────────┘
                     ▼
   ── EVIDENCE & COMPUTE TIER (facts) ─────────────────────────────────────
   ┌───────────────────────────┐   internal-first; EMET gates/boosts, never authors
   │ DISCOVER  (= cascade)      │   → ranked candidates + cited evidence; "#7" is defined here
   │  internal moat → L2 gate   │
   │  → L3 boost                │
   └───────┬───────────────────┘
           ▼  candidate(s) of interest
   ┌───────────────────────────┐   run a specialist model on the SPECIFIC pair/target
   │ VALIDATE  (Q-Models)       │   Boltz → binding, ADMET → tox, ion-channel FT → selectivity
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

## 2. Why this is not "Emit 2.0"

Inherited from the brief and the cascade: **internal data is the privileged substrate; external tools
form an envelope around it.** The orchestrator preserves that — Discover is internal-first, EMET only
gates/boosts — and adds two layers Emit structurally lacks: **on-demand specialist compute** (Q-Models)
and a **judgment panel** that argues over the evidence with explicit, dissenting viewpoints.

## 3. Persona auto-convening (router logic)

The router maps `(question type × disease area)` to a panel. Each lens is filled by the best-fit
archetype from [`../personas/`](../personas/):

| Lens | Picks from | Example (Nav1.8 pain) | Example (TSC2) |
|---|---|---|---|
| **scientific / translational** | Biotech CSO (disease-matched) | Xenon (ion channels) | Denali (CNS translational) |
| **commercial / competitive** | Pharma BD SVP | Lundbeck BD (CNS pain) | BioMarin BD (rare disease) |
| **investability** | Venture GP | RA Capital | Third Rock |
| **safety / regulatory** | Pharma neuroscience SVP / the [CAP-15 expert-agent](../expert-agent/) | Takeda Neuro | Takeda Neuro |

Default panel size 4 (one per lens); the router may add a second CSO for cross-disease questions or
drop investability for a pure internal-science query. Panel selection itself is part of the
transparent execution plan.

## 4. The persona verdict contract

Every panelist returns the same structured object so the router can compare and surface dissent:

```json
{"persona":"…","role":"…","lens":"scientific|commercial|investability|regulatory",
 "stance":"champion|conditional|skeptic|veto","conviction":1-5,
 "headline":"…","rationale":"… grounded, with citations …","top_risk":"…","ask":"…"}
```

**Grounding rule (enforced in the panelist prompt):** every factual claim must cite the Discover/
Validate evidence (PMIDs, genetics terms, Q-Models numbers). The persona owns *stance, priorities,
and the "ask"* — not the facts.

## 5. Synthesis

The router fuses the panel into: a single **recommendation**, the **consensus**, the **dissent**
(stance/conviction spread), the **convergent gate** (a risk multiple lenses independently raised), a
**proposed experiment**, and a **confidence** split (biology vs. feasibility). When the panel can't
converge or evidence is thin, it **abstains and proposes the resolving experiment** — same exit
discipline as the cascade.

## 6. Real vs. mock (demo)

| Box | Demo | Production |
|---|---|---|
| internal moat (Discover L1) | curated mock | real Quiver latent-space query |
| EMET (Discover L2/L3) | **live** (cascade, Playwright) | external **+ internal** data |
| Q-Models (Validate) | **mock**, shaped outputs | AWS GPU launches (`Q-Models/aws/*`) |
| persona panel (Consult) | **live** LLM agents on real persona files | same |

Nothing in the stage contracts changes between demo and production — only the substrate under each box.

## 7. Relation to sapphire-cascade

The cascade is the Discover+Validate engine (it already produces the #7→#1 ranked, evidence-backed
list). The orchestrator calls it, runs Q-Models on the top survivor, then runs the persona panel and
synthesis on top. Build the cascade once; the orchestrator is the layer that makes it conversational
and adds judgment.
