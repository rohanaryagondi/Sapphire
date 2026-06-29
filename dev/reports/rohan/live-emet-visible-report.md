# live-emet-visible — report (Task 1: real EMET in a shared VISIBLE browser)

**Branch:** `rohan/live-emet-visible` · **Built-By:** rohan · **Supersedes:** #77 (held — headless path).

## Why
Head Claude's Gate-5 on #77: real moat ✓ + 🧪-simulated labeling ✓, but `emet-runner` landed **no
PMIDs** — `_default_runner` launched a **separate, *headless*, invisible** `npx @playwright/mcp`
browser (`--user-data-dir`) that hit a login wall. Real EMET is confirmed working when driven in the
**shared, visible, already-authenticated** browser. Task 1: re-architect to that.

## What changed (carries #77's good content + the re-architecture)
- **`emet/handler.py` — drive a VISIBLE browser via CDP, never a silent invisible one.**
  `_resolve_emet_cdp()`: explicit `$SAPPHIRE_EMET_CDP` → else **auto-detect** a reachable CDP browser
  on `$SAPPHIRE_EMET_CDP_PORT` (default 9222, stdlib `urllib` probe). `_emet_mcp_config()` precedence:
  **CDP (explicit/auto-detected) → opt-in headless profile (`$SAPPHIRE_EMET_ALLOW_HEADLESS=1`, the
  old invisible path, now never the silent default) → honest abstain**. So a Live run reuses the
  shared authenticated browser and the EMET query opens a **second VISIBLE tab**.
- **`_build/sapphire_live_demo.sh`** — the demo launcher: refresh the dedicated session (headless
  auto-login), then open ONE **visible** authenticated Chrome (CDP :9222) with the Sapphire console as
  tab 1. The runner auto-detects :9222 and opens EMET as tab 2 in the same window — Sapphire + EMET,
  side by side, watchable. (Plus the existing `_build/emet_login.sh --manual` route.)
- Carries from #77 (so it isn't lost): the **simulate-models** mode (`🧪`-labeled persona/claude-fact
  reasoning, provenance `simulated`), the **per-agent timeout cap** (`$SAPPHIRE_AGENT_TIMEOUT_S`), the
  bounded EMET timeout (`$SAPPHIRE_EMET_TIMEOUT_S`), and honest-abstain.
- **Fallback:** if CDP is unreliable, the proven in-session capture (`emet/session_bridge.py`, #57)
  injects a captured envelope. Docs: `emet/LIVE_EMET.md`.

## Verification
- **Offline:** `emet.tests.test_handler` green incl. new precedence tests — explicit CDP, **auto-detected
  visible CDP preferred**, headless **requires opt-in**, CDP beats headless, none-reachable → abstain
  (a closed port → `_default_runner` → `login_required`). Full Gate-1 green (see PR).
- **Gate-5 (Head Claude watches both tabs):** run the launcher + a `Live (demo · simulated models)`
  TSC2 query → Sapphire in tab 1, EMET opens tab 2 visibly and returns real `emet-live` PMIDs. The CDP
  endpoint a headed Chrome exposes is reachable (verified earlier); the visible-tab + real-PMID landing
  is the browser-verify. Honest-abstain stays when no session.

## Safety
Public identifiers only cross to EMET; password never printed/logged/committed; `RohanOnly/` + the
profile + venv gitignored; engine stdlib-only; captured-scenario replay unaffected.
