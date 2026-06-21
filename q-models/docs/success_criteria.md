# Success Criteria

Empirical bar for each test in the exploration plan. "Pass" = MAMMAL is at least useful. "Strong pass" = MAMMAL is genuinely valuable. "Fail" = the test invalidates the claim and we should stop.

## Per-test grid

| Test | Pass | Strong pass | Fail |
|---|---|---|---|
| **Phase 1 — Jernabix → Nav1.8** | Predicted affinity is higher than for an unrelated random drug-target pair | Predicted affinity matches known KD within an order of magnitude | Predictions are noise / inverted (real binders score same or lower than random pairs) |
| **Phase 1 — 5–10 known drug-target pairs** | Spearman correlation > 0.4 between predicted and experimental affinity | Spearman > 0.6 or matches a specialized DTI baseline within 10% | No correlation or specialized baseline dominates by >20% |
| **Phase 2a — Hit-list expansion** | Expanded set passes BBB + ClinTox filters at reasonable rate (>30% survive) | Expanded set contains compounds Quiver would have wanted to test (manual review by Matt/Rohan) | Filtered to ~zero compounds, or set is full of obvious toxics |
| **Phase 2b — TSC top 20 genes** | Known TSC drugs (rapamycin, everolimus, MTOR-pathway) appear in the top 100 candidates | Known TSC drugs in top 10 | Known drugs missing from top 100 |
| **Phase 2c — CRISPR-N gene interrogation** | At least 2 of the disease-target genes get plausible small-molecule candidates | Multiple genes get candidates that overlap with known druggable targets | All candidates look like noise |
| **Phase 3 — MAMMAL vs Proton (CNS-specific)** | MAMMAL within 20% of Proton on TSC use case | MAMMAL competitive or better than Proton on CNS-relevant tasks | Proton clearly wins on every CNS task — use Proton instead |
| **Phase 3 — MAMMAL vs specialized DTI** | MAMMAL within 10% of specialist on our calibration set | MAMMAL beats specialist on our data | Specialist clearly wins; MAMMAL is downstream enrichment only |
| **Phase 4 — Sapphire integration** | Hybrid query returns sensible results manually | Hybrid query surfaces something neither KG nor MAMMAL alone would find | Integration breaks or results are noise |

## Decision rules at the end of exploration

- **3+ strong passes** → MAMMAL becomes a candidate for Sapphire's latent space layer; promote to architecture-track work
- **Most passes, few strong passes** → MAMMAL is a useful enrichment tool but not core infrastructure; build a workflow that uses it for hit-list expansion + de-risking
- **Phase 1 fails** → stop, write up findings; do not proceed to Phase 2. Explore Proton as alternative.
- **Phase 1 passes but Phase 2 fails** → MAMMAL works in principle but doesn't generalize to our use cases; reconsider fine-tuning as a separate decision

## What "strong pass" needs to feel like

Borrowing from the senior voice in the 5/28 meeting, a strong pass on Phase 2a (hit-list expansion) should produce a story like:

> *"We took our top 50 from a real screen, MAMMAL expanded it to 200, de-risked by BBB and toxicity filters down to 20, the 20 survivors included 4 candidates Matt confirmed we'd want to wet-lab. Total elapsed time: 2 hours."*

That's the bar. Not "AUROC 0.95 on the paper benchmark." A concrete workflow with a measured time-to-result.

## Notes on calibration

- **Domain shift caveat**: MAMMAL was trained on general biomedical data, not specifically CNS. The Jernabix → Nav1.8 test is partly a "does this work for ion-channel drug-target pairs" test, which may not generalize. Document the domain of every test case so we know where MAMMAL is reliable vs unreliable.
- **Confidence calibration**: track not just whether predictions are right, but whether the model's confidence scores are meaningful. A model that's wrong but confident is worse than one that's wrong and uncertain.
- **Negative result documentation**: failures are findings. Write them up as carefully as successes. The decision rules above only work if we have honest data on what doesn't work.
