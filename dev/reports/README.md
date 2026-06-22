# Build Reports

Per-contributor build reports — the tracked, attributable record of what each task did, how it was verified,
and any gaps. One subdirectory per contributor handle.

```
dev/reports/
  rohan/   hayes/   gavin/
```

## What goes here
- One report per shipped (or in-flight) task: `<task-id>-report.md`.
- A report states: what changed (files), the gate results with real evidence (test counts, verify output),
  any skips/caveats, and follow-ups. It is the durable companion to the one-line `dev/LEDGER.md` entry.

## Conventions
- File: `dev/reports/<handle>/<task-id>-report.md`.
- Scratch/ephemeral notes may stay in `.git/sdd/` (untracked); **promote the final report here** when the PR
  opens so it ships with the change and is attributable in git.
- Never put secrets, internal candidate IDs (`QS\d+`), or proprietary structures in a report — public
  identifiers only, same boundary as everything else.

`dev/LEDGER.md` remains the canonical append-only merge log; these reports are the detail behind each entry.
