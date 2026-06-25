# Report — post-market-safety corpus (semantic-corpora, 4th of 6)

**Built-By:** hayes · **Branch:** `hayes/corpus-post-market-safety` · **Task:** `semantic-corpora` → post-market-safety ·
**Date:** 2026-06-25 · **Method:** `corpus/fda-institutional-memory/METHOD.md`.

## What this delivers
The **post-market-safety** Bucket-1 corpus (fields **C1** class/target safety liabilities + **C2** prior clinical safety signals), **Pass A complete**. It reads the real-world AE record of approved CNS drugs sharing a candidate's mechanism/modality — the trial-vs-real-world gap as a predictor.

- `index.jsonl` — **8 verified cards, all T1** (`api.fda.gov`): the FDA boxed warning / Warnings-&-Cautions (**verbatim, byte-verified against raw JSON**) + FAERS disproportionality counts (T2 supporting, caveated). Class liabilities by modality: anti-amyloid mAb → **ARIA** (lecanemab); AAV gene therapy → **hepatotoxicity/acute liver failure** (Zolgensma); intrathecal ASO → **thrombocytopenia/renal** (nusinersen); 5-HT2 → **valvulopathy/PAH** (fenfluramine, REMS); GABA-T → **permanent vision loss** (vigabatrin, REMS); SSRI → **suicidality** (fluoxetine); CBD → **hepatotoxicity** (Epidiolex); NMDA-ant → **sedation/dissociation/abuse** (esketamine, REMS).
- `notes/cns-class-safety-liabilities.md` (liabilities by modality + the key C2 lesson) · `manifest.md` · `QUERIES.md` (6 C1/C2 checks).

## Sourcing finding (reusable)
The spec's named primary is the **openFDA API** (`api.fda.gov`) — a JSON REST API that **is reachable here**, unlike `www.fda.gov` HTML (403-blocked). So FDA label/boxed-warning (T1) + FAERS (T2) data is fully accessible via the API even though the HTML site is blocked. **`api.fda.gov`, `clinicaltrials.gov` (v2 API), and `govinfo.gov` (HTML) are the reliable `.gov` fetch paths; `www.fda.gov` + `cms.gov` are 403.**

## Anti-fabrication
A research subagent pulled the openFDA data, then **I byte-verified every boxed-warning quote against the raw JSON** (`Invoke-RestMethod` directly on `api.fda.gov`, no summarizer in the loop) — resolving the subagent's own flag that its quotes were summarizer-transcribed. Two drugs (Epidiolex, Spinraza) have **no boxed warning**; their quotes are taken verbatim from the byte-confirmed Warnings-&-Cautions field and flagged. The sharp **C2 finding** (FAERS under-captures insidious/lab-detected harms — vision loss, hepatotoxicity, suicidality are *not* in the top FAERS terms) is surfaced so the dossier doesn't misread low FAERS counts as low risk.

## Gate evidence
- [x] **`validate-corpus.sh` checks: CLEAN** — 8 cards; invariant fields; max quote 35 words; **all T1 on `api.fda.gov` (`.gov`) → no tier-HELP**; all 8 label URLs HTTP 200 (return JSON). FAERS = T2 supporting data, caveated in-card. Run directly (the canonical script's `/tmp` Windows bug is the open HELP).
- [x] **Gate 1 — full suite GREEN** (`dev/run-tests.sh`; the new corpus dir doesn't perturb any suite).

## Pass B (EMET) — blocked by an intermittent permission
EMET-*driving* not achieved: the Claude-in-Chrome host-permission for `emet.benchsci.com` is **intermittent** (one `get_page_text` read succeeded, then both reads and the `computer` tool failed with the host-permission error on new tabs). So I could not reliably type/submit EMET queries. The mechanism literature behind each class liability is a pending gap (this agent is EMET-central) — needs a stable EMET-driving path (e.g. the extension's "on all benchsci.com" site-access made permanent, or the `$SAPPHIRE_EMET_PROFILE` path Rohan is building in `real-live-emet-frontend`).

## Notes
- **4th of 6** (3 merged: #76/#83/#85; this is the 4th, in review). All-T1, clean `.gov` (openFDA).
- Remaining: payer-market-access (`cms.gov` 403), manufacturing-cmc (`fda.gov` 403; 5 T2-secondary cards researched + held). Both gated on those domains' fetch access, or ship T2-secondary if accepted.
