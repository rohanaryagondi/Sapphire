# WO-5 — Moat rescue-ranking fix (port Loka's scoring) · bonus, parallelizable

**For:** Rohan Claude (worker) · **Branch:** `rohan/moat-rescue-fix` cut from `main` · **Plan:** [`docs/plan/06_LOKA_ASSETS.md`](../../docs/plan/06_LOKA_ASSETS.md)
**Lifecycle:** `/sapphire-build`. **Blocked? →** `dev/HELP.md`. **Depends on:** nothing — independent of WO-2/3/4, run in parallel.
**Priority: high value, low cost** — fixes the known caveat that our raw EP-antipodal distance doesn't reproduce Loka's "rapamycin rescues TSC2".

## Goal
Make `sapphire-orchestrator/moat/` reproduce Loka's rescue/similar ranking by replicating its scoring (which
is **pure distance-rank**, not a 40/30/30 formula). Reference: the Loka repo at
`/Users/rohanaryagondi/Desktop/Projects/Quiver/drug-discovery-agent`.

## The fix (exact, from the mine)
Today `moat_facts` reads the raw parquet and computes EP-antipodal distance directly — missing three steps:
1. **Direction → match_effect** (`docs/PERTURBATION_DATA.md:69-76`): `query_perturbationDirection`
   `Original → 'similar'` (mimic), **`Antipodal → 'opposite'` (rescue)**. Filter rescue queries to Antipodal.
2. **Partition + dual within-partition rank** (`docs/PERTURBATION_DATA.md:250-286`): partition by
   `(query_perturbation, match_effect)`; compute `rank_cosine` (cosine asc, euclidean tiebreak) and
   `rank_euclidean` (euclidean asc, cosine tiebreak) **within each partition**.
3. **Union-rank ordering** (`src/tools/perturbation_search.py:201-208`): keep `rank_cosine <= N OR
   rank_euclidean <= N`, order by **`(rank_cosine + rank_euclidean) ASC`**; keep top-K **per ref_type**
   (genes + compounds separately). Multi-gene queries: `best_rank = MIN(LEAST(rank_cosine, rank_euclidean))`
   + `supporting_genes = COUNT(DISTINCT query_perturbation)` (`src/tools/global_ranking.py:106-130`).

## Steps
1. Implement the partition + dual-rank + Antipodal filtering — preferably **precompute the ranks when building
   `RohanOnly/moat/moat.sqlite`** (`_build/build_moat_db.py`) so lookups stay fast, mirroring Loka's
   materialized view; `MoatClient` then reads the ranked table.
2. Add `supporting_genes` to the `moat_facts` output (enriches what the Internal Science Lead sees).
3. Keep `provenance: "moat-real"`; keep honest degradation to `[]`/mock when the SQLite is absent.

## DoD
**`TSC2` rescue query surfaces rapamycin/Sirolimus/Everolimus in the top results** (the correctness check that
fails today); genes + compounds both represented (per-type top-K); `supporting_genes` present; moat tests
green; **data boundary intact — the internal cosine/euclidean distances are used in reasoning/report ONLY,
never sent to any external tool.**

## Gates
Suite green · independent review · provenance + no secrets · **data-boundary check (the headline risk here)** ·
Gate 5: run a `TSC2` rescue query through `run_live` and confirm rapamycin appears.
