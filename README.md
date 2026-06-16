# Sapphire Capability Map

Operationalizes James' Feb-2026 Sapphire prompt corpus the way he laid it out in the 2026-06-11
meeting: turn **persona -> prompt -> capability -> model/tool -> gap** into a living map of what
Sapphire must do, what can do it today, how well, and where Quiver should build.

> **New here? Read [`HANDOFF.md`](HANDOFF.md) first** — single-doc orientation to everything below.

## What's here

| File | What it is |
|---|---|
| [`capability_map.xlsx`](capability_map.xlsx) | The centerpiece. **Capabilities** sheet = 16 capability areas (strategy view); **Prompts** sheet = all 299 customer prompts mapped to a capability + disease area; **How to read** sheet = legend. |
| [`model_landscape.md`](model_landscape.md) | The **supply side**: 3-6 candidate models/tools per capability (2023-26), each with maturity + `proven`/`paper-claim` flag. The "find all the models" deliverable. |
| [`integration_map.md`](integration_map.md) | Tool/data-source frequency re-cut into James' Internal / Context / Predictivity layers, with a build-priority order. |
| [`personas/`](personas/) | All 59 personas as markdown (foldered by archetype) + [`INDEX.md`](personas/INDEX.md). The demand source - usable as agent system-personas or to regenerate prompts. |
| [`expert-agent/`](expert-agent/) | CAP-15 build: [`PROPOSAL.md`](expert-agent/PROPOSAL.md) (the "$50k expert from public posts" design) + a **runnable offline scaffold** (`python expert-agent/run.py "..."`). |
| [`orchestration_brief_hayes.md`](orchestration_brief_hayes.md) | Strategic brief for Hayes: 4 agentic-orchestration archetypes for Sapphire, grounded in the v3 stack, with a recommended re-ranking-cascade architecture. |
| [`sapphire-cascade/`](sapphire-cascade/) | **Runnable multi-agent realization of the orchestration brief** — the 3-layer re-ranking cascade (internal moat → context *gate* → predictivity *boost* → uncertainty/abstention) as a 5-agent panel that pulls live, cited evidence from **EMET (BenchSci)**. Two end-to-end **#7→#1** runs ([Nav1.8 pain](sapphire-cascade/scenarios/nav1_8_pain.md), [TSC2](sapphire-cascade/scenarios/tsc2.md)); see [`RUN_LOG.md`](sapphire-cascade/RUN_LOG.md). |
| [`sapphire-orchestrator/`](sapphire-orchestrator/) | **The front-facing agent vision**: one router → Discover (EMET) → Validate ([Q-Models](https://github.com/rohanaryagondi/Q-Models)) → Consult (auto-convened persona panel) → Synthesize. Composes the cascade and adds on-demand compute + a judgment panel. Two scenarios with **live persona deliberation** ([Nav1.8](sapphire-orchestrator/scenarios/nav1_8.json), [TSC2](sapphire-orchestrator/scenarios/tsc2.json)). |
| [`site/`](site/) | **Interactive localhost walkthrough** — methodology flow, the animated gate→boost system flow, the 3-layer data map, the 16-capability dashboard, and the **Console** (the orchestrator running live, four stages + persona panel). Run `python -m http.server` in that folder. |
| [`HANDOFF.md`](HANDOFF.md) | Comprehensive single-doc handoff — start here. |
| [`meetings/`](meetings/) | The 2026-06-11 strategy meeting transcript + structured notes (+ Granola link). |
| [`source/`](source/) | James' raw Feb-2026 corpus (59 personas, 299 + 100 prompts, 399 pipelines, tool-frequency PNGs, Quiver context docs) — the inputs everything was built from. |
| [`specs/`](specs/) | The design spec this was built from. |
| `_build/` | The conversion/build scripts (re-runnable). |

## The throughline (James' design)

```
59 personas  ->  299 prompts  ->  399 pipelines  ->  tool-frequency ranking
   (who asks)    (what they ask)   (how to answer)    (what to integrate first)
        \_______________________________ ________________________________/
                                         v
                         capability_map.xlsx  +  integration_map.md
              (which model fills each cell, and where the gaps are)
```

## The three findings that matter for Tuesday

1. **The moat holds, externals enrich.** Quiver EP-CRISPR Atlas is referenced in 104/299 pipelines -
   2x the next source. Every external tool is enrichment around it (see `integration_map.md`).
2. **Most capabilities are untested or gaps, not solved.** Only the binding/embedding/ADMET cluster
   (CAP-01/03/07/08) has empirical model verdicts - all from the Q-Mammal eval. The rest are native
   Quiver functions or genuinely open. The map marks these honestly; it does not invent performance.
3. **CAP-15 (expert judgment) is the headline build.** No off-the-shelf model. This is James' "$50k
   Pfizer expert from public posts" idea - the stock-sentiment-bot pattern applied to biology. The map
   flags it as a build, scoped separately.

## How to keep building it

- **More rows / refinement:** edit `_build/build_xlsx.py` (capability metadata is the `CAPS` list;
  prompt->capability rules are in `cap_of()`), then re-run:
  `python _build/build_xlsx.py`
- **Fill Status/Verdict** as new model evals land - pull verdicts from the Q-Mammal repo
  (`RohanOnly/model_options_briefing.md`, `CLAUDE.md`, `results/`).
- **Regenerate / add prompts:** load any persona from `personas/` as a system prompt and ask it what it
  would query Sapphire for - that's exactly how James generated the original 299.
- **Polish for presentation:** the working files are deliberately un-branded; generate a Quiver-branded
  deck/Word version once content is locked (use the `quiver-branding` skill).

## Source corpus

`C:\Users\rohan.gondi\Desktop\Sapphire\extracted\Sapphire Prompt Work_Feb 2026\` (James' folder) and
the Q-Mammal repo (https://github.com/rohanaryagondi/Q-Mammal) for empirical model verdicts.

## Open items

- **GenomicsDB layer membership** - confirm whether it's an internal Quiver store or external (affects its layer in `integration_map.md`).
- The expert-agent scaffold is a **runnable skeleton with a fictional sample corpus** - real ingestion (podcast transcription, live blog/RSS), embeddings, and a tuned abstain threshold are Phase-1 work (see `expert-agent/PROPOSAL.md`).
- `model_landscape.md` rows flagged `paper-claim` are **candidates to test, not capabilities we have** - they need an empirical pass on Quiver targets before promotion.

## Not done here (by design)

- A polished Quiver-branded deck (working files first; use the `quiver-branding` skill once content is locked).
- New model evaluations (the landscape records what exists + Q-Mammal's findings; it runs nothing new).
- Per-prompt model mapping on the Prompts sheet (we deepened the 16 areas instead).
