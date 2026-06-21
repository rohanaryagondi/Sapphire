"""Phase 6 generation — FOLLOW-UP probe (interpretive hardening).

The first run (phase6_generation.py) showed: SMILES/protein span-INFILL is T5-format-compliant
and RDKit/AA-valid, but (i) open-ended de-novo collapsed to a SINGLE atom + <EOS> ('valid' but
hollow), and (ii) greedy infill substitutes plausible-but-different fragments (low exact recovery;
protein greedy collapses to homopolymers except hyper-conserved ubiquitin).

Three things to settle before writing conclusions, all on ONE base_458m load:

  (1) CLASSIFIER PATH INTACT? The sanity decode used a prompt without the @MAX-LEN ordering and
      returned '<SENTINEL_ID_0>)(<EOS>' (not '<1>'). Confirm the *validated* molnet readout still
      yields a real P(<1>) probability (rule out broken weights / wrong load).

  (2) IS DE-NOVO COLLAPSE A PROMPT ARTIFACT OR THE MODEL? Force length with min_new_tokens, try
      beam search, and SEED the decoder with a partial scaffold (prefix-only mask) so the model
      must *extend*. If it still won't produce a multi-atom molecule, the limitation is the model
      (no unconditional generative prior), not the prompt.

  (3) DOES INFILL IMPROVE WITH SAMPLING / SHORTER SPANS? Re-run a couple of drug infills with
      sampling + a short (2-char) interior span to see if exact-recovery is reachable at all, and
      whether sampling avoids the homopolymer attractor on proteins.

MEMORY: one model load, write JSON, exit. CPU-forced by default.
Run: USE_TF=0 USE_FLAX=0 /opt/anaconda3/envs/mammal/bin/python experiments/phase6_generation_probe2.py
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
FORCE_CPU = os.environ.get("PHASE6_GEN_FORCE_CPU", "1") == "1"

import json, sys, re, traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import torch
torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4))))

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
JSON_OUT = REPO / "results" / "phase6_generation_probe2.json"

SENTINEL_RE = re.compile(r"<SENTINEL_ID_\d+>")
SPECIAL_RE = re.compile(r"<[^>]+>")
AA = set("ACDEFGHIKLMNPQRSTVWY")


def _p(*a): print(*a, flush=True)


def canon(s):
    from rdkit import Chem
    from rdkit import RDLogger; RDLogger.DisableLog("rdApp.*")
    if not s: return None
    m = Chem.MolFromSmiles(s)
    if m is None: return None
    try: return Chem.MolToSmiles(m)
    except Exception: return None


def n_heavy(smi):
    from rdkit import Chem
    m = Chem.MolFromSmiles(smi) if smi else None
    return m.GetNumHeavyAtoms() if m else 0


def fill_of(decoded):
    if "<SENTINEL_ID_0>" not in decoded:
        return None
    after = decoded.split("<SENTINEL_ID_0>", 1)[1]
    nxt = SENTINEL_RE.search(after)
    raw = after[: nxt.start()] if nxt else after
    return SPECIAL_RE.sub("", raw).strip()


def load():
    from mammal_quiver.embed import BASE_SOURCE
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.model import Mammal
    device = "cpu" if FORCE_CPU else ("mps" if torch.backends.mps.is_available()
              else ("cuda" if torch.cuda.is_available() else "cpu"))
    _p(f"[load] {BASE_SOURCE} on {device}")
    model = Mammal.from_pretrained(BASE_SOURCE).to(device).eval()
    tp = os.path.join(BASE_SOURCE, "tokenizer") if os.path.isdir(BASE_SOURCE) else BASE_SOURCE
    tok = ModularTokenizerOp.from_pretrained(tp)
    return model, tok, device


@torch.no_grad()
def gen(model, tok, prompt, **kw):
    from mammal.keys import (ENCODER_INPUTS_ATTENTION_MASK, ENCODER_INPUTS_STR,
                             ENCODER_INPUTS_TOKENS, CLS_PRED)
    seed = kw.pop("seed", None)
    if seed is not None: torch.manual_seed(seed)
    sd = {ENCODER_INPUTS_STR: prompt}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.generate([sd], **kw)
    ids = [i for i in out[CLS_PRED][0].tolist() if i != model.config.t5_config.pad_token_id]
    return tok._tokenizer.decode(ids)


def main():
    R = {"phase": "phase6_generation_probe2", "timestamp": TS,
         "device": "cpu" if FORCE_CPU else "auto"}
    try:
        model, tok, device = load(); R["device_actual"] = device
    except Exception as e:
        R["fatal"] = repr(e); JSON_OUT.write_text(json.dumps(R, indent=2)); return

    # (1) classifier path intact — validated molnet readout, read real P(<1>)
    try:
        from mammal.keys import (ENCODER_INPUTS_ATTENTION_MASK, ENCODER_INPUTS_STR,
                                 ENCODER_INPUTS_TOKENS, SCORES, CLS_PRED)
        def molnet_p1(smi, task="BBBP"):
            pos1 = tok.get_token_id("<1>"); pos0 = tok.get_token_id("<0>")
            prompt = (f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
                      f"<{task}><SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100>"
                      f"<SEQUENCE_NATURAL_START>{smi}<SEQUENCE_NATURAL_END><EOS>")
            sd = {ENCODER_INPUTS_STR: prompt}
            tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
                key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
            sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
            sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
            o = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
            sc = o[SCORES][0]
            dec = tok._tokenizer.decode([i for i in o[CLS_PRED][0].tolist()
                                         if i != model.config.t5_config.pad_token_id])
            p1 = float(sc[1, pos1]); p0 = float(sc[1, pos0])
            return {"decode": dec, "P1_raw": round(p1, 4), "P0_raw": round(p0, 4),
                    "P1_norm": round(p1 / (p1 + p0 + 1e-10), 4)}
        # diazepam (CNS-penetrant, BBBP should be high) vs a charged/large peripheral
        R["classifier_check"] = {
            "diazepam_BBBP": molnet_p1("CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21"),
            "ethanol_BBBP": molnet_p1("CCO"),
        }
        _p(f"[classifier] diazepam BBBP = {R['classifier_check']['diazepam_BBBP']}")
    except Exception as e:
        R["classifier_check"] = {"error": repr(e), "tb": traceback.format_exc()}

    # (2) de-novo: force length / beams / scaffold-extend
    HEADER = ("<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
              "<SEQUENCE_NATURAL_START>{body}<SEQUENCE_NATURAL_END><EOS>")
    denovo = []
    trials = [
        ("sentinel_only_greedy", "<SENTINEL_ID_0>", dict(max_new_tokens=64)),
        ("sentinel_only_min20", "<SENTINEL_ID_0>", dict(max_new_tokens=64, min_new_tokens=20)),
        ("sentinel_only_beam5", "<SENTINEL_ID_0>", dict(max_new_tokens=64, num_beams=5)),
        ("sentinel_only_beam5_min20", "<SENTINEL_ID_0>", dict(max_new_tokens=64, num_beams=5, min_new_tokens=20)),
        # scaffold-extend: give a benzene-ring prefix then a sentinel to continue
        ("scaffold_c1ccccc1_ext", "c1ccccc1<SENTINEL_ID_0>", dict(max_new_tokens=48, min_new_tokens=10)),
        ("scaffold_CCO_ext", "CCN<SENTINEL_ID_0>", dict(max_new_tokens=48, min_new_tokens=10)),
        # sampling with forced length
        ("sample_T1.2_min20", "<SENTINEL_ID_0>", dict(max_new_tokens=64, do_sample=True, temperature=1.2, top_p=0.95, min_new_tokens=20, seed=7)),
    ]
    for name, body, kw in trials:
        try:
            dec = gen(model, tok, HEADER.format(body=body), **kw)
        except Exception as e:
            denovo.append({"trial": name, "error": repr(e)}); continue
        f = fill_of(dec)
        cand = f if f is not None else SPECIAL_RE.sub("", dec).strip()
        c = canon(cand)
        denovo.append({"trial": name, "decoded": dec[:160], "candidate": cand,
                       "canonical": c, "valid": c is not None,
                       "heavy_atoms": n_heavy(c) if c else 0})
        _p(f"  [denovo] {name:26s} valid={c is not None} heavy={n_heavy(c) if c else 0} cand={cand[:40]!r}")
    R["denovo_forced"] = denovo

    # (3) infill with sampling + short span; protein sampling vs homopolymer
    def smi_infill_prompt(pre, suf):
        return ("<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
                f"<SEQUENCE_NATURAL_START>{pre}<SENTINEL_ID_0>{suf}<SEQUENCE_NATURAL_END><EOS>")
    def prot_infill_prompt(pre, suf):
        return ("<@TOKENIZER-TYPE=AA><MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
                f"<SEQUENCE_NATURAL_START>{pre}<SENTINEL_ID_0>{suf}<SEQUENCE_NATURAL_END><EOS>")

    # short 2-char interior span on aspirin: CC(=O)Oc1ccccc1C(=O)O — mask 'cc' at idx 11..13
    asp = "CC(=O)Oc1ccccc1C(=O)O"; a, b = 11, 13
    pre, held, suf = asp[:a], asp[a:b], asp[b:]
    short = {"parent": asp, "held": held, "greedy": None, "samples": []}
    try:
        dec = gen(model, tok, smi_infill_prompt(pre, suf), max_new_tokens=12)
        fg = fill_of(dec); rc = canon(pre + (fg or "") + suf)
        short["greedy"] = {"fill": fg, "recon_canonical": rc, "exact": fg == held,
                           "equals_parent": rc == canon(asp)}
        for k in range(8):
            d2 = gen(model, tok, smi_infill_prompt(pre, suf), max_new_tokens=12,
                     do_sample=True, temperature=1.0, top_p=0.95, seed=20 + k)
            f2 = fill_of(d2); r2 = canon(pre + (f2 or "") + suf)
            short["samples"].append({"fill": f2, "recon_canonical": r2,
                                     "exact": f2 == held, "equals_parent": r2 == canon(asp)})
        short["any_sample_recovers_parent"] = any(s["equals_parent"] for s in short["samples"])
        _p(f"  [short-infill aspirin] greedy_exact={short['greedy']['exact']} "
           f"any_sample_parent={short['any_sample_recovers_parent']}")
    except Exception as e:
        short["error"] = repr(e)
    R["smiles_short_span_infill"] = short

    # protein: lysozyme greedy collapsed to SSSSSSS — does sampling escape the homopolymer?
    lyso = "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSR"
    L = len(lyso); sl = max(3, L // 6); ca = (L - sl) // 2; cb = ca + sl
    pre, held, suf = lyso[:ca], lyso[ca:cb], lyso[cb:]
    prot = {"held": held, "samples": []}
    try:
        for k in range(6):
            d = gen(model, tok, prot_infill_prompt(pre, suf), max_new_tokens=sl + 12,
                    do_sample=True, temperature=1.0, top_p=0.95, seed=40 + k)
            f = fill_of(d) or ""
            faa = "".join(c for c in f if c in AA)
            ov = min(len(faa), len(held))
            aar = sum(1 for i in range(ov) if faa[i] == held[i]) / len(held) if held else 0
            homo = (len(set(faa)) <= 1) if faa else True
            prot["samples"].append({"fill": f, "aar": round(aar, 3), "homopolymer": homo})
        prot["mean_sample_aar"] = round(sum(s["aar"] for s in prot["samples"]) / len(prot["samples"]), 3)
        prot["any_non_homopolymer"] = any(not s["homopolymer"] for s in prot["samples"])
        _p(f"  [prot sampling lysozyme] mean_AAR={prot['mean_sample_aar']} "
           f"any_non_homopolymer={prot['any_non_homopolymer']}")
    except Exception as e:
        prot["error"] = repr(e)
    R["protein_sampling_infill"] = prot

    JSON_OUT.write_text(json.dumps(R, indent=2))
    _p(f"[done] wrote {JSON_OUT}")


if __name__ == "__main__":
    main()
