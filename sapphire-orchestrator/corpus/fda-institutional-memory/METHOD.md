# METHOD — How to build a Bucket-1 agent knowledge corpus

This is the **repeatable recipe** used to build the FDA Institutional Memory corpus (the pilot). It is
written so another contributor (Hayes/Gavin) can replicate it for any of the other 12 semantic agents
*without re-deriving the approach*. Follow the six steps in order.

> **Principle.** Pre-ingest the **stable ~70%** of an agent's domain knowledge into a local, queryable
> corpus so a run hits local first; spend a live web/EMET call only on the **novel ~30%**. Cheaper, faster,
> grounded — and every claim is traceable.

---

## Step 1 — Read the agent's spec, derive its *lens* and *check types*

Open `architecture/bucket1/semantic/<agent>.md`. Extract, in this order:
- **Purpose / one-liner** — what decision the agent informs, and whether it is **veto-class**.
- **Activate-when** — which dossier field(s) it fills (for FDA-memory: **C3** veto, **D2** precedent).
- **Procedure → check types** — the discrete questions the agent asks at runtime. These become your
  **coverage map**. For FDA-memory the check types are: frame a *flaw hypothesis* → look for matching
  FDA precedent → classify each hit as `precedent` (informative) vs **`veto`** (dispositive prior
  rejection of the *same* flaw). The decision categories that follow: CRL, withdrawal/market action,
  AdComm vote, clinical hold, accelerated/surrogate approval, guidance/endpoint precedent.
- **Output contract + Rules** — what fields the agent must emit, the tiering scheme (here **T1** =
  regulatory/primary, **T2** = secondary), and the hard rules (veto is a *gate not a kill*; facts only;
  a veto needs a T1 citation; public identifiers only).

The lens is literally "what fields would let this agent answer its checks." Write them down before you
search — they define the claim-card schema in Step 2 and the coverage map in Step 5.

## Step 2 — Define the claim-card schema (the lens), one JSON object per line

`index.jsonl` is the machine-queryable core: **one claim-card per line, valid JSON**. The schema is the
agent's lens turned into fields. For FDA-memory:

```json
{"claim":"<one-sentence statement of the precedent>","drug":"<name or '-'>","sponsor":"<name>","indication":"<CNS indication>","decision":"approval|CRL|withdrawal|adcomm_vote|clinical_hold|guidance|safety_action","date":"YYYY-MM","reason":"<documented rationale>","precedent_implication":"<what a program carrying this flaw must therefore expect/show>","source":"<agency/publication>","url":"<verified URL>","quote":"<=2 sentences, fair use","tier":"T1|T2"}
```

For a different agent, swap the domain fields (e.g. Clinical-Trial-Registry would use `trial_id`,
`phase`, `status`, `amendment`, `termination_reason`), but keep the invariant fields: `claim`,
`date`, `reason`/implication, `source`, `url`, `quote`, `tier`. **`precedent_implication` is the
value-add** — it pre-computes the "so what" the agent would otherwise reason out at runtime.

## Step 3 — Sourcing strategy (authoritative-first): two STANDARD ingestion passes

Every agent's build runs **both** passes below — they are not optional. They produce two complementary,
honestly-tiered source streams. Rank by authority and prefer the highest tier that resolves.

### Pass A — the **browser pass** (FDA-primary → T1)
Drive the **shared Playwright browser** (`browser_navigate` to the primary URL, then `browser_evaluate`
returning `document.querySelector('main')?.innerText`/`document.body.innerText`; for PDFs, fetch the bytes
and `pdftotext`) to open the **actual primary document** and verify a **verbatim** supporting substring:
- **T1 (primary / regulatory).** For FDA-memory: `fda.gov` (drug-safety communications, news releases,
  AdComm meeting **summary** docs + decision memos under `fda.gov/media/<id>/download`), `accessdata.fda.gov`
  (Drugs@FDA labels/reviews), `federalregister.gov`, `govinfo.gov`. **T1 requires that you actually loaded
  the primary AND found verbatim support.** These are the only valid basis for a **veto**.
- If a primary genuinely won't render (some Akamai-fronted PDFs, image-only scans), keep the card **T2** (or
  tag `"unverifiable_by_fetch": true` honestly) — never claim a T1 you did not fetch. A wrong/dead URL (404)
  is a hard failure, repoint it.
- The browser pass is what **upgrades T2 → T1**: re-anchor a sponsor/press-confirmed action to its
  Drugs@FDA review / AdComm summary / FDA press page, replace the `quote` with a verbatim substring of the
  fetched primary, set `tier:"T1"`, and drop any `unverifiable_by_fetch`.

### Pass B — the **EMET pass** (biomedical class-grounding → T2, `emet-live`)
Drive **EMET (BenchSci)** live per `sapphire-cascade/emet_protocol.md` (open your own tab at
`emet.benchsci.com`, set thinking level **Thorough**, type into the TipTap input, **submit with the
`.lucide-arrow-up` send button — Enter does NOT submit**, wait for the slow agentic run, read the inline
PMID citations + the Sources panel, capture the `chat_url`). Public identifiers only ever go to EMET; if a
login wall (`id.summit.benchsci.com`) appears, STOP and report `login_required` — never log in.
- EMET adds the **cited biomedical basis** *behind* the regulatory record — the C1–C2 class-liability /
  biomarker mechanism that explains *why* the FDA acted (e.g. 5-HT2B agonism → valvulopathy behind the
  pergolide withdrawal; ARIA behind the amyloid-mAb scrutiny; NfL behind tofersen's surrogate approval).
- EMET cards are **T2**, `source:"EMET (BenchSci)"`, `provenance:"emet-live"`, `emet_chat_url:"<uuid url>"`,
  and `url` set to the **PMID/PMC/DOI** the answer returned (`pubmed.ncbi.nlm.nih.gov/<pmid>/` — fetchable,
  so the gate verifies liveness). `quote` is a **verbatim substring of the EMET answer** (≤2 sentences).
  **Only real PMIDs EMET actually returned** — if a query returns nothing citable, record it as a gap in
  the manifest; never invent a PMID.
- **EMET's contribution varies by agent.** For this regulatory agent it is *limited* (a supporting layer
  behind the regulatory facts). For **post-market-safety, clinical-trial-registry, target-validation**
  agents it is *central*. Run it regardless; let the yield be honest.

Use `WebSearch` to find primary-document candidates (then verify in the browser). **Parallelize by theme**
for the browser pass (CRLs, withdrawals, AdComm, guidances, holds/accelerated-approval — one researcher
per theme); run the EMET pass as a focused set of ~5 Thorough queries on the domain's key class-mechanisms.

## Step 4 — Extraction rules (ANTI-FABRICATION is the whole game)

This is a **veto-class** agent: a fabricated precedent could wrongly gate a program. Non-negotiable:
- **Every claim traces to a real URL you actually fetched and that resolves.** Verify drug, sponsor,
  indication, decision type, **date**, and the stated reason *against the fetched page*.
- **If you cannot verify a source/URL/date/reason, DO NOT include the claim.** Omit it and record it in
  `manifest.md` under known-gaps. No invented citations, dates, CRL details, AdComm vote counts, or quotes.
  Never include a vote count you did not read.
- **Store extracted facts + citations, never dumps.** Quotes are **≤2 sentences (~50 words), fair use** —
  enough to anchor the claim, never a copyrighted block.
- **Quote fidelity differs by source type — be precise about which you're producing:**
  - **Browser/web cards (T1 + secondary T2):** the `quote` MUST be a **verbatim substring** of the fetched
    page. If you're summarizing, it is NOT a quote — put the summary in `claim` and either drop `quote` or use
    a real substring. (Pilot audit caught paraphrases passed as verbatim quotes — a serious integrity defect.)
  - **EMET cards (`provenance:"emet-live"`):** the `quote` is a **synthesized, EMET-grounded statement**, not
    necessarily a verbatim string from the cited PMID abstract — but it **must be faithful to and not overstate
    the cited evidence**: verify every number against the PMID's abstract and label genotypes/subgroups exactly
    as the source does (the pilot's EMET audit caught a "carriers" figure mislabeled "heterozygotes" and a
    fold-estimate above the cited OR). The PMID `url` is what's independently verifiable; the quote is your
    faithful synthesis of the EMET answer.
- **`url` must resolve to the page that supports the claim.** If the correct primary URL is blocked/un-fetchable
  (e.g. `fda.gov`/`federalregister.gov` often block automated fetch), set **`"unverifiable_by_fetch": true`** on
  the card — never leave a URL you couldn't actually open without flagging it. A wrong/dead URL (404) is a hard
  failure, not an "unverifiable" — repoint it.
- **`tier` T1 requires a primary domain** (`*.gov` / `*.edu` / PMC / NCBI). A press-wire or sponsor page that
  merely reproduces FDA text is **T2**, even if the text is verbatim.
- **Public identifiers only** (drug names, gene symbols, indications, SMILES, PMIDs). Never any
  Quiver-internal data.
- **Provenance honesty** (`dev/CONVENTIONS.md` §3): T1 vs T2 reflects the *actual* source you read.

## Step 5 — Organize: notes + index + manifest + queries

- **`notes/*.md`** — themed human-readable knowledge-notes (one file per theme). Every claim **inline-cited
  + dated**. These are what a human/agent reads for context.
- **`index.jsonl`** — the queryable claim-cards (Step 2). One JSON object per line. This is what the agent
  greps/loads at runtime.
- **`manifest.md`** — the source list; the **coverage map** (which agent check types the corpus covers,
  with counts); the **retrieval date**; and the explicit **known-gaps** list (the ~30% the agent must
  still search live).
- **`QUERIES.md`** — take ~6 realistic checks the agent would run and answer each **from the corpus**,
  pointing at the claim-card(s)/note. For checks the corpus can't answer, say so explicitly — that *is*
  the demonstrated gap, and proves the corpus-first → search-the-gap design.

## Step 6 — The quality bar (self-check before reporting)

1. Corpus covers the agent's common check types (coverage map present; gaps honest).
2. Every claim cited + dated + short quote + tier + lens fields; **zero fabrication**; public-only; URLs verified.
3. Organized: themed notes + valid (parseable) `index.jsonl` + real manifest.
4. `QUERIES.md` demonstrates real checks answered from the corpus + explicit gaps.
5. `METHOD.md` (this file) is a clean repeatable recipe.
6. The skill doc is upgraded to **corpus-first → search-the-gap**.

**Run the mechanical gate — it must pass before the PR:**
```
bash dev/validate-corpus.sh sapphire-orchestrator/corpus/<agent>/
```
It enforces, deterministically: valid JSON + invariant fields + quote ≤60 words; **tier T1 only on a primary
domain** (.gov/.edu/PMC/NCBI); and **every `url` resolves** (a 404/4xx is a hard fail; a 403/timeout is a fail
*unless* the card is tagged `"unverifiable_by_fetch": true`). This catches the pilot's defect class (dead URLs,
press-wire-as-T1, silently-unfetched URLs) before it can propagate. **EMET cards** (Pass B) pass cleanly: they
are **T2** (so the T1-domain rule does not apply) citing a `pubmed.ncbi.nlm.nih.gov/<pmid>/` URL (which resolves
2xx), and the extra `provenance`/`emet_chat_url` fields are additive — the invariant-field check is a subset
test, so extra fields never break it. Do **not** weaken the gate to admit EMET cards; they already conform. Quote-verbatim fidelity is not fully
mechanizable (primary domains block fetch) — it stays a Step-4 discipline + the adversarial review.

Be **frank in the report** about where coverage is thin and which claims you omitted for lack of a verifiable
source — thinness honestly stated beats false completeness.
