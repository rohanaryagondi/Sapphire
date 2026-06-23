#!/usr/bin/env bash
# One-time per-clone setup for a Sapphire contributor (run by you or your Claude
# the first time you work in this repo). Wires the branch-rule guardrails.
#
# Usage:  bash dev/setup-contributor.sh <handle>      # handle ∈ rohan | hayes | gavin
set -euo pipefail

git rev-parse --git-dir >/dev/null 2>&1 || { echo "Error: run this from inside the Sapphire repo."; exit 1; }

handle="${1:-}"
case "$handle" in
  rohan|hayes|gavin) ;;
  *) echo "Usage: bash dev/setup-contributor.sh <handle>   (handle ∈ rohan | hayes | gavin)"; exit 1 ;;
esac

# 1. Use the version-controlled hooks (pre-push + commit-msg).
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

# 2. Record who this clone belongs to (the pre-push hook enforces the prefix).
git config sapphire.handle "$handle"

# 3. Encourage a matching git identity for the Built-By attribution.
echo "Configured this clone for contributor: $handle"
echo "  core.hooksPath = .githooks   (pre-push + commit-msg guards active)"
echo "  sapphire.handle = $handle"
echo
echo "Branch rules now enforced locally:"
echo "  • No direct pushes to main (or any protected branch) — open a PR."
echo "  • Branches must be named  $handle/<slug>."
echo "  • Every commit must carry a 'Built-By: $handle' trailer."
echo
echo "Do NOT bypass with --no-verify (hard violation — see dev/CONTRIBUTOR_RULES.md)."
echo "Read dev/CONTRIBUTOR_RULES.md and dev/CONTRIBUTORS.md before you start."
