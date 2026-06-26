# Running the full Sapphire demo (`:8099` + `:8101`)

This branch (`rohan/orchestrator-8101`) contains the **complete, runnable Sapphire** — both demo surfaces plus
everything they need. This guide is the single entry point for showing/running it.

Sapphire is an agentic CNS drug-discovery decision firm: **Bucket 1** gathers a cited fact dossier (Quiver
moat + EMET literature + Q-Models/ESM + tool seams); **Bucket 2** is a persona roundtable; the orchestrator
writes the report. Two surfaces:

| Surface | Dir | What it is | Cost |
|---|---|---|---|
| **`:8099` — Console** | `frontend2/` | Deterministic console — replays pre-captured scenario runs. Always works, $0, no live deps. | $0 |
| **`:8101` — Orchestrator** | `orchestrator_ui/` | **Live** LLM orchestrator: a real `claude -p` agent that decides the flow, calls the tools, reasons as the team, and streams its trace. | subscription |

A saved snapshot of the current state of each is in this folder: **`8101_tsc2_run.png`** + **`8101_tsc2_run.md`**
(the live TSC2 15-gene blind ranking) and **`8099_console.png`**.

---

## Quick start

```bash
# :8099 — deterministic console (no external deps)
cd frontend2 && python3 server.py --port 8099
#   → open http://127.0.0.1:8099

# :8101 — live orchestrator (needs the claude CLI + the moat DB; see Prerequisites)
cd orchestrator_ui && SAPPHIRE_MOAT_DB="$PWD/../RohanOnly/moat/moat.sqlite" \
  SAPPHIRE_ENGAGEMENTS_DIR=/tmp/demo-traces python3 server.py --port 8101
#   → open http://127.0.0.1:8101, ask a CNS question
```

The flagship query (paste into :8101):
> *Rank these genes by how strongly knocking each one down reverses the TSC2-KO / mTORC1-hyperactivation
> phenotype … Genes: BCL2, VPS54, KMT2D, DPM2, RPS3, FZD7, SSU72, DIDO1, ACTR3, CDK9, NCOA6, SMARCE1, SAP18,
> MTOR, PSMD13*

---

## The :8101 flow (what the orchestrator does)

Driven by `claude -p` + the `.claude/skills/sapphire-orchestrate/SKILL.md` skill, over the tools in
`sapphire-orchestrator/orchestrator_tools.py`:

1. **moat** (`moat --gene TSC2 --direction opposite` / `--probe G1,…`) — Quiver's internal EP-signature; each
   gene has a `cosine_distance` (smaller = stronger). Real, from the Loka CNS_DFP data.
2. **EMET** (`emet --gene TSC2 --batch G1,…`) — cited literature, **EMET-evidence is the primary ranker**.
   Defaults to the **captured blind dossier** (instant, real; in `sapphire-orchestrator/scenarios/emet_*`); add
   `--live` to route through the Chrome worker (below).
3. **ESM** (`esm --genes … --vs TSC2`) — ESM-2 embedding similarity (gene/protein enrichment; **down-weighted**
   — proximity ≠ rescue). Cached for TSC2; the warm GPU box computes new targets.
4. **semantic** (`semantic --batch '[{agent,gene,context},…]'`) — cheap claude-haiku specialists
   (mechanism/pathway/toxicity/expression/essentiality/genetics) run **in parallel**, after EMET, with the
   EMET evidence as context.
5. **synthesis** — EMET-focused ranking, moat as corroboration, DIVERGENCES (strong moat / no literature)
   flagged as Quiver alpha. UI: LEFT = expandable agent/tool outputs (full sources), RIGHT = live trace.

Discover everything with `python sapphire-orchestrator/orchestrator_tools.py catalog`.

---

## Prerequisites & secrets (gitignored — provide locally under `RohanOnly/`)

`RohanOnly/` is **gitignored** (it holds proprietary data + credentials and is never committed). To run :8101
fully you provide:

- **`claude` CLI** on the subscription (the orchestrator + semantic agents shell out to `claude -p`). Path is
  `SAPPHIRE_CLAUDE_BIN` (default `~/.local/bin/claude`).
- **`RohanOnly/moat/moat.sqlite`** — the Quiver moat, built from the Loka `CNS_DFP_distance_*.parquet` (the
  `neighbors` table: query/ref/effect/rank/cosine). Without it the moat honestly degrades to empty/mock.
- **EMET (BenchSci) login** — only for *live* EMET via the Chrome worker. The committed **captured blind
  dossier** already lets :8101 run fully without live EMET.
- **Warm ESM box** *(optional)* — for live ESM on new targets. TSC2 is cached, so not required for the
  flagship query. Launch via the `sapphire-aws-runner` agent (account-gated, auto-teardown); it registers
  `RohanOnly/qmodels_run/warm_instance.json`.

> Data boundary: only public identifiers (gene symbols / SMILES / disease terms / sequences) ever leave to
> EMET / Boltz / ESM / web. Internal moat `cosine_distance` is used in reasoning + the report, never sent to a tool.

---

## Setting up the Chrome-Claude EMET worker (live EMET)

Live EMET runs in **your own authenticated Chrome** via a persistent Claude session — this sidesteps the
headless-login problem. The orchestrator drops tasks on a file queue; the worker fulfils them.

1. **Queue** (auto-created): `RohanOnly/emet_queue/{tasks,results,done}/`. The orchestrator writes
   `tasks/<id>.json` on `emet … --live` and polls `results/<id>.json`.
2. **Start the worker:** open a Claude session that drives your signed-in Chrome (Claude-in-Chrome / the
   Playwright MCP), and paste this prompt:

   ```
   You are the Sapphire live-EMET worker. Use the `emet-chrome-worker` and `emet-prompting` skills.
   Repo: <path>/sapphire-capability-map. Watch RohanOnly/emet_queue/tasks/ (arm a Monitor on it; else re-check
   every ~15s) and keep running until I stop you. For each task with no matching results/<id>.json:
     1. Open a NEW tab at https://emet.benchsci.com/ (leave base tab 0 open).
     2. If a login screen appears → STOP, write results/<id>.json = {"login_required": true}, tell me. Never auto-login.
     3. thinking=Thorough. Run the task's `query` using EMET's FULL breadth (genetics/expression/perturbation/
        pathway/clinical, not just papers) and capture evidence FOR *and* AGAINST.
     4. Capture every claim with its PMID/source; drop uncited claims.
     5. Write the cited envelope to results/<id>.json, move the task to done/.
   Public identifiers ONLY ever cross to EMET (gene symbols / SMILES / disease terms) — never Quiver scores or QS… IDs.
   ```
3. **Use it:** the orchestrator defaults to **captured** EMET (instant, reliable). To pull *fresh* live EMET,
   it adds `--live` — but only when the worker is confirmed looping (a stalled worker is why captured is the
   default). See `.claude/skills/emet-chrome-worker/SKILL.md` and `emet-prompting/SKILL.md` for the full protocol.

---

## Architecture pointers
- Orchestrator skill: `.claude/skills/sapphire-orchestrate/SKILL.md` · tools: `sapphire-orchestrator/orchestrator_tools.py`
- :8101 server (SSE + `claude -p`): `orchestrator_ui/server.py` + `orchestrator_ui/static/`
- :8099 server: `frontend2/server.py`
- Moat client: `sapphire-orchestrator/moat/` · EMET envelopes: `sapphire-orchestrator/scenarios/emet_*`
- Q-Models/ESM/Boltz seams + launcher: `sapphire-orchestrator/qmodels/`, `sapphire-orchestrator/tools/`
- Full architecture: `docs/ARCHITECTURE.md` · overnight build log: `RohanOnly/OVERNIGHT_STATE.md`
