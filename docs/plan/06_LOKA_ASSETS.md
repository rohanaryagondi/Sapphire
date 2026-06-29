# 06 — Loka reusable assets (what we mined from the repo)

> Source: `q-state-biosciences/drug-discovery-agent` (local: `/Users/rohanaryagondi/Desktop/Projects/Quiver/drug-discovery-agent`),
> mined 2026-06-28. Decision D8 stands: **we do not build on Loka's code** — we adopt its **data scoring**
> and **patterns**. The headline below is a real, concrete fix for our moat.

## Headline — the rescue/similar scoring (and why ours is wrong)
**There is NO weighted multi-factor formula (no 40/30/30).** Loka's ranking is **pure distance-rank**, but
with three steps our `moat_facts` currently skips:
1. **Directionality at ingest** (`docs/PERTURBATION_DATA.md:69-76`): `match_effect` is derived from
   `query_perturbationDirection` — `Original → 'similar'` (mimic), **`Antipodal → 'opposite'` (rescue)**.
   Rescue = the Antipodal rows. (This is why "rapamycin rescues TSC2" works for Loka.)
2. **Partition + dual within-partition rank** (`docs/PERTURBATION_DATA.md:250-286`): partition by
   `(query_perturbation, match_effect)`; compute `rank_cosine` (cosine asc, euclidean tiebreak) AND
   `rank_euclidean` (euclidean asc, cosine tiebreak) **within each partition**.
3. **Union-rank ordering** (`src/tools/perturbation_search.py:201-208`): keep rows where
   `rank_cosine <= N OR rank_euclidean <= N`, order by **`(rank_cosine + rank_euclidean) ASC`**.
   Global/multi-gene queries add `best_rank = MIN(LEAST(rank_cosine, rank_euclidean))` +
   `supporting_genes = COUNT(DISTINCT query_perturbation)` (`src/tools/global_ranking.py:106-130`).

**Our gap:** `sapphire-orchestrator/moat/` reads the raw parquet and computes EP-antipodal distance directly
— it does **not** partition by `(query, match_effect)`, does **not** compute the two within-partition ranks,
and may not filter on `Antipodal` correctly. **The fix = replicate the materialized-view logic** (→ WO-5 /
`dev/work-orders/WO-5-moat-rescue-fix.md`).

## Reuse table (condensed)
| Asset | File | Decision |
|---|---|---|
| Partition + dual-rank + union-rank scoring | `docs/PERTURBATION_DATA.md:250-286`, `src/tools/perturbation_search.py:201-208` | **ADOPT** → moat (WO-5) |
| `match_effect` from `query_perturbationDirection` (Antipodal=rescue) | `docs/PERTURBATION_DATA.md:69-76` | **ADOPT** → moat (WO-5) |
| `best_rank` + `supporting_genes` (multi-gene support) | `src/tools/global_ranking.py:111-129` | **ADOPT** → enrich `moat_facts` |
| 30 TSC/mTOR NL eval questions | `notebooks/eval_questions.json` | **ADOPT** → `sapphire-orchestrator/scenarios/` |
| 4-type query taxonomy (gene/drug × gene/drug) + Phase-5 source-attribution (`[Quiver]/[Public]/[Inference]`) | `src/prompts/system` | **REFERENCE** → synthesis + research-manager specs |
| DisGeNET gene–disease tool (score + PMID count) | `src/tools/disgenet.py` | **REFERENCE** → optional semantic source (EMET already supersets most) |
| 150k token sliding-window trim | `src/agent/chatbot.py:35-57` | **REFERENCE** → per-persona context budgeting |
| Bedrock toolSpec / ToolRegistry / Think / RespondMessage / DataFrame scratchpad / Chainlit elements | `src/tools/*`, `public/elements.example/` | **IGNORE (D8)** — our harness + consoles supersede |

## Top 3 to port (each → a Sapphire file)
1. **Moat rescue fix** — replicate partition + dual-rank + Antipodal filtering in `sapphire-orchestrator/moat/`
   (+ the SQLite build). The single highest-value port. → **WO-5**.
2. **`supporting_genes`** in `moat_facts` output — surfaces multi-target rescue vs single-gene artifact.
3. **Synthesis taxonomy + source-attribution labels** — into the synthesis + research-manager specs under
   `architecture/orchestrator/`. (Reference-only; tighten our prompts.)

## ⚠️ Security
The Loka shared-folder `.env` has live secrets — never commit. The repo itself: scan before reusing any
config. Our scanners now cover the BenchSci key prefix (PR #110).
