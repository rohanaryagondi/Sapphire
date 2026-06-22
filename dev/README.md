# Sapphire Dev Harness

**This directory is the system Claude agents (and humans) use to *build* Sapphire — not part of Sapphire itself.**

Sapphire is a long-term, high-stakes build. To keep it correct, honest, and fast as it grows, every change goes through a disciplined process with a defined set of agent roles and non-negotiable quality gates. That process *is* the dev harness. It lives here, in the repo, versioned alongside the code — it does not depend on any external plugin.

---

## The one distinction that matters: Product vs. Build

| | **Sapphire (the product)** | **The Dev Harness (this dir)** |
|---|---|---|
| What it is | the firm that answers drug-discovery questions | the process that builds the firm |
| "Harness" | **runtime harness** — `sapphire-orchestrator/harness/` (the engine that dispatches *product* agents: internal-science-lead, EMET, personas, …) | **dev harness** — `dev/` (the methodology + roles + gates that dispatch *builder* agents: planner, implementer, reviewer, …) |
| "Skills/Agents" | product skills (`.claude/skills/sapphire*`, `emet-runner`) and the 22-agent product registry | build agents (`.claude/agents/sapphire-dev-*`) and the build skill (`.claude/skills/sapphire-build`) |
| Audience | Quiver's scientists & decision-makers | the engineering loop |

Never conflate them. A "reviewer" in the runtime harness is a *persona judging a drug program*; a "reviewer" in the dev harness is a *subagent judging a code change*. When in doubt, prefix: **runtime** vs **dev**.

---

## What's in here

| File | What it governs |
|---|---|
| [`METHODOLOGY.md`](METHODOLOGY.md) | The build lifecycle (in-repo SDD) and the dev-agent roles |
| [`CONVENTIONS.md`](CONVENTIONS.md) | The binding engineering rules every change must follow |
| [`GATES.md`](GATES.md) | Definition of Done — the mandatory gates before anything lands on `main` |
| [`CONTRIBUTORS.md`](CONTRIBUTORS.md) | Who builds Sapphire, the Claude each drives, attribution, ownership |
| [`DELEGATION.md`](DELEGATION.md) | The live task-assignment board + the claim protocol |
| [`PR_REVIEW.md`](PR_REVIEW.md) | The approver playbook — how Rohan's Claude gates a PR before merge |
| [`LEDGER.md`](LEDGER.md) | Append-only build log (what shipped, when, which commit, `Built-By`) |
| [`reports/`](reports/) | Per-contributor build reports (`reports/<handle>/`) |
| [`templates/`](templates/) | Reusable prompts: task brief, code review, functional verify |

GitHub plumbing: [`.github/CODEOWNERS`](../.github/CODEOWNERS) (every PR needs Rohan's review),
[`.github/pull_request_template.md`](../.github/pull_request_template.md) (gate-evidence checklist), and
[`.github/workflows/branch-guard.yml`](../.github/workflows/branch-guard.yml) (flags direct pushes to `main`).
Branch-rule enforcement: [`.githooks/`](../.githooks/) + [`dev/setup-contributor.sh`](setup-contributor.sh)
(client-side guards) and [`CONTRIBUTOR_RULES.md`](CONTRIBUTOR_RULES.md) (the hard rules for contributor agents).

## Collaboration model (rohan · hayes · gavin)

Sapphire is built by three contributors, each driving their own Claude. The model:

- **Everyone branches off `main`** as `<handle>/<slug>` (e.g. `hayes/aso-design-tool`). The former `Rohan`
  bedrock branch *is* `main` now; the pre-collaboration `main` is preserved at `main-backup-2026-06-22`.
- **Attribution is git-native:** branch prefix + a `Built-By: <handle>` commit trailer (alongside the Claude
  `Co-Authored-By`) + the `CONTRIBUTORS.md` registry. No in-file tags. `git log`/`blame` answer "who built this".
- **Contributors run the full local lifecycle** (Gates 1–5) and **ship by opening a PR** — they never merge.
  First thing in any clone: `bash dev/setup-contributor.sh <handle>` to install the branch guards. Contributor
  agents (hayes/gavin) are bound by `CONTRIBUTOR_RULES.md`.
- **Only Rohan's Claude reviews, approves, and merges to `main`** — re-establishing the gates independently on
  the PR (`PR_REVIEW.md`). Enforcement is layered (`CONVENTIONS.md` §1): client-side hooks hard-block main
  pushes / wrong branch names / missing `Built-By`; the `branch-guard` Action flags any direct push to `main`;
  CODEOWNERS routes review. *Hard* server-side branch protection needs GitHub Pro (`dev/enable-branch-protection.sh`
  applies it once upgraded); until then layers above hold the line and are treated as binding.

Runnable assets (so the process is enforced, not just described):
- `.claude/agents/sapphire-dev-{planner,implementer,reviewer,verifier,integrator}.md` — the builder roles.
- `.claude/skills/sapphire-build/SKILL.md` — the workflow that runs the lifecycle end-to-end.

---

## How to use it (the 30-second version)

The **controller** (the main Claude loop, or a human lead) owns an engagement and never writes feature code directly when it can delegate. The flow:

```
on your branch <handle>/<slug>:
PLAN ─▶ per task: TASK-BRIEF ─▶ IMPLEMENT ─▶ REVIEW ─▶ fix ─▶ VERIFY (does it actually work?) ─▶ fix
                                                                          │
                          (feature complete) ─▶ WHOLE-BRANCH REVIEW ─▶ OPEN PR ─▶ [Rohan's Claude gates + merges]
```

A contributor's branch ships by **opening a PR to `main`**. Rohan's Claude is the sole approver: it
re-establishes the [gates](GATES.md) on the PR, then merges and writes the [ledger](LEDGER.md) entry. The
single most important gate — added because "tests pass" is not the same as "it works" — is **functional
verification**: a `sapphire-dev-verifier` agent that actually runs the thing, adversarially, and sends it
back for fixes if it doesn't behave.

Start a build by invoking the **`sapphire-build`** skill, or by reading `METHODOLOGY.md` and driving it manually.

---

## Principles (why this exists)

1. **Honesty over optimism.** A green test suite is a claim, not a proof. We verify behavior, label provenance, and report failures plainly. We never fabricate data or overclaim "done."
2. **The controller stays lean.** Heavy reading, building, and reviewing happen in subagents so the controller keeps a clear head and a long horizon.
3. **Separation of powers.** The agent that builds a change does not get to approve it. Review and verification are independent.
4. **Self-contained & portable.** This harness is plain files in the repo. It works on any machine, for any contributor, with no plugin to install.
