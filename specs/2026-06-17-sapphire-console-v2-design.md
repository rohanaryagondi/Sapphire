# Sapphire Console v2 — Design Spec

**Date:** 2026-06-17
**Owner:** Rohan Gondi
**Status:** Approved (design); implementing.

## Goal

Turn the Console from a stylistic stage-animation into a **proper, functional, honest chat UI**. Two
problems to fix: (1) it's too animated and not interactive; (2) it presents Claude-reconstructed facts
as if they came from live tools (EMET/Q-Models), hiding what isn't wired. The redesign makes the
chat real (multi-turn) and the wiring state explicit (status panel + per-fact provenance).

## Wiring reality (the honesty baseline)

In the **web flow**, only **Claude** (via the subscription bridge) is genuinely live. EMET is **not
queried** for web runs — Claude reconstructs facts from training. Q-Models and the internal moat are
**mock**. Only the two shipped scenarios (`nav1_8`, `tsc2`) carry **real captured EMET evidence**.
The UI must show this, not hide it.

## Layout — split (chat + inspector)

- **Left (~62%) — chat thread.** User bubbles + Sapphire answers; scrollable history; input bar pinned
  bottom (textarea + Send). An answer is a clean structured message: headline + recommendation + a
  "view in inspector" affordance. No lit-stage animation; a "thinking" indicator while a live call runs.
- **Right (~38%) — inspector**, two cards:
  1. **Systems** (always visible): `Claude ● live` · `EMET ○ not wired (web)` · `Q-Models ◍ mock` ·
     `moat ◍ mock`, each with a one-line meaning. The standing honesty surface; flip a dot when a
     subsystem is wired later (Q-Models next).
  2. **Active run**: the selected answer's Dossier (facts + provenance badges + VETO/DIVERGENCE/
     KNOWN-UNKNOWN flags), Roundtable (round 1 + round 2, collapsible), Synthesis. Clicking any
     Sapphire message loads its run here.

## Provenance model (per fact)

Each dossier fact carries a badge for its **true** origin:
- `✓ EMET (captured)` — shipped-scenario facts whose source mentions EMET (real Playwright evidence).
- `◇ Claude (reconstructed)` — **all** facts in a live web run (EMET not queried).
- `◍ mock` — Q-Models / internal-moat facts (source mentions MOCK / Q-Models / moat).

Derivation: the engine/bridge stamps `provenance` on each fact. Shipped scenarios derive it from the
existing `source` string; live runs are stamped `claude` wholesale (the prompt forces Claude to state
it did not query EMET). Live answers also carry a one-line banner making the reconstruction explicit.

## Conversation model (multi-turn)

Frontend holds `messages[]` and `currentRun`. Each send → `POST /api/chat`.
- **Fresh engagement** (planner routes to a scenario, or message names a new target/disease + a
  deliverable): produce a full run — instant for scenarios, one Claude call for novel — rendered as a
  rich answer message and set as the inspector's active run.
- **Follow-up** (no new engagement; references the current run, e.g. "what about cardiac risk?"): one
  Claude call grounded in the current dossier + recent history → a normal chat reply (text, may cite
  dossier fields), **no** new run. Honest: the reply reasons over the current (possibly Claude-
  reconstructed) dossier and says so.

Routing decision is the engine's `triage`/scenario match plus a lightweight "is this a follow-up"
heuristic (short, pronoun/anaphora, no new target named, and a currentRun exists).

## API (bridge — `serve.py`)

- `GET /api/health` → `{live, model, subsystems:{claude,emet,qmodels,moat}}` (unchanged + subsystems).
- `POST /api/chat` → body `{message, history:[{role,content}], current_run_id|current_dossier}`.
  Returns either:
  - `{kind:"run", run:{…canonical run…, provenance stamped}, live, model}` — fresh engagement.
  - `{kind:"reply", text, cites:[field…], live, model}` — follow-up.
  On `claude` failure → `{kind:"reply", text:"<engagement plan> — live brain unavailable", live:false}`.
- Keep `/api/run` as a thin alias (back-compat) or drop; Console uses `/api/chat`.

## Components touched

- `serve.py` — add `/api/chat`, follow-up path, provenance stamping, subsystems in health.
- `site/index.html` — split layout markup (chat pane + inspector pane).
- `site/console.js` — rewritten as a small chat app: message thread, input, multi-turn calls,
  inspector render (systems + dossier w/ provenance + roundtable + synthesis), click-to-load.
- `site/styles.css` — chat + inspector styles; reuse existing tokens/badges.
- `site/explainer.html` / `app.js` — untouched.

## Out of scope (YAGNI)

No EMET/Q-Models wiring this pass (Q-Models next), no accounts/persistence, no token streaming,
no server-side session store (history lives in the frontend and is sent per call).

## Success criteria / verification

- `serve.py` runs; `/api/health` returns subsystems; `/api/chat` handles a scenario message (run),
  a follow-up (reply), and a novel query (live run, all facts badged `Claude (reconstructed)`).
- In-browser: split layout renders; sending messages builds a thread; clicking an answer loads the
  inspector; systems panel shows the honest state; 0 JS errors.
- Static (no bridge): chat still works for the two shipped scenarios + shows the plan honestly for
  anything else; systems panel shows EMET/Q-Models/moat states.
