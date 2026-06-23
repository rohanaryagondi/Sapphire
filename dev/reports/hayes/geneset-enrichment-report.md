# Report — `geneset-enrichment` seam (PR-D) · completes quant-fact-seams

**Built-By:** hayes · **Branch:** `hayes/geneset-enrichment` · **Task:** `quant-fact-seams` (seam 4 of 4, last) ·
**Tier:** Standard · **Date:** 2026-06-23 · **Template:** the merged gnomAD/GTEx/InterPro seams.

## What this delivers
The fourth and final Bucket-1 fact seam: **g:Profiler functional enrichment** — the top over-represented
GO / pathway terms (with p-values) for the query's **gene set**, via g:Profiler's public g:GOSt REST API.
A cited, provenance-stamped **T2** fact (enrichment is a *computed* statistic, distinct from the measured T1
sources). This is the one seam that operates on a SET, so it also threads the full extracted gene list into
the engine's Bucket-1 inputs.

## Files
| File | Change |
|---|---|
| `sapphire-orchestrator/tools/geneset_enrichment_seam.py` | **new** — stdlib seam (`urllib`+`json`). One POST `_fetch(genes)` to g:GOSt. `_resolve_genes` (engine-threaded `genes` set, else single `candidate`; dedupe/strip). One T2 fact: significant-term count + top-N by p-value (name, native id, p). Honest-empty / honest-error / never-raises. |
| `sapphire-orchestrator/tests/test_geneset_enrichment_seam.py` | **new** — 10 tests over a recorded g:GOSt fixture (parse/sort/significance-filter, dedupe, single-candidate fallback, no-genes, no-significant, empty, transport/TLS error) + a guarded live test. |
| `sapphire-orchestrator/contracts/provenance.py` | +`"gprofiler"` label. |
| `sapphire-orchestrator/harness/agents.json` | +`geneset-enrichment` agent (kind python; inline schema; guardrails incl. `data_boundary`; `timeout_s: 60`). |
| `sapphire-orchestrator/live_engine.py` | import seam; add id to `_BUCKET1_AGENTS`; wire `python_fns`; **thread `ents["genes"]` into `bucket1_inputs` as `genes`** (the gene SET; other agents ignore it). |
| `sapphire-orchestrator/tests/test_live_engine.py` | mock geneset in shared `_build_ctx()` + `TestGenesetEnrichmentWiring` (5 tests incl. the Gate-5-in-test + a set-threading proof). |
| `status/tools.md` | listed g:Profiler as a live source; marked all four seams done. |

## Design notes
- **Gene SET, not a single gene.** `bucket1_inputs` now carries `genes = ents["genes"]` (candidate is `genes[0]`).
  The seam runs enrichment over the whole set; a single-gene query degrades to a one-element set. Verified
  through `run_live` that both genes of a 2-gene query reach g:Profiler (`test_gene_set_threaded_from_query`),
  and live that a 3-gene set yields more terms than a 2-gene set (188 vs 152) — enrichment is computed over the
  SET, not one gene.
- **Data boundary still holds on the new field:** `data_boundary` serialises the *whole* inputs dict, so the
  `genes` list is in scope; a `QS#####` anywhere in inputs blocks dispatch (verified:
  `test_internal_id_in_query_blocks_geneset` → agent abstains, no network call).
- **Tier T2** (computed enrichment statistic) — deliberately distinct from gnomAD/GTEx/InterPro's measured/curated T1.
- **Source label** `g:Profiler g:GOSt (hsapiens)` — pins the organism it queries; the API has no pinnable
  release, so the label is version-agnostic on release (pilot-review refinement #1). No silent field drift —
  the fact surfaces the true significant-term count even though only the top N are named (refinement #2).
- **TLS note (environmental):** g:Profiler's host (`biit.cs.ut.ee`) serves a valid HARICA chain
  (`openssl` Verify=0). Python `urllib` verifies it on standard CA stores (Mac/Linux). On a *fresh* Windows box
  the HARICA root may not be pre-installed until Schannel fetches it on-demand (the first stdlib-urllib call can
  fail SSL until then); the seam degrades honestly (error envelope) in that window. Live verified here after the
  root installed. Not a seam defect — same class as the earlier Windows cross-platform notes.

## Gate evidence (run locally on `hayes/geneset-enrichment`)
- **Gate 1 — full suite GREEN: 342 tests.** `bash dev/run-tests.sh` (tests suite 131; +15 vs the post-InterPro 327).
- **Gate 2 — independent review: Approved.** No Critical/Important code issues; gene-SET + data_boundary
  interaction scrutinised and proven; tests non-vacuous. (Reviewer flagged tools.md as not listing the seams —
  on check it already listed gnomAD/GTEx/InterPro; this PR adds the g:Profiler row, closing the whole-task DoD.)
- **Gate 3 — provenance + secrets/binaries:** no secrets/binaries; `gprofiler` registered; only public gene symbols leave Quiver.
- **Gate 4 — stdlib-only runtime:** seam imports `json` + `urllib` only.
- **Gate 5 — functional verification: Works as claimed** (independent verifier + my own live run). Real
  `run_live` against the live g:Profiler API landed:
  ```
  {"value": "g:Profiler enrichment for TSC1, TSC2 (hsapiens): 152 significant terms; top — TSC1-TSC2 complex (GO:0033596, p=2.6e-06); Inhibition of TSC complex formation by PKB (REAC:R-HSA-165181, p=1.4e-05); ...",
   "source": "g:Profiler g:GOSt (hsapiens)", "tier": "T2", "provenance": "gprofiler"}
  agent: {"id": "geneset-enrichment", "status": "ok"}
  ```
  Adversarial all pass: no-gene → no network; API-down → honest empty + error, no crash; `QS00123` → data_boundary blocks (no network).

## Status / next
- **`quant-fact-seams` is now complete** (gnomAD #6, GTEx #9, InterPro #11 merged; g:Profiler PR-D in review).
- Next queue item is the **experiment-design epic (ED-1)** — currently **BLOCKED**: `MatthewCarey24/design-form-agent`
  returns "Repository not found" (no access from this machine). Raising a HELP request for source access; will
  start ED-1 the moment the repo/code drop is available.
