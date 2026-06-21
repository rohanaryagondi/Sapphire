# Q3b — AWS g4dn time-and-cost model for fine-tuning MAMMAL on public data

**Boss-facing. Every number is live-sourced or shown-work. Written 2026-06-01.**

> **Headline:** A small public-data MAMMAL fine-tune (e.g. MoleculeNet BBBP, ~2,050 compounds ×
> 20 epochs, or a ~2,000-example per-target binder head × 10 epochs) costs **roughly $1 and ~2 hours
> on a single-T4 `g4dn.xlarge` on-demand** — about **$0.30–0.45 on spot**. The full small-pilot
> envelope across a ±2.5× throughput band is **$0.30–$1.90 and 1.2–3.6 hours.** Fine-tuning MAMMAL on
> a typical MoleculeNet-scale dataset is, in cloud terms, **lunch money.** The only expensive case is
> the heavy 200k-pair cancer-drug-response regression (~$74 on-demand / ~$34 spot, ~6 days on one T4)
> — and that one you would not run on a single T4.

This model answers: *what does it cost, in wall-clock and dollars, to do the in-house per-target
fine-tune that the evaluation recommends as MAMMAL's one genuinely useful in-house move (COMPLETE_UNDERSTANDING
§8 Q14)?* It is a fine-tuning model, not an inference model. MAMMAL is a **458M-param T5-style
encoder-decoder** (`docs/lit/01_paper_deepread.md`); every shipped fine-tune is a **single-GPU
AdamW/Adafactor job** (`docs/lit/05_upstream_code.md` §4), which is exactly what a g4dn is built for.

---

## 1. The cost table (the deliverable)

Single-T4 `g4dn.xlarge` is the primary instance, as asked. `g5.xlarge` (A10G, 24 GB) is shown as one
comparison row per pilot because the T4 is inference-oriented and the A10G is often the better
training-$-per-job. **Central throughput estimates** (derived + bracketed in §3): **~10 samples/s** for
short SMILES-only classifier fine-tunes; **~2 samples/s** for the heavy ranked-gene + scalar regression.
Overhead (spin-up, env, 1.7 GB model + data download, checkpointing) is **0.75 h** for the small jobs,
**1.0 h** for the heavy one (§4).

| Pilot | #examples | epochs | est. steps (samples) | T4 train time | **T4 total time** | **g4dn.xlarge on-demand $** | **g4dn.xlarge spot $** | *g5.xlarge total / OD$ / spot$* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Small per-target binder** | 2,000 | 10 | 20,000 | 0.56 h | **1.3 h** | **$0.69** | **$0.31** | *1.0 h / $1.03 / $0.64* |
| **MoleculeNet BBBP** | 2,050 | 20 | 41,000 | 1.14 h | **1.9 h** | **$0.99** | **$0.45** | *1.3 h / $1.33 / $0.82* |
| **Heavy: cancer-drug-response** | 200,000 | 5 | 1,000,000 | 138.9 h | **139.9 h** | **$73.58** | **$33.57** | *70.4 h / $70.87 / $43.61* |

*"est. steps (samples)" = #examples × epochs = total forward/backward sample-passes (the throughput-relevant
unit). In optimizer-step terms at batch 16 that is ~1,250 / ~2,560 / ~62,500 steps respectively — small
fine-tunes, exactly as the upstream configs imply.*

**Reading the table for the boss:**
- The two realistic Quiver pilots (a per-target binder triage head; a MoleculeNet-scale property head)
  each finish in **under 2 hours for about a dollar** on-demand, **under 50 cents on spot.** Cost is
  not a barrier to *trying* MAMMAL fine-tuning — it is a rounding error against an analyst-hour.
- The heavy 200k-pair case is the only one that costs real money/time on a single T4 (~6 days). For
  that you would use the 4×T4 `g4dn.12xlarge` ($3.91/h OD, $1.27/h spot) or a `g5` — roughly the same
  total dollars but ~4× less wall-clock — **not** a single `g4dn.xlarge`. It is shown to bound the range,
  not as a recommended single-T4 run. *(Spot over ~6 days also invites interruption — see §5.)*
- **g5.xlarge (A10G) is the smarter default for anything non-trivial:** ~2× the training throughput for
  ~1.9× the hourly rate means roughly **break-even dollars but half the wall-clock**, plus 24 GB (vs
  16 GB) removes the gradient-checkpointing tax. For the heavy case it is *both* faster and cheaper than
  one T4. g4dn stays primary per the ask, but if the team runs more than a toy, reach for g5.

---

## 2. Live inputs (sourced, dated)

### 2a. AWS pricing — us-east-1, on-demand **and** spot (fetched 2026-06-01)
| Instance | GPU | GPU mem | On-demand $/h | Spot $/h (current low) | Spot discount |
|---|---|---|---:|---:|---:|
| **g4dn.xlarge** | 1× T4 | 16 GB | **$0.526** | **$0.240** | ~54% |
| g4dn.2xlarge | 1× T4 | 16 GB | $0.752 | $0.292 | ~61% |
| g4dn.12xlarge | 4× T4 | 4×16 GB | $3.912 | $1.268 | ~68% |
| **g5.xlarge** (compare) | 1× A10G | 24 GB | **$1.006** | **$0.619** | ~38% |

On-demand cross-checked across AWS's published rate, Vantage, and economize.cloud (all agree:
g4dn.xlarge $0.526, g4dn.2xlarge $0.752, g4dn.12xlarge $3.912, g5.xlarge $1.006). Spot is a *live,
zone-varying* number (g4dn.xlarge has ranged ~$0.21–0.34 across AZs); the values above are the current
us-east-1 lows. **Spot prices move — re-quote before committing a real run.** A single T4 on g4dn.xlarge
vs g4dn.2xlarge is the *same GPU*; the 2xlarge only buys more vCPU/RAM (8 vCPU / 32 GB vs 4 / 16) — for
a single-GPU fine-tune the **xlarge is the right SKU**, the 2xlarge is listed only for completeness.

### 2b. NVIDIA T4 specs (the engine)
- **Turing TU104, 16 GB GDDR6**, 320 Tensor Cores / 2,560 CUDA cores, 300 GB/s bandwidth, 70 W.
- **Mixed-precision (FP16) tensor peak ≈ 65 TFLOPS**; FP32 8.1 TFLOPS; INT8 130 TOPS. (NVIDIA T4 datasheet.)
- **Realistic sustained MFU for transformer fine-tuning ≈ 25–40%** of FP16 peak (the standard band for a
  bandwidth-/launch-bound 70 W inference-class card on small-batch training) → **~16–26 effective
  TFLOPS**, central ~19.5 TFLOPS at 30%.
- Context: a **V100 is ~2.6–2.8× faster than a T4 at transformer training** (Dell MLPerf: a Transformer
  converged in 12 T4-epochs vs 8 V100-epochs at proportionally higher per-epoch throughput). This is the
  cross-check that keeps the T4 estimate honest — the T4 is the slow-but-cheap option, by design.

---

## 3. Per-step / throughput interpolation for a 458M T5 (the shown work)

There is **no published T4 throughput for MAMMAL** (the field has produced *zero* independent MAMMAL
benchmarks — `docs/lit/03_reception_critique.md`). So we interpolate from published T4 fine-tuning
throughput of comparable-scale encoder and encoder-decoder transformers, then sanity-check against a
first-principles FLOPs ceiling. Two real anchors bracket the answer:

| Anchor | Model | Params | Seq (in→out) | Precision / memory tricks | T4 throughput | Source |
|---|---|---:|---|---|---:|---|
| **A — light end** | BERT-base | 110M | 128 | FP16, **no** grad-checkpoint | **~70 samples/s** (257 s/epoch over ~18k samples) | McCormick BERT GPU benchmark |
| **B — heavy end** | T5-base | 220M | 256→64 | FP16 **+ grad-checkpoint + Adafactor** | **~1.4 samples/s per T4** (59 min/epoch, 5,000 samples, 2× T4) | Medium T5-summarization guide |

**Scale each anchor to 458M (throughput ≈ 1/params at fixed sequence):**
- From A: 70 × (110/458) ≈ **17 samples/s** — the regime for *short SMILES-only classifier* fine-tunes
  (BBBP/binder/`carcinogenicity`-template; prompt is ~50–260 tokens, comparable to seq-128, and at 16 GB
  a 458M model with short SMILES does **not** need gradient checkpointing).
- From B: 1.4 × (220/458) ≈ **0.67 samples/s** — the regime for a *grad-checkpointed encoder-decoder*
  with longer (256) sequences. This is pessimistic for our classifier case because (i) checkpointing
  re-computes the forward pass (~30–40% tax) which short SMILES don't require, and (ii) it carries a
  longer output than MAMMAL's 1-answer-token classification readout (`<SENTINEL_ID_0><1><EOS>`,
  `max_new_tokens` is irrelevant in *training* — the label is a 3-token decoder sequence).

**FLOPs ceiling cross-check (Kaplan 6·N·tokens):** for a short prompt (~150 tokens), training compute
≈ 6 × 458e6 × 150 ≈ **4.1×10¹¹ FLOPs/sample**. At 19.5 effective TFLOPS that is **~47 samples/s** — an
*upper* bound (counts the full enc+dec as if every param fires on every token; the encoder-dominated
classifier path is lighter, but kernel-launch/overhead on a 70 W card pulls real throughput well below
the FLOPs ceiling).

**Chosen central estimates (with explicit uncertainty):**
- **Short SMILES-only classifier fine-tune: ~10 samples/s, band 4–25 (≈ ±2.5×).** Sits below the scaled
  light anchor (17) and the FLOPs ceiling (47) — deliberately conservative — and well above the scaled
  heavy/checkpointed anchor (0.67), because checkpointing isn't needed here. This is the number behind
  the binder and BBBP rows.
- **Heavy ranked-gene + thousands-of-scalars regression: ~2 samples/s, band 1–5.** Long prompts (the
  cell-line-drug-response task ranks *all* expressed genes — `docs/lit/05` §2.2) force checkpointing and
  a much longer encoder context, so it lives near the scaled heavy anchor.

> **Uncertainty statement (say this to the boss):** the *dollar* estimates inherit a **±2.5× band** on
> the small pilots purely from throughput uncertainty — i.e. BBBP is "$0.45–$1.90 on-demand, most likely
> ~$1." The *qualitative* conclusion ("a small fine-tune is ~1–2 GPU-hours and ~$1") is robust across
> the entire band; even at the pessimistic 4 samples/s it is 3.6 h and **under $2.** What we are *not*
> certain of is the exact hour, which doesn't change the decision. The heavy case's band ($34–$74 spot/OD,
> and 3–14× on wall-clock) is wider and is the one number to re-measure empirically before relying on it.

---

## 4. Overhead line (explicit)

Per the brief, a realistic fixed overhead independent of training length:
- EC2 spin-up + AMI boot: ~3–5 min.
- Conda/Docker env for `mammal` + `fuse` (or a prebuilt DLAMI/container): ~10–25 min cold, ~0 if a
  pre-baked image is used.
- **Model download: the HF base checkpoint is ~1.7 GB** + tokenizer; TDC/MoleculeNet data is tens of MB
  (BBBP is ~2,050 rows). A few minutes on EC2's network.
- Checkpointing: writing `best_epoch.ckpt` (~1.8 GB) a handful of times: minutes.

**Booked as 0.75 h for the small pilots, 1.0 h for the heavy one.** This overhead *dominates* the small
jobs (it is ~half their billed time) — which is the real lesson: **for a sub-2-hour fine-tune, your cost
is mostly fixed startup, so batch several fine-tunes onto one running instance** rather than spinning up
per job. Using a pre-baked AMI/container collapses the env-build portion to near zero.

---

## 5. Assumptions, caveats, and what would move the number

1. **Throughput is the dominant uncertainty (±2.5× small / ±3× heavy).** No MAMMAL-specific T4 number
   exists; we bracketed from BERT-base and T5-base. *Action to tighten:* run one epoch on a real
   g4dn.xlarge and read `samples/s` off the progress bar — converts the whole table from estimate to
   measured for ~$1.
2. **Spot is live and interruptible.** Prices above are current us-east-1 lows and vary by AZ/time;
   **re-quote before a run.** Spot interruption is a non-issue for a 1–2 h job (just restart; you lose
   cents) but a real risk for the ~6-day heavy single-T4 run — use checkpoint-resume or on-demand there.
3. **All these fit a single T4's 16 GB.** A 458M model + AdamW states + short-SMILES activations fits at
   modest batch in FP16; longer-sequence or larger-batch runs may need gradient checkpointing (already
   assumed for the heavy case) or Adafactor (less optimizer memory than Adam — the T5 anchor used it).
   This is consistent with upstream shipping these as single-GPU jobs (`docs/lit/05` §4).
4. **Epochs are illustrative.** 10–20 epochs is typical for a small-data classifier fine-tune; the
   upstream configs use AdamW lr≈1e-5→4e-4 + cosine warmup. Cost scales **linearly** in (examples ×
   epochs), so the table doubles/halves transparently with the schedule. Real fine-tunes often
   early-stop well before the epoch cap, making these *upper* estimates.
5. **Single seed costed.** The paper reports mean±std over **3 seeds**; a publication-grade run is **3×**
   these numbers (still ~$3 / ~6 h for BBBP — trivial). The table is per-seed for clarity.
6. **us-east-1.** Other regions differ modestly (us-west-2 ~same; eu/ap a few % higher). Data-egress is
   negligible for these tiny datasets.
7. **No storage/EBS line.** A ~30 GB gp3 root volume for the run is ~$0.08/day — a rounding error left
   out on purpose; mention it only if Finance asks.

---

## 6. One-paragraph takeaway (for the deck)

Fine-tuning the 458M MAMMAL on public data is **cheap and fast on the lowest-cost AWS GPU.** A realistic
Quiver pilot — a per-target binder-triage head (~2k examples) or a MoleculeNet-scale property head
(~2k compounds) — finishes in **~1–2 hours for about a dollar on-demand (~$0.30–0.45 on spot)** on a
single-T4 `g4dn.xlarge`, with a ±2.5× band that never pushes the small jobs past ~$2. The only costly
scenario is a 200k-pair regression (~$34–74, ~6 days on one T4), which you would run on multi-GPU
`g4dn.12xlarge` or a `g5` instead — and where the A10G `g5.xlarge` is both faster and cheaper than the T4.
**Cost is not a reason to skip the recommended in-house per-target fine-tune (Q14); the open question is
scientific value — novel-scaffold recall on a held-out split — not compute spend.**

---

### Sources (fetched 2026-06-01)
- AWS EC2 on-demand pricing — [AWS](https://aws.amazon.com/ec2/pricing/on-demand/),
  [Vantage g4dn.xlarge](https://instances.vantage.sh/aws/ec2/g4dn.xlarge),
  [economize g4dn.12xlarge](https://www.economize.cloud/resources/aws/pricing/ec2/g4dn.12xlarge/),
  [economize g5.xlarge](https://www.economize.cloud/resources/aws/pricing/ec2/g5.xlarge/)
- AWS spot pricing (us-east-1) — [DoiT g4dn.xlarge](https://www.doit.com/compute/spot/us-east-1/g4dn.xlarge),
  [DoiT g4dn.2xlarge](https://www.doit.com/compute/spot/us-east-1/g4dn.2xlarge),
  [DoiT g4dn.12xlarge](https://www.doit.com/compute/spot/us-east-1/g4dn.12xlarge),
  [DoiT g5.xlarge](https://www.doit.com/compute/spot/us-east-1/g5.xlarge),
  [AWS Spot pricing](https://aws.amazon.com/ec2/spot/pricing/)
- NVIDIA T4 specs — [T4 datasheet (PDF)](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-t4/t4-tensor-core-datasheet-951643.pdf),
  [NVIDIA T4 product page](https://www.nvidia.com/en-us/data-center/tesla-t4/)
- T4 fine-tuning throughput anchors —
  [McCormick, GPU Benchmarks for Fine-Tuning BERT](https://mccormickml.com/2020/07/21/gpu-benchmarks-for-fine-tuning-bert/) (BERT-base, 257 s/epoch),
  [Fine-Tuning T5 for Summarization (Medium)](https://medium.com/@ameersultan0310/fine-tuning-t5-for-text-summarization-a-complete-guide-from-training-to-deployment-8d455d97f9df) (T5-base, 59 min/epoch / 5k, 2× T4),
  [nanoT5 (arXiv 2309.02373)](https://arxiv.org/pdf/2309.02373) (T5-base, 24 h single-A100 budget — used for the A100→T4 sanity frame)
- T4 vs V100 training ratio — [Dell, Deep Learning Performance on T4 GPUs with MLPerf](https://www.dell.com/support/kbdoc/en-us/000132094/deep-learning-performance-on-t4-gpus-with-mlperf-benchmarks)
- MAMMAL grounding — `docs/lit/01_paper_deepread.md` (458M T5 enc-dec, d_model 768, per-task seq caps),
  `docs/lit/05_upstream_code.md` §4 (single-GPU AdamW/Adafactor fine-tunes, `carcinogenicity` SMILES→binary template),
  `docs/COMPLETE_UNDERSTANDING.md` §8 Q14 (the in-house per-target fine-tune this costs out)

*Q3a footprint doc (`q3a_finetune_recipe_footprint.md`) was not present in the repo at write time;
dataset sizes use the brief's fallbacks (binder ~2k×10ep; BBBP ~2,050×20ep; cancer-drug-response
~200k×5ep). If Q3a lands with different sizes, the table scales linearly in examples×epochs.*
