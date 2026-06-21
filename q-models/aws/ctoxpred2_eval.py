"""CToxPred2 (JCIM 2024) — Track-5 cardiac/ion-channel toxicity evaluation.

WHY
===
Our Track-5 hERG winner is MapLight / Morgan-FP+XGBoost (AUROC ~0.889, far-OOD-Tanimoto<0.3
0.809, Brier ~0.137). CToxPred2 (github.com/issararab/CToxPred2) is the only verified-
downloadable model EXPLICITLY TRAINED on ion-channel blockade: a multitask classifier with
SEPARATE pretrained heads for hERG / Nav1.5 / Cav1.2 cardiac-channel block (ligand-only,
SMILES -> per-channel block probability). Two questions:
  (a) PRIMARY: does its hERG head match/beat MapLight on the SAME TDC hERG_Karim test
      (Murcko scaffold split + applicability-domain Tanimoto stratification + Brier)?
  (b) BONUS: do its Nav1.5/Cav1.2 heads give a usable cardiac multi-channel signal on a
      small ChEMBL blocker-vs-decoy panel (SCN5A=CHEMBL1980, CACNA1C=CHEMBL1940)?

CAVEAT to carry into the writeup: these are CARDIAC channels, ligand-only, NOT CNS-channel
target-conditioned DTI. CToxPred2's hERG/Nav1.5/Cav1.2 answer "is this molecule a cardiac
liability?", not "does this molecule bind Quiver's CNS Nav1.x target?". It complements our
single hERG gate; it does not replace the CNS DTI lane (BALM/Boltz-2).

THE REPO'S OWN INFERENCE CONTRACT (replicated VERBATIM here — do not invent featurization)
=========================================================================================
notebooks/nutils.py -> process_smiles(smiles, GLB_Model) is the canonical entry point. It
returns only argmax 0/1 + max-prob confidence string, which is useless for AUROC, so we call
the repo's lower-level pieces directly to recover a continuous P(block=positive class):

  Featurization (CToxPred2/utils.py):
    compute_fingerprint_features(smiles_list) -> np.int32 [n, 1905]  (PyBioMed ECFP2 1024
        + PubChem 881; raises on a None mol, so we featurize per-molecule and drop failures).
    compute_descriptor_features(smiles_list)  -> pandas DataFrame  (Mordred 2D, ignore_3D).

  Two prediction backends ship with the repo (we try SSL-RF first, then SL-DL, record which):
    SSL (random-forest, semi-supervised) — _generate_predictions_ssl:
        features = concat(fingerprints[1905], global_pipeline.transform(descriptors))  for ALL channels
        models/random_forest/{hERG,Nav1.5,Cav1.2}/_ssl_*_model.joblib  ->  predict_proba(X)[:,1]
        Deterministic, native probability. PREFERRED for AUROC.
    SL (deep, MC-dropout) — _generate_predictions_sl:
        hERG head: fingerprints ONLY (1905).
        Nav1.5 head: concat(fingerprints, nav_pipeline.transform(descriptors)) -> 2453.
        Cav1.2 head: concat(fingerprints, cav_pipeline.transform(descriptors)) -> 2586.
        {hERGClassifier(1905,2), Nav15Classifier(2453,2), Cav12Classifier(2586,2)} load
        models/model_weights/{hERG,Nav1.5,Cav1.2}/_*_checkpoint.model; .train() + 100 forward
        passes (MC-dropout), mean over passes; we read column [:,1] = P(toxic/blocker).

Weights ship in the repo as .rar archives (model_weights.rar, decriptors_preprocessing.rar,
random_forest.rar) under CToxPred2/models/ and are decompressed by the userdata (unar/unrar).

OUTPUT
======
JSON to env OUT: per-channel AUROCs, the hERG head-to-head vs MapLight 0.889 / FP-XGBoost 0.890
(random + scaffold + far-OOD bands + Brier on the SAME hERG_Karim test), the Nav1.5/Cav1.2
ChEMBL blocker-vs-decoy AUROCs (or insufficient-data marks), the backend used, and any
featurization failures (note explicitly if PyBioMed/Mordred reject SMILES — the CardioGenAI
closed-vocab failure mode). Every block is independently try/except-guarded and the JSON is
rewritten after each, so partial failures still bank everything that finished.

Config (env vars):
  OUT            output JSON (default /root/ctox_out/ctoxpred2_result.json)
  CTOX_DIR       repo root (default /opt/CToxPred2)
  BACKEND        "rf-ssl" (default) | "dl-sl" | "auto" (try rf-ssl, fall back to dl-sl)
  MC_ITERS       MC-dropout forward passes for the dl-sl backend (default 100, repo value)
  MAX_HERG       cap rows/class on the hERG_Karim test featurization (default 4000)
  ACTIVE_PCHEMBL / INACTIVE_PCHEMBL / MIN_ACTIVES / MAX_ACTIVES / DECOY_RATIO / MIN_DECOYS
                 ChEMBL panel knobs for the Nav1.5/Cav1.2 bonus (defaults mirror
                 aws/cns_dti_benchmark_eval.py).
"""
from __future__ import annotations

import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUT", "/root/ctox_out/ctoxpred2_result.json"))
CTOX_DIR = Path(os.environ.get("CTOX_DIR", "/opt/CToxPred2"))
BACKEND = os.environ.get("BACKEND", "rf-ssl")          # rf-ssl | dl-sl | auto
MC_ITERS = int(os.environ.get("MC_ITERS", "100"))      # repo's GLB_FORWARD_ITERATIONS
MAX_HERG = int(os.environ.get("MAX_HERG", "4000"))

# ChEMBL panel knobs (Nav1.5 / Cav1.2 bonus) — mirror aws/cns_dti_benchmark_eval.py.
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "20"))
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "120"))
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))
SEED = int(os.environ.get("SEED", "20260615"))
RNG = np.random.default_rng(SEED)

# The cardiac channels CToxPred2 exposes; ChEMBL ids for the bonus blocker-vs-decoy panel.
CARDIAC_TARGETS = {
    "Nav1.5": {"gene": "SCN5A", "uniprot": "Q14524", "chembl": "CHEMBL1980"},
    "Cav1.2": {"gene": "CACNA1C", "uniprot": "Q13936", "chembl": "CHEMBL1940"},
}
BINDING_TYPES = ["IC50", "Ki", "Kd"]

# Track-5 reference points (the bar CToxPred2's hERG head must clear).
MAPLIGHT_HERG_AUROC = 0.889
MAPLIGHT_HERG_FAR_OOD_AUROC = 0.809
MAPLIGHT_HERG_BRIER = 0.137
FP_XGB_HERG_AUROC = 0.890


# ===========================================================================
# Metrics (rank-sum AUROC with average ties; Brier; quantile reliability table)
# — shape copied from aws/derisking_characterization.py so CToxPred2 is judged
# on the SAME metric definitions as MapLight / FP-XGBoost.
# ===========================================================================
def auroc(y, s):
    y = np.asarray(y)
    s = np.asarray(s, float)
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    if p == 0 or n == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), float)
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return float((ranks[y == 1].sum() - p * (p + 1) / 2.0) / (p * n))


def calibration(y, p, bins=5):
    y = np.asarray(y)
    p = np.asarray(p, float)
    brier = float(np.mean((p - y) ** 2))
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    rel = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        m = (p >= lo) & (p <= hi) if i == len(edges) - 2 else (p >= lo) & (p < hi)
        if m.sum() > 0:
            rel.append({"bin": i, "pred_mean": round(float(p[m].mean()), 3),
                        "obs_rate": round(float(y[m].mean()), 3), "n": int(m.sum())})
    return {"brier": round(brier, 4), "n_bins": len(rel), "reliability": rel}


# ===========================================================================
# RDKit helpers (applicability domain / scaffolds) — same recipe as
# aws/derisking_characterization.py so the AD bands line up with MapLight's.
# ===========================================================================
def morgan(smis):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    fps = []
    for s in smis:
        m = Chem.MolFromSmiles(s)
        fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None)
    return fps


def max_tanimoto(test_fps, train_fps):
    from rdkit import DataStructs
    tr = [f for f in train_fps if f is not None]
    out = []
    for f in test_fps:
        if f is None or not tr:
            out.append(0.0)
            continue
        sims = DataStructs.BulkTanimotoSimilarity(f, tr)
        out.append(max(sims) if sims else 0.0)
    return np.array(out)


def applicability_domain(yte, p, te_fp, tr_fp):
    """AUROC + accuracy per Tanimoto-to-train band; the far/OOD band (<0.3) is the
    head-to-head number vs MapLight's far-OOD 0.809."""
    mt = max_tanimoto(te_fp, tr_fp)
    pred = (np.asarray(p) >= 0.5).astype(int)
    yte = np.asarray(yte)
    bands = []
    far_ood_auroc = None
    for lo, hi, lab in [(0.0, 0.3, "far/OOD"), (0.3, 0.5, "mid"), (0.5, 1.01, "near")]:
        m = (mt >= lo) & (mt < hi)
        if m.sum() >= 10:
            acc = float((pred[m] == yte[m]).mean())
            au = auroc(yte[m], np.asarray(p)[m]) if len(set(yte[m])) == 2 else float("nan")
            bands.append({"band": lab, "tanimoto": f"{lo}-{hi}", "n": int(m.sum()),
                          "auroc": None if au != au else round(au, 3), "accuracy": round(acc, 3)})
            if lab == "far/OOD" and au == au:
                far_ood_auroc = round(au, 4)
    return {"mean_tanimoto_to_train": round(float(mt.mean()), 3),
            "frac_OOD_<0.3": round(float((mt < 0.3).mean()), 3),
            "far_ood_auroc": far_ood_auroc, "bands": bands}


# ===========================================================================
# CToxPred2 backend — imports the repo's OWN classes + featurizers, replicates
# its two prediction paths but reads the POSITIVE-class probability (for AUROC)
# instead of the repo's argmax/max-confidence packaging.
# ===========================================================================
class CToxPred2:
    """Wraps the repo's featurization + per-channel heads. Returns, per channel, a
    continuous P(positive class = blocker/toxic) so we can compute AUROC. Featurizes
    per-molecule and reports SMILES that PyBioMed/Mordred reject (the closed-vocab
    failure mode CardioGenAI hit)."""

    def __init__(self):
        # The repo lays its python out as CToxPred2/CToxPred2/*.py + notebooks/*.py and
        # references models via relative "../CToxPred2/models/..." from notebooks/. We add
        # both source dirs to sys.path and resolve weight paths absolutely off CTOX_DIR.
        self.src = CTOX_DIR / "CToxPred2"
        self.nb = CTOX_DIR / "notebooks"
        for d in (str(self.src), str(self.nb)):
            if d not in sys.path:
                sys.path.insert(0, d)
        # Featurizers + correlation-threshold transformer the pickled pipelines need in scope.
        from utils import compute_fingerprint_features, compute_descriptor_features  # noqa
        # UNPICKLE FIX: the SSL random-forest pipelines + the descriptor-preprocessing
        # pipelines (global / Nav1.5 / Cav1.2) were pickled from a notebook/script whose
        # __main__ namespace held a `from pairwise_correlation import CorrelationThreshold`
        # (see notebooks/make_predictions.ipynb + notebooks/nutils.py). pickle therefore
        # recorded the custom selector's path as `__main__.CorrelationThreshold`, so joblib.load
        # raises `AttributeError: Can't get attribute 'CorrelationThreshold' on <module
        # '__main__'>` unless the REAL fitted class is reachable at __main__.CorrelationThreshold
        # *before* any joblib.load. The class (CToxPred2/CToxPred2/pairwise_correlation.py) is a
        # SelectorMixin/BaseEstimator whose transform() applies the pickled `self.mask` via
        # _get_support_mask(), so importing the real class restores fitted state correctly.
        # Register it into __main__ (the namespace pickle looks in) and keep the module import
        # so `pairwise_correlation.CorrelationThreshold` resolves too.
        import __main__
        from pairwise_correlation import CorrelationThreshold  # the repo's real fitted selector
        __main__.CorrelationThreshold = CorrelationThreshold
        self._fp = compute_fingerprint_features
        self._desc = compute_descriptor_features
        self.models_root = self.src / "models"

    # ---- featurization (per-molecule guarded) ----
    def featurize(self, smiles_list):
        """Return (fingerprints[n,1905], descriptors_df[n], kept_idx, failures).
        A SMILES is a failure if RDKit can't parse it or PyBioMed/Mordred raise."""
        from rdkit import Chem
        kept, failures = [], []
        for i, smi in enumerate(smiles_list):
            m = Chem.MolFromSmiles(smi) if smi else None
            if m is None:
                failures.append({"idx": i, "smiles": smi, "reason": "rdkit_parse_failed"})
                continue
            try:
                fp = self._fp([smi])  # raises on bad mol; per-molecule isolates the failure
                if fp is None or np.asarray(fp).shape[-1] != 1905:
                    failures.append({"idx": i, "smiles": smi,
                                     "reason": f"fp_shape={None if fp is None else np.asarray(fp).shape}"})
                    continue
            except Exception as e:
                failures.append({"idx": i, "smiles": smi,
                                 "reason": f"fingerprint:{type(e).__name__}:{str(e)[:80]}"})
                continue
            kept.append(i)
        kept_smiles = [smiles_list[i] for i in kept]
        if not kept_smiles:
            return np.zeros((0, 1905), np.float32), None, kept, failures
        fps = self._fp(kept_smiles).astype(np.float32)
        descs = None
        try:
            descs = self._desc(kept_smiles)
        except Exception as e:
            failures.append({"idx": -1, "smiles": None,
                             "reason": f"descriptor_batch:{type(e).__name__}:{str(e)[:120]}"})
        return fps, descs, kept, failures

    @staticmethod
    def _coerce_descriptors(descs):
        """Mordred returns objects/NaN for compounds it can't compute; coerce to float and
        zero-fill so the (pickled) preprocessing pipeline gets a clean numeric matrix."""
        import pandas as pd
        df = pd.DataFrame(descs).apply(pd.to_numeric, errors="coerce")
        return df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # ---- SSL random-forest backend (preferred: deterministic predict_proba) ----
    def _proba_rf_ssl(self, fps, descs):
        import joblib
        pre = joblib.load(self.models_root / "decriptors_preprocessing" /
                          "global_preprocessing_pipeline.sav")
        d = pre.transform(self._coerce_descriptors(descs))
        X = np.concatenate((fps, np.asarray(d, dtype=np.float32)), axis=1)
        out = {}
        rf_paths = {
            "hERG": self.models_root / "random_forest" / "hERG" / "_ssl_herg_model.joblib",
            "Nav1.5": self.models_root / "random_forest" / "Nav1.5" / "_ssl_nav_model.joblib",
            "Cav1.2": self.models_root / "random_forest" / "Cav1.2" / "_ssl_cav_model.joblib",
        }
        for ch, pth in rf_paths.items():
            mdl = joblib.load(pth)
            out[ch] = np.asarray(mdl.predict_proba(X))[:, 1].astype(np.float64)
        return out

    # ---- SL deep MC-dropout backend (P(toxic) = mean softmax col 1 over MC passes) ----
    def _proba_dl_sl(self, fps, descs):
        import torch
        from hERG_model import hERGClassifier
        from nav15_model import Nav15Classifier
        from cav12_model import Cav12Classifier
        import joblib
        dev = torch.device("cpu")

        def mc_proba(model, X):
            X = torch.from_numpy(np.asarray(X, dtype=np.float32)).to(dev)
            model.train()  # repo keeps dropout ON for MC-dropout uncertainty
            acc = torch.zeros(X.shape[0], 2)
            with torch.no_grad():
                for _ in range(MC_ITERS):
                    acc += model(X).cpu()
            mean = acc / MC_ITERS
            return mean[:, 1].numpy().astype(np.float64)  # P(positive class)

        out = {}
        # hERG: fingerprints ONLY (1905).
        herg = hERGClassifier(1905, 2, 0.2)
        herg.load(str(self.models_root / "model_weights" / "hERG" / "_herg_checkpoint.model"))
        out["hERG"] = mc_proba(herg, fps)
        # Nav1.5 / Cav1.2: fingerprints + channel-specific descriptor pipeline.
        dcoerced = self._coerce_descriptors(descs)
        for ch, cls, dim, pipe, ckpt in [
            ("Nav1.5", Nav15Classifier, 2453,
             self.models_root / "decriptors_preprocessing" / "Nav1.5" / "nav_descriptors_preprocessing_pipeline.sav",
             self.models_root / "model_weights" / "Nav1.5" / "_nav15_checkpoint.model"),
            ("Cav1.2", Cav12Classifier, 2586,
             self.models_root / "decriptors_preprocessing" / "Cav1.2" / "cav_descriptors_preprocessing_pipeline.sav",
             self.models_root / "model_weights" / "Cav1.2" / "_cav12_checkpoint.model"),
        ]:
            d = joblib.load(pipe).transform(dcoerced)
            X = np.concatenate((fps, np.asarray(d, dtype=np.float32)), axis=1)
            mdl = cls(dim, 2, 0.2)
            mdl.load(str(ckpt))
            out[ch] = mc_proba(mdl, X)
        return out

    def predict_proba(self, smiles_list, backend):
        """Return {channel: {p[], kept_idx[], failures[], backend}}.
        backend: 'rf-ssl' | 'dl-sl' | 'auto' (rf-ssl then dl-sl)."""
        fps, descs, kept, failures = self.featurize(smiles_list)
        meta = {"n_in": len(smiles_list), "n_kept": len(kept),
                "kept_idx": kept, "failures": failures[:50],
                "n_failures": len(failures)}
        if len(kept) == 0:
            meta["error"] = "all SMILES failed featurization"
            return meta, None, "none"
        order = [("rf-ssl", self._proba_rf_ssl), ("dl-sl", self._proba_dl_sl)]
        if backend == "rf-ssl":
            order = [order[0]]
        elif backend == "dl-sl":
            order = [order[1]]
        last_err = None
        for name, fn in order:
            try:
                probs = fn(fps, descs)
                return meta, probs, name
            except Exception as e:
                last_err = f"{name}:{type(e).__name__}:{str(e)[:160]}"
                print(f"[backend {name} failed] {last_err}\n{traceback.format_exc()[:500]}", flush=True)
        meta["error"] = f"all backends failed: {last_err}"
        return meta, None, "none"


# ===========================================================================
# (a) PRIMARY — hERG head on TDC hERG_Karim, SAME protocol as MapLight/FP-XGBoost.
# ===========================================================================
def load_herg_karim(max_per_class):
    """Random + scaffold splits from TDC hERG_Karim (binary). The model is pretrained, so we
    score its hERG head directly on each split's TEST set (no training); the TRAIN set is used
    only to build the applicability-domain Tanimoto reference (same as the MapLight eval)."""
    from tdc.single_pred import Tox

    def to_rows(split):
        rows = []
        for _, r in split.iterrows():
            smi, y = r.get("Drug"), r.get("Y")
            if smi is None or y is None:
                continue
            rows.append({"smiles": str(smi), "y": int(round(float(y)))})
        pos = [x for x in rows if x["y"] == 1][:max_per_class]
        neg = [x for x in rows if x["y"] == 0][:max_per_class]
        return pos + neg

    data = Tox(name="hERG_Karim")
    rnd = data.get_split(method="random", seed=42)
    out = {"random": {"train": to_rows(rnd["train"]), "test": to_rows(rnd["test"])}}
    try:
        sc = data.get_split(method="scaffold", seed=42)
        out["scaffold"] = {"train": to_rows(sc["train"]), "test": to_rows(sc["test"])}
    except Exception as e:
        out["scaffold"] = {"error": f"{type(e).__name__}: {e}"}
    return out


def score_split_herg(model, split, backend):
    """Run CToxPred2's hERG head on one split's test set; AUROC + AD bands + Brier."""
    tr, te = split["train"], split["test"]
    te_s = [r["smiles"] for r in te]
    yte = np.array([r["y"] for r in te])
    meta, probs, used = model.predict_proba(te_s, backend)
    if probs is None or "hERG" not in probs:
        return {"error": meta.get("error", "no hERG probs"), "featurization": meta}
    kept = meta["kept_idx"]
    yk = yte[kept]
    p = np.asarray(probs["hERG"], float)
    res = {
        "backend_used": used, "n_test_in": len(te_s), "n_test_scored": len(kept),
        "test_pos": int(yk.sum()), "n_featurization_failures": meta["n_failures"],
        "auroc": None, "calibration": None, "applicability_domain": None,
    }
    au = auroc(yk, p)
    res["auroc"] = round(au, 4) if au == au else None
    if len(set(yk)) == 2:
        res["calibration"] = calibration(yk, p)
        tr_fp = morgan([r["smiles"] for r in tr])
        te_fp_kept = morgan([te_s[i] for i in kept])
        res["applicability_domain"] = applicability_domain(yk, p, te_fp_kept, tr_fp)
    if meta["failures"]:
        res["sample_failures"] = meta["failures"][:10]
    return res


def run_herg_primary(model, herg_data, backend):
    out = {"reference": {"maplight_auroc": MAPLIGHT_HERG_AUROC,
                         "maplight_far_ood_auroc": MAPLIGHT_HERG_FAR_OOD_AUROC,
                         "maplight_brier": MAPLIGHT_HERG_BRIER,
                         "fp_xgboost_auroc": FP_XGB_HERG_AUROC}}
    for split_name in ("random", "scaffold"):
        split = herg_data.get(split_name)
        if not isinstance(split, dict) or "train" not in split:
            out[split_name] = {"skip": f"{split_name} split unavailable: {split}"}
            continue
        try:
            out[split_name] = score_split_herg(model, split, backend)
            r = out[split_name]
            ad = r.get("applicability_domain") or {}
            print(f"[hERG/{split_name}] AUROC={r.get('auroc')} far-OOD={ad.get('far_ood_auroc')} "
                  f"brier={(r.get('calibration') or {}).get('brier')} backend={r.get('backend_used')}",
                  flush=True)
        except Exception as e:
            out[split_name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL hERG/{split_name}] {e}\n{traceback.format_exc()[:500]}", flush=True)

    # Head-to-head verdict on the honest (scaffold) split where available, else random.
    basis = "scaffold" if isinstance(out.get("scaffold"), dict) and out["scaffold"].get("auroc") else "random"
    au = (out.get(basis) or {}).get("auroc")
    ad = (out.get(basis) or {}).get("applicability_domain") or {}
    far = ad.get("far_ood_auroc")
    h2h = {"basis_split": basis, "ctoxpred2_herg_auroc": au,
           "ctoxpred2_herg_far_ood_auroc": far}
    if au is not None:
        h2h["delta_vs_maplight"] = round(au - MAPLIGHT_HERG_AUROC, 4)
        h2h["verdict"] = ("CToxPred2 hERG head beats MapLight"
                          if au > MAPLIGHT_HERG_AUROC else
                          "MapLight/FP-XGBoost hERG gate holds vs CToxPred2")
    if far is not None:
        h2h["delta_far_ood_vs_maplight"] = round(far - MAPLIGHT_HERG_FAR_OOD_AUROC, 4)
    out["head_to_head"] = h2h
    return out


# ===========================================================================
# (b) BONUS — Nav1.5 / Cav1.2 heads on small ChEMBL blocker-vs-decoy panels.
# ChEMBL puller reused from aws/cns_dti_benchmark_eval.py.
# ===========================================================================
def resolve_chembl_id(meta):
    from chembl_webresource_client.new_client import new_client
    acc = meta["uniprot"]
    try:
        hits = list(new_client.target.filter(
            target_components__accession=acc, target_type="SINGLE PROTEIN",
            organism="Homo sapiens").only(["target_chembl_id"]))
        for h in hits:
            if h.get("target_chembl_id"):
                return h["target_chembl_id"], "resolved_by_uniprot_accession"
    except Exception as e:
        print(f"[warn] resolve {acc}: {e}", flush=True)
    if meta.get("chembl"):
        return meta["chembl"], "hardcoded_fallback"
    return None, None


def fetch_activities(chembl_id):
    from chembl_webresource_client.new_client import new_client
    qs = new_client.activity.filter(
        target_chembl_id=chembl_id, standard_type__in=BINDING_TYPES,
        pchembl_value__isnull=False).only(["canonical_smiles", "pchembl_value"])
    best = {}
    for a in qs:
        smi, pv = a.get("canonical_smiles"), a.get("pchembl_value")
        if not smi or pv is None:
            continue
        try:
            pv = float(pv)
        except (TypeError, ValueError):
            continue
        if smi not in best or pv > best[smi]:
            best[smi] = pv
    return best


def mol_props(smi):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return {"mw": Descriptors.MolWt(m), "logp": Descriptors.MolLogP(m),
            "hbd": Lipinski.NumHDonors(m), "hba": Lipinski.NumHAcceptors(m)}


def morgan_fp(smi):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smi)
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None


def property_matched_decoys(active_smiles, active_props, pool, n_needed):
    from rdkit import DataStructs
    if not active_props:
        return []
    arr = lambda k: np.array([p[k] for p in active_props])
    env = {"mw": (arr("mw").mean(), max(arr("mw").std(), 50.0) * 1.5),
           "logp": (arr("logp").mean(), max(arr("logp").std(), 1.0) * 1.5),
           "hbd": (arr("hbd").mean(), max(arr("hbd").std(), 1.0) * 2.0),
           "hba": (arr("hba").mean(), max(arr("hba").std(), 1.0) * 2.0)}
    active_fps = [fp for fp in (morgan_fp(s) for s in active_smiles) if fp is not None]
    picked, pool = [], list(pool)
    RNG.shuffle(pool)
    for smi in pool:
        if smi in active_smiles:
            continue
        p = mol_props(smi)
        if p is None:
            continue
        if any(abs(p[k] - env[k][0]) > env[k][1] for k in env):
            continue
        fp = morgan_fp(smi)
        if fp is None:
            continue
        if active_fps and max(DataStructs.BulkTanimotoSimilarity(fp, active_fps)) >= 0.35:
            continue
        picked.append(smi)
        if len(picked) >= n_needed:
            break
    return picked


def build_cardiac_panel():
    """Per cardiac channel: actives (pchembl>=ACTIVE) vs decoys (same-target inactives, else
    property-matched cross-target). Returns built panels + dropped log + the cross-target pool."""
    raw_actives, raw_inactives, built, dropped = {}, {}, {}, {}
    for ch, meta in CARDIAC_TARGETS.items():
        try:
            cid, src = resolve_chembl_id(meta)
            if not cid:
                dropped[ch] = "no ChEMBL id"
                continue
            best = fetch_activities(cid)
            actives = {s: v for s, v in best.items() if v >= ACTIVE_PCHEMBL}
            inactives = {s: v for s, v in best.items() if v <= INACTIVE_PCHEMBL}
            if len(actives) > MAX_ACTIVES:
                actives = dict(sorted(actives.items(), key=lambda kv: -kv[1])[:MAX_ACTIVES])
            raw_actives[ch], raw_inactives[ch] = actives, inactives
            built[ch] = {"chembl_id": cid, "chembl_id_source": src,
                         "n_actives_pre_drop": len(actives), "n_chembl_inactives": len(inactives)}
            print(f"[chembl] {ch} ({cid},{src}): {len(actives)} actives / {len(inactives)} inactives", flush=True)
        except Exception as e:
            dropped[ch] = f"fetch error: {type(e).__name__}: {e}"
            print(f"[warn] {ch} fetch failed: {e}", flush=True)
    for ch in list(built.keys()):
        if built[ch]["n_actives_pre_drop"] < MIN_ACTIVES:
            dropped[ch] = f"sparse: {built[ch]['n_actives_pre_drop']} actives < {MIN_ACTIVES}"
            built.pop(ch)
            raw_actives.pop(ch, None)
    global_pool = [s for acts in raw_actives.values() for s in acts]
    for ch in list(built.keys()):
        try:
            actives = raw_actives[ch]
            n_cap = int(round(len(actives) * DECOY_RATIO))
            inactives = raw_inactives.get(ch, {})
            if len(inactives) >= MIN_DECOYS:
                decoys = [s for s, _ in sorted(inactives.items(), key=lambda kv: kv[1])[:n_cap]]
                dsrc = "chembl_inactives_same_target"
            else:
                cand = [s for c2, acts in raw_actives.items() if c2 != ch for s in acts] or list(global_pool)
                aprops = [p for p in (mol_props(s) for s in actives) if p is not None]
                decoys = property_matched_decoys(set(actives), aprops, cand, n_cap)
                dsrc = "property_matched_cross_target_decoys"
                for s in inactives:
                    if len(decoys) >= n_cap:
                        break
                    if s not in decoys:
                        decoys.append(s)
            if len(decoys) < MIN_DECOYS:
                dropped[ch] = f"no usable decoys ({len(decoys)} < {MIN_DECOYS}; src={dsrc})"
                built.pop(ch)
                continue
            built[ch].update({"actives": list(actives), "decoys": decoys,
                              "decoy_source": dsrc, "n_actives": len(actives), "n_decoys": len(decoys)})
            print(f"[panel] {ch}: {len(actives)} actives / {len(decoys)} decoys ({dsrc})", flush=True)
        except Exception as e:
            dropped[ch] = f"decoy build error: {type(e).__name__}: {e}"
            built.pop(ch, None)
    return built, dropped


def run_cardiac_bonus(model, backend):
    out = {"note": ("CARDIAC ion-channel blocker-vs-decoy, ligand-only (NOT CNS-channel "
                    "target-conditioned DTI). Tests whether CToxPred2's Nav1.5/Cav1.2 heads add a "
                    "usable multi-channel cardiac-liability signal beyond our single hERG gate.")}
    try:
        panels, dropped = build_cardiac_panel()
    except Exception as e:
        out["error"] = f"panel build failed: {type(e).__name__}: {e}"
        print(f"[FAIL cardiac panel] {e}\n{traceback.format_exc()[:500]}", flush=True)
        return out
    out["dropped"] = dropped
    out["channels"] = {}
    for ch, p in panels.items():
        try:
            smiles = list(p["actives"]) + list(p["decoys"])
            labels = np.array([1] * len(p["actives"]) + [0] * len(p["decoys"]))
            meta, probs, used = model.predict_proba(smiles, backend)
            if probs is None or ch not in probs:
                out["channels"][ch] = {"error": meta.get("error", f"no {ch} probs"),
                                       "featurization": {"n_kept": meta.get("n_kept"),
                                                         "n_failures": meta.get("n_failures")}}
                continue
            kept = meta["kept_idx"]
            yk = labels[kept]
            sc = np.asarray(probs[ch], float)
            au = auroc(yk, sc)
            entry = {"backend_used": used, "chembl_id": p["chembl_id"],
                     "decoy_source": p["decoy_source"],
                     "n_actives_scored": int((yk == 1).sum()), "n_decoys_scored": int((yk == 0).sum()),
                     "n_featurization_failures": meta["n_failures"],
                     "auroc": round(au, 4) if au == au else None}
            if au != au or (yk == 1).sum() < 10 or (yk == 0).sum() < 10:
                entry["insufficient_data"] = True
            out["channels"][ch] = entry
            print(f"[cardiac/{ch}] AUROC={entry['auroc']} "
                  f"(act={entry['n_actives_scored']}/dec={entry['n_decoys_scored']})", flush=True)
        except Exception as e:
            out["channels"][ch] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL cardiac/{ch}] {e}\n{traceback.format_exc()[:500]}", flush=True)
    return out


# ===========================================================================
def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = {
        "model": "CToxPred2 (issararab/CToxPred2, JCIM 2024)",
        "track": "5 - cardiac / ion-channel toxicity (hERG / Nav1.5 / Cav1.2 block, ligand-only)",
        "framing_caveat": ("CToxPred2 predicts CARDIAC-channel block from SMILES alone — a "
                           "molecule-level liability flag, NOT CNS-channel target-conditioned DTI. "
                           "Its hERG head is a direct competitor to our Track-5 hERG gate; its "
                           "Nav1.5/Cav1.2 heads are a multi-channel cardiac-safety extra our single "
                           "gate lacks. It does not address the CNS Nav1.x binder question (BALM/Boltz-2)."),
        "config": {"backend": BACKEND, "mc_iters": MC_ITERS, "max_herg": MAX_HERG,
                   "active_pchembl": ACTIVE_PCHEMBL, "inactive_pchembl": INACTIVE_PCHEMBL,
                   "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
                   "decoy_ratio": DECOY_RATIO, "min_decoys": MIN_DECOYS, "seed": SEED},
        "reference_track5": {"maplight_herg_auroc": MAPLIGHT_HERG_AUROC,
                             "maplight_herg_far_ood_auroc": MAPLIGHT_HERG_FAR_OOD_AUROC,
                             "maplight_herg_brier": MAPLIGHT_HERG_BRIER,
                             "fp_xgboost_herg_auroc": FP_XGB_HERG_AUROC},
        "load": {}, "herg_primary": {}, "cardiac_bonus": {},
    }

    def flush():
        json.dump(res, open(OUT, "w"), indent=2, default=str)

    flush()

    # Load the model wrapper (imports repo classes + decompressed weights presence).
    try:
        model = CToxPred2()
        present = {}
        for sub in ["model_weights", "random_forest", "decriptors_preprocessing"]:
            d = model.models_root / sub
            present[sub] = d.exists()
        res["load"] = {"status": "ok", "weights_dirs_present": present}
        print(f"[load] ok; weights dirs: {present}", flush=True)
    except Exception as e:
        res["load"] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}",
                       "traceback": traceback.format_exc()[:1500]}
        print(f"[FATAL load] {e}\n{traceback.format_exc()[:1500]}", flush=True)
        flush()
        return 1
    flush()

    # (a) PRIMARY: hERG head on TDC hERG_Karim (same protocol as MapLight/FP-XGBoost).
    try:
        herg_data = load_herg_karim(MAX_HERG)
        rnd = herg_data["random"]
        res["herg_primary"]["data"] = {
            "random_train": len(rnd["train"]), "random_test": len(rnd["test"]),
            "scaffold_split": isinstance(herg_data.get("scaffold"), dict) and "train" in herg_data["scaffold"]}
        print(f"[tdc hERG_Karim] {len(rnd['train'])} train / {len(rnd['test'])} test", flush=True)
        flush()
        res["herg_primary"].update(run_herg_primary(model, herg_data, BACKEND))
    except Exception as e:
        res["herg_primary"]["error"] = f"{type(e).__name__}: {e}"
        print(f"[FAIL hERG primary] {e}\n{traceback.format_exc()[:800]}", flush=True)
    flush()

    # (b) BONUS: Nav1.5 / Cav1.2 heads on ChEMBL blocker-vs-decoy.
    try:
        res["cardiac_bonus"] = run_cardiac_bonus(model, BACKEND)
    except Exception as e:
        res["cardiac_bonus"] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL cardiac bonus] {e}\n{traceback.format_exc()[:800]}", flush=True)
    flush()

    res["elapsed_s"] = round(time.time() - t0, 1)
    flush()
    print(f"[done] {res['elapsed_s']}s -> {OUT}", flush=True)
    print(json.dumps(res.get("herg_primary", {}).get("head_to_head", {}), indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
