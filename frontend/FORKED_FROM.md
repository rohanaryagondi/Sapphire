# FORKED_FROM — provenance of `frontend/`

`frontend/` is a **fork** of LOKA, Quiver's conversational drug-discovery front end, re-pointed
from its AWS Bedrock agent loop to Sapphire's in-process `live_engine.run_live` firm.

## Upstream

- **Repo:** `q-state-biosciences/drug-discovery-agent` (LOKA)
- **Upstream commit:** `8685382` ("Merge remote-tracking branch 'origin'", 2026-02-12)
- **Local read-only clone:** `../drug-discovery-agent` (a sibling of this repo) — **never modified**.
  We copy assets *out* of it; we do not edit it in place.
- **Framework:** Chainlit `2.9.5` (pinned in `requirements.txt`).

## Ownership / license  ✅ (RESOLVED — Quiver owns LOKA outright)

**Quiver owns LOKA in full.** Quiver contracted Loka to build the drug-discovery-agent
(LOKA) for Quiver; Quiver owns every part of it and may do whatever it wants with it —
internal use, modification, and **external distribution all permitted, no restriction**.
(Confirmed by Rohan, 2026-06-24.)
- **Attribution (courtesy):** original build by Loka for Q-State Biosciences (Quiver).
- **Status:** no license gate. `frontend/` may ship internally or externally freely. The
  earlier "resolve before external distribution" caveat is **withdrawn** — there is nothing
  to resolve; the work is Quiver's property.

## What was KEPT (forked, adapted)

- The **Chainlit shell**: `.chainlit/config.toml` (+ `translations/`), `public/custom.css`,
  `public/custom.js`, `public/theme.json`, `public/favicon.svg`, `public/logo_{dark,light}.png`.
  (`enable_telemetry` flipped to `false` in the forked `config.toml`.)
- The **element-rendering pattern** — LOKA's `_create_*_table` helpers (`src/agent/agent.py`
  ~146-340) that build `cl.Dataframe` / `cl.Step` / `cl.Text` elements. Re-implemented in
  `frontend/render.py` against Sapphire's `run_live` output (we kept the *pattern*, not the
  perturbation/UniProt-specific tables).
- The **Chainlit entrypoint** shape (`src/main.py`) — `@cl.set_starters`, `@cl.set_chat_profiles`,
  `@cl.on_message` — adapted in `frontend/main.py`, with the CNS-reframed starters.

## What was REPLACED

- LOKA's **AWS Bedrock agent loop** (`src/agent/agent.py` `Agent.process_message`, the ≤50-iter
  tool loop, + `src/agent/chatbot.py` Bedrock `converse()`) → an **in-process bridge**
  (`frontend/bridge.py`) that calls `sapphire-orchestrator/live_engine.run_live(query, ctx=...)`
  and maps the result to Chainlit elements via `frontend/render.py`. No Bedrock, no token stream
  (a real run is a single batch call behind a `cl.Step` spinner).

## What was STRIPPED (not carried over)

- `cdk/` — the entire AWS CDK deployment stack.
- AWS data layers: `src/data/dynamo.py`, `src/data/s3.py`, `@cl.data_layer` (we use Chainlit's
  **default local data layer** — in-memory, no AWS, no config).
- The 13 LOKA tools (`src/tools/*`) incl. the **RDS perturbation** tools
  (`perturbation_search.py`, `global_ranking.py`) that query Quiver internal HTS Postgres,
  UniProt/KEGG/DisGeNET/web tools, the CSV-upload/dataframe path, and Bedrock model selection.
- Deps: `boto3`/`aioboto3`, `tiktoken`, `psycopg2-binary`, `crawl4ai`, `ddgs`, etc. — none are in
  `frontend/requirements.txt`.
- `public/uniprot.png` and the `*.example` asset dirs (LOKA-tool-specific).

## Why fork instead of HTTP

The older `docs/integrations/loka/` plan described LOKA calling Sapphire over HTTP without forking.
Current direction (2026-06-24): fork the Chainlit shell into our repo and bridge **in-process** —
the engine is right here and stdlib-only, so an in-process `run_live` call is simpler than running
a separate `serve.py` and avoids a network hop. We still honor the render mapping
(`docs/integrations/loka/CONTRACT.md` §3) and the non-negotiables (provenance/tier verbatim, two
data planes, no forced consensus, public-identifiers-only).
