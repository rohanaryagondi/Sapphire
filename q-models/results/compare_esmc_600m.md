# ESM-C 600M (EvolutionaryScale) on the 40-gene CRISPR-N panel — Track 1

**Date:** 2026-06-12 · **Branch:** `models` · **Track:** 1 (protein family clustering)
**Question (Q3 punchlist #1):** is ESM-C 600M a drop-in **upgrade** over ESM-2-650M for
Quiver's gene-family clustering? Success criterion from the scorecard: **NN-recall ≥ 0.80**
on the 40-gene CRISPR-N panel (vs the MAMMAL ≈ ESM-2 tie at 0.750).

**One-line verdict:** **No — do not adopt ESM-C for Track 1.** It is *not* an upgrade.
The real finding is methodological: **layer selection, not model choice, is the dominant
lever** — and once both ESM models are read out at their best layer, **ESM-2-650M wins
(0.875) and ESM-C loses (0.825).** ESM-C also ships the worst possible default: its obvious
`return_embeddings` output scores **0.625**, a textbook false negative.

Cost: **$0** (ran locally on CPU in ~60 s; ESM-C 600M is *not* HF-gated). This is a positive
deviation from the scorecard's planned $0.30 g5 run — no AWS was needed.

> **Follow-up done (2026-06-12):** the "is 650M an unfair comparison?" question was answered by
> running the biggest commercially-usable ESM (ESM-2 3B + 15B) on the same panel —
> `results/esm_scale_ladder_track1.md`. Verdict: **scale doesn't help** (650M 0.875 ≥ 3B 0.850 ≈
> 15B 0.850); the panel is saturated. So ESM-C still loses, and bigger ESM-2 isn't worth it either.

---

## TL;DR table

| Model | recipe | NN-recall | clears 0.80? |
|---|---|---:|:--:|
| MAMMAL 458M | last-layer (canonical) | 0.750 | — |
| ESM-2-650M | last-layer (canonical) | 0.725 / 0.750¹ | no |
| **ESM-C 600M** | **default `embeddings` output** | **0.625 / 0.650¹** | **no (trap)** |
| ESM-C 600M | **best layer (5 of 36)** | **0.825** | ✅ yes |
| **ESM-2-650M** | **best layer (8 of 33)** | **0.875** | ✅ **best** |
| MAMMAL 458M | best layer | *not re-swept — open follow-up* | ? |

¹ raw cosine / mean-centered cosine. The centered number is the fair one (standard
anisotropy fix); ESM-2's headline 0.750 was already its centered number.

**Decision-relevant conclusion:** best-vs-best, **ESM-2-650M (0.875) > ESM-C 600M (0.825)**.
ESM-C's "successor, parity-or-better at smaller weights" claim does **not** hold for this
family-clustering readout. (Δ = 0.05 ≈ 2 proteins on n=40, so call it "at best parity, more
likely a slight downgrade" — but it is certainly *not an upgrade*, which settles the punchlist.)

---

## Setup (identical protocol to `compare_esm2_650m.py`)

- **Panel:** the 40-gene CRISPR-N panel (`experiments/phase5_crispr_gene_panel.PANEL`):
  kinases (12, incl. 2 stress-test dupes), GPCRs (8), ion channels (8, incl. the Nav
  paralogs SCN9A/10A/1A/5A + KCNQ2/5/HCN1/TRPV1), nuclear receptors (6), a synthetic
  "e3_ligase" group (4), and two n=1 outliers (PIK3CA lipid-kinase, PTEN phosphatase).
  Panel + ordering read from `results/compare_esm2_650m.json` so it is byte-identical to
  the ESM-2 baseline.
- **Recipe:** mean-pool residue positions (exclude BOS/EOS), L2-normalize, cosine
  similarity, leave-one-out nearest-neighbour same-family recall. Sequences truncated to
  **1022 aa** to exactly match the ESM-2 protocol (so any difference is the model, not the
  input). Anisotropy robustness = mean-center then cosine.
- **ESM-C:** `esmc_600m` via the EvolutionaryScale `esm` SDK (v3.2.1), CPU, weights
  cached locally (`data/weights/esmc_600m_2024_12_v0.pth`, ~1.2 GB, ungated).
- **Layer sweep:** one forward per protein with `return_hidden_states=True` →
  all 36 transformer-block hidden states; mean-pool each; NN-recall raw + centered per layer.
  Same sweep run on ESM-2-650M (34 hidden states) for a fair best-vs-best comparison.
- **Reproduce:**
  ```bash
  /private/tmp/esmc-venv/bin/python experiments/compare_esmc_600m.py   # naive recipe
  /private/tmp/esmc-venv/bin/python experiments/esmc_layer_sweep.py    # ESM-C layer sweep
  /private/tmp/esmc-venv/bin/python experiments/esm2_layer_sweep.py    # ESM-2 layer sweep (fairness)
  ```
  Raw JSON: `results/compare_esmc_600m.json`, `results/esmc_layer_sweep.json`,
  `results/esm2_layer_sweep.json`.

---

## Section A — where ESM-C 600M *does* earn its keep

With **layer selection** (early layer ~5/36) + cosine, ESM-C clears the bar at
**NN-recall 0.825** and is **perfect on the three clean structural druggable families**:

| Family (best layer 5) | n | ESM-C recall |
|---|---:|---:|
| kinase | 12 | **1.000** |
| gpcr | 8 | **1.000** |
| ion_channel | 8 | **1.000** |
| nuclear_receptor | 6 | 0.500 |
| e3_ligase | 4 | 0.500 |
| lipid_kinase | 1 | 0.000 |
| phosphatase | 1 | 0.000 |

The ion-channel 1.000 is the Quiver-relevant highlight: ESM-C correctly clusters **all four
Nav paralogs (SCN9A/SCN10A/SCN1A/SCN5A)** plus KCNQ2/KCNQ5/HCN1/TRPV1 — better than ESM-2's
best layer on ion channels (0.875) and matching MAMMAL's last-layer 0.875. So as a *protein
embedding for structurally-coherent families*, ESM-C works fine **when read out at the right
layer**.

That is the entire "earns its keep" story: it is a competent sequence encoder for clean
structural families. It just isn't *better* than what we already have.

## Section B — where ESM-C 600M fails

1. **The default API output is a trap (0.625).** `client.logits(..., LogitsConfig(
   return_embeddings=True)).embeddings` — the obvious "give me an embedding" call — is the
   *post-final-norm* representation and scores **0.625 raw / 0.650 centered**, the worst of
   any model/readout tested. Anyone dropping ESM-C in via the documented one-liner gets a
   below-baseline embedding and would wrongly conclude ESM-C is bad. (This is precisely the
   "wrong readout" false-negative this project has hit 3× — caught here by sweeping.)
2. **Heterogeneous / functional families.** At its best layer ESM-C scores NR 0.50 and
   e3_ligase 0.50 — **worse than ESM-2-650M's best layer** (NR 0.833, e3 0.75). ESM-C does
   not crack families defined by function rather than fold.
3. **n=1 families (PIK3CA, PTEN): 0.000.** Structural auto-fail — a singleton family can
   never have a same-family nearest neighbour. Shared by *all* models; a panel artifact, not
   an ESM-C weakness. (These two genes cap the achievable panel NN-recall below 1.0.)
4. **Best-vs-best, it loses.** 0.825 (ESM-C) < 0.875 (ESM-2-650M). No upgrade.

## Section C — the architectural reason (the Boltz-style rule)

**Rule: family-separable geometry lives in the *early-to-mid* layers of these encoders and
degrades toward the output, where representations specialize for the masked-LM logits head
and collapse into a high-anisotropy cone.** ESM-C exhibits this *more sharply* than ESM-2.

Evidence:
- **Peak depth.** ESM-2-650M peaks at hidden-state idx 8 / 33 (~24 % depth); ESM-C peaks at
  layer 5 / 36 (~14 % depth). ESM-C's useful representation is even earlier — consistent with
  a model whose deeper half is more committed to the output objective.
- **Output collapse.** ESM-C's final exposed `embeddings`: 0.625. Its last raw hidden layer
  (35): 0.725. Its best layer (5): 0.825. The monotone-ish degradation over the last third,
  plus the extra drop at the post-norm output, is the signature. At the last layer every
  pair sits at cosine 0.92–0.97 (gap 0.032) — anisotropy has erased family structure, so a
  kinase's top-1 neighbour is an ion channel at 0.946.
- **Family-type axis (shared across MAMMAL / ESM-2 / ESM-C / SaProt).** Sequence(+structure)
  encoders cluster by **fold/catalytic-domain homology**. They nail families that *are*
  homology classes (kinase fold, 7TM GPCR fold, ion-channel pore) → 1.0. They fail families
  defined by **function, not fold**: "E3 ligase" spans RING/HECT/U-box architectures;
  "nuclear receptor" here even includes TP53 (a TF) and the panel mislabels RARA (a real NR)
  as an E3. **This limit is intrinsic to the embedding modality — not fixable by swapping
  ESM-2 → ESM-C.** (It is the same reason PINNACLE/PROTON also stumble on heterogeneous
  groups.)

So ESM-C's failure pattern = ESM-2's failure pattern, one notch worse, plus a more
dangerous default readout.

## Section D — best-fit Quiver use case + cost

- **Best-fit use case: none that ESM-2-650M doesn't fill better.** For Track-1 family
  clustering (the Sapphire/KG gene-grouping use case), **ESM-2-650M with layer selection**
  is the better embedding *and* the cleaner license (MIT, vs ESM-C 600M's Cambrian Open /
  6B non-commercial). ESM-C buys nothing here.
- **Cost-per-inference: ~$0.** 40 short proteins embed in ~60 s on a laptop CPU (incl. model
  load from cache); ~1.5 s/protein. No GPU/AWS required for panels of this size — a free,
  reproducible local run.
- **The actual deliverable is the layer-selection rule, not ESM-C.** Whatever embedding
  model backs the Sapphire/KG layer, it should extract an **early-mid layer (~20–25 % depth)
  + mean-center**, *not* the default last-layer/pooled output. That single change lifts
  Track-1 NN-recall from the canonical **0.750 → 0.875** (ESM-2-650M). That is the lever
  worth shipping.

---

## Fairness caveat + the open follow-up (read before citing these numbers)

- **The 0.875 / 0.825 best-layer numbers are NOT directly comparable to MAMMAL's 0.750.**
  Both ESM models were given a full layer sweep; **MAMMAL was not** — its `embed.py` only
  exposes `encoder_last_hidden_state`, and extracting intermediate layers needs forward
  hooks into the biomed-multi-alignment encoder (heavy `mammal` env, real surgery). I did
  **not** do that this session, so do **not** read "ESM-2 0.875 beats MAMMAL 0.750" — that
  compares ESM-2's best layer to MAMMAL's last layer.
- **MAMMAL last-layer per-family:** kinase 1.0, gpcr 1.0, ion_channel 0.875, NR **0.333**,
  e3 **0.25**, singletons 0.0. MAMMAL is already strong on the clean families even at the
  last layer; it loses overall only on NR/e3 — exactly the families where a layer sweep
  helped the ESM models most. So **MAMMAL plausibly also jumps with layer selection**, and a
  MAMMAL sweep could land it above or below ESM-2's 0.875. **This is the high-value
  follow-up** (`docs/models_tracks_scorecard.md` Track 1).
- **n=40 sensitivity:** one protein flip = 0.025. The 0.875-vs-0.825 gap is ~2 proteins —
  enough to say "ESM-C is not an upgrade," not enough to finely rank the two. The 1,400-gene
  full CRISPR-N panel is where any of this should be re-confirmed before it's load-bearing.

## What this changes in the scorecard

1. **Track 1 punchlist #1 (ESM-C 600M): DONE → not adopted.** Tested; not an upgrade over
   ESM-2-650M best-vs-best; ships a misleading default embedding. Move to the
   negative-result registry.
2. **New methodological note on Track 1:** the canonical 0.750 NN-recall numbers use the
   naive last-layer recipe and **undersell every encoder by ~0.10–0.12**. Layer selection
   (early-mid layer + center) is the real lever; ESM-2-650M reaches **0.875**.
3. **New open follow-up:** MAMMAL layer sweep, to settle a fair three-way best-vs-best and
   the true Track-1 winner.
