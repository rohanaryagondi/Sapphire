# Phase 4 — BBBP head vs textbook BBB pharmacology (literature ground truth)

**As of 2026-05-29.** Tier-1 reality check: does MAMMAL's BBBP head agree with what clinical
pharmacology already knows? Tested on named drugs whose brain penetrance is textbook, focusing
on "smoking-gun" cases (efflux substrates / by-design peripheral drugs) where the answer is
unambiguous. Scripts: `experiments/phase4_bbbp_literature.py`; raw `results/phase4_bbbp_literature_*.json`.

## TL;DR — revises the earlier "BBBP deployable as-is" claim

**The BBBP head is good in ONE direction and weak in the other.** It correctly confirms brain
penetrance for clearly CNS-active drugs (11/11), and correctly excludes large/obvious non-
penetrants (sirolimus, vancomycin). **But it has a systematic false-positive bias toward
"penetrant" and misses small peripherally-restricted / efflux-substrate drugs** (cetirizine,
atenolol, domperidone all called penetrant). It also emits **hard 0/1 labels, not calibrated
probabilities** (93% of scores saturate to ~0 or ~1), and is **sensitive to SMILES form**
(loperamide flips between two valid SMILES of the same molecule). The 0.968/0.996 benchmark
AUROC is real for *ranking on the dataset's 76%-positive label mix* — it **oversells per-compound
reliability for de-risking**, which is exactly the rule-OUT direction that matters.

## What we ran

20 named drugs, clinical BBB label from pharmacology, **clean neutral-parent SMILES** (salts
stripped, uncharged — v1 had a salt/protonation bug from PubChem isomeric SMILES). Each compound
mapped to its MoleculeNet BBBP **scaffold-split fold** (train/valid/test) by neutral-parent
InChIKey, so memorization is separated from generalization. Readout = the IBM molnet generative
P(`<1>`)=P(BBB-penetrant), validated to reproduce AUROC 0.996 on a balanced dataset sample.

## Results

**Positive direction — "is it CNS-active?" → 11/11 correct.** All clearly central drugs scored
penetrant: morphine, diphenhydramine, hydroxyzine, diazepam, caffeine, haloperidol, fluoxetine,
donepezil, carbamazepine, phenytoin, metoclopramide.

**Negative direction — "de-risk: will it be kept OUT?" → unreliable.**

| BBB− compound | clinical | dataset label | P(BBB+) | call | note |
|---|---|---|---|---|---|
| sirolimus | − | (not in set) | 0.000 | ✅ − | large macrocycle, correctly excluded |
| vancomycin | − | (not in set) | 0.000 | ✅ − | large glycopeptide, correctly excluded |
| fexofenadine | − | − | 0.000 | ✅ − | correct (robust across SMILES) |
| **cetirizine** | − | − | 1.000 | ❌ + | genuine error (consistent across SMILES forms) |
| **atenolol** | − | − | 1.000 | ❌ + | genuine error (hydrophilic β-blocker) |
| **domperidone** | − | − | 1.000 | ❌ + | genuine error (held-out test fold) |
| loperamide | − | − | 0.000 / 1.000 | ⚠️ flips | correct on dataset SMILES, wrong on neutral SMILES — **SMILES-form sensitivity** |
| sulpiride | −(strict) | **+** | 1.000 | ~ | model agrees with dataset; clinical label debatable (it is a marketed antipsychotic) |
| loratadine | −(non-sedating) | **+** | 0.935 | ~ | model agrees with dataset; lipophilic, label debatable |

So of the clinically clear BBB− small molecules, the model correctly rules out only the
large/obvious ones; it **passes cetirizine, atenolol, domperidone as penetrant** — false positives
in the exact direction a CNS de-risking filter is supposed to catch.

## Three robust technical findings

1. **Not calibrated — hard 0/1.** 93% of outputs are ~0.000 or ~1.000. "P(BBB+)" is a binary
   label; you cannot tune a threshold or rank compounds within a class by it.
2. **False-positive bias toward penetrant.** Errors are one-directional (BBB− → predicted +),
   consistent with the 76%-positive training distribution. The minority (BBB−) class — the one
   that matters for de-risking — is where it fails.
3. **Input-form sensitivity (narrower than first thought).** A dedicated robustness test
   (`phase4_smiles_robustness.py`) showed BBBP is **stable to SMILES atom-reordering** (0/6
   molecules flip across 8 randomized encodings of the identical structure). So the loperamide
   discrepancy (0.000 vs 1.000) came from a chemically *different* input form (protonation/salt),
   not re-encoding → **standardize protonation/salt/tautomer before scoring**, but canonical
   re-ordering is safe. (Also a reminder that benchmark labels themselves diverge from clinical
   pharmacology in places — see sulpiride/loratadine.)

## Revised usage guidance for Quiver

- **Use it as a soft POSITIVE signal**, not a rule-out gate: a high score weakly supports CNS
  exposure; a "penetrant" call on a small drug-like molecule does **not** rule out efflux-driven
  peripheral restriction.
- **Don't gate de-risking on it** (the rule-OUT direction is unreliable) and **don't threshold/
  rank by the score** (uncalibrated). Canonicalize SMILES before scoring.
- For real CNS exposure prediction, efflux (P-gp/BCRP) liability is the dominant factor BBBP does
  not capture — a dedicated P-gp-substrate / Kp,uu model would be needed.

## Reconciliation with the benchmark
The 0.968 (paper 0.957) held-out AUROC and our 0.996 balanced-sample AUROC are not wrong — they
measure ranking on the dataset's label mix, which is 76% penetrant. They simply don't reflect
(a) calibration, (b) per-direction reliability, or (c) SMILES robustness. "Honest benchmark,
narrow usefulness" — the project's recurring theme — applies here too.
