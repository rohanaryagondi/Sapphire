# Report — `interpro-domains` seam (PR-C)

**Built-By:** hayes · **Branch:** `hayes/interpro-domains` · **Task:** `quant-fact-seams` (seam 3 of 4) ·
**Tier:** Standard · **Date:** 2026-06-23 · **Template:** the merged gnomAD (#6) + GTEx (#9) seams.

## What this delivers
The third Bucket-1 fact seam: **InterPro protein domain/family annotations** (with IPR accessions), via UniProt
(symbol→accession) + InterPro's public REST API. EMET paraphrases what's written about a protein's structure;
this seam returns the curated InterPro annotation as a cited **T1** fact. Built in the exact gnomAD/GTEx pattern.

## Files
| File | Change |
|---|---|
| `sapphire-orchestrator/tools/interpro_domains_seam.py` | **new** — stdlib seam (`urllib`+`json`). One `_fetch(url)` boundary; **two-call flow across two hosts**: (1) UniProt `rest.uniprot.org` resolves symbol→reviewed-human accession, (2) InterPro `www.ebi.ac.uk/interpro/api` lists entries. Summarises to one T1 fact: domain + family annotations (IPR accessions) + total entry count. Honest-empty / honest-error / never-raises; InterPro 404 → honest-empty (not error). |
| `sapphire-orchestrator/tests/test_interpro_domains_seam.py` | **new** — 13 tests over recorded fixtures (parse, overflow cap, superfamily-only, two-call accession flow, no-target, no-protein, no-entries, 404-honest-empty, other-HTTP-envelope, transport error) + a guarded live test. |
| `sapphire-orchestrator/contracts/provenance.py` | +`"interpro"` label. |
| `sapphire-orchestrator/harness/agents.json` | +`interpro-domains` agent (kind python; inline `output_schema` candidate/facts/provenance/error, `additionalProperties:false`; guardrails incl. `data_boundary`; `timeout_s: 60` for the two-call flow). |
| `sapphire-orchestrator/live_engine.py` | import seam; add id to `_BUCKET1_AGENTS`; wire `python_fns["interpro-domains"]`. |
| `sapphire-orchestrator/tests/test_live_engine.py` | mock interpro in shared `_build_ctx()` (offline suite stays $0) + `TestInterproDomainsWiring` (4 tests incl. the Gate-5-in-test). |
| `status/tools.md` | listed InterPro as a live structured source. |

## Lessons + refinements applied
- **Schema completeness / Gate-5-through-run_live**: schema lists `error`; an `interpro` fact is proven to land
  in `discover["dossier"]` via real `run_live` (offline fixture + live).
- **Version the source label**: InterPro's release is NOT pinnable on this endpoint, so the label is
  deliberately version-agnostic (`"InterPro (EBI)"`) — the brief's "be deliberate" path for the unpinnable case
  (contrasts with GTEx, which pins `gtex_v8` and names it).
- **No silent field drift**: the fact reports the API's true total entry `count`; the shown names are a capped
  per-type sample, and a dedicated superfamily-only branch avoids a misleading empty fact when entries exist but
  none are domain/family.
- **Honest 404 handling**: InterPro 404 (no entries for the protein) → honest-empty; other HTTP / network →
  error envelope.

## Gate evidence (run locally on `hayes/interpro-domains`)
- **Gate 1 — full suite GREEN: 327 tests.** `bash dev/run-tests.sh`: contracts 23 · harness 68 · emet 18 ·
  memory 14 · selfimprove 20 · moat 68 · tests 116. (+17 vs the post-GTEx 310 = this PR's new tests.)
- **Gate 2 — independent review: Approved.** No Critical/Important; tests non-vacuous. Two cosmetic Minors
  (superfamily-only trailing-empty edge — guarded; "first page" wording) — non-blocking, noted.
- **Gate 3 — provenance + secrets/binaries:** no secrets/binaries; `interpro` registered; only the public gene
  symbol → public UniProt accession leaves Quiver.
- **Gate 4 — stdlib-only runtime:** seam imports `json` + `urllib` only; engine gains no third-party dep.
- **Gate 5 — functional verification: Works as claimed** (independent verifier + my own live run). Real
  `run_live` against the live UniProt+InterPro APIs landed:
  ```
  {"value": "TSC2 (UniProt P49815) InterPro: 8 entries — domains: Rap/Ran-GAP domain (IPR000331), Tuberin-type domain (IPR018515), Tuberin, N-terminal (IPR024584); families: Tuberin (IPR003913), Tuberin/Ral GTPase-activating protein subunit alpha (IPR027107)",
   "source": "InterPro (EBI)", "tier": "T1", "provenance": "interpro"}
  agent: {"id": "interpro-domains", "status": "ok"}
  ```
  Adversarial probes all pass: no-gene → no network call; API-down → honest empty + error, no crash; `QS00123`
  (with a real gene also present) → `data_boundary` blocks (no network); no-reviewed-protein and InterPro-404 →
  honest-empty (no error). Live parse is real (the env-gated live test runs in ~0.9s vs ~0.002s mocked).

## Notes / env
- Built on the canonical `sapphire-capability-map` clone with `PYTHONUTF8=1` (cross-platform hardening is the
  separate `crossplatform-test-hardening` backlog item).
- Verifier's optional (non-blocking) suggestion: wire a periodic `SAPPHIRE_LIVE_TESTS=1` lane so real-parse
  drift is caught automatically — out of scope for this PR; noted for the dev-harness owner.
- Last of the seams after this: g:Profiler (PR-D), then the experiment-design epic.
