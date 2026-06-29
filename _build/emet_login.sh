#!/usr/bin/env bash
# Authenticate the DEDICATED EMET browser profile so front-end Live runs land REAL PMIDs.
#
#   bash _build/emet_login.sh            # AUTO: log in with the provided creds (headless)
#   bash _build/emet_login.sh --manual   # MANUAL: open a headed Chrome to sign in by hand (SSO/2FA)
#
# Creds come from the GITIGNORED RohanOnly/emet_creds.env (SAPPHIRE_EMET_USER / _PASS / _PROFILE).
# The password is never printed/logged/committed. After it succeeds, run live with EITHER:
#   export SAPPHIRE_EMET_PROFILE="$PWD/RohanOnly/emet_profile"   # profile route (close this first)
#   export SAPPHIRE_EMET_CDP=http://localhost:9222               # CDP route (manual window stays open)
# If no authenticated session is reachable, the EMET agent abstains honestly — never fabricates.
set -euo pipefail

CREDS="${SAPPHIRE_EMET_CREDS:-RohanOnly/emet_creds.env}"
[ -f "$CREDS" ] && { set -a; . "$CREDS"; set +a; } || echo "note: $CREDS not found — relying on the environment"
PROFILE="${SAPPHIRE_EMET_PROFILE:-$PWD/RohanOnly/emet_profile}"
export SAPPHIRE_EMET_PROFILE="$PROFILE"
mkdir -p "$PROFILE"

if [ "${1:-}" = "--manual" ]; then
  PORT="${SAPPHIRE_EMET_CDP_PORT:-9222}"
  CHROME="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
  [ -x "$CHROME" ] || { echo "ERROR: Chrome not at '$CHROME' (set CHROME_BIN)." >&2; exit 1; }
  echo "Manual login — sign into https://emet.benchsci.com/ in the window, then:"
  echo "  • keep it open + export SAPPHIRE_EMET_CDP=http://localhost:$PORT   (CDP route), or"
  echo "  • close it + export SAPPHIRE_EMET_PROFILE=$PROFILE                  (profile route)"
  exec "$CHROME" --user-data-dir="$PROFILE" --remote-debugging-port="$PORT" \
       --no-first-run --no-default-browser-check "https://emet.benchsci.com/"
fi

# AUTO route — bootstrap an isolated playwright venv (gitignored) if needed, then run the login.
VENV="${SAPPHIRE_EMET_VENV:-.emet-venv}"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Bootstrapping playwright venv at $VENV (one-time)…"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install --upgrade pip >/dev/null
  "$VENV/bin/pip" -q install playwright >/dev/null
  "$VENV/bin/python" -m playwright install chromium >/dev/null
fi
echo "Auto-login (headless) into $PROFILE …"
set +e
"$VENV/bin/python" _build/emet_login.py
rc=$?
set -e
if [ "$rc" = "2" ]; then
  echo ""
  echo "Auto-login could not complete (likely SSO/2FA). Falling back to MANUAL:"
  echo "    bash _build/emet_login.sh --manual"
  exit 2
fi
exit "$rc"
