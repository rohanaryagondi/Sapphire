# Off-target sanity check — does MAMMAL's DTI head encode ANY specificity?

**NEXT_STEPS item 1a (Graham's promised off-target check), restricted to UBE3A.**
Run: `experiments/offtarget_ube3a.py` · raw: `results/offtarget_ube3a_20260607_005109.json` · 2026-06-07.

## The question (decision rule)

The on-target signal is suzetrigine → Nav1.8 (SCN10A) ≈ 7.6, BUT the head was already shown to give
**no binder-vs-decoy separation** on Nav1.8 (decoys score ~7.6 too, `results/phase2b_quiver_targets.md`).
Graham's test: score the Nav1.8 drugs against a totally unrelated off-target (**UBE3A**, an E3 ubiquitin
ligase with no known affinity for these compounds). Does the predicted pKd drop?

- UBE3A also comes back **~7** → the head predicts "binds" for everything → no specificity, useless as a triage gate.
- UBE3A comes back **much lower (~2–4)** → "there's something in there" → enriching, just not precise.

## Setup

- **Checkpoint:** PEER (`models/dti_bindingdb_pkd_peer`), the correct one for our problem classes.
- **Norm constants (PEER, required):** 6.286291085593906 / 1.5422950906208512. Defaults are for the wrong (cold-split) checkpoint.
- **Drugs:** suzetrigine + vixotrigine (Nav1.8 blockers) + metformin / caffeine / ibuprofen (background = random small molecules).
- **Targets:** UBE3A (Q05086, **875 aa — FITS the 1250-aa cap, NO truncation penalty**), Nav1.8 (Q9Y5Y9, 1956 aa — on-target, truncated to 1250), TUBB tubulin beta (P07437, 444 aa, fully visible — secondary off-target).

**Vixotrigine SMILES used:** `C1C[C@H](N[C@H]1C2=CC=C(C=C2)OCC3=CC=CC=C3F)C(=O)N`
(PubChem CID 16046068; rdkit formula **C18H19FN2O2**, MW 314.4; IUPAC (2S,5R)-5-[4-[(2-fluorophenyl)methoxy]phenyl]pyrrolidine-2-carboxamide).
**Provenance note:** all four aliases (vixotrigine / BIIB074 / raxatrigine / GSK1014802) resolve to the
same CID and the same formula, which matches DrugBank and ChEMBL (CHEMBL2105708): vixotrigine is
**C18H19FN2O2, MW 314.36, one fluorine**. The task spec's expected "C₁₆H₁₆F₂N₂O₂, MW≈322 (two F)" is
**incorrect** — it does not describe vixotrigine; we verified against the authoritative formula instead.

## Results — pKd matrix

| drug | UBE3A (off, full) | Nav1.8 (on, trunc) | TUBB (off, full) |
|---|---|---|---|
| **suzetrigine** | 6.48 | **7.01** | 6.74 |
| **vixotrigine** | 6.37 | **7.69** | 6.70 |
| metformin (bg) | 5.71 | 6.47 | 6.06 |
| caffeine (bg) | 5.91 | 6.96 | 6.08 |
| ibuprofen (bg) | 6.76 | 7.60 | 6.82 |

Whole-matrix pKd spread: **min 5.71, max 7.69, range 1.99**. Every cell — including all three random
background molecules against all three targets — falls in a narrow ~5.7–7.7 band.

## On-target − off-target deltas (the answer)

| Nav1.8 drug | Nav1.8 (on) | UBE3A (off) | Δ (Nav−UBE3A) | TUBB (off) | Δ (Nav−TUBB) |
|---|---|---|---|---|---|
| suzetrigine | 7.01 | 6.48 | **+0.53** | 6.74 | +0.26 |
| vixotrigine | 7.69 | 6.37 | **+1.32** | 6.70 | +0.99 |

## Verdict

**The head encodes essentially NO target specificity.** UBE3A does NOT drop to the ~2–4 "non-binder"
range Graham flagged as the good outcome — it comes back at **6.4–6.5 pKd** (Kd ≈ 0.3–0.4 µM, i.e.
"binds") for drugs it has no business binding. And this is the case **without a truncation excuse**:
UBE3A (875 aa) and TUBB (444 aa) are fully visible, yet still score ~6–7. The random background molecules
(metformin, caffeine, ibuprofen) score 5.7–7.6 against every target — the same band as the real Nav1.8
drugs. **The head emits ~6–7 for everything**, so a high pKd alone carries no information that a compound
actually binds the queried protein.

The one shred of structure: the on-target deltas are positive (suzetrigine +0.53, vixotrigine +1.32 vs
UBE3A), and Nav1.8 runs slightly hotter overall (every drug, including caffeine, scores highest against
Nav1.8). So there is a faint, sub-pKd-unit lean in the right direction — "something in there" — but it is
(a) tiny relative to the ~2-pKd background spread, (b) confounded by Nav1.8 being the one target that's
truncated/different, and (c) smaller than the drug-to-drug noise (ibuprofen out-scores suzetrigine
against UBE3A). It is not a usable specificity signal.

**One line:** No — off the shelf the MAMMAL DTI head does not encode usable target specificity; it scores
~6–7 pKd for everything (Nav drugs and random molecules alike, on-target and off-target alike), with only
a faint sub-unit on-target lean (suzetrigine Nav−UBE3A +0.53, vixotrigine +1.32) that's swamped by the
~2-pKd background. Consistent with Phase 1/2b: soft cross-target re-ranking at best, never single-target binder triage.
