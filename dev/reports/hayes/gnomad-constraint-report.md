# Report — `gnomad-constraint` seam (PR-A pilot)

**Built-By:** hayes · **Branch:** `hayes/gnomad-constraint` · **Task:** `quant-fact-seams` (pilot) ·
**Tier:** Standard (first of the Feature's several PRs) · **Date:** 2026-06-23

## What this delivers
The first quantitative-fact Bucket-1 seam: **gnomAD gene loss-of-function constraint** (pLI, LOEUF, missense Z)
via gnomAD's public GraphQL API, built in the exact `aso-tox` seam pattern. EMET paraphrases the literature;
this seam returns the *actual measured number* as a cited, provenance-stamped **T1** fact, so the Research
Manager can flag number-vs-narrative DIVERGENCE. This PR ships **only** the gnomAD pilot (the pilot-gate);
GTEx / InterPro / g:Profiler follow as separate PRs once this is merged.

## Files
| File | Change |
|---|---|
| `sapphire-orchestrator/tools/gnomad_constraint_seam.py` | **new** — stdlib seam (`urllib`+`json`). `findings(inputs)->dict`; single `_fetch` network boundary; honest-empty / honest-error / never-raises. |
| `sapphire-orchestrator/tests/test_gnomad_constraint_seam.py` | **new** — 12 unit tests over recorded gnomAD fixtures (parse, partial fields, tolerant-gene, no-target, gene-not-found, no-constraint, transport error, GraphQL-error) + a `SAPPHIRE_LIVE_TESTS`-gated live test. |
| `sapphire-orchestrator/contracts/provenance.py` | +`"gnomad"` provenance label. |
| `sapphire-orchestrator/harness/agents.json` | +`gnomad-constraint` agent (kind `python`; inline `output_schema` listing `candidate/facts/provenance/error`, `additionalProperties:false`; guardrails `facts_only_cited`+`stamp_provenance`+`data_boundary`). |
| `sapphire-orchestrator/live_engine.py` | import seam; add id to `_BUCKET1_AGENTS`; wire `ctx["python_fns"]["gnomad-constraint"] = …findings`. |
| `sapphire-orchestrator/tests/test_live_engine.py` | mock gnomad in shared `_build_ctx()` (keeps the offline suite $0) + new `TestGnomadConstraintWiring` (4 tests, incl. the Gate-5-in-test). |
| `status/tools.md` | listed gnomAD as a live quantitative source. |

## The two aso-tox lessons — both absorbed
1. **Schema completeness.** The harness validates output against `output_schema` with `additionalProperties:false`;
   a stray field → silent reject → abstain → dropped facts. The agent schema lists every field the seam emits
   (`candidate`, `facts`, `provenance`, `error`); the seam emits nothing outside it
   (`test_fact_has_only_schema_allowed_keys`). Proven **through `run_live`**, not just a seam unit test.
2. **Gate 5 ≠ "tests pass".** A `gnomad`-provenance fact is shown landing in `discover["dossier"]` from a real
   `run_live(...)` call — offline in `TestGnomadConstraintWiring` (fixture-patched `_fetch`) and live against the
   real API in the Gate-5 verification below.

## Gate evidence (run locally on `hayes/gnomad-constraint`)
- **Gate 1 — full suite GREEN: 294 tests.** Canonical runner `bash dev/run-tests.sh`:
  `contracts 23 · harness 68 · emet 18 · memory 14 · selfimprove 20 · moat 68 · tests 83 → Gate 1 GREEN — 294 tests.`
  (+16 vs the prior 278 = this PR's new tests; zero new failures — proven by stashing the change and re-running.)
- **Gate 2 — independent review: Approved.** A reviewer subagent (not the implementer) judged spec-compliance +
  quality: no Critical/Important findings; tests confirmed non-vacuous; stdlib runtime / valid provenance /
  public-IDs-only / `data_boundary`-present all verified. One Minor (see Follow-ups).
- **Gate 3 — provenance + secrets/binaries:** no secrets in the diff; no binaries; new files are `.py` text;
  `gnomad` registered in `contracts/provenance.py`; only the public gene symbol leaves Quiver.
- **Gate 4 — stdlib-only runtime:** the seam imports `json` + `urllib` only; `live_engine`'s sole new import is
  the first-party seam. No third-party dep enters the engine path.
- **Gate 5 — functional verification: Works as claimed.** An independent verifier subagent ran `run_live`
  end-to-end against the **live** gnomAD API and observed the fact land:
  ```
  GNOMAD FACTS: [{"value": "TSC2 gnomAD constraint: pLI 1.00, LOEUF 0.20, missense Z -0.08 (loss-of-function intolerant)",
                  "source": "gnomAD v4 constraint (GraphQL)", "tier": "T1", "provenance": "gnomad"}]
  GNOMAD AGENT: {"id": "gnomad-constraint", "status": "ok", "provenance": "gnomad"}
  ```
  Adversarial probes all passed: no-gene → no network call, agent `ok`, 0 facts; API-down (`_fetch` raises) →
  no crash, honest empty + error envelope; `QS00123` in query → `data_boundary` blocks (abstain), `_fetch` not
  called; gene-not-found → honest-empty with **no** error key. A counterfactual payload with different numbers
  produced a dossier value tracking those numbers (and correctly withheld the "intolerant" call) — the parse and
  threshold are live, not hardcoded.

## Honest degradation (CONVENTIONS §3)
- No target gene → `facts: []` (the seam makes no network call).
- Gene not found (`data.gene == null`) → `facts: []`, **no** error — a known-unknown, not a failure, not a faked number.
- Gene present but no constraint record → `facts: []`.
- API unreachable / GraphQL error with no data → `facts: []` + honest `error` envelope; never raises into the engine.

## Follow-ups / notes (non-blocking)
- **`_SOURCE` label "gnomAD v4 constraint (GraphQL)"** (reviewer Minor): currently accurate (the API default is
  v4; TSC2 LOEUF 0.20 is the v4 value) and matches the brief's worked example, but the query does not pin a
  dataset version, so the label could drift if gnomAD's default advances. Left as-is for the pilot; a future
  hardening could pin the dataset or soften the label. Flagged for the approver.
- **Environment (Windows contributor machine):** the clone was placed at the canonical
  `…/sapphire-capability-map` name (CONVENTIONS §1) — required, because `moat/tests/test_client.py` asserts that
  default-db-path suffix. The full suite was run with `PYTHONUTF8=1` (the Mac/Linux default this UTF-8 codebase
  assumes; without it, two unrelated suites — `test_scenarios`, `test_trace_view` — error on cp1252 stdout/file
  I/O). Both are pre-existing cross-platform conditions, independent of this change (the 4 aso-tox + 1 moat-DB
  skips in `tests` are likewise pre-existing: `joblib`/`sklearn` and the unbuilt moat SQLite aren't present in
  this env). Raised in `dev/HELP.md` for awareness.
