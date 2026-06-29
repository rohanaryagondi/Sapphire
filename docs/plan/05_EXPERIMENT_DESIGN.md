# 05 — Experiment Design (build plan · step 4)

> Status: 🔵 PLANNED. The **experiment** capability class — the firm proposes the wet-lab experiment that
> resolves the engagement's top open question. This is what *closes the design–decision loop*.

## Goal
At synthesis, turn the dossier's unresolved items — **DIVERGENCEs** (internal↔external conflicts, often the
alpha), **KNOWN_UNKNOWNs**, and any **designed candidates** awaiting validation — into a **structured,
actionable experiment proposal**: hypothesis · platform/assay · perturbations · readout · controls · sample
size/power · decision rule · *what it resolves*. The natural platform is **Quiver's own optical-electro­
physiology (OEP) assay** (the same substrate the moat is built on), which lets the firm propose experiments
Quiver can actually run.

## Current state 🟡
- Synthesis already emits a **freeform** `proposed_experiment` string (`synth.proposed_experiment`, rendered
  in the console). It's unstructured and not derived from the flags.
- **Prior art exists** — the ED-1 effort: the brief `docs/superpowers/plans/2026-06-23-experiment-design-tool.md`,
  a vendored `vendor/design-form-agent/` (with `sample_extraction_jan6.json`), and `tools/experiment_design/`.
  **Build on this, don't reinvent.** (Verify these paths first; if absent, start from the brief.)

## Target
An **Experiment Design seam** (`class: "experiment"`) that consumes structured inputs and emits a structured
proposal, replacing the freeform string with a real, schema'd deliverable.

## Build steps
1. **Land the tool.** Port/finish the ED-1 tool into `tools/experiment_design/` per its brief — copy the
   assay vocabulary / `MENUS_REFERENCE` / extraction prompt **verbatim** with attribution; keep heavy deps
   (Anthropic SDK / PDF) in the tool subprocess (engine stays stdlib-only); lock it with a **golden-value
   fidelity test** against `vendor/design-form-agent/sample_extraction_jan6.json`. (Per the resolved ED-1 HELP item.)
2. **The seam** — `sapphire-orchestrator/tools/experiment_design_seam.py` (kind `python` or `claude`).
   - **Input** (public/internal-reasoning, no external leak): the dossier's `flags.DIVERGENCE` +
     `flags.KNOWN_UNKNOWNS` + the synthesis recommendation + (optional) the design-tool candidate bundle.
   - **Output** (schema in `contracts/`): `{hypothesis, platform, perturbations[], readout, controls[],
     n_per_arm, power, decision_rule, resolves:[<flag refs>], provenance:"experiment-design"}`.
3. **Activation.** Fires at **synthesis** whenever there are unresolved DIVERGENCE/KNOWN_UNKNOWN items or a
   designed candidate to validate. Unlike design tools (D5: explicit-ask, ~3 hr AWS), this is **reasoning,
   not compute** — cheap — so it can fire **by default at synthesis** when there's something to resolve.
4. **Deliverable.** Replace the freeform `proposed_experiment` with the structured proposal in the report
   (and the console synthesis block). Each proposal cites *which* open item it resolves.
5. **Honest degradation.** If there's nothing unresolved → no proposal (don't invent an experiment). If the
   tool can't run → abstain, keep the freeform fallback labeled.

## Why this is high-leverage
It makes Sapphire's output *actionable*, not just a verdict — and it's the natural endpoint of the loop in
[`00 §0`](00_FULL_FLOW.md): assess → (design) → deliberate → **propose the test**. It also pairs with the
self-improvement loop: a proposed experiment that gets run produces an outcome that updates the moat
(`record_outcome` → `moat_blindspot`).

## DoD
A `run_live` engagement with a DIVERGENCE (e.g. a Quiver-alpha rescue with no published mechanism) yields a
**structured** experiment proposal that names the OEP assay, controls, n/power, decision rule, and the exact
flag it resolves; the freeform string is gone; golden-value test green; honest "no proposal when nothing
unresolved" path tested.

## Gates
Suite green · independent review · provenance + no secrets · stdlib-engine boundary (deps in the subprocess) ·
**Gate 5:** drive a real engagement that carries a DIVERGENCE end-to-end and confirm the structured proposal
renders + cites the resolved flag.

## Risks / notes
- Don't over-scope the assay menu in v1 — start with OEP + the ED-1 vocabulary; expand later.
- Keep the proposal honest: it proposes a test, it does not claim the result.
- Sequence after Phase A of [`04`](04_FRONT_DOOR.md) (needs the flags populated by the whole live firm).
