"""Phase 7 — local throughput ANCHOR for fine-tuning the 458M MAMMAL model.

Purpose (memory-safe, single process): get an EMPIRICAL per-step time for the
cheapest realistic fine-tune shape — a short SMILES-only generative *classifier*
(the carcinogenicity / per-target binder template the Q3b cost lane prices). This
is a secondary sanity anchor for the published-benchmark interpolation in
docs/analysis/q3b_aws_g4dn_cost.md; it is NOT a real training run.

What it measures, in order, all at BATCH=1 / fp32 / tiny input:
  (1) FORWARD ONLY  — encoder-decoder forward over the classifier prompt + a
      3-token classification label (<SENTINEL_ID_0><1><EOS>). torch.no_grad.
      Median of N timed runs after a warmup. Low memory.
  (2) FORWARD+BACKWARD — same forward WITH grads, T5 computes its own CE loss
      from `labels`, then loss.backward(). This is one (fwd+bwd) of a real train
      step minus the optimizer .step(). If it OOMs/errors, we catch it, record
      "backward not feasible locally", and FALL BACK to estimating a train step
      as ~3x the forward time (standard fwd:bwd:step ~= 1:2:0.x heuristic; we use
      train_step ~= 3x fwd as the conventional fwd+bwd+step approximation).

Why this prompt is the right proxy: docs/analysis/q3a_finetune_recipe_footprint.md
shows the shipped recipe is a full FT (AdamW, fp32, no grad-checkpoint, single
GPU); the cheapest pilot is the carcinogenicity-shaped binary classifier (batch
~15, encoder seq <=320 tokens, generative P(<1>) readout). We replicate that exact
architecture path (mammal_quiver.wdr91._prompt) at batch 1.

Device: defaults to CPU (most stable here for the backward pass; M3 18GB RAM).
Set PHASE7_FORCE_CPU=0 to allow MPS. We additionally try an MPS forward-only
timing as a secondary anchor if memory permits.

Run:
  USE_TF=0 USE_FLAX=0 /opt/anaconda3/envs/mammal/bin/python \
      experiments/phase7_finetune_probe.py
"""

from __future__ import annotations

import os

# macOS TF-deadlock guard + keep this single-threaded-ish for a clean CPU timing.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import gc
import json
import statistics
import sys
import time

import torch

# Make the repo importable so we reuse the validated wrappers/prompts.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp  # noqa: E402
from mammal.keys import (  # noqa: E402
    ENCODER_INPUTS_ATTENTION_MASK,
    ENCODER_INPUTS_STR,
    ENCODER_INPUTS_TOKENS,
    LABELS_ATTENTION_MASK,
    LABELS_STR,
    LABELS_TOKENS,
)
from mammal.model import Mammal  # noqa: E402

from mammal_quiver.wdr91 import _prompt as binder_prompt  # the validated classifier prompt  # noqa: E402

# ----------------------------------------------------------------------------- config
N_TIMED = 5          # median of this many runs after warmup (brief: ~5)
N_WARMUP = 2         # warmup runs (kernel/alloc warm; excluded from timing)
TASK_TOKEN = "WDR91_ASMS"  # any per-target classifier token; same arch path

# A short, drug-like SMILES (caffeine) -> short encoder context, the cheap regime.
SMILES = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"

# The classification label is a 3-token decoder sequence, molnet-style:
#   <SENTINEL_ID_0> <1> <EOS>   (the "active" label). This is what training fits.
LABEL_STR = "<@TOKENIZER-TYPE=SMILES><SENTINEL_ID_0><1><EOS>"

_REPO_MODELS = os.path.join(_REPO, "models")
_LOCAL_BASE = os.path.join(_REPO_MODELS, "base_458m")
BASE_SOURCE = (
    _LOCAL_BASE
    if os.path.isfile(os.path.join(_LOCAL_BASE, "model.safetensors"))
    else "ibm/biomed.omics.bl.sm.ma-ted-458m"
)


def _now() -> float:
    return time.perf_counter()


def _sync(device: str) -> None:
    if device == "mps":
        try:
            torch.mps.synchronize()
        except Exception:
            pass
    elif device == "cuda":
        torch.cuda.synchronize()


def _build_sample(tok, device: str) -> dict:
    """Tokenize the classifier prompt + label into a single-sample batch dict."""
    prompt = binder_prompt(SMILES, TASK_TOKEN)
    sd = {ENCODER_INPUTS_STR: prompt, LABELS_STR: LABEL_STR, "data.sample_id": 0}
    # encoder inputs
    tok(
        sample_dict=sd,
        key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
    )
    # labels (decoder targets) — T5 computes CE loss internally from these
    tok(
        sample_dict=sd,
        key_in=LABELS_STR,
        key_out_tokens_ids=LABELS_TOKENS,
        key_out_attention_mask=LABELS_ATTENTION_MASK,
    )
    enc_len = len(sd[ENCODER_INPUTS_TOKENS])
    lab_len = len(sd[LABELS_TOKENS])
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=device).unsqueeze(0)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(
        sd[ENCODER_INPUTS_ATTENTION_MASK], device=device
    ).unsqueeze(0)
    sd[LABELS_TOKENS] = torch.tensor(sd[LABELS_TOKENS], device=device).unsqueeze(0)
    sd[LABELS_ATTENTION_MASK] = torch.tensor(
        sd[LABELS_ATTENTION_MASK], device=device
    ).unsqueeze(0)
    return sd, enc_len, lab_len


def _forward_only(model, sample: dict, device: str) -> float:
    """One encoder-decoder forward, no grad. Returns elapsed seconds."""
    with torch.no_grad():
        _sync(device)
        t0 = _now()
        _ = model.forward_encoder_decoder(dict(sample))
        _sync(device)
        return _now() - t0


def _forward_backward(model, sample: dict, device: str) -> float:
    """One forward (with grad) + loss.backward(). Returns elapsed seconds.

    T5 returns its own CE loss at model.out['loss'] because we passed `labels`.
    """
    model.zero_grad(set_to_none=True)
    _sync(device)
    t0 = _now()
    out = model.forward_encoder_decoder(dict(sample))
    model_out = out["model.out"]
    # model_out is a dict(...) of the HF Seq2SeqLMOutput; 'loss' present when labels given
    loss = model_out["loss"] if "loss" in model_out else None
    if loss is None:
        # extremely defensive: compute CE ourselves from logits+labels
        logits = model_out["logits"]
        labels = sample[LABELS_TOKENS]
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.size(-1)), labels.reshape(-1)
        )
    loss.backward()
    _sync(device)
    dt = _now() - t0
    model.zero_grad(set_to_none=True)
    return dt, float(loss.detach().item())


def _median_forward(model, sample, device, n_timed=N_TIMED, n_warmup=N_WARMUP):
    for _ in range(n_warmup):
        _forward_only(model, sample, device)
    times = [_forward_only(model, sample, device) for _ in range(n_timed)]
    return times


def run_on_device(device: str, do_backward: bool) -> dict:
    print(f"\n=== device={device} (backward={'yes' if do_backward else 'no'}) ===", flush=True)
    t_load0 = _now()
    model = Mammal.from_pretrained(BASE_SOURCE).to(device).eval()
    tok_path = os.path.join(BASE_SOURCE, "tokenizer") if os.path.isdir(BASE_SOURCE) else BASE_SOURCE
    tok = ModularTokenizerOp.from_pretrained(tok_path)
    load_s = _now() - t_load0
    n_params = sum(p.numel() for p in model.parameters())
    print(f"loaded {n_params:,} params in {load_s:.1f}s", flush=True)

    sample, enc_len, lab_len = _build_sample(tok, device)
    print(f"encoder_seq_len={enc_len} tokens, label_len={lab_len} tokens", flush=True)

    result = {
        "device": device,
        "n_params": n_params,
        "load_s": round(load_s, 2),
        "encoder_seq_len": enc_len,
        "label_len": lab_len,
        "smiles": SMILES,
        "task_token": TASK_TOKEN,
    }

    # (1) forward-only
    fwd_times = _median_forward(model, sample, device)
    result["forward_times_s"] = [round(t, 4) for t in fwd_times]
    result["forward_median_s"] = round(statistics.median(fwd_times), 4)
    result["forward_min_s"] = round(min(fwd_times), 4)
    print(f"FORWARD median={result['forward_median_s']}s  runs={result['forward_times_s']}", flush=True)

    # (2) forward+backward (only on the chosen primary device, to bound memory)
    if do_backward:
        try:
            bwd_times = []
            losses = []
            # warmup once (allocates grad buffers), then time
            for _ in range(1):
                _forward_backward(model, sample, device)
            for _ in range(N_TIMED):
                dt, lv = _forward_backward(model, sample, device)
                bwd_times.append(dt)
                losses.append(lv)
            result["fwd_bwd_feasible"] = True
            result["fwd_bwd_times_s"] = [round(t, 4) for t in bwd_times]
            result["fwd_bwd_median_s"] = round(statistics.median(bwd_times), 4)
            result["loss_value"] = round(statistics.median(losses), 4)
            print(
                f"FWD+BWD median={result['fwd_bwd_median_s']}s  loss~{result['loss_value']}  "
                f"runs={result['fwd_bwd_times_s']}",
                flush=True,
            )
        except (RuntimeError, MemoryError) as e:
            result["fwd_bwd_feasible"] = False
            result["fwd_bwd_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            print(f"FWD+BWD NOT FEASIBLE: {result['fwd_bwd_error']}", flush=True)

    # free the model promptly (memory-safe: this is the only model-touching agent)
    del model, tok, sample
    gc.collect()
    if device == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
    return result


def main():
    force_cpu = os.environ.get("PHASE7_FORCE_CPU", "1") != "0"  # default: CPU primary
    primary = "cpu" if force_cpu else (
        "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    print(f"torch {torch.__version__} | mps={torch.backends.mps.is_available()} "
          f"cuda={torch.cuda.is_available()} | primary={primary} "
          f"(PHASE7_FORCE_CPU={'1' if force_cpu else '0'})", flush=True)

    results = {"torch": torch.__version__, "runs": []}

    # Primary: CPU (stable for backward). Do forward + backward here.
    primary_res = run_on_device(primary, do_backward=True)
    results["runs"].append(primary_res)

    # Secondary anchor: MPS forward-only, ONLY if not already primary and memory looks ok.
    # Gated behind PHASE7_TRY_MPS=1 to stay memory-safe by default.
    if primary != "mps" and torch.backends.mps.is_available() and os.environ.get("PHASE7_TRY_MPS", "0") == "1":
        try:
            mps_res = run_on_device("mps", do_backward=False)
            results["runs"].append(mps_res)
        except Exception as e:  # never let the secondary anchor crash the probe
            print(f"MPS secondary anchor skipped: {type(e).__name__}: {str(e)[:200]}", flush=True)

    # ----- derive the local train-step estimate + a rough T4 cross-check -----
    p = primary_res
    fwd = p["forward_median_s"]
    if p.get("fwd_bwd_feasible"):
        # measured fwd+bwd; a full train step adds the optimizer .step() (~0.1-0.3x fwd
        # for AdamW elementwise). Estimate step = fwd_bwd + ~0.2*fwd as a small add-on.
        train_step_measuredish = p["fwd_bwd_median_s"] + 0.2 * fwd
        p["train_step_est_s"] = round(train_step_measuredish, 4)
        p["train_step_basis"] = "measured fwd+bwd + 0.2x fwd optimizer add-on"
    else:
        # fallback heuristic: train step ~= 3x forward
        p["train_step_est_s"] = round(3.0 * fwd, 4)
        p["train_step_basis"] = "ESTIMATED 3x forward (backward infeasible locally)"
    print(f"\nLOCAL train-step estimate ({primary}): {p['train_step_est_s']}s/step "
          f"[{p['train_step_basis']}]", flush=True)

    # T4 cross-check (LABELLED UNRELIABLE, +/-3x). We do NOT scale CPU->T4 naively;
    # instead we report the local number and note the cost lane uses published-benchmark
    # interpolation as the primary basis. As a courtesy cross-check we bracket a T4
    # samples/s implied by the cost lane (~10 s/s central) against our local s/step.
    local_samples_per_s = 1.0 / p["train_step_est_s"] if p["train_step_est_s"] > 0 else float("nan")
    p["local_samples_per_s"] = round(local_samples_per_s, 3)
    results["costlane_central_t4_samples_per_s"] = 10.0
    results["costlane_band_t4_samples_per_s"] = [4.0, 25.0]
    print(f"local throughput ~{p['local_samples_per_s']} samples/s on {primary} "
          f"(batch 1). Cost lane assumes ~10 s/s on a T4 (band 4-25).", flush=True)

    out_json = os.path.join(_REPO, "results", "phase7_finetune_probe.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out_json}", flush=True)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
