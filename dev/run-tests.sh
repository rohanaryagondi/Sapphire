#!/usr/bin/env bash
# Canonical Gate-1 runner — the single source of truth for "the full suite is green".
# Used by the pre-push hook (before any push that touches Python) and by humans/agents
# running Gate 1 manually. Offline, $0. Exits non-zero if any suite fails.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/sapphire-orchestrator" || { echo "run-tests: cannot find sapphire-orchestrator"; exit 1; }

fail=0
total=0
for s in contracts harness emet memory selfimprove moat; do
  out="$(python -m unittest discover -s "$s/tests" 2>&1)"
  n="$(printf '%s' "$out" | grep -oE 'Ran [0-9]+' | grep -oE '[0-9]+' | head -1)"
  if printf '%s' "$out" | grep -qE '^OK'; then
    echo "  ✓ $s (${n:-0})"; total=$((total + ${n:-0}))
  else
    echo "  ✗ $s FAILED"; printf '%s\n' "$out" | tail -8; fail=1
  fi
done
# top-level suite (note: -s tests, not tests/tests)
out="$(python -m unittest discover -s tests 2>&1)"
n="$(printf '%s' "$out" | grep -oE 'Ran [0-9]+' | grep -oE '[0-9]+' | head -1)"
if printf '%s' "$out" | grep -qE '^OK'; then
  echo "  ✓ tests (${n:-0})"; total=$((total + ${n:-0}))
else
  echo "  ✗ tests FAILED"; printf '%s\n' "$out" | tail -8; fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "Gate 1 GREEN — $total tests."
else
  echo "Gate 1 RED — fix before pushing."
fi
exit $fail
