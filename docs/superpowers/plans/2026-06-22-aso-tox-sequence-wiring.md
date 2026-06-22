# Task Brief — Feed ASO sequences into `run_live` so `aso-tox` produces dossier facts

*Tier: Standard. First exercise of the dev harness (`dev/`). Follow the lifecycle in `dev/METHODOLOGY.md`; honor `dev/CONVENTIONS.md`; pass `dev/GATES.md` — especially Gate 5 (functional verification): actually run it and show tox facts in the dossier.*

## Goal
The `aso-tox` tool is integrated and correct, but `run_live` has no way to pass ASO sequences to it, so it always runs empty. Give `run_live` a sequence-input channel and thread it to the `aso-tox` agent, so a query that carries ASO candidate sequences yields real tox facts (provenance `aso-tox`) in the dossier — and so the forthcoming ASO-Design tool has a defined handoff.

## Context the implementer needs
- Read first:
  - `sapphire-orchestrator/live_engine.py` — `run_live(...)`; the Bucket-1 dispatch loop that builds each agent's `inputs` dict; the `_BUCKET1_AGENTS` list; where `ctx["python_fns"]["aso-tox"]` is wired (~lines 48, 136–137).
  - `sapphire-orchestrator/tools/aso_tox_seam.py` — `predict_findings(inputs)` reads `inputs.get("sequences") or inputs.get("aso_sequences") or []`.
  - `sapphire-orchestrator/tests/test_live_engine.py` — the offline-mock `ctx` pattern to reuse.
  - `sapphire-orchestrator/engagement.py` — `extract_entities` (for the style of a query-extraction helper, if you add one).
- Verified current behavior: `run_live(...)` dispatches `aso-tox` (status ok) but harvests 0 tox facts because no sequences reach it. Calling the seam directly with sequences returns correct facts.

## What to build
1. Add an explicit sequence channel to `run_live` — a keyword param (e.g. `run_live(query, *, sequences=None, ctx=None, ...)`). Thread the provided sequences into the per-agent `inputs` dict so the `aso-tox` python_fn receives them (e.g. `inputs["sequences"] = sequences or []`). Keep all existing behavior intact (additive, default `None`).
2. (Secondary, optional but preferred) A conservative query-extraction helper: detect explicit ASO sequences embedded in the query text — standalone tokens that are pure `A/T/G/C`, length ≥ 15 — and feed those too. Must NOT false-positive on gene symbols/ordinary text; if unsure, prefer the explicit param and keep extraction strict. Unit-test the extractor's negative cases.
3. The same `sequences` channel is the documented handoff point for the future ASO-Design tool (note it in a comment).

## Constraints (binding — see `dev/CONVENTIONS.md`)
- Runtime stays **stdlib-only**: `live_engine.py` gains no third-party import; sklearn stays in the tool subprocess via the seam.
- Provenance: tox facts carry `aso-tox` (already set by the seam) — don't re-stamp.
- Don't modify the tool's scientific logic (`tools/aso_tox/predict.py`, the `.pkl`) — this task is purely the feed.
- No secrets/binaries.

## Definition of Done
- [ ] `run_live("...", sequences=["GCACTTGAATTTCACGTTGT","TTGCTCCACCTTGGCCTGGCA"], ctx=<offline mocks + real seam>)` puts ≥1 fact with `provenance=="aso-tox"` into `discover["dossier"]`, with the correct GBR/label content.
- [ ] A normal target query (no sequences) still dispatches `aso-tox` and contributes `facts: []` with no error (unchanged honest-empty behavior).
- [ ] (if extractor added) sequences embedded in a query string are detected; gene symbols / ordinary words are NOT misread as sequences (negative test).
- [ ] New/updated tests in `tests/test_live_engine.py` (offline, $0) assert the above. Full suite green (was 268).
- [ ] **Gate 5:** the verifier RUNS `run_live` with sequences and shows the real tox facts landing in the dossier (not just a passing unit test).
- [ ] Short report to `.git/sdd/aso-tox-wiring-report.md`.

## Out of scope
- The ASO-Design tool itself (doesn't exist yet) — only define/leave the handoff channel.
- Wiring `run_live` into `serve.py`/Console (that's the separate keystone task, REPORT §6 #2).
- Any change to the tox model logic or the canned `orchestrator.run` path.
