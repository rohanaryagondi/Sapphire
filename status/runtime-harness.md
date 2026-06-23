# Status — Runtime Harness

*The product runtime harness (distinct from the `dev/` build harness). Updated 2026-06-22.* Code:
`sapphire-orchestrator/harness/`, registry `harness/agents.json`, contracts `sapphire-orchestrator/contracts/`.

## State
- ✅ **Done.** One runtime every product agent runs through: declare → dispatch → validate → guard → stamp →
  trace. `harness.run(agent_id, inputs)`.
- ✅ **22-agent registry** (`agents.json`). Dispatch by kind: `claude` / `qmodels` / `python` / `emet`.
- ✅ Mechanical guardrails: data-boundary BLOCKS, personas no-tools + must-cite, veto-is-a-gate, provenance
  stamped from the allowed set in `contracts/provenance.py`.
- ✅ Fail-safe: abstain/escalate on guardrail or schema failure — never fabricates. Append-only trace at
  `RohanOnly/engagements/<id>/trace.jsonl`; `trace_view.py` for transparency.
- ✅ Self-improvement loop (`memory/` + `selfimprove/`): public-only memory, entity recall, active-learning
  spine, tiered governance.

## Open items
- None blocking. New agents (e.g. ASO Design) are added here with an `output_schema` — recall the aso-tox
  lesson: a fact-emitting agent's schema must list every field the seam can return (`additionalProperties:
  false` otherwise silently abstains and drops facts).

## Watch-outs
- Adding/altering an agent's schema is high-leverage — a too-strict schema silently abstains. Always verify a
  new agent's output lands in the dossier through `run_live`, not just a unit test (Gate 5).
