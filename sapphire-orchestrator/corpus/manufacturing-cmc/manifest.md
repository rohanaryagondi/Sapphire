# Manifest — manufacturing-cmc corpus

**Agent:** `manufacturing-cmc` (Bucket-1 semantic; dossier field **E5** — manufacturing/CMC feasibility). **Built-By:** rohan.
**Retrieval date:** 2026-06-29. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (FDA enforcement records, primary → T1):** FDA warning letters fetched directly from `fda.gov` (returns HTTP 200 to curl; content verified verbatim). FDA Drug Master Files page (`fda.gov`). FDA Inspections Dashboard (`datadashboard.fda.gov`, 403 to automation — tagged `unverifiable_by_fetch: true`).
  - **Tiering:** All cards cite `*.fda.gov` or `datadashboard.fda.gov` (US government primary) → **T1** under `validate-corpus.sh` allowlist.
  - **FDA warning letter fetch note:** Individual FDA warning letter HTML pages (e.g. `fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/...`) return HTTP 200 to `curl -L` and their content was verified by direct curl extraction. The WebFetch tool (browser-based) returned 404, but the shell validate-corpus.sh script uses curl and those pages return 200 — so they pass the URL liveness check without `unverifiable_by_fetch`.
- **Pass B (EMET biomedical grounding):** NOT RUN for Phase 0 — manufacturing-cmc is not a mechanism agent; the enforcement and regulatory precedents are the core value.

## Coverage map (against the agent's check types from `architecture/bucket1/semantic/manufacturing-cmc.md`)
| Check type | Covered? | Cards |
|---|---|---|
| FDA Warning Letters (CGMP violations, sterility) | ✅ | Cards 1, 2, 3 |
| FDA Drug Master File (DMF) — CMO engagement signal | ✅ | Card 4 |
| FDA inspection classification / dashboard | ✅ | Card 5 |
| ASO oligonucleotide-specific CMO warning letters | ❌ | Gap — no public enforcement actions found for ASO CMOs (see known-gaps) |
| Gene therapy (AAV) facility warning letters | ❌ | Gap — no specific 2022-2024 warning letters found for AAV/viral vector facilities |
| FDA Form 483 specific observations (published) | ❌ | Gap — most 483s require FOIA; not pre-ingested |
| DEA-licensed manufacturer constraint (controlled substances) | ❌ | Gap — deferred to DEA scheduling agent |

**Card count:** 5 (all **T1** FDA primary). Theme: sterile aseptic manufacturing CGMP enforcement (the dominant FDA enforcement pattern for injectable/biologic CMOs) + DMF program overview.

## Tiering note
All 5 cards cite `*.fda.gov` or `datadashboard.fda.gov` (US `.gov` primary), so they are **T1** under `validate-corpus.sh`'s allowlist. Card 5 is tagged `unverifiable_by_fetch: true` because `datadashboard.fda.gov` returns HTTP 403 to automated curl.

## Known gaps (the ~30% to search live)
1. **Oligonucleotide-specific CMO warning letters** — no public FDA enforcement actions against ASO/oligonucleotide API or fill-finish CMOs (Avecia, PCI Synthesis, TriLink) were found in web-accessible search (2019–2024). This is a genuine gap; the live web call is the right gap-filler for modality-specific records.
2. **Gene therapy (AAV) facility warning letters** — no 2022–2024 FDA warning letters to AAV/viral vector CMOs (e.g. Catalent Indiana, Charles River) found in accessible web search. Live search gap.
3. **FDA Form 483 published observations** — the OII FOIA Reading Room posts a subset of 483s; none were pre-ingested. Live gap-filler for program-specific facility checks.
4. **Establishment Inspection Reports (EIRs)** — most EIRs require FOIA requests; not available for pre-ingestion. Live gap.
5. **DEA-licensed manufacturer capacity** — the constraint that controlled substance manufacturing requires a DEA-licensed facility is deferred to the DEA scheduling agent; not modeled here.
