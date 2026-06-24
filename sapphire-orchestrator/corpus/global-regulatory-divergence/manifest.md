# Manifest — Global Regulatory Divergence corpus

**Agent:** Global Regulatory Divergence Analyst (Bucket 1, semantic) · dossier field **D3** (ex-US regulator divergence).
**Built:** `gavin/corpus-global-regulatory-divergence` (first of Gavin's 6 semantic corpora; pilot per the locked `fda-institutional-memory/METHOD.md`).
**Retrieval window:** 2026-06-24.
**Cards:** **9** in `index.jsonl` (6 regulatory-divergence + 3 EMET biomedical-grounding) · **Notes:** 2 themed files in `notes/`.
**Tier split:** **0 T1 / 9 T2** — see the **Tiering note** below; this is a deliberate, honest under-claim pending a gate decision, not an absence of primary evidence.
**Scope:** a representative CNS slice exercising the divergence check types across **Alzheimer's (anti-amyloid mAbs)** and **DMD (exon-skip / nonsense-readthrough)**, spanning **EMA, MHRA, NICE, FDA**. Breadth-of-method over depth (pilot).

## Dual-source method (both passes run — see METHOD.md Step 3)
- **Browser pass (regulator/HTA primary + secondary).** The shared Playwright browser loaded each source
  and a **verbatim** supporting substring was extracted before tiering. **gov.uk (MHRA)** and
  **nice.org.uk (NICE)** rendered cleanly; sponsor/NGO secondaries (Sarepta, PTC, Alzheimer Europe) were
  used where the regulator primary was unreachable (see below).
- **EMET pass (biomedical class-grounding → T2, `emet-live`).** Live EMET (BenchSci), Thorough mode, 2
  queries → 3 cards, each citing a **real PMID** re-verified against the PubMed abstract. As the METHOD
  predicts, EMET's contribution is **limited for this regulatory agent** — a supporting layer explaining
  *why* regulators diverged (ARIA/ApoE4; the dystrophin surrogate), not the divergence facts themselves.

## ⚠️ Tiering note — why 0 T1 (OPEN question for the approver)
The agent spec says **"Tier regulator decisions T1; HTA bodies T2."** But `dev/validate-corpus.sh` only
accepts **T1** on hosts ending `.gov`/`.edu` or PMC/NCBI. **Every credentialed ex-US regulator fails that
check** (EMA `ema.europa.eu`, MHRA `gov.uk`, PMDA `pmda.go.jp`, TGA `tga.gov.au`, Health Canada
`canada.ca`, …). So the two genuine **regulator-primary** cards here (MHRA lecanemab #1, MHRA donanemab #2)
are **held at T2** with a `tier_note` marking them **T1-eligible**, rather than failing the gate. Logged
to **`dev/HELP.md`** (2026-06-24) with a proposed fix (extend the gate's primary-domain allowlist to
credentialed ex-US national regulators). **If approved, cards #1/#2 (and future EMA/PMDA primaries) flip to T1.**

## EMET pass — 2 Thorough queries run
Public identifiers only. PMIDs re-verified against the PubMed abstract (numbers checked, no mislabeling).
| # | Query (class-mechanism) | Grounds card(s) | chat_url | Verified PMIDs |
|---|---|---|---|---|
| 1 | APOE4 allele dose → ARIA-E/H risk (lecanemab, donanemab) | #1/#2/#6 anti-amyloid + EMET #7/#8 | `emet.benchsci.com/chat/f4a446f3-577d-41c4-816d-c90029cf0f7b` | 38730496, 40063015 |
| 2 | Dystrophin surrogate vs functional benefit (eteplirsen, ataluren) | #4/#5 DMD + EMET #9 | `emet.benchsci.com/chat/362d319b-df27-4295-b37c-79dbceffd36c` | 21784508, 19713152 |

**EMET query 2 caveat:** the chat hit a **network error mid-synthesis** after the eteplirsen dystrophin
section — the ataluren functional-endpoint synthesis did not complete. The eteplirsen citations it had
already produced were verified and used; the ataluren functional-evidence gap is recorded below.

## Coverage map — agent check types
The agent's procedure: find ex-US regulator decisions that **diverge** from the FDA; capture regulator ·
outcome · endpoint/evidence · date · citation; frame as intelligence, not contradiction.

| Check type | Covered? | Cards / note |
|---|---|---|
| **FDA-approved / ex-US-refused** (surrogate not accepted abroad) | ✅ | aducanumab #6, eteplirsen #4 · both notes |
| **Ex-US-approved / FDA-refused** (reverse divergence) | ✅ | ataluren #5 · `notes/dmd-exon-skipping-divergence.md` |
| **Same approval, narrower ex-US label** (genotype gate) | ✅ | lecanemab #1, donanemab #2 · `notes/anti-amyloid-divergence.md` |
| **Regulator-approved but HTA/reimbursement-refused** | ✅ | NICE #3 · anti-amyloid note |
| **Biomedical basis behind the divergence** (EMET) | ✅ | #7/#8 ARIA-ApoE4; #9 dystrophin surrogate |
| **Endpoint/evidence-standard divergence** (surrogate vs functional) | ✅ | eteplirsen #4 + EMET #9; aducanumab #6 |

**Jurisdictions covered:** EMA, MHRA (UK), NICE (UK HTA), FDA. **Modalities:** amyloid-β mAbs,
exon-skipping morpholino ASO, nonsense-readthrough small molecule. **Indications:** Alzheimer's, DMD.

## Source list (retrieved/verified 2026-06-24)
**Regulator / HTA primary (basis for the T1-eligible / T2 cards):**
- MHRA (gov.uk) press releases — lecanemab (22 Aug 2024), donanemab (23 Oct 2024).
- NICE (nice.org.uk) — final draft guidance news, lecanemab + donanemab (19 Jun 2025).

**Secondary, announcing the regulator action (T2):** Sarepta Therapeutics PR (eteplirsen CHMP negative
opinion, 2018); PTC Therapeutics PR (ataluren FDA Refuse-to-File, 2016); Alzheimer Europe (EMA aducanumab
refusal, 2021).

**Biomedical class-grounding (EMET pass; `emet-live` T2):** EMET (BenchSci) Thorough, 2 chats →
PMIDs 38730496 (Honig 2024, *Alzheimers Res Ther*), 40063015 (Zimmer/Mintun 2025, *JAMA Neurol*),
21784508 (Cirak 2011, *Lancet*), 19713152 (Kinali 2009, *Lancet Neurol*). URLs are
`pubmed.ncbi.nlm.nih.gov/<pmid>/` (resolve 2xx; gate-verified).

## Known gaps — the ~30% the agent MUST still search live
1. **EMA primary documents** — EMA's website **search was down on 2026-06-24** ("technical difficulties …
   use our JSON data files"), and deep-links 404'd. The EMA refusals (aducanumab, eteplirsen) and the
   ataluren 2014 conditional MA are therefore cited to faithful secondaries, **not** the EMA EPAR/refusal
   primary. **Re-run when EMA is back to upgrade #4/#5/#6 to EMA-primary** (and, pending the gate decision, T1).
2. **PMDA (Japan), NMPA (China), TGA (Australia), Health Canada, Swissmedic** — no cards this pass;
   ex-Europe/UK jurisdictions are a live-search gap. (Aducanumab was also rejected/withdrawn in Japan —
   unverified here.)
3. **HTA bodies beyond NICE** — PBAC (Australia), G-BA/IQWiG (Germany), ICER (US), CDA-AMC (Canada) not covered.
4. **Ataluren functional-endpoint evidence** — EMET query 2 errored before synthesising it (see EMET caveat).
5. **Therapeutic breadth** — corpus is Alzheimer's + DMD only; psychiatry, epilepsy, pain, PD divergences absent.
6. **Anything fresher than 2026-06-24** — divergence status changes (re-examinations, new HTA appraisals) — always a live call.

## Omitted for lack of a verifiable source this pass (NOT fabricated)
Per-genotype donanemab ARIA percentages (40.6% / 22.8% / 15.7%): EMET attributed these partly to a review
(PMID 38001337) whose **abstract does not contain them** — omitted rather than mis-cited; the verified
overall figures + allele-dose statement (PMID 40063015) are used instead. Lecanemab/donanemab EU (EMA)
authorisations and their ApoE4 scope (well documented, EMA-primary unreachable) — not carded separately;
the MHRA cards carry the genotype-restriction divergence.
