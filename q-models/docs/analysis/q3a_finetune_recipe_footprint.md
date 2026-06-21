# Q3a — What fine-tuning MAMMAL actually entails (recipe + memory footprint + GPU verdict)

**Written 2026-06-01.** Audience: Rohan + boss; feeds the cost lane and the throughput probe.
Bar: empirical, defensible, public-data-only (NOT Quiver data yet). Builds on
`docs/lit/05_upstream_code.md` (the fine-tune entrypoint + readouts) and
`docs/lit/03_reception_critique.md` (per-target head provenance). Numbers below come from a fresh
shallow clone of `github.com/BiomedSciAI/biomed-multi-alignment` (5 example configs + `main_finetune.py`
+ `lora.py` + `lr_schedulers.py`), the HuggingFace `config.json`, a **direct param count of the local
safetensors**, and TDC/DeepSol dataset cards.
Confidence tags: **[HIGH]** read directly from code/weights, **[MED]** standard ML arithmetic on
verified inputs, **[SPEC]** inference where the repo is silent.

> **The 60-second answer.** The shipped recipe is a **plain full fine-tune** of all 458M params:
> PyTorch Lightning + Hydra, `torch.optim.AdamW` at **lr 1e-5**, cosine-annealing-with-warmup,
> **fp32 (no mixed precision set anywhere), no gradient checkpointing, single GPU (`devices: 1`)**,
> tiny batch sizes (6–20). The full-FT optimizer state alone is **~7.3 GB** (1.8 weights + 1.8 grads
> + 3.7 Adam) before activations — so it **fits a 16 GB T4 with room for activations at the configs'
> own batch sizes**, but only because the model is small (458M) and the optimizer is the cost driver,
> not the model. A LoRA path exists in the code (`lora.py`, PEFT `r=8`) but is **OFF by default and
> not wired into the finetune entrypoint** — full FT is what every public example does. The cheapest
> realistic pilot is a per-target binder classifier (~hundreds to ~1.4k SMILES, carcinogenicity-shaped,
> a few hundred to low-thousands of steps → **single-digit GPU-minutes to ~1 GPU-hour on a T4**); the
> heaviest public task is GDSC2 cell-line drug response (**92,703 pairs**, the only one that needs
> `accumulate_grad_batches` and runs in **GPU-hours, not minutes**). **A single g4dn.xlarge T4 (16 GB)
> is sufficient for every public example.** You do not need an A10G/A100 to fine-tune this model; you
> only want one for speed.

---

## 1. The fine-tuning RECIPE (read directly from the repo) **[HIGH]**

### 1.1 Full fine-tune, not head-only, not LoRA — confirmed at the code level
The single fine-tune entrypoint is `mammal/main_finetune.py` (Hydra). The decisive line is the
optimizer construction in `configure_optimizers`:

```python
# main_finetune.py:48
opt = opt_callable(module.trainer.model.parameters())   # ALL params -> AdamW
```

`main_finetune.py` **never freezes any parameters** and **never calls `get_lora_model`**. It loads
the base model with `Mammal.from_pretrained(...)`, hands `model.parameters()` (every weight) to
AdamW, and fits. So the shipped recipe = **full fine-tune of all 458M params** (encoder + decoder +
lm_head + the scalar projection). This matches the per-target head behavior we already documented:
the `wdr91`/`pgk2` heads "modify encoder+decoder," consistent with a full FT, not an adapter. **[HIGH]**

**LoRA exists but is dormant.** `mammal/lora.py` wraps PEFT (`get_peft_model`, `LoraConfig`) with
defaults `r=8, lora_alpha=8, lora_dropout=0, bias="none"`. It is invoked **only** inside
`Mammal.from_pretrained` and **only when `config.use_lora is True`** (`model.py:502–557`). The HF
`config.json` ships `use_lora: false`, and the finetune entrypoint never overrides it. The *only*
trace of an intent to use it is a **commented-out** line in the scRNA config
(`scrna_cell_type/config.yaml:31`: `# config_overrides: { use_lora: True }`). So to fine-tune with
LoRA you would add `config_overrides: {use_lora: True}` to `pretrained_kwargs` — it is *available* but
**untested by any shipped example** (we'd be first; same caveat class as the input-scalar hook). **[HIGH]**

### 1.2 Framework, optimizer, schedule, precision — the common recipe across all 5 examples

| Knob | Value | Source |
|---|---|---|
| Trainer / framework | **PyTorch Lightning** `pl.Trainer`, config via **Hydra** | `main_finetune.py:132` |
| Tuning mode | **Full FT** (all params trainable) | `main_finetune.py:48` |
| Optimizer | `torch.optim.AdamW` | every `config.yaml` `module.opt_callable` |
| Learning rate | **1e-5** (identical in all 5 examples) | every `config.yaml` |
| Weight decay | **default** (AdamW default 0.01; only cldr config *comments* it as optional) | configs |
| LR schedule | `cosine_annealing_with_warmup` → linear warmup, cosine decay to `0.1×lr`, then constant | `lr_schedulers.py:36`, configs |
| Warmup steps | **300** (carcinogenicity, scrna); default **2000** if unset (DTI, solubility, cldr leave it default) | `lr_schedulers.py:39`, configs |
| Cosine `T_max` | 10k (carcinogenicity, cldr, scrna), 20k (solubility), 100k (DTI) | configs |
| **Precision** | **NOT SET → fp32** (no `precision:` key in any config; Lightning default is 32-true) | configs (absent) |
| **Gradient checkpointing** | **NOT enabled** (no flag anywhere in configs or `model.py`) | grep: 0 hits |
| Accelerator / devices | `accelerator: "auto"`, **`devices: 1`**, `num_nodes: 1` | every `config.yaml` |
| Strategy | `ddp_find_unused_parameters_true` (a DDP setting; irrelevant at `devices: 1`, but confirms full-FT DDP-all-params framing) | configs |
| `accumulate_grad_batches` | **only** cldr sets it (=4); all others = 1 | `cell_line_drug_response/config.yaml:67` |
| `gradient_clip_val` | default (off); cldr *comments* `# 1.0` as optional | configs |
| Checkpoint selection | `ModelCheckpoint` on val metric (acc↑ for classifiers, mse↓ for regressors) | configs |
| `max_epochs` | 100 (carcinogenicity, cldr, scrna), **1000** (DTI, solubility) — but these are ceilings; real stop is early via best-epoch monitoring + the step-based `T_max` | configs |

**Per-task batch size & sequence length (the activation-memory drivers):**

| Example | Task type / readout | `batch_size` | encoder seq len | label len | Notes |
|---|---|---|---|---|---|
| `dti_bindingdb_kd` | regression (scalar head, `forward_encoder_only`) | **8** | 1560 (tgt 1250 + drug 256) | — | config comment: *"# over a100_80g"* — IBM ran this on an A100-80G |
| `protein_solubility` | binary classifier (generative P(<1>)) | **6** | 1260 | 4 | longest single-sequence input (proteins ≤1250) |
| `carcinogenicity` | binary classifier (generative P(<1>)) | **15** | **320** (drug ≤292) | 4 | **short context → cheapest per-step** |
| `cell_line_drug_response` | regression (scalar head) | **8** ×4 accum = eff. 32 | 1500 | — | only task using grad accumulation |
| `scrna_cell_type` | 11-class classifier (generative) | **20** | 512 | 20 | short context, biggest batch |

> **Read:** the recipe is deliberately vanilla — one LR (1e-5), one optimizer (AdamW), one schedule
> (cosine+warmup), fp32, one GPU. There is no fancy memory engineering (no checkpointing, no fp16/bf16,
> no ZeRO/FSDP — `ddp_find_unused_parameters_true` is the heaviest strategy and it only matters
> multi-GPU). That tells you IBM fine-tuned these on a **single large-VRAM card (the DTI config
> literally says A100-80G)** and never needed to optimize memory. We do not have that constraint at
> 458M — see §2.

---

## 2. MEMORY FOOTPRINT of fine-tuning a 458M T5 — the GB math **[MED, on HIGH inputs]**

### 2.1 Ground-truth inputs (not estimates)
- **Exact param count, from the local safetensors:** `458,004,897` params (≈458.0M), **all stored F32**
  (HF card also lists tensor type **F32**, ~0.5B). Verified by reading
  `…ma-ted-458m.tcr_epitope_bind/…/model.safetensors` (288 F32 tensors; `lm_head.weight` is
  `[100001, 768]` — note the lm_head is **untied**, which is why the architecture lands at 458M not
  ~275M). **[HIGH]**
- **Architecture (HF `config.json`):** T5, `d_model=768, d_ff=2048, d_kv=64, num_heads=12,
  num_layers=12, num_decoder_layers=12, vocab=100,001`, `dropout=0.1`, `support_input_scalars=true`,
  `use_lora=false`. This is a **T5-base-scale** trunk; the params are dominated by the
  100k-token vocab embedding (76.8M) **counted twice** (input embed + untied lm_head ≈ 154M of the 458M).
- **On-disk / download size:** `458M × 4 bytes = 1.83 GB` (matches the ~1.8 GB HF artifact). **[HIGH]**

### 2.2 The four memory consumers (the standard decomposition)
For AdamW full FT, steady-state VRAM = **weights + gradients + optimizer states (2×: m and v) +
activations** (+ small CUDA/framework overhead, typically 0.5–1.5 GB).

**Full FT, fp32 (the shipped recipe):**

| Component | Math (458M params) | Size |
|---|---|---|
| Weights (fp32) | 458M × 4 B | **1.83 GB** |
| Gradients (fp32) | 458M × 4 B | **1.83 GB** |
| AdamW optimizer states (m + v, fp32) | 458M × 8 B | **3.66 GB** |
| **Subtotal (model state, no activations)** | | **≈ 7.33 GB** |
| Activations | batch- & seq-len-dependent (see §2.4) | ~1–5 GB at config batch sizes |
| CUDA context + PyTorch/Lightning overhead | fixed | ~0.5–1.5 GB |
| **Total expected peak** | | **≈ 9–13 GB** |

**Mixed precision (`16-mixed` / bf16 autocast) — what it does and doesn't do:**
AMP keeps **fp32 master weights, fp32 grads, and fp32 optimizer states** and only casts the
forward/backward *compute* (matmuls) to bf16/fp16, plus a transient half-precision weight copy.
So the **7.33 GB model-state floor does NOT shrink** — AMP's win is (a) **smaller activations**
(roughly halved) and (b) **faster matmuls** (≈1.5–2× throughput on T4 fp16 / A10G+ bf16). The
optimizer state is the dominant cost and AMP leaves it alone. **[MED]**

> A common misconception worth pre-empting for the cost write-up: "use fp16 to fit it" — at 458M you
> already fit in fp32 on a T4. AMP here is a **speed** lever (and a small activation-memory lever),
> **not** a "make it fit" lever. The thing that would actually cut the 7.3 GB floor is a different
> optimizer (8-bit Adam → ~halves the 3.66 GB) or LoRA (§2.3) — neither is needed at this size.

**LoRA (if you flip `use_lora: True`) — for completeness, not required:**
PEFT `r=8` on T5 q/v projections ≈ **~0.9M trainable params (~0.19% of base)**. Base weights stay
resident (1.83 GB, frozen), LoRA weights+grads+Adam ≈ **0.014 GB (negligible)**. So LoRA total model
state ≈ **1.85 GB** + activations — i.e. it mostly saves the **5.5 GB of grad+optimizer state** of full
FT. At 458M on a T4 this is a nice-to-have, **not a necessity**; it matters far more if Quiver ever
wants many per-target heads cheaply (one frozen base + tiny per-target adapters). **[MED]**

### 2.3 Does it fit a 16 GB T4? **YES.** **[MED, high-confidence]**
- Full-FT fp32 model state (7.33 GB) + activations at the configs' **own** batch sizes (6–20, mostly
  short contexts) + ~1 GB overhead lands at **~9–13 GB peak**, inside 16 GB.
- The one to watch is **DTI/cldr at 1500–1560-token context**: long sequences inflate activations.
  If peak approaches 16 GB, the standard, recipe-preserving fixes are (in order, all free):
  **(1)** enable bf16/fp16 AMP (halves activations), **(2)** drop batch size to 4 and raise
  `accumulate_grad_batches` to hold the effective batch, **(3)** enable gradient checkpointing
  (trades ~20–30% compute for a large activation cut). None change the result; all are one-line config
  edits. **[MED]**
- The DTI config's *own* note ("# over a100_80g", batch 8) reflects IBM's convenience hardware, **not
  a 16 GB infeasibility** — at batch 8 the model state is still 7.3 GB; an A100-80G was just what they
  had. **[SPEC on intent, HIGH on the arithmetic]**

---

## 3. Representative PUBLIC fine-tune targets — sizes, epochs, step counts **[HIGH on sizes, MED on steps]**

Datasets are pulled at runtime (TDC for most; DeepSol `.tab` for solubility), so the configs don't
hardcode sizes. Sizes below are from TDC dataset cards / DeepSol; **steps = ⌈train_examples /
(batch × accum)⌉ × epochs**, using the config's batch and the step-based `T_max` as the realistic
schedule length (the `max_epochs` ceilings of 100–1000 are early-stopped by best-epoch monitoring, so
`T_max` is the better proxy for "how long it actually trains").

| Public target | Task shape | **Total examples** | batch (eff.) | steps/epoch | Realistic schedule | ~Total steps | Cost class on T4 |
|---|---|---|---|---|---|---|---|
| **Carcinogenicity** (`Tox: Carcinogens_Lagunin`) | SMILES → binary, generative | **278** (≈195/28/56 random split) | 15 | ~13 | `T_max=10k`, warmup 300; in practice a few hundred steps to converge on 195 train | **few hundred** (≈13/epoch × ~10–50 epochs) | **GPU-minutes** |
| **A per-target binder head** (carcinogenicity-shaped; cf. PGK2 = **1,388** CACHE#7 hits, WDR91 = up to **375,595** AIRCHECK DEL but typically subsampled) | SMILES → binary, generative | **~hundreds–few k** (PGK2 ~1.4k is the realistic pilot scale) | ~15 | ~90 (at 1.4k) | a few hundred to low-thousands of steps | **~hundreds–~2k** | **single-digit GPU-min → ~1 GPU-hr** |
| **MoleculeNet BBBP** (`ADME: BBB_Martins`) | SMILES → binary, generative | **1,975** (~1.4k train at 70/10/20) | ~15 (BBBP head ships no config — use carcinogenicity's) | ~92 | ~10–50 epochs | **~1k–5k** | **tens of GPU-min** |
| **Protein solubility** (DeepSol) | AA → binary, generative | **71,419** (62,478 / 6,942 / 1,999) | 6 | ~10,413 | `T_max=20k` ≈ **~2 epochs** | **~20k** | **GPU-hours** |
| **DTI BindingDB_Kd** | (target+drug) → pKd, regression | **52,284** pairs (cold-split) | 8 | ~6,535 (train share) | `T_max=100k` (long) | **~50k–100k** | **many GPU-hours** |
| **Cell-line drug response GDSC2** (heaviest pilot) | (expr+SMILES) → IC50, regression | **92,703** pairs (GDSC1 = 177,310) | 8×4=**32** eff. | ~2,897 | `T_max=10k` ≈ **~3.5 epochs** | **~10k** | **GPU-hours** (only task with grad accum) |

**Cheapest realistic pilot vs heaviest, stated plainly:**
- **Cheapest:** a **per-target binder classifier** on a few-hundred-to-~1.4k SMILES set (the PGK2
  CACHE#7 1,388-hit scale, or carcinogenicity's 278). Generative P(<1>) readout, batch ~15, short
  context (≤320 tokens → cheap activations), a few hundred to low-thousands of steps, **a handful of
  epochs**. This is **single-digit GPU-minutes to ~1 GPU-hour on a T4** and is exactly the
  "hit / non-hit on screening data" shape — the right template for a Quiver in-house per-target head.
  The data module just swaps TDC `Tox` for a parquet via `OpReadDataframe(columns=["Drug","label"])`.
- **Heaviest (public):** **GDSC2 cell-line drug response**, ~92.7k pairs, 1500-token context, the only
  task that needs `accumulate_grad_batches`. **GPU-hours, not minutes.** (DTI Kd is similar scale with
  a longer `T_max=100k` schedule.) **MoleculeNet BBBP (~2,050 compounds)** sits in between — **tens of
  GPU-minutes**.

> Wall-clock vs step count is what the **throughput probe** must measure — the steps above are exact
> arithmetic, but seconds/step on a T4 depends on context length and AMP, which is the empirical
> unknown the probe should pin down (expect short-context classifier steps to be fast; the 1500–1560-token
> regression steps to be the slow ones). **[MED]**

---

## 4. GPU verdict — does a single g4dn T4 (16 GB) suffice, or do you need more? **[MED]**

**Single g4dn.xlarge T4 (16 GB) is SUFFICIENT for every public example fine-tune.** The full-FT fp32
model state is only 7.3 GB; even the long-context regression tasks fit with the free, recipe-preserving
levers (AMP / smaller batch + accum / gradient checkpointing) if activations push toward the ceiling.

- **g4dn.xlarge (1× T4, 16 GB):** fits all examples; the **cheapest** option and the right default for
  a pilot. Trade-off vs bigger cards is **wall-clock**, not feasibility.
- **g5.xlarge (1× A10G, 24 GB):** not required, but the better *value* if you care about speed —
  bf16 (Ampere) gives a real throughput bump over T4 fp16, +8 GB headroom removes any long-context
  anxiety, and it lets you raise batch size to cut step count. Recommended if the throughput probe
  shows T4 step-times are painful on the 1500-token tasks.
- **A100-80G:** what IBM used (per the DTI config comment) purely for convenience — **overkill** for
  458M. Only worth it to brute-force the largest datasets (GDSC1 177k, BindingDB_IC50 ~991k) fast.
- **Multi-GPU:** **not needed.** The `ddp_find_unused_parameters_true` strategy is present but at
  `devices: 1` it does nothing; you'd only go multi-GPU to shorten wall-clock on the big regression
  sets, never to fit the model.

**Bottom line for the cost lane:** budget the pilot on a **single g4dn.xlarge T4**; a per-target
binder head is GPU-minutes-to-~1-hour, BBBP is tens-of-minutes, and only the big regression tasks
(GDSC2/DTI) reach GPU-hours. Step the instance up to **g5 (A10G)** for speed if the probe says so —
but the honest answer to "do we need a big GPU to fine-tune MAMMAL" is **no**.

---

## 5. Open items the throughput/cost probe must close (don't fake these)
1. **Seconds/step on T4** for (a) a short-context classifier (~320 tok) and (b) a long-context
   regression step (~1500 tok), fp32 vs bf16-AMP. Steps are exact; wall-clock is the unknown. **[MED]**
2. **Peak VRAM measured** on the 1500–1560-token DTI/cldr tasks at batch 8 — confirm the ~9–13 GB
   estimate empirically and whether AMP/checkpointing is actually needed on a 16 GB T4. **[MED]**
3. **DeepSol split provenance** — the example reads local `.tab` files; the 62,478/6,942/1,999 figure
   is the canonical DeepSol split, but the exact files IBM ships may differ. Verify if solubility cost
   matters. **[SPEC]**

---

## Source index (all read/verified 2026-06-01)
- Fine-tune entrypoint + full-FT proof: `/tmp/bma` clone — `mammal/main_finetune.py:48,115,132`,
  `mammal/lora.py` (PEFT r=8 defaults), `mammal/lr_schedulers.py:36` (cosine+warmup defaults).
- Per-task recipe: `mammal/examples/{dti_bindingdb_kd,carcinogenicity,protein_solubility,
  cell_line_drug_response,scrna_cell_type}/config.yaml` (batch, lr, T_max, warmup, devices, accum;
  precision/grad-checkpoint absent).
- Data modules (sizes pulled at runtime via TDC): `…/carcinogenicity/pl_data_module.py:85`,
  `…/dti_bindingdb_kd/pl_data_module.py:101`.
- Architecture + dtype: HF `ibm/biomed.omics.bl.sm.ma-ted-458m/config.json` (T5 dims,
  `support_input_scalars`, `use_lora=false`, F32) + **direct param count of local
  `…tcr_epitope_bind/model.safetensors` = 458,004,897 params, 288 F32 tensors, untied lm_head**.
- Dataset sizes: TDC cards — BindingDB_Kd 52,284 / IC50 991,486 / Ki 375,032; Carcinogens_Lagunin 278;
  ClinTox 1,484; BBB_Martins 1,975; GDSC2 92,703 / GDSC1 177,310. DeepSol 62,478/6,942/1,999
  (Khurana et al., *Bioinformatics* 2018). PGK2 1,388 (CACHE#7) / WDR91 375,595 (AIRCHECK) from
  `docs/lit/03_reception_critique.md`.
- Memory math: standard AdamW decomposition (weights + grads + 2× optimizer states) on the verified
  458M F32 param count.
