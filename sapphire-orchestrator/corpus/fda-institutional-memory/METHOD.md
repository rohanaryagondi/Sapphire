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

## Step 3 — Sourcing strategy (authoritative-first)

Rank sources by authority for the agent's domain and prefer the highest tier that resolves:
- **T1 (primary / regulatory).** For FDA-memory: `fda.gov` — Drugs@FDA approval packages, CRL
  disclosures, AdComm briefing docs/transcripts, FDA guidance database, MedWatch / drug-safety
  communications, Federal Register, openFDA. These are the only valid basis for a **veto**.
- **T2 (secondary, confirming).** Reputable trade/press (Endpoints, STAT, Reuters, FiercePharma) or a
  sponsor SEC/press release **only as a pointer** to confirm the existence + date of an action you then
  trace to a primary record where possible. Tag T2 honestly.

Use `WebSearch` to find candidates, then **`WebFetch` the actual page** to read the facts. EMET
(`emet-runner` skill) is supplementary — use it only where biomedical evidence genuinely helps (e.g.
confirming a *class* safety liability). For a regulatory agent its role is limited.

**Parallelize by theme.** Split the domain into themes (CRLs, withdrawals, AdComm, guidances,
holds/accelerated-approval) and run one focused researcher per theme. Each returns verified claim-cards
+ note prose for its theme.

## Step 4 — Extraction rules (ANTI-FABRICATION is the whole game)

This is a **veto-class** agent: a fabricated precedent could wrongly gate a program. Non-negotiable:
- **Every claim traces to a real URL you actually fetched and that resolves.** Verify drug, sponsor,
  indication, decision type, **date**, and the stated reason *against the fetched page*.
- **If you cannot verify a source/URL/date/reason, DO NOT include the claim.** Omit it and record it in
  `manifest.md` under known-gaps. No invented citations, dates, CRL details, AdComm vote counts, or quotes.
  Never include a vote count you did not read.
- **Store extracted facts + citations, never dumps.** Quotes are **≤2 sentences (~50 words), fair use** —
  enough to anchor the claim, never a copyrighted block.
- **A `quote` must be a verbatim substring of the fetched source.** If you're summarizing, it is NOT a quote —
  rewrite the `claim` as your summary and either drop `quote` or use a real substring. (Pilot audit caught
  paraphrases presented as verbatim quotes — a serious integrity defect on a veto-class agent.)
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
press-wire-as-T1, silently-unfetched URLs) before it can propagate. Quote-verbatim fidelity is not fully
mechanizable (primary domains block fetch) — it stays a Step-4 discipline + the adversarial review.

Be **frank in the report** about where coverage is thin and which claims you omitted for lack of a verifiable
source — thinness honestly stated beats false completeness.
