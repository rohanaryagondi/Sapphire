# Boltz-2 on CNS ion channels — DEFERRED (not run on AWS), 2026-06-15

Phase 1b of the overnight CNS campaign was to co-fold Boltz-2 on the hard ion channels (Cav1.2, NMDA/GRIN,
Nav1.5) where sequence-DTI is at chance. **After reading the `boltz` branch's comprehensive Boltz-2
documentation (`results/aws_eval/boltz_nav_eval.md`), this run is deferred — it is partly redundant and not
viable on affordable AWS GPUs.** No AWS spend incurred (caught before launch).

## Why deferred
1. **Toolchain in the draft `aws/boltz_cns_userdata.sh` is wrong** (it used the stale handoff recipe). The
   boltz branch's §11 establishes: `cuequivariance-ops-cu13-torch` **does not exist** (cu12 only); the
   handoff verify line is a lazy-import false-positive; PyPI default torch is cu130 (won't run on driver
   570 — needs cu128); the cu12 kernels crash at runtime → **must run `--no_kernels`** (pure-PyTorch).
2. **Full-length channels need a 141 GB H200.** With `--no_kernels`, ~2000-aa proteins OOM a 32 GB Ada, so
   the prior Nav1.8 (1956 aa)/mTOR (2549 aa) co-folds ran on Bouchet's **H200 141 GB** (`gpu_devel`). Our
   AWS g5.2xlarge (A10G 24 GB) would OOM every big channel (Cav1.2 2221 aa, Nav1.5 2016 aa). An H200-class
   AWS instance (p5e) is ~$30–40/hr — far over the $45 cap.
3. **Already done.** The boltz branch already co-folded the Nav family + mTOR (see "Existing Boltz-2
   results" below), so re-running Nav1.5/Nav1.8 here adds nothing.

## Existing Boltz-2 results (Bouchet H200, 2026-06-08 — `results/aws_eval/boltz_nav_eval.md`)
| Test | Target | AUROC | Read |
|---|---|---|---|
| B (headline) | Nav1.8 binder-vs-decoy | **0.714** (n=11, p=0.16) | marginal; first off-the-shelf > chance |
| E | Nav1.8 / Nav1.7 / Nav1.5 | **0.75 / 0.71 / 0.75** | separation reproduces across paralogs |
| D | mTOR | **1.000** (p=0.029) | decisive — co-folding's home turf |
| C | suzetrigine × 9 Nav paralogs | Nav1.8 #1 (0.440) | correct rank, **soft** (0.31–0.44 spread; Nav1.5 mid-pack) |
| off-target | Nav drugs × UBE3A/TUBB | binders > off-targets, decoys flat | target-aware but **soft** (A-803467 leaks ~0.46) |

**Read:** Boltz-2 is strong where structural precedent exists (mTOR/kinases 1.000), a real but marginal
step up on Nav (0.71–0.75), target-conditioned but with soft selectivity + low absolute binder
probabilities — a coarse "Nav-blocker-like?" pre-filter, not a confident selective-triage oracle.

## The genuinely-NEW question (Cav1.2, NMDA) — how to answer it properly
Boltz never covered **CACNA1C (Cav1.2)** or **GRIN/NMDA** — the channels where seq-DTI is *below* chance
(0.20 / 0.32). Whether co-folding beats chance there is open. To answer it without a $30/hr H200:
- **Domain-construct route (recommended):** co-fold the ~250–500-aa pore/selectivity-filter domain (not
  the full ~2000-aa channel) → fits a 24 GB GPU on `--no_kernels`, fast, and is how selective small
  molecules bind anyway. Requires defining the pore-domain windows per channel (structural curation).
- **Or coordinate with the `boltz` lane / Bouchet H200** (free academic, the proven Boltz environment) for
  full-length Cav1.2/NMDA co-folds.

## Decision
Deferred from the AWS overnight run (toolchain wrong + OOM + redundant). The Nav/mTOR Boltz story is already
captured in the scorecard (Tracks DTI/structure/selectivity = Boltz-2 0.714/1.000). The Cav1.2/NMDA
co-fold is a **domain-construct follow-up or a Bouchet-H200 job**, not a commodity-AWS run. Budget preserved
for the viable phases (truncation test, rejected-DTI re-test, new-model scout, round-out, synthesis).
