"""MAMMAL 458M layer sweep on the 40-gene CRISPR-N panel — fair companion to the
ESM-2 / ESM-C layer sweeps, closing the Track-1 best-vs-best comparison.

MAMMAL's canonical 0.750 (phase5) uses the masked-mean-pool of the encoder's LAST
hidden state (`mammal_quiver/embed.py`). The ESM sweeps showed last-layer is a trap
and an early-mid layer wins (ESM-2-650M 0.750 -> 0.875). So: does MAMMAL also jump
with layer selection? If yes, the true Track-1 winner is still open; if it lands
above ESM-2-650M's 0.875, MAMMAL stays the incumbent.

Method: register forward hooks on every encoder transformer block (auto-detected as
the longest ModuleList of repeated layer modules), run `forward_encoder_only`, and
masked-mean-pool each block's output with the SAME mask/recipe as embed.py (include
special tokens — the canonical MAMMAL pooling, so the post-norm last layer reproduces
~0.750 as a sanity check). NN-recall raw + centered per layer; best; per-family.

Run (shared mammal env): USE_TF=0 USE_FLAX=0 \
  /opt/anaconda3/envs/mammal/bin/python experiments/mammal_layer_sweep.py
Out: results/mammal_layer_sweep.json
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
RESULTS = REPO / "results"
ESM2_JSON = RESULTS / "compare_esm2_650m.json"
SEQ_CACHE = RESULTS / "_uniprot_cache.json"
OUT_JSON = RESULTS / "mammal_layer_sweep.json"

from mammal_quiver.embed import (  # noqa: E402
    load_base_model, _prompt_protein, _HID, _MASK,
)
from mammal.keys import (  # noqa: E402
    ENCODER_INPUTS_ATTENTION_MASK, ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS,
)


def _p(*a):
    print(*a, flush=True)


def cosine_sim_matrix(E):
    n = np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
    Z = E / n
    return Z @ Z.T


def nn_recall(sim, labels):
    n = len(labels); c = 0
    for i in range(n):
        row = sim[i].copy(); row[i] = -np.inf
        if labels[int(np.argmax(row))] == labels[i]:
            c += 1
    return c / n


def per_family_recall(sim, labels):
    by = {}
    for i in range(len(labels)):
        row = sim[i].copy(); row[i] = -np.inf
        nn = int(np.argmax(row))
        by.setdefault(labels[i], []).append(1 if labels[nn] == labels[i] else 0)
    return {f: float(np.mean(v)) for f, v in by.items()}


def find_encoder_blocks(model):
    """Longest ModuleList of repeated transformer-like layer modules = encoder stack."""
    best = None  # (len, name, module)
    for name, mod in model.named_modules():
        if type(mod).__name__ == "ModuleList" and len(mod) >= 4:
            child_cls = type(mod[0]).__name__
            if any(k in child_cls.lower() for k in ["layer", "block", "encoder"]):
                if best is None or len(mod) > best[0]:
                    best = (len(mod), name, mod)
    if best is None:  # fallback: any longest ModuleList
        for name, mod in model.named_modules():
            if type(mod).__name__ == "ModuleList" and (best is None or len(mod) > best[0]):
                best = (len(mod), name, mod)
    return best


def masked_pool(h, m):
    # h: (1,L,D), m: (1,L) — same recipe as embed.py (include special tokens)
    m = m.to(h.dtype)
    pooled = (h * m.unsqueeze(-1)).sum(1) / m.sum(1, keepdim=True).clamp(min=1)
    return pooled.squeeze(0).float().cpu().numpy().astype(np.float64)


def main():
    t0 = datetime.now()
    proteins = json.loads(ESM2_JSON.read_text())["proteins"]
    labels = [p["family"] for p in proteins]
    cache = json.loads(SEQ_CACHE.read_text())
    seqs = [cache[p["accession"]] for p in proteins]
    _p(f"panel: {len(proteins)} proteins")

    model, tok, device = load_base_model(device="cpu")
    model.eval()
    n_blocks, stack_name, blocks = find_encoder_blocks(model)
    _p(f"encoder block stack: '{stack_name}'  ({n_blocks} blocks, child={type(blocks[0]).__name__})")

    # hook every block to capture its output hidden state
    captured = {}

    def mk_hook(i):
        def hook(_m, _inp, out):
            h = out[0] if isinstance(out, (tuple, list)) else out
            captured[i] = h.detach()
        return hook

    handles = [blocks[i].register_forward_hook(mk_hook(i)) for i in range(n_blocks)]

    # per_layer[i] = list of pooled vectors; plus 'final' = post-norm encoder_last_hidden_state
    per_layer = [[] for _ in range(n_blocks)]
    final_pooled = []
    with torch.no_grad():
        for idx, seq in enumerate(seqs):
            captured.clear()
            sd = {ENCODER_INPUTS_STR: _prompt_protein(seq), "data.sample_id": 0}
            tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
                key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
                key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
            sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS]).to(model.device)
            sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK]).to(model.device)
            out = model.forward_encoder_only([sd])
            rec = out[0] if isinstance(out, list) else out
            mask = rec[_MASK]
            if mask.dim() == 1:
                mask = mask.unsqueeze(0)
            for i in range(n_blocks):
                h = captured[i]
                if h.dim() == 2:
                    h = h.unsqueeze(0)
                per_layer[i].append(masked_pool(h, mask))
            hl = rec[_HID]
            if hl.dim() == 2:
                hl = hl.unsqueeze(0)
            final_pooled.append(masked_pool(hl, mask))
            if (idx + 1) % 10 == 0:
                _p(f"  {idx+1}/{len(seqs)}")
    for h in handles:
        h.remove()

    rows = []
    for i in range(n_blocks):
        E = np.array(per_layer[i])
        raw = nn_recall(cosine_sim_matrix(E), labels)
        Ec = E - E.mean(0, keepdims=True)
        cen = nn_recall(cosine_sim_matrix(Ec), labels)
        rows.append({"block": i, "nn_raw": float(raw), "nn_centered": float(cen),
                     "best": float(max(raw, cen))})

    Ef = np.array(final_pooled)
    final_raw = nn_recall(cosine_sim_matrix(Ef), labels)
    final_cen = nn_recall(cosine_sim_matrix(Ef - Ef.mean(0, keepdims=True)), labels)

    best = max(rows, key=lambda r: r["best"])
    bL = best["block"]
    Eb = np.array(per_layer[bL])
    cen_better = best["nn_centered"] >= best["nn_raw"]
    Euse = (Eb - Eb.mean(0, keepdims=True)) if cen_better else Eb
    best_fam = per_family_recall(cosine_sim_matrix(Euse), labels)

    result = {
        "test": "mammal_458m_layer_sweep_crispr_n_panel",
        "timestamp": t0.isoformat(),
        "model": "ibm/biomed.omics.bl.sm.ma-ted-458m (base_458m)",
        "encoder_block_stack": stack_name, "n_blocks": n_blocks,
        "embedding_dim": int(Ef.shape[1]),
        "pooling": "masked-mean over all tokens (embed.py recipe, incl. special tokens)",
        "final_post_norm_nn": {"raw": float(final_raw), "centered": float(final_cen),
                               "note": "encoder_last_hidden_state = the canonical phase5 0.750 readout (sanity check)"},
        "per_block": rows,
        "best_block": {"block": bL, "nn_raw": best["nn_raw"], "nn_centered": best["nn_centered"],
                       "used": "centered" if cen_better else "raw",
                       "per_family_nn_recall": best_fam},
        "references": {"esm2_650M_best": 0.875, "esm2_3B_best": 0.850, "esm2_15B_best": 0.850,
                       "esmc_600M_best": 0.825, "mammal_canonical_last_layer": 0.750, "bar": 0.80},
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    _p("\n=== MAMMAL 458M layer sweep ===")
    _p(f"  {'block':>5} {'raw':>7} {'centered':>9} {'best':>7}")
    for r in rows:
        mark = "  <-- BEST" if r["block"] == bL else ""
        _p(f"  {r['block']:>5} {r['nn_raw']:>7.3f} {r['nn_centered']:>9.3f} {r['best']:>7.3f}{mark}")
    _p(f"\n  post-norm final (canonical 0.750 sanity): raw {final_raw:.3f} / centered {final_cen:.3f}")
    _p(f"  BEST block {bL}: {best['best']:.3f} ({result['best_block']['used']})")
    _p(f"  best-block per-family: {best_fam}")
    _p(f"  refs: ESM-2-650M 0.875, 3B/15B 0.850, ESM-C 0.825, MAMMAL canonical 0.750")
    bestv = best["best"]
    if bestv >= 0.875 + 1e-9:
        _p(f"  => MAMMAL WINS Track 1 with layer selection ({bestv:.3f} > ESM-2-650M 0.875)")
    elif bestv >= 0.85:
        _p(f"  => MAMMAL competitive ({bestv:.3f}); within noise of the ESM ladder")
    elif bestv > 0.750 + 1e-9:
        _p(f"  => MAMMAL also benefits from layer selection ({bestv:.3f}) but trails ESM-2-650M 0.875")
    else:
        _p(f"  => layer selection does NOT lift MAMMAL above its canonical 0.750")
    _p(f"\nSaved -> {OUT_JSON}\nElapsed: {(datetime.now()-t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
