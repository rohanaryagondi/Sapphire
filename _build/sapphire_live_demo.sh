#!/usr/bin/env bash
# Sapphire VISIBLE live-EMET demo launcher (Task-1 re-architecture).
#
# Opens ONE visible, authenticated Chrome with a CDP endpoint on :9222 and the Sapphire console as
# tab 1. A "Live (demo · simulated models)" run then drives the real EMET query in a SECOND VISIBLE
# tab of THIS browser (the EMET runner auto-detects the CDP endpoint — see emet/handler.py
# `_resolve_emet_cdp`). So you watch Sapphire convene + the real EMET PMIDs land, side by side.
#
#   1. Serve the console (separate shell):  cd frontend && chainlit run main.py   # → http://localhost:8000
#   2. bash _build/sapphire_live_demo.sh                                          # auth + open visible Chrome
#   3. export SAPPHIRE_EMET_CDP=http://localhost:9222                             # (printed below)
#   4. In the console, pick "Live (demo · simulated models)" and ask the TSC2 question.
#      → EMET opens a 2nd visible tab here and returns real emet-live PMIDs.
#
# Creds come from the gitignored RohanOnly/emet_creds.env; the password is never printed/logged.
# If the session can't be established, the EMET agent abstains honestly — it never fabricates.
set -euo pipefail
cd "$(dirname "$0")/.."                                          # repo root

CREDS="${SAPPHIRE_EMET_CREDS:-RohanOnly/emet_creds.env}"
[ -f "$CREDS" ] && { set -a; . "./$CREDS"; set +a; } || echo "note: $CREDS not found — relying on the environment"
PROFILE="${SAPPHIRE_EMET_PROFILE:-$PWD/RohanOnly/emet_profile}"
export SAPPHIRE_EMET_PROFILE="$PROFILE"
PORT="${SAPPHIRE_EMET_CDP_PORT:-9222}"
CONSOLE_URL="${SAPPHIRE_CONSOLE_URL:-http://localhost:8000}"
CHROME="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] || { echo "ERROR: Chrome not at '$CHROME' (set CHROME_BIN)." >&2; exit 1; }
mkdir -p "$PROFILE"

# 1) Make sure the dedicated profile holds a live BenchSci session (headless auto-login; safe to
#    re-run — it no-ops if already authenticated). If it can't (SSO/2FA), the headed window below
#    still lets you sign in by hand, and the runner abstains honestly until then.
if [ -x "${SAPPHIRE_EMET_VENV:-.emet-venv}/bin/python" ]; then
  echo "Refreshing the dedicated EMET session (headless)…"
  SAPPHIRE_EMET_HEADLESS=1 "${SAPPHIRE_EMET_VENV:-.emet-venv}/bin/python" _build/emet_login.py || \
    echo "  (auto-login did not complete — sign in by hand in the window that opens)"
else
  echo "note: no .emet-venv — run 'bash _build/emet_login.sh' once to bootstrap headless auto-login."
fi

echo ""
echo "Opening the VISIBLE authenticated Chrome (CDP :$PORT) with the Sapphire console…"
echo "  → Then run, in another shell:  export SAPPHIRE_EMET_CDP=http://localhost:$PORT"
echo "  → In the console tab, pick 'Live (demo · simulated models)' and ask the TSC2 question."
echo "  → EMET will open a SECOND visible tab in THIS window and return real PMIDs."
# Headed Chrome: tab 1 = Sapphire console; the EMET runner opens tab 2 here via CDP. Visible, authenticated.
exec "$CHROME" \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port="$PORT" \
  --no-first-run --no-default-browser-check \
  "$CONSOLE_URL"
