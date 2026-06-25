# Manifest — clinical-trial-registry corpus

**Agent:** `clinical-trial-registry` (Bucket-1 semantic; dossier field **D1** — trial precedent + status as signals). **Built-By:** hayes.
**Retrieval date:** 2026-06-25. **Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`.

## Sources
- **Pass A (registry record, primary → T1):** the **ClinicalTrials.gov v2 REST API** (`https://clinicaltrials.gov/api/v2/studies`) — the source the agent spec names. **12 cards**, every NCT fetched + confirmed real via the API; 4 load-bearing records (aducanumab ENGAGE, nusinersen ENDEAR, WVE-120101, BIIB105) were **independently re-verified** field-for-field (status + verbatim `whyStopped` + phase + sponsor). The CT.gov API is reachable here and returns clean structured JSON, so quotes are exact registry fields (incl. preserved registry typos, a fidelity signal).
- **Pass B (EMET / published-literature behind the trials):** **not yet run, now ADDRESSABLE** — the BenchSci/EMET extension host-permission was just granted (verified: the EMET chat UI now reads). This agent is **EMET-central** (the mechanism/efficacy literature behind these programs is high-value), so a dedicated EMET pass is the priority follow-up (see gaps).

## Coverage map (against the agent's check types)
| Check type (from `architecture/bucket1/semantic/clinical-trial-registry.md`) | Covered? | Cards |
|---|---|---|
| Trial record — id · phase · status · sponsor · condition | ✅ | all 12 |
| **Termination records — stated reason + timing** (the agent's special value) | ✅ strong | 10 termination/withdrawal cards w/ verbatim `whyStopped` + date |
| Trial precedent for key CNS indications/modalities | ✅ | AD anti-amyloid, ALS (incl. ATXN2 ASO), HD (HTT ASOs), SMA, Dravet/SCN1A, MECP2 |
| Protocol-amendment events (what/when) | ⚠️ gap | not mined this pass (version-history endpoint) |
| Posted results + adverse-event tables | ⚠️ gap | not extracted this pass |
| DSMB/interim timing (inference, T3) | ⚠️ gap | not inferred (would be T3-flagged) |

**Card count:** 12 (all Pass A, all **T1** `clinicaltrials.gov`). Theme: CNS trial **signals** — termination reasons read as intelligence (`notes/cns-trial-signals.md`).

## Tiering note
All 12 cards cite `clinicaltrials.gov` (a US `.gov` registry), so they are **T1** under the gate's allowlist — no HELP needed (like dea-scheduling; unlike patent-ip).

## Known gaps (the ~30% to search live)
1. **EMET Pass B (now addressable)** — the published-literature/mechanism evidence behind these programs (e.g. ATXN2-lowering rationale in ALS, HTT-lowering target engagement vs. clinical outcome in HD, the amyloid hypothesis). EMET access is now live; this is the **priority follow-up** (and high-value, since this agent is EMET-central).
2. **Amendment / AE-table / DSMB-timing signal types** — only the trial-record + termination layer was mined; the protocol-version-history and results/AE endpoints (and update-pattern DSMB inference, T3) are a deeper Pass-A extension.
3. **tominersen dosing halt not in structured data** — GENERATION HD1 is registry-COMPLETED; the March-2021 halt must be sourced from a release/publication, not this API (flagged on the card).
4. **Notable precedents not surfaced this pass** — tofersen/VALOR (SOD1 ASO), Angelman UBE3A ASO programs, C9orf72 ALS — good targets for a follow-up query batch.
5. **Ex-US registries** (WHO ICTRP, EUCTR, ISRCTN, ANZCTR, etc., per the spec) not queried — CT.gov-only this pass.

Coverage is deliberately deep on the **termination-signal** layer (the agent's distinctive value) over broad-but-shallow; gaps stated plainly.
