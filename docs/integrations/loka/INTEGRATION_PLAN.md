# LOKA ↔ Sapphire — Integration Plan

*Direction chosen (Rohan, 2026-06-24): **LOKA as a thin UI over Sapphire.** This session: **plan + contract
docs only**, no code. The data-boundary question is escalated to a human — see [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md).*

> Companion docs: [`CONTRACT.md`](CONTRACT.md) (the wire contract + render mapping) ·
> [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) (decisions needed before building). Background: [`../../LOKA.md`](../../LOKA.md).
> The LOKA source is the **read-only** clone at `../drug-discovery-agent` (`q-state-biosciences/drug-discovery-agent`,
> HEAD `8685382`, 2026-02-12) — **we do not modify it**; LOKA-side changes here are *specifications for the LOKA team*.

---

## 1. What LOKA is (resolved from the source)

LOKA (`q-state-biosciences/drug-discovery-agent`) is Quiver + LOKA's **conversational front end**: a
**Chainlit 2.9.5** app where a single Claude agent (**AWS Bedrock** — Sonnet 4.5 "Pro" / Haiku 4.5 "Fast")
runs an iterative tool loop (≤50 iterations) over **13 tools**, deployed on AWS (ECS Fargate · S3 · DynamoDB ·
RDS Postgres). Good docs, **no test suite**.

| Layer | Where | Note |
|---|---|---|
| UI / session | Chainlit + `src/main.py` | OAuth, chat profiles (Pro/Fast), CSV upload, resume from S3 pickle |
| Agent loop | `src/agent/agent.py` (`Agent.process_message`, loop `:505-688`) | Pro path does a `think` step first, then tool selection; ≤50 iters |
| LLM | `src/agent/chatbot.py` (`:121-153`) | Bedrock `converse()` with `toolConfig`; 150K token sliding window |
| Tools | `src/tools/registry.py` + `base.py` | `BaseTool` subclasses; `execute()` returns a JSON string; rendered as Chainlit elements |
| State | DynamoDB (threads/messages) · S3 (files, dataframe pickles, model context) · RDS | per-session |

**The 13 tools:** `think`, `respond_message`, `manage_dataframe`, `search_perturbation_matches`,
`search_global_ranking` (both hit Quiver HTS electrophysiology signatures in Postgres
`perturbation_similarity_top200`), `search_disgenet_gda`, `search_uniprot_by_name`/`_by_id`/`map_ids_to_uniprot`,
`search_kegg_by_keyword`/`_by_id`, `search_web` (DuckDuckGo), `browse_web` (crawl4ai/Playwright).

## 2. How the two relate

Complementary, **not** duplicative:
- **LOKA = fast, single-shot lookups** (perturbation match, UniProt/KEGG, web) in a chat UI.
- **Sapphire = deep, cited, deliberative** — the two-bucket firm (`live_engine.run_live`): Bucket-1 cited-fact
  dossier (EMET · moat · seams · corpora, corpus-first → search-the-gap) → Bucket-2 persona roundtable → synthesis,
  all harness-enforced (provenance stamped, data-boundary guarded, traced).

"Thin UI over Sapphire" means: **for hard/CNS/"what would the room think" queries, LOKA stops driving its own
Bedrock tool loop and instead routes the query to Sapphire's `run_live`, then renders Sapphire's dossier +
roundtable + synthesis as first-class Chainlit output.** LOKA keeps its fast tools for simple lookups.

## 3. Target architecture

```
Chainlit UI (LOKA)
  └─ Agent.process_message
       ├─ route(query)
       │    ├─ simple lookup  ──► LOKA's existing Bedrock tool loop (perturbation / UniProt / KEGG / web)
       │    └─ complex / CNS  ──► Sapphire bridge ──HTTP──► serve.py /api/run ──► live_engine.run_live
       │                                                          │
       │                                          { plan, discover{dossier,flags}, consult{round1,round2},
       │                                            synthesize, engagement_id, _via }   (run_live_schema.md)
       └─ render: dossier (tier/flag chips) · roundtable spread · synthesis  ──► cl.Dataframe / cl.Text / cl.Step
```

**Key fact: the bridge already exists on our side.** `serve.py`'s **`/api/run`** already serves the real
harnessed `run_live` (`via=engine-live`, K1/PR #24), frozen to `contracts/run_live_schema.md`. LOKA does **not**
need to import our Python — it makes **one HTTP call**. The wire shape is fixed in [`CONTRACT.md`](CONTRACT.md).

## 4. What changes — LOKA side (spec for the LOKA team; we don't edit their repo)

1. **A Sapphire bridge.** Two viable shapes (pick in [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) Q2):
   - **(a) A `BaseTool`** — `SapphireAnalysisTool` (~40 lines) that POSTs the query to `/api/run` and returns the
     dossier JSON; the existing agent loop calls it like any other tool. *Lowest-friction; works today.*
   - **(b) A router in `Agent.process_message`** — classify the query up front; complex → bypass the Bedrock loop
     and call the bridge directly. *Truer to "thin UI over Sapphire"; bigger change to `agent.py:505`.*
   Recommended path: **ship (a) first** (drop-in, reversible), then graduate to (b) once routing is trusted.
2. **A render mapping** — translate `discover.dossier` / `consult.round1`+`round2` / `synthesize` into Chainlit
   elements (table per the mapping in [`CONTRACT.md §3`](CONTRACT.md)). Reuse the existing `_create_*_table`
   helpers in `agent.py:146-340` as the pattern.
3. **A routing decision** — when to call Sapphire vs. LOKA's own tools (heuristics + an explicit "deep analysis"
   affordance). See [`CONTRACT.md §4`](CONTRACT.md).
4. **Streaming/UX** — `run_live` is a single batch call (no token stream); LOKA should show a `cl.Step`
   ("Sapphire is convening the firm…") and optionally surface the `engagement_id` for the trace.

## 5. What changes — Sapphire side (our repo, future tasks — not this session)

- **Bridge hardening:** `/api/run` already conforms; add a thin `integrations/loka/` adapter + a contract
  conformance test when we build (separate task brief). *No code this session.*
- **Optional convergence:** expose LOKA's `search_perturbation_matches` to Sapphire as a **Bucket-1 seam** (same
  `tools/<name>_seam.py` pattern as `aso_tox_seam.py`) so the firm can use LOKA's perturbation data as cited
  facts — gated by the data-boundary decision ([`OPEN-QUESTIONS.md` Q1](OPEN-QUESTIONS.md)).
- **Inference path:** resolve how `run_live` reaches a model when invoked behind LOKA (Bedrock vs. our
  subscription path) — [`OPEN-QUESTIONS.md` Q3](OPEN-QUESTIONS.md).

## 6. Phasing

| Phase | What | Gate |
|---|---|---|
| **0 (this session)** | These docs: plan + wire contract + open questions. | — |
| **1** | Resolve the 3 open questions (human: data boundary; us: bridge shape, inference path). | decisions logged |
| **2** | Build the Sapphire-side `integrations/loka/` adapter + conformance test (drop-in `BaseTool` artifact for LOKA). | dev harness Standard tier |
| **3** | LOKA team adds the bridge + render mapping; end-to-end smoke against a live `/api/run`. | joint test |
| **4** | Graduate to in-loop routing (3b); optional perturbation-as-Bucket-1-seam convergence. | per-task |

## 7. Non-negotiables carried across the seam

- **Data boundary** (escalated — see Q1): only public identifiers leave to *external* evidence; internal data may
  reach the reasoning LLM, never an external source. LOKA already queries internal perturbation data directly —
  that perimeter question is a **human decision** before we couple.
- **Provenance honesty:** render `run_live`'s tiers/flags/provenance verbatim; never relabel a T2 as T1 or a mock
  as live. Degraded runs surface abstained agents + `KNOWN_UNKNOWNS` — show them, don't hide them.
- **The spread is the product:** render Bucket-2 as divergent verdicts (no forced consensus), not a single answer.
- **We don't modify the LOKA repo** — LOKA-side items here are specs; integration code lives in Sapphire as
  drop-in artifacts (precedent: `vendor/design-form-agent/`).
