# Manifest — FDA Institutional Memory corpus

**Agent:** FDA Institutional Memory ⛔ (Bucket 1, semantic, veto-class) · dossier fields **C3** (veto) / **D2** (precedent).
**Built:** pilot (`rohan/corpus-pilot-fda-memory`), then **perfected** (`rohan/corpus-perfect-fda-memory`) by adding the two missing ingestion sources — a browser FDA-primary pass and a live EMET pass.
**Retrieval window:** 2026-06-22 → 2026-06-23.
**Cards:** **45** in `index.jsonl` (35 regulatory-precedent + **10 EMET biomedical-grounding**) · **Notes:** 5 themed files in `notes/`.
**Tier split:** **21 T1 / 24 T2** (was 11 T1 / 24 T2 at pilot close; the browser pass upgraded 10 regulatory cards to T1, and the EMET pass added 10 new T2 cards).
**Scope:** representative CNS-relevant slice exercising every check type — NOT exhaustive (pilot). Breadth-of-method over depth.

## Dual-source method (both passes are STANDARD — see METHOD.md Step 3)
This corpus is built from **two complementary ingestion passes**, honestly tiered:
- **Browser pass (FDA-primary → T1).** The shared Playwright browser loads the actual primary document
  (fda.gov drug-safety communications / news releases / `fda.gov/media/<id>/download` AdComm summaries +
  decision memos; `accessdata.fda.gov` labels/reviews; `federalregister.gov`; `govinfo.gov`) and a
  **verbatim** supporting substring is extracted before a card is tiered **T1**. PDFs are fetched + `pdftotext`'d.
  If a primary genuinely won't render, the card stays **T2** (honest). This pass is what upgrades T2 → T1.
- **EMET pass (biomedical class-grounding → T2, `emet-live`).** Live EMET (BenchSci), Thorough mode, supplies
  the *cited biomedical basis behind* the regulatory record — the receptor/biomarker mechanism explaining
  *why* the FDA acted. EMET cards are **T2**, cite a real **PMID** (`pubmed.ncbi.nlm.nih.gov/<pmid>/`), carry
  `provenance:"emet-live"` + `emet_chat_url`, and quote a verbatim substring of the EMET answer. EMET's
  contribution is **limited for this regulatory agent** (a supporting layer); it is **central** for the
  post-market-safety / clinical-trial-registry / target-validation agents.

## Cards upgraded to T1 by the browser pass (10) — each with the primary loaded + verbatim quote
| Card (drug / action) | T1 primary URL loaded |
|---|---|
| #6 lorcaserin (Belviq) withdrawal | fda.gov DSC page (`…belviq-belviq-xr-lorcaserin…`) |
| #9 valdecoxib (Bextra) withdrawal | fda.gov NSAID/CV review memo (`fda.gov/media/74279/download`) |
| #10 antidepressant pediatric-suicidality boxed warning | accessdata.fda.gov label PDF (`…/2005/18207s030lbl.pdf`) |
| #13 opioid+benzodiazepine boxed warning | fda.gov news/safety-measures page |
| #15 aducanumab AdComm 10-against / 1-uncertain | fda.gov Dunn accelerated-approval memo (`fda.gov/media/149903/download`) |
| #16 tofersen AdComm 9-0 NfL-surrogate vote | fda.gov PCNS AdComm summary (`fda.gov/media/167354/download`) |
| #18 MDMA AdComm 2-9 efficacy vote | fda.gov PDAC meeting summary (`fda.gov/media/180463/download`) |
| #21 aducanumab accelerated approval | fda.gov Dunn accelerated-approval memo (`fda.gov/media/149903/download`) |
| #22 lecanemab conversion to traditional approval | fda.gov news release (`…fda-converts-novel-alzheimers…`) |
| #23 tofersen accelerated approval | accessdata.fda.gov QALSODY label (`…/2023/215887s000lbl.pdf`) |

**Stayed T2 (primary not cleanly fetchable / not published):** most CRLs (FDA does not publish CRLs — #1
pimavanserin, #2 NurOwn, #3 zuranolone, #4 MDMA, #5 AXS-07 stay on sponsor releases); #7 pergolide (2007
withdrawal, no fetchable FDA-primary — kept on NBC + grounded by EMET 5-HT2B cards); #11 antipsychotic
mortality warning (kept on PMC, grounded by EMET); #14 Chantix, #17 AMX0035, #19 esketamine, #20 lecanemab
AdComm (clean verbatim FDA-primary vote text not extractable this pass); #25 nusinersen, #26/#27 gene-therapy
holds (sponsor/trade press). These are honest T2 — not failures, just not browser-upgradable this pass.

## EMET pass — 5 Thorough queries run (all returned citable PMIDs; no gaps)
Public identifiers only. Each query → 2 EMET claim-cards (`provenance:"emet-live"`).
| # | Query (class-mechanism) | Grounds card(s) | chat_url | Key PMIDs |
|---|---|---|---|---|
| 1 | 5-HT2B agonism → cardiac valvulopathy (ergots / fenfluramine) | #7 pergolide withdrawal | `emet.benchsci.com/chat/595fe1c8-7cac-4a5f-84ef-ad404877ac84` | 10617681, 16614540 |
| 2 | amyloid-β mAbs → ARIA (incidence, APOE ε4) | #15/#20/#21/#22 amyloid | `emet.benchsci.com/chat/1411400e-20f6-4bf4-a8aa-45648431db0f` | 34807243, 38730496 |
| 3 | plasma NfL as surrogate biomarker in ALS | #16/#23 tofersen NfL | `emet.benchsci.com/chat/a0707246-264f-4b81-aeb7-7441f5bd67ee` | 30014505, 36129998 |
| 4 | SSRIs/antidepressants → pediatric suicidality | #10 boxed warning | `emet.benchsci.com/chat/8ba63754-6ae3-4687-b5d1-80d21da70b85` | 16520440, 17440145 |
| 5 | antipsychotics → mortality in elderly dementia | #11 boxed warning | `emet.benchsci.com/chat/ab6359a8-a4c2-4ca8-8302-a54d7d22fa16` | 16234500, 16319382 |

**EMET gap queries:** none — every query returned multiple verified PMIDs (each chat returned 17–31 cited
sources). No EMET query came back empty; nothing was invented.

## What this corpus is for
Pre-ingested, cited FDA regulatory precedent so a run hits **local first** (the stable ~70%) and spends a
live web/EMET call only on the novel/fresh ~30%. Every claim is traceable to a real fetched source; a
**veto requires a T1 citation** per the agent spec.

## Card distribution (by decision type)
| decision | count |
|---|---|
| guidance | 8 |
| adcomm_vote | 6 |
| CRL | 5 |
| approval (incl. accelerated/surrogate) | 5 |
| safety_action (boxed warning / dosing restriction) | 5 |
| withdrawal (market removal) | 4 |
| clinical_hold | 2 |
| class_evidence (EMET biomedical grounding) | 10 |
| **total** | **45** |

## Coverage map — agent check types
The agent's procedure: frame a *flaw hypothesis* → look for matching FDA precedent → classify `precedent`
vs **`veto`**. Coverage of the decision categories that feed that:

| Check type (procedure step) | Covered? | Cards / note |
|---|---|---|
| **CRL / refuse-to-file** precedent (efficacy, CMC, subgroup, modality) | ✅ | 5 cards · `notes/cns-crls.md` |
| **Withdrawal / market action** on a shared liability | ✅ | 4 cards · `notes/cns-withdrawals.md` |
| **Boxed warning / safety restriction** (class-wide & reversible) | ✅ | 5 cards · `notes/cns-withdrawals.md` |
| **Advisory Committee** outcome + what it turned on | ✅ | 6 cards · `notes/advisory-committee.md` |
| **Clinical hold** (trial death / platform tox) | ⚠️ partial | 2 cards (both gene-therapy/neuromuscular) · `notes/endpoint-precedent.md` |
| **Guidance / endpoint precedent** (what FDA expects) | ✅ | 8 cards · `notes/guidances.md` |
| **Accelerated approval / surrogate-endpoint** case law + confirmatory outcomes | ✅ | 5 cards · `notes/endpoint-precedent.md` |
| **AdComm-is-advisory-not-binding** interpretive rule | ✅ | aducanumab override card + `notes/advisory-committee.md` |
| **Biomedical class/biomarker basis behind the FDA action** (EMET) | ✅ | 10 EMET cards (`provenance:"emet-live"`) grounding #7/#10/#11/#15/#16/#20/#21/#22/#23 |

**Indication breadth:** Alzheimer's, ALS, depression/MDD/PPD, PTSD/psychedelic, schizophrenia/dementia
psychosis, Parkinson's, epilepsy, migraine, pain (incl. opioids/COX-2), insomnia, ADHD, smoking cessation,
SMA, DMD (neuromuscular surrogate precedent).

## Source list (authoritative; retrieved/verified in window — primary .gov pages that block automated fetch are flagged, see Tiering note)
**Primary / regulatory (basis for T1):**
- govinfo.gov Federal Register PDF — pemoline withdrawal (FR-2023-05-23).
- NIH PMC / PubMed / NCBI Bookshelf reproducing FDA primary text — Early-AD guidance (PMC6804505),
  zolpidem DSC analysis (PMC4560192), migraine endpoints (PubMed 30953576), accelerated-approval BEST
  framework (NBK453485), aducanumab AdComm review (PMC8491638), eteplirsen accelerated approval (PMC5338848).
- federalregister.gov canonical guidance notices (ALS 2019-20629, MDD 2018-13297, POS 2019-19291,
  DMD 2018-03225) — cited canonically; verified via the live search index + reproducing sources.
- NIH PMC reproducing the FDA action verbatim — eteplirsen accelerated approval (PMC5338848).
- **Browser-pass FDA-primary documents loaded + verbatim-verified this pass (basis for the 10 T1 upgrades):**
  fda.gov lorcaserin DSC; fda.gov Bextra NSAID/CV review memo (media/74279); accessdata.fda.gov antidepressant
  boxed-warning label (18207s030lbl); fda.gov opioid+benzodiazepine safety-measures page; fda.gov Dunn
  aducanumab accelerated-approval memo (media/149903 — both the AdComm vote recount and the approval rationale);
  fda.gov tofersen PCNS AdComm summary (media/167354); fda.gov MDMA PDAC meeting summary (media/180463);
  fda.gov lecanemab traditional-approval news release; accessdata.fda.gov QALSODY/tofersen label (215887s000lbl).

**Biomedical class-grounding (EMET pass; basis for the 10 `emet-live` T2 cards):** EMET (BenchSci), Thorough
mode, 5 chats (see "EMET pass" table above) returning peer-reviewed PMIDs (PubMed) — e.g. Fitzgerald 2000
(10617681), Hofmann 2006 (16614540), Salloway 2022 (34807243), Honig 2024 (38730496), Benatar 2018 (30014505),
Miller 2022 (36129998), Hammad 2006 (16520440), Bridge 2007 (17440145), Schneider 2005 (16234500), Wang 2005
(16319382). URLs are `pubmed.ncbi.nlm.nih.gov/<pmid>/` (fetchable; gate-verified).

**Secondary, confirming the FDA action (basis for T2):** sponsor press releases (Acadia, Axsome,
BrainStorm, Lykos, Amylyx, BioArctic, Biogen, Eisai, Pfizer), Drugs.com FDA approval history,
BioPharma Dive, Pharmacy Times, HCPLive, NBC News, Psychiatric News, pharmaphorum, CGTLive,
Oligonucleotide Therapeutics Society. Canonical fda.gov DSC/guidance URLs are retained in cards even
where the page itself blocked WebFetch (see tiering note).

## Tiering note (honesty about verification)
**fda.gov, accessdata.fda.gov, federalregister.gov, and regulations.gov consistently blocked automated
`WebFetch`** (403/404/redirect-to-interstitial), though they **resolve in the Playwright browser** — which is
exactly why the **browser pass** (METHOD Step 3, Pass A) was added: it loads these primaries in a real browser
(or fetches the PDF bytes + `pdftotext`) and verifies a verbatim substring, upgrading 10 cards from T2 to T1
this pass. Per `dev/CONVENTIONS.md` §3 (provenance honesty) we still tier conservatively:
- **T1** only where a primary `.gov` archive or a primary-equivalent record was *directly fetched and
  read* (pemoline FR PDF; zolpidem via PMC; the guidance set verified against fetchable NIH/PMC/NCBI
  reproductions of the FDA text; eteplirsen via the FDA's verbatim announcement).
- **T2** where the anchor is a sponsor/secondary source quoting the FDA action (most CRLs, withdrawals,
  AdComm votes, and accelerated approvals). The underlying *action* is FDA-primary, but we did not
  directly fetch the FDA PDF, so we do not over-claim T1.
- **A follow-up pass with a browser-capable fetch can upgrade many T2 cards to T1** by re-anchoring to
  the Drugs@FDA review package / AdComm briefing doc / FDA press page (NDA/media identifiers noted in
  the originating research where known: tofersen NDA 215887 / media 186135; MDMA NDA 215455;
  eteplirsen NDA 206488).

## Known gaps — the ~30% the agent MUST still search live
1. **Parkinson's disease standalone FDA guidance** — not found/verified this pass; PD precedent here is
   only the pergolide withdrawal. Search live for PD disease-modification endpoint thinking.
2. **Epilepsy/pain AdComm votes** — no AdComm cards in these areas (covered only via guidance + withdrawal).
3. **Clinical holds beyond gene therapy** — both hold cards are AAV/neuromuscular. Holds on small-molecule
   or ASO CNS programs (e.g. tominersen/Huntington's ventricular-enlargement signal was found but **no
   verifiable FDA hold** — omitted, not fabricated) are a live-search gap.
4. **Non-US and pre-2004 precedent** — corpus skews 2004→2025; older landmark CRLs/withdrawals are thin.
5. **The actual FDA primary-document wording** for T2 cards (Drugs@FDA CRL text, AdComm transcripts) —
   blocked this pass; a veto built on a T2 card should be confirmed against the FDA primary before being
   raised as dispositive.
6. **Anything fresher than the retrieval window** (new CRLs/holds/AdComm votes after 2026-06-23) — always
   a live call.
7. **Program-specific mapping** — whether a *specific* Quiver program's flaw maps to a precedent is a
   runtime judgment; the corpus supplies the precedent, not the mapping.

## Omitted for lack of a verifiable source (NOT fabricated)
tegaserod (weak CNS relevance), methaqualone (DEA action, not FDA market-action of this type), rofecoxib
(deduped against Bextra), brexanolone/eteplirsen-as-CRL/Sarepta-SRP-9001-CRL (no verifiable CRL found),
tominersen clinical hold (safety signal real, FDA hold unverifiable), individual Vyondys/Amondys cards
(same surrogate precedent as eteplirsen — depth not method).
