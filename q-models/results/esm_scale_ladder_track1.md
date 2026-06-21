# ESM size ladder on Track 1 (gene-family clustering): does scale help?

**Date:** 2026-06-12 · **Branch:** `models` · **Track:** 1 (protein family clustering)
**Question:** ESM-C 600M lost to ESM-2-650M best-vs-best (0.825 vs 0.875), and a 650M-vs-600M
comparison is soft. Does *scale* change the verdict? Run the biggest **commercially-usable**
ESM (ESM-2 15B, MIT) + the 3B mid-point on the 40-gene CRISPR-N panel, identical layer-sweep
protocol, so the whole ladder is best-layer-vs-best-layer comparable.

**One-line answer: NO. Scale does not help.** ESM-2 650M (0.875) ≥ 3B (0.850) ≈ 15B (0.850).
A **23× parameter increase moves nothing** — the panel is saturated at ~0.85–0.875, and the
ceiling is set by the panel's built-in traps, not by model capacity. For Track-1 clustering the
lever is **layer selection, not size**: pick the smallest model (650M, MIT) at its best layer.

---

## The ladder (best-layer-vs-best-layer, identical protocol)

| Model | params | dim | last-layer NN | **best-layer NN** | best idx (of N) |
|---|---:|---:|---:|---:|---|
| ESM-C 600M | 0.6B | 1152 | 0.625 / 0.650 | 0.825 | 5 / 36 |
| **ESM-2 650M** | 0.65B | 1280 | 0.725 / 0.750 | **0.875** | 8 / 33 |
| ESM-2 3B | 3B | 2560 | 0.800 / 0.675 | 0.850 | 33 / 37 |
| ESM-2 15B | 15B | 5120 | 0.750 / 0.775 | 0.850 | 14 / 49 |
| **MAMMAL 458M** | 0.46B | 768 | 0.750 / 0.800¹ | **0.850** | block 8 / 12 |

¹ **MAMMAL now swept too** (`results/mammal_layer_sweep.json`, via encoder-block forward-hooks
in the `mammal` env, local $0). Sanity check passed: the post-norm final hidden state reproduces
the canonical phase5 **0.750** exactly. MAMMAL also benefits from layer selection
(0.750 → 0.850 at block 8) and from centering the final layer (0.750 → 0.800). Best-block
per-family: kinase 1.0, gpcr 1.0, ion_channel 0.875, NR 0.83, e3 0.5.

**Fair best-vs-best verdict (Track 1, complete):** a **4-way near-tie at 0.85–0.875** —
ESM-2-650M 0.875 ≥ MAMMAL 0.850 = ESM-2 3B 0.850 = ESM-2 15B 0.850 > ESM-C 600M 0.825. On
n=40 (±0.025/protein) these are statistically indistinguishable except ESM-C trailing.
**MAMMAL holds its own but shows no embedding-space advantage over open MIT ESM-2-650M** —
consistent with the project spine (the moat is V1-T, not the embedding layer). For ops, pick
**ESM-2-650M (smallest, MIT, nominally best) or MAMMAL 458M (if already in the stack)**, each at
its mid-stack best layer + centering. Don't pay for 3B/15B; ESM-C is the only one to avoid here.

Raw: `results/esm2_big_layer_sweep.json` (+ `…_run.log`), `results/esm2_layer_sweep.json`,
`results/esmc_layer_sweep.json`. Compute: ESM-2 3B+15B on a g6.12xlarge (4× L4) in ~110 s of
GPU work, ~$0.55; ESM-C + 650M ran locally for $0. Total session AWS spend ≈ $0.57.

**n=40 caveat up front:** one protein flip = 0.025 NN-recall. 0.875 vs 0.850 is **one protein** —
i.e. 650M / 3B / 15B are a statistical wash at ~0.85–0.875. The load-bearing claim is the
*absence of a scaling trend*, not the precise ranking.

## Section A — where the big models earn their keep

At their best layer, **3B and 15B are perfect on the clean structural druggable families**:

| Family | n | 650M | 3B | 15B |
|---|---:|---:|---:|---:|
| kinase | 12 | 1.00 | 0.92 | **1.00** |
| gpcr | 8 | 1.00 | 1.00 | 1.00 |
| ion_channel | 8 | 0.875 | **1.00** | **1.00** |
| nuclear_receptor | 6 | 0.83 | 0.83 | 0.67 |
| e3_ligase | 4 | **0.75** | 0.50 | 0.50 |
| lipid_kinase | 1 | 0.00 | 0.00 | 0.00 |
| phosphatase | 1 | 0.00 | 0.00 | 0.00 |

The one place scale visibly *helps*: **ion channels go 0.875 → 1.00** at 3B/15B — both cleanly
cluster all four Nav paralogs (SCN9A/10A/1A/5A) + KCNQ2/KCNQ5/HCN1/TRPV1, the most
Quiver-relevant family. (But ESM-C 600M also hit ion_channel 1.00, so even that isn't a
scale-only win.)

## Section B — where they fail (identically, regardless of size)

- **e3_ligase ≤ 0.50 and singletons = 0.00 at every scale.** 15B does *no better* than 650M on
  the heterogeneous/functional families. The 650M is actually **best on e3_ligase (0.75)** —
  the only model to crack 3 of 4 — which 3B and 15B *regress* on. Scale doesn't buy function-level
  grouping; if anything the bigger models over-commit to fold homology.
- **No overall lift from 23× params.** 650M 0.875 ≥ 3B 0.850 = 15B 0.850. Flat-to-down.
- **Last-layer is still a trap at scale** (3B 0.675 centered, 15B 0.775) — confirms the
  layer-selection finding holds for every size: never use the final layer's mean-pool.

## Section C — the architectural reason (scale-invariant)

**The 40-gene panel is saturated at ~0.85–0.875, and the ceiling is the panel's design, not
model capacity.** Two structural facts cap it:
1. **Two n=1 families** (PIK3CA lipid_kinase, PTEN phosphatase) can *never* score a same-family
   nearest neighbour — they are auto-fails. That alone caps max NN-recall at **0.90 (36/40)**.
2. **Functional-not-fold groups.** The "e3_ligase" label spans RING/HECT/U-box architectures;
   "nuclear_receptor" includes TP53 (a TF) and the panel mislabels RARA (a real NR) as an E3.
   Sequence embeddings cluster by **fold/catalytic-domain homology**, so these groups are
   unclusterable *by any sequence model at any size* — 650M, 3B, 15B, and ESM-C all hit the
   same wall (e3 ≤ 0.5, NR 0.67–0.83).

So once a model is "big enough" to resolve fold homology (≈650M already is — kinase/GPCR/ion-channel
all ≈1.0), more parameters add nothing on this task. The residual error is **irreducible given
the panel**, not a capacity gap. Bigger ESM-2 spends its extra capacity on within-fold detail the
family-clustering metric doesn't reward.

A secondary architectural note: **best-layer depth is model-specific** (650M idx 8/33 ≈ 24 %,
15B idx 14/49 ≈ 29 %, ESM-C layer 5/36 ≈ 14 %, but 3B idx 33/37 ≈ 89 %). You cannot assume a
fixed depth fraction — each model needs its own quick sweep to find the family-separable layer.

## Section D — best-fit Quiver use case + cost

- **Use ESM-2-650M at its best layer (idx 8) + mean-center.** It is the **smallest, cheapest,
  MIT-licensed**, and (within noise) **best** option for Track-1 gene-family clustering. Paying
  for 3B/15B buys nothing on this task; ESM-C 600M is strictly worse and more license-restricted.
- **Cost-per-inference:** 650M runs on a laptop CPU for $0 (40 genes in ~60 s). 15B needs a
  multi-GPU box (4× L4, ~$4.60/hr) for no quality gain — a clear "don't."
- **When scale *might* matter:** the full **1,400-gene** CRISPR-N panel, where the singleton/
  mislabel traps are diluted and real family resolution at fine grain could separate the models.
  Re-test the ladder there before treating any of this as final. On the **40-gene** panel the
  question is answered: **size is not the lever.**

## Open follow-up

- **MAMMAL layer sweep: ✅ DONE** (2026-06-12, `results/mammal_layer_sweep.json`) — best block 8
  = 0.850, ties the big ESM-2s, no advantage over ESM-2-650M's 0.875. Track-1 best-vs-best is
  now settled (4-way tie at the saturation ceiling).
- **Full 1,400-gene CRISPR-N panel** is the one place left where scale/model could still
  separate (the 40-gene panel is saturated by its design traps). Needs the real accession list
  (Caitlin/KG). Until then, Track 1 is **closed at "ESM-2-650M or MAMMAL, layer-selected."**

## Bottom line for the scorecard

- **Scale tested and rejected as a Track-1 lever** (ESM-2 650M ≈ 3B ≈ 15B ≈ 0.85–0.875).
- **Recommendation stands: ESM-2-650M + layer selection + centering** is the Track-1
  embedding of choice among open models; don't buy bigger, don't switch to ESM-C.
- The decision-relevant numbers all come from a saturated 40-gene panel; the 1,400-gene
  re-test + the MAMMAL sweep are the two things that could still move the verdict.
