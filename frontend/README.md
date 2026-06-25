# Sapphire frontend — a transparent control surface over the live firm

A **fork of LOKA's Chainlit app** (see [`FORKED_FROM.md`](FORKED_FROM.md)) re-pointed from its AWS
Bedrock agent loop to Sapphire's in-process firm. You ask a deliberative CNS question; the app
calls `live_engine.run_live(query, ctx=...)` **in-process** and renders the **full firm process** so
you can see what's working and what isn't:

**plan** → **Bucket-1 agent roster** (id · status · provenance; abstained shown) → **dossier** split
into the **two data planes** (internal Quiver moat vs external public evidence) with columns
`value · field · tier · provenance · source · flag` → **VETO / DIVERGENCE / KNOWN_UNKNOWNS** callouts
→ **Bucket-2 roundtable spread** (one card per persona — no forced consensus; round1 → round2 when
present) → **synthesis**. Tier / provenance / plane strings are rendered **verbatim** — nothing is
relabelled, no mock is dressed up as live, and there is **no per-agent timing** (the contract has
none — we show one total wall-clock instead, never a fabricated per-agent number).

## Architecture (modules)

| File | Role | Deps |
|---|---|---|
| `bridge.py` | in-process seam → `run_live(query, ctx=...)`; never raises. Wires the **session-bridge** real-EMET path (`emet_envelopes` / auto-load) | engine (stdlib) only |
| `render.py` | pure `run_live` dict → render *specs* (chainlit-free, unit-tested in Gate-1) | stdlib only |
| `elements.py` | specs → `cl.Dataframe` / `cl.Message` (only module importing chainlit) | chainlit + pandas |
| `mock_ctx.py` | the Demo ctx — reuses the engine tests' `_build_ctx` (parity, never drifts) | engine tests |
| `main.py` | Chainlit entrypoint: starters, Demo/Live profiles, `@cl.on_message` | chainlit |
| `starters.py` | CNS-reframed starter prompts (public identifiers only) | — |

The engine stays **stdlib-only**: `chainlit`/`pandas` live only in this process
([`requirements.txt`](requirements.txt)); importing `live_engine` in-process pulls in no
third-party package.

## Run it

```bash
pip install -r frontend/requirements.txt     # chainlit==2.9.5, pandas
cd frontend && chainlit run main.py          # opens http://localhost:8000
```

> **Run from inside `frontend/`** so Chainlit picks up the forked `.chainlit/config.toml`,
> `public/`, and `chainlit.md` (it resolves these relative to the working directory). The engine
> import path is computed from `__file__`, so it works regardless of where you launch.

Then pick a **chat profile**:

### Demo (mock backends) — the verification path · $0, deterministic
Runs the real firm logic through the offline mock ctx (the same `_build_ctx` the engine's own test
suite uses) — no `claude` CLI, no network, no AWS. Use this to inspect the full process. This is the
path Gate-5 verifies.

### Live (real firm) — real backends
`ctx=None` → the real moat (if `RohanOnly/moat/moat.sqlite` is built) + real seams + a registered
EMET handler. The live persona/fact subagents shell out to the **`claude` CLI** (Claude Code on your
subscription).

**EMET — the real-EMET path is the session-bridge.** `bridge.run` auto-loads the captured EMET
envelope for the run's candidate from `sapphire-orchestrator/scenarios/emet_envelopes/<candidate>.json`
(or you pass `emet_envelopes={...}` explicitly) and wires the in-session handler, which **wins** over
the default. A **covered** candidate (e.g. TSC2) lands real `emet-live` PMIDs (driven live in the
orchestrator's authenticated BenchSci session, then injected — see
[`../sapphire-orchestrator/emet/LIVE_EMET.md`](../sapphire-orchestrator/emet/LIVE_EMET.md)); an
**uncovered** candidate **abstains honestly** (`login-required`), never fabricates. The result echoes
`_emet_session: [covered candidates]`.

> The detached **`claude -p` EMET runner is a shelved, NON-default fallback** (used only for
> candidates with no captured envelope): Gate-5 found it tool-fails / is too slow even on sonnet
> (`#77`/`#84`). The session/captured envelope wins for covered candidates.

Without a model the live subagents abstain honestly; the UI shows degraded agents + KNOWN_UNKNOWNS
openly. A real run is **slow** (multi-agent, no token stream).

### Live (cheap · haiku) — real firm, cheap reasoning
Same live backends as **Live** (real moat · real EMET · real seams/corpora · real Q-Models), but every
`claude` agent (Bucket-1 fact agents + Bucket-2 personas) runs on **haiku** — pinned via `CLAUDE_MODEL`
(the bridge's lever; `dispatch_claude` also honors `SAPPHIRE_MODEL`, serve.py's lever) →
`dispatch_claude --model` — so a real run doesn't burn default-model tokens.
**Honest:** the facts are real; only the model is cheaper (nothing is mocked or relabeled). Needs the
`claude` CLI + a logged-in EMET session.

### Replay (captured TSC2 · $0) — frozen REAL runs, instant
A **frozen REAL `run_live` capture** replayed deterministically (no model, no network); provenance /
tiers / flags rendered verbatim. ⚠ Contains internal moat data — internal demo only. Two captures:

- **Replay (captured TSC2 · $0)** → `tsc2_live_run.json` (real moat + real EMET PMIDs + the spread).
- **Replay (TSC2 · session-bridge EMET · $0)** → `tsc2_emet_session.json` — the **session-bridge**
  capture: EMET came from the front end's real-EMET path (the captured envelope, 9 real TSC2 PMIDs,
  injected via `make_session_emet_handler`). Re-capture with `_build/capture_tsc2_emet_session.py`.

No AWS, no DynamoDB/S3: this fork uses Chainlit's **default local (in-memory) data layer** — chat
history is ephemeral (fine for a control surface).

## Tests

- **Gate-1 (offline, $0):** `bash dev/run-tests.sh` runs `frontend/tests/` (render + bridge) with the
  rest of the suite — no chainlit needed (`render.py` is pure).
- **Re-capture the render fixture:** `python frontend/tests/_capture_fixture.py` (writes
  `tests/fixtures/run_live_mock.json`, validated against the `run_live` contract).
- **Gate-5 (functional):** launch the app (Demo profile) and confirm the six render regions appear;
  see the PR's verifier evidence.
