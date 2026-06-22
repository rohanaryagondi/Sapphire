# Task Brief — <task name>

*Fill this in before dispatching an implementer. A precise brief is the difference between a clean task and scope creep. Delete the guidance lines once filled.*

## Goal
<One sentence: what this task delivers and why.>

## Context the implementer needs
- Plan/feature: <link to the plan doc, if any>
- Read first: <exact files/paths the implementer must read to do this correctly>
- Verbatim-preserve: <any vendored/proprietary code that must be copied character-for-character — paste it here>

## What to build
<Concrete, bounded. The files to create/change. The interface/signature. The behavior. Stay inside this — no extras.>

## Constraints (binding — see dev/CONVENTIONS.md)
- Runtime stays stdlib-only? <yes/which seam handles third-party deps>
- Provenance label(s) used: <from contracts/provenance.py>
- Data boundary / public-IDs-only: <applies?>
- Don't modify: <files/logic that must not change>

## Definition of Done
- [ ] <observable behavior 1>
- [ ] <observable behavior 2>
- [ ] Tests (real-behavior, offline/$0) covering: <cases incl. the negative/edge path>
- [ ] Focused tests run and green
- [ ] Short report written to `.git/sdd/<task>-report.md`

## Out of scope
<What this task explicitly does NOT touch — prevents creep.>
