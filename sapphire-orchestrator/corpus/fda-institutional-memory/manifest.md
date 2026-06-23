# Manifest — FDA Institutional Memory corpus

**Agent:** FDA Institutional Memory ⛔ (Bucket 1, semantic, veto-class) · dossier fields **C3** (veto) / **D2** (precedent).
**Built:** pilot, this branch (`rohan/corpus-pilot-fda-memory`).
**Retrieval window:** 2026-06-22 → 2026-06-23. Sources were retrieved/verified in this window, but **not every URL is fetchable**: primary regulatory domains (fda.gov, federalregister.gov, accessdata.fda.gov, regulations.gov) frequently block automated fetch. Cards that rely on such a page are tagged `unverifiable_by_fetch` and/or tiered **T2**; the underlying regulatory *action* in those cards was cross-confirmed via independent reputable sources (PMC/NCBI reproductions, sponsor releases, trade press).
**Cards:** 35 in `index.jsonl` · **Notes:** 5 themed files in `notes/`.
**Scope:** representative CNS-relevant slice exercising every check type — NOT exhaustive (pilot). Breadth-of-method over depth.

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
| **total** | **35** |

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

**Secondary, confirming the FDA action (basis for T2):** sponsor press releases (Acadia, Axsome,
BrainStorm, Lykos, Amylyx, BioArctic, Biogen, Eisai, Pfizer), Drugs.com FDA approval history,
BioPharma Dive, Pharmacy Times, HCPLive, NBC News, Psychiatric News, pharmaphorum, CGTLive,
Oligonucleotide Therapeutics Society. Canonical fda.gov DSC/guidance URLs are retained in cards even
where the page itself blocked WebFetch (see tiering note).

## Tiering note (honesty about verification)
**fda.gov, accessdata.fda.gov, federalregister.gov, and regulations.gov consistently blocked automated
WebFetch** (403/404/redirect-to-interstitial) during the retrieval window, though they resolve in a
browser. Per `dev/CONVENTIONS.md` §3 (provenance honesty) we therefore tier conservatively:
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
