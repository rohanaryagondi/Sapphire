# Status — Fact Tools

*The fact sources the firm calls. Updated 2026-06-22.* Each carries an honest provenance label.

| Tool | State | Provenance | Notes |
|---|---|---|---|
| **EMET (BenchSci)** | ✅ live | `emet-live` | Playwright skill behind an MCP-swappable seam; cited T2 facts; never emits a formal VETO. |
| **Personas (Bucket 2)** | ✅ live | `persona-judgment` | No-tools, must-cite-dossier; independent verdicts → moderated rebuttal. |
| **Q-Models** | ✅ real | `qmodels:*` | 24 tools vendored in `q-models/`; CPU sync (`live-local`, $0); GPU via async launcher (live-proven). Some tracks marked `stub`/`eval` in `qmodels/registry.json` — never silently mocked. |
| **Internal moat** | ✅ real | `moat-real` | `MoatClient` + `moat_facts` read Loka CNS_DFP EP-distance data; degrades honestly to `[]`/mock if `RohanOnly/moat/moat.sqlite` isn't built. |
| **ASO-tox** | ✅ real | `aso-tox` | Hongkang's GBR model (`tools/aso_tox/`); stdlib seam `tools/aso_tox_seam.py`; real predictions when sequences present, honest-empty otherwise. Input validated (non-ATGC rejected). sklearn pinned 1.8.0 in the subprocess. |
| **gnomAD constraint** | ✅ live | `gnomad` | Gene LoF-constraint (pLI, LOEUF, missense Z) via the public GraphQL API; stdlib seam `tools/gnomad_constraint_seam.py`; cited **T1** facts; fires on a target gene symbol, honest-empty otherwise, honest error envelope when the API is down. First of the `quant-fact-seams` pilot (PR-A). |
| **GTEx expression** | ✅ live | `gtex` | Tissue expression (median TPM) + CNS selectivity via the public REST API (dataset `gtex_v8`, pinned); stdlib seam `tools/gtex_expression_seam.py`; cited **T1** facts; fires on a target gene symbol, honest-empty otherwise, honest error envelope when the API is down. `quant-fact-seams` PR-B. |
| **InterPro domains** | ✅ live | `interpro` | Protein domain/family annotations (IPR accessions) via UniProt (symbol→accession) + the public InterPro REST API; stdlib seam `tools/interpro_domains_seam.py`; cited **T1** facts; fires on a target gene symbol, honest-empty otherwise (incl. 404), honest error envelope when an API is down. `quant-fact-seams` PR-C. |
| **g:Profiler enrichment** | ✅ live | `gprofiler` | Functional enrichment (top over-represented GO / pathway terms + p-values) over the query's gene **set** via the public g:GOSt REST API; stdlib seam `tools/geneset_enrichment_seam.py`; cited **T2** facts (computed enrichment); fires on a gene set / target, honest-empty otherwise, honest error envelope when the API is down. `quant-fact-seams` PR-D (completes the four). |

## Open items
1. **ASO Design tool** — does not exist yet. Build it; its output feeds the `aso-tox` `sequences=` channel
   (the handoff is already defined in `run_live`). → backlog `aso-design-tool` (suggested: hayes).
2. **Chronic-tox model** — roadmap; scope the integration. → backlog `chronic-tox` (suggested: hayes).
3. **Retire/label remaining mocks** — audit every track; mark `proven` vs `paper-claim`; nothing silently
   mocked. → backlog `retire-mocks`.
4. **Quantitative-fact seams — ✅ COMPLETE** (`quant-fact-seams`, **hayes**): all 4 stdlib Bucket-1 seams
   shipped — gnomAD constraint (#6), GTEx expression (#9), InterPro domains (#11), g:Profiler enrichment (#12).
   Hard numbers (provenance `gnomad`/`gtex`/`interpro`/`gprofiler`) that complement EMET's narrative; ToolUniverse
   runtime NOT adopted; DepMap/AlphaMissense/Foldseek deferred (bulk-data/job-based) — a possible later batch.
5. **Experiment Design tool** — port Matt's `design-form-agent` (Otter meeting-notes → Quiver
   experiment-design-sheet JSON, Claude-based, Quiver optogenetics assay vocabulary) into Sapphire as a
   standalone Quiver tool (`tools/experiment_design/`). Phase 1: meeting-notes → filled design sheet
   (JSON + MD, ± xlsx). Internal-only (LLM reasoning is allowed; no external evidence source touched).
   Moat/firm integration = later epic. → `experiment-design` (**hayes**): **ED-1 in review (PR-E1)** — tool
   ported to `tools/experiment_design/` (domain prompt / `MENUS_REFERENCE` / schema **verbatim** from
   `vendor/design-form-agent/`; `anthropic` lives in the tool subprocess so the engine stays stdlib-only;
   **internal-only** — transcripts go only to the LLM + local files, never to an external evidence source).
   ED-2 (fill the design sheet) next · [brief](../docs/superpowers/plans/2026-06-23-experiment-design-tool.md).

## Watch-outs
- **Data boundary is absolute**: public identifiers only leave Quiver. Tools that call external services
  (EMET, Q-Models) must never receive internal candidate IDs or proprietary structures.
- Vendored model logic (e.g. the tox `.pkl`) is **verbatim** + golden-tested + dep-pinned (Gate 4).
