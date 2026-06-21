# Boltz round 2 — QS-scaffold polypharmacology panel (2026-06-12)

**Run:** AWS g6e.xlarge in us-east-1a, 22 min wall time, $0.68 spend.
All 15 complexes rc=0. Total Boltz-lane spend: **$5.02 / $15 cap.**

**Reason for the run:** The pathway-neighbor hypothesis (James, 6/11) was
refuted on 4 of 5 Tier-1 metabolic/nuclear-receptor targets in the overnight
panel. We then asked a different question: does QS0069567 / QS0113172 bind
proteins that match the *scaffold-class polypharmacology* of QS0069567 (=
CHEMBL1605376)? Built a focused panel on 3 strong-evidence targets:

| Target | Construct | Why this target | Positive ctrl |
|---|---|---|---|
| **BAZ2B BRD** | Q9UIF8 res 2054-2168, 115 aa | Direct CHEMBL1605376 hit | GSK2801 |
| **HSD11B1** | P28845 full, 292 aa | Strong look-alike scaffold-class signal (aryl-sulfonyl-piperazine class is a published 11β-HSD1 inhibitor chemotype) | carbenoxolone |
| **EHMT2 SET** | Q96KQ7 res 1000-1210 | Look-alike class hit (BIX-01294 style sulfonyl-piperazine) | BIX-01294 |

## TL;DR — first positive Boltz signal in this campaign

| Target | Calibration | QS0069567 | QS0113172 |
|---|---|---|---|
| BAZ2B BRD | ✗ FAILED (positive control ranked 5/5) | INCONCLUSIVE | INCONCLUSIVE |
| **HSD11B1** | ✓ STRONG (+0.42 margin) | **#1 of 5 at 0.657 — TIES the positive control. Likely binder.** | rank 3/5 at 0.365; weak signal but above both decoys |
| EHMT2 SET | ✓ SUCCEEDED (+0.25 margin) | REFUTED (rank 4/5) | REFUTED (rank 5/5) |

**QS0069567 may physically bind 11β-HSD1 (HSD11B1).** This is the first
positive Boltz result for either compound across the entire campaign
(prior runs: PKM2 dimer refuted, PPARD inconclusive, 4-of-5 pathway
neighbors refuted, all PROTON-KG look-alikes refuted).

## Per-target details

### BAZ2B-BRD — calibration FAILED, result not interpretable

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| 1 | 0.296 | QS0069567 | putative |
| 2 | 0.262 | BIIB021 | negative |
| 3 | 0.203 | BMS 191011 | negative |
| 4 | 0.159 | QS0113172 | putative |
| **5** | **0.091** | **GSK2801** | **POSITIVE CTRL** |

GSK2801 is a well-characterized BAZ2B BRD probe (PubChem CID 71744817,
spirocyclic dihydroisoxazole + thiophene + pyridine scaffold) but Boltz
ranked it LOWEST of the 5 — even the QS putatives beat it. Without
calibration we can't interpret the QS scores: QS0069567's #1 finish is
likely Boltz-noise rather than real signal.

*Why the failure:* small isolated bromodomains (~115 aa) are hard targets
for Boltz — the binding pose depends on a flexible ZA loop and acetyllysine-
mimetic positioning that Boltz captures imperfectly without context.
**BAZ2B verdict: untestable by Boltz alone.**

### HSD11B1 — calibration SUCCEEDED, QS0069567 LIT UP

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.657** | **QS0069567** | **putative — LIKELY BINDER** |
| 2 | 0.638 | carbenoxolone | POSITIVE CTRL |
| 3 | 0.365 | QS0113172 | putative — weak signal |
| 4 | 0.215 | BMS 191011 | negative |
| 5 | 0.110 | BIIB021 | negative |

- Positive control margin over top decoy: **+0.423** (very clean calibration).
- **QS0069567 (0.657) and carbenoxolone (0.638) are essentially tied** — QS0069567 is fractionally higher but within the noise envelope. Both score in the "clean binder" regime.
- QS0113172 (0.365) is above both decoys but ~0.27 below the positive control — a possible weak binder, not as confident as QS0069567.
- Decoys (BMS 191011, BIIB021) land in the 0.11-0.22 band, consistent with the "non-binder" regime.

This is the FIRST positive Boltz signal for these compounds in the whole
campaign. It's also CONSISTENT with the ChEMBL look-alike polypharmacology:
QS0069567's scaffold cousins frequently appear in 11β-HSD1 screening
literature, so this isn't out of left field.

### EHMT2-SET — calibration SUCCEEDED, BOTH QS REFUTED

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.518** | **BIX-01294** | **POSITIVE CTRL** |
| 2 | 0.267 | BIIB021 | negative |
| 3 | 0.215 | BMS 191011 | negative |
| 4 | 0.176 | QS0069567 | putative |
| 5 | 0.113 | QS0113172 | putative |

Clean calibration: BIX-01294 (positive) at #1, margin +0.251 over top decoy.
**Both QS compounds scored BELOW the negatives** (ranks 4/5 and 5/5).
EHMT2/G9a binding is **strongly refuted** for both.

## Biological interpretation — what 11β-HSD1 binding could mean for the TSC2 phenotype

11β-HSD1 (HSD11B1, 11β-hydroxysteroid dehydrogenase type 1) is an
endoplasmic-reticulum enzyme that converts **inactive cortisone → active
cortisol** in tissue. It's a major intracellular glucocorticoid amplifier.

Mechanistic connection to a TSC2-rescue phenotype (the actual Quiver assay
QS compounds were pulled from):

1. **TSC2 loss → mTORC1 hyperactivation → glucocorticoid receptor (GR) signaling cross-talk.** mTORC1 modulates GR transcriptional activity in multiple cell types, including neurons.
2. **11β-HSD1 inhibition lowers intracellular cortisol → reduced GR signaling → suppression of stress-response gene programs** (NR3C1-driven, FKBP5, SGK1, etc.).
3. In neurons specifically, **chronic GR activation promotes hyperexcitability** (NMDA-receptor upregulation, BDNF dysregulation, dendritic spine remodeling).
4. So an 11β-HSD1 inhibitor could plausibly **rescue a TSC2-hyperexcitability phenotype** in the Optopatch assay by attenuating the GR-driven excitability program — without ever touching PKM2 or PPARD directly.

This is a coherent, testable alternative-target hypothesis. It explains:
- Why the DFP signature for QS0069567 matched compounds with different
  primary targets (Dasa-58 / GSK 3787) — they're all converging on a
  similar downstream effect (modulating neuronal metabolic-stress state).
- Why the literal-target Boltz runs failed (PKM2 monomer, PPARD covalent)
  and the pathway-neighbor runs failed — we were looking in the wrong
  protein space.

**Caveat: the Boltz margin is narrow.** QS0069567 ties the positive
control rather than clearly exceeding it. We can say "looks like a binder";
we cannot say "definitely a binder" from Boltz alone.

## Recommended next experiments (in priority order)

1. **Wet-lab confirmation of QS0069567 ↔ 11β-HSD1.** Two paths:
   - **HSD11B1 enzyme activity assay** (commercial kit; ~$500-1K; <1 week turnaround). Measure cortisone-to-cortisol conversion ± QS0069567 vs ± carbenoxolone.
   - **Thermal shift / CETSA** with QS0069567 against recombinant HSD11B1 protein.
2. **Re-look at the DFP signature.** Now that we have an alternative-target hypothesis (HSD11B1), does QS0069567's DFP fingerprint also match known HSD11B1 inhibitors? If yes, the DFP-validation case strengthens significantly.
3. **Quiver Optopatch rescue test with a CLEAN 11β-HSD1 inhibitor** (e.g., AZD4017, ABT-384, BVT2733). If a known 11β-HSD1 inhibitor recapitulates the TSC2 rescue phenotype, the mechanism is locked in.
4. **QS0113172 + 11β-HSD1 follow-up.** Its Boltz score (0.365) was above noise but below the positive. Worth a dose-response in the same enzyme assay.

## Cost summary

- Round 2 instance (g6e.xlarge, us-east-1a, 22 min): **$0.68**
- Cumulative Boltz-lane spend: $4.34 (prior) + $0.68 = **$5.02 / $15 cap**
- Remaining budget: $9.98

## Files
- `aws/boltz_round2_panel.json` (boltz branch) — 15-complex input
- `aws/boltz_round2_userdata.sh` (boltz branch) — AWS userdata
- `results/aws_eval/boltz_round2/results.json` — raw Boltz outputs
- `results/aws_eval/boltz_round2_report.md` (boltz) — this report
- `docs/boltz_round2_report_2026-06-12.md` (RohanOnly) — same content

## Cross-branch note for the `models` scorecard

`docs/models_tracks_scorecard.md` (models branch): Track 2 (DTI/binder
triage) and Track 9 (off-target/selectivity) should be updated to reflect:
- Boltz can calibrate cleanly on small enzyme targets (HSD11B1, 292 aa, +0.42 margin)
- Boltz fails on small isolated bromodomains (BAZ2B BRD, 115 aa) — same architectural limit we've documented before (small isolated domains have weak prior structure context)
- **Most importantly:** an off-the-shelf Boltz panel found a real-looking
  positive (QS0069567 ↔ 11β-HSD1) for an undiscovered Quiver compound. This
  is a genuine pipeline win, narrow margin notwithstanding.
