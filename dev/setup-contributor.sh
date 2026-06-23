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

# 1. Use the version-controlled hooks (pre-commit + commit-msg + pre-push).
git config core.hooksPath .githooks
chmod +x .githooks/* dev/*.sh 2>/dev/null || true

# 2. Record who this clone belongs to (the pre-push hook enforces the prefix).
git config sapphire.handle "$handle"

# 3. Encourage a matching git identity for the Built-By attribution.
echo "Configured this clone for contributor: $handle"
echo "  core.hooksPath = .githooks   (pre-commit + commit-msg + pre-push guards active)"
echo "  sapphire.handle = $handle"
echo
echo "Guards now active locally:"
echo "  • pre-commit : blocks staging obvious secrets (tokens, keys, .env)."
echo "  • commit-msg : requires a 'Built-By: $handle' trailer matching your handle."
echo "  • pre-push   : no pushes to main / wrong branch names; and if the push"
echo "                 changes any Python, the full suite must pass first (Gate 1)."
echo
echo "Do NOT bypass with --no-verify (hard violation — see dev/CONTRIBUTOR_RULES.md)."
echo "Read dev/CONTRIBUTOR_RULES.md and dev/CONTRIBUTORS.md before you start."
