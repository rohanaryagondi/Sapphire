# Phase 4 `cns_roundout` — BANKED (redundant), 2026-06-15

Phase 4 of the overnight CNS campaign was a "round-out": (a) MapLight on a CNS **held-out BBB funnel**, and
(b) funNCion on a **broader CNS channel-variant set** (Track 10). On re-derivation, **both components are
already answered — there is no new model-selection result to gain — so Phase 4 is banked, not launched.** No
AWS spend incurred.

## (a) Held-out BBB funnel — ALREADY DONE by `maplight_b3db`
The pending request ("run a held-out BBB funnel, find a dataset online" → task #6) is satisfied by
`results/maplight_b3db_characterization.md`:
- Train on **TDC BBB_Martins**, test on **B3DB** (theochem, CC0, 7,807 cpds) — a genuinely independent
  dataset, **canonical-SMILES leakage removed** (1,665 overlaps dropped → **6,142 held-out molecules**).
- **MapLight 0.919 AUROC vs MolFormer-XL 0.854**; better calibrated (Brier 0.126 vs 0.157).
- The funnel that matters — **far-OOD** (max Tanimoto-to-train < 0.3, n=824): **MapLight 0.674 vs MolFormer
  0.590** (near chance). MapLight degrades gracefully where the SMILES LM collapses.
- Verdict already in the scorecard: **Track 4 BBB primary = MapLight** (commercial-OK, CPU-only), MolFormer
  a backstop; ship a Tanimoto-to-train confidence flag in the Explorer.

A second "CNS-held-out" split would re-confirm the same ranking on the same chemistry — no new decision.

## (b) funNCion broader variant set — no model-selection value
funNCion is already the **Track 10 (variant-effect) best** in the scorecard. Running it on more CNS
ion-channel genes is a *generalization check of the incumbent*, not a head-to-head against a competing
model, so it cannot change "which model is best for variant-effect." The campaign's purpose is
**model selection per capability**; Track 10's winner is settled. Deferred as a future generalization study,
not a model-map gap.

## Why this is the right call (not skipping work that matters)
- The "explore new models for CNS" directive is being served by **Phase 3 (`cns_new_models` / DTIAM)** — the
  dedicated new-model scout — which is the live phase. Phase 4 would not add a new model.
- Budget discipline: a g5.xlarge launch (~$0.5) for a re-confirmation + an incumbent-generalization check is
  spend without a decision. Preserved under the $45 cap for anything that *does* change the map.

## Scorecard impact
**None.** Track 4 = MapLight (held-out-confirmed); Track 10 = funNCion (incumbent). Task #6 (held-out BBB
funnel) is **complete** via `maplight_b3db`.

**Receipts:** the BBB-funnel result lives at
`s3://rohan-mammal-bootstrap-20260610-213029/maplight_b3db/maplight_b3db_result.json`
(`results/maplight_b3db_characterization.md`). No `cns_roundout` instance was launched; a SKIPPED-redundant
DONE marker is placed at `s3://.../cns_roundout/DONE` for driver idempotency.
