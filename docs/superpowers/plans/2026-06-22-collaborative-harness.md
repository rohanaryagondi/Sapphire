# Plan — Collaborative dev harness (multi-contributor, PR-gated)

*Feature tier. Evolves the solo `dev/` harness into a 3-contributor harness (rohan, hayes, gavin), each
driving their own Claude. Attribution is git-native; shipping is PR-gated; **only Rohan's Claude reviews,
approves, and merges to `main`.** Dogfooded: this change itself ships via the new PR flow.*

## Goal
Give the team visibility into who builds what (git-native attribution), a delegation board, per-contributor
reporting, and a PR-gated ship path where Rohan's Claude is the sole approver — enforced by GitHub branch
protection, not just convention.

## Decisions (locked with Rohan, 2026-06-22)
1. **Attribution:** git-native — branch prefix `<handle>/<slug>` + mandatory `Built-By: <handle>` commit
   trailer + `dev/CONTRIBUTORS.md` registry + `Built-By` in the ledger. No in-file headers (avoid churn).
2. **Enforcement:** via GitHub branch protection on `main` (PR + CODEOWNERS review required, only Rohan
   merges, no direct pushes). Repo moved to the Quiver-owned **`rohanaryagondi-quiver/Sapphire`** (Rohan's
   decision, 2026-06-22). That account is currently GitHub **free**, where protection + rulesets still 403,
   so hard enforcement is **one step away**: enable GitHub Pro on `rohanaryagondi-quiver`, then run
   `dev/enable-branch-protection.sh`. Interim: CODEOWNERS routes review + the rule is convention-backed.
3. **Reporting:** tracked `dev/reports/<handle>/`; `dev/LEDGER.md` stays the canonical merge log.
4. **Branch surgery (DONE before this plan):** old `main` → `main-backup-2026-06-22`; `main` fast-forwarded
   to the former `Rohan` bedrock; `Rohan` branch retired. Everyone now branches off `main`.

## Tasks
1. **Contributors registry** — `dev/CONTRIBUTORS.md`: handles, GitHub usernames, the Claude each drives,
   owned subsystems, the approver. (Hayes/Gavin GitHub usernames are placeholders until Rohan confirms.)
2. **Delegation board** — `dev/DELEGATION.md`: ownership map, the task table (id/owner/status/links), and the
   claim protocol.
3. **Approver playbook** — `dev/PR_REVIEW.md`: exactly how Rohan's Claude reviews a PR (gates on someone
   else's diff) and the merge decision.
4. **PR plumbing** — `.github/pull_request_template.md` (gate checklist + evidence + Built-By) and
   `.github/CODEOWNERS` (`* @rohanaryagondi`).
5. **Reporting area** — `dev/reports/<handle>/` with a README; migrate the inaugural ASO-tox report in as the
   first tracked example.
6. **Harness doc updates** — `dev/README.md`, `METHODOLOGY.md`, `CONVENTIONS.md`, `GATES.md`: multi-contributor
   roles, branch naming, `Built-By` trailer, the PR-gated ship path + the approver gate, reports location.
7. **Orientation update** — root `CLAUDE.md`: replace "work on the `Rohan` branch" with the feature-branch +
   PR-to-`main` model.
8. **Ship via the new flow** — open a PR `rohan/collab-harness` → `main`; Rohan's Claude reviews + approves +
   merges (inaugural reference PR). Branch protection would be applied here (CODEOWNERS must be on `main`
   first) — but it is BLOCKED by the plan tier (see decision #2); apply once the plan is resolved.

## Definition of Done
- [ ] All files above exist, internally consistent (no contradictions across README/METHODOLOGY/GATES/CONVENTIONS).
- [ ] `.github/CODEOWNERS` is syntactically valid; PR template renders.
- [ ] Branch surgery verified: `main` = bedrock, backup preserved, `Rohan` gone.
- [ ] This change merged to `main` via a PR through the documented flow.
- [~] Branch protection on `main` — BLOCKED by plan tier (403); deferred to the enforcement decision. CODEOWNERS
      in place so it can be turned on the moment the plan is upgraded.
- [ ] Full test suite still green (no runtime code touched, but confirm — 278).
- [ ] Ledger entry with `Built-By: rohan`.

## Out of scope
- Adding Hayes/Gavin as repo collaborators (needs their GitHub usernames — flagged to Rohan as the follow-up).
- Any product/runtime code change. CI/GitHub Actions automation of the gates (future; manual review for now).
- An auto-watcher that triggers PR review (Rohan invokes his Claude to review; revisit later).
