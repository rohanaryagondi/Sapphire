# Report — dea-scheduling corpus (semantic-corpora, 2nd of 6)

**Built-By:** hayes · **Branch:** `hayes/corpus-dea-scheduling` · **Task:** `semantic-corpora` → dea-scheduling ·
**Date:** 2026-06-25 · **Method:** `corpus/fda-institutional-memory/METHOD.md`.

## What this delivers
The **dea-scheduling** Bucket-1 knowledge corpus (dossier field **D4** controlled-substance status), **Pass A
complete**. It pre-ingests the stable DEA scheduling record for the CNS-relevant controlled compounds, organized
by the recurring patterns the agent reasons over.

- `index.jsonl` — **9 verified cards**, **all T1** (`govinfo.gov` `.gov` primaries): psilocybin · LSD · MDMA
  (Schedule I, 21 CFR 1308.11(d)); ketamine · esketamine (Sched III, the latter by isomer-reference); GHB/sodium
  oxybate (split Sched I/III); dronabinol/Marinol (Sched III); cannabidiol/Epidiolex (Sched V, 2018); FDA-approved
  marijuana products (Sched III, **the April 2026 rescheduling**).
- `notes/cns-controlled-substance-scheduling.md` — the 4 patterns: Schedule I psychedelics · the FDA-approval→
  scheduling pathway · the split schedule · isomer-reference.
- `manifest.md` (sources + coverage map + honest gaps) · `QUERIES.md` (6 D4 checks answered from the corpus).

## Sourcing finding (reusable for future corpora)
`federalregister.gov` and `ecfr.gov` **bot-wall** automated fetches (302 → `unblock.federalregister.gov`), and
`dea.gov`/`deadiversion.usdoj.gov` PDFs return 403/binary. **GPO `govinfo.gov` HTML** (`/content/pkg/.../html/…htm`)
is the reliably-fetchable `.gov` primary and is the canonical fetch target for Federal-Register/CFR-based corpora.

## Anti-fabrication (verified, not trusted)
A research subagent surfaced candidates; I then **independently re-verified all load-bearing cards** against the
fetched govinfo primary, and caught two issues:
- **GHB quote was truncated** mid-sentence (dropped the "...except that it will be subject to the criminal
  sanctions applicable to a Schedule I controlled substance…" clause) → replaced with the **full verbatim sentence**.
- **MDMA card over-reached its citation** (claimed the 2024 FDA CRL, which the cited CFR doesn't support) → claim
  **scoped to the CFR-backed Schedule-I fact**; the 2024 Lykos CRL kept as clearly-labeled *context* (not the cited/quoted primary).
- The recent, high-impact **April 2026 marijuana → Schedule III** card was verified word-for-word against the FR
  final order; ketamine, dronabinol, Epidiolex, and the CFR codes (psilocybin 7437 / LSD 7315 / MDMA 7405) all confirmed verbatim.

## Gate evidence
- [x] **`validate-corpus.sh` checks: CLEAN** — 9 cards; all invariant fields; max quote 46 words (≤60); **all T1
  on `govinfo.gov` (`.gov`) — tier-domain rule satisfied with no HELP needed**; all URLs HTTP 200. Verified by
  running the gate's exact logic directly (the canonical script still can't run on Windows — the `/tmp` bug filed
  in HELP for patent-ip).
- [x] **Gate 1 — full suite GREEN** (`dev/run-tests.sh`; the new corpus dir doesn't perturb any suite).

## Pass B (EMET) — pending the same extension permission
EMET not run — the Claude-in-Chrome extension lacks host access to `emet.benchsci.com` (logged in, DOM reads
permission-blocked). For this regulatory agent EMET is a *literature* layer (METHOD §3 Pass B), so Pass A stands
on its own; recorded as an honest gap in `manifest.md`, to add once host access is granted.

## Notes
- **2nd of my 6 corpora**, after patent-ip (#76, merged). dea-scheduling is **all-T1** (clean `.gov` sourcing),
  so unlike patent-ip it needs no tier-upgrade HELP.
- Remaining: post-market-safety + clinical-trial-registry (EMET-*central* — gated on the BenchSci extension
  permission), then payer-market-access + manufacturing-cmc (Pass-A-amenable, like this one).
