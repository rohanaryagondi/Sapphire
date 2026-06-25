# Manifest — Financial & Investor Intelligence corpus

**Agent:** Financial & Investor Intelligence Analyst (Bucket 1, semantic) · dossier field **E2** (competitive pipeline / deals).
**Built:** `gavin/corpus-financial-investor` (2nd of Gavin's 6 semantic corpora; per the locked `fda-institutional-memory/METHOD.md`).
**Retrieval window:** 2026-06-24.
**Cards:** **6** in `index.jsonl` (5 financial/deal events + 1 EMET deal-thesis grounding) · **Notes:** 2 themed files in `notes/`.
**Tier split:** **3 T1 / 3 T2** — T1 = SEC primary filings (`sec.gov` 8-Ks); T2 = company/IR press + the EMET card.
**Scope:** a representative CNS slice exercising the agent's check types — deal intel (M&A structure → implied PoS), risk/write-down events (clinical failures, impairment), and the biomedical thesis behind the deals. Breadth-of-method over depth (pilot).

## Tiering note — spec "T3" mapped to the corpus's T1/T2 scheme
The agent spec (Hayes' draft) says *"Tier SEC filings T1, press/analyst T3."* The corpus/gate scheme
(`dev/validate-corpus.sh`, METHOD) is **two-tier (T1/T2 only)**. Mapping applied: **SEC filings → T1**
(host `sec.gov`, passes the gate's `.gov` primary rule); **press/analyst/IR → T2**. (So the spec's "T3
press" = corpus "T2".) This is a within-METHOD interpretation, not a gate change — no HELP needed. EMET
cards are T2 `emet-live` as usual.

## Dual-source method (both passes run — METHOD.md Step 3)
- **Pass A (browser):** loaded each SEC 8-K (Exhibit 99.1 press releases) and company/IR pages in the
  shared Playwright browser; extracted **verbatim** deal terms / trial outcomes. SEC EDGAR rendered cleanly.
- **Pass B (EMET):** 1 Thorough query (the M1/M4 muscarinic schizophrenia thesis behind the Karuna/Cerevel
  deals) → 1 `emet-live` card, PMID re-verified vs the PubMed abstract. As the brief predicts, EMET is
  **thin for this financial agent** — it grounds the *science behind* a deal, not the deal facts; 1 card is
  the honest yield.

## EMET pass — 1 Thorough query
| # | Query (deal thesis) | Grounds | chat_url | Verified PMID |
|---|---|---|---|---|
| 1 | M1/M4 muscarinic agonism (KarXT) & M4 PAM (emraclidine) efficacy in schizophrenia | #1/#2/#3 + EMET #6 | `emet.benchsci.com/chat/fc6c233e-1ef8-412a-89c5-71236226baef` | 33626254 (EMERGENT-1, NEJM 2021) |

## Coverage map — agent check types
| Check type (procedure) | Covered? | Cards |
|---|---|---|
| **DEAL INTEL** — M&A structure → implied PoS | ✅ | #1 BMS/Karuna · #2 AbbVie/Cerevel · #4 J&J/Intra-Cellular |
| **RISK DISCLOSURES / write-downs** — program failure, impairment | ✅ | #3 emraclidine Ph2 fail/impairment · #5 navacaprant Ph3 fail |
| **COMPETITIVE PIPELINE (E2)** — who/what-stage in CNS | ✅ | schizophrenia (KarXT, emraclidine, Caplyta), MDD (navacaprant) |
| **Deal thesis (biomedical basis)** — EMET | ✅ | #6 EMERGENT-1 muscarinic PoC |
| **Stage-de-risks-price** (pre-approval vs commercial) | ✅ | #1/#2 (pre-approval) vs #4 (approved franchise) |

**Companies/tickers:** BMY, KRTX, ABBV, CERE, JNJ, ITCI, NMRA. **Modalities/MoA:** M1/M4 muscarinic
agonist, M4 PAM, lumateperone, kappa-opioid antagonist. **Indications:** schizophrenia, bipolar depression, MDD.

## Source list (retrieved/verified 2026-06-24)
**SEC primary (T1):** SEC EDGAR 8-K Exhibit-99.1 press releases — BMS/Karuna (data/14272/…ef20017313_ex99-1.htm);
Cerevel/AbbVie (data/1805387/…d509048dex991.htm); Intra-Cellular/J&J (data/1567514/…d910241dex991.htm).
*These three loaded + verbatim-verified in the Playwright browser, but `sec.gov` returns HTTP 403 to
automated `curl` (SEC requires a declared User-Agent), so each is tagged `"unverifiable_by_fetch": true`
per METHOD — honest flag for a primary the gate's curl can't reach but the browser pass read directly.*
**Company / press (T2):** AbbVie PR (emraclidine EMPOWER Phase 2 update, Nov 2024); Psychiatric Times
(Neumora KOASTAL-1, Jan 2025 — Neumora's own IR PR is browser-loadable but curl-unreachable here, so a
faithful secondary is cited; see card `primary_source_note`).
**Biomedical grounding (EMET, T2 `emet-live`):** PMID 33626254 (Brannan et al., *NEJM* 2021, EMERGENT-1),
`pubmed.ncbi.nlm.nih.gov/33626254/`.

## Known gaps — the ~30% the agent MUST still search live
1. **10-K/10-Q risk-factor language & XBRL impairments** — this pass used 8-K event filings + PRs; the candid
   10-K risk factors and the exact emraclidine impairment figure ($ from AbbVie's Q4-2024/Jan-2025 filing)
   were not fetched — pull from EDGAR for the precise write-down number.
2. **Deal *structure* detail** — all 5 events here are all-cash buyouts/clinical readouts; **licensing deals
   with upfront/milestone splits** (which most directly encode implied PoS) are not yet carded — add a few
   (e.g. CNS licensing/option deals) live.
3. **Private-company financings** — Crunchbase/PitchBook rounds, IPOs; thin public disclosure (e.g. Lykos
   after its CRL) — known-unknowns.
4. **Earnings-call / conference commentary** (Seeking Alpha transcripts, JPM Healthcare) — not mined this pass.
5. **Therapeutic breadth** — schizophrenia + MDD heavy; neurodegeneration/rare-CNS deal intel thin.
6. **Anything after 2026-06-24** — deal/catalyst calendar is live; always a fresh call.

## Omitted for lack of a verifiable source this pass (NOT fabricated)
The exact AbbVie emraclidine impairment figure (~$3.5B, reported via press citing a Jan-2025 SEC filing) —
stated qualitatively in card #3, not as a verified number, because the AbbVie SEC filing was not fetched.
Neumora's exact "−80%" stock move is press-sourced (not in the IR PR), so it's flagged "per press" not quoted.
