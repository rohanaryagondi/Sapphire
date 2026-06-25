# Live EMET from the front end — real PMIDs (+ simulated-models demo mode)

A front-end **Live** run drives the EMET agent through a detached `claude -p` subprocess. By
default that subprocess's Playwright opens a **fresh, unauthenticated** browser that can't reach
your BenchSci session → `⚠ tool-failure`, no real PMIDs. To get **real** EMET PMIDs, point the
runner at a **dedicated authenticated browser**, set up once by the login helper.

## One-time login (creds in the gitignored `RohanOnly/emet_creds.env`)
```bash
bash _build/emet_login.sh            # AUTO: headless login with SAPPHIRE_EMET_USER/_PASS into the profile
bash _build/emet_login.sh --manual   # MANUAL: opens a headed Chrome to sign in by hand (SSO/2FA)
```
The password is read from the env only — **never printed, logged, or committed**. Auto-login
bootstraps an isolated, gitignored playwright venv (`.emet-venv`). If BenchSci uses SSO/2FA and the
password flow can't complete, the helper exits 2 and tells you to use `--manual`.

## The VISIBLE demo (recommended) — one launcher, two watchable tabs
```bash
cd frontend && chainlit run main.py        # shell A: serve the console → http://localhost:8000
bash _build/sapphire_live_demo.sh          # shell B: auth + open a VISIBLE authenticated Chrome (CDP :9222)
```
The launcher opens ONE visible authenticated Chrome with the Sapphire console as **tab 1**. Pick the
**"Live (demo · simulated models)"** profile and ask the TSC2 question — the EMET runner auto-detects
the CDP endpoint and opens the real EMET query in a **second VISIBLE tab of the same window**, landing
real `emet-live` PMIDs. You watch Sapphire convene + the PMIDs arrive, side by side.

## How the runner picks a browser (Task-1 precedence)
The runner drives a **shared VISIBLE authenticated browser via CDP** — never a silent invisible one
(`emet/handler.py::_resolve_emet_cdp`):
| Order | Source | Notes |
|---|---|---|
| 1 | explicit `$SAPPHIRE_EMET_CDP` | e.g. `http://localhost:9222` — connect to that browser. |
| 2 | **auto-detected** CDP on `$SAPPHIRE_EMET_CDP_PORT` (default 9222) | so the demo "just works" + stays **watchable** when the launcher's Chrome is up. |
| 3 | `$SAPPHIRE_EMET_PROFILE` **only if** `$SAPPHIRE_EMET_ALLOW_HEADLESS=1` | a separate **invisible** headless browser — opt-in, never the silent default (it was the Gate-5 failure mode). |
| 4 | none reachable | **honest abstain** (`login_required`) — run the launcher / `_build/emet_login.sh --manual` first. |

A Live run then reuses that authenticated browser and lands real `emet-live` PMIDs (the live step tree
shows `EMET … ✓ N PMIDs`). **Fallback:** if CDP is unreliable, the proven in-session capture path
(`emet/session_bridge.py`, #57) injects a captured envelope instead.

## Simulated-models demo mode (fast, fully labeled)
Real `claude -p` reasoning (personas + claude fact agents) is slow/can hang. The **`Live (demo ·
simulated models)`** front-end profile (or `SAPPHIRE_SIMULATE_MODELS=1`) replaces ONLY that model
reasoning with a **clearly-labeled** stand-in — `🧪 simulated model — real reasoning pending`,
**provenance `simulated`** — so the run is fast. **Real EMET PMIDs + real moat + real seams/Q-Models
stay genuinely REAL.** Honesty is enforced mechanically: simulated content carries the 🧪 marker and
the `simulated` provenance everywhere it renders, and a banner heads every simulated run — it can
never be mistaken for a real verdict. (`harness/guardrails.py::stamp_provenance` stamps `simulated`
for claude-subagents in this mode; non-claude agents keep their genuine label.)

## Honesty & safety
- **No authenticated session, or it expired** → the runner returns `{"login_required": true}` → the
  EMET agent **abstains honestly** (`login-required`). It never fabricates a PMID.
- **Credential-at-rest:** the authenticated profile (and `emet_creds.env`, `.emet-venv`) are
  **internal-only**, gitignored under `RohanOnly/` / the repo root. Never commit them.
- **Public identifiers only** still cross to EMET (the data boundary is unchanged).
- **Timeouts:** a Live EMET run is bounded by `SAPPHIRE_EMET_TIMEOUT_S` (default 240s); per-agent
  claude timeouts are capped by `SAPPHIRE_AGENT_TIMEOUT_S` (`harness/dispatch.py`) — a stuck agent
  abstains visibly instead of hanging the firm.

The in-session capture path (`_build/capture_tsc2_live.py`) and the `$0` replay are unaffected — they
inject the envelope directly and don't use this live runner.
