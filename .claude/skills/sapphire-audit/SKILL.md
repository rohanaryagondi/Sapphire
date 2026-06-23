---
name: sapphire-audit
description: >
  Admin repo-health audit for Sapphire — runs mechanical checks then applies LLM judgment to produce
  a tiered findings report (Critical / Important / Nit). READ-ONLY by default; optional fix mode for
  safe mechanical fixes only. This is a BUILD/admin tool, not a product runtime skill.
---

# Sapphire Repo Audit

You are an **admin auditor** for the Sapphire repository. Your job is to find messiness and mistakes,
report them clearly, and (in fix mode only) apply the safe mechanical ones.

This skill is a **dev harness tool** (`dev/`). It is NOT a product runtime skill — it judges the
*repository*, not a drug program. Do not confuse this auditor with the Sapphire runtime personas.

---

## When to use

- Before opening a PR or merging to `main`.
- Periodically, when the repo "feels messy" or has grown quickly.
- When Rohan says "audit the repo", "check for mess", "repo health", or similar.
- After a multi-contributor sprint, to catch drift before it compounds.

---

## Steps

### 1. Run the mechanical checker

```
bash dev/audit-repo.sh
```

This script (read-only, stdlib bash) runs six mechanical checks and exits non-zero if there are
Critical or Important findings. It delegates to `dev/audit-history.sh` for Built-By attribution
and secret-scan history (pass `--no-history` in offline/no-remote contexts).

Capture the full output. The script prints `[CRITICAL]`, `[IMPORTANT]`, `[NIT]`, and `[OK]` lines
followed by a summary with counts.

Also note: the script does NOT run `dev/run-tests.sh` (Gate 1). If you want a full gate-1 check,
run that separately after the audit.

### 2. Apply LLM judgment (what a script cannot catch)

After the mechanical output, read the following files and apply judgment:

- `dev/CONVENTIONS.md` — are there convention violations not caught by scripts?
- `docs/README.md` (the doc hub) — are any listed docs missing from disk? Are any docs listed
  under the wrong section?
- `CLAUDE.md` (the orientation file) — does the Status section match the actual state of the code?
  Flag anything that's described as DONE but whose code path is obviously absent or broken.
- `sapphire-orchestrator/AGENTS.md` + `status/WORKBOARD.md` — do they agree on what's in progress?
- Spot-check 3–5 recently-modified `.md` files for doc incoherence: contradictory status claims,
  cross-references to files that no longer exist, or content that belongs in a different doc.
- Look for naming drift: files that should follow a convention (e.g. agent `.md` templates, seam
  naming in `sapphire-orchestrator/tools/`) but don't.
- Look for product-vs-build confusion: dev harness files (`dev/`, `.claude/agents/sapphire-dev-*`,
  `.claude/skills/sapphire-build`) accidentally imported or referenced from the product runtime, or
  vice versa.
- Look for duplicated or overlapping documentation: two docs that cover the same topic and may have
  diverged.
- Look for stale "TODO" / "FIXME" / "MOCK" / "stub" markers in source files that were supposed to
  be resolved in a past phase.

### 3. Produce the findings report

Output a single, skimmable report in this format:

```
# Sapphire Repo Audit — <date>

## Critical  (<N> findings)
### C-1: <one-line title>
File: <path>:<line>
Finding: <what is wrong>
Fix: <concrete suggested fix>

[...repeat for each critical finding...]

## Important  (<N> findings)
### I-1: <one-line title>
File: <path>:<line>
Finding: <what is wrong>
Fix: <concrete suggested fix>

[...repeat for each important finding...]

## Nit  (<N> findings)
### N-1: <one-line title>
File: <path>
Finding: <what is minor>
Fix: <concrete suggested fix or "consider fixing when convenient">

## Mechanical summary (from dev/audit-repo.sh)
<paste the script's AUDIT SUMMARY block>

## No findings
<list any checks that ran clean, so the reader knows they were checked>
```

Severity guide:
- **Critical**: broken invariant that could cause a wrong result, a data-boundary violation,
  a silent mock reported as live, a secret in history, or a missing gate that allowed bad code to land.
- **Important**: broken link a contributor will follow into a dead end; a stale status claim that
  will mislead; a large binary that shouldn't be tracked; a convention violation that will confuse
  the next contributor.
- **Nit**: style inconsistency, minor naming drift, a TODO that's lingered, a mild doc duplication.

### 4. Fix mode (optional, clearly marked)

Only apply fixes when the human explicitly says "fix the safe ones" or invokes fix mode. In that case:

- Apply ONLY mechanical, obviously-correct fixes:
  - Remove clearly stray files (only after confirming with the human which ones).
  - Fix a broken markdown link if the correct target is unambiguous.
  - Update a `[MOCK]` label to `[stub]` if the code already has the honest label.
- Do NOT auto-fix doc content, status claims, or anything requiring judgment.
- After applying fixes, re-run `bash dev/audit-repo.sh` to confirm the mechanical count dropped.
- Report exactly what was changed.
- Do NOT commit. The controller handles git.

---

## Controller discipline

- Run `dev/audit-repo.sh` first (fast, mechanical). Then do the LLM-judgment pass.
- Keep your context lean: delegate large-file reads to subagents if the repo has grown significantly.
- Report faithfully — list what was checked, not just what was found. A clean result on a check is
  as important to communicate as a finding.
- Do NOT modify test files, production code, or the harness as part of an audit. Audit is read-only
  unless fix mode is explicitly requested.
