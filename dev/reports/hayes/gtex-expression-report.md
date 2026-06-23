# Report — `gtex-expression` seam (PR-B)

**Built-By:** hayes · **Branch:** `hayes/gtex-expression` · **Task:** `quant-fact-seams` (seam 2 of 4) ·
**Tier:** Standard · **Date:** 2026-06-23 · **Template:** the merged gnomAD pilot (PR #6).

## What this delivers
The second quantitative-fact Bucket-1 seam: **GTEx tissue expression** (median TPM per tissue) + **CNS
selectivity**, via GTEx's public REST API. EMET says where a gene is reportedly expressed; this seam returns the
measured numbers — the top CNS (brain) region's median TPM and a verifiable selectivity ranking over all tissues
— as a cited, provenance-stamped **T1** fact. Built in the exact gnomAD/aso-tox pattern.

## Files
| File | Change |
|---|---|
| `sapphire-orchestrator/tools/gtex_expression_seam.py` | **new** — stdlib seam (`urllib`+`json`). One `_fetch(path, params)` boundary; **two-call flow**: (1) `/reference/gene` resolves symbol→Ensembl `gencodeId`, (2) `/expression/medianGeneExpression` (dataset `gtex_v8`, pinned). Summarises to one T1 fact: top brain region median TPM + CNS-selectivity rank. Honest-empty / honest-error / never-raises. |
| `sapphire-orchestrator/tests/test_gtex_expression_seam.py` | **new** — 12 tests over recorded fixtures (parse/CNS-enriched, broadly-expressed rank>5, no-brain, two-call gencode flow, no-target, gene-not-found, no-record, transport error) + a guarded live test. |
| `sapphire-orchestrator/contracts/provenance.py` | +`"gtex"` label. |
| `sapphire-orchestrator/harness/agents.json` | +`gtex-expression` agent (kind python; inline `output_schema` candidate/facts/provenance/error, `additionalProperties:false`; guardrails incl. `data_boundary`; `timeout_s: 60` for the two-call flow). |
| `sapphire-orchestrator/live_engine.py` | import seam; add id to `_BUCKET1_AGENTS`; wire `python_fns["gtex-expression"]`. |
| `sapphire-orchestrator/tests/test_live_engine.py` | mock gtex in shared `_build_ctx()` (offline suite stays $0) + `TestGtexExpressionWiring` (4 tests incl. the Gate-5-in-test). |
| `status/tools.md` | listed GTEx as a live quantitative source. |

## Lessons + refinements applied
- **Schema completeness / Gate-5-through-run_live** (the two aso-tox lessons): schema lists `error`; a `gtex`
  fact is proven to land in `discover["dossier"]` via real `run_live` (offline fixture + live).
- **Version the source label** (pilot-review refinement): the request pins `gtex_v8`, and `_SOURCE` is derived
  from the `_DATASET` constant (single source of truth) — label and request can't drift.
- **No silent field drift**: the one-fact summary is derived from *all* fetched tissue medians (the selectivity
  rank is over the full set); documented in the seam.
- **CNS selectivity is a verifiable ranking, not an invented score**: rank of the top brain tissue among all
  tissues by measured median; calibrated language (#1 → "CNS-enriched"; ≤5 → "high CNS expression"; else
  "broadly expressed"). Honors the brief's "don't invent scoring."

## Gate evidence (run locally on `hayes/gtex-expression`)
- **Gate 1 — full suite GREEN: 310 tests.** `bash dev/run-tests.sh`: contracts 23 · harness 68 · emet 18 ·
  memory 14 · selfimprove 20 · moat 68 · tests 99. (+16 vs the post-pilot 294 = this PR's new tests.)
- **Gate 2 — independent review: Approved.** No Critical/Important; tests non-vacuous. Two Minors both
  addressed in-PR: `_SOURCE` now derives from `_DATASET` (DRY); a comment documents the `_resolve_gencode`
  alias-fallback.
- **Gate 3 — provenance + secrets/binaries:** no secrets/binaries; `gtex` registered; only the public gene
  symbol (→ public Ensembl gencodeId) leaves Quiver.
- **Gate 4 — stdlib-only runtime:** seam imports `json` + `urllib` only; engine gains no third-party dep.
- **Gate 5 — functional verification: Works as claimed.** Independent verifier ran `run_live` against the
  **live** GTEx API; the fact landed:
  ```
  {"value": "TSC2 GTEx tissue expression (gtex_v8, median TPM): top brain region Brain Cerebellum 133.2; highest-expressing of 54 tissues (CNS-enriched)",
   "source": "GTEx Portal v2 (gtex_v8 medianGeneExpression)", "tier": "T1", "provenance": "gtex"}
  agent: {"id": "gtex-expression", "status": "ok"}
  ```
  Data-driven cross-check (3 genes): TSC2 → rank #1 (CNS-enriched); ALB → brain rank #8 (broadly expressed);
  INS → brain rank #4 (high CNS expression) — distinct real numbers + ranks ⇒ not hardcoded. Adversarial:
  no-gene → no network call; API-down → honest empty + error, no crash; `QS00123` → `data_boundary` blocks
  (no network); gene-not-found → honest-empty (no error), expression endpoint not called.

## Notes / env
- Built on the canonical `sapphire-capability-map` clone with `PYTHONUTF8=1` (the cross-platform conditions are
  tracked separately as `crossplatform-test-hardening`, per Rohan's HELP.md ruling on PR-A — not this PR).
- Next after this merges: InterPro (PR-C), then g:Profiler (PR-D).
