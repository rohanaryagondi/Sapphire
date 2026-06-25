# Report — patent-ip corpus (semantic-corpora, 1st of 6)

**Built-By:** hayes · **Branch:** `hayes/corpus-patent-ip` · **Task:** `semantic-corpora` → patent-ip ·
**Date:** 2026-06-25 · **Method:** `corpus/fda-institutional-memory/METHOD.md`.

## What this delivers
The **patent-ip** Bucket-1 knowledge corpus (veto-class, dossier field **E1** freedom-to-operate), **Pass A
complete**. It pre-ingests the stable CNS-FTO patent landscape, anchored on the **SMA franchise** — the one
disease addressed by all three modalities the agent reasons over (ASO · small molecule · AAV gene therapy) — so a
run hits local first and spends a live call only on the novel ~30%.

- `index.jsonl` — **7 verified claim-cards**: nusinersen SMN2 family (`US8361977B2`, `US8980853B2`), risdiplam
  composition (`US9969754B2`, →2035), Genzyme AAV9-SMA method (`US10821154B2`, →2033), UPenn AAV9 capsid
  (`US7906111B2`, lapsing 2026), AveXis/Zolgensma PCT (`WO2019094253A1`, ceased), Ionis gapmer platform
  (`US9550988B2`, →2028). 5 veto-candidate · 2 landscape; modalities ASO/SM/AAV/platform all covered.
- `notes/sma-franchise-and-modality-fto.md` — themed FTO note + the composite expiry-cliff timeline (2026→2035).
- `manifest.md` — sources, coverage map, retrieval date (2026-06-25), tiering note, honest known-gaps.
- `QUERIES.md` — 6 realistic FTO checks answered from the corpus + the explicit live-search gaps.

## Anti-fabrication (the whole game for a veto-class agent)
Every card was verified against the **fetched primary patent page**; search summaries were treated as unverified
leads only. Caught and discarded real mismatches:
- WebSearch claimed `US9416143` = a nusinersen 2'-MOE composition patent → fetching it showed a **Pierre Fabre
  "Griseofulvin derivatives"** patent (unrelated). Dropped.
- A research subagent caught `US12478692` (titled "Gene therapy for SMA") = a **UMass competitor** patent that
  *compares itself against* Zolgensma — not Zolgensma's own IP. Dropped.
- I **independently re-verified every quote** against the primary; where Google Patents didn't server-render the
  abstract I used **verbatim independent-claim text** (claims render reliably). This replaced several
  secondary-mirror quotes the subagent had drawn from freepatentsonline — e.g. `US10821154`'s original quote
  ("Viral particles comprising AAV9 capsids are contemplated") was **not on the primary**; replaced with a
  verbatim leading substring of claim 1.

## Gate evidence
- **`validate-corpus.sh` checks: CLEAN** — 7 cards parsed; all invariant fields present; max quote 48 words
  (≤60); tier rule satisfied (all T2 → T1-domain rule N/A); **all 7 URLs resolve HTTP 200**. Verified by running
  the gate's exact schema/tier + URL-liveness logic directly (the canonical script can't run on this Windows box
  — it hardcodes `/tmp`, which Windows-`python3` resolves to a non-existent `C:\tmp`; flagged in HELP as a
  cross-platform tooling bug, same class as the moat/cp1252 fixes).
- **Gate 1 — full suite GREEN: 478 tests** (`dev/run-tests.sh`; the new corpus dir doesn't perturb any suite).

## Tiering (HELP-gated T1 upgrade)
All 7 cards cite `patents.google.com` and are tiered **T2** because the gate's T1 allowlist is `.gov/.edu/PMC`
(+ ex-US regulators) and excludes patent domains. The spec treats granted patents as **T1-primary**, so I filed
HELP **`patent-ip-t1-patent-domains`** to add patent domains to the allowlist (same pattern as the ex-US-regulator
fix, PR #31); on resolution I re-tier the 5 granted-US patent cards to T1. The gate passes cleanly at T2 today.

## Pass B (EMET) — pending an extension permission
The EMET biomedical-grounding pass is **not yet run**: the Claude-in-Chrome extension lacks host access to
`emet.benchsci.com` (session is logged in, but `get_page_text`/`find` are permission-blocked). For this
legal-record agent EMET is a supporting layer (METHOD §3 Pass B), so Pass A stands on its own; the EMET
PMID cards are an honest pending gap (`manifest.md` gap 1) to add as a follow-up once host access is granted.

## Asks for the approver
1. **Content audit** the 7 cards (citations / verbatim quotes / tiering / classification) — same audit you ran on
   Gavin's first corpus.
2. Answer the two HELP items: **`patent-ip-t1-patent-domains`** (T1 re-tier) and the **`validate-corpus.sh` `/tmp`
   Windows bug**.
3. If you want Pass B before merge, I'll add it once the BenchSci extension permission is granted; otherwise this
   ships Pass-A-first and EMET follows.

This is the **first** of my 6 corpora — shipping it for review before batching the rest (post-market-safety,
clinical-trial-registry, payer-market-access, manufacturing-cmc, dea-scheduling), per the locked method.
