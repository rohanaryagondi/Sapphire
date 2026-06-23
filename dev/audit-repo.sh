#!/usr/bin/env bash
# dev/audit-repo.sh — mechanical repo-health checks for Sapphire.
# Invoked by the `sapphire-audit` skill; can also be run directly.
#
# Checks (in order):
#   1. Stray top-level files (only CLAUDE.md / README.md / .gitignore allowed)
#   2. Broken relative markdown links (most valuable — file:line reported)
#   3. Large tracked binaries (> 1 MB)
#   4. Same-basename collisions across dirs (heads-up, not an error)
#   5. Workboard branch-existence sanity (best-effort)
#   6. Delegates to dev/audit-history.sh for Built-By attribution + secret scan
#
# Exit codes:
#   0 — clean (no Critical or Important findings)
#   1 — one or more Critical/Important findings
#
# Safe to re-run anytime; read-only.  Does not call dev/run-tests.sh (Gate 1)
# — call that separately for a full gate check.
#
# Compatibility: bash 3.2+, macOS grep (no -P).  Uses python3 for link parsing.
#
# Usage:
#   bash dev/audit-repo.sh [--no-history]
#     --no-history  skip the audit-history.sh delegation (useful in offline/
#                   no-remote contexts where git fetch would block)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

NO_HISTORY=0
for arg in "$@"; do [[ "$arg" == "--no-history" ]] && NO_HISTORY=1; done

# ── counters ──────────────────────────────────────────────────────────────────
crit=0; imp=0; nit=0

_crit() { echo "  [CRITICAL] $*"; crit=$((crit+1)); }
_imp()  { echo "  [IMPORTANT] $*"; imp=$((imp+1)); }
_nit()  { echo "  [NIT] $*"; nit=$((nit+1)); }
_ok()   { echo "  [OK] $*"; }

# ── CHECK 1: Stray top-level files ────────────────────────────────────────────
echo ""
echo "══ 1. Top-level files (allowed: CLAUDE.md README.md .gitignore) ══"
ALLOWED_TOPS=".gitignore CLAUDE.md README.md"
stray=0
while IFS= read -r f; do
  # git ls-files returns paths; top-level files have no '/' in them.
  # Dotfiles/dot-dirs at top level (e.g. .githooks, .github) are fine.
  # We only flag plain files that are NOT in the allowed list AND don't start with '.'.
  [[ "$f" == *"/"* ]] && continue                       # not top-level
  [[ "$f" == .* ]]    && continue                       # dotfiles are fine
  ok=0
  for a in $ALLOWED_TOPS; do [[ "$f" == "$a" ]] && ok=1 && break; done
  if [[ "$ok" -eq 0 ]]; then
    _crit "Stray top-level file: $f"
    stray=$((stray+1))
  fi
done < <(git ls-files)
[[ "$stray" -eq 0 ]] && _ok "Top level clean — only allowed files present."

# ── CHECK 2: Broken relative markdown links ───────────────────────────────────
# Uses python3 (stdlib only) for portable regex extraction — avoids relying on
# GNU grep -P which is unavailable on macOS stock grep.
# The Python helper is written to a temp file to avoid bash-3.2 heredoc-in-
# process-substitution limitations.
echo ""
echo "══ 2. Broken relative markdown links ══"

# Write the Python link-extractor to a temp file once.
_LINK_PY="$(mktemp /tmp/sapphire_audit_links_XXXXXX.py)"
trap 'rm -f "$_LINK_PY"' EXIT
cat > "$_LINK_PY" << 'PYEOF'
import re, sys, os

path = sys.argv[1]
try:
    text = open(path, encoding="utf-8", errors="replace").read()
except OSError:
    sys.exit(0)

# Remove fenced code blocks (``` ... ```) to avoid false-positives on
# SMILES strings and code samples that happen to contain ]( sequences.
text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
# Remove inline code spans (`...`).
text = re.sub(r'`[^`\n]+`', '', text)

# Extract inline link targets: [text](target)
for m in re.finditer(r'\]\(([^)]+)\)', text):
    raw = m.group(1).strip()
    # skip external / anchor-only / empty
    if not raw or raw.startswith(('#', 'http://', 'https://', 'mailto:', '//')):
        continue
    # strip trailing #anchor fragment
    target = raw.split('#')[0].strip()
    if target:
        print(target)
PYEOF

broken_links=0
while IFS= read -r mdfile; do
  mddir="$(dirname "$mdfile")"
  # Extract all inline markdown link targets.
  while IFS= read -r target; do
    [[ -z "$target" ]] && continue

    # Resolve relative to the .md file's own directory.
    if [[ "$target" == /* ]]; then
      resolved="$ROOT/$target"
    else
      resolved="$ROOT/$mddir/$target"
    fi

    # Normalise path components (/../, /./) using python3 — portable.
    norm="$(python3 -c "import os.path,sys; print(os.path.normpath(sys.argv[1]))" "$resolved" 2>/dev/null || echo "$resolved")"

    if [[ ! -e "$norm" ]]; then
      _imp "Broken link in $mdfile -> $target"
      broken_links=$((broken_links+1))
    fi
  done < <(python3 "$_LINK_PY" "$ROOT/$mdfile")
done < <(git ls-files | grep '\.md$')
[[ "$broken_links" -eq 0 ]] && _ok "No broken relative markdown links found."

# ── CHECK 3: Large tracked binaries (> 1 MB) ──────────────────────────────────
# Skips the vendored q-models/ subtree (an external repo vendored into the tree with
# its own benchmark artifacts — see q-models/VENDORED.md; not Sapphire's code to police).
echo ""
echo "══ 3. Large tracked files (> 1 MB, excluding vendored q-models/) ══"
large=0
while IFS= read -r f; do
  [[ "$f" == q-models/* ]] && continue   # vendored external repo — out of scope
  size="$(git cat-file -s ":$f" 2>/dev/null || echo 0)"
  if [[ "$size" -gt 1048576 ]]; then
    kb=$(( size / 1024 ))
    _imp "Large tracked file: $f  (${kb} KB)"
    large=$((large+1))
  fi
done < <(git ls-files)
[[ "$large" -eq 0 ]] && _ok "No large tracked files found (outside vendored q-models/)."

# ── CHECK 4: Same-basename collisions ─────────────────────────────────────────
# Flag non-trivial basenames (not README.md / __init__.py / .gitignore / SKILL.md
# / requirements.txt — these are universally multi-copy by design) that appear
# 4+ times across different directories.  bash 3.2 compatible (no assoc arrays).
echo ""
echo "══ 4. Same-basename collisions (heads-up, not an error) ══"
UBIQUITOUS_BASENAMES="README.md __init__.py .gitignore SKILL.md requirements.txt"
any_coll=0
while IFS=" " read -r cnt bn; do
  # skip the universally multi-copy names
  skip=0
  for ub in $UBIQUITOUS_BASENAMES; do [[ "$bn" == "$ub" ]] && skip=1 && break; done
  [[ "$skip" -eq 1 ]] && continue

  if [[ "$cnt" -ge 4 ]]; then
    _nit "Basename '$bn' appears ${cnt} times — confirm each copy is intentional:"
    escaped="$(printf '%s' "$bn" | sed 's/\./\\./g')"
    git ls-files | grep "${escaped}$" | sed 's/^/        /'
    any_coll=1
  fi
done < <(git ls-files | xargs -I{} basename "{}" | sort | uniq -c | sort -rn)
[[ "$any_coll" -eq 0 ]] && _ok "No notable basename collisions."

# ── CHECK 5: Workboard branch-existence sanity ────────────────────────────────
echo ""
echo "══ 5. Workboard branch sanity (best-effort) ══"
WORKBOARD="$ROOT/status/WORKBOARD.md"
if [[ ! -f "$WORKBOARD" ]]; then
  _nit "status/WORKBOARD.md not found — skipping branch-sanity check."
else
  # Fetch remote branch list (quiet; non-fatal).
  git fetch -q origin 2>/dev/null || true
  remote_branches="$(git branch -r 2>/dev/null | sed 's|^[[:space:]]*origin/||;s|^.*->.*||' | grep -v '^[[:space:]]*$' || true)"
  local_branches="$(git branch 2>/dev/null | sed 's/^\*[[:space:]]*//' | sed 's/^[[:space:]]*//' || true)"
  all_branches="$(printf '%s\n%s\n' "$local_branches" "$remote_branches" | grep -v '^[[:space:]]*$' | sort -u)"

  wb_issues=0
  # Find table rows with an active status that also reference a handle/slug branch.
  # Uses grep+sed (macOS compatible, no -P).  Pattern: `handle/slug` in backticks.
  while IFS= read -r line; do
    # Extract the first `handle/slug` token from the line.
    branch="$(printf '%s' "$line" | grep -oE '`[a-z][a-zA-Z0-9-]+/[a-zA-Z0-9_-]+`' | head -1 | tr -d '`')"
    [[ -z "$branch" ]] && continue
    if ! printf '%s\n' "$all_branches" | grep -qxF "$branch"; then
      _nit "Workboard: branch '$branch' not found locally or remotely (active row)"
      wb_issues=$((wb_issues+1))
    fi
  done < <(grep -E '\|\s*(assigned|claimed|in-progress|in-review)\s*\|' "$WORKBOARD" || true)
  [[ "$wb_issues" -eq 0 ]] && _ok "Workboard branch references look healthy."
fi

# ── CHECK 6: History audit (Built-By + secret scan) ──────────────────────────
echo ""
echo "══ 6. History audit (Built-By attribution + secret scan) ══"
AUDIT_HISTORY="$ROOT/dev/audit-history.sh"
if [[ "$NO_HISTORY" -eq 1 ]]; then
  echo "  (skipped — --no-history flag set)"
elif [[ ! -x "$AUDIT_HISTORY" ]]; then
  _nit "dev/audit-history.sh not found or not executable — skipping history audit."
else
  # Run and capture; relay output indented; treat its non-zero as an Important finding.
  hist_out="$(bash "$AUDIT_HISTORY" 2>&1)" || true
  hist_exit=$?
  printf '%s\n' "$hist_out" | sed 's/^/  /'
  if [[ "$hist_exit" -ne 0 ]]; then
    imp=$((imp+1))
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════════════"
echo "  AUDIT SUMMARY"
echo "  Critical : $crit"
echo "  Important: $imp"
echo "  Nit      : $nit"
echo "══════════════════════════════════════════════════════════════════════"
echo ""
if [[ $((crit + imp)) -gt 0 ]]; then
  echo "AUDIT: $((crit + imp)) Critical/Important finding(s) require attention."
  exit 1
else
  echo "AUDIT CLEAN — no Critical or Important findings."
  exit 0
fi
