# WO-6 — Semantic agents: pilot-slice → production-grade (corpus + API + spec, per agent)

**For:** Rohan Claude (worker) · **Branch:** `rohan/semantic-agents` cut from `main` (per-phase sub-branches OK).
**Lifecycle:** `/sapphire-build` (plan→implement→review→verify→ship) **per agent** — each agent is its own small,
independently-shippable change. **Blocked? →** `dev/HELP.md`. **Depends on:** nothing (the 13 already dispatch).
**Priority: high** — these are the firm's intelligence breadth, and several are currently broken or ungrounded.

## Goal
Take all **13 Bucket-1 semantic agents** from CNS pilot-slices to **production-grade**, improving **all three
dimensions per agent**: **(1) corpus** (deep, cited grounding), **(2) sources/APIs** (a real dedicated source,
not just WebSearch), **(3) spec** (a sharp prompt: what it hunts for + a tight output contract). Do a focused
**starting cluster** first (the scientific/safety-diligence agents), prove the per-agent template, then sweep
the rest. Every fact stays cited, tiered, provenance-stamped; honest-abstain over fabrication; public
identifiers only.

## Where we are now (verified on `main`, 2026-06-29)
All 13 dispatch live (`live_engine._BUCKET1_AGENTS`). Each is a `claude -p` subagent + WebSearch running the
**corpus-first → search-the-gap (K2)** pattern: `read_corpus(id, query, ents)` surfaces cited cards as
`provenance="corpus"` T2 facts AND feeds `corpus_hits` into the prompt so the live web call only fills the gap.
**Grounding is the differentiator — and it's uneven:**
- ✅ **Corpus + real API** — `clinical-trial-registry` (CT.gov v2), `post-market-safety` (openFDA), `fda-institutional-memory` (45 cards, the template).
- ✅ **Corpus only, thin** — `global-regulatory-divergence` (9), `patent-ip` (7), `dea-scheduling` (9), `patient-advocacy` (5), `policy-legislative` (6).
- 🐛 **Corpus silently disabled (ID mismatch)** — `financial`↔`corpus/financial-investor/`, `kol-social`↔`corpus/kol-social-signal/`, `reputational`↔`corpus/reputational-institutional/`. `has_corpus(id)` never matches → K2 skipped.
- ❌ **No corpus** — `payer`, `manufacturing-cmc` → pure web-search → the **180s `claude -p` timeouts** seen in the live run.
- 📉 Corpora are CNS pilot slices (4–45 cards); the **EMET "Pass B"** biomedical-mechanism grounding layer was only completed for `fda-institutional-memory` + `financial-investor`.

`fda-institutional-memory` is the **gold standard** — dual-pass (browser FDA-primary + EMET biomedical), 45
cited cards, corpus-first spec, veto logic. **Every agent's target is its own version of that.**

## The per-agent definition of "production-grade" (the template)
For an agent to be DONE under this WO, all three hold:
1. **Corpus** — a real, deep, cited corpus at `corpus/<id>/index.jsonl` (id matches the registry id), broader
   than the CNS pilot, each card tiered (T1 primary / T2 secondary) with a real source URL, dual-pass where
   scientific (the EMET biomedical-mechanism Pass B), and it loads via K2 (verify `has_corpus(id)` → True and
   `read_corpus` returns cards for a representative query).
2. **Source/API** — a dedicated real source wired (see the per-agent map below), preferred over open WebSearch
   for the primary record; WebSearch only surfaces *candidates*, the primary is fetched from the real source.
   Honest-abstain (KNOWN_UNKNOWN) when the source is unavailable — never fabricate.
3. **Spec** — the `architecture/bucket1/semantic/<id>.md` spec sharpened: a crisp "what it hunts for", the
   tiering rule, the output contract, and the corpus-first instruction. The `claude -p` prompt is built from
   this spec; a sharper spec = sharper facts.

## Phase 0 — Structural fixes (do FIRST; fast; unblocks everyone)
1. **Fix the 3 corpus ID mismatches.** Either rename the dirs (`financial-investor`→`financial`,
   `kol-social-signal`→`kol-social`, `reputational-institutional`→`reputational`) **or** add an explicit
   id→dir alias map in `sapphire-orchestrator/corpus/__init__.py` (`has_corpus`/`read_corpus`). Prefer rename
   (simpler, no indirection) unless the dir name is referenced elsewhere. Add a test that `has_corpus(id)` is
   True for all 11 agents that have a corpus dir.
2. **Build corpora for the 2 ungrounded agents** (`payer`, `manufacturing-cmc`) — even a small first slice
   (per their specs' sources) gives K2 something to load and cuts the live web call. Mirror the existing
   corpus build method (`_build/` corpus ingestion + the dual-pass pattern).
3. **Add a guard test** asserting every id in `_BUCKET1_AGENTS` that has a corpus dir actually loads it, so a
   future mismatch can't regress silently.

**Phase 0 DoD:** all 13 agents that have a corpus load it via K2 (no silent skips); `payer` + `manufacturing-cmc`
have a first corpus; the guard test is green; suite green.

## Phase 1 — the starting cluster (the scientific/safety-diligence agents)
Do the **full 3-dimension treatment** for these first (highest scientific value; two already have real APIs):
**`clinical-trial-registry`, `post-market-safety`, `global-regulatory-divergence`, `patent-ip`**, using
**`fda-institutional-memory` as the reference template** (don't rebuild it; deepen if cheap). One agent per
`/sapphire-build` cycle, each shipped independently.

## Per-agent map (all 13 — the real source to wire + corpus target)
| Agent | Dedicated real source/API to wire (primary) | Corpus deepening target | Spec note |
|---|---|---|---|
| fda-institutional-memory | Drugs@FDA / accessdata.fda.gov, Federal Register, AdComm transcripts | template (45) — broaden beyond CNS only if cheap | gold standard — keep as reference |
| clinical-trial-registry | **ClinicalTrials.gov v2 REST API** (wired) + WHO ICTRP, EUCTR | add EMET Pass B (mechanism lit); deepen beyond 12 | amendments/termination as signals |
| post-market-safety | **openFDA** FAERS + labels (wired) + EMA, WHO VigiAccess (ex-US gap) | add ex-US PV; EMET Pass B; deepen beyond 8 | class-level safety, not single-drug |
| global-regulatory-divergence | **EMA medicines API**, MHRA (gov.uk), NICE, HTA bodies | deepen beyond AD/DMD slice; raise T1 count | ex-FDA decisions FDA hasn't acted on |
| patent-ip | **USPTO PatentsView API** / Google Patents + **Orange Book + Purple Book** (exclusivity gap) | deepen beyond 7; add exclusivity cards; EMET Pass B | FTO + veto on in-force blocker |
| dea-scheduling | **govinfo.gov API** (DEA Federal Register), 21 CFR 1308 | dispatched ✓; deepen beyond 9; EMET Pass B | scheduling trajectory for class |
| financial | **SEC EDGAR full-text + filings API** (8-K/10-K), earnings | fix mismatch (P0); deepen beyond 6 | asset-class pricing signals |
| payer | **ICER** reports, **NICE TAs**, **CMS NCD/LCD API**, G-BA, PBAC | build corpus (P0); then deepen | coverage + price, not approval |
| manufacturing-cmc | **FDA Warning Letters + 483 dashboards/API**, DMF index | build corpus (P0); then deepen | CMC manufacturability liabilities |
| patient-advocacy | FDA PFDD transcripts, advocacy org sites, **ProPublica Nonprofit (IRS 990) API** | deepen beyond 5; EMET Pass B | advocacy influence on benefit-risk |
| kol-social | PubMed (named-KOL editorials) + X/Substack/LinkedIn (live, ephemeral T4) | fix mismatch (P0); deepen beyond 6 | pre-publication signal is the value |
| policy-legislative | **congress.gov API**, CMS.gov, KFF (congress.gov Cloudflare gap) | deepen beyond 6; add EU/state | power signals, not policy text |
| reputational | oversight.house.gov, SEC, **Retraction Watch / PubPeer**, journal retractions | fix mismatch (P0); deepen beyond 4 (amyloid-only) | press/institutional perception |

## Phase 2+ — sweep the rest
After Phase 1 proves the template, do the remaining 8 (commercial/stakeholder cluster) the same way — one agent
per cycle, all three dimensions, independently shipped. Order by value: `financial`, `dea-scheduling`,
`payer`, `manufacturing-cmc`, `patient-advocacy`, `policy-legislative`, `kol-social`, `reputational`.

## Per-agent DoD (each agent is DONE when)
- Corpus loads via K2 (`has_corpus(id)`=True, `read_corpus` returns ≥N cited cards for a representative query),
  each card tiered + real source URL; EMET Pass B done where the agent is scientific.
- The dedicated real source/API is wired + **live-tested** (a real call returns real records), with honest
  KNOWN_UNKNOWN abstain when it's down.
- The spec is sharpened; the agent produces **≥ a target number of real cited facts** on a representative
  query (not abstain), and **abstains honestly** on an out-of-scope query (no fabrication).
- Data boundary intact (public identifiers only; no internal scores leave); provenance stamped; traced.

## Gates (per agent)
Full suite green · independent review (different agent) · provenance + no secrets (API keys in gitignored env
only) · stdlib-engine boundary (heavy/HTTP deps in the seam/subprocess or `_build/`, not the engine) ·
**Gate 5: actually run the agent live on a representative CNS query and confirm it returns real cited facts
from the real source + loads its corpus; and confirm honest-abstain on an out-of-scope query.**

## Notes
- **`fda-institutional-memory` is the worked example** — read its spec + corpus build before starting any agent.
- Keep the corpus-build deps (HTTP/API clients) out of the stdlib engine — in `_build/` ingestion or the seam.
- **Performance is partly a grounding problem:** a deeper corpus shrinks the live web call. A separate perf WO
  should raise/parallelize the 180s `claude -p` timeout, but corpus depth is the first lever — do it here.
- Don't break the demo/replay path or the existing corpora that work; the 8 matched corpora are real assets.
