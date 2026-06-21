# ConPLex — full Nav family + off-target sanity

**Two gaps filled in the alternative-models comparison.** Prior compare suite
tested ConPLex only on Nav1.8 (single paralog) against the Nav blocker set, and
never gave it Graham's off-target check. This run closes both.

Script: `experiments/compare_conplex_nav_offtarget.py` ·
raw: `results/compare_conplex_nav_offtarget_20260607_180236.json` · 2026-06-07.

## Headline (one paragraph)

**ConPLex is pan-Nav blind and has poor off-the-shelf specificity.** Across
all 9 SCN paralogs (Nav1.1–Nav1.9) ConPLex sits at chance on the
binder-vs-decoy test (mean AUROC = **0.437**; 0/9 paralogs cross the useful
0.60 line, 0/9 cross strong 0.70). On Graham's off-target probe the picture
is the same as MAMMAL's: of 5 Nav-blocker / background drugs scored against
Nav1.8 + UBE3A + TUBB, the on-vs-off-target separation is tiny or zero — the
strongest "specificity" signal is **ibuprofen** preferring Nav1.8 (Δ = +0.26),
not the Nav drugs (Δ = +0.05 for suzetrigine, +0.13 for vixotrigine).

The earlier MAMMAL-Nav1.8 result was not a paralog-specific accident, and the
ConPLex-doesn't-beat-MAMMAL result is not a Nav1.8-specific accident either.
**The BindingDB-trained DTI tooling space is uniformly Nav-blind off the
shelf.** A Quiver Nav fine-tune (whether of MAMMAL or anything in this class)
is the only available lever.

## Part 1 — full Nav family (Nav1.1 → Nav1.9)

Protocol: per paralog, score 7 Nav blockers (suzetrigine, A-803467, lidocaine,
mexiletine, ranolazine, carbamazepine, lacosamide) vs 4 decoys (metformin,
caffeine, ibuprofen, atenolol). AUROC via Mann-Whitney with tie handling.

| paralog | accession | gene | seq_len | AUROC | sep (binder − decoy) |
|---|---|---|---:|---:|---:|
| Nav1.1 | P35498 | SCN1A | 2009 (trunc) | **0.393** | +0.043 |
| Nav1.2 | Q99250 | SCN2A | 2005 (trunc) | 0.429 | +0.042 |
| Nav1.3 | Q9NY46 | SCN3A | 2000 (trunc) | **0.393** | +0.040 |
| Nav1.4 | P35499 | SCN4A | 1836 (trunc) | 0.500 | +0.027 |
| Nav1.5 | Q14524 | SCN5A | 2016 (trunc) | 0.500 | +0.025 |
| Nav1.6 | Q9UQD0 | SCN8A | 1980 (trunc) | 0.429 | +0.040 |
| Nav1.7 | Q15858 | SCN9A | 1988 (trunc) | 0.464 | +0.035 |
| Nav1.8 | Q9Y5Y9 | SCN10A | 1956 (trunc) | **0.393** | +0.015 |
| Nav1.9 | Q9UI33 | SCN11A | 1791 (trunc) | 0.429 | +0.009 |

**Mean AUROC across the family = 0.437. Max = 0.500. 0/9 above 0.60.**

Reading: every Nav paralog truncates to 1250 aa (the same cap that hurts the
MAMMAL Nav1.8 case). The mean and ceiling are both below chance, and the
per-paralog scores barely move when changing the protein input — i.e. ConPLex
isn't reading the protein context in a useful way for this family. Within
each row, the by-drug scores are *almost identical* across paralogs (Nav1.1
top drug = lacosamide @ 0.53; Nav1.5 top drug = lacosamide @ 0.38; Nav1.9 top
drug = lacosamide @ 0.27 — same drug ordering, just attenuated by sequence
length / truncation). The model has a strong drug-only prior that swamps the
target signal.

## Part 2 — off-target sanity (Graham's protocol)

5 drugs × 3 targets. Raw ConPLex probabilities (0–1 scale):

| target | suzetrigine | vixotrigine | metformin | caffeine | ibuprofen | spread |
|---|---:|---:|---:|---:|---:|---:|
| UBE3A (off) | 0.0000 | 0.0000 | 0.0032 | 0.0823 | 0.0000 | 0.082 |
| **Nav1.8 (on)** | **0.0472** | **0.1457** | 0.1400 | 0.0778 | **0.2610** | 0.214 |
| TUBB (off) | 0.0000 | 0.0269 | 0.0256 | 0.0139 | 0.0000 | 0.027 |

Per-drug specificity (Nav1.8 score − mean of the two off-targets):

| drug | Nav1.8 | mean off | Δ | interpretation |
|---|---:|---:|---:|---|
| suzetrigine | 0.047 | 0.000 | **+0.047** | weak — both ~0; not a real signal |
| vixotrigine | 0.146 | 0.014 | **+0.132** | weak — modest on-target lean |
| metformin (decoy) | 0.140 | 0.014 | +0.126 | similar to vixotrigine — drug-only effect |
| caffeine (decoy) | 0.078 | 0.048 | +0.030 | none |
| ibuprofen (decoy) | 0.261 | 0.000 | **+0.261** | strongest "specificity" — for a decoy |

Two diagnoses:

1. **The strongest on-target signal in the whole table belongs to ibuprofen,
   not a Nav drug.** Ibuprofen is a Nav decoy in our test set. ConPLex says it
   binds Nav1.8 ~5× more strongly than the actual Nav blocker suzetrigine.
   That's a hallmark of drug-only-bias rather than learned target specificity.

2. **For real Nav drugs the on-vs-off Δ is small** (+0.05 to +0.13 on a 0–1
   scale). MAMMAL's equivalent test ([`offtarget_ube3a.md`](offtarget_ube3a.md))
   showed the same pattern: drugs score in a tight band across unrelated
   targets, with at-best a faint on-target lean that's swamped by the
   background spread.

UBE3A and TUBB scores are mostly 0.00 for the Nav drugs — i.e. **the absolute
ConPLex scores are extremely low everywhere** (most cells are < 0.05). This
isn't "ConPLex predicts binders for everything" like MAMMAL did with its
pKd 6–7 band; ConPLex is closer to "predicts non-binder for everything, with
small differences that don't track the right axis." Different failure mode,
same operational consequence: no useful binder triage off the shelf.

## What this changes

- **Confirms** the prior compare3 result (ConPLex doesn't beat MAMMAL on
  Nav1.8) generalises across the whole Nav family — not a paralog-specific
  accident.
- **Confirms** the prior MAMMAL off-target finding (
  [`offtarget_ube3a.md`](offtarget_ube3a.md)) is a property of off-the-shelf
  DTI on this family, not MAMMAL-specific.
- **Closes** the alternative-models story for ConPLex: every test we
  promised — correlation, named test, Nav1.8, mTOR, fine-tuned-vs-zero-shot,
  full Nav family, off-target sanity — is now done. Net result: **no slot in
  the binder-triage stack**.
- **Sharpens the Nav fine-tune case**: there is no off-the-shelf DTI tool
  (MAMMAL or ConPLex) we can swap in for ion channels. Quiver Nav data is the
  only lever. Boltz-2 (different architecture: co-folding + affinity) remains
  the one unknown.

## Caveats

- ConPLex truncates target sequences with its own cap (different code path
  from MAMMAL's 1250 aa, but every Nav is > 1700 aa so all are truncated by
  every tool in this comparison).
- 7 binders vs 4 decoys per paralog → small n; per-paralog CIs are wide.
  Conclusion rests on the *consistency across 9 paralogs* (mean 0.437,
  max 0.50), not any single number.
- Pure protein-name lookup for SMILES via PubChem — `vixotrigine` is a
  reasonably uncommon drug; if the SMILES it resolved to differs from the
  literature reference compound, the +0.13 lean could be smaller still. The
  qualitative finding (ibuprofen > suzetrigine on Nav1.8) is robust to this.
- ConPLex emits a probability, not a calibrated pKd; absolute values are not
  comparable to MAMMAL's pKd numbers. We compare only by rank (AUROC) and
  within-model deltas.
