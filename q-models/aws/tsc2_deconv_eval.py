"""Quiver TARGET DECONVOLUTION eval: can a SEQUENCE-based DTI model recover Ben's
TSC2-screen deconvolution? — BALM (cosine) + PLAPT (affinity) on the PKM2 + PPARD panel.

THE TASK
========
Ben's TSC2 Optopatch phenotype-rescue screen produced two hits (QS0069567, QS0113172).
Against the DFP library they functionally matched known reference compounds, deconvolving to:
  - PKM2  (Pyruvate kinase M2,  UniProt P14618) — Dasa-58 is the confirmed reference activator.
  - PPARD (PPAR-delta,          UniProt Q03181) — GSK 3787 is the confirmed reference antagonist.
QS0113172 matched BOTH targets; QS0069567 matched PPARD only. Five control compounds bind NEITHER.

QUESTION: scoring every compound x {PKM2, PPARD} with each model, does the model
  (A) separate each target's binders from the controls (per-target AUROC), and
  (B) put each hit's ANNOTATED target on top (deconvolution argmax)?
A sequence-only DTI model recovering the wet-lab DFP deconvolution would be a real
Track-2 win; failure (e.g. controls scoring as high as hits, or argmax landing on the
wrong target) is itself a finding about the operating envelope.

MODELS (both: pretrained weights, protein SEQUENCE + ligand SMILES, NO 3D structure)
====================================================================================
  1. BALM  (github.com/meyresearch/BALM) — ESM-2-150M (protein) + ChemBERTa-77M (ligand)
     two-tower -> shared embedding space; cosine(protein, drug) IS the binding score
     (HIGHER = more likely binder), also mapped to a pKd. Loader/API reused VERBATIM from
     aws/balm_crossmodal_eval.py / aws/balm_characterization.py (checkpoint
     BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse, balm_peft.yaml config).
     CAVEAT: ESM-2 truncates at 1024 tokens; PKM2 (531 aa) and PPARD (441 aa) both fit
     comfortably, so unlike the Nav1.8/mTOR panels there is NO truncation wall here.

  2. PLAPT (github.com/Bindwell/PLAPT) — branched transformer on frozen ProtBERT +
     ChemBERTa embeddings; affinity head ships as models/affinity_predictor.onnx.
     API reused VERBATIM from aws/dti_nav_eval.py:
       from plapt import Plapt; Plapt(...).predict_affinity(prots, smiles)
     -> list of dicts with key `neg_log10_affinity_M` (pKd-like; HIGHER = STRONGER binder).

Each model section + each analysis is independently try/except-guarded so a single
failure still banks partial results. Writes JSON to env OUT
(default /root/deconv_out/tsc2_deconv_result.json).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.request
from pathlib import Path

import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
PANEL = Path(os.environ.get("PANEL", "/opt/tsc2_deconv_panel.json"))
OUT = Path(os.environ.get("OUT", "/root/deconv_out/tsc2_deconv_result.json"))
BALM_DIR = Path(os.environ.get("BALM_DIR", "/opt/BALM"))
PLAPT_DIR = Path(os.environ.get("PLAPT_DIR", "/opt/PLAPT"))
CKPT = os.environ.get("BALM_CKPT", "BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse")
CONFIG = os.environ.get("BALM_CONFIG", str(BALM_DIR / "default_configs" / "balm_peft.yaml"))

# Hardcoded canonical UniProt sequences (fallback ONLY if the live REST fetch fails).
# NOTE: these are best-effort transcriptions of the canonical human isoforms for
# P14618 (PKM2, ~531 aa) and Q03181 (PPARD, ~441 aa). The PRIMARY path is the live
# UniProt REST fetch (authoritative); the run records `seq_source` so a fallback is
# never silent. If a fallback sequence is used, treat its scores as provisional and
# re-run once REST is reachable rather than trusting a hand-copied string.
FALLBACK_SEQS = {
    "P14618": (  # PKM2 / Pyruvate kinase isozyme M2 (~531 aa)
        "MSKPHSEAGTAFIQTQQLHAAMADTFLEHMCRLDIDSPPITARNTGIICTIGPASRSVETLKEMIKSGMNVARLNFSHGTHEYHAETIKNVRTATESFASDPILYRPVAVALDTKGPEIRTGLIKGSGTAEVELKKGATLKITLDNAYMEKCDENILWLDYKNICKVVEVGSKIYVDDGLISLQVKQKGADFLVTEVENGGSLGSKKGVNLPGAAVDLPAVSEKDIQDLKFGVEQDVDMVFASFIRKASDVHEVRKVLGEKGKNIKIISKIENHEGVRRFDEILEASDGIMVARGDLGIEIPAEKVFLAQKMMIGRCNRAGKPVICATQMLESMIKKPRPTRAEGSDVANAVLDGADCIMLSGETAKGDYPLEAVRMQHLIAREAEAAIYHLQLFEELRRLAPITSDPTEATAVGAVEASFKCCSGAIIVLTKSGRSAHQVARYRPRAPIIAVTRNPQTARQAHLYRGIFPVLCKDPVQEAWAEDVDLRVNFAMNVGKARGFFKKGDVVIVLTGWRPGSGFTNTMRVVPVP"
    ),
    # PPARD: no verified hand-copy is committed here; the REST fetch is authoritative.
    # Leaving this absent means a REST failure for PPARD is reported as a missing
    # sequence (seq_source=None) instead of silently scoring against a wrong string.
}


# ---------------------------------------------------------------------------
# AUROC (rank-sum; ties get average rank). Higher score => label 1 (binder).
# ---------------------------------------------------------------------------
def auroc(labels, scores):
    labels = np.asarray(labels, dtype=float)
    scores = np.asarray(scores, dtype=float)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        ranks[order[i:j + 1]] = avg
        i = j + 1
    rank_pos = ranks[labels == 1].sum()
    n_pos, n_neg = len(pos), len(neg)
    return float((rank_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


# ---------------------------------------------------------------------------
# UniProt WT-sequence fetch (pattern from aws/mission_eval.py), with fallback.
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "tsc2-deconv-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    seq = "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))
    return seq


def get_target_sequences(targets):
    """targets: {name: {uniprot, ...}} -> {name: {acc, seq, source, len}}."""
    out = {}
    for name, meta in targets.items():
        acc = meta["uniprot"]
        seq, source = None, None
        try:
            seq = fetch_uniprot_seq(acc)
            if seq and len(seq) > 30:
                source = "uniprot_rest"
        except Exception as e:
            print(f"[warn] UniProt REST fetch failed for {name} ({acc}): {e}", flush=True)
        if not seq:
            seq = FALLBACK_SEQS.get(acc)
            source = "hardcoded_fallback"
            print(f"[warn] using HARDCODED FALLBACK sequence for {name} ({acc})", flush=True)
        out[name] = {"acc": acc, "seq": seq, "source": source,
                     "len": (len(seq) if seq else None)}
    return out


# ---------------------------------------------------------------------------
# BALM loader (reused VERBATIM from aws/balm_characterization.py::Balm).
# cosine = binding score (higher = more likely binder); also mapped to pKd.
# ---------------------------------------------------------------------------
class Balm:
    def __init__(self):
        import torch
        sys.path.insert(0, str(BALM_DIR))
        from balm import common_utils
        from balm.configs import Configs
        from balm.models import BALM
        from balm.models.utils import load_trained_model, load_pretrained_pkd_bounds
        from transformers import AutoTokenizer
        cfg = Configs(**common_utils.load_yaml(CONFIG))
        try:
            cfg.model_configs.checkpoint_path = CKPT
        except Exception as e:
            print(f"[warn] could not set checkpoint_path: {e}", flush=True)
        m = BALM(cfg.model_configs)
        m = load_trained_model(m, cfg.model_configs, is_training=False)
        m.to(DEVICE).eval()
        self.m, self.torch = m, torch
        self.lo, self.hi = load_pretrained_pkd_bounds(cfg.model_configs.checkpoint_path)
        self.pt = AutoTokenizer.from_pretrained(cfg.model_configs.protein_model_name_or_path)
        self.dt = AutoTokenizer.from_pretrained(cfg.model_configs.drug_model_name_or_path)
        self.pmax = 1024

    def score(self, seq, smi):
        import torch
        p = self.pt(seq.strip().replace(" ", ""), return_tensors="pt",
                    truncation=True, max_length=self.pmax).to(DEVICE)
        d = self.dt(smi, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            o = self.m({"protein_input_ids": p["input_ids"],
                        "protein_attention_mask": p["attention_mask"],
                        "drug_input_ids": d["input_ids"],
                        "drug_attention_mask": d["attention_mask"]})
        cos = float(o["cosine_similarity"].reshape(-1)[0])
        pkd = float(self.m.cosine_similarity_to_pkd(
            o["cosine_similarity"], pkd_upper_bound=self.hi,
            pkd_lower_bound=self.lo).reshape(-1)[0])
        return cos, pkd


# ---------------------------------------------------------------------------
# Scoring: 9 compounds x {PKM2, PPARD} for each model.
# Returns score_matrix: {qs_id: {target_name: score}} plus the primary score key.
# ---------------------------------------------------------------------------
def score_balm(compounds, target_seqs):
    balm = Balm()
    matrix = {}
    pkd_matrix = {}
    for c in compounds:
        matrix[c["qs_id"]] = {}
        pkd_matrix[c["qs_id"]] = {}
        for tname, tinfo in target_seqs.items():
            if not tinfo.get("seq"):
                matrix[c["qs_id"]][tname] = None
                pkd_matrix[c["qs_id"]][tname] = None
                continue
            cos, pkd = balm.score(tinfo["seq"], c["smiles"])
            matrix[c["qs_id"]][tname] = round(cos, 5)
            pkd_matrix[c["qs_id"]][tname] = round(pkd, 4)
    return {
        "model": "BALM (ESM-2-150M + ChemBERTa-77M, cosine=pKd)",
        "source": "github.com/meyresearch/BALM",
        "checkpoint": CKPT,
        "primary_score": "cosine",
        "score_key": "cosine similarity in shared space (higher = more likely binder)",
        "score_matrix": matrix,       # the matrix analyses operate on (cosine)
        "pkd_matrix": pkd_matrix,     # cosine->pKd mapping, recorded for reference
    }


def score_plapt(compounds, target_seqs):
    sys.path.insert(0, str(PLAPT_DIR))
    os.chdir(PLAPT_DIR)  # affinity_predictor.onnx referenced relative to repo root
    from plapt import Plapt
    plapt = Plapt(device=DEVICE, use_tqdm=False)
    matrix = {c["qs_id"]: {} for c in compounds}
    for tname, tinfo in target_seqs.items():
        if not tinfo.get("seq"):
            for c in compounds:
                matrix[c["qs_id"]][tname] = None
            continue
        smiles = [c["smiles"] for c in compounds]
        prots = [tinfo["seq"]] * len(smiles)  # strict 1:1 pairing
        preds = plapt.predict_affinity(prots, smiles)
        for c, p in zip(compounds, preds):
            matrix[c["qs_id"]][tname] = round(float(p["neg_log10_affinity_M"]), 5)
    return {
        "model": "PLAPT (ProtBERT + ChemBERTa -> ONNX affinity head)",
        "source": "github.com/Bindwell/PLAPT (models/affinity_predictor.onnx)",
        "primary_score": "neg_log10_affinity_M",
        "score_key": "neg_log10_affinity_M (pKd-like; higher = stronger binder)",
        "score_matrix": matrix,
    }


# ---------------------------------------------------------------------------
# Analysis (A): per-target binder-vs-control AUROC for one model.
#   PKM2 binders  = compounds with binds_PKM2 == 1, decoys = the 5 controls.
#   PPARD binders = compounds with binds_PPARD == 1, decoys = the 5 controls.
# ---------------------------------------------------------------------------
def analysis_A_auroc(compounds, score_matrix):
    controls = [c for c in compounds if c["role"] == "control"]
    out = {}
    for tname, flag in (("PKM2", "binds_PKM2"), ("PPARD", "binds_PPARD")):
        binders = [c for c in compounds if c[flag] == 1]
        binder_ids = {c["qs_id"] for c in binders}
        decoys = controls  # controls bind neither target
        rows, labels, scores = [], [], []
        for c in binders + decoys:
            sc = score_matrix.get(c["qs_id"], {}).get(tname)
            label = 1 if c["qs_id"] in binder_ids else 0
            rows.append({"qs_id": c["qs_id"], "name": c["name"], "role": c["role"],
                         "label": label, "score": sc})
            if sc is not None:
                labels.append(label)
                scores.append(sc)
        a = auroc(labels, scores) if len(scores) == len(binders) + len(decoys) else None
        out[tname] = {
            "auroc": a,
            "n_binders": len(binders),
            "n_controls": len(decoys),
            "binder_ids": [c["qs_id"] for c in binders],
            "scores": sorted(rows, key=lambda r: (-(r["score"] if r["score"] is not None else -1e9))),
            "score_units": "higher = stronger predicted binder",
        }
    return out


# ---------------------------------------------------------------------------
# Analysis (B): deconvolution matrix. For each compound, PKM2 vs PPARD score
# and argmax_target. Records the annotated target(s) for comparison.
# ---------------------------------------------------------------------------
def annotated_targets(c):
    t = []
    if c.get("binds_PKM2") == 1:
        t.append("PKM2")
    if c.get("binds_PPARD") == 1:
        t.append("PPARD")
    return t


def analysis_B_matrix(compounds, score_matrix):
    rows = []
    for c in compounds:
        s_pkm2 = score_matrix.get(c["qs_id"], {}).get("PKM2")
        s_ppard = score_matrix.get(c["qs_id"], {}).get("PPARD")
        argmax = None
        if s_pkm2 is not None and s_ppard is not None:
            argmax = "PKM2" if s_pkm2 >= s_ppard else "PPARD"
        ann = annotated_targets(c)
        rows.append({
            "qs_id": c["qs_id"], "name": c["name"], "role": c["role"],
            "annotated_targets": ann,
            "PKM2_score": s_pkm2, "PPARD_score": s_ppard,
            "argmax_target": argmax,
            "argmax_matches_annotation": (argmax in ann) if (argmax and ann) else None,
        })
    return {"rows": rows,
            "note": ("expectations: QS0113172 high for BOTH; QS0069567 PPARD>PKM2; "
                     "Dasa-58 PKM2>PPARD; GSK 3787 PPARD>PKM2; controls low for both")}


# ---------------------------------------------------------------------------
# Analysis (C): deconvolution accuracy on the 4 non-promiscuous hits/refs +
# the promiscuous QS0113172 (correct if BOTH targets score above control median).
# ---------------------------------------------------------------------------
def analysis_C_accuracy(compounds, score_matrix):
    controls = [c for c in compounds if c["role"] == "control"]

    def control_median(tname):
        vals = [score_matrix.get(c["qs_id"], {}).get(tname) for c in controls]
        vals = [v for v in vals if v is not None]
        return float(np.median(vals)) if vals else None

    med = {"PKM2": control_median("PKM2"), "PPARD": control_median("PPARD")}

    # The 4 single-target hits/refs: argmax must equal the single annotated target.
    single = {"QS0069567": "PPARD", "QS0321744": "PKM2", "QS0321760": "PPARD"}
    by_id = {c["qs_id"]: c for c in compounds}
    detail = []
    correct = 0
    n_eval = 0

    for qs_id, ann_t in single.items():
        c = by_id.get(qs_id)
        if c is None:
            continue
        s = score_matrix.get(qs_id, {})
        s_pkm2, s_ppard = s.get("PKM2"), s.get("PPARD")
        argmax = None
        if s_pkm2 is not None and s_ppard is not None:
            argmax = "PKM2" if s_pkm2 >= s_ppard else "PPARD"
        ok = (argmax == ann_t)
        detail.append({"qs_id": qs_id, "name": c["name"], "annotated": ann_t,
                       "PKM2_score": s_pkm2, "PPARD_score": s_ppard,
                       "argmax": argmax, "correct": ok, "criterion": "argmax == annotated"})
        n_eval += 1
        correct += int(ok)

    # The promiscuous hit: correct iff BOTH targets above their control median.
    prom_id = "QS0113172"
    c = by_id.get(prom_id)
    if c is not None:
        s = score_matrix.get(prom_id, {})
        s_pkm2, s_ppard = s.get("PKM2"), s.get("PPARD")
        above_pkm2 = (s_pkm2 is not None and med["PKM2"] is not None and s_pkm2 > med["PKM2"])
        above_ppard = (s_ppard is not None and med["PPARD"] is not None and s_ppard > med["PPARD"])
        ok = bool(above_pkm2 and above_ppard)
        detail.append({"qs_id": prom_id, "name": c["name"], "annotated": "PKM2+PPARD (both)",
                       "PKM2_score": s_pkm2, "PPARD_score": s_ppard,
                       "PKM2_control_median": med["PKM2"], "PPARD_control_median": med["PPARD"],
                       "above_PKM2_control_median": above_pkm2,
                       "above_PPARD_control_median": above_ppard,
                       "correct": ok, "criterion": "both targets > their control median"})
        n_eval += 1
        correct += int(ok)

    return {"n_evaluated": n_eval, "n_correct": correct,
            "accuracy": (correct / n_eval) if n_eval else None,
            "control_medians": med, "detail": detail,
            "note": ("deconvolution recovered if a sequence-only DTI model places each "
                     "hit/ref's annotated target on top; promiscuous hit scored on both-above-median")}


def run_model_block(model_name, scorer, compounds, target_seqs, results):
    """Score one model + run analyses A/B/C, each independently guarded."""
    block = {"model_label": model_name}
    try:
        scored = scorer(compounds, target_seqs)
        block.update(scored)
        smatrix = scored["score_matrix"]
    except Exception as e:
        block["error"] = f"{type(e).__name__}: {e}"
        print(f"[FAIL] {model_name} scoring: {e}\n{traceback.format_exc()[:1500]}", flush=True)
        results[model_name] = block
        return

    for aname, fn in (("A_per_target_auroc", analysis_A_auroc),
                      ("B_deconvolution_matrix", analysis_B_matrix),
                      ("C_deconvolution_accuracy", analysis_C_accuracy)):
        try:
            block[aname] = fn(compounds, smatrix)
        except Exception as e:
            block[aname] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] {model_name}.{aname}: {e}\n{traceback.format_exc()[:800]}", flush=True)

    A = block.get("A_per_target_auroc", {})
    C = block.get("C_deconvolution_accuracy", {})
    print(f"[ok] {model_name}  PKM2_AUROC={ (A.get('PKM2') or {}).get('auroc') } "
          f"PPARD_AUROC={ (A.get('PPARD') or {}).get('auroc') } "
          f"deconv_acc={ C.get('accuracy') }", flush=True)
    results[model_name] = block


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    panel = json.loads(PANEL.read_text())
    targets = panel["targets"]
    compounds = panel["compounds"]

    target_seqs = get_target_sequences(targets)
    for tname, info in target_seqs.items():
        print(f"[seq] {tname} ({info['acc']}): len={info['len']} source={info['source']}", flush=True)

    results = {
        "task": ("Quiver target deconvolution: can a sequence-based DTI model recover the "
                 "TSC2-screen hits' PKM2/PPARD deconvolution?"),
        "provenance": panel.get("provenance"),
        "device": DEVICE,
        "targets": {tname: {"uniprot": info["acc"], "seq_len": info["len"],
                            "seq_source": info["source"],
                            "hugo": targets[tname].get("hugo"),
                            "name": targets[tname].get("name")}
                    for tname, info in target_seqs.items()},
        "n_compounds": len(compounds),
        "compound_roles": {c["qs_id"]: {"name": c["name"], "role": c["role"],
                                        "binds_PKM2": c["binds_PKM2"],
                                        "binds_PPARD": c["binds_PPARD"]}
                           for c in compounds},
        "models": {},
    }

    run_model_block("BALM", score_balm, compounds, target_seqs, results["models"])
    run_model_block("PLAPT", score_plapt, compounds, target_seqs, results["models"])

    # Compact verdict summary across models.
    verdict = {}
    for mname, m in results["models"].items():
        A = m.get("A_per_target_auroc", {})
        C = m.get("C_deconvolution_accuracy", {})
        verdict[mname] = {
            "PKM2_auroc": (A.get("PKM2") or {}).get("auroc") if isinstance(A, dict) else None,
            "PPARD_auroc": (A.get("PPARD") or {}).get("auroc") if isinstance(A, dict) else None,
            "deconvolution_accuracy": C.get("accuracy") if isinstance(C, dict) else None,
            "n_deconv_correct": C.get("n_correct") if isinstance(C, dict) else None,
            "n_deconv_evaluated": C.get("n_evaluated") if isinstance(C, dict) else None,
            "error": m.get("error"),
        }
    results["deconvolution_verdict"] = verdict

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(verdict, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
