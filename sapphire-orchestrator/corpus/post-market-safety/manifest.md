# Manifest — post-market-safety corpus

**Agent:** `post-market-safety` (Bucket-1 semantic; dossier fields **C1** class/target safety liabilities + **C2** prior clinical safety signals). **Built-By:** hayes.
**Retrieval date:** 2026-06-25. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (FDA label + FAERS, primary → T1):** the **openFDA API** (`api.fda.gov`) — the agent spec's named primary. **8 cards**, each from a fetched `drug/label.json` record (boxed warning / Warnings & Cautions) + `drug/event.json` FAERS reaction counts. **Quotes byte-verified against the raw JSON `boxed_warning` field** (fetched directly via PowerShell `Invoke-RestMethod`, not via a summarizer). `api.fda.gov` is reachable here and returns clean JSON — **distinct from `www.fda.gov` HTML, which is 403-blocked in this environment**.
- **Pass B (EMET / mechanism literature):** **NOT run** — the Claude-in-Chrome extension's host-permission for `emet.benchsci.com` is **intermittent** (a `get_page_text` read succeeded once, then both reads and the `computer` tool failed with the host-permission error on subsequent tabs). EMET-*driving* is not reliably available, so the mechanism layer is a pending gap (this agent is EMET-central — high-value follow-up once EMET driving is stable).

## Coverage map (against the agent's check types)
| Check type (from `architecture/bucket1/semantic/post-market-safety.md`) | Covered? | Cards |
|---|---|---|
| Comparator set — approved drugs sharing mechanism/target/class | ✅ | 8 (anti-amyloid mAb, NMDA-ant, AAV GT, 5-HT2, GABA-T, SSRI, CBD, ASO) |
| Real-world AE record — boxed warning / REMS | ✅ | all 8 (verbatim boxed warning or W&C; REMS noted: Spravato, Fintepla, Sabril) |
| FAERS disproportionality | ✅ (raw counts) | top reaction terms per drug (T2, caveated) |
| Trial → real-world gap (C2) | ✅ | per-card `trial_vs_realworld` — incl. the **FAERS-under-captures-insidious-harms** finding |
| Ex-US pharmacovigilance (EMA, WHO VigiAccess) | ⚠️ gap | not queried this pass |

**Card count:** 8 (all Pass A, all **T1** `api.fda.gov` label; FAERS = T2 supporting data, caveated in-card). Theme: CNS class-safety liabilities by modality (`notes/cns-class-safety-liabilities.md`).

## Tiering note
All 8 cards cite `api.fda.gov` (a US `.gov` API) and their `quote` is the **verbatim FDA boxed warning / W&C** (label = **T1** per the spec). FAERS counts are included as a **supporting data field** with an explicit spontaneous-reporting caveat (the spec tiers FAERS **T2**); they are not the cited/quoted fact. So the cards are correctly **T1** under the gate's allowlist — no HELP needed.

## Known gaps (the ~30% to search live)
1. **EMET Pass B (mechanism literature)** — the biomedical "why" behind each class liability (e.g. ApoE4 + vascular amyloid → ARIA; 5-HT2B agonism → valvulopathy; AAV capsid dose → hepatotoxicity/TMA). Blocked by the **intermittent EMET host-permission** (see Sources) — the priority follow-up once EMET driving is stable.
2. **Ex-US pharmacovigilance** — EMA PSURs / DHPCs, WHO VigiAccess, Health Canada MedEffect, TGA DAEN (per the spec) not queried; openFDA-only this pass.
3. **Computed FAERS disproportionality (PRR/ROR)** — only raw reaction counts captured, not a computed disproportionality statistic with a comparator background.
4. **PMR/PMC (FDA post-market study commitments)** — the unresolved-safety-question layer; the PMR/PMC database wasn't queried (and `www.fda.gov` is 403-blocked).
5. **SPL is manufacturer-specific** — openFDA returns one labeler's Structured Product Label per query (e.g. vigabatrin resolved to the VIGADRONE generic, fluoxetine to a generic fluoxetine); the boxed-warning *content* is class/molecule-consistent but the proper-name token in the quote is manufacturer-specific (flagged where relevant).

Coverage is deep on the FDA label + FAERS layer (the agent's C1/C2 core); the mechanism (EMET) + ex-US PV layers are stated gaps.
