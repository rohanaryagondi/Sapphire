# AdaMBind — Track-2/3 few-shot DTI displacer test (scout campaign Phase 4, 2026-06-14)

**Question:** AdaMBind is a MAML meta-learning DTA model whose pitch is **few-shot cold-start** — adapt to a
new target from k≈5 labeled pairs. That's exactly the prior-art for our Nav fine-tune. Does it beat
**BALM** (Nav1.8 0.857 / mTOR 1.000) and **Boltz-2** (0.714 / 1.000) on our binder-decoy panels after k=5
adaptation? Repo: github.com/Moohyun-w/AdaMBind. Eval: `aws/adambind_eval.py`, g5.xlarge, meta-trained
on-instance from PyTDC BindingDB_Kd (no weights shipped).

## Verdict: **NOT adoptable, and the few-shot claim could not be tested — its adaptation path is broken by an upstream bug. Zero-shot (no adaptation) is at chance on our targets. BALM + Boltz-2 remain the Track-2/3 winners.**

## Results
| Mode | Nav1.8 (n=11) | mTOR (n=7) | vs BALM | vs Boltz-2 |
|---|---|---|---|---|
| **Zero-shot** (meta-init, no adapt) | AUROC **0.429** | **0.500** | 0.857 / 1.000 | 0.714 / 1.000 |
| **Few-shot k=5** (the actual claim) | **FAILED** (0/8 repeats) | **FAILED** (0/8) | — | — |
| Meta-training | **FAILED** | — | — | — |

- **Zero-shot** ran cleanly and is **chance / below-chance** (Nav1.8 0.43, mTOR 0.50) — expected for an
  un-adapted MAML initialization, and far below BALM/Boltz-2. Zero-shot was never the selling point.
- **Few-shot k=5 and meta-training both crash** with the *same* upstream error, on every one of the 8
  stratified repeats per target:
  ```
  UnboundLocalError: local variable 'y' referenced before assignment
  ```
  Origin: AdaMBind's own `model/Trainer.py` `train()` (the MAML inner/outer loop), reached via the exact
  documented API (`trainer.train(net, args, it, [task], F_data, update=0/1)`, mirroring their `train.py`).
  It fires in both the `update=0` inner-adapt path (used by few-shot scoring) and the `update=1`
  meta-update path — so **no adaptation happens at all**. This is a bug in the repo's training code under
  our task setup, not in our shim (our `build_dataset` goes through their `TestbedDataset` /
  `create_data` featurizer, and zero-shot inference through the same net works fine).

## Why this is a bank, not a fixable fight
- **License: none.** The repo ships **no LICENSE file** → all-rights-reserved → **research/eval only, not
  adoptable** regardless of accuracy. Even a perfect few-shot number couldn't ship.
- **The blocker is upstream.** Fixing it means debugging their `Trainer.py` on-instance (read their loop,
  find where `y` is conditionally bound, patch, re-upload) — an open-ended fight on unlicensed code whose
  best-case payoff is a non-adoptable datapoint. Not worth a parallel slot or the budget.
- **The cold-start lesson stands on its own.** Our Nav fine-tune plan (fine-tune `base_458m` on Quiver
  binders + matched decoys, **scaffold-held-out** split) does not depend on AdaMBind working. If we want a
  published few-shot DTA baseline to compare against, BALM's cosine-retrieval (already 0.857 on Nav1.8,
  Apache-2.0) is the better-licensed, already-working reference.

## Scorecard impact
**None.** Track 2/3 stays **Boltz-2 + BALM-triage**. AdaMBind filed as: *non-adoptable (no license);
few-shot adaptation blocked by an upstream `Trainer.py` bug; un-adapted zero-shot is chance-level on our
panels — does not challenge BALM/Boltz-2.*

## Receipts
- Result: `s3://rohan-mammal-bootstrap-20260610-213029/adambind/adambind_result.json`
  (zero-shot AUROCs + 8×2 `UnboundLocalError` few-shot traces).
- Eval: `aws/adambind_eval.py`. Instance `i-0cc109345e61ae875` ran rc=0 (per-section guards caught the
  upstream crash) and self-terminated; no strays. Spend ~$0.4.
