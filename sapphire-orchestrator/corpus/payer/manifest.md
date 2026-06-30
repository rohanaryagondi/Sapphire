# Manifest — payer corpus

**Agent:** `payer` (Bucket-1 semantic; dossier field **E4** — payer / reimbursement precedent). **Built-By:** rohan.
**Retrieval date:** 2026-06-29. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (primary records):** ICER evidence report press releases (`icer.org`), CMS press releases and statements (`cms.gov`). All URLs verified 200 via curl. Verbatim quotes extracted directly from the fetched primary pages.
  - **Tiering (enforced):** CMS `*.gov` records → **T1** (primary US government payer authority). ICER evidence reports → **T2** (HTA/reimbursement body, not a national drug regulator). NICE/PBAC/G-BA → **T2** by same rule.
- **Pass B (EMET biomedical grounding):** NOT RUN for Phase 0 — payer is not primarily a mechanism agent; the stable coverage/pricing precedents are the core value. EMET pass is a Phase 1+ enhancement.

## Coverage map (against the agent's check types from `architecture/bucket1/semantic/payer-market-access.md`)
| Check type | Covered? | Cards |
|---|---|---|
| Cost-effectiveness precedent for CNS drug class (ICER HBPB range) | ✅ | Cards 1, 2, 5 |
| CMS NCD/LCD coverage determination for CNS indication | ✅ | Cards 3, 4 |
| HTA committee vote on net health benefit | ✅ | Card 1 (lecanemab 12-3), Card 2 (SMA) |
| Coverage-with-evidence-development (CED) pathway | ✅ | Cards 3, 4 |
| Price-at-listing vs. value-based benchmark | ✅ | Cards 1, 2 |
| Ex-US payer assessment (NICE, G-BA, PBAC) | ❌ | Gap — see known-gaps |
| PBM formulary exclusion | ❌ | Gap — see known-gaps |
| REMS-driven distribution constraints | ❌ | Gap — see known-gaps |

**Card count:** 5 (3 T2 ICER/HTA + 2 T1 CMS). Theme: anti-amyloid antibody coverage precedent (lecanemab) + gene/RNA therapy pricing (SMA) + CNS addiction formulary (OUD).

## Tiering note
ICER reports are T2 (HTA/reimbursement body; the `validate-corpus.sh` allowlist correctly excludes ICER from T1). CMS `cms.gov` records are T1 (US primary federal payer authority — qualifies under `*.gov` suffix).

## Architectural note
Now that all 13 semantic agents have a corpus (Phase 0 complete), the Opt-2 batch path (`_batch_bucket1` in `live_engine.py`) has no production agents to batch — it correctly skips all corpus-grounded agents. This is a finding for the perf/parallelization WO, not for Phase 0 to resolve; the batch mechanism remains exercised via the test monkeypatch.

## Known gaps (the ~30% to search live)
1. **NICE TA on lecanemab** — the appraisal is still in progress (appeal upheld March 2026; final committee meeting July 2026); cannot yet pre-ingest a final TA. Live agent call required.
2. **G-BA early benefit assessment (AMNOG)** — no CNS anti-amyloid decision yet; live search gap.
3. **PBAC (Australia)** — no lecanemab PBAC decision found; live search gap.
4. **PBM formulary exclusion data** — Express Scripts / CVS Caremark formulary exclusion lists are not publicly indexed; live search gap.
5. **IRA drug negotiation list** — Medicare Drug Price Negotiation Program (IRA) affects small-molecule CNS drugs; not yet pre-ingested; live search gap.
6. **REMS-driven distribution constraints** — REMS data for anti-CGRP, ketamine, and other CNS products; live search gap.
