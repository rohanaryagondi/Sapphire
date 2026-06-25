# Task brief — cheap-live runs (real EMET + real moat, without burning default-model tokens)

*Owner: **rohan** (built by Rohan Claude; Head Claude reviews/gates/merges). Tier: **Standard** (two small, independent
work-items). Created 2026-06-24.*

## Why
Today the front end has two profiles: **Demo** (full mock ctx, $0) and **Live** (`ctx=None`). Two gaps make a
*useful* live run impossible right now:
1. **Live EMET never fires.** `live_engine.run_live` auto-wires real `python_fns` (moat + seams) but does **not**
   wire an `emet_handler` into the ctx. So with `ctx=None`, the `emet-runner` agent hits
   `dispatch_emet` → "emet handler not registered" → **abstains**. A user can log into EMET and the Live profile
   still won't use it.
2. **No cost control.** `dispatch_claude` (`harness/dispatch.py`) builds `claude -p …` with **no `--model`**, so
   every persona/claude-fact agent runs on the CLI default model (can be Opus). There is no way to run a live firm
   cheaply (haiku) or to keep the expensive **persona roundtable** mocked while the facts are real.

Goal: a live run that uses **real moat + real EMET (the user's logged-in session) + real corpora/seams**, but with
the **LLM reasoning either on haiku or with personas mocked**, so it doesn't burn default-model tokens.

## Work-item 1 — wire EMET into the live ctx (so a logged-in session is actually used)
- In `live_engine.run_live`, **`setdefault` an `emet_handler`** the same way `python_fns` are wired (around
  `live_engine.py:220`). Use the existing seam — `sapphire-orchestrator/emet/` (`make_emet_handler()` /
  `handler.py`). **Lazy-import it inside the setdefault** so the stdlib engine import graph stays clean (no
  Playwright/Claude import at engine import time). When a caller supplies its own `emet_handler` (tests), don't override.
- **The hard part — session reuse (verify, don't assume):** the live EMET handler drives Claude+Playwright. It must
  reuse the **already-authenticated** BenchSci session, not spawn a fresh unauthenticated browser. Investigate how
  the handler launches the browser:
  - If it drives a **persistent browser profile / user-data-dir**, point it at one the user logs into once
    (document the path + the one-time login step). 
  - If it spawns an ephemeral browser each run, the login will NOT carry — in that case **do not fake it**: wire the
    handler, make the agent **abstain honestly with a clear "EMET login required / session not shared" note**, and
    **raise the session-sharing design question in `dev/HELP.md`** (it may need an EMET-MCP or a shared-profile
    decision above your pay grade). Surfacing the limitation honestly is the deliverable if true reuse isn't
    achievable in this task.
- Test offline: with an injected mock `emet_handler`, the emet agent fires and lands a fact (don't require a real
  browser in the suite). Add a test that `run_live(ctx=None)` now *registers* an emet_handler (so it's no longer
  silently absent), without making a live call in CI.

## Work-item 2 — cheap-live controls (haiku model + optional mock-personas)
- **Model pass-through:** in `harness/dispatch.py::dispatch_claude`, if `CLAUDE_MODEL` (env) is set, add
  `["--model", CLAUDE_MODEL]` to the `claude` command (mirror `serve.py`, which already reads `CLAUDE_MODEL`).
  Additive + backward-compatible (unset → current default behavior). Add a unit test that the flag is included when
  the env is set (inject a fake runner capturing argv; no live claude).
- **A cheap-live front-end profile:** add a 3rd Chainlit chat profile in `frontend/` — e.g. **"Live (cheap)"** —
  that runs the real firm but (a) sets the agents to **haiku** (via `CLAUDE_MODEL`/the model seam) and/or (b)
  injects a **mock persona runner** so the Bucket-2 roundtable is mocked while Bucket-1 facts (moat, EMET, seams,
  corpora, Q-Models) are real. Pick the cleanest of: model=haiku for everything, OR real facts + mock personas, OR
  both as two toggles. Label it honestly in the UI (the render already shows provenance/`mock` verbatim — keep that).
- Keep the **engine stdlib-only**; all model/persona wiring stays in `frontend/` + the existing harness seam. No
  fabrication: a mocked persona must render as `mock` provenance (as the Demo profile already does).

## Definition of done
- `run_live(ctx=None)` wires a real `emet_handler` (lazy) — EMET either fires live against the user's session, or
  abstains with an honest "login/session" note (+ a HELP entry if true reuse needs a design call).
- `CLAUDE_MODEL` controls the agent model via `--model`; a "Live (cheap)" front-end profile runs real facts with
  haiku and/or mocked personas, clearly labeled.
- Suite green; engine stays stdlib-only; data boundary intact (EMET = external plane, public identifiers only).
- Gates 1–5. Hand to Head Claude (don't self-merge).

## Constraints
- **Don't touch `vendor/`.** Don't break the existing Demo/Live profiles or the run_live contract (additive only).
- Engine import graph stays stdlib (lazy-import the EMET handler + any heavy deps).
- If EMET session-reuse can't be solved cleanly here, **ship the honest-abstain + HELP escalation** rather than a
  fragile or fake-live path. Honesty over a demo that overclaims.
