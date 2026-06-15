# HANDOFF — Sapphire Capability Map

Single-doc orientation for anyone (or any future Claude session) picking this up. Read this top-to-bottom
and you'll know what exists, why, and what's next. Everything referenced is in this repo unless linked out.

---

## 1. What this project is

In a 2026-06-11 strategy meeting ([full transcript + notes](meetings/2026-06-11-sapphire-strategy-james.md)),
James (Quiver leadership) handed Rohan a folder of work — ~59 exec personas, 299 Sapphire prompts, 399
prompt "pipelines," and a tool-frequency analysis — and asked that it be turned into a **capability map**:
for every kind of question a customer would ask Quiver's *Sapphire* discovery system, say what capability
is needed, which model/tool can do it today, how well, and where the gap is that Quiver should fill.

This repo is the execution of that ask, plus three deeper deliverables James/Rohan scoped: a full **model
landscape**, a scoped + scaffolded **expert agent**, and an **orchestration brief** for Hayes.

**Quiver context:** Quiver Bioscience runs *Sapphire*, a closed-loop CNS drug-discovery engine. Its moat is
unique functional data — electrophysiology (oEP) + CRISPR perturbations + drug perturbations + transcriptomics
— fused into a shared latent space, with a Neo4j knowledge graph (1.8M nodes / 17.9M edges), a ChromaDB
literature store (29k papers), and a "DrugReflector" rescuer-ranking model. External models/data are
*enrichment around* that moat, never the core.

---

## 2. James' design — the throughline

```
59 personas  ->  299 prompts  ->  399 pipelines  ->  tool-frequency ranking
   (who asks)    (what they ask)   (how to answer)    (what to integrate first)
        \_______________________________ ________________________________/
                                         v
              capability_map.xlsx  +  model_landscape.md  +  integration_map.md
              (which model fills each cell, and where the gaps are)
```

### The three-layer data vision (the strategic frame everything maps to)
1. **Internal (moat):** Quiver EP-CRISPR functional data — novel target signals (e.g. sodium targets for
   pain nobody else has seen).
2. **Context:** external data Quiver *can't* know — safety/contraindication, prevalence, competition — that
   gates go/no-go. *"Great pain target but causes cancer → no-go."*
3. **Predictivity / boosting:** independent corroboration (genetics, PPI, pathway, transcriptomic signatures)
   that *re-ranks* hits. *The #7 → #1 example: a target Quiver ranks #7 that independently shows up in an
   academic screen and interacts with the disease gene gets promoted to #1.*

---

## 3. What's in this repo

| Path | What it is |
|---|---|
| [`capability_map.xlsx`](capability_map.xlsx) | **The centerpiece.** 3 sheets: **Capabilities** (16 areas, the strategy view), **Prompts** (all 299 mapped to capability + disease area), **How to read** (legend). |
| [`model_landscape.md`](model_landscape.md) | The **supply side**: 3–6 candidate models/tools per capability (2023–26), each tagged maturity (`production`/`research`/`preprint`/`data-resource`) + honesty (`proven`/`paper-claim`). |
| [`integration_map.md`](integration_map.md) | Tool-frequency data re-cut into the Internal / Context / Predictivity layers + a build-priority order. |
| [`personas/`](personas/) | All 59 personas → clean markdown, foldered by archetype, + [`INDEX.md`](personas/INDEX.md). |
| [`expert-agent/`](expert-agent/) | CAP-15 build: [`PROPOSAL.md`](expert-agent/PROPOSAL.md) + a **runnable offline scaffold** (`python expert-agent/run.py "..."`). |
| [`orchestration_brief_hayes.md`](orchestration_brief_hayes.md) | 4 orchestration archetypes for Sapphire + a recommended re-ranking-cascade architecture. |
| [`meetings/`](meetings/) | The 2026-06-11 meeting transcript + structured notes (+ Granola link). |
| [`source/`](source/) | James' raw Feb-2026 corpus (personas, 299 + 100 prompts, 399 pipelines, tool-frequency PNGs, Quiver context docs). The inputs everything was built from. |
| [`specs/`](specs/) | The design spec the build followed. |
| `_build/` | Re-runnable conversion/build scripts (`convert_personas.py`, `build_xlsx.py`). |

**External (not vendored here):** the empirical model-evaluation work lives in the separate
**Q-Mammal repo → https://github.com/rohanaryagondi/Q-Mammal** (MAMMAL/Boltz/ConPLex evals; its
`RohanOnly/model_options_briefing.md` + `CLAUDE.md` are the source of every "tested" verdict below).

---

## 4. The 16 capability areas

| ID | Capability area | Layer | Status |
|---|---|---|---|
| CAP-01 | Functional similarity / embedding & clustering | Internal | Tested |
| CAP-02 | Target discovery & prioritization | Internal | Native |
| CAP-03 | Drug–target binding / DTI / ligandability | Internal+Pred | Tested |
| CAP-04 | ASO design & sequence generation | Internal | **Gap** |
| CAP-05 | Mechanism disambiguation | Internal | Native |
| CAP-06 | Genetics ↔ function integration | Predictivity | Untested |
| CAP-07 | BBB / PK-PD / druggability | Context | Tested |
| CAP-08 | Toxicity & safety prediction | Context | Tested |
| CAP-09 | Combination & network strategy | Internal | Native/Untested |
| CAP-10 | Biomarker & translational | Predictivity | Untested |
| CAP-11 | Variant→disease / prevalence / genetic epidemiology | Context | Untested |
| CAP-12 | Protein–protein interaction / pathway | Predictivity | Untested |
| CAP-13 | Competitive & commercial intelligence | Context | Untested |
| CAP-14 | Portfolio & capital allocation / financial optimization | Meta | Untested |
| CAP-15 | Expert judgment / strategic reasoning | Meta | **Gap** (scaffolded) |
| CAP-16 | AI self-reflection / uncertainty quantification | Meta | Partial/Native |

> Disease-specific prompt batches (monogenic, neuropsych, neurodegen, pain) are treated as *applications*
> of CAP-02/03/04/05, tagged via a disease column on the Prompts sheet — not as separate areas.
> CAP-11 and CAP-12 are James' *verbal* additions in the meeting; the 299-prompt corpus doesn't exercise
> them, which is itself a finding (a gap in the prompt set, not just the toolset).

---

## 5. Findings that matter

1. **The moat holds.** Quiver EP-CRISPR Atlas appears in 104/299 pipelines — 2× the next source (DrugBank 55).
   Everything external is enrichment.
2. **Foundation models are enrichment, not oracles.** On the hard internal task — single-target binder
   triage — MAMMAL and ConPLex are ≈ chance (Nav1.8 0.43 / 0.39); Boltz-2 is a split (mTOR AUROC 1.0,
   Nav1.8 0.71 marginal). The win is **Quiver-data fine-tunes** + the functional moat, not an off-the-shelf model.
3. **Half the capability areas are data/agent problems, not ML-model problems.** CAP-11/12/13/14 are solved
   by querying ClinVar/STRING/ClinicalTrials.gov/Evaluate with an LLM that aggregates + cites — never
   invents. This is the **Emit-overlap zone**.
4. **CAP-04 (ASO design) and CAP-15 (expert judgment) are the genuine build gaps** — no mature off-the-shelf
   solution. CAP-15 now has a scaffolded head start in `expert-agent/`.
5. **Recommended orchestration (for Hayes):** a **three-layer re-ranking cascade** — internal latent →
   context *gate* (subtractive/veto) → predictivity *boost* (additive/re-rank), with a calibrated
   uncertainty/abstention gate at the exit that *proposes the experiment* instead of guessing when
   confidence is low. This is the concrete form of James' #7→#1 demo, and what makes it "not Emit 2.0."

---

## 6. Empirical ground rules (Quiver culture — keep these)

- *"State-of-the-art on shit is still shit."* Paper benchmarks ≠ performance on Quiver targets.
- Status/verdict columns reflect **only** what the Q-Mammal eval established. Everything else is `Untested`
  or `Gap` — no invented model performance. Rows flagged `paper-claim` are candidates to test, not
  capabilities we have.
- **Never feed proprietary functional/EP/CRISPR data into an external model or service.** These tools are
  queried with public identifiers only (gene symbols, disease terms, SMILES, trial IDs).

---

## 7. Timeline & deliverables (from the meeting)

- **Tue (review week):** review the full capability table with James + Gavin.
- **Before Fri:** present the "master plan of all the models and what they can do."
- Parallel: James + Marty + Matt's "secret project" — rank haploinsufficiency CRISPR hits (125 of ~1500
  meaningful signatures) by commercial attractiveness using Claude.

---

## 8. How to keep building

- **Refine the table:** edit `_build/build_xlsx.py` (capability metadata = the `CAPS` list; prompt→capability
  rules = `cap_of()`), then `python _build/build_xlsx.py`.
- **Fill Status/Verdict** as new evals land — pull from the [Q-Mammal repo](https://github.com/rohanaryagondi/Q-Mammal).
- **Regenerate/add prompts:** load any `personas/` file as a system prompt and ask it what it would query
  Sapphire for — exactly how James generated the original 299.
- **Expert agent → Phase 1:** real ingestion (podcast transcription, live blog/RSS), embeddings, tuned
  abstain threshold, eval against held-out expert statements (see `expert-agent/PROPOSAL.md`).
- **Polish for presentation:** generate a Quiver-branded deck once content is locked (use the
  `quiver-branding` skill).

---

## 9. Open items / decisions pending

- **GenomicsDB layer membership** — confirm internal vs external (affects its layer in `integration_map.md`).
- **Per-prompt model mapping** — deliberately deferred; we deepened the 16 areas instead. Could extend the
  Prompts sheet with a candidate-model column if James wants the "100+ rows" literally.
- **Expert-agent legal review** — public-content-only, no impersonation of a named living person; emulate an
  archetype/role and cite sources (flagged in the proposal; worth a real legal check before ingesting).
