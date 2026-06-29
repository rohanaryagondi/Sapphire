# Work orders — Sapphire next build wave

Self-contained task briefs for contributor (Rohan Claude) sessions. Each names its branch, its plan doc,
its dependencies, the steps, the Definition of Done, and the gates. Drive each with `/sapphire-build`
(plan→implement→review→verify→ship). If blocked on something you shouldn't guess about, append to
[`dev/HELP.md`](../HELP.md) and keep working on anything unblocked.

| WO | Title | Branch | Plan | Depends on | Priority |
|---|---|---|---|---|---|
| [WO-2](WO-2-front-door.md) | Front door: one live path (make live firm whole → converge) | `rohan/front-door` | [04](../../docs/plan/04_FRONT_DOOR.md) | — | **P0 (keystone)** |
| [WO-3](WO-3-aso-design.md) | ASO Design seam (first design-class tool) | `rohan/aso-design` | [02 §7](../../docs/plan/02_ASO_DESIGN.md) | WO-2 Phase A | P1 |
| [WO-4](WO-4-experiment-design.md) | Experiment Design (closes the loop) | `rohan/experiment-design` | [05](../../docs/plan/05_EXPERIMENT_DESIGN.md) | WO-2 Phase A | P1 |
| [WO-5](WO-5-moat-rescue-fix.md) | Moat rescue-ranking fix (port Loka scoring) | `rohan/moat-rescue-fix` | [06](../../docs/plan/06_LOKA_ASSETS.md) | — (parallel) | high value / low cost |
| [WO-6](WO-6-semantic-agents.md) | Semantic agents → production-grade (corpus + API + spec, per agent, all 13; start w/ scientific cluster) | `rohan/semantic-agents` | — | — (the 13 already dispatch) | **high** |

## Suggested order
1. **WO-2 Phase A** first — it unblocks everything (the whole live firm + the `class` field).
2. **WO-5** in parallel from the start — independent, high value, low cost (fixes the rescue ranking).
3. Then **WO-2 Phase B**, then **WO-3** and **WO-4** (both need Phase A; can be sequential or two sessions).

Only Rohan's Claude (Head Claude / the approver) reviews + merges PRs. Push your gated branch; the approver
opens + merges (`dev/PR_REVIEW.md`). The approver can now push main bookkeeping without `--no-verify`
(PR #110 carve-out); `--no-verify` is forbidden for everyone.
