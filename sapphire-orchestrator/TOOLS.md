# Sapphire Scientific Tool Catalog

This file documents the 8 **selectable scientific tools** that go through the orchestrator's
Claude-driven tool-selection step in the PLAN stage. The machine-readable source is
`sapphire-orchestrator/tool_catalog.json`.

## Always-on core (NOT selectable — always run)

These agents run unconditionally on every engagement:

- **moat** — Quiver internal EP/CRISPR data (internal plane; data-boundary guarded)
- **EMET** (`emet-runner`) — BenchSci live literature search (cited T2 facts)
- **internal-science-lead** — moat wrapper + science reasoning
- **all 13 semantic fact agents** — FDA memory, IP/patent, clinical trials, payer, DEA, etc.
- **scientific-reasoning / rescue-mechanism** — invoked for rescue-ranking queries only

---

## Selectable scientific tools

The orchestrator reads this catalog and the user query, then decides which tools below to run.
Only selected tools are dispatched — skipped tools produce zero facts and zero trace noise.

| ID | Name | Required inputs | When to select |
|---|---|---|---|
| `aso-tox` | ASO Acute-Tox Screener | ASO nucleotide sequences (pure uppercase A/T/G/C, ≥15 nt) | ASO therapy queries or explicit ASO sequences present |
| `boltz` | Boltz-2 Structure + Binding | Protein sequence (≥25 AA) and/or ligand SMILES/CCD | Protein structure, binding affinity, molecular docking queries |
| `q-models-runner` | Q-Models Runner (ESM-2 / DTI / Variant) | Gene symbol, protein sequence, or SMILES | Protein function, drug-target binding, variant effect scoring |
| `gnomad-constraint` | gnomAD Gene Constraint | Gene symbol | Gene-target queries — haploinsufficiency, pLI, LOEUF |
| `gtex-expression` | GTEx Tissue Expression | Gene symbol | Gene-target queries — CNS expression patterns, tissue selectivity |
| `interpro-domains` | InterPro Protein Domains | Gene symbol | Gene-target queries — domain architecture, druggable pocket |
| `geneset-enrichment` | Gene Set Enrichment (g:Profiler) | ≥1 gene symbol | Multi-gene or pathway-context queries |
| `robyn-scs` | Robyn SCS Neuronal Connectivity | v17_traces imaging plate directory | Only when imaging plate data is explicitly in context |

### Selection logic (brief)

1. **Gene-ranking / single-gene queries** → select `gnomad-constraint`, `gtex-expression`,
   `interpro-domains`, `geneset-enrichment`, `q-models-runner` (ESM-2 / variant track).
   Skip `boltz`, `aso-tox`, `robyn-scs` unless specific inputs are present.
2. **SMILES / small-molecule queries** → select `boltz` (binding), `q-models-runner` (DTI).
   Skip gene-level tools unless a gene target is also named.
3. **ASO sequence queries** → select `aso-tox`. May also run gene tools if a target gene is named.
4. **Non-gene / regulatory / policy queries** → skip all 8 (always-on core still runs).
5. **Imaging-data context** → select `robyn-scs` (otherwise always skip).

The orchestrator's Claude call in `tool_selector.py` uses this catalog plus detected inputs
(from `planner.classify_query`) to make the final `tools_selected` list. A deterministic fallback
fires when the Claude call fails — see `tool_selector.py` for the fallback rules.
