# WO-4 — Experiment Design (the experiment-class tool; closes the loop)

**For:** Rohan Claude (worker) · **Branch:** `rohan/experiment-design` cut from `main` · **Plan:** [`docs/plan/05_EXPERIMENT_DESIGN.md`](../../docs/plan/05_EXPERIMENT_DESIGN.md)
**Lifecycle:** `/sapphire-build`. **Blocked? →** `dev/HELP.md`. **Depends on:** WO-2 Phase A (flags populated by the whole live firm).
**Build on prior art (verify first):** the ED-1 brief `docs/superpowers/plans/2026-06-23-experiment-design-tool.md`, the vendored `vendor/design-form-agent/` (`sample_extraction_jan6.json`), and `tools/experiment_design/`. Don't reinvent.

## Goal
At synthesis, turn unresolved **DIVERGENCEs / KNOWN_UNKNOWNs** (and any designed candidates) into a
**structured, actionable experiment proposal** on **Quiver's OEP assay** — replacing the current freeform
`synth.proposed_experiment` string.

## Steps
1. **Land the tool.** Finish/port ED-1 into `tools/experiment_design/` per its brief — copy the assay
   vocabulary / `MENUS_REFERENCE` / extraction prompt **verbatim** with attribution; heavy deps (Anthropic
   SDK / PDF) in the tool subprocess (engine stays stdlib-only); lock with a **golden-value fidelity test**
   against `vendor/design-form-agent/sample_extraction_jan6.json`.
2. **The seam** `sapphire-orchestrator/tools/experiment_design_seam.py` (kind `python` or `claude`,
   `class:"experiment"`, `provenance:"experiment-design"`). Input: `flags.DIVERGENCE` + `flags.KNOWN_UNKNOWNS`
   + the synthesis recommendation + (optional) the design-tool candidate bundle. Output (schema in
   `contracts/`): `{hypothesis, platform, perturbations[], readout, controls[], n_per_arm, power,
   decision_rule, resolves:[<flag refs>], provenance}`.
3. **Activation.** Fires at **synthesis** whenever there's an unresolved DIVERGENCE/KNOWN_UNKNOWN or a
   candidate to validate. It's reasoning, not compute (cheap) → may fire **by default** at synthesis (unlike
   the AWS design tool, which is explicit-ask). No unresolved items → no proposal (don't invent one).
4. **Deliverable.** Replace the freeform `proposed_experiment` with the structured proposal in the report +
   the console synthesis block; each proposal cites which flag it resolves.

## DoD
A `run_live` engagement carrying a DIVERGENCE (e.g. a Quiver-alpha rescue with no published mechanism) yields
a **structured** proposal naming the OEP assay, controls, n/power, decision rule, and the exact flag it
resolves; freeform string gone; golden-value test green; "no proposal when nothing unresolved" tested.

## Gates
Suite green · independent review · provenance + no secrets · stdlib-engine boundary (deps in subprocess) ·
**Gate 5:** drive a real DIVERGENCE engagement end-to-end and confirm the structured proposal renders + cites
the resolved flag.

## Notes
Don't over-scope the assay menu in v1 (OEP + the ED-1 vocabulary). It proposes a test; it never claims the
result. Pairs with the self-improvement loop (`record_outcome` → `moat_blindspot`) once experiments are run.
