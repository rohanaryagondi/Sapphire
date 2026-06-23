# Sapphire Cascade

A runnable, multi-agent realization of the **three-layer re-ranking cascade** from
[`orchestration_brief_hayes.md`](../docs/foundation/orchestration_brief_hayes.md): **internal moat → context
*gate* → predictivity *boost* → uncertainty/abstention**. It makes James' **#7 → #1** demo concrete
and shows, structurally, why Sapphire is *not* "Emit 2.0."

It is driven inside a Claude Code session (the orchestration substrate). The internal moat layer
(L1) is a **curated synthetic mock**; every external evidence claim is **real and cited**, pulled
live from **EMET (BenchSci)**.

## What's here

| Path | What it is |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The design — the cascade, the agent panel, the scoring contract, EMET-as-evidence mapping, path to a standalone port. |
| [`emet_protocol.md`](emet_protocol.md) | The exact, reproducible protocol every agent follows to drive EMET (new tab → Thorough/workflow → public-ID query → read + cite → close tab). |
| [`agents/`](agents/) | The five agent definitions: `orchestrator`, `l1-internal-retrieval`, `l2-context-gate`, `l3-predictivity-boost`, `uncertainty-abstention`. |
| [`internal_moat/`](internal_moat/) | The curated synthetic candidate sets (`*.candidates.json`) — ranked targets + `s_internal` + provenance. **Labeled MOCK**; stands in for Quiver's real EP-CRISPR latent space. |
| [`scenarios/`](scenarios/) | The flagship scenarios: `nav1_8_pain` and `tsc2`, each with the #7→#1 promotion and a no-go context veto. |
| [`RUN_LOG.md`](RUN_LOG.md) | Captured end-to-end runs with the real, cited EMET evidence — reviewable without re-running. |

## How to run it

Invoke the driver skill (`/sapphire-cascade`) with EMET signed in, or ask the session to "run the
Sapphire Cascade on the Nav1.8 pain scenario." The orchestrator drives the four worker agents in
cascade order, each pulling cited evidence from EMET, and renders the transparent execution plan.

## The data boundary (non-negotiable)

L1 (the moat) is synthetic and **never** touches EMET. Only **public identifiers** (gene symbols,
SMILES, disease terms) ever cross to EMET. No proprietary EP/CRISPR/functional data leaves the
building. See [`ARCHITECTURE.md`](ARCHITECTURE.md) §3 and [`emet_protocol.md`](emet_protocol.md).

## Status

Demo prototype (option b — session-driven). Structured to graduate to a standalone Python program
(option a) without changing the cascade contract; see [`ARCHITECTURE.md`](ARCHITECTURE.md) §6.
