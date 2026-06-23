# Status — Engine

*The orchestration engine. Updated 2026-06-22.* Code: `sapphire-orchestrator/orchestrator.py`,
`live_engine.py`, `run.py`, `engagement.py`, `serve.py`.

## State
- ✅ **Two execution paths exist:**
  - **Canned path** — `orchestrator.run(sid)` replays pre-captured scenario JSONs. $0, deterministic. Used by
    `run.py` / `serve.py` / the Console today.
  - **Live harnessed path** — `live_engine.run_live(query)` dispatches **every** agent + persona through
    `harness.run` (guard-enforced, schema-validated, provenance-stamped, traced). Verified **offline** with
    mock backends + the real moat.
- ✅ Real triage → scope → plan; Bucket-1 dossier with completeness/contradiction/VETO/DIVERGENCE rules;
  Bucket-2 two-round roundtable + spread; deterministic synthesis.
- ✅ `run_live(..., sequences=[...])` feeds ASO sequences to the `aso-tox` agent (shipped 2026-06-22).

## Open items
1. **Wire `run_live` to the front door (the keystone).** `serve.py`/Console still use the canned path. Until
   this lands, demos do not exercise the live harnessed firm. → backlog `frontdoor-wire-run-live`.
2. **Broaden captured scenario coverage** across the 10-axis variety matrix (`scenarios/manifest.json`); most
   axes are honest `stub`. → backlog `scenario-coverage`.

## Watch-outs
- Don't claim the Console is "live" — it's the canned path. Be precise in any demo/deck.
- The engine is **stdlib-only**; keep third-party deps in `_build/` or tool subprocesses (Gate 4).
