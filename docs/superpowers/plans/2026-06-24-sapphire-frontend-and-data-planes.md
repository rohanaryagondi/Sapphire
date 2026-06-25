# Feature brief — Sapphire transparent front end (LOKA-fork) + two enforced data planes

*Owner: **rohan**. Tier: **Feature** (dev harness → PLAN via `sapphire-dev-planner` → tasks → whole-branch
review via `sapphire-dev-integrator`). Created 2026-06-24. Direction set by Rohan this session.*

> Supersedes the "LOKA stays the external front end" assumption in `docs/integrations/loka/` for *our* surface:
> we **fork LOKA's Chainlit UI into Sapphire** as our own front end (the real LOKA repo stays untouched and can
> adopt the same `run_live` pattern later). Retires the old `site/` Console.

## Goal (definition of done)
A **working front end** that (1) connects to the real back end (`live_engine.run_live`), and (2) shows the
**actual tools, agents, and the full firm process in a highly transparent way — so we can see what's doing well
and what isn't** — with (3) **web/external evidence separated from Quiver internal data** into two enforced
planes that are **visible in the UI**.

Observable success:
- Launch the app locally, type a CNS query, and watch the firm run end-to-end against `run_live` (not canned):
  plan → each Bucket-1 agent (id · tool · provenance · pass/abstain · timing) → dossier (value/field/tier/flag/
  **plane**) → Bucket-2 roundtable **spread** (per-persona, no forced consensus) → synthesis.
- Every fact is tagged **internal** or **external**; the UI renders the two planes distinctly; a test proves
  internal data can never reach an external-fetch agent.
- A transparency/health view shows per-agent status across the run (live vs mock vs abstain, latency, error) so
  "what's doing well and what isn't" is obvious at a glance.

## Two work-streams

### A. Two enforced data planes (the data-boundary call, now ruled: separate + visible)
1. **Define the planes** in one place (extend `contracts/provenance.py`): map every provenance label to a
   **plane** — `internal` = `moat-real` (+ any future internal source); `external` = `emet-live`, `gnomad`,
   `gtex`, `interpro`, `gprofiler`, `corpus`, Q-Models, web. A single source of truth, tested.
2. **Enforce the guard** in the harness/engine: internal-plane data must never be passed to an external-fetch
   agent's inputs. Centralize the existing data-boundary BLOCK behind this plane map; add an adversarial test
   (feed an internal value toward EMET/web → must BLOCK/abstain, never transmit).
3. **Tag facts** in `run_live` output: each dossier fact gains an additive `plane` field (derived from
   provenance). Update `run_live_schema.{md,py}` together + conformance tests (additive-only).
4. **Surface it**: the front end renders internal vs external facts in separate, clearly-labeled regions/columns.

### B. The front end (fork of LOKA's Chainlit app)
1. **Fork into `frontend/`** (a working copy we modify — NOT `vendor/`, which is verbatim originals). Record
   provenance in `frontend/FORKED_FROM.md` (upstream `q-state-biosciences/drug-discovery-agent` @ `8685382`).
   - **Keep:** the Chainlit shell (`main.py`, `.chainlit/`, `public/` CSS/JS), the element-rendering patterns
     (`_create_*_table`, `cl.Dataframe`/`cl.Step`/`cl.Text`/`cl.Image`), `src/visualization/components.py`,
     reframed CNS starters.
   - **Replace:** the Bedrock agent loop (`agent/agent.py` loop + `agent/chatbot.py`) with a **Sapphire bridge**
     that calls `run_live` (in-process; same repo) and maps its output to Chainlit elements.
   - **Strip:** `cdk/`, `src/data/dynamo.py` + `s3.py`, RDS/`database_tools.py`, the perturbation/global-ranking
     tools, and the Bedrock deps (`aioboto3`/`botocore`). Use Chainlit's default local data layer (no AWS).
2. **Wire to the back end**: bridge calls `live_engine.run_live(query, ctx=...)` and consumes the documented
   contract (`contracts/run_live_schema.md`). Keep a `/api/run`-over-HTTP option as a fallback, but in-process is
   primary (one repo). The front end's frozen view of the contract is `docs/integrations/loka/CONTRACT.md`.
3. **Transparency rendering** (the heart of this — go beyond LOKA's chat):
   - **Process timeline**: plan → Bucket-1 dispatch → dossier → Bucket-2 round1→round2 → synthesis, each a
     `cl.Step` you can expand.
   - **Agent/tool panel**: list the actual agents that ran (from `discover.agents` + the harness roster), each
     with tool/kind, provenance, status (live/mock/abstain), and timing. This is the "what's doing well" view.
   - **Dossier table**: value · field · tier (T1/T2 chip) · provenance chip · **plane** · flag (⛔VETO/⚠DIVERGENCE).
   - **Roundtable**: per-persona verdict cards (stance · conviction · rationale · fact-claims) — render the
     **spread**, never collapse to consensus; show the round1→round2 rebuttal progression.
   - **Synthesis**: recommendation · confidence · proposed_experiment · entities.
   - **Honesty**: show abstained agents + `KNOWN_UNKNOWNS`; label any mock surface; never relabel a tier/provenance.
4. **Run/setup**: a one-command local launch (`chainlit run frontend/main.py`), documented in `frontend/README.md`,
   plus how it reaches `run_live`. Engine stays stdlib; the front end's heavier deps (chainlit) are isolated to
   `frontend/` (its own `pyproject`/requirements), per the runtime-stdlib convention.

## Sequencing (PLAN will refine into per-task DoD)
1. A1–A3 (planes: provenance map → guard+test → `plane` in contract) — small, lands first; unblocks the UI tag.
2. B1 (fork skeleton into `frontend/` + provenance) → B2 (bridge to `run_live`, minimal end-to-end render).
3. B3 (full transparency rendering) + A4/B (plane visualization).
4. B4 (run docs) → Gate 5 functional verification (run a real query, adversarially) → integrator whole-branch review.

## Constraints / watch-outs
- **Do NOT modify the upstream LOKA repo** (`../drug-discovery-agent`); the fork is a copy under `frontend/` with
  attribution. (Convention precedent: `vendor/` for verbatim, but this is a *modified* fork → `frontend/` + FORKED_FROM.md.)
- **Engine stays stdlib-only**; front-end deps live in `frontend/` only (don't leak chainlit/pandas into the engine).
- **Data boundary is the point** — internal never crosses to external; the plane guard must be code-enforced + tested,
  not just visual.
- **Contract changes are additive-only** and update `.md` + `.py` together with green conformance tests.
- **Retire `site/`** as the destination once `frontend/` runs end-to-end (note it, don't delete blindly).
- This is a real product surface for judging the firm — **transparency/honesty beats polish**; show the warts.
