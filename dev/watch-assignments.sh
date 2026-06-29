#!/usr/bin/env bash
# dev/watch-assignments.sh <handle> <github-username>
#
# The autonomous-contributor watcher. A contributor's Claude runs this as a background
# Monitor; each stdout line is an event telling the agent something needs its attention,
# so it can run continuously with no human prompting. It watches TWO channels:
#
#   [board]      origin/main : status/WORKBOARD.md + dev/HELP.md
#                 → these coordination docs changed on main (only the approver can change them).
#                   Could be a new/updated assignment for you, an answer to one of your HELP
#                   requests, or (when the approver merges your PR + bumps the board) the cue to
#                   start your next task. It hashes the WHOLE files, so a change to another
#                   contributor's row also wakes you — re-check YOUR section; if nothing's new,
#                   re-idle (one harmless cycle).
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

# Preflight: the [board] channel is git-only and always works; the [pr-review] channel needs gh auth.
# Warn loudly (don't die — board signals still flow) so the dead channel is never a SILENT failure.
if ! gh auth status >/dev/null 2>&1; then
  echo "WARN: gh is NOT authenticated — the [pr-review] channel is DISABLED (you won't be woken on PR reviews)."
  echo "WARN: run 'gh auth login', then restart this watcher. The [board] channel (assignments/HELP) still works."
fi

pm="$(board_sig)"
pp="$(pr_sig)"
echo "watching for '$handle' ($ghuser): origin/main WORKBOARD+HELP, and open-PR reviews by $APPROVER (every ${INTERVAL}s)"

# Exponential backoff: when BOTH channels are idle the sleep doubles each cycle
# (base=$INTERVAL, cap=600s).  Any change resets to the base interval.
_cur_interval="$INTERVAL"
_backoff_cap=600

while true; do
  sleep "$_cur_interval"
  cm="$(board_sig)"
  cp="$(pr_sig)"
  _changed=0
  if [ "$cm" != "$pm" ]; then
    echo "SIGNAL[board]: origin/main WORKBOARD.md or HELP.md changed — git pull origin main; re-read status/WORKBOARD.md ($handle section) and dev/HELP.md (answers to your requests). If your PR merged, start the next pending task; if a blocking HELP request was answered, act on the answer."
    pm="$cm"
    _changed=1
  fi
  if [ -n "$cp" ] && [ "$cp" != "$pp" ]; then
    echo "SIGNAL[pr-review]: the approver ($APPROVER) left a new review/comment on one of your open PRs — run 'gh pr view <n> --comments'; address change-requests on the same branch and push, or proceed if approved."
    pp="$cp"
    _changed=1
  fi
  if [ "$_changed" -eq 1 ]; then
    _cur_interval="$INTERVAL"  # reset to base on any change
  else
    # Both channels idle — double the sleep up to the cap.
    _cur_interval=$(( _cur_interval * 2 ))
    if [ "$_cur_interval" -gt "$_backoff_cap" ]; then
      _cur_interval="$_backoff_cap"
    fi
  fi
done
