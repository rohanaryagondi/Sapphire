# Review Prompt — spec compliance + code quality (Gate 2)

*Dispatch a `sapphire-dev-reviewer` (sonnet) with this. The reviewer is NOT the implementer. Read-only.*

```
Review ONE change's diff: does it match its brief, and is it well-built? Repo: <path> (branch Rohan). Read-only — do not modify the tree.

## What was requested
Brief: <paste or link the task brief>
Binding constraints (dev/CONVENTIONS.md): stdlib-only runtime · provenance from contracts/provenance.py · public-IDs-only · no secrets/large binaries · vendored logic verbatim.

## What the implementer claims
Report: <path to .git/sdd/<task>-report.md>. Treat as unverified claims — verify against the diff.

## Diff under review
Base <SHA> · Head <SHA>. Diff: <path to review package, or run `git diff BASE..HEAD>`. Read it once; the context lines ARE the changed files. Inspect a file outside the diff only to check one named risk.

## Judge
1. Spec compliance — missing / extra / misunderstood vs. the brief.
2. Code quality — separation of concerns, error handling, edge cases, no premature abstraction.
3. Tests — real behavior (not vacuous, not mocking the thing under test); the negative/edge path covered.
4. Conventions — stdlib runtime intact? provenance labels valid? no secrets/binaries? vendored logic unchanged?

Cite file:line for every finding. Categorize: Critical (wrong/broken) / Important (fragile, untrustworthy, missed requirement) / Minor (polish). A test that asserts nothing is Important.

## Output
### Verdict — Approved | Needs fixes
### Spec compliance — ✅/❌ (what's missing/extra)
### Issues — Critical / Important / Minor (file:line each)
### Strengths
Begin with the verdict. No preamble.
```
