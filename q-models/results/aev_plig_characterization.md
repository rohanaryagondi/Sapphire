# AEV-PLIG — Track-9 affinity re-scorer on Quiver Nav1.8 + mTOR (2026-06-14)

Does AEV-PLIG (oxpig, GATv2 FEP-surrogate re-scorer, BSD-3, weights in-repo) help score binders on our
Quiver targets? **Setup:** g5.xlarge; the eval attempts to manufacture poses (smina-dock or RDKit
conformer into the apo AlphaFold model) since we have no holo structures, then re-scores. ~$0.5 over 2
runs (run1 = a userdata apt bug, fixed; run2 ran clean).

## Verdict: **Pose-gated and unusable on Quiver's no-holo targets — n_scored = 0/18. Same failure mode as GatorAffinity and DrugCLIP. BALM/PLAPT (sequence) + Boltz-2 (co-fold) remain the Track-2/3/9 tools.**

- **AEV-PLIG requires a 3D bound protein-ligand complex** (CSV of `{sdf docked pose, pdb protein}`) — there
  is **no sequence+SMILES path**. We have zero holo structures / co-crystal poses for the panel compounds.
- The eval's pose-manufacturing step **failed before any scoring**: `structure/pocket prep failed: HTTP
  Error 404` — the apo **AlphaFold model download 404'd** (the AF EBI URL/version moved, the same
  v4→v6-style breakage seen in prior campaigns). Result: **Nav1.8 0/11 scored, mTOR 0/7 scored.**
- Even had the AlphaFold fetch succeeded, the scorer would be docking ligands into an **apo** channel with
  no holo reference — an asterisked "sanity floor," not a real evaluation. So fixing the 404 to obtain an
  apo-docked number is **low value and was not pursued** (would not change the verdict).

## Why this is a (useful) negative result
This is the **third** structure-based affinity scorer to fail on Quiver's no-holo targets — after
**DrugCLIP** and **GatorAffinity** (both pose/pocket-quality-gated, scored 0 usable pairs). The pattern is
now firmly established for the scorecard:

> Off-the-shelf structure-based DTI/affinity scorers (DrugCLIP, GatorAffinity, AEV-PLIG) need
> crystal-quality pockets + bound poses that Quiver's data-poor targets don't have. The only structure
> route that works is **Boltz-2**, because it *co-folds the complex itself* rather than consuming a
> pre-existing pose. For everything else, **sequence-based** models (BALM 0.857, PLAPT 0.75 on Nav1.8) are
> the practical tools.

## Scorecard impact
**None to the winners.** Track 9 / structure-based scoring: AEV-PLIG filed alongside DrugCLIP + GatorAffinity
as **pose-gated, not landable on no-holo Quiver targets.** Track-2/3 stack unchanged: BALM/PLAPT triage →
Boltz-2 co-fold.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/aev_plig/aev_plig_result.json` (n_scored=0,
skip_reason = AlphaFold 404); eval `aws/aev_plig_eval.py`; instances `i-06a0b42a2db170f98` (run1, apt bug)
+ `i-01198369c97c6b4e4` (run2) self-terminated; no strays.
