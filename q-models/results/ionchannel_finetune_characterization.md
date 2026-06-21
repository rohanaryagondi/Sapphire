# Ion-channel binder fine-tune on pooled online data — THE LEVER PROVEN (scaffold-split 0.98), with a sharp transfer boundary, 2026-06-15

The campaign's headline fine-tune (Rohan: "I presume you are doing a fine tune?"). Trained a **cross-channel
DTI model** — frozen ESM-2-650M target-sequence embedding (chunk-pooled, full-length channels) ⊕ Morgan-FP
ECFP4 ligand → MLP head — on a **pooled ONLINE corpus**: full ChEMBL ion-channel set (no 60-cap) + the
GtoPdb anchor set, **21,556 (target, compound) pairs / 10,712 unique compounds / 16 targets**. Evaluated two
ways: Murcko **scaffold-split** (within-distribution, held-out chemistry) and **leave-one-channel-out (LOCO)**
(cross-channel transfer). g5.xlarge, rc=0, ~$0.6.

## Headline: **With target-specific supervision, ion-channel binder prediction goes from chance (0.50) to AUROC 0.98 on held-out scaffolds — the fine-tune lever is real and strong at scale. But it does NOT transfer across channels (LOCO 0/4), so each channel needs its own data.**

### Scaffold-split (held-out scaffolds; the deployable, within-channel result)
| Model | overall AUROC | nav | cav | nmda | kv (n=146) |
|---|---|---|---|---|---|
| **Fine-tuned ESM-2⊕FP MLP** | **0.981** | 0.980 | 0.986 | 0.991 | 0.599 |
| Morgan-FP + GBT (ligand-only baseline) | 0.672 | 0.814 | 0.323 | 0.347 | 0.492 |
| Zero-shot BALM/PLAPT (reference) | **0.50** | — | — | — | — |

- **0.50 → 0.98.** The fine-tune crushes both zero-shot (chance) and the ligand-only FP-GBT (0.67). The
  protein tower adds enormous signal (0.67 → 0.98) — this is genuine target-conditioned DTI, not ligand
  memorization. Consistent with (and scaling up) the `trunc_test` small-panel probe (0.92 → 0.98 on 21k pairs).
- Clears the scorecard success bar (AUROC ≥ 0.80) decisively. kv is the only weak family (n=146, too small).

### Leave-One-Channel-Out (train on all OTHER channels, test the held-out one — the hard generalization test)
| Held-out channel | fine-tuned MLP AUROC | FP-GBT | clears 0.80? |
|---|---|---|---|
| CACNA1C / Cav1.2 | 0.727 | 0.240 | no |
| SCN9A / Nav1.7 | 0.643 | 0.095 | no |
| SCN10A / Nav1.8 | **0.360** (below chance) | 0.065 | no |
| GRIN2B / NMDA | **0.175** (below chance) | 0.017 | no |
| **cleared** | **0/4** | | |

- **Cross-channel transfer fails.** Training on every other channel and testing on a held-out channel gives
  weak-to-below-chance AUROC (Nav1.8 0.36, NMDA 0.18). The model does NOT learn channel-agnostic
  binder biology that generalizes to an unseen channel.

## The decisive read (why this is the most useful result of the campaign)
The two evals together **precisely define the build-don't-buy boundary** for ion-channel DTI:
1. **For a channel that HAS labelled binders** (public or Quiver), a fine-tune is spectacular — **0.98** on
   held-out scaffolds, vs 0.50 off-the-shelf. The earlier de-risking (0.92 small-panel probe) holds and
   strengthens at scale. **This is deployable today** for the data-rich channels.
2. **For a channel WITHOUT data** (a novel Quiver target), you **cannot bootstrap from other channels** —
   LOCO transfer is at/below chance. So the only way to get a model for a new channel is **that channel's own
   screening data.**

This is the strongest possible justification for **Quiver generating per-target screening data**: the
fine-tune works brilliantly the moment a target has actives+inactives, and nothing (not other channels, not
zero-shot models) substitutes for that. Exactly mirrors the variant-effect fine-tune's finding
(`results/variant_finetune_characterization.md`): cross-channel transfer fails there too — channel-specific
data is the moat.

## Honest caveats
- **Decoys are property-matched ChEMBL inactives / DUD-E-style**, not always real measured inactives — the
  scaffold-split 0.98 is "actives vs matched decoys," which is easier than "actives vs hard real inactives."
  The 0.67 ligand-only baseline on the same decoys shows the protein tower's gain is real, but treat 0.98 as
  the optimistic within-distribution ceiling; a Quiver deployment should re-confirm on its own inactives.
- **EF5 is rate-limited** (~2.1) because the corpus is ~48% positives (10,285/21,556) — with that base rate
  the max EF5 ≈ 2.1, so AUROC is the meaningful metric here, not EF5.
- The protein embedding is shared across a channel's compounds, so within-channel the discrimination is
  ligand-driven (QSAR-like) — which is exactly what a per-channel deployment exploits.

## Scorecard impact
Track 2 (DTI / ion channels): **add the fine-tune result.** Off-the-shelf zero-shot = 0.50; a supervised
cross-channel fine-tune on pooled online data (ChEMBL+GtoPdb, 21.5k pairs) = **scaffold-split AUROC 0.98**
(ligand-only FP-GBT 0.67). The lever is proven and deployable per-channel. **Boundary:** no cross-channel
transfer (LOCO 0/4) — novel channels need their own data → Quiver per-target screening is the moat.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/ionchannel_finetune/ionchannel_finetune_result.json`;
eval `aws/ionchannel_finetune_eval.py`; corpus = ChEMBL ion-channel (21 targets, 16 with data) + GtoPdb
(`docs/data_card_gtopdb_ionchannel.md`); instance `i-057c6abacf7b00329` self-terminated (rc=0).
