#!/usr/bin/env bash
# Enable branch protection on main for rohanaryagondi-quiver/Sapphire.
#
# Prereq: the rohanaryagondi-quiver account must be on GitHub Pro (or the repo in a
# paid org). On the free tier this returns HTTP 403 ("Upgrade to GitHub Pro …").
#
# Usage:  GH_TOKEN=<admin PAT for rohanaryagondi-quiver> bash dev/enable-branch-protection.sh
# The token is read from the environment ONLY — never hard-code it here or commit it.
set -euo pipefail

REPO="rohanaryagondi-quiver/Sapphire"
BRANCH="main"

: "${GH_TOKEN:?Set GH_TOKEN to an admin PAT for rohanaryagondi-quiver (do not commit it)}"

echo "Applying branch protection to ${REPO}@${BRANCH} …"
gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo
echo "Verifying …"
gh api "repos/${REPO}/branches/${BRANCH}/protection" \
  --jq '{pr_review: .required_pull_request_reviews, code_owners: .required_pull_request_reviews.require_code_owner_reviews, force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, linear: .required_linear_history.enabled}'

echo
echo "Done. main now requires a reviewed PR with CODEOWNERS (@rohanaryagondi-quiver) approval."
echo "enforce_admins is FALSE so the owner retains an emergency override; the documented flow is PR-only."
