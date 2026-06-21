"""Track-2 thoroughness eval: two STRONG, UNTESTED public DTI models on the Quiver
Nav1.8 + mTOR binder/decoy panels.

WHY THESE TWO (both: downloadable pretrained weights, run from protein SEQUENCE + ligand
SMILES with NO 3D structure, output a binding/affinity score):

  1. PLAPT  (Bindwell/PLAPT) — branched transformer regressor on top of frozen ProtBERT
     (Rostlab/prot_bert) + ChemBERTa (seyonec/ChemBERTa-zinc-base-v1) embeddings. The
     affinity head ships in-repo as `models/affinity_predictor.onnx` (~5.9 MB, ONNX).
     API: `from plapt import Plapt; Plapt(...).predict_affinity(prot_seqs, mol_smiles)`
     returns a list of dicts with key `neg_log10_affinity_M` (a pKd-like score; HIGHER =
     STRONGER binder -> correct AUROC directionality). 1:1 pairing, ProtBERT max_length
     3200 (Nav 1956 / mTOR 2549 both fit, no truncation). pip-only deps, GPU via cuda.

  2. DeepPurpose MPNN_CNN_BindingDB_IC50 (kexinhuang12345/DeepPurpose) — MPNN drug encoder
     + CNN protein encoder, weights pulled by `models.model_pretrained(model=...)` from the
     Harvard Dataverse. Inference path: `utils.data_process(X_drug, X_target, y,
     drug_encoding='MPNN', target_encoding='CNN', split_method='no_split')` -> a single df ->
     `net.predict(df)` returns pIC50 (HIGHER = STRONGER -> correct AUROC directionality).

Both are BindingDB-family pretrained. Nav1.8 (SCN10A) has ~0 entries in the BindingDB_Kd
DTI splits these models learned from, so a CHANCE-LEVEL Nav result is itself a finding
(Nav-blind), consistent with the other off-the-shelf models (ConPLex Nav ~0.437). mTOR is
well represented in BindingDB, so a high mTOR AUROC is the expected sanity check.

Baselines already in the panel / known (for the head-to-head table):
  BALM    Nav1.8 0.857 / mTOR 1.000   (current best, real shared cosine space)
  Boltz-2 Nav1.8 0.714 / mTOR 1.000   (needs 3D fold; included for reference)
  ConPLex Nav1.8 ~0.437               (Nav-blind, chance)

Each model section is try/except-guarded so a single failure can't sink the run; partial
results still upload. Writes JSON to env OUT (default /root/dti_out/dti_nav_result.json).
"""
from __future__ import annotations
import json, os, sys, traceback
from pathlib import Path
import numpy as np

OUT = Path(os.environ.get("OUT", "/root/dti_out/dti_nav_result.json"))
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
PLAPT_DIR = Path(os.environ.get("PLAPT_DIR", "/opt/PLAPT"))
DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"

# Known baselines for the head-to-head table (per-target binder-vs-decoy AUROC).
BASELINES = {
    "BALM":    {"nav18": 0.857, "mtor": 1.000, "note": "real compound<->target shared cosine space (current Track-2 best on Nav)"},
    "Boltz-2": {"nav18": 0.714, "mtor": 1.000, "note": "co-fold scoring; needs 3D structure (reference only)"},
    "ConPLex": {"nav18": 0.437, "mtor": None,  "note": "Nav-blind / chance"},
}


def auroc(labels, scores):
    """Mann-Whitney / rank-sum AUROC. Higher score should mean 'binder' (label 1).
    Ties get the average rank (0.5 credit). Returns None if only one class present."""
    labels = np.asarray(labels, dtype=float)
    scores = np.asarray(scores, dtype=float)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    # rank-based to handle ties cleanly
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


def load_panels():
    with open(PANELS) as f:
        return json.load(f)


def summarize_target(compounds, score_by_drug):
    """Build per-compound rows + binder-vs-decoy AUROC for one target."""
    rows, labels, scores = [], [], []
    for c in compounds:
        drug = c["drug"]
        sc = score_by_drug.get(drug)
        rows.append({"drug": drug, "label": c["label"],
                     "score": (None if sc is None else float(sc))})
        if sc is not None:
            labels.append(c["label"])
            scores.append(float(sc))
    a = auroc(labels, scores) if len(scores) == len(compounds) else None
    n_pos = sum(1 for c in compounds if c["label"] == 1)
    n_neg = sum(1 for c in compounds if c["label"] == 0)
    return {"auroc": a, "n_scored": len(scores), "n_binders": n_pos,
            "n_decoys": n_neg, "scores": rows,
            "score_units": "higher = stronger predicted binder"}


# ---------------------------------------------------------------------------
# Model 1: PLAPT (ProtBERT + ChemBERTa -> ONNX affinity head)
# ---------------------------------------------------------------------------
def run_plapt(panels):
    sys.path.insert(0, str(PLAPT_DIR))
    os.chdir(PLAPT_DIR)  # affinity_predictor.onnx is referenced relative to repo root ("models/...")
    from plapt import Plapt  # noqa: E402

    plapt = Plapt(device=DEVICE, use_tqdm=False)
    out = {"model": "PLAPT",
           "source": "github.com/Bindwell/PLAPT (models/affinity_predictor.onnx, ProtBERT+ChemBERTa)",
           "score_key": "neg_log10_affinity_M (pKd-like; higher = stronger binder)",
           "targets": {}}
    for key in ("nav18", "mtor"):
        panel = panels[key]
        seq = panel["protein_seq"]
        smiles = [c["smiles"] for c in panel["compounds"]]
        prots = [seq] * len(smiles)  # predict_affinity enforces strict 1:1 pairing
        preds = plapt.predict_affinity(prots, smiles)
        score_by_drug = {}
        for c, p in zip(panel["compounds"], preds):
            # p is a dict; neg_log10_affinity_M is the affinity (higher = stronger).
            score_by_drug[c["drug"]] = float(p["neg_log10_affinity_M"])
        out["targets"][key] = summarize_target(panel["compounds"], score_by_drug)
    return out


# ---------------------------------------------------------------------------
# Model 2: DeepPurpose MPNN_CNN_BindingDB_IC50 (pretrained, Harvard Dataverse)
# ---------------------------------------------------------------------------
def run_deeppurpose(panels):
    # Quiet TF imports just in case (DeepPurpose pulls in lots of transitive deps).
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    from DeepPurpose import DTI as models  # noqa: E402
    from DeepPurpose import utils  # noqa: E402

    model_name = os.environ.get("DP_MODEL", "MPNN_CNN_BindingDB_IC50")
    drug_encoding, target_encoding = "MPNN", "CNN"
    net = models.model_pretrained(model=model_name)

    out = {"model": f"DeepPurpose:{model_name}",
           "source": "github.com/kexinhuang12345/DeepPurpose (Harvard Dataverse pretrained)",
           "drug_encoding": drug_encoding, "target_encoding": target_encoding,
           "score_key": "predicted pIC50 (higher = stronger binder)",
           "targets": {}}
    for key in ("nav18", "mtor"):
        panel = panels[key]
        seq = panel["protein_seq"]
        comps = panel["compounds"]
        X_drug = [c["smiles"] for c in comps]
        X_target = [seq] * len(comps)
        y_dummy = [0.0] * len(comps)  # placeholder labels; predict() ignores y
        df = utils.data_process(
            X_drug=X_drug, X_target=X_target, y=y_dummy,
            drug_encoding=drug_encoding, target_encoding=target_encoding,
            split_method="no_split", mode="DTI",
        )
        y_pred = net.predict(df)
        y_pred = [float(v) for v in np.asarray(y_pred).ravel()]
        # data_process(no_split) preserves row order, so y_pred aligns to comps order.
        score_by_drug = {c["drug"]: y_pred[i] for i, c in enumerate(comps)}
        out["targets"][key] = summarize_target(comps, score_by_drug)
    return out


def section(name, fn, results, panels):
    try:
        results[name] = fn(panels)
        ts = results[name].get("targets", {})
        msg = "  ".join(f"{k}={ (ts.get(k) or {}).get('auroc') }" for k in ("nav18", "mtor"))
        print(f"[ok] {name}  {msg}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1500]}", flush=True)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    panels = load_panels()

    results = {
        "task": "Track-2 binder triage: untested public DTI models on Quiver Nav1.8 + mTOR panels",
        "device": DEVICE,
        "panel_counts": {k: {"binders": sum(1 for c in panels[k]["compounds"] if c["label"] == 1),
                             "decoys": sum(1 for c in panels[k]["compounds"] if c["label"] == 0)}
                         for k in ("nav18", "mtor")},
        "baselines": BASELINES,
        "expectation": ("BindingDB-pretrained DTI models are typically Nav-BLIND (Nav1.8/SCN10A "
                        "has ~0 training pairs in BindingDB_Kd), so a chance-level Nav AUROC is "
                        "itself a finding; mTOR is well represented and should score high."),
        "models": {},
    }

    section("plapt", run_plapt, results["models"], panels)
    section("deeppurpose", run_deeppurpose, results["models"], panels)

    # Compact head-to-head table (new models + known baselines), per target.
    table = {"nav18": {}, "mtor": {}}
    for mname, m in results["models"].items():
        if "targets" in m:
            for k in ("nav18", "mtor"):
                table[k][m.get("model", mname)] = (m["targets"].get(k) or {}).get("auroc")
    for bname, b in BASELINES.items():
        for k in ("nav18", "mtor"):
            table[k].setdefault(bname, b.get(k))
    results["head_to_head_auroc"] = table

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results["head_to_head_auroc"], indent=2), flush=True)


if __name__ == "__main__":
    main()
