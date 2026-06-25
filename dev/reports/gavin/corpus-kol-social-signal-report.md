# Report — corpus: kol-social-signal (Gavin, 4th of 6)

**Branch:** `gavin/corpus-kol-social-signal` · **Built-By:** gavin · **Date:** 2026-06-25
**Task:** `semantic-corpora` (Gavin 6) — 4th PR.
**Method:** `sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md` (FDA-memory worked example).

## What this PR adds
A dual-source, queryable knowledge corpus for the **KOL & Social Signal Monitor** (Bucket-1 semantic,
dossier field **F2** — KOL / expert sentiment):
- `sapphire-orchestrator/corpus/kol-social-signal/index.jsonl` — **6 claim-cards**
- `…/notes/` — 1 themed note · `…/manifest.md`, `…/QUERIES.md`
- Upgraded the skill doc `architecture/bucket1/semantic/kol-social-signal.md` → **corpus-first → search-the-gap**

## Tiering decision (read first)
The spec tiers **named-expert-on-record = T3**, **anonymous/social = T4**; the corpus gate accepts only **T1/T2**.
Resolution (consistent with financial-investor's T3→T2 mapping):
- **Pre-ingest only named-expert-on-record signals → mapped to T2**, each fully attributed + dated + cited to a durable PubMed URL.
- **Ephemeral social signal (spec T4: X.com, Substack, LinkedIn, podcasts) is intentionally NOT pre-ingested** — it isn't stably citable/verbatim-verifiable and changes daily. That is the agent's **live-harvest ~30%**.

**Tier split: 0 T1 / 6 T2 — by design** (expert opinion is inherently secondary; nothing here is a regulator/primary fact).

## Coverage (6 cards, breadth-of-method over depth)
Named-KOL on-record positions on the two dominant CNS sentiment debates:
- **Anti-amyloid skeptics:** Kurkinen (lecanemab "not the right drug"); Knopman & Perlmutter ("Meager Efficacy and Real Risks", aducanumab) — Knopman was on the FDA AdComm; Bauchner & Alexander ("Rejection of Aducanumab by the Health Care Community") — Alexander was on the FDA AdComm.
- **Muscarinic optimists:** Javitt ("Hope for Some, or Hope for All?", KarXT/Cobenfy — leading schizophrenia KOL, cautious-optimistic); Hasan & Abid (Cobenfy "a significant advancement" — named but **junior**, explicitly down-weighted per spec).
- **EMET validation (1 `emet-live` card):** the spec's load-bearing-claim hand-off, executed — validates Kurkinen's subgroup claim (PMID 41352683, Shim et al. meta-analysis, N=5633): subgroup heterogeneity is real (efficacy greatest in ApoE4 non-carriers; ARIA higher in ε4 carriers) **but** CLARITY AD was not powered for a sex×treatment interaction, so "no benefit in women" overreads an underpowered subgroup.

## Dual-source passes
- **Pass A (browser + PubMed MCP):** each card cites a real, resolving PMID with a **verbatim** quote — the editorial abstract where indexed, else the verbatim **editorial title** (the expert's on-record framing). Author standing noted (senior KOLs up-weighted, junior down-weighted).
- **Pass B (EMET):** 1 Thorough query validating a load-bearing KOL claim; PMID re-verified vs the PubMed abstract.
  - chat: `emet.benchsci.com/chat/ca0f85cd-cced-4634-bbf2-3ea50eb977a0`

## Gate
`bash dev/validate-corpus.sh sapphire-orchestrator/corpus/kol-social-signal` → **`✓ corpus validation CLEAN`**
(6 cards; schema + tier-domain ok; all PMIDs resolve). Verified in a **clean (no-User-Agent) environment** — no
latent 403s. Branch synced to current `main`; suite **478 green**.

## Honest gaps (the ~30% the agent MUST harvest live)
1. **Ephemeral social signal (the agent's core live job):** X.com high-signal accounts, Substack, podcasts, conference (ACNP/APA) reactions, LinkedIn — not pre-ingestable; harvest live, attribute, tier T4 in-flight.
2. **Pre-publication / preprint discussion** — EMET owns the preprints; this agent reads the *discussion*.
3. **Therapeutic breadth** — anti-amyloid + muscarinic only; psychedelics, ALS, PD, pain absent.
4. **Anything after the retrieval window** — sentiment moves fast; always a live call.

## Omitted for lack of a stable primary this pass (NOT fabricated)
The famous FDA AdComm *resignation* quotes (e.g., "worst approval decision…") are widely reported but the
primary (resignation letter / news interview) isn't stably citable; the *published* critiques by the same
experts (Knopman, Alexander) are carded instead. CLARITY AD sex-subgroup exact CIs live in the trial supplement
(not the PubMed abstract) — described, not quoted-as-abstract.

## Anti-fabrication
Every quote is a verbatim substring of the PubMed record (title or abstract) or an abstract-verified EMET
synthesis. No invented PMIDs, dates, or quotes. Public identifiers only. Junior-author sentiment is flagged
and down-weighted, never presented as senior-KOL authority.
