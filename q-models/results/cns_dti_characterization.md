# CNS-broad DTI benchmark — does binder-triage hold across CNS, or just Nav1.8? (2026-06-15)

The Track-2 verdict rested on a tiny **n=11 Nav1.8** panel (+ n=7 mTOR). This benchmark de-anecdotes it:
**BALM (cosine) + PLAPT (affinity) scored on 19 CNS targets across 4 families**, public actives (ChEMBL
pChEMBL≥6, ≤60/target) vs decoys (same-target inactives, else property-matched), binder-vs-decoy AUROC,
aggregated **by family**. g5.xlarge, ~45 min, ~$0.75. (RHEB + KCNQ2 auto-dropped: <30 public actives.)

## Verdict: **Off-the-shelf binder-triage is a KINASE / mTOR-pathway tool, NOT a general CNS tool — and on ion channels (Quiver's core) it is at CHANCE as a family. The Nav1.8 0.857 was a small-panel over-read; it does not generalize.**

### Per-family mean AUROC (the headline)
| Family (targets) | BALM | PLAPT | read |
|---|---|---|---|
| **Kinase** (GSK3B, LRRK2, BACE1) | **0.798** | 0.770 | ✅ reliable |
| **mTOR pathway** (MTOR, AKT1, PKM2, PPARD, S6K1) | **0.722** | 0.739 | ✅ usable |
| GPCR (DRD2, HTR2A) | 0.577 | 0.664 | ⚠️ mediocre |
| **Ion channel** (9 × SCN/CACNA/GRIN) | **0.499** | **0.501** | ⛔ **chance** |
| overall (19) | 0.613 | 0.623 | family-dependent |

### Per-target — ion channels are bimodal, which is why the family averages to chance
| target | family | BALM | PLAPT | seq (trunc>1024) |
|---|---|---|---|---|
| MTOR | mTOR | 0.825 | 0.821 | 2549 ✂️ |
| AKT1 / PKM2 / PPARD | mTOR | 0.73 / 0.76 / 0.70 | 0.80 / 0.84 / 0.61 | — |
| GSK3B / BACE1 / LRRK2 | kinase | 0.81 / 0.82 / 0.77 | 0.65 / 0.86 / 0.80 | LRRK2 2527 ✂️ |
| **SCN9A (Nav1.7)** | ion ch | **0.845** | 0.659 | 1988 ✂️ |
| **SCN10A (Nav1.8)** | ion ch | **0.780** | 0.480 | 1956 ✂️ |
| SCN2A (Nav1.2) | ion ch | 0.710 | 0.719 | 2005 ✂️ |
| SCN8A (Nav1.6) | ion ch | 0.556 | 0.503 | 1980 ✂️ |
| SCN5A (Nav1.5) | ion ch | 0.459 | 0.429 | 2016 ✂️ |
| SCN1A (Nav1.1) | ion ch | **0.292** | 0.647 | 2009 ✂️ |
| GRIN1 / GRIN2B (NMDA) | ion ch | 0.32 / 0.33 | 0.41 / 0.35 | — |
| **CACNA1C (Cav1.2)** | ion ch | **0.204** | 0.307 | 2221 ✂️ |
| DRD2 / HTR2A | gpcr | 0.50 / 0.65 | 0.61 / 0.72 | — |

- **Ion channels split into "works" and "chance/inverted":** BALM is good on Nav1.7/1.8/1.2 (0.71–0.85) but
  **at or below chance on Cav1.2 (0.20), NMDA (0.32–0.33), Nav1.1 (0.29), Nav1.5 (0.46)**. Averaged over the
  family = **0.50**. You cannot say "BALM does ion channels" — it does *some sodium channels* and fails the rest.
- **Nav1.8 on the proper 60-active panel: BALM 0.78** (PLAPT collapses to 0.48). So the old 0.857 was
  optimistic-but-not-fiction for BALM — but it's a single lucky target inside a family that's otherwise chance.

### Why
1. **Training-data distribution.** BALM/PLAPT are BindingDB-pretrained, which is **kinase/GPCR-rich and
   ion-channel-poor** — so they generalize where the data lives (kinases 0.80, mTOR/kinase-like 0.72) and
   collapse where it's sparse + the pharmacology is state/use-dependent (Cav, NMDA, most Navs).
2. **Sequence truncation contributes but isn't decisive.** Every ion channel (1956–2221 aa) is truncated to
   BALM's 1024-token cap (✂️) — losing the pore/binding domains. But MTOR (2549) and LRRK2 (2527) are
   *also* truncated and score 0.83/0.77, so truncation compounds the data-distribution problem rather than
   being the sole cause.

## Implications
- **Scorecard Track 2 reframed:** BALM/PLAPT are **reliable CNS-kinase + mTOR-pathway binder-triage**
  (0.72–0.80) and **mediocre on GPCRs**; they are **NOT a trustworthy ion-channel triage tool** (family
  mean 0.50 — usable only on Nav1.7/1.8/1.2, unusable on Cav/NMDA/Nav1.1/1.5). Use them for kinase/mTOR CNS
  targets; do **not** rely on them for ion channels off-the-shelf.
- **This is the sharpest justification for a Quiver-data fine-tune, and it re-points it:** the public models
  are at **chance** on the CNS ion-channel family — there is nowhere to go but up, and no public substitute.
  The fine-tune data that matters most is **ion-channel** screening data (Nav/Cav/NMDA, with inactives),
  *not* kinases (already solved off-the-shelf). Cav1.2 and NMDA (sub-chance) are the biggest open gaps.
- Boltz-2 (co-fold) remains the structure route; it isn't in this seq-DTI benchmark.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/cns_dti/cns_dti_result.json` (per-target +
per-family AUROC, decoy sources, seq-truncation flags); eval `aws/cns_dti_benchmark_eval.py`; instance
`i-0e2f50c1be417265a` self-terminated; no strays.
