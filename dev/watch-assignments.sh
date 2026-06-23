#!/usr/bin/env bash
# dev/watch-assignments.sh <handle> <github-username>
#
# The autonomous-contributor watcher. A contributor's Claude runs this as a background
# Monitor; each stdout line is an event telling the agent something needs its attention,
# so it can run continuously with no human prompting. It watches TWO channels:
#
#   [board]      origin/main : status/WORKBOARD.md + dev/HELP.md
#                 → a new/updated assignment under your handle, OR an answer to one of your
#                   HELP requests, OR (when the approver merges your PR) the cue to start the
#                   next task. These files change on main only when the approver merges.
#   [pr-review]  your open PRs : a new review or comment from the approver
#                 → address requested changes on the same branch + push, or proceed if approved.
#
# It never fires on your own feature-branch pushes (those don't touch main, and a self-comment
# isn't an approver comment). Resilient to transient network/gh errors (won't emit false events).
#
# Usage (typically via the Monitor tool, persistent):
#   bash dev/watch-assignments.sh hayes HayesStewart-QuiverBS
set -uo pipefail

handle="${1:?usage: watch-assignments.sh <handle> <github-username>}"
ghuser="${2:?usage: watch-assignments.sh <handle> <github-username>}"
APPROVER="rohanaryagondi"
INTERVAL="${SAPPHIRE_WATCH_INTERVAL:-90}"

# Signature of the two main-side coordination docs (assignments + answered help).
board_sig() {
  git fetch -q origin main 2>/dev/null || true
  { git show origin/main:status/WORKBOARD.md 2>/dev/null
    echo "---HELP---"
    git show origin/main:dev/HELP.md 2>/dev/null
  } | shasum | awk '{print $1}'
}

# Latest approver review/comment timestamp across this contributor's OPEN PRs ("" if none).
pr_sig() {
  local nums n
  nums="$(gh pr list --author "$ghuser" --state open --json number --jq '.[].number' 2>/dev/null || true)"
  [ -z "$nums" ] && { echo ""; return; }
  for n in $nums; do
    gh pr view "$n" --json reviews,comments \
      --jq "[ (.reviews[]?|select(.author.login==\"$APPROVER\")|.submittedAt),
              (.comments[]?|select(.author.login==\"$APPROVER\")|.createdAt) ] | max // empty" \
      2>/dev/null || true
  done | sort | tail -1
}

pm="$(board_sig)"
pp="$(pr_sig)"
echo "watching for '$handle' ($ghuser): origin/main WORKBOARD+HELP, and open-PR reviews by $APPROVER (every ${INTERVAL}s)"

while true; do
  sleep "$INTERVAL"
  cm="$(board_sig)"
  if [ "$cm" != "$pm" ]; then
    echo "SIGNAL[board]: origin/main WORKBOARD.md or HELP.md changed — git pull origin main; re-read status/WORKBOARD.md ($handle section) and dev/HELP.md (answers to your requests). If your PR merged, start the next pending task; if a blocking HELP request was answered, act on the answer."
    pm="$cm"
  fi
  cp="$(pr_sig)"
  if [ -n "$cp" ] && [ "$cp" != "$pp" ]; then
    echo "SIGNAL[pr-review]: the approver ($APPROVER) left a new review/comment on one of your open PRs — run 'gh pr view <n> --comments'; address change-requests on the same branch and push, or proceed if approved."
    pp="$cp"
  fi
done
