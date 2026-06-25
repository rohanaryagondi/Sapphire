# Manifest — KOL & Social Signal corpus

**Agent:** KOL & Social Signal Monitor (Bucket 1, semantic) · dossier field **F2** (KOL / expert sentiment).
**Built:** `gavin/corpus-kol-social-signal` (4th of Gavin's 6 semantic corpora; per `fda-institutional-memory/METHOD.md`).
**Retrieval window:** 2026-06-25.
**Cards:** **6** in `index.jsonl` (5 named-KOL on-record positions + 1 EMET validation) · **Notes:** 1 themed file in `notes/`.
**Tier split:** **0 T1 / 6 T2** — by design: this agent's signal is *expert opinion*, which is inherently secondary. The spec's 4-tier scheme (T3 named-expert / T4 anonymous) maps onto the corpus's T1/T2 gate as **T2**; **T4 anonymous/social is excluded from pre-ingestion** (live-harvest only — see scope note).
**Scope:** durable, attributable named-KOL positions on the two dominant CNS sentiment debates (anti-amyloid AD antibodies; muscarinic antipsychotics). Breadth-of-method over depth (pilot).

## Scope & tiering decision (important — read first)
The spec tiers **named-expert-on-record = T3**, **anonymous/social = T4**; the corpus gate accepts only **T1/T2**.
Resolution (consistent with financial-investor's T3→T2 mapping):
- **Pre-ingest only named-expert-on-record signals**, mapped to **T2**, each fully attributed + dated +
  cited to a durable public source (journal editorial/viewpoint URL on PubMed).
- **Ephemeral social signal (spec T4: X.com, Substack, LinkedIn, podcasts) is intentionally NOT pre-ingested**
  — it isn't stably citable/verbatim-verifiable and changes daily. That is the agent's **live-harvest ~30%**.
- Per the spec, a claim's *validity* is not asserted here; load-bearing claims are **validated against EMET**
  (demonstrated by card #6).

## Dual-source method (both passes — METHOD.md Step 3)
- **Pass A (browser + PubMed):** identified named-KOL editorials/viewpoints via the PubMed MCP; each card cites
  a real PMID (resolves) with a **verbatim** quote — the editorial's abstract where indexed, else the verbatim
  **editorial title** (the expert's on-record framing). Authors' standing noted (senior KOLs up-weighted; junior down-weighted).
- **Pass B (EMET):** 1 Thorough query **validating a load-bearing KOL claim** (Kurkinen's "no benefit in women / harm in ApoE4 homozygotes"), PMID re-verified vs the PubMed abstract. This is the agent's own EMET hand-off, executed.

## EMET pass — 1 Thorough query (claim-validation)
| # | Query | Validates | chat_url | Verified PMID |
|---|---|---|---|---|
| 1 | CLARITY AD lecanemab subgroup effect by sex & APOE4 (women / ε4 homozygotes) | KOL card #1 (Kurkinen) | `emet.benchsci.com/chat/ca0f85cd-cced-4634-bbf2-3ea50eb977a0` | 41352683 (Shim et al. meta-analysis) |
**Finding:** subgroup heterogeneity is real (efficacy greatest in ApoE4 non-carriers; sex a modifier; ARIA higher in ε4 carriers) — but CLARITY AD was **not powered** for a sex×treatment interaction, so the KOL's "no benefit in women" overreads an underpowered subgroup. (van Dyck CLARITY AD = PMID 36449413; subgroup detail is in the supplement, not the abstract — so it is described, not quoted-as-abstract.)

## Coverage map — agent check types
| Check type (procedure) | Covered? | Cards |
|---|---|---|
| **KOL sentiment** (who · venue · claim · date · attribution) | ✅ | #1–#5 |
| **Divergence** (informal/expert view vs published consensus, and optimist vs skeptic) | ✅ | anti-amyloid skeptics (#1–#3) vs muscarinic optimists (#4–#5) |
| **Validate load-bearing claim against EMET** (the spec hand-off) | ✅ | #6 |
| **Pre-publication / social signal** (X/Substack/conference posts) | ⚠️ gap | live-harvest only (T4 — not pre-ingestable) |

**Experts captured:** Knopman, Perlmutter, Bauchner, Alexander (anti-amyloid skeptics; several FDA AdComm members), Kurkinen (lecanemab skeptic), Javitt (muscarinic, cautious-optimistic). **Drugs:** aducanumab, lecanemab, xanomeline-trospium (KarXT/Cobenfy).

## Source list (retrieved/verified 2026-06-25; all PubMed)
PMID 37676096 (Kurkinen, Adv Clin Exp Med 2023) · 34233938 (Knopman & Perlmutter, Neurology 2021) ·
35319522 (Bauchner & Alexander, Med Care 2022) · 40022530 (Javitt, Am J Psychiatry 2025) ·
39525169 (Hasan & Abid, Cureus 2024) · 41352683 (Shim et al., Ageing Res Rev 2025 — EMET validation).
URLs are `pubmed.ncbi.nlm.nih.gov/<pmid>/` (resolve 2xx; gate-verified).

## Known gaps — the ~30% the agent MUST harvest live
1. **Ephemeral social signal (the agent's core live job):** X.com high-signal accounts, Substack newsletters,
   podcast/interview commentary, conference (ACNP/APA/ADAA) abstract reactions, LinkedIn posts — **not
   pre-ingestable** (unstable, often not verbatim-citable). Harvest live, attribute, tier T4 in-flight.
2. **Pre-publication / preprint discussion** — EMET owns the preprints; this agent reads the *discussion*.
3. **Therapeutic breadth** — anti-amyloid + muscarinic only; psychedelics, ALS, PD, pain KOL sentiment absent.
4. **Anything after the retrieval window** — sentiment moves fast; always a live call.

## Omitted for lack of a verifiable source this pass (NOT fabricated)
The famous FDA AdComm *resignation* quotes (e.g., a member calling aducanumab's approval "the worst…in recent
US history") are widely reported but the primary is a resignation letter / news interview not stably citable
this pass; the *published* critiques by the same experts (Knopman, Alexander) are carded instead. CLARITY AD
sex-subgroup exact CIs live in the trial supplement (not the PubMed abstract) — described, not quoted.
