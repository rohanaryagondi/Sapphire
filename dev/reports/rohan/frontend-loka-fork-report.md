# Work-stream B — LOKA frontend fork → transparent control surface over `run_live` — report

**Branch:** `rohan/frontend-loka-fork` · **Built-By:** rohan · **Tier:** Feature

## Goal
Fork LOKA's Chainlit app into a new `frontend/` dir and wire it **in-process** to
`live_engine.run_live(query, ctx=...)` as a **transparent control surface** over the Sapphire firm —
so we can see what each part of the firm is doing. Honor the render mapping
(`docs/integrations/loka/CONTRACT.md` §3) and the non-negotiables (§7).

## What shipped (9-task plan, `docs/superpowers/plans/2026-06-24-frontend-loka-fork-tasks.md`)

- **Fork (T1):** static LOKA shell copied into `frontend/` from the read-only clone
  (`q-state-biosciences/drug-discovery-agent` @ `8685382`, never modified) — `.chainlit/config.toml`
  (+translations), `public/{custom.css,custom.js,theme.json,favicon.svg,logo_*}`. Telemetry off; app
  name → "Sapphire"; the `custom.js` welcome title re-pointed to Sapphire (honest labeling).
  `FORKED_FROM.md` records upstream commit + kept/replaced/stripped + the absent-LICENSE note.
- **In-process bridge (T6):** `bridge.py` — `run(query, *, mock)` → `run_live(query, ctx=...)`. Never
  raises (honest error envelope). The engine path is inserted into `sys.path` at **call time** (not
  just import) because Chainlit rebuilds `sys.path` between importing the app and running the message
  handler — a bug Gate-5 caught and this fixed. `mock_ctx.py` reuses the engine tests' `_build_ctx`
  (parity, never drifts).
- **Pure render (T3–T5):** `render.py` — chainlit-free, stdlib `run_live` dict → render *specs*.
  Two **distinct** data-plane sections (internal Quiver moat vs external public evidence), dossier
  columns `value·field·tier·provenance·source·flag`, the roundtable **spread** (one card per persona,
  no forced consensus, round2 when present), agent roster with abstained/escalated **shown**,
  VETO/DIVERGENCE/KNOWN_UNKNOWNS callouts. Tier/provenance/plane **verbatim**; **no fabricated
  per-agent timing** (the contract has none — a single total wall-clock is measured by the bridge).
- **Chainlit UI (T7):** `elements.py` (the only chainlit-importing module) maps specs →
  `cl.Dataframe`/`cl.Message`; `main.py` wires starters + Demo/Live `ChatProfile` + `@cl.on_message`
  → bridge → render → elements. **Default local data layer (no AWS).** `starters.py` = 5 CNS starters
  (public identifiers only).
- **Retire `site/` (T8):** `site/README.md` marked **superseded** by `frontend/` (not deleted).
- **STRIPPED:** `cdk/`, `src/data/dynamo.py`/`s3.py`, the 13 LOKA tools (incl RDS perturbation),
  Bedrock — no `boto/dynamo/s3/bedrock` imports in `frontend/`. Deps: only `chainlit==2.9.5` + pandas.

## Gate evidence

- **Gate 1 — full suite:** `bash dev/run-tests.sh` → **456 GREEN** (… corpus 8 · tests 187 ·
  **frontend 22**). The 22 frontend tests (render + bridge) are stdlib-only (no chainlit needed) and
  run in Gate-1; `dev/run-tests.sh` extended to discover `frontend/tests`.
- **Gate 3 — provenance/secrets:** no secrets, no `.env`. Only binaries are the two LOKA logos
  (53/61 KB, small assets). No new engine provenance labels.
- **Gate 4 — stdlib runtime + fork attribution:** `git diff <base>..HEAD -- sapphire-orchestrator/`
  is **EMPTY** — the engine is untouched; `chainlit`/`pandas` live only in `frontend/`. Fork
  provenance in `FORKED_FROM.md` (upstream `8685382`, attribution to Q-State Biosciences).
- **Gate 5 — functional (RAN it in a browser):** launched `chainlit run main.py` from `frontend/`,
  Demo profile, submitted "Is TSC2 a viable target in tuberous sclerosis?". The **full transparency
  view rendered**: plan (deliverable/disease/modality/agents/panel) · firm roster (10 agents,
  id·status·provenance, real provenance moat-real/emet-live/qmodels/fda-primary/semantic-web) ·
  **Internal plane (8 facts)** and **External plane (11 facts)** as two distinct tables with the 6
  columns · tier/provenance **verbatim** incl **corpus-sourced FDA facts showing a faithful T1 vs T2
  distinction** · roundtable **spread** (5 persona cards, no consensus collapse) · synthesis
  ("Conditional advance", confidence `medium`, proposed experiment, entities `TSC2`) · trace
  `eng_7831be68`. **Adversarial:** garbage query "xyzzy plugh nonsense" → well-formed **degraded**
  view (Entities: —, no crash); the earlier import bug rendered honestly as a KNOWN_UNKNOWN (no
  traceback to the user). **Bug found & fixed by Gate-5:** Chainlit `sys.path` rebuild → call-time
  engine-path insertion.

## Decisions / escalations
- **Q-A** mock ctx: thin `mock_ctx.py` re-exporting the test `_build_ctx` (parity).
- **Q-B** planes: two distinct sections. **Q-D** Gate-5 gated on the mock path; live path documented.
- **Q-C — license (escalated, non-blocking):** the LOKA source has no LICENSE file. `dev/HELP.md`
  `[OPEN] frontend-loka-fork: license/attribution` flags whether external distribution needs explicit
  permission; internal reuse proceeds.

## Out of scope (per plan)
Routing (firm vs LOKA fast tools — the fork has no LOKA tools left, every query → run_live), durable
chat history (SQLite data layer), full Sapphire re-skin of `public/`, deleting `site/`, ASO-Design
wiring. No change to `sapphire-orchestrator/` runtime or the contract.

## How to run
`pip install -r frontend/requirements.txt` then `cd frontend && chainlit run main.py` → pick
**Demo (mock backends)** ($0, deterministic) or **Live (real firm)** (needs the `claude` CLI; without
it the firm abstains honestly). See `frontend/README.md`.
