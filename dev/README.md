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
| [`GATES.md`](GATES.md) | Definition of Done — the mandatory gates before anything lands on `Rohan` |
| [`LEDGER.md`](LEDGER.md) | Append-only build log (what shipped, when, which commit) |
| [`templates/`](templates/) | Reusable prompts: task brief, code review, functional verify |

Runnable assets (so the process is enforced, not just described):
- `.claude/agents/sapphire-dev-{planner,implementer,reviewer,verifier,integrator}.md` — the builder roles.
- `.claude/skills/sapphire-build/SKILL.md` — the workflow that runs the lifecycle end-to-end.

---

## How to use it (the 30-second version)

The **controller** (the main Claude loop, or a human lead) owns an engagement and never writes feature code directly when it can delegate. The flow:

```
PLAN ─▶ per task: TASK-BRIEF ─▶ IMPLEMENT ─▶ REVIEW ─▶ fix ─▶ VERIFY (does it actually work?) ─▶ fix
                                                                          │
                          (feature complete) ─▶ WHOLE-BRANCH REVIEW ─▶ LEDGER ─▶ COMMIT/PUSH
```

Every arrow into `COMMIT/PUSH` is blocked by the [gates](GATES.md). The single most important gate — added because "tests pass" is not the same as "it works" — is **functional verification**: a `sapphire-dev-verifier` agent that actually runs the thing, adversarially, and sends it back for fixes if it doesn't behave.

Start a build by invoking the **`sapphire-build`** skill, or by reading `METHODOLOGY.md` and driving it manually.

---

## Principles (why this exists)

1. **Honesty over optimism.** A green test suite is a claim, not a proof. We verify behavior, label provenance, and report failures plainly. We never fabricate data or overclaim "done."
2. **The controller stays lean.** Heavy reading, building, and reviewing happen in subagents so the controller keeps a clear head and a long horizon.
3. **Separation of powers.** The agent that builds a change does not get to approve it. Review and verification are independent.
4. **Self-contained & portable.** This harness is plain files in the repo. It works on any machine, for any contributor, with no plugin to install.
