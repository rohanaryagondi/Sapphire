# Task Brief — Quantitative-fact seams (hard numbers alongside EMET)

*Tier: **Feature** (multiple new Bucket-1 fact agents + harness registry + engine wiring + provenance + tests).
Owner: **rohan**. Ship **incrementally** — one seam (gnomAD) first as the pilot that establishes the
"quantitative-fact REST seam" pattern, then the rest follow the template as separate Standard-tier PRs.*

## Goal
Give Sapphire's Bucket 1 a small set of **structured quantitative fact sources** that EMET (an LLM knowledge
source) can only paraphrase. EMET tells us *what the literature says*; these seams return *the actual number* —
genetic constraint, expression, dependency, predicted variant effect, structural/sequence neighbours. Each is a
Bucket-1 fact agent in the **`aso-tox` seam pattern**, emitting high-tier, provenance-stamped facts that
complement EMET's narrative and let the Research Manager flag number-vs-narrative `DIVERGENCE`.

## Why (context — see the systems review)
With unlimited EMET, ToolUniverse's ~1,000 tools are overwhelmingly knowledge/DB wrappers that EMET subsumes,
and its heavy compute (Boltz/ESMFold/etc.) is redundant with what Quiver already has (Boltz, AlphaFold-like,
Rosetta, TMOL, Q-Models). What survives the filter "EMET structurally can't do this — a fresh computation or a
precise structured value" is a focused set of quantitative target-validation data sources. We do **not** adopt
the ToolUniverse runtime; we read its Apache-2.0 wrapper implementations as the API-contract reference and
reimplement the few we want as our own stdlib seams.

## Scope — the seams (priority order)
**Pilot (build first, it sets the pattern):**
1. `gnomad-constraint` — gnomAD gene constraint (pLI / LOEUF / mis-z) for a gene. The strongest single
   quantitative target-validation signal (LoF intolerance). Source: gnomAD GraphQL API (public).

**Core target-validation set (next):**
2. `gtex-expression` — GTEx tissue-level expression (TPM) → CNS selectivity + peripheral-tissue safety signal.
3. `depmap-dependency` — DepMap gene essentiality (Chronos/CERES) across lineages → target prioritisation.
4. `alphamissense` — AlphaMissense predicted pathogenicity for a variant/gene (a prediction, not a lookup).

**Useful general comp-bio (optional, build if/when needed):**
5. `foldseek` — structural-similarity search (off-target / paralog structural liability scan). NOTE: public
   Foldseek is API-based; confirm a stable programmatic endpoint or treat as a delegate.
6. `interpro-domains` — InterPro/Pfam domain annotation for a sequence/accession.
7. `geneset-enrichment` — Enrichr / g:Profiler over a hit list (statistics, for multi-omics interpretation).
8. (only if a sequence-search need is concrete) `mmseqs`/`blast` — sequence search. Caveat: MMseqs2 wants a
   local binary; BLAST has a public API. Decide per need; lowest priority.

Target 6–10 seams total; items 1–4 are the must-haves for CNS diligence.

## Build pattern (per seam — mirror `tools/aso_tox/` + `sapphire-orchestrator/tools/aso_tox_seam.py`)
- **Stdlib-only seam.** These are REST/GraphQL sources, so the seam can use **stdlib `urllib.request` + `json`**
  — no `requests`, no third-party import in the engine path (cleaner than aso-tox, which needs an sklearn
  subprocess). The engine stays stdlib-only (CONVENTIONS §2).
- **Harness agent.** Register each in `sapphire-orchestrator/harness/agents.json` with a complete
  `output_schema`. **Recall the aso-tox lesson:** `additionalProperties:false` means the schema must list every
  field the seam can emit (facts + `error` + any `invalid_*`) or the harness silently abstains and drops facts.
- **Engine wiring.** Add the agent id to `_BUCKET1_AGENTS` in `live_engine.py`; it fires when a target gene /
  public identifier is present in inputs (the same gating shape as aso-tox firing on sequences).
- **Provenance.** Add new allowed labels to `sapphire-orchestrator/contracts/provenance.py`
  (`gnomad`, `gtex`, `depmap`, `alphamissense`, `foldseek`, `interpro`, `enrichr`, …). Gate 3.
- **Tiering.** These are measured/curated quantitative data → tier them **T1/T2** (higher confidence than
  LLM-synthesised narrative). Decide per source in the seam.
- **Reference, don't depend.** Cite the corresponding ToolUniverse Apache-2.0 wrapper (e.g. its gnomAD / GTEx /
  DepMap / Foldseek tool files) in a comment as the API-contract reference. Do **not** import or vendor
  ToolUniverse.

## Constraints (binding — `dev/CONVENTIONS.md`)
- Engine stays **stdlib-only**; REST seams use `urllib`, not `requests`.
- **Data boundary absolute:** these seams send **public identifiers only** (gene symbols, Ensembl/UniProt IDs,
  variants, sequences) to public endpoints. No Quiver internal candidate IDs (`QS\d+`) or proprietary data ever
  leaves. The `data_boundary` guardrail must cover each new seam.
- **Never fabricate / degrade honestly:** on API error/empty, return `facts: []` + honest `error`/provenance —
  never a made-up number. Mark predictions (AlphaMissense, Foldseek) as predictions, not measurements.
- No new heavy deps in the engine; no secrets/binaries.

## Definition of Done
- [ ] Pilot `gnomad-constraint` seam shipped: stdlib `urllib`, harness agent + schema, wired into Bucket 1,
      provenance `gnomad` allowed, tiered, emits a real pLI/LOEUF fact for a known gene.
- [ ] **Gate 5 per seam:** prove the fact lands in `discover["dossier"]` through `run_live(...)` (offline test
      with the HTTP mocked at the seam boundary + recorded fixtures), not just a unit test on the parser.
      A clearly-skipped live integration test may hit the real API ($0, public).
- [ ] Honest-empty + error paths covered (no fabrication); data-boundary guardrail verified per seam.
- [ ] Full suite green; new provenance labels added; no third-party import in the engine (Gate 4 grep).
- [ ] Each subsequent seam (gtex, depmap, alphamissense, …) ships as its own Standard-tier PR reusing the pilot
      pattern, updating its workboard row to `merged` on landing.
- [ ] Per-seam report in `dev/reports/rohan/`.

## Out of scope
- Adopting the ToolUniverse runtime / MCP server / embedding model (we reimplement ~a handful of wrappers only).
- Slurm / HPC job wrapping (we don't use Slurm).
- Small-molecule ADMET (the `aso-tox` seam is our analog for the ASO modality) and the heavy structural
  predictors (Boltz / AlphaFold-like / Rosetta / TMOL / Q-Models already exist).
- Any change to EMET — EMET remains the curated narrative knowledge layer; these are the numeric complement.
