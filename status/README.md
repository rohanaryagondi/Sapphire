# Status

The live state of the Sapphire build — what's done, what's in flight, and who's building what. This directory
is the bridge between the **vision** (`docs/VISION.md`), the **architecture** (`docs/ARCHITECTURE.md`), and
**work assignment**.

## What's here
| File | What it tells you |
|---|---|
| [`OVERALL.md`](OVERALL.md) | The one-screen build status — phase, test count, what's live vs mock, top risks. Start here. |
| [`WORKBOARD.md`](WORKBOARD.md) | **The workboard** — per-agent assignments (rohan / hayes / gavin) + the shared backlog. Where each contributor's Claude looks for "what's pending for me." |
| `engine.md` | Status of the orchestrator engine (`orchestrator.py`, `live_engine.py`, `run_live`). |
| [`frontend-loka.md`](frontend-loka.md) | Front-end / LOKA integration + the `run_live`-as-front-door keystone. |
| `runtime-harness.md` | Status of the product runtime harness (`sapphire-orchestrator/harness/`) + the 22-agent registry. |
| `tools.md` | Status of the fact sources/tools: moat, EMET, Q-Models, ASO-tox. |
| `dev-harness.md` | Status of the build system itself (`dev/` — this collaborative harness). |

## How it connects to work
```
docs/VISION.md   →  why we build           (north star)
status/OVERALL   →  where we are           (state)
status/<area>    →  state per subsystem     (detail + the open items)
status/WORKBOARD →  who builds what next    (assignment)  ←─ open items flow here
dev/DELEGATION   →  HOW to claim/assign     (the protocol)
dev/METHODOLOGY  →  HOW to build it         (the lifecycle + gates)
```
An **open item** in an area status doc, once assigned, becomes a row on the **workboard** under an owner; the
owner follows `dev/DELEGATION.md`'s claim protocol and `dev/METHODOLOGY.md`'s lifecycle to ship it.

## Keeping it honest
Status docs follow the same rule as everything else: **state what's real.** Mark live vs mock, proven vs
paper-claim. Update the relevant area doc + `OVERALL.md` in the same PR that changes a subsystem's state (the
approver checks this at merge). A stale status doc is a defect.
