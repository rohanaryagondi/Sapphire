# Task brief — real live EMET from the front-end (a genuinely real live run)

*Owner: **rohan** (Rohan Claude builds; Head Claude reviews/gates + browser-verifies a real PMID lands). Tier: **Feature**.
Created 2026-06-25. Priority: HIGH — the demo's live button must produce REAL data, not failed/abstaining EMET.*

## The problem (observed, with the new step-tree visibility)
A front-end **Live (cheap · haiku)** run now streams transparently — and that exposed the truth: **EMET fails** in
a live run (`⚠ escalated — tool-failure · emet-live · 0.94s`). Root cause: the front-end EMET path shells a
**detached `claude -p`** (`emet/handler.py::_default_runner`) that drives a **fresh, unauthenticated** Playwright
browser — it cannot reach the BenchSci session the user logged into. So front-end live EMET never returns real PMIDs.
(Moat is real — the earlier "0 facts" was a worktree missing the gitignored `RohanOnly/moat/moat.sqlite`; on the
real server `moat_facts('TSC2')` → 8 real signatures. Q-Models is honest-labeled. EMET is the gap.)

The fully-real run (real moat + real EMET PMIDs + real personas) ALREADY works via **in-session capture** (a Claude
session driving the authenticated browser → envelope → `session_bridge` → run_live; this produced the captured
scenario). Goal here: make the **front-end Live button** do a genuinely real run too — including **real EMET PMIDs**.

## Approach (primary: a dedicated authenticated browser profile the EMET runner reuses)
- The EMET runner's Playwright (inside the `claude -p` subprocess, or a direct Playwright call) must use a
  **dedicated persistent Chrome profile** that holds a logged-in BenchSci session — `--user-data-dir=$SAPPHIRE_EMET_PROFILE`
  (a path env, e.g. `RohanOnly/emet_profile/`). One-time login: a small `frontend/` (or `_build/`) **"emet-login"**
  helper opens that profile's browser → user signs into `emet.benchsci.com` once → the session persists on disk →
  every subsequent front-end live run's EMET subprocess opens that profile already authenticated.
- **Profile-lock caveat (handle it):** Chrome locks a user-data-dir to one running instance. The runner's profile
  must be **dedicated** (not the user's everyday browser) so the runner can open it without contention. Document
  that the login helper must be closed before a run (or use a copy-on-run of the profile).
- **Alternative if cleaner:** CDP-connect (`playwright connect_over_cdp`) to an already-running authenticated browser
  exposing a remote-debugging endpoint (`$SAPPHIRE_EMET_CDP`). Investigate both; ship whichever reliably lands a
  real PMID. (EMET-MCP remains the durable future answer; this is the interim.)
- **Honesty preserved:** if no authenticated profile/endpoint is available → the existing **honest abstain**
  (login_required/escalate, never fabricate). Real PMIDs only when the session is genuinely reachable.

## Definition of done (Head Claude browser-verifies)
- A front-end **Live (cheap · haiku)** TSC2 run lands **≥1 real `emet-live` PMID** in the external plane (the step
  tree shows EMET `✓ N PMIDs`, not `tool-failure`) — verified by Head Claude watching a real run in the browser.
- Without an authenticated profile → honest abstain (unchanged), clearly labeled.
- A documented one-time **emet-login** step (how the user authenticates the runner's profile).
- **Credential-at-rest:** the authenticated profile on disk is an internal-only artifact (user-approved for the
  internal demo) — gitignored (`RohanOnly/`), documented, never committed.
- Suite green; engine stdlib; vendor untouched; agent outputs/guards/provenance unchanged; the in-session capture
  path + replay + honest-abstain all still work.
- Gates 1–5 (Feature → 6). Hand to Head Claude; don't self-merge.

## Also (perf, from the same observation)
- A single live run spawned **11 `claude -p` haiku procs for >5 min** — confirm `dispatch_claude` has a sane
  per-agent timeout and the concurrency is bounded; surface per-agent elapsed (done by the step tree now). If
  agents hang, lower the timeout so a stuck agent abstains visibly rather than blocking the run.

## Constraints
- No fabrication — real PMIDs only from a real session; otherwise abstain. Don't break the captured-scenario replay
  (the demo's reliable path) or the honest-abstain default. Credential artifact stays in gitignored `RohanOnly/`.

---

## UPDATE (Rohan, 2026-06-25) — creds provided, auto-login authorized, + simulate model calls for now
- **EMET creds are provided** in the **gitignored** file `RohanOnly/emet_creds.env` (`SAPPHIRE_EMET_USER`,
  `SAPPHIRE_EMET_PASS`, `SAPPHIRE_EMET_PROFILE`). Read them from there (or the env) — **never** read/print/commit
  the password; never put it in any tracked file, log, report, or commit message. `RohanOnly/` is gitignored.
- **Auto-login is AUTHORIZED** for the dedicated profile: the emet-login helper may sign into BenchSci using those
  creds (one-time, into `$SAPPHIRE_EMET_PROFILE`), so **all agents reuse that authenticated session**. (This relaxes
  the skill's "never auto-login" rule ONLY for this dedicated tester profile, per Rohan.) Honest-abstain still applies
  if login fails / session expires.
- **Model calls = SIMULATED for now (clearly labeled).** Per Rohan: the `claude-subagent` model reasoning (personas +
  any claude fact agents) should run as a **labeled simulated response** for the demo — NOT real `claude -p` (which is
  slow/hanging). Add a **"simulate model" mode** (e.g. a `Live (demo · simulated models)` profile or a
  `SAPPHIRE_SIMULATE_MODELS=1` lever) that returns plausible persona/agent outputs with **provenance `simulated`** and a
  clear UI marker (e.g. "🧪 simulated model — real reasoning pending"). HONESTY IS MANDATORY: simulated content must be
  unmistakably labeled simulated everywhere it renders; never presented as a real model verdict. Real EMET + real moat +
  real seams stay REAL; only the model reasoning is simulated. Rohan wires real models in a few hours.
- **Net demo target:** a Live run shows REAL moat + REAL EMET PMIDs (logged-in) + REAL seams/Q-Models + SIMULATED
  (labeled) roundtable/synthesis — fully working, fast, honest. The captured replay (real haiku personas) stays as-is.
