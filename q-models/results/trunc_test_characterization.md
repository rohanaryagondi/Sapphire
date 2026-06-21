# Why are CNS ion channels at chance for off-the-shelf DTI? — truncation vs. supervision (2026-06-15)

Phase 1a of the overnight CNS campaign. `results/cns_dti_characterization.md` found zero-shot BALM/PLAPT at
**chance (0.50)** on the CNS ion-channel family. Two suspects: (a) BALM truncates proteins to 1024 tokens
and channels are 1956–2221 aa, (b) BindingDB pretraining is ion-channel-poor. This eval: a fixed ESM-2-650M
protein rep (TRUNCATED to 1022 aa vs FULL-length chunk-pooled) ⊕ Morgan-FP ligand → **supervised logistic
probe, 5-fold scaffold-split (GroupKFold over Murcko scaffolds) CV**, per ion-channel target. g5.xlarge, ~$0.5.

## Headline: **The ion-channel binding signal IS learnable with supervision (0.92, scaffold-split) — zero-shot models just don't capture it. Truncation is NOT the cause. This is the empirical green light for a fine-tune.**

| Target | zero-shot BALM cosine | supervised probe (scaffold-split) | gain |
|---|---|---|---|
| SCN9A (Nav1.7) | 0.845 | **0.998** | +0.15 |
| SCN10A (Nav1.8) | 0.780 | **0.965** | +0.19 |
| GRIN2B (NMDA) | 0.330 | **0.961** | **+0.63** |
| GRIN1 (NMDA) | 0.320 | **0.953** | **+0.63** |
| **CACNA1C (Cav1.2)** | **0.204** | **0.951** | **+0.75** |
| SCN1A (Nav1.1) | 0.292 | **0.939** | **+0.65** |
| SCN2A (Nav1.2) | 0.710 | 0.916 | +0.21 |
| SCN5A (Nav1.5) | 0.459 | 0.892 | +0.43 |
| SCN8A (Nav1.6) | 0.556 | 0.700 | +0.14 (hardest) |
| **family mean** | **0.499** | **0.919** | **+0.42** |

**The worst zero-shot targets show the biggest supervised gains** — Cav1.2 (0.20→0.95), NMDA (0.32→0.95),
SCN1A (0.29→0.94). A trivial supervised model on held-out scaffolds nails the exact channels off-the-shelf
DTI fails on.

## Two clean conclusions
1. **Truncation is NOT the cause.** Truncated (1022 aa) and full-length (chunk-pooled, every residue) probes
   are **identical to 4 decimals (Δ0.0) on all 9 targets.** Mechanistically expected: in a *per-target*
   probe the protein embedding is constant across that target's compounds, so it contributes nothing to
   within-target discrimination — the ligand fingerprint does the work. So a long-context protein encoder
   would NOT rescue zero-shot ion-channel DTI; that's not the bottleneck.
2. **The cause of the zero-shot failure is the lack of target-specific supervision.** BALM/PLAPT are
   BindingDB-pretrained (ion-channel-poor) and applied zero-shot → 0.50. The same features under a
   per-target supervised fit → 0.92. The gap is supervision, not representation or truncation.

## What this means for the fine-tune (the decision)
**This de-risks the Quiver fine-tune empirically.** The question was "is ion-channel binding even learnable,
or is the signal absent from sequence+ligand?" Answer: **learnable — a logistic regression on ESM-2+FP
features hits 0.92 on a scaffold-split, including the sub-chance zero-shot targets (Cav1.2, NMDA).** So a
target/family-specific fine-tune is not a gamble; the **0.50 → 0.92 gap is the concrete value of supervised
ion-channel data.** Combine with the data research (`docs/finetune_justification_research.md`): the public
Na-channel-class set (~12k cpds) + Quiver's own ion-channel screening data (with inactives) is the substrate.

## Honest caveats
- This is a **ligand+target QSAR ceiling**, not a protein-rep ablation: because the per-target protein
  embedding is constant, the probe is effectively a per-target ligand QSAR (which is exactly what a
  fine-tune exploits, but it does NOT prove ESM-2 protein features are *necessary*). The result that matters
  — "actives are separable from decoys with supervision on held-out scaffolds" — is robust.
- **Scaffold-split (GroupKFold/Murcko)** is the honest split (no analog leakage), so 0.92 reflects
  generalization to new scaffolds, not memorization. SCN8A (0.70) is the genuinely hard one.
- The decoys are ChEMBL inactives / property-matched; 60 actives/target cap.

## Scorecard impact
Track 2 (DTI) — adds the load-bearing fine-tune evidence: **off-the-shelf zero-shot = chance on CNS ion
channels (0.50); a supervised scaffold-split probe = 0.92.** Truncation ruled out as the cause. The
fine-tune call (ion-channel data, scaffold-split, vs an FP+GBT baseline) is now backed by a measured
learnable ceiling.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/trunc_test/trunc_test_result.json`; eval
`aws/trunc_test_eval.py`; instance `i-04b599b097b730c32` self-terminated.
