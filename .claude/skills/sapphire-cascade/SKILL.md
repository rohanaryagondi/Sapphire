---
name: sapphire-cascade
description: Run the Sapphire Cascade — a 5-agent internal-first re-ranking cascade (internal moat → context GATE → predictivity BOOST → uncertainty/abstention) that pulls all external evidence live from EMET (BenchSci) via Playwright. Use when asked to run the cascade, reproduce the #7→#1 target-promotion demo, prioritize CNS targets with internal-first reasoning, or demonstrate the Hayes-brief orchestration on a query.
---

# Sapphire Cascade — driver

Operationalizes the three-layer re-ranking cascade from `sapphire-cascade/ARCHITECTURE.md`. You
(the main session) act as the **Orchestrator**; the four worker agents are defined in
`sapphire-cascade/agents/`. All external evidence comes from **EMET** via
`sapphire-cascade/emet_protocol.md`.

## Preconditions
- The shared Playwright browser is open and EMET (`https://app.summit-prod.benchsci.com/`) is
  **signed in**. If any tab shows a login screen, STOP and ask the user to re-authenticate.
- Read `ARCHITECTURE.md`, `emet_protocol.md`, and the five `agents/*.md` before driving.

## Inputs
- A target-prioritization query for a CNS disease area, OR a named scenario in `scenarios/`
  (`nav1_8_pain`, `tsc2`). Scenarios ship a curated synthetic moat in `internal_moat/`.

## Procedure (cascade order — sequential; one agent drives EMET at a time)
1. **L1 — Internal Retrieval.** Load `internal_moat/<scenario>.candidates.json`. Emit the ranked list
   with `s_internal` + provenance. Record the initial ranks (define "#7"). *Never query EMET here.*
2. **L2 — Context/Safety GATE.** For the candidate set, drive EMET per `emet_protocol.md`
   (Drug Safety / Safety Assessment / Database Q&A; a workflow tool fixes its own depth, otherwise
   set **Thorough**). Public identifiers only. Assign `pass | flag | no_go` with cited evidence.
   Remove `no_go`; apply the `flag` penalty.
3. **L3 — Predictivity BOOST.** For survivors, drive EMET (Target Validation / Pathway Analysis /
   Quantitative Evidence). Tally cited independent corroboration; compute `s_final`; re-rank.
4. **Uncertainty/Abstention.** Fuse neighborhood density + context↔predictivity agreement + evidence
   sufficiency. Emit confidence per top candidate; abstain + propose an experiment where thin.
5. **Render the execution plan** exactly as specified in `agents/orchestrator.md`.

## EMET tab discipline (hard rules)
- Each EMET interaction: open a **new tab**, do the work, **close that tab**. Always leave **base
  tab 0** open so the browser never closes.
- **Public identifiers only** to EMET (gene symbols, SMILES, disease terms). Never the internal
  scores, `QS…` IDs, the synthetic moat, or any proprietary EP/CRISPR/functional data.
- Cite every external claim to its EMET source; drop uncited claims.

## Output
The transparent execution plan + final ranked answer (and, on abstain, the proposed experiment).
Append the run to `sapphire-cascade/RUN_LOG.md` with the EMET chat URLs used as evidence anchors.
