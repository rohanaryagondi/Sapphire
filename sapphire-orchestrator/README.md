# Sapphire Orchestrator

A front-facing **router agent** that turns a single question into a four-stage pipeline:

```
 user ⇄ ROUTER  →  DISCOVER (EMET)  →  VALIDATE (Q-Models)  →  CONSULT (persona panel)  →  SYNTHESIZE
```

It **composes**, not replaces, the existing [`../sapphire-cascade/`](../sapphire-cascade/): the cascade
*is* Discover+Validate (internal moat → context **gate** → predictivity **boost**). The orchestrator
adds the two pieces the cascade didn't have — an **on-demand compute step (Q-Models)** and a
**persona-consult panel** — behind one conversational face.

> Realizes the architecture in [`../orchestration_brief_hayes.md`](../orchestration_brief_hayes.md)
> and the user's three-workflow vision (EMET · Q-Models · personas).
>
> **The four stages below are the happy-path view.** The full operating model — the two-bucket "firm"
> (junior analysts → partners), the agent roster, the iterate-until-complete fact loop, contradiction/
> veto/divergence handling, and the dossier "done" definition — lives in **[`AGENTS.md`](AGENTS.md)**
> and **[`dossier_schema.md`](dossier_schema.md)**. Start there.

## The four stages

| Stage | Subsystem | Produces | Demo fidelity |
|---|---|---|---|
| **Discover** | EMET (BenchSci) + internal moat | hypotheses + cited evidence; the ranked candidate list | EMET **live** in the cascade; moat **mock** |
| **Validate** | [Q-Models launchpad](qmodels/catalog.json) | quantitative predictions (Boltz binding, ADMET, ion-channel selectivity) on the specific pairs Discover surfaced | **mock** (no AWS yet; same I/O contract) |
| **Consult** | auto-convened roundtable — [company partners](agents/partners/company-partner-template.md) + [institutional partners](agents/partners/institutional/) | multi-viewpoint verdicts (scientific / commercial / investability / regulatory / payer / academic / adversarial), grounded in the dossier, dissent surfaced | persona deliberation is **live** (real LLM agents on the real persona files) |
| **Synthesize** | the [Engagement Lead](agents/control/engagement-lead.md) (+ [Research Manager](agents/control/research-manager.md), [Moderator](agents/control/roundtable-moderator.md)) | one recommendation + consensus/dissent + confidence + proposed experiment | — |

## Facts vs. judgment (the key design rule)

EMET and Q-Models produce **facts** (retrieved evidence, computed predictions). Personas produce
**opinions** (priorities, viewpoints) — and must ground every factual claim in the facts above. A
persona supplies *its lens*, never invented data. This dodges the documented "persona prompting
degrades accuracy" failure mode (see [`../expert-agent/PROPOSAL.md`](../expert-agent/PROPOSAL.md)).

## Auto-convening the panel

The router reads the question + disease area and convenes a 3–5 persona panel from the archetypes in
[`../personas/`](../personas/) — see the routing table in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Worked scenarios (real persona deliberation)

- [`scenarios/nav1_8.json`](scenarios/nav1_8.json) — Nav1.9 #7→#1; panel converges on **cardiac
  Nav1.5 selectivity** as the one gate.
- [`scenarios/tsc2.json`](scenarios/tsc2.json) — RHEB #7→#1; panel **reframes** it from a small
  molecule to an ASO/degrader genetic medicine.

Both panels are real persona-agent runs (4 personas each) grounded in the cascade's cited EMET
evidence + the Q-Models mock outputs.

## See it
The interactive visualization is the **Console** section of the site
([`../site/`](../site/)) — run `python -m http.server` there and open the Console tab.

## Demo vs. production
- **Now (demo):** EMET live (cascade), Q-Models mocked, personas live, internal moat mocked.
- **Later:** Q-Models → real AWS launches (same contract); internal moat → real Quiver latent space;
  EMET → external **+ internal** data once that lands. No contract changes — only the substrate under
  each box.
