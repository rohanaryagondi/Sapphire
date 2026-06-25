# Manifest — patent-ip corpus

**Agent:** `patent-ip` (Bucket-1 semantic, veto-class; dossier field **E1** freedom-to-operate). **Built-By:** hayes.
**Retrieval date:** 2026-06-25. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (legal record, primary):** Google Patents (USPTO granted-patent + WIPO PCT records) — 7 patents, each fetched and verified individually (title/assignee/dates/legal-status confirmed; quote = a verbatim abstract or independent-claim substring read from the patent page). WebSearch / secondary aggregators (drugpatentwatch, patsnap) were used **only** to surface candidate numbers, then discarded in favor of the fetched primary (e.g. a search claim that "US9416143" was a nusinersen patent was refuted by fetching it — it is an unrelated Pierre Fabre griseofulvin patent — and dropped).
- **Pass B (EMET / biomedical class-grounding):** **NOT YET RUN** — see known-gaps.

## Coverage map (against the agent's check types)
| Check type (from `architecture/bucket1/semantic/patent-ip.md`) | Covered? | Cards |
|---|---|---|
| Define the claim surface (composition / method-of-use / modality-specific) | ✅ | all 7 (claim_type field) |
| Per-patent capture (assignee · number · legal status · est. expiry · priority · claim read-on) | ✅ | all 7 |
| Classify `landscape` vs ⛔`veto` | ✅ | 4 veto-candidate (US8361977, US9969754, US8980853, US9550988, US10821154) · 3 landscape (US7906111, WO2019094253) |
| Expiry / legal-status timeline | ✅ | est_expiry across cards (2026→2035 cliff in the note) |
| Modality coverage (ASO · small molecule · AAV gene therapy · platform chemistry) | ✅ | ASO (US8361977/US8980853), SM (US9969754), AAV (US10821154/US7906111/WO2019094253), platform (US9550988) |
| Exclusivity (Orange Book / Purple Book) | ❌ gap | — (see below) |

**Card count:** 7 (all Pass A). Theme: SMA franchise as the cross-modality CNS-FTO exemplar (`notes/sma-franchise-and-modality-fto.md`).

## Tiering note (important)
All 7 cards cite `patents.google.com` and are tiered **T2**. Per the patent-ip spec granted patents are **T1-eligible (primary)**, but `validate-corpus.sh`'s T1 allowlist is `.gov/.edu/PMC/NCBI` (+ ex-US regulators) and does **not** include patent domains (`patents.google.com` / `uspto.gov`). HELP raised — **`patent-ip-t1-patent-domains`** (`dev/HELP.md`) — to add patent-primary domains to the T1 allowlist; on resolution, re-tier the granted-patent cards (not the WO PCT) to **T1**. This mirrors the ex-US-regulator allowlist fix (PR #31). The gate passes cleanly at T2 today.

## Known gaps (the ~30% to search live)
1. **EMET Pass B not run** — the Claude-in-Chrome extension lacks host permission for `emet.benchsci.com` this session (`get_page_text`/`find` → "Extension manifest must request permission to access the respective host"); the EMET session is logged in but unreadable. The biomedical class-grounding layer (SMN2-splicing biology, AAV9 CNS tropism) is pending that permission grant — to be added as `provenance:"emet-live"` T2 cards. For this legal-record agent EMET is a supporting layer (METHOD §3 Pass B), so Pass A stands on its own meanwhile.
2. **Orange Book / Purple Book exclusivity** — regulatory-exclusivity dates for the marketed comparators (Spinraza, Evrysdi, Zolgensma) not fetched (fda.gov Orange Book is a JS/form app; would be **T1** from fda.gov). Live-search gap.
3. **AveXis/Novartis granted-US Zolgensma composition patent** — not pinned this pass; the verified AveXis IP (WO2019094253A1) is a ceased PCT and the live AAV9-SMA blocker found is third-party (Genzyme US10821154). Recommend a follow-up on the Nationwide Children's (Kaspar/Foust) scAAV9-SMN US grants + the WO2020113034 intrathecal-AAV9-SMN1 family.
4. **Other CNS targets / indications** — this corpus is SMA-franchise-anchored (chosen because it spans all three modalities). FTO for other targets is a live-search gap.
5. **PTAB / Paragraph-IV / litigation records** — beyond noting the Roche v. Natco risdiplam contest, IPR/ANDA/PACER dockets are not ingested (live `known unknowns`).

Coverage is deliberately **deep-and-honest over the SMA franchise + platform IP** rather than broad-and-thin; gaps above are stated plainly.
