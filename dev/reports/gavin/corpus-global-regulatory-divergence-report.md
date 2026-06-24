# Report — corpus: global-regulatory-divergence (Gavin, pilot of the 6)

**Branch:** `gavin/corpus-global-regulatory-divergence` · **Built-By:** gavin · **Date:** 2026-06-24
**Task:** `semantic-corpora` (Gavin 6) — first PR, the pilot-gate one (ship → wait for review → batch the rest).
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md` (FDA-memory worked example).

## What this PR adds
A dual-source, queryable knowledge corpus for the **Global Regulatory Divergence Analyst** (Bucket-1
semantic, dossier field **D3**):
- `sapphire-orchestrator/corpus/global-regulatory-divergence/index.jsonl` — **9 claim-cards**
- `…/notes/anti-amyloid-divergence.md`, `…/notes/dmd-exon-skipping-divergence.md`
- `…/manifest.md`, `…/QUERIES.md`
- Upgraded the skill doc `architecture/bucket1/semantic/global-regulatory-divergence.md` → **corpus-first → search-the-gap**
- `dev/HELP.md` — one OPEN request (the tier/gate question below)

## Coverage (9 cards, breadth-of-method over depth)
Divergence check types, all cited + dated + verbatim-quoted:
- **FDA-approved / ex-US-refused:** aducanumab (EMA refused 2021 vs FDA accel. approval); eteplirsen (EMA CHMP negative 2018 vs FDA accel. approval 2016).
- **Ex-US-approved / FDA-refused (reverse):** ataluren (EMA conditional MA 2014 vs FDA Refuse-to-File 2016).
- **Same drug, narrower ex-US label (ApoE4-gated):** lecanemab & donanemab (MHRA licensed, restricted to non-homozygotes).
- **Regulator-approved but HTA-refused:** NICE did not recommend lecanemab/donanemab for the NHS (2025).
- **Biomedical basis (EMET pass, 3 `emet-live` cards):** APOE ε4 allele-dose ARIA risk (PMIDs 38730496, 40063015); eteplirsen dystrophin surrogate (PMID 21784508).

Jurisdictions: EMA, MHRA, NICE, FDA. Modalities: amyloid-β mAbs, exon-skipping ASO, nonsense-readthrough. Indications: Alzheimer's, DMD.

## Dual-source passes
- **Pass A (browser):** loaded each source in the shared Playwright browser, extracted **verbatim** quotes. gov.uk (MHRA) + nice.org.uk rendered cleanly; sponsor/NGO secondaries used where the regulator primary was unreachable.
- **Pass B (EMET):** 2 Thorough queries → 3 cards. **Every PMID re-verified against the PubMed abstract** (caught + avoided one mislabel: EMET attributed per-genotype donanemab numbers to a review (PMID 38001337) whose abstract doesn't contain them — omitted, used the verified PMID 40063015 instead).
  - chat 1 (ARIA/ApoE4): `emet.benchsci.com/chat/f4a446f3-577d-41c4-816d-c90029cf0f7b`
  - chat 2 (DMD surrogate): `emet.benchsci.com/chat/362d319b-df27-4295-b37c-79dbceffd36c` — **hit a network error mid-synthesis** after the eteplirsen section; ataluren functional-endpoint synthesis incomplete (recorded as a gap).

## Gate
`bash dev/validate-corpus.sh sapphire-orchestrator/corpus/global-regulatory-divergence` →
**`✓ corpus validation CLEAN`** (9 cards parsed; schema + tier-domain ok; all 9 URLs resolve).
*Windows note:* the gate's `python3`/`/tmp` assumptions need a shim + a `/tmp`→`C:/tmp` Git Bash mount on this box; build-environment only, no repo change. (Same cross-platform class Hayes flagged; not in scope to fix here.)

## ⚠️ OPEN question for the approver (dev/HELP.md, 2026-06-24) — please decide before I batch the other 5
The spec says **"tier regulator decisions T1; HTA bodies T2."** But `validate-corpus.sh` only allows T1 on
`.gov`/`.edu`/PMC/NCBI hosts, and **every ex-US regulator domain fails** (EMA `ema.europa.eu`, MHRA
`gov.uk`, PMDA `pmda.go.jp`, TGA `tga.gov.au`, Health Canada `canada.ca`, …). So I held the two genuine
regulator-primary cards (MHRA lecanemab/donanemab) at **T2** with a `tier_note` (T1-eligible) rather than
fail the gate. **Proposed fix:** extend the gate's primary-domain allowlist to credentialed ex-US national
regulators (keep HTA bodies T2). If you approve, those cards (and future EMA/PMDA primaries) flip to T1.
This affects the other ex-US-primary agents too (e.g. policy-legislative), so worth settling on this pilot.

## Honest gaps (see manifest)
1. **EMA primary docs** — EMA's website **search was down 2026-06-24** ("technical difficulties… use our JSON data files"); deep-links 404'd. EMA refusals (aducanumab, eteplirsen) + ataluren's 2014 conditional MA are cited to faithful secondaries, not the EMA EPAR. Re-fetch to upgrade.
2. PMDA/NMPA/TGA/Health Canada/Swissmedic — no cards this pass.
3. HTA beyond NICE (PBAC/G-BA/ICER/CDA-AMC) — none.
4. Ataluren functional-endpoint EMET synthesis — incomplete (chat network error).
5. Therapeutic breadth — Alzheimer's + DMD only.

## Anti-fabrication
Every quote is a verbatim substring of the fetched page (Pass A) or a faithful, abstract-verified synthesis
of the EMET answer (Pass B). No invented PMIDs, dates, or quotes. Public identifiers only. Where a primary
couldn't be fetched, the card is honest T2 + flagged, never up-tiered.

## Next (after review)
On approval + the tier decision, I'll batch the remaining 5 (financial-investor, kol-social-signal,
patient-advocacy, policy-legislative, reputational-institutional), one PR each.
