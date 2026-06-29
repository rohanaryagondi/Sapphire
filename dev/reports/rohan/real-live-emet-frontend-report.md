# real-live-emet-frontend — report

**Branch:** `rohan/real-live-emet-frontend` · **Built-By:** rohan · **Tier:** Feature

## Goal (+ the 2026-06-25 brief UPDATE)
Make a front-end **Live** run genuinely real: real **EMET PMIDs** (logged-in) + real moat/seams/Q-Models,
with the persona/claude-fact **model reasoning SIMULATED (clearly labeled)** for now so the demo is fast.
Plus: bound the per-agent claude timeout.

## What I built (the rest was pre-staged on main by Head Claude — see below)

### 1. Real live EMET via a dedicated authenticated browser (`emet/handler.py`)
The detached `claude -p` EMET runner now pins its Playwright MCP to a **dedicated authenticated browser**
instead of a fresh, unauthenticated one:
- `_emet_mcp_config()` builds a `--mcp-config` for `@playwright/mcp` using **`$SAPPHIRE_EMET_CDP`** (connect
  to a running authenticated browser — preferred, no profile-lock) or **`$SAPPHIRE_EMET_PROFILE`** (a dedicated
  persistent profile authenticated once). `--strict-mcp-config` + scoped `--allowedTools`.
- **Honest abstain unchanged:** neither env set, or session expired → `{"login_required": true}` →
  the EMET agent abstains (no more `tool-failure`, never a fabricated PMID).
- **Auto-login (authorized for this tester profile):** when `RohanOnly/emet_creds.env` (or `$SAPPHIRE_EMET_USER`/
  `_PASS`) is present, the runner is told it MAY sign in — it **reads the password from the gitignored file
  itself**; the password never touches this process, argv, logs, or any tracked file. (`Read` is added to the
  runner's allowed tools only then.)
- `_build/emet_login.sh` — one-time login helper (dedicated Chrome + CDP). Docs: `emet/LIVE_EMET.md`.
- **Timeout:** `_emet_timeout_s()` bounds a live EMET run (`$SAPPHIRE_EMET_TIMEOUT_S`, default 240, floor 30).

### 2. Simulate-models mode — frontend wiring
The engine hook (`dispatch.py::_simulate_claude` + the `simulated` provenance) was **pre-staged on main**.
I wired the front end to it:
- `bridge.run(..., simulate=True)` sets/restores `SAPPHIRE_SIMULATE_MODELS` around the run; stamps `_simulated`.
- `main.py` — a **`Live (demo · simulated models)`** profile (real backends + simulated claude reasoning) +
  a prominent **🧪 banner** so the labeling is unmistakable. Honest: real moat/EMET/seams stay real; only
  persona + claude-fact-agent reasoning is the labeled `🧪 simulated` stand-in (provenance `simulated`).

### 3. Per-agent claude timeout cap (`harness/dispatch.py`)
`_agent_timeout(contract_timeout_s)` caps the subprocess timeout by `$SAPPHIRE_AGENT_TIMEOUT_S` (min with the
contract; floor 30) on both `dispatch_claude` and `dispatch_claude_batch` — a stuck agent abstains visibly.

## Verification
- **Gate 1:** `bash dev/run-tests.sh` → **577 GREEN** (incl. the pre-staged `TestSimulateModelsRunLive`,
  which needed a `validate_run_live` import — fixed). New tests: EMET auth-gating/auto-login/timeout (handler),
  simulate-models + timeout-cap (dispatch), simulate + profile-mapping (frontend).
- **Plumbing verified (cheap, no creds):** a dedicated-profile Chrome with `--remote-debugging-port` exposes a
  reachable CDP endpoint (`webSocketDebuggerUrl`) — the runner's `--cdp-endpoint` target is real.
- **Simulate path verified offline:** a `bridge.run(simulate=True)` TSC2 run → 5 personas all `provenance:
  simulated` + `🧪` rationale, while moat stays `moat-real`/internal; run_live contract valid.
- **Gate 5 — Head Claude browser-verifies (per the brief):** a real `emet-live` PMID landing requires the
  one-time BenchSci login into the dedicated profile (creds I don't hold). The mechanism + honest-abstain +
  the simulate UI are in place + offline-tested; the authenticated browser-verify is Head Claude's.

## Safety / honesty
- Credential-at-rest (`RohanOnly/emet_creds.env`, `RohanOnly/emet_profile/`) is gitignored (all of `RohanOnly/`);
  the password is never read by this process, logged, or committed.
- Simulated content is unmistakably labeled (🧪 markers in every text field + provenance `simulated` + a banner).
- Engine stays stdlib-only; `vendor/` untouched; the captured-scenario replay + honest-abstain default unbroken.
