# Sapphire — Architecture Plan (living blueprint)

This is the **forward-looking** plan for how the whole of Sapphire fits together as it grows — the place
where we *ideate and flesh out the full flow* before building. It is deliberately separate from
[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md), which documents the system **as it is today**.

- **`ARCHITECTURE.md`** = current state (what's built, what's wired).
- **`docs/plan/`** (this set) = target state + the path to it (what we're building toward, the seams, the open decisions).

Audience: the build team (rohan · hayes · gavin, each driving Claude). Treat it as the blueprint we
execute against. It's a living document — when a decision is made, fold it into the relevant doc and update
the status; when reality changes, update it. Don't let it drift (that's the lesson from the stale `CLAUDE.md`).

## The set

| Doc | What it covers |
|---|---|
| [`00_FULL_FLOW.md`](00_FULL_FLOW.md) | **The end-to-end target blueprint** — one query → the firm (control + two buckets) → the tool suite → the report/deliverable. The big diagram + every layer + the tool-suite map + what's built vs planned. Read this first. |
| [`01_TOOL_SEAM_PATTERN.md`](01_TOOL_SEAM_PATTERN.md) | **The reusable pattern** for plugging any Quiver tool into the firm — the seam contract, where a tool fires, the data boundary, provenance, where it runs (inline vs sandbox vs AWS), honest degradation, and how its output reaches the dossier. The thing every new tool conforms to. |
| [`02_ASO_DESIGN.md`](02_ASO_DESIGN.md) | **The worked example** — the ASO Design pipeline (a heavy, multi-stage, AWS-orchestrated *design* tool) mapped onto the seam pattern: how it wraps, how it composes the existing `aso-tox`, what it produces, and the open questions it forces. |
| [`03_OPEN_DECISIONS.md`](03_OPEN_DECISIONS.md) | **The decision log** — the cross-cutting architecture decisions we still need to make (front-door convergence, where tools run, design-vs-evidence capability split, …). We resolve these here together, then fold the answer into the docs above. |

## Status legend (used throughout)
- 🟢 **BUILT** — exists and is wired/tested today.
- 🟡 **PARTIAL** — exists but degraded, unwired, or behind a flag.
- 🔵 **PLANNED** — designed here, not yet built.
- ⚪ **PROPOSED** — an idea on the table; needs a decision (see `03_OPEN_DECISIONS.md`).

## How this relates to the rest of the docs
- North star / why: [`docs/VISION.md`](../VISION.md).
- Current build state: [`status/OVERALL.md`](../../status/OVERALL.md), [`status/SAPPHIRE_GAPS.md`](../../status/SAPPHIRE_GAPS.md).
- Loka (the front-end / orchestrator scaffold the Quiver tools plug into): [`docs/LOKA.md`](../LOKA.md).
- The operating model + agent roster: [`sapphire-orchestrator/AGENTS.md`](../../sapphire-orchestrator/AGENTS.md).
</content>
