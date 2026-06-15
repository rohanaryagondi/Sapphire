# Sapphire Capability Map — Design Spec

**Date:** 2026-06-15
**Owner:** Rohan Gondi
**Audience for deliverables:** James + Gavin (Tuesday review), building toward the
"master plan of all the models and what they can do" by next Friday.

## Goal

Operationalize James' Feb-2026 Sapphire prompt corpus the way he intended: turn the
persona → prompt → pipeline → tool-frequency chain into a living **capability map** that
says, for every kind of question a customer would ask Sapphire: *what capability is needed,
which model/tool can do it today, how well (empirically), and where the gap is that Quiver
should fill* (curated corpus / expert agent / fine-tune on Quiver data).

## Inputs (what we extract from the messy folder)

- **299 prompts** — `Sapphire_Pipeline_Master_Checklist.md` (~25 categories). The demand side.
- **399 pipelines** — structured per-prompt decompositions (inputs, tools, sub-prompts, outputs).
  Used to source which tools each capability calls.
- **Tool-frequency analysis** — `Sapphire_Tool_Frequency_Analysis.png` (+ Common-Nodes version).
  The prioritized external-integration ranking.
- **59 personas** — Biotech CSO (15), Pharma SVP (12), Pharma BD SVP (12), EC Venture GP (10),
  WC Venture GP (10) + Neuro Persona List. The demand source.
- **Quiver context** — marketecture / Sapphire v3 docs (Neo4j 1.8M nodes/17.9M edges, ChromaDB
  29k papers, multimodal encoder, DrugReflector, 3-tier query). Ground truth on the real system.
- **Q-Mammal repo** — supply-side seed (`RohanOnly/model_options_briefing.md`) + empirical
  tested-status verdicts (`CLAUDE.md`, `results/`). Cross-referenced by link, not copied.

## Deliverables

All under `C:\Users\rohan.gondi\Desktop\Sapphire\sapphire-capability-map\`.

### 1. `capability_map.xlsx` — the centerpiece (two sheets)

**Sheet 1 — `Capabilities` (~16 rows, the strategy view):** one row per capability *area*.
Columns:

| Col | Meaning |
|---|---|
| ID | CAP-01 … |
| Capability area | the underlying technical capability |
| Description | one line |
| Representative prompts | prompt IDs from the 299 |
| Layer | Internal / Context / Predictivity / Meta (James' 3-layer frame) |
| Quiver data needed | EP-CRISPR Atlas / V1-T / none |
| Key external data·tools | from frequency analysis |
| Candidate model(s)/tool(s) | supply side |
| Status | tested / scaffolded / untested / gap |
| Empirical verdict | finding + Q-Mammal link where we have one |
| Gap → build? | curated corpus / expert agent / Quiver fine-tune / — |
| Notes |

**Sheet 2 — `Prompts` (299 rows, the backing detail):** prompt ID, text, original category,
mapped capability ID, disease area, pipeline-doc reference. Lets any area drill down to its prompts.

### 2. `personas/` — 59 markdown files

Foldered by archetype mirroring the zip (`biotech-cso/`, `pharma-svp/`, `pharma-bd/`,
`venture-ec/`, `venture-wc/`), one `.md` per persona, faithful conversion of the DOCX (fix the
mojibake — smart quotes, em-dashes). Plus `personas/INDEX.md` listing all 59 with one-line role +
archetype, usable as a menu for regenerating prompts later.

### 3. `integration_map.md` — the 3-layer roadmap

The tool-frequency data re-cut into James' three layers, each source tagged with frequency count,
priority tier, the capability areas it serves, and *why* it belongs to that layer:

- **Internal (unique):** Quiver EP-CRISPR Atlas (104), V1-T — the moat.
- **Context** (things Quiver *can't* know → go/no-go): ClinVar, OMIM, HPO, DisGeNET,
  ClinicalTrials.gov, Cortellis, ToxCast, competitive/commercial.
- **Predictivity / boosting** (independent corroboration → re-rank): STRING, BioGRID, Reactome,
  LINCS/CMap, GTEx, GWAS, Expression Atlas.
- **Meta / reasoning:** financial-optimization + expert-judgment tooling (mostly LLM + market data).

## Proposed capability areas (the judgment call — review this)

Clustered from the 299-prompt categories into the underlying *capability*, not the disease:

| ID | Capability area | Layer | Source prompt clusters |
|---|---|---|---|
| CAP-01 | Functional similarity / embedding & clustering (EP signature proximity, antipodal, pathway reconstruction) | Internal | 010–012, 030–041, 088 |
| CAP-02 | Target discovery & prioritization (rank targets, antipodal-to-disease, convergent nodes) | Internal | 013–020, 042–043, 123–124, 260 |
| CAP-03 | Drug–target binding / DTI / ligandability (binder triage, rescue match, repurposing) | Internal+Pred | 045–054, 099–104 |
| CAP-04 | ASO design & sequence generation (knockdown, allele-specific, splice-mod, chemistry) | Internal | 021–029, 275–299 |
| CAP-05 | Mechanism disambiguation (synaptic vs intrinsic; disease-mod vs symptomatic) | Internal | 075–084 |
| CAP-06 | Genetics ↔ function integration (GWAS support, ClinVar mapping, protective variants) | Predictivity | 085–094 |
| CAP-07 | BBB / PK-PD / druggability (penetrance, exposure, metabolic liability) | Context | 095–098, 101 |
| CAP-08 | Toxicity & safety prediction (seizure/immunogenicity/ADMET, contraindications) | Context | 009, 105–114 |
| CAP-09 | Combination & network strategy (synergy, dual-target, hub collapse) | Internal | 055–059, 115–124 |
| CAP-10 | Biomarker & translational (fluid biomarkers, EEG correlation, symptom mapping) | Predictivity | 060–064 |
| CAP-11 | Variant→disease association / patient prevalence / genetic epidemiology | Context | 076, 089, 129 + James' adds |
| CAP-12 | Protein–protein interaction / pathway membership | Predictivity | 033, 036–040 + James' adds |
| CAP-13 | Competitive & commercial intelligence (active programs, white-space, pricing, peak sales) | Context | 070, 135–142 |
| CAP-14 | Portfolio & capital allocation / financial optimization (rNPV, budget allocation, kill calls) | Meta | 065–069, 143–154, 273 |
| CAP-15 | Expert judgment / strategic reasoning (CSO-persona asks, regulatory & trial-design wisdom) | Meta | 165–174 → **expert-agent gap** |
| CAP-16 | AI self-reflection / uncertainty quantification (where data is insufficient, confidence, replication) | Meta | 155–164 |

Disease-specific batches (175–259: monogenic, neuropsych, neurodegen, pain) are *applications* of
CAP-02/03/04/05 — captured on the Prompts sheet via the disease-area column, not as separate areas.

## Build order

1. `personas/` conversion + INDEX (mechanical, unblocks nothing else).
2. `Prompts` sheet (parse the 299, assign each to a capability area + disease area).
3. `Capabilities` sheet (fill supply/status/verdict; pull DTI/embedding/ADMET/structure verdicts
   from Q-Mammal, leave the rest as untested/gap with honest blanks).
4. `integration_map.md` (re-cut frequency data into the 3 layers).
5. Top-level `README.md` tying the four together + how to keep building it.

## Explicitly out of scope (for now)

- The orchestration brief for Hayes (separate deliverable, not chosen this round).
- The expert-agent corpus *build* (this map only *flags* CAP-15 as the gap + names the pattern).
- Quiver-branded deck/Word versions (working files first; polish once content is locked).
- Running any new model evals (the map records existing Q-Mammal findings; it doesn't generate new ones).

## Honesty rules

- Status/verdict columns reflect only what's empirically established in Q-Mammal. Everything else is
  marked `untested` or `gap` — no inventing model performance.
- Where a capability has no off-the-shelf model (e.g. CAP-15), say so and route it to the build column.
