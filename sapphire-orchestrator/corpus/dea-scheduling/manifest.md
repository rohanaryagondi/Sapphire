# Manifest — dea-scheduling corpus

**Agent:** `dea-scheduling` (Bucket-1 semantic; dossier field **D4** controlled-substance status). **Built-By:** hayes.
**Retrieval date:** 2026-06-25. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (regulatory record, primary → T1):** **GPO `govinfo.gov` HTML** — DEA Federal Register final rules/orders + codified 21 CFR Part 1308. **9 cards, each fetched and re-verified individually** (schedule + action + date confirmed against the document; quote = a verbatim substring of the fetched page). WebSearch was used only to locate the exact FR citation/URL, then discarded in favor of the fetched primary.
  - **Why govinfo, not federalregister.gov:** `federalregister.gov` and `ecfr.gov` 302-redirect every automated fetch to an `unblock.federalregister.gov` bot-wall; `deadiversion.usdoj.gov`/`dea.gov` PDFs return 403/binary. GPO `govinfo.gov` HTML (`/content/pkg/.../html/...htm`) is the reliably-fetchable `.gov` primary and is the canonical fetch target for this corpus.
- **Pass B (EMET / literature grounding):** **NOT YET RUN** — see known-gaps. For this regulatory agent EMET is a *literature* layer (METHOD §3 Pass B), not the core, so Pass A stands on its own.

## Coverage map (against the agent's check types)
| Check type (from `architecture/bucket1/semantic/dea-scheduling.md`) | Covered? | Cards |
|---|---|---|
| Current status — is the compound/analog scheduled, which schedule | ✅ | all 9 |
| DEA primary action + citation (scheduling order / final rule / CFR) | ✅ | all 9 (Federal Register or codified CFR) |
| Rescheduling history / pending action | ✅ (partial) | MDMA (1988 reaffirmation + 2024 CRL context), Epidiolex (Farm-Bill), marijuana (2026), dronabinol (2010/2017 formulations) |
| Program impact (trial DEA-registration / quota / REMS / mfg-license) | ✅ | per-card `program_impact` |
| Schedule-pattern coverage | ✅ | Schedule I (psilocybin, LSD, MDMA) · III (ketamine, esketamine, GHB-product, dronabinol, marijuana-product) · V (Epidiolex) |

**Card count:** 9 (all Pass A, all **T1** `govinfo.gov`). Theme: the recurring CNS scheduling patterns (`notes/cns-controlled-substance-scheduling.md`) — Schedule I psychedelics, the FDA-approval→scheduling pathway, the split schedule, isomer-reference.

## Tiering note
All 9 cards cite `govinfo.gov` (a US `.gov` primary), so they are **T1** under `validate-corpus.sh`'s allowlist — no HELP needed (contrast patent-ip, whose patent-domain cards are T2 pending the allowlist).

## Known gaps (the ~30% to search live)
1. **EMET Pass B not run** — the Claude-in-Chrome extension lacks host access to `emet.benchsci.com` (logged in but DOM reads permission-blocked). The literature behind abuse-potential / mechanism findings (e.g. 5-HT2A for psychedelics) is pending that grant — to add as `provenance:"emet-live"` PMID cards.
2. **Pre-govinfo original FR citations** — the 1971 original Schedule I placements (LSD/psilocybin) and the 1988 MDMA FR text predate govinfo full-text; **current status verified instead via codified 21 CFR 1308.11(d)** (1996 edition HTML — the listings are unchanged since the 1980s; a current-edition verbatim re-confirm is a minor open item).
3. **Esketamine-specific FR** — none exists; controlled by isomer-reference under the 1999 ketamine rule (cited). Honest.
4. **Epidiolex current status** — the 2018 Schedule V order is verified, but FDA-approved CBD <0.1% THC was effectively descheduled after the 2018 Farm Bill; flagged on the card rather than asserting current Schedule V.
5. **MDMA 2024 CRL** — corroborated by FDA + widespread reporting but not fetched as a primary; recorded as *context* on the card, not as the cited/quoted fact.
6. **In-flight rescheduling petitions / analog-act ambiguity** — live `known unknowns`.

Coverage is deep-and-honest over the stable scheduling record; gaps stated plainly.
