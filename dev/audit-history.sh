#!/usr/bin/env bash
# Backup detective control — audits commit history for rule violations.
# Replaces the (unavailable) GitHub Action: run this locally, periodically, and before
# trusting `main` (e.g. before a leadership deck or a round close). Reports + exits non-zero
# if it finds a problem.
#
# Usage:  bash dev/audit-history.sh [<range>]      # default: origin/main
# The Built-By + secret checks only consider commits authored on/after the convention-adoption
# date (SAPPHIRE_AUDIT_SINCE, default 2026-06-22) — pre-collaboration history is exempt.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1
RANGE="${1:-origin/main}"
SINCE="${SAPPHIRE_AUDIT_SINCE:-2026-06-22}"
git fetch -q origin 2>/dev/null || true

problems=0
echo "Auditing: $RANGE  (commits since $SINCE)"

# 1. Every non-merge commit (since the convention) must carry a valid Built-By trailer.
echo "── Built-By attribution ──"
while read -r sha; do
  [ -z "$sha" ] && continue
  # skip merge commits (2+ parents)
  if [ "$(git rev-list --parents -n1 "$sha" | wc -w)" -gt 2 ]; then continue; fi
  bb="$(git show -s --format=%B "$sha" | git interpret-trailers --parse 2>/dev/null | sed -n 's/^Built-By:[[:space:]]*//p' | head -1)"
  if [[ ! "$bb" =~ ^(rohan|hayes|gavin)$ ]]; then
    echo "  ✗ $(git show -s --format='%h %s' "$sha") — missing/invalid Built-By ('$bb')"
    problems=$((problems + 1))
  fi
done < <(git rev-list --no-merges --since="$SINCE" "$RANGE")
[ "$problems" -eq 0 ] && echo "  ✓ all non-merge commits since $SINCE attributed"

# 2. No secrets anywhere in the range's diffs.
#    Note: bio-safe — protein/DNA sequences are pure letters, so the AWS pattern is word-bounded
#    AND must contain a digit (AKIARPKKRAETIRFSQHAV and friends must not false-positive).
echo "── Secret scan ──"
added="$(git log -p --since="$SINCE" "$RANGE" 2>/dev/null | grep -E '^\+' || true)"
safe="$(printf '%s' "$added" | grep -EI 'gh[pousr]_[A-Za-z0-9]{20,}|BEGIN ([A-Z]+ )?PRIVATE KEY|xox[baprs]-[A-Za-z0-9-]{10,}|aws_secret_access_key[[:space:]]*=[[:space:]]*[A-Za-z0-9/+]{40}' || true)"
aws="$(printf '%s' "$added" | grep -oE '\bAKIA[A-Z0-9]{16}\b' | grep -E '[0-9]' || true)"
if [ -n "$safe$aws" ]; then
  echo "  ✗ possible secret(s) found in history:"; printf '%s\n%s\n' "$safe" "$aws" | grep -v '^$' | head -5; problems=$((problems + 1))
else
  echo "  ✓ no secret patterns in range"
fi

echo
if [ "$problems" -eq 0 ]; then
  echo "AUDIT CLEAN."
else
  echo "AUDIT FOUND $problems problem(s) — investigate before trusting this range."
fi
exit $([ "$problems" -eq 0 ] && echo 0 || echo 1)
