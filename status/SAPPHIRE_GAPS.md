# Sapphire — known product gaps (as of 2026-06-28)

Living record of **product** gaps found in an evidence-based evaluation (code-verified, not doc-trusted).
This is documentation only — these are NOT yet fixed. The build harness gaps are being fixed separately
(branch `rohan/harness-hardening`); this file tracks the **product** (engine / agents / front door).

> Source: independent Sonnet judge pass over `sapphire-orchestrator/`, `architecture/`, `frontend2/`,
> `orchestrator_ui/` (branch `rohan/orchestrator-8101`). Each item cites the file that proves it.
> Overall product grade at evaluation time: **B−** — integrity is genuine; the gap is *completeness*.

## What's solid (so we don't re-litigate it)
- Guardrails enforced in code (`harness/runtime.py`, `harness/guardrails.py::data_boundary` — a test proves
  `QS00123` abstains, not leaks). Honest degradation (moat → `[]` when SQLite absent). ASO-tox runs a real
  model. Q-Models GPU tracks honestly marked `gpu-unproven`. Tests are *understated*, not inflated
  (~706 green on the harness branch; LLM backends mocked, real backends skipped when deps absent).

## Gaps (priority-ordered)

### P0 — the live firm is materially weaker than the demo
1. **Round 2 (rebuttal) + spread missing from `run_live`.**
   `sapphire-orchestrator/live_engine.py` returns only `{round1}`; the canned `orchestrator.py` returns
   `{round1, round2, spread}`. "The spread is the product," and the live path doesn't produce it.
   *Fix sketch:* port the rebuttal loop + spread computation (~live_engine.py ll. 640–703); contracts +
   persona subagents already support it.
2. **6 of 13 semantic agents never fire in the live path.**
   `live_engine._BUCKET1_AGENTS` dispatches 7; `dea-scheduling`, `manufacturing-cmc`, `patient-advocacy`,
   `kol-social`, `policy-legislative`, `reputational` are fully specced + in `harness/agents.json` but
   absent from the dispatch list. *Fix:* add them to `_BUCKET1_AGENTS` (~live_engine.py l. 39).

### P1 — convergence + correctness
3. **VETO is surfaced, not gated.** `guardrails.py::veto_is_gate` blocks silent drops, but the roundtable
   runs unconditionally; there is no mechanical adjudication step despite `AGENTS.md` describing one.
   *Fix:* between Bucket-1 completion and Bucket-2 dispatch in `live_engine.py`, if `veto_flags` is
   non-empty, open with an explicit adjudication step.
4. **Front-door path proliferation (the real "keystone").** Three live paths now coexist: canned
   `orchestrator.run`, harnessed `run_live`, and the `:8101` `claude -p` console (`orchestrator_ui/`).
   `serve.py GET /api/run` → harnessed engine, but `POST /api/chat` still spawns the old subprocess and
   `site/index.html` still renders canned data. *Fix:* pick ONE live path; point `/api/chat` + the Console
   at it; retire the others or clearly demote them.
5. **EMET "live" is environment-conditional.** `emet/handler.py` needs `$SAPPHIRE_EMET_CDP` (authenticated
   Chrome :9222) or `$SAPPHIRE_EMET_PROFILE` + `SAPPHIRE_EMET_ALLOW_HEADLESS=1`; otherwise it honestly
   abstains (`login_required`). The claim "EMET = live" overstates the out-of-box default. *Fix:* either
   document the setup as required, or wire the Chrome-Claude worker queue as the default live path.

### P2 — doc / signal hygiene
6. **`CLAUDE.md` is stale** — says `run_live` is "NOT yet wired to the front door" (partially done), claims
   278 tests (actual ~706), and omits gaps #1–#3. Update it.
7. **`serve.py` health label hardcodes `"moat": "mock"`** even when the real moat would run — compute it
   from `MoatClient.available()`.

## Highest-leverage next step
Close #1 + #2 together (small, contract-supported edits in `live_engine.py`) — that alone roughly doubles
semantic coverage and restores the roundtable spread, making the live firm match the demo it's selling.
