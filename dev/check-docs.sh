#!/usr/bin/env bash
# dev/check-docs.sh — Doc-freshness gate (WO 4.1)
#
# Usage:
#   dev/check-docs.sh [<range>]                  block mode: exit 1 on violations
#   dev/check-docs.sh --warn [<range>]           warn mode:  print then exit 0
#   dev/check-docs.sh --tier trivial [<range>]   trivial exemption: skip all checks
#   dev/check-docs.sh --dry-run <range>          print range, then check (block mode)
#   dev/check-docs.sh --selftest                 run self-test across 8 scenarios
#
# Default range: origin/main..HEAD
#
# Rules applied to all commits in <range>:
#   Rule 1  runtime .py changed   → dev/LEDGER.md must appear in the range
#   Rule 2  agents.json ↔ architecture/**/*.md must both change together
#   Rule 3  state-changing change → at least one status/ file must update
#   Rule 4  feature-tier (>3 .py) → WO-<id> or plans/<slug> in commit subjects,
#                                    or a dev/work-orders/ file changed
set -euo pipefail

# ─── helpers ──────────────────────────────────────────────────────────────────

is_runtime_py() {
  local f="$1"
  [[ "$f" == "sapphire-orchestrator/live_engine.py"  ]] && return 0
  [[ "$f" == "sapphire-orchestrator/orchestrator.py" ]] && return 0
  [[ "$f" == "sapphire-orchestrator/serve.py"        ]] && return 0
  [[ "$f" == "frontend/bridge.py"                    ]] && return 0
  [[ "$f" =~ ^sapphire-orchestrator/harness/.*\.py$  ]] && return 0
  [[ "$f" =~ ^sapphire-orchestrator/moat/.*\.py$     ]] && return 0
  [[ "$f" =~ ^sapphire-orchestrator/tools/.*\.py$    ]] && return 0
  return 1
}

is_docs_only_path() {
  local f="$1"
  [[ "$f" =~ ^dev/     ]] && return 0
  [[ "$f" =~ ^docs/    ]] && return 0
  [[ "$f" =~ ^status/  ]] && return 0
  [[ "$f" =~ ^site/    ]] && return 0
  [[ "$f" =~ ^architecture/.*\.md$ ]] && return 0
  [[ "$f" == "CLAUDE.md" || "$f" == "README.md" ]] && return 0
  [[ "$f" =~ \.txt$   ]] && return 0
  [[ "$f" =~ \.jsonl$ ]] && return 0
  return 1
}

# ─── arg parsing ──────────────────────────────────────────────────────────────

WARN_MODE=0
TRIVIAL=0
SELFTEST=0
DRY_RUN=0
RANGE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --warn)
      WARN_MODE=1; shift
      ;;
    --tier)
      shift
      if [[ "${1:-}" == "trivial" ]]; then
        TRIVIAL=1; shift
      fi
      ;;
    --selftest)
      SELFTEST=1; shift
      ;;
    --dry-run)
      DRY_RUN=1; shift
      ;;
    *)
      RANGE="$1"; shift
      ;;
  esac
done

[[ -z "$RANGE" ]] && RANGE="origin/main..HEAD"

# ─── self-test ────────────────────────────────────────────────────────────────

if [[ "$SELFTEST" == "1" ]]; then
  _self="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)/$(basename "${BASH_SOURCE[0]}")"
  _pass=0
  _fail=0

  _ok() {
    printf '  PASS [%s] %s\n' "$1" "$2"
    _pass=$((_pass + 1))
  }
  _nok() {
    printf '  FAIL [%s] %s — %s\n' "$1" "$2" "$3"
    _fail=$((_fail + 1))
  }

  # Create a minimal git repo with one base commit.
  _init_repo() {
    local d="$1"
    git -C "$d" init -q 2>/dev/null
    git -C "$d" config user.email "test@test.local"
    git -C "$d" config user.name "Test"
    git -C "$d" config commit.gpgsign false
    printf 'init\n' > "$d/init.txt"
    git -C "$d" add init.txt
    git -C "$d" -c commit.gpgsign=false commit -q -m "initial"
  }

  # Add files and create a commit on top of the base.
  # Args: <dir> <commit-msg> [path:content ...]
  _commit() {
    local d="$1" msg="$2"; shift 2
    for pair in "$@"; do
      local p="${pair%%:*}"
      local v="${pair#*:}"
      mkdir -p "$d/$(dirname "$p")"
      printf '%s\n' "$v" > "$d/$p"
      git -C "$d" add "$p"
    done
    git -C "$d" -c commit.gpgsign=false commit -q -m "$msg"
  }

  # Run check-docs.sh from inside <dir> with --warn and range HEAD^..HEAD.
  # Extra flags (other than range) go before the range.
  _run() {
    local d="$1"; shift
    _out=""
    set +e
    _out="$(cd "$d" && bash "$_self" --warn "$@" "HEAD^..HEAD" 2>&1)"
    set -e
  }

  echo "check-docs: --selftest"

  # 1. docs-only commit → EXEMPT (exit 0)
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "update gates" "dev/GATES.md:updated gates"
  _run "$_d"
  if echo "$_out" | grep -q "\[EXEMPT"; then
    _ok 1 "docs-only → EXEMPT"
  else
    _nok 1 "docs-only → EXEMPT" "output: $_out"
  fi
  rm -rf "$_d"

  # 2. runtime .py without LEDGER → Rule 1 fires
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "add dispatch" \
    "sapphire-orchestrator/harness/dispatch.py:# engine"
  _run "$_d"
  if echo "$_out" | grep -q "Runtime .py changed but dev/LEDGER.md not updated"; then
    _ok 2 "runtime .py without LEDGER → Rule 1 fires"
  else
    _nok 2 "runtime .py without LEDGER → Rule 1 fires" "output: $_out"
  fi
  rm -rf "$_d"

  # 3. runtime .py WITH LEDGER → Rule 1 passes (no Rule-1 WARN)
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "add dispatch with ledger" \
    "sapphire-orchestrator/harness/dispatch.py:# engine" \
    "dev/LEDGER.md:## entry"
  _run "$_d"
  if ! echo "$_out" | grep -q "Runtime .py changed but dev/LEDGER.md not updated"; then
    _ok 3 "runtime .py WITH LEDGER → Rule 1 passes"
  else
    _nok 3 "runtime .py WITH LEDGER → Rule 1 passes" "Rule 1 still fired: $_out"
  fi
  rm -rf "$_d"

  # 4. agents.json without architecture spec → Rule 2 fires
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "add agent registry" \
    "sapphire-orchestrator/harness/agents.json:{}" \
    "dev/LEDGER.md:## entry" \
    "status/OVERALL.md:updated"
  _run "$_d"
  if echo "$_out" | grep -q "harness/agents.json changed without a paired"; then
    _ok 4 "agents.json without spec → Rule 2 fires"
  else
    _nok 4 "agents.json without spec → Rule 2 fires" "output: $_out"
  fi
  rm -rf "$_d"

  # 5. agents.json WITH paired architecture spec → Rule 2 passes
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "add agent with spec" \
    "sapphire-orchestrator/harness/agents.json:{}" \
    "architecture/bucket1/new_agent.md:# spec" \
    "dev/LEDGER.md:## entry" \
    "status/OVERALL.md:updated"
  _run "$_d"
  if ! echo "$_out" | grep -q "harness/agents.json changed without a paired"; then
    _ok 5 "agents.json WITH spec → Rule 2 passes"
  else
    _nok 5 "agents.json WITH spec → Rule 2 passes" "Rule 2 still fired: $_out"
  fi
  rm -rf "$_d"

  # 5b. architecture spec changed WITHOUT agents.json → Rule 2 fires (reverse direction)
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "spec only no registry" \
    "architecture/bucket1/new_agent.md:# spec" \
    "status/OVERALL.md:updated"
  _run "$_d"
  if echo "$_out" | grep -q "architecture/\*\*/\*.md spec changed without a paired harness/agents.json"; then
    _ok "5b" "arch spec without agents.json → Rule 2 (reverse) fires"
  else
    _nok "5b" "arch spec without agents.json → Rule 2 (reverse) fires" "output: $_out"
  fi
  rm -rf "$_d"

  # 6. state-changing change without status/ → Rule 3 fires
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "add dispatch no status" \
    "sapphire-orchestrator/harness/dispatch.py:# engine" \
    "dev/LEDGER.md:## entry"
  _run "$_d"
  if echo "$_out" | grep -q "State-changing change.*but no status/ file updated"; then
    _ok 6 "state-change without status/ → Rule 3 fires"
  else
    _nok 6 "state-change without status/ → Rule 3 fires" "output: $_out"
  fi
  rm -rf "$_d"

  # 7. feature-tier (>3 .py files) without WO ref → Rule 4 fires
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "big feature no wo ref" \
    "sapphire-orchestrator/harness/a.py:# a" \
    "sapphire-orchestrator/harness/b.py:# b" \
    "sapphire-orchestrator/harness/c.py:# c" \
    "sapphire-orchestrator/harness/d.py:# d" \
    "dev/LEDGER.md:## entry" \
    "status/OVERALL.md:updated"
  _run "$_d"
  if echo "$_out" | grep -q "Feature-tier change:"; then
    _ok 7 "feature-tier without WO ref → Rule 4 fires"
  else
    _nok 7 "feature-tier without WO ref → Rule 4 fires" "output: $_out"
  fi
  rm -rf "$_d"

  # 8. --tier trivial → EXEMPT (even with runtime .py)
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "trivial change" \
    "sapphire-orchestrator/harness/dispatch.py:# engine"
  set +e
  _out="$(cd "$_d" && bash "$_self" --warn --tier trivial "HEAD^..HEAD" 2>&1)"
  set -e
  if echo "$_out" | grep -q "\[EXEMPT"; then
    _ok 8 "--tier trivial → EXEMPT"
  else
    _nok 8 "--tier trivial → EXEMPT" "output: $_out"
  fi
  rm -rf "$_d"

  # 9. [trivial] in commit subject → EXEMPT (even with runtime .py)
  _d="$(mktemp -d)"; _init_repo "$_d"
  _commit "$_d" "fix typo [trivial]" \
    "sapphire-orchestrator/harness/dispatch.py:# engine"
  _run "$_d"
  if echo "$_out" | grep -q "\[EXEMPT"; then
    _ok 9 "[trivial] in commit subject → EXEMPT"
  else
    _nok 9 "[trivial] in commit subject → EXEMPT" "output: $_out"
  fi
  rm -rf "$_d"

  printf '\ncheck-docs: self-test: %d passed, %d failed\n' "$_pass" "$_fail"
  [[ "$_fail" -eq 0 ]] && exit 0 || exit 1
fi

# ─── normal mode ──────────────────────────────────────────────────────────────

root="$(git rev-parse --show-toplevel 2>/dev/null)"
cd "$root"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "check-docs: range → $RANGE"
fi

# Trivial exemption — via --tier trivial flag OR [trivial] token in any commit subject
if [[ "$TRIVIAL" == "1" ]]; then
  echo "check-docs: [EXEMPT trivial]"
  exit 0
fi
_subjects_early="$(git log --format='%s' "$RANGE" 2>/dev/null || true)"
if echo "$_subjects_early" | grep -qF '[trivial]'; then
  echo "check-docs: [EXEMPT trivial (commit subject contains [trivial])]"
  exit 0
fi

# Get changed files in the range
changed="$(git diff --name-only "$RANGE" 2>/dev/null || true)"

# Empty range → nothing to check
if [[ -z "$changed" ]]; then
  echo "check-docs: [EXEMPT docs-only]"
  exit 0
fi

# ─── pre-compute flags from the changed file list ─────────────────────────────
# (done before docs-only check so Rule 2 arch-spec trigger can override the exemption)

_runtime_py=0   # any runtime .py changed
_agents_json=0  # harness/agents.json changed
_arch_md=0      # architecture/**/*.md changed
_ledger=0       # dev/LEDGER.md changed
_status=0       # any status/ file changed
_py_count=0     # total .py files changed
_work_orders=0  # any dev/work-orders/ file changed
_all_docs=1     # every changed file is docs-only

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if is_runtime_py "$f"; then _runtime_py=1; fi
  [[ "$f" == "sapphire-orchestrator/harness/agents.json" ]] && _agents_json=1
  if [[ "$f" =~ ^architecture/.*\.md$ ]]; then _arch_md=1; fi
  [[ "$f" == "dev/LEDGER.md" ]] && _ledger=1
  if [[ "$f" =~ ^status/ ]]; then _status=1; fi
  if [[ "$f" == *.py ]]; then _py_count=$((_py_count + 1)); fi
  if [[ "$f" =~ ^dev/work-orders/ ]]; then _work_orders=1; fi
  if ! is_docs_only_path "$f"; then _all_docs=0; fi
done <<< "$changed"

# Docs-only exemption: every file matches the docs-only pattern, none are runtime .py,
# AND the change does NOT trigger a Rule-2 pairing requirement (arch spec without agents.json).
# Architecture specs LOOK like docs but require registry synchronisation (Rule 2), so a
# spec-only change is not truly docs-only.
if [[ "$_all_docs" == "1" && "$_runtime_py" == "0" ]]; then
  if [[ "$_arch_md" == "0" || "$_agents_json" == "1" ]]; then
    echo "check-docs: [EXEMPT docs-only]"
    exit 0
  fi
  # Fall through: arch spec changed without agents.json → Rule 2 must fire.
fi

# Detect new files added under sapphire-orchestrator/tools/ or harness/
_has_new_tool_harness=0
changed_status="$(git diff --name-status "$RANGE" 2>/dev/null || true)"
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  # status field is the first tab-separated token (A, M, D, R100, etc.)
  [[ "$line" =~ ^A ]] || continue
  # extract the path (second field after the tab)
  _ns_path="${line#*$'\t'}"
  _ns_path="${_ns_path%%$'\t'*}"
  if [[ "$_ns_path" =~ ^sapphire-orchestrator/tools/ ]] || \
     [[ "$_ns_path" =~ ^sapphire-orchestrator/harness/ ]]; then
    _has_new_tool_harness=1
  fi
done <<< "$changed_status"

# ─── apply rules ──────────────────────────────────────────────────────────────

violations=0

# Rule 1: runtime .py changed → dev/LEDGER.md must be in the range
if [[ "$_runtime_py" == "1" && "$_ledger" == "0" ]]; then
  echo "WARN [doc-gate] Runtime .py changed but dev/LEDGER.md not updated in this range. Add a ledger entry."
  violations=$((violations + 1))
fi

# Rule 2: agents.json ↔ architecture spec pairing
if [[ "$_agents_json" == "1" && "$_arch_md" == "0" ]]; then
  echo "WARN [doc-gate] harness/agents.json changed without a paired architecture/**/*.md spec change."
  violations=$((violations + 1))
fi
if [[ "$_arch_md" == "1" && "$_agents_json" == "0" ]]; then
  echo "WARN [doc-gate] architecture/**/*.md spec changed without a paired harness/agents.json registry change."
  violations=$((violations + 1))
fi

# Rule 3: state-changing change → at least one status/ file updated
_state_changing=0
[[ "$_runtime_py"           == "1" ]] && _state_changing=1
[[ "$_agents_json"          == "1" ]] && _state_changing=1
[[ "$_has_new_tool_harness" == "1" ]] && _state_changing=1

if [[ "$_state_changing" == "1" && "$_status" == "0" ]]; then
  echo "WARN [doc-gate] State-changing change (runtime/agent/tool) but no status/ file updated. Update status/OVERALL.md or status/WORKBOARD.md."
  violations=$((violations + 1))
fi

# Rule 4: feature-tier (state-changing AND >3 .py files) → WO reference required
if [[ "$_state_changing" == "1" && "$_py_count" -gt 3 ]]; then
  _wo_ref=0
  _subjects="$(git log --format='%s' "$RANGE" 2>/dev/null || true)"
  if echo "$_subjects" | grep -qE "WO-\w+";  then _wo_ref=1; fi
  if echo "$_subjects" | grep -qE "plans/\S+"; then _wo_ref=1; fi
  [[ "$_work_orders" == "1" ]] && _wo_ref=1

  if [[ "$_wo_ref" == "0" ]]; then
    echo "WARN [doc-gate] Feature-tier change: no WO-<id> or plans/<slug> reference found in commit subjects, and no dev/work-orders/ file changed. Add a WO reference."
    violations=$((violations + 1))
  fi
fi

# ─── exit ─────────────────────────────────────────────────────────────────────

if [[ "$violations" -gt 0 ]]; then
  printf 'check-docs: %d violation(s) in range [%s].\n' "$violations" "$RANGE"
  if [[ "$WARN_MODE" == "0" ]]; then
    exit 1
  fi
fi

exit 0
