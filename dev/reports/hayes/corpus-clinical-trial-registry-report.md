# Report — clinical-trial-registry corpus (semantic-corpora, 3rd of 6)

**Built-By:** hayes · **Branch:** `hayes/corpus-clinical-trial-registry` · **Task:** `semantic-corpora` → clinical-trial-registry ·
**Date:** 2026-06-25 · **Method:** `corpus/fda-institutional-memory/METHOD.md`.

## What this delivers
The **clinical-trial-registry** Bucket-1 corpus (dossier field **D1** — trial precedent + status read as *signals*), **Pass A complete**. It reads ClinicalTrials.gov as an analyst: termination reasons, early stops, and status changes are timestamped intelligence about what happened to a program.

- `index.jsonl` — **12 verified cards, all T1** (`clinicaltrials.gov`), from the **CT.gov v2 REST API** (the source the spec names): 10 termination/withdrawal signals + 2 trial-precedents, across AD anti-amyloid (aducanumab ENGAGE, crenezumab CREAD), ALS (dexpramipexole, Triumeq, the **BIIB105 ATXN2 ASO**), HD HTT-lowering ASOs (WVE-120101, tominersen), SMA (nusinersen ENDEAR), Dravet/SCN1A, MECP2.
- `notes/cns-trial-signals.md` (the signal patterns + the key lessons) · `manifest.md` (coverage + gaps) · `QUERIES.md` (6 D1 checks).

## The analyst value captured
- **Termination reasons verbatim** — e.g. aducanumab "discontinued based on futility analysis … not based on safety concerns"; WVE-120101 "Lack of Efficacy"; BIIB105 "Sponsor's decision".
- **The read-`whyStopped`-not-`status` lesson** — nusinersen **ENDEAR** is "TERMINATED" but for a **positive interim** (→ open-label); a status-only read would invert the signal. Same for the MECP2 / SCN1A "objectives met" early stops.
- **A registry-vs-reality caveat** — tominersen GENERATION HD1 is registry-COMPLETED with no `whyStopped`, though Roche halted dosing March 2021 (flagged on the card).

## Anti-fabrication
Every NCT confirmed real via the API; **4 load-bearing records re-verified field-for-field by me** (aducanumab/ENGAGE, nusinersen/ENDEAR, WVE-120101, BIIB105 — status + verbatim `whyStopped` + phase + sponsor all matched). Quotes are exact registry fields, including **preserved registry typos** (e.g. CoQ10 "failed to showed likelihoo") — a fidelity tell that the field is raw, not paraphrased.

## Gate evidence
- [x] **`validate-corpus.sh` checks: CLEAN** — 12 cards; invariant fields present; max quote 26 words; **all T1 on `clinicaltrials.gov` (`.gov`) → no tier-HELP** (like dea-scheduling); all 12 study URLs HTTP 200. Run directly (the canonical script's `/tmp` Windows bug is the open HELP).
- [x] **Gate 1 — full suite GREEN** (`dev/run-tests.sh`; the new corpus dir doesn't perturb any suite).

## Pass B (EMET) — now addressable (priority follow-up)
This agent is **EMET-central**, and the EMET host-permission was **just granted** (verified: the EMET chat UI now reads). The published-literature/mechanism layer behind these programs (ATXN2-lowering rationale, HTT target-engagement-vs-outcome, the amyloid hypothesis) is the **priority EMET follow-up** — to add as `provenance:"emet-live"` PMID cards. Pass A stands as a strong standalone termination-signal corpus meanwhile.

## Notes
- **3rd of 6**, after patent-ip (#76 merged) + dea-scheduling (#83). All-T1, clean `.gov` sourcing.
- The **CT.gov v2 API is the reliable fetch path** (`fda.gov`/`cms.gov` are 403-blocked in this env; `govinfo.gov` + `clinicaltrials.gov` work).
- Deeper Pass-A signal types (amendments, AE tables, DSMB timing) + ex-US registries are noted gaps.
