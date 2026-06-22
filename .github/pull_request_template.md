<!-- Sapphire PR. Contributors: fill every section. Rohan's Claude is the sole approver/merger (dev/PR_REVIEW.md). -->

## What & why
<One paragraph: what this PR delivers and why. Link the task brief / plan.>

- **Task id:** <area-slug from dev/DELEGATION.md>
- **Built-By:** <your handle — rohan | hayes | gavin>
- **Tier:** <Trivial | Standard | Feature>
- **Plan/brief:** <docs/superpowers/plans/...>

## Gate evidence (run locally before opening — see dev/GATES.md)
- [ ] **Gate 1** — full suite green: `<N tests, all OK>` (paste the count)
- [ ] **Gate 2** — independent review (a different agent than the implementer): `<Approved>`
- [ ] **Gate 3** — provenance labels allowed · no secrets/keys · no unexpected binaries · public-IDs-only held
- [ ] **Gate 4** — engine stayed stdlib-only · any vendored logic verbatim + golden-tested + dep pinned (or N/A)
- [ ] **Gate 5** — functional verification: **I RAN it** adversarially; observable behavior matches the claim
      <paste the key evidence — real output, not just "tests pass">

## Scope
- **Files touched:** <list / "see diff">
- **Out of scope / deferred:** <what this PR deliberately does not do>

## Notes for the approver
<Anything the reviewer should know: risks, follow-ups, a known limitation, a question.>

---
*Attribution: this branch is `<handle>/<slug>` and every commit carries `Built-By: <handle>`. The approver
re-establishes the gates independently (`dev/PR_REVIEW.md`) before merge.*
