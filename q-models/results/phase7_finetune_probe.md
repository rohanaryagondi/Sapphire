# Phase 7 — Local fine-tune throughput probe + cost-lane verification

**Written 2026-06-01.** Audience: Rohan + boss. This is the **secondary empirical anchor** for the
Q3b cost model (`docs/analysis/q3b_aws_g4dn_cost.md`). The cost lane's primary basis is published-benchmark
interpolation; this probe is a real-hardware sanity check run locally on an M3 Pro (18 GB).

> **Bottom line.** A single forward+backward of the 458M MAMMAL model on the cheapest fine-tune shape
> (short SMILES generative classifier, the per-target binder template) is **feasible locally at batch 1
> in fp32** — no OOM. Measured **CPU train-step ~0.55 s (1.8 samples/s); MPS train-step ~0.077 s
> (13.0 samples/s)** at batch 1. The MPS number lands **squarely inside the cost lane's assumed T4 band
> (central 10, band 4-25 samples/s)**, so the Q3b small-pilot cost — **~$0.69 on-demand / ~$0.31 spot,
> ~1.3 h on a g4dn.xlarge** — is **SOUND**. My independent recompute from scratch reproduces it to within
> 8%. **Verdict: the boss-facing cost numbers hold; ship them.** One scope flag below (the probe only
> anchors the *short-context* classifier row, not the 1500-token regression row).

---

## 1. What was measured (every number labeled measured-vs-estimated)

Probe script: `experiments/phase7_finetune_probe.py`. Raw JSON: `results/phase7_finetune_probe.json`.
Model: local `models/base_458m` (`Mammal.from_pretrained`), **458,007,202 params** (matches Q3a's 458M,
all fp32). Batch = 1. Workload = the validated per-target classifier path
(`mammal_quiver.wdr91._prompt`: SMILES + task token + `<SENTINEL_ID_0>`), with a 3-token classification
label `<SENTINEL_ID_0><1><EOS>` so the T5 computes its real cross-entropy loss internally — i.e. a true
(forward + backward) of one training sample, minus only the optimizer `.step()`.

| Quantity | Device | Value | Measured / estimated |
|---|---|---:|---|
| Model load | CPU | 10.6 s | **measured** |
| Param count | — | 458,007,202 | **measured** (direct count) |
| Encoder seq len (caffeine SMILES) | — | **26 tokens** | **measured** |
| Encoder seq len (atorvastatin, 71-char SMILES) | — | **29 tokens** | **measured** |
| Label len | — | 3 tokens | **measured** |
| **Forward only** (median of 5, 2 warmups) | **CPU** | **0.0997 s** | **measured** |
| **Forward + backward** (median of 5, 1 warmup) | **CPU** | **0.535 s** | **measured** (loss 6.55, sane untrained CE on 100k vocab) |
| Forward only (long SMILES, enc=29) | CPU | 0.132 s | **measured** |
| Forward + backward (long SMILES) | CPU | 0.592 s | **measured** |
| **CPU train-step estimate** | CPU | **0.555 s** (1.8 samp/s) | **measured fwd+bwd + 0.2x fwd** optimizer add-on |
| **Forward only** (median of 5, 3 warmups) | **MPS** | **0.0194 s** | **measured** |
| **Forward + backward** (median of 3) | **MPS** | **0.0729 s** | **measured** — **MPS backward IS feasible** |
| **MPS train-step estimate** | MPS | **0.0768 s** (13.0 samp/s) | **measured fwd+bwd + 0.2x fwd** |

**Notes on the numbers:**
- **Backward at fp32, batch 1, was feasible on a 16-GB-class machine** — no OOM on CPU *or* MPS. This
  directly corroborates Q3a §2.3 ("fits a 16 GB T4"): the 7.3 GB full-FT model state + tiny-batch
  short-context activations is comfortable. *(We did not instrument peak VRAM — that's a CUDA-only ask;
  the no-OOM result + Q3a's 7.3 GB arithmetic is the evidence.)*
- **fwd:bwd ratio is ~5.4x on CPU** (0.535 / 0.099) but only ~3.8x on MPS (0.073 / 0.019). Both are
  *above* the textbook 2x because the backward must traverse the **untied 100k-token lm_head** (the
  largest single matmul in this model). On a T4 with fused fp16 kernels this ratio compresses toward the
  usual ~2-3x — which is why the standard "train-step ~= 3x forward" fallback is a reasonable rule here.
- **SMILES contexts are genuinely short.** A 71-char drug SMILES tokenizes to only **29 tokens**; even a
  250-char string is 50 tokens. So MAMMAL's SMILES classifier prompt is *well under* the cost lane's
  "<=320 token" cap and below its conservative "~150 token" working figure. The probe therefore anchors
  the **light end** of the priced regime — which is exactly the *cheapest-pilot* row, and if anything makes
  the cost lane's 10 samp/s look conservative, not aggressive.

---

## 2. T4 cross-check (rough — labeled unreliable, ±3x)

Per the brief, a direct M3/CPU -> T4 scaling is unreliable, so this is a *sanity* cross-check, not the
basis. Two independent angles, both consistent with the cost lane:

1. **MPS-at-batch-1 vs cost-lane T4:** measured **MPS 13.0 samples/s** at batch 1 sits **inside the cost
   lane's assumed T4 band (10 central, 4-25)**. An M3 Pro GPU and a 70 W T4 are the same rough class; a T4
   running batch >1 (amortizing kernel-launch overhead, which dominates at these tiny sequences) lands in
   the same 10-17 samp/s zone the cost lane derived from the scaled BERT anchor (17) and chose 10 for.
   **The hardware anchor agrees with the interpolation.**
2. **CPU train-step (0.55 s, 1.8 samp/s)** is the slow floor; a T4 being ~5-7x a single-thread-ish CPU on
   a transformer step would put it ~9-13 samp/s — again the same neighborhood. (This is the ±3x-unreliable
   direction; reported only because it points the same way.)

Neither cross-check contradicts the cost lane. They make the **10 samp/s central estimate look slightly
conservative** for the short-context classifier — i.e. real cost is, if anything, a touch *lower* than
booked.

---

## 3. Independent cost recompute from scratch (the verification ask)

I rebuilt the **small per-target binder pilot** cost bottom-up using **my own throughput pick** and the
cost lane's cited us-east-1 pricing (g4dn.xlarge $0.526/h OD, $0.240/h spot; 0.75 h fixed overhead).
Pilot = 2,000 examples x 10 epochs = 20,000 sample-passes.

| Throughput assumption | Train time | **Total time** | **On-demand $** | **Spot $** |
|---|---:|---:|---:|---:|
| **My central — 12 samp/s** | 0.46 h | **1.21 h** | **$0.64** | **$0.29** |
| Cost lane's 10 samp/s | 0.56 h | 1.31 h | $0.69 | $0.31 |
| Pessimistic — 5 samp/s | 1.11 h | 1.86 h | $0.98 | $0.45 |
| **Cost lane headline (q3b §1)** | 0.56 h | **1.3 h** | **$0.69** | **$0.31** |

**My from-scratch central ($0.64 OD / 1.21 h) reproduces the cost lane's $0.69 / 1.3 h to within ~8%** —
far inside the "within ~2x" bar. Even the pessimistic 5 samp/s case stays **under $1 and under 2 hours**.
The qualitative claim ("a small MAMMAL fine-tune is ~1-2 GPU-hours and ~$1; lunch money") is robust across
the whole band. **The cost lane's small-pilot numbers are sound.**

---

## 4. Assumption audit — did I find anything off in Q3b? (the "flag it" ask)

I checked precision, overhead, MFU, and price against my measurements. Findings:

- **Precision — CORRECT.** Q3b/Q3a correctly treat the shipped recipe as **fp32** (no mixed precision in
  any config) and correctly note AMP is a *speed* lever, not a *fit* lever at 458M. My probe ran fp32 and
  fit fine. ✅
- **Overhead (0.75 h) — REASONABLE and correctly called the dominant term** for sub-2-hour jobs. Model
  load alone was 10.6 s locally; on EC2 the 1.7 GB download + env dominate, and 0.75 h is a fair booking.
  ✅ (The cost lane's advice to *batch multiple fine-tunes onto one running instance* is the right call —
  the probe confirms training is minutes, so startup genuinely dominates.)
- **Throughput (10 samp/s central, band 4-25) — SOUND, mildly conservative** for the short-context
  classifier. My measured MPS 13 samp/s and the recompute both support it. No correction needed. ✅
- **Pricing ($0.526 OD / $0.240 spot) — not re-verified live by this agent** (no web access used here);
  the cost lane cross-checked it across 3 sources on 2026-06-01 and flags spot as live/movable. Inherit
  as-is; **re-quote spot before a real run** per their own caveat. ✅ (no issue found, just not
  independently re-fetched)
- **The "train-step ~= 3x forward" fallback — not needed, but validated as conservative.** Backward was
  feasible, and the real CPU fwd+bwd ratio (5.4x) is *higher* than 3x because of the 100k-vocab lm_head;
  on a T4 with fused kernels it compresses to ~2-3x. The 3x rule is a fine fallback. ✅

### The one scope flag (not an error — a coverage gap to state out loud)
The probe anchors **only the short-context classifier** (binder / BBBP rows — the realistic Quiver
pilot). It says **nothing empirical about the heavy 1500-1560-token regression row** (DTI / cancer-drug-
response), whose throughput (~2 samp/s) and ~$34-74 / ~6-day figure carry a wider ±3x band that Q3b
itself flags as "the one number to re-measure." **Do not let the probe's clean result imply the heavy
case is verified — it isn't.** If anyone needs the heavy-case cost defended, that one still wants a real
g4dn epoch (or at least a 1500-token forward timing, which this probe did not run because the SMILES
tokenizer caps these molecules at tens of tokens). For the *recommended* pilot (per-target binder
triage), the number is solid.

---

## 5. Verdict

**The Q3b boss-facing cost numbers are SOUND for the recommended pilot and need no revision.**
- Small per-target binder fine-tune: **~$0.69 on-demand / ~$0.31 spot, ~1.3 h on a single-T4
  g4dn.xlarge** — independently reproduced to within ~8%, robust to within $1 across a 5-25 samp/s band.
- MoleculeNet BBBP (2,050 x 20 ep): same regime, **~$1 OD / ~$0.45 spot, ~1.9 h** — consistent with the
  measured throughput (scales linearly in examples x epochs).
- Empirically grounded facts added by this probe: (1) **fp32 batch-1 forward+backward of 458M is
  feasible on a 16-GB-class machine** (no OOM, confirms the "fits a T4" claim); (2) **measured throughput
  (MPS 13 samp/s @ batch 1) corroborates the cost lane's interpolated T4 band**; (3) **MAMMAL SMILES
  prompts are very short (~26-50 tokens)**, so the classifier pilot is the light/cheap end of the curve.
- **Caveat to carry forward:** verified the *classifier/pilot* row only; the heavy 1500-token regression
  row remains interpolation-only and should be re-measured on real GPU before being leaned on.

---

### Repro
```bash
USE_TF=0 USE_FLAX=0 PHASE7_FORCE_CPU=1 \
  /opt/anaconda3/envs/mammal/bin/python experiments/phase7_finetune_probe.py
# -> results/phase7_finetune_probe.json
```
Device defaults to CPU (most stable for backward on this box). MPS forward-only + the long-SMILES and
MPS-fwd+bwd cross-checks were run as ad-hoc one-offs (numbers in §1); set `PHASE7_TRY_MPS=1` to enable the
in-script MPS anchor. Single process, batch 1, model freed at exit (memory-safe).
