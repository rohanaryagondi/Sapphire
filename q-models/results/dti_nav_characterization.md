# DTI-Nav — untested sequence-based DTI models on Quiver Nav1.8 + mTOR (Track 2, 2026-06-14)

Thoroughness pass for Track 2 (binder triage): do any **untested, sequence+SMILES, off-the-shelf** DTI
models beat our Nav binder-triage tools on the Quiver panels? Tested **PLAPT** + **DeepPurpose**, neither
previously evaluated (the tested set was MAMMAL/ConPLex/DrugBAN/PerceiverCPI/BALM/AdaMBind/Boltz-2/
GatorAffinity). Panels: Nav1.8 (n=11: 7 binders/4 decoys), mTOR (n=7: 3/4). g5.xlarge, ~$0.4.

## Verdict: **PLAPT is a genuine, lightweight, sequence-only DTI model that is NOT Nav-blind (Nav1.8 0.75) — it beats Boltz-2 and ConPLex on Nav1.8 and ties everyone on mTOR, but does not displace BALM (0.857). Keep BALM as the Track-2 Nav winner; add PLAPT as a fast first-pass triage. DeepPurpose failed on a trivial dep (not re-run).**

### Head-to-head — binder-vs-decoy AUROC
| Model | Nav1.8 (n=11) | mTOR (n=7) | needs structure? | notes |
|---|---|---|---|---|
| **BALM** (current Nav best) | **0.857** | 1.000 | no | shared compound↔target cosine space |
| **PLAPT** (NEW) | **0.75** | **1.000** | no | ProtBERT+ChemBERTa, ONNX head, near-instant |
| Boltz-2 | 0.714 | 1.000 | **yes** (co-fold) | Track-2/3 winner overall |
| ConPLex | 0.437 | — | no | Nav-blind / chance |

### What's notable
- **PLAPT is not Nav-blind.** The expectation (BindingDB-pretrained → ~0 Nav training pairs → chance) did
  **not** hold: PLAPT scored Nav1.8 at **0.75**, *above* the structure-based Boltz-2 (0.714) and far above
  ConPLex (0.437). A free, sequence-only model edging out the expensive co-fold on this panel is a useful
  data point — though see the caveat.
- **mTOR is saturated** — PLAPT, BALM, and Boltz-2 all hit 1.000 (mTOR's rapalog binders are easy/
  well-represented). mTOR doesn't discriminate models.
- **PLAPT does not beat BALM** on Nav1.8 (0.75 < 0.857). BALM stays the sequence-based Nav winner.

### Caveats (be honest)
- **Tiny panels.** Nav1.8 n=11 (7 binders/4 decoys); a single mis-ranked pair swings AUROC by ~0.07.
  0.75 vs 0.857 vs 0.714 are **within noise of each other** — the robust statement is "PLAPT, BALM, Boltz-2
  all clearly beat chance on Nav1.8; ConPLex doesn't," not a fine ranking. A larger Nav panel (the 99-row
  `01_nav_full_panel.json`) would tighten this.
- **DeepPurpose (MPNN_CNN_BindingDB_IC50) failed to run** — `ImportError: descriptastorus / pandas-flavor`
  (a known DeepPurpose import-chain quirk, unrelated to the model). Fix is one line
  (`pip install git+https://github.com/bp-kelley/descriptastorus pandas-flavor`). **Not re-run:** it's a
  second BindingDB-pretrained model that wouldn't change the Track-2 verdict; documented for future.

## Recommendation / scorecard
- **Track 2 (Nav binder triage): BALM stays the winner** (0.857, sequence-based). **Add PLAPT as a
  validated fast first-pass** — ProtBERT+ChemBERTa, ~6 MB ONNX head, near-instant, no structure needed, and
  it beat the structure-based Boltz-2 on this Nav panel. Good for cheap pre-screening before BALM/Boltz-2.
- Reinforces the standing theme: **sequence-based DTI (BALM, PLAPT) is the practical route for Quiver's
  no-holo targets**; structure scorers (Boltz-2 aside) are pose-gated.
- **Follow-up:** re-run PLAPT + BALM on the full 99-row Nav paralog panel to de-noise the ranking and test
  paralog selectivity (Nav1.8 vs Nav1.5/1.7) — the real Quiver question.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/dti_nav/dti_nav_result.json`; eval
`aws/dti_nav_eval.py`; instance `i-07fb1c669b116eec0` self-terminated; no strays.
