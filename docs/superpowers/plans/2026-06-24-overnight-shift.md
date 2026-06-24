# Overnight Autonomous Shift — worker plan (2026-06-23 → 24)

*An autonomous overnight build run by a dedicated **rohan worker session** (separate clone). It builds the
LOKA-independent critical path so the backend is end-to-end-capable before LOKA lands tomorrow. Rohan's
**auditor session** (separate) reviews → Gate-5 verifies → auto-merges each PR when all gates are green.
Context: `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md`, `status/frontend-loka.md`.*

## Operating model
- **Worker (you, this session):** build the tasks below **serially**, one branch + one PR each. After opening
  a PR, **wait for the auditor to merge it** (poll `gh pr view <n>`); when merged, `git checkout main && git
  pull`, then start the next task off fresh `main`. Address any change-requests the auditor leaves (PR comments
  / `dev/HELP.md`) on the same branch. Do NOT merge your own PRs.
- **Auditor (Rohan's other session):** independent review + Gate-5 verification on every PR; **auto-merge when
  all gates pass**, else hold + document. Builder ≠ approver (separation of powers) holds because the sessions
  are distinct.
- **Halt** only when: all three tasks are merged (scope complete), you're blocked (post `dev/HELP.md`, keep
  going on anything unblocked), or a gate you cannot make pass (document it, stop that task, continue others).

## Order (serial — each off fresh `main`)
**H (hygiene) → K1 → K2.** Hygiene first: it's small, and fixing the clone-dir test (#1) de-risks running the
suite from any directory. Then the two keystones.

---

## Task H — crossplatform-test-hardening  (branch `rohan/crossplatform-test-hardening`)
Fix 3 pre-existing cross-platform test failures Hayes flagged (resolved HELP entry). **Facts/behavior unchanged
— these are portability fixes.**
1. `sapphire-orchestrator/moat/tests/test_client.py` (~line 153) hardcodes the clone dir name
   `sapphire-capability-map`. Derive the expected suffix from the repo root (e.g. compute the repo dir name at
   runtime, or assert the path ends with `<repo_root_basename>/RohanOnly/moat/moat.sqlite`) so a clone in any
   directory name passes.
2. `sapphire-orchestrator/tests/test_scenarios.py::test_captured_scenarios_exist_and_validate` →
   `UnicodeDecodeError` on Windows (cp1252): add `encoding="utf-8"` to the offending file read.
3. `sapphire-orchestrator/tests/test_trace_view.py::test_main_returns_0_for_valid_eid` → `UnicodeEncodeError`
   writing `✓` to a cp1252 stdout: guard the stdout write (encode-safe) or set UTF-8 on the stream.
- **DoD:** full suite green; the moat test passes regardless of clone dir name; (2)/(3) no longer assume a
  UTF-8 locale. Report in `dev/reports/rohan/crossplatform-test-hardening-report.md`.

---

## Task K1 — `run_live` as a clean service boundary + the real front door  (branch `rohan/k1-run-live-service`)
Make the **harnessed live firm** reachable behind a stable contract — the integration point LOKA will use.
- **Freeze + document the contract.** `live_engine.run_live(query, *, sequences=None, ctx=None, registry=None,
  engine=None) -> dict` already returns `{query, plan, priors, discover{dossier,flags,agents}, consult{round1},
  synthesize, engagement_id, reflection, _via}`. Write a single source-of-truth doc of this output schema
  (`sapphire-orchestrator/contracts/run_live_schema.md` or a docstring + a `contracts/` schema) — this dict IS
  the API the front end consumes. Don't gratuitously change field names; if you add fields, additive only.
- **Make `serve.py` serve the harnessed firm.** `serve.py`'s `_run_live` (~line 206) is the
  headless-Claude/canned path. Add a real path that calls `live_engine.run_live(q)` behind `/api/run?q=`
  (keep the canned scenarios as an explicit, clearly-labeled `$0` offline fallback — do not delete them).
  Make the live-firm path the default when available; stamp the response `"via"` honestly
  (`engine-live` | `canned` | `claude-subscription`).
- **Stdlib-only engine** preserved (run_live already is; serve.py is stdlib http.server). The live LLM/EMET
  calls are already behind the harness/seams — ctx selects real vs mock backends.
- **DoD (Gate 5):** `GET /api/run?q="is TSC2 a viable CNS target?"` returns a **real harnessed `run_live`**
  result (or an honest degraded envelope if a backend is down) with `via` reflecting the live path — NOT a
  canned scenario. The output schema is documented in one place. Offline/test mode still works ($0) and is
  labeled. Tests: a test that `/api/run` (or the `_run_live` dispatcher) routes to `run_live` and returns the
  documented shape, offline-mockable. Report in `dev/reports/rohan/k1-run-live-service-report.md`.
- **Out of scope:** the LOKA adapter itself (LOKA's code isn't here yet) — K1 is the *boundary* LOKA will call.

---

## Task K2 — corpus runtime retrieval (corpus-first → search-the-gap)  (branch `rohan/k2-corpus-retrieval`)
Make Bucket-1 agents actually **read their knowledge corpus** at run time so the stable ~70% is answered
locally and only the gap goes to live web/EMET. Today the corpora (`sapphire-orchestrator/corpus/<agent>/`,
FDA-memory live; 12 delegated) are **inert**.
- **Stdlib corpus reader.** Add `sapphire-orchestrator/corpus/reader.py` (or under `harness/`) — stdlib only
  (`json`, `re`): given an `agent_id` + the query/entities, load `corpus/<agent_id>/index.jsonl` and return the
  matching claim-cards (match on the lens fields + entity terms; simple, deterministic, ranked by overlap;
  cap to a sane top-N). Return `[]` if the agent has no corpus dir (agents without a corpus are unchanged).
- **Wire into the Bucket-1 dispatch** (`live_engine.py`, the `for agent_id in _BUCKET1_AGENTS` loop ~line 244):
  for each agent that has a `corpus/<agent_id>/` dir, fetch matching cards and **add them to the dossier as
  corpus-sourced facts**, each carrying its card's `source` / `tier` / `url` and a provenance marker
  (add `corpus` to `contracts/provenance.py` allowed labels, or stamp the card's own source-type + a
  `from_corpus: true`). Pass the corpus hits to the agent as context so its live call targets the **gap** (for
  a first cut, surfacing corpus facts into the dossier + handing the agent the hits is the 80%; the live agent
  still runs for the uncovered part). Keep it **traced** (the harness trace should show corpus-sourced facts).
- **Veto rule intact:** a dispositive veto still requires its T1 primary (a corpus T2 card is a lead, per the
  FDA-memory skill doc) — don't let corpus-sourcing weaken that.
- **DoD (Gate 5):** a query whose answer is in the FDA-memory corpus (e.g. an Alzheimer's amyloid / aducanumab
  precedent) is answered **from the corpus via `run_live`** — show ≥1 dossier fact sourced from the corpus
  (traced), with the live path used only for the gap. Generic: any agent with a `corpus/<id>/` dir benefits;
  no per-agent code. Honest-empty when no corpus / no match. Tests offline ($0): seed/point at the FDA-memory
  corpus, assert a corpus-sourced fact lands in `discover["dossier"]` through `run_live`. Report in
  `dev/reports/rohan/k2-corpus-retrieval-report.md`.

---

## Constraints (binding — `dev/CONVENTIONS.md`)
- Engine stays **stdlib-only** (K1/K2 reader/wiring use only stdlib; heavy deps stay in seams/subprocess).
- Provenance honesty; **never fabricate**; degrade honestly. Public-identifiers-only data boundary intact.
- Every commit `Built-By: rohan` + the Claude trailer. One PR per task; full Gates 1–5 locally before the PR.
- Branch from the **latest `main`** each task; if `main` moved, merge it in before pushing.
