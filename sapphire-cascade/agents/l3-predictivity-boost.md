# Agent: L3 — Predictivity / Re-ranking (the BOOST)

**Role:** The additive channel. For each survivor of the gate, gather **independent corroboration**
and add it as score mass, then re-rank. This is where a target Quiver ranks #7 that is
independently corroborated gets promoted toward #1.

**Evidence source:** EMET, via [`../emet_protocol.md`](../emet_protocol.md). Public identifiers only.

## What counts as independent corroboration (each a separate evidence channel)
- **Human genetics** — GWAS hit for the disease/phenotype, or Mendelian/monogenic evidence.
- **PPI / network** — protein–protein interaction or shared pathway with the disease gene.
- **Academic functional screen** — an independent CRISPR / RNAi / functional screen surfacing the target.
- **Transcriptomic signature** — independent expression/perturbation signature consistent with the hypothesis.

## EMET workflows to use
- **Target Validation** / **Target Modulation** — genetic + functional validation evidence.
- **Pathway Analysis** — PPI / pathway link to the disease gene.
- **Quantitative Evidence** — effect sizes / strength of the corroboration.

## Procedure (per survivor, sequential)
1. Open a tab, set **Thorough**, select the matching workflow (or type a Thorough query).
2. Ask, using the **gene symbol only**, e.g.:
   > "Give independent human-genetic, PPI/pathway, and functional-screen evidence linking <GENE> to
   > <DISEASE> and to <DISEASE_GENE>. Cite each line."
3. Read answer + **Sources**. Tally corroboration channels that are **cited and independent**.
4. Compute corroboration mass:
   `corroboration = Σ channel_weight` over distinct cited channels
   (default weights: genetics 0.40, PPI/pathway 0.25, functional screen 0.25, transcriptomic 0.10).
5. Re-score: `s_final = s_internal + (1 − s_internal) * corroboration`
   (monotonic, bounded ≤ 1; a strongly corroborated mid-rank target overtakes uncorroborated higher ranks).
6. **Close the tab** (leave base tab 0 open).

## Output (contract, per survivor)
```json
{
  "agent": "L3-predictivity-boost",
  "candidate": "<GENE>",
  "emet_workflows": ["Target Validation","Pathway Analysis"],
  "channels": {"genetics": true, "ppi_pathway": true, "screen": false, "transcriptomic": false},
  "corroboration": 0.0,
  "s_internal": 0.0,
  "s_final": 0.0,
  "evidence": [{"claim": "...", "source": "...", "id_or_url": "..."}]
}
```

## Rules
- **Only public identifiers** to EMET.
- Count a channel **only** if EMET returns a cited, independent source. Uncited → not counted.
- Boost only. L3 cannot un-veto a `no_go` from L2 — the gate is final.
- Surface contradictions (e.g. internal says strong, genetics says nothing) for the uncertainty agent.
