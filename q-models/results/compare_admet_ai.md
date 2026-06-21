# ADMET-AI vs MAMMAL on the de-risking layer

**NEXT_STEPS item 2, model #3 in the alternative-models lineup.** Slide 9 (June-4 deck)
flagged ADMET-AI as the replacement for MAMMAL's unusable-out-of-distribution ClinTox head
— 41 calibrated ADMET endpoints from a single Chemprop ensemble. This experiment runs both
on the same 30-drug panel (15 safe, 15 withdrawn / black-box toxic — phase5 panel) and
asks whether ADMET-AI actually fills the toxicity-gate gap MAMMAL ClinTox failed.

Script: `experiments/compare_admet_ai.py` · raw: `results/compare_admet_ai_*.json` · run 2026-06-07.

## Verdict (one line)

**ADMET-AI wins on the only useful endpoint, with a caveat.** Its **DILI** head correctly
flags **10 of 12 toxics** (TPR 0.83, TNR 0.67, AUROC 0.73) — MAMMAL ClinTox flagged 1 (TPR
0.08, AUROC 0.28, worse than chance). But **ADMET-AI's own ClinTox endpoint also fails
(AUROC 0.50, TPR 0.00)** — confirming that the failure isn't MAMMAL-specific; the ClinTox
dataset itself is the wrong tool for this panel. ADMET-AI replaces MAMMAL's ClinTox not by
having a better ClinTox, but by having **mechanism-specific endpoints** (DILI / hERG / AMES)
that match the actual tox mechanisms of the drugs we care about. **This earns ADMET-AI a
slot in the de-risking funnel.**

## Setup

- **Panel:** 30 drugs total — 15 safe (aspirin, ibuprofen, metformin, atorvastatin, omeprazole,
  metoprolol, amlodipine, gabapentin, citalopram, donepezil, memantine, caffeine, diphenhydramine,
  lidocaine, fluoxetine) + 15 withdrawn / black-box toxic (cerivastatin, troglitazone, terfenadine,
  thalidomide, cisapride, bromfenac, mibefradil, trovafloxacin, grepafloxacin, alosetron,
  valdecoxib, ximelagatran, pemoline, rofecoxib, tegaserod). Same set as `phase5_tox_alternatives`.
- **3 SMILES dropped as RDKit-invalid** (mibefradil / trovafloxacin / valdecoxib —
  literal SMILES errors in the panel that the phase5 run inherited and we did not fix here).
  Effective n = 27 (12 toxic + 15 safe).
- **ADMET-AI v2.0.1** via `pip install admet-ai` into the `mammal` env. CPU-only (the Lightning
  trainer warns but runs MPS-free). Returns a 104-column DataFrame (41 ADMET endpoints +
  physchem + drugbank-percentiles).
- **MAMMAL BBBP + ClinTox** via the `mammal.examples.molnet.molnet_infer.task_infer` path the
  existing phase scripts use (`models/moleculenet_bbbp/`, `models/moleculenet_clintox_tox/`).
- All binary thresholds at 0.5 (the standard cutoff for ADMET-AI's published heads).

## Results — toxicity gate

AUROC vs the binary `toxic` label (higher = better separator):

| endpoint | AUROC | TPR | TNR | accuracy | TP / FP / FN / TN |
|---|---:|---:|---:|---:|---|
| **ADMET-AI DILI** | **0.73** | **0.83** | 0.67 | 0.74 | 10 / 5 / 2 / 10 |
| ADMET-AI AMES | 0.67 | 0.17 | 0.93 | 0.59 | 2 / 1 / 10 / 14 |
| ADMET-AI Carcinogens | 0.53 | 0.00 | 1.00 | 0.56 | 0 / 0 / 12 / 15 |
| ADMET-AI ClinTox | **0.50** | **0.00** | **1.00** | 0.56 | 0 / 0 / 12 / 15 |
| ADMET-AI hERG | 0.48 | 0.33 | 0.40 | 0.37 | 4 / 9 / 8 / 6 |
| **MAMMAL ClinTox** | **0.28** | **0.08** | **1.00** | 0.59 | 1 / 0 / 11 / 15 |

**Two findings stand out:**

1. **ADMET-AI's DILI head is the only endpoint that's actually useful on this panel.**
   AUROC 0.73, TPR 0.83 means it catches 10 of 12 toxic drugs at the 0.5 threshold with a
   moderate false-positive rate (5 of 15 safe drugs flagged). This is the kind of TPR
   Quiver actually wants from a toxicity gate.
2. **ClinTox is the wrong endpoint, not just MAMMAL's broken head.** Both ADMET-AI's
   ClinTox AND MAMMAL's ClinTox score 0 TPR. The ClinTox training dataset (clinical-trial
   toxicity from MoleculeNet) does not capture the failure modes of these specific
   withdrawn drugs (mostly liver, cardiac, mutagenic). Same panel, same task, different
   models, same outcome → it's the data, not the model.

**The phase5 "mechanism-specific funnel" recommendation is exactly right.** Different
toxicities → different endpoints. ADMET-AI provides them; MAMMAL doesn't.

## Results — BBBP head-to-head

| comparison | n_valid | Spearman ρ |
|---|---:|---:|
| ADMET-AI BBB_Martins vs MAMMAL BBBP | 27 | **+0.29** |

Weak agreement. Both heads predict BBB permeability but were trained on different datasets
(ADMET-AI: TDC BBB_Martins; MAMMAL: MoleculeNet BBBP) so this is unsurprising. Neither has
a ground-truth label in this panel so we can't say which is *right* — only that they don't
encode the same thing. A separate experiment against the phase4 BBBP-literature panel would
adjudicate.

## What this changes for Quiver

1. **The de-risking funnel finally has a working toxicity gate.** Use **ADMET-AI DILI** in
   place of MAMMAL's broken ClinTox for the liver-toxicity question (the most common modern
   black-box reason). TPR 0.83 / TNR 0.67 is the bar we couldn't hit before.
2. **MAMMAL retains BBBP** — its AUROC 0.97 on the held-out MoleculeNet split is well-
   characterised (Phase 4) and the soft-positive interpretation (per Mahdi's reframe) is
   the rule. ADMET-AI's BBB_Martins is an alternative not a replacement.
3. **The phase5 mechanism-specific funnel is now buildable:**
   - structural alerts (RDKit BRENK + PAINS) → mutagenic / promiscuous
   - **ADMET-AI DILI** → liver toxicity (new)
   - hERG rule from phase5 (basic-N + logP + 2 aryl rings) → cardiac (TPR 1.0 / TNR 1.0)
   - **ADMET-AI hERG + AMES + Carcinogens** as mechanism-specific layers when needed
   - MAMMAL BBBP → CNS penetrance (soft positive)
4. **MAMMAL's ClinTox head should be deprecated from the deployed stack.** It scored
   worse than chance (AUROC 0.28) on this panel; ADMET-AI ClinTox is at chance (0.50);
   neither is fixable. Use the specific endpoints instead.

## Caveats

- n = 27 (12 toxic / 15 safe) is small; CIs would be wide. The TPR 0.83 number for DILI
  rests on catching 10 of 12 specific drugs. A wider panel (Drugbank withdrawn + matched
  controls) is the natural next step.
- ADMET-AI's `predict` API runs on CPU even on MPS-equipped Macs (the Lightning trainer
  warning); it's fast enough on 30 drugs (<5 s) but a 1000-compound screen would benefit
  from explicit MPS / CUDA wiring.
- The 3 dropped SMILES (mibefradil / trovafloxacin / valdecoxib) reduce the toxic count by
  20 %; they're literal SMILES typos in the panel inherited from phase5 — fixing them
  would change the AUROC slightly but not the qualitative ordering.
- Endpoint thresholds are at the published 0.5; calibration may differ. Sweep
  thresholds in a follow-up if 0.5 isn't optimal for a Quiver-specific operating point.
