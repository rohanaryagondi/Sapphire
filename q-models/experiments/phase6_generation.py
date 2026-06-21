"""Phase 6 — GENERATION CAPABILITY of the public base MAMMAL (base_458m).

THE question prior phases never asked: every Quiver phase used MAMMAL's generative
READOUT (decode 1 token, read P(<1>) for classification) but never exercised the model
as an actual GENERATOR. The paper (arXiv 2410.22367, npj Drug Discovery 2026) advertises
generation — antibody CDR infilling (+19% AAR), PPI generation, molecule design — but the
upstream-code lane (docs/lit/05_upstream_code.md) established that the PUBLIC repo ships
NO free-generation example, NO checkpoint, NO test for any generative-output task. Every
shipped `generate()` call is the 1-token classifier readout (max_new_tokens=5, read pos 1).

So: what can the PUBLIC base_458m weights actually generate off-the-shelf? `Mammal.generate`
is a thin wrapper over HF `T5ForConditionalGeneration.generate` and forwards do_sample /
num_beams / max_new_tokens unchanged, so de-novo decoding is *implementable* — but unvalidated.
This script BUILDS and MEASURES that harness.

MAMMAL is a T5 pretrained with SPAN CORRUPTION over AA + SMILES vocabularies. The native
generative ability is therefore SPAN INFILLING: place <SENTINEL_ID_0> where a span is removed;
a correctly-pretrained T5 decoder emits `<SENTINEL_ID_0> <fill tokens> <SENTINEL_ID_1> ...`.
We test exactly that, plus open-ended decoding, in both modalities:

  (a) SMALL MOLECULE / SMILES
      - INFILL: take a known-drug SMILES, mask an interior contiguous span with <SENTINEL_ID_0>,
        generate, splice the predicted fill back in, RDKit-parse the reconstructed SMILES.
        Metrics: T5-format compliance (did it emit the sentinel?), reconstructed-validity rate,
        exact-recovery rate (did it reproduce the held-out span / a valid isomer of the parent?).
      - DE-NOVO: prompt only the molecule header + <SENTINEL_ID_0>, sample N completions,
        RDKit parse rate + uniqueness + example valid structures.

  (b) PROTEIN / AA SEQUENCE
      - INFILL: mask an interior span of a real protein with <SENTINEL_ID_0>, generate, check
        the fill is (i) T5-format-compliant, (ii) composed of valid AA letters, (iii) plausible
        (length, recovery of the true residues — an AAR-style accuracy vs the held-out span).

Decoding configs: greedy (deterministic) + a couple of sampling temperatures, modest beams.

HONEST SCOPE (stated in output): the antibody-design and PPI-generation HEADS are NOT public —
only base_458m + the 9 task heads ship. This characterizes what the BASE weights support via
the pretraining span task and open decoding; anything requiring the unpublished design heads is
marked as such and NOT claimed.

MEMORY: loads ONE model (base_458m), computes everything, writes JSON+MD, exits. CPU-forced by
default (PHASE6_GEN_FORCE_CPU=1) — MPS uses unified RAM and thrashes on the 18 GB machine.

Run:  USE_TF=0 USE_FLAX=0 /opt/anaconda3/envs/mammal/bin/python experiments/phase6_generation.py
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
FORCE_CPU = os.environ.get("PHASE6_GEN_FORCE_CPU", "1") == "1"

import json, sys, re, gc, traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch
torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4))))

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS = REPO / "results"
JSON_OUT = RESULTS / "phase6_generation.json"
MD_OUT = RESULTS / "phase6_generation.md"


def _p(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------------------- inputs
# Known drug SMILES (canonical, neutral) — small/medium so the SMILES token sequence is short
# enough that a masked interior span is well-defined and the model has a fighting chance.
DRUGS = {
    "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "benzene": "c1ccccc1",
    "phenol": "Oc1ccccc1",
    "toluene": "Cc1ccccc1",
    "ethanol": "CCO",
}

# Real, well-characterized protein fragments (N-terminal windows; lengths kept modest so a
# masked interior span leaves enough flanking context). Sequences are standard UniProt.
PROTEINS = {
    # Ubiquitin (P0CG48) — 76 aa, extremely conserved; good infilling recovery target.
    "ubiquitin": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
    # Insulin A+B style short chain (human insulin B-chain, P01308 26-55 region).
    "insulin_b": "FVNQHLCGSHLVEALYLVCGERGFFYTPKT",
    # Lysozyme C (P00698) first 60 aa.
    "lysozyme": "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSR",
}

AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


# ----------------------------------------------------------------------------- model load
def load():
    from mammal_quiver.embed import BASE_SOURCE  # resolves local dir or HF id
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.model import Mammal
    device = "cpu" if FORCE_CPU else (
        "mps" if torch.backends.mps.is_available()
        else ("cuda" if torch.cuda.is_available() else "cpu"))
    _p(f"[load] source={BASE_SOURCE} device={device}")
    model = Mammal.from_pretrained(BASE_SOURCE).to(device).eval()
    tok_path = os.path.join(BASE_SOURCE, "tokenizer") if os.path.isdir(BASE_SOURCE) else BASE_SOURCE
    tok = ModularTokenizerOp.from_pretrained(tok_path)
    return model, tok, device


# ----------------------------------------------------------------------------- generate core
@torch.no_grad()
def generate_decoded(model, tok, prompt: str, max_new_tokens: int = 64,
                     do_sample: bool = False, temperature: float = 1.0,
                     num_beams: int = 1, top_p: float = 1.0, seed: int | None = None):
    """Run model.generate on a prompt string; return (decoded_str, token_ids list)."""
    from mammal.keys import (
        ENCODER_INPUTS_ATTENTION_MASK, ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS, CLS_PRED,
    )
    if seed is not None:
        torch.manual_seed(seed)
    sd = {ENCODER_INPUTS_STR: prompt}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    gen_kwargs = dict(max_new_tokens=max_new_tokens)
    if do_sample:
        gen_kwargs.update(do_sample=True, temperature=temperature, top_p=top_p)
    if num_beams and num_beams > 1:
        gen_kwargs.update(num_beams=num_beams, do_sample=False)
    out = model.generate([sd], **gen_kwargs)
    ids = out[CLS_PRED][0].tolist()
    # strip pad
    pad_id = model.config.t5_config.pad_token_id
    ids_nopad = [i for i in ids if i != pad_id]
    decoded = tok._tokenizer.decode(ids_nopad)
    return decoded, ids_nopad


# ----------------------------------------------------------------------------- parsing helpers
def canonical_smiles(s: str):
    """Return canonical SMILES if RDKit parses it, else None."""
    from rdkit import Chem
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    if not s:
        return None
    m = Chem.MolFromSmiles(s)
    if m is None:
        return None
    try:
        return Chem.MolToSmiles(m)
    except Exception:
        return None


# Strip the modular-tokenizer special markers from a decoded string. The fuse decode renders
# special tokens like '<SENTINEL_ID_0>' literally; SMILES/AA chars render as their literal text.
SENTINEL_RE = re.compile(r"<SENTINEL_ID_\d+>")
SPECIAL_RE = re.compile(r"<[^>]+>")


def extract_sentinel_fill(decoded: str) -> dict:
    """T5 span-infill decode looks like '<SENTINEL_ID_0>FILL<SENTINEL_ID_1>...'.
    Return the FILL between sentinel 0 and the next sentinel (or end), plus a compliance flag."""
    has_s0 = "<SENTINEL_ID_0>" in decoded
    fill = None
    if has_s0:
        after = decoded.split("<SENTINEL_ID_0>", 1)[1]
        # cut at the next sentinel token if present
        nxt = SENTINEL_RE.search(after)
        fill_raw = after[: nxt.start()] if nxt else after
        # remove any other special tokens (EOS/PAD/etc.) and whitespace
        fill = SPECIAL_RE.sub("", fill_raw).strip()
    return {"format_compliant": has_s0, "fill": fill}


def strip_specials(decoded: str) -> str:
    return SPECIAL_RE.sub("", decoded).strip()


# ----------------------------------------------------------------------------- prompt builders
def smiles_infill_prompt(prefix: str, suffix: str) -> str:
    """Mask an interior SMILES span: prefix + <SENTINEL_ID_0> + suffix, inside a small-molecule entity."""
    return (
        "<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        f"<SEQUENCE_NATURAL_START>{prefix}<SENTINEL_ID_0>{suffix}<SEQUENCE_NATURAL_END><EOS>"
    )


def smiles_denovo_prompt() -> str:
    """Open-ended: header + a single sentinel to fill, nothing else specified."""
    return (
        "<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        "<SEQUENCE_NATURAL_START><SENTINEL_ID_0><SEQUENCE_NATURAL_END><EOS>"
    )


def protein_infill_prompt(prefix: str, suffix: str) -> str:
    return (
        "<@TOKENIZER-TYPE=AA><MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
        f"<SEQUENCE_NATURAL_START>{prefix}<SENTINEL_ID_0>{suffix}<SEQUENCE_NATURAL_END><EOS>"
    )


# ----------------------------------------------------------------------------- experiments
def run_smiles_infill(model, tok):
    """Mask an interior span of each drug SMILES and try to recover it (greedy)."""
    rows = []
    for name, smi in DRUGS.items():
        parent_canon = canonical_smiles(smi)
        L = len(smi)
        if L < 6:
            # too short to carve an interior span; mask the middle char
            cut_a, cut_b = L // 2, L // 2 + 1
        else:
            # mask a contiguous interior span ~1/3 of the string, centered
            span_len = max(2, L // 3)
            cut_a = (L - span_len) // 2
            cut_b = cut_a + span_len
        prefix, held, suffix = smi[:cut_a], smi[cut_a:cut_b], smi[cut_b:]
        prompt = smiles_infill_prompt(prefix, suffix)
        try:
            decoded, ids = generate_decoded(model, tok, prompt, max_new_tokens=48, do_sample=False)
        except Exception as e:
            rows.append({"name": name, "error": repr(e)})
            continue
        sent = extract_sentinel_fill(decoded)
        # Reconstruction strategy A: splice the sentinel fill into prefix...suffix
        recon = None
        recon_canon = None
        if sent["fill"] is not None:
            recon = prefix + sent["fill"] + suffix
            recon_canon = canonical_smiles(recon)
        # Reconstruction strategy B: if no sentinel, treat the whole decoded (specials stripped)
        # as a free SMILES guess.
        free = strip_specials(decoded)
        free_canon = canonical_smiles(free)
        rows.append({
            "name": name,
            "parent_smiles": smi,
            "parent_canonical": parent_canon,
            "masked_prefix": prefix,
            "held_out_span": held,
            "masked_suffix": suffix,
            "decoded_raw": decoded[:300],
            "format_compliant": sent["format_compliant"],
            "predicted_fill": sent["fill"],
            "fill_recovers_span_exact": (sent["fill"] == held) if sent["fill"] is not None else False,
            "reconstructed_smiles": recon,
            "reconstructed_canonical": recon_canon,
            "reconstructed_valid": recon_canon is not None,
            "reconstructed_equals_parent": (recon_canon is not None and recon_canon == parent_canon),
            "free_strip_canonical": free_canon,
            "free_strip_valid": free_canon is not None,
        })
        ok = "OK" if recon_canon else ("free:OK" if free_canon else "INVALID")
        _p(f"  [smiles-infill] {name:12s} compliant={sent['format_compliant']} "
           f"fill={str(sent['fill'])[:24]!r} recon_valid={recon_canon is not None} {ok}")
    n = len([r for r in rows if "error" not in r])
    summary = {
        "n": n,
        "format_compliant_rate": _rate(rows, "format_compliant"),
        "reconstructed_valid_rate": _rate(rows, "reconstructed_valid"),
        "exact_span_recovery_rate": _rate(rows, "fill_recovers_span_exact"),
        "reconstructed_equals_parent_rate": _rate(rows, "reconstructed_equals_parent"),
        "free_strip_valid_rate": _rate(rows, "free_strip_valid"),
    }
    return {"rows": rows, "summary": summary}


def run_smiles_denovo(model, tok, n_samples=12):
    """Open-ended SMILES generation: header + sentinel, sample completions, RDKit parse rate."""
    rows = []
    configs = (
        [("greedy", dict(do_sample=False))]
        + [(f"sample_T{t}", dict(do_sample=True, temperature=t, top_p=0.95))
           for t in (0.7, 1.0, 1.3)]
    )
    prompt = smiles_denovo_prompt()
    for cfg_name, kw in configs:
        for k in range(n_samples if kw.get("do_sample") else 1):
            try:
                decoded, ids = generate_decoded(model, tok, prompt, max_new_tokens=64,
                                                seed=1000 + k, **kw)
            except Exception as e:
                rows.append({"config": cfg_name, "k": k, "error": repr(e)})
                continue
            sent = extract_sentinel_fill(decoded)
            cand = sent["fill"] if sent["fill"] else strip_specials(decoded)
            canon = canonical_smiles(cand)
            rows.append({
                "config": cfg_name, "k": k,
                "decoded_raw": decoded[:200],
                "candidate": cand,
                "canonical": canon,
                "valid": canon is not None,
            })
    valids = [r["canonical"] for r in rows if r.get("valid")]
    uniq = sorted(set(valids))
    summary = {
        "n_total": len([r for r in rows if "error" not in r]),
        "valid_rate": _rate(rows, "valid"),
        "n_valid": len(valids),
        "n_unique_valid": len(uniq),
        "examples_unique_valid": uniq[:15],
    }
    _p(f"  [smiles-denovo] valid_rate={summary['valid_rate']} "
       f"n_unique_valid={summary['n_unique_valid']}")
    return {"rows": rows, "summary": summary}


def run_protein_infill(model, tok):
    """Mask an interior span of each protein; check format-compliance, AA-validity, recovery (AAR)."""
    rows = []
    for name, seq in PROTEINS.items():
        L = len(seq)
        span_len = max(3, L // 6)
        cut_a = (L - span_len) // 2
        cut_b = cut_a + span_len
        prefix, held, suffix = seq[:cut_a], seq[cut_a:cut_b], seq[cut_b:]
        prompt = protein_infill_prompt(prefix, suffix)
        try:
            # allow a bit more than the span length so it can emit the closing sentinel
            decoded, ids = generate_decoded(model, tok, prompt,
                                            max_new_tokens=span_len + 16, do_sample=False)
        except Exception as e:
            rows.append({"name": name, "error": repr(e)})
            continue
        sent = extract_sentinel_fill(decoded)
        fill = sent["fill"] or ""
        fill_aa = "".join(ch for ch in fill if ch in AA_ALPHABET)
        aa_valid_frac = (len(fill_aa) / len(fill)) if fill else 0.0
        # AAR: position-wise identity over the overlap of fill vs held span
        overlap = min(len(fill_aa), len(held))
        matches = sum(1 for i in range(overlap) if fill_aa[i] == held[i])
        aar = (matches / len(held)) if held else 0.0
        rows.append({
            "name": name,
            "seq_len": L,
            "held_out_span": held,
            "span_len": span_len,
            "decoded_raw": decoded[:300],
            "format_compliant": sent["format_compliant"],
            "predicted_fill": fill,
            "predicted_fill_len": len(fill),
            "aa_valid_fraction": round(aa_valid_frac, 3),
            "all_chars_valid_aa": (fill != "" and aa_valid_frac == 1.0),
            "fill_recovers_span_exact": (fill == held),
            "aar_vs_held_span": round(aar, 3),
        })
        _p(f"  [prot-infill] {name:10s} compliant={sent['format_compliant']} "
           f"fill_len={len(fill)} aa_valid={aa_valid_frac:.2f} AAR={aar:.2f} fill={fill[:20]!r}")
    summary = {
        "n": len([r for r in rows if "error" not in r]),
        "format_compliant_rate": _rate(rows, "format_compliant"),
        "all_chars_valid_aa_rate": _rate(rows, "all_chars_valid_aa"),
        "exact_span_recovery_rate": _rate(rows, "fill_recovers_span_exact"),
        "mean_aar_vs_held": _mean(rows, "aar_vs_held_span"),
        "mean_aa_valid_fraction": _mean(rows, "aa_valid_fraction"),
    }
    return {"rows": rows, "summary": summary}


def _rate(rows, key):
    vals = [bool(r.get(key)) for r in rows if "error" not in r and key in r]
    return round(sum(vals) / len(vals), 3) if vals else None


def _mean(rows, key):
    vals = [r[key] for r in rows if "error" not in r and isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None


# ----------------------------------------------------------------------------- main
def main():
    result = {
        "phase": "phase6_generation",
        "timestamp": TS,
        "model": "base_458m (ibm/biomed.omics.bl.sm.ma-ted-458m)",
        "device": "cpu" if FORCE_CPU else "auto",
        "question": ("What can the PUBLIC base_458m weights actually GENERATE off-the-shelf? "
                     "Exercise model.generate (not the 1-token classifier readout) for SMILES "
                     "infilling/de-novo and protein span infilling; validate with RDKit/AA checks."),
        "scope_caveat": ("Antibody-design and PPI-generation HEADS are NOT public — only base_458m "
                         "+ 9 task heads ship. This tests the BASE model's pretraining span-infill / "
                         "open decoding only. The paper's +19% AAR antibody CDR infilling and PPI "
                         "generation require the UNPUBLISHED design checkpoints and are NOT tested here."),
    }
    try:
        model, tok, device = load()
        result["device_actual"] = device
    except Exception as e:
        result["fatal_load_error"] = repr(e)
        result["traceback"] = traceback.format_exc()
        JSON_OUT.write_text(json.dumps(result, indent=2))
        _p("[FATAL] model load failed; wrote partial JSON")
        return

    # sanity: reproduce a known 1-token classification decode (proves generate path is alive)
    try:
        from mammal.keys import ENCODER_INPUTS_STR
        chk_prompt = (
            "<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
            "<BBBP><SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100>"
            "<SEQUENCE_NATURAL_START>CCO<SEQUENCE_NATURAL_END><EOS>"
        )
        dec, _ = generate_decoded(model, tok, chk_prompt, max_new_tokens=5, do_sample=False)
        result["sanity_classification_decode"] = dec
        _p(f"[sanity] BBBP(CCO) decode = {dec!r}")
    except Exception as e:
        result["sanity_classification_decode_error"] = repr(e)

    for label, fn in [
        ("smiles_infill", lambda: run_smiles_infill(model, tok)),
        ("smiles_denovo", lambda: run_smiles_denovo(model, tok)),
        ("protein_infill", lambda: run_protein_infill(model, tok)),
    ]:
        _p(f"[run] {label}")
        try:
            result[label] = fn()
        except Exception as e:
            result[label] = {"error": repr(e), "traceback": traceback.format_exc()}
            _p(f"[err] {label}: {e!r}")
        gc.collect()

    JSON_OUT.write_text(json.dumps(result, indent=2))
    _p(f"[done] wrote {JSON_OUT}")

    # one-line verdict echoed to stdout
    si = result.get("smiles_infill", {}).get("summary", {})
    sd = result.get("smiles_denovo", {}).get("summary", {})
    pi = result.get("protein_infill", {}).get("summary", {})
    _p("\n==== VERDICT (rates) ====")
    _p(f"SMILES infill : compliant={si.get('format_compliant_rate')} "
       f"recon_valid={si.get('reconstructed_valid_rate')} exact={si.get('exact_span_recovery_rate')}")
    _p(f"SMILES de-novo: valid={sd.get('valid_rate')} unique_valid={sd.get('n_unique_valid')}")
    _p(f"Protein infill: compliant={pi.get('format_compliant_rate')} "
       f"aa_valid={pi.get('all_chars_valid_aa_rate')} mean_AAR={pi.get('mean_aar_vs_held')}")


if __name__ == "__main__":
    main()
