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

## Then pick a route (set ONE env, then run a Live query)
| Route | Env | Notes |
|---|---|---|
| **Persistent profile** | `export SAPPHIRE_EMET_PROFILE="$PWD/RohanOnly/emet_profile"` | The auto-login default. Close any login window first — Chrome locks a user-data-dir. |
| **CDP** | `export SAPPHIRE_EMET_CDP=http://localhost:9222` | Keep the `--manual` window **open**; the runner connects to it. No profile-lock. |

`SAPPHIRE_EMET_CDP` wins if both are set. With one set, a Live run's EMET agent reuses the
authenticated browser and lands real `emet-live` PMIDs (the live step tree shows `EMET … ✓ N PMIDs`).

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
