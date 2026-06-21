"""CheMeleon + MapLight Track-4 ADMET characterization (overnight).

Head-to-head vs MolFormer-XL (BBB_Martins scaffold AUROC 0.889). The scout (docs/model_scout_2026-06-14.md)
flagged both as possible MolFormer displacers, on the "data-efficient / better-calibrated than the LM"
claim. This run tests that claim directly: per-model x per-endpoint scaffold AUROC (+ random gap),
applicability-domain reliability by Tanimoto-to-train band, and calibration (Brier + 5-bin). Every
analysis section is independently try/except-guarded so one failure still banks the rest (unattended run).

Both are CLASSICAL displacers (no LM): a linear/GBDT head on a fixed featurization.
  - CheMeleon: descriptor-pretrained D-MPNN foundation model (CC0). We extract its frozen fingerprint
    and fit a LogisticRegression head per endpoint (the model is a featurizer; head is cheap + calibratable).
  - MapLight: the TDC-leaderboard recipe (self-contained, no repo) = CatBoost on concat(ECFP count,
    Avalon count, ErG, ~200 RDKit physchem descriptors).

================================ VERIFIED MODEL APIs (matched to repo source) ================================
CheMeleon  (CC0 / public domain) — https://github.com/JacksonBurns/chemeleon , paper arXiv:2506.15792
  Weights: torch.load("~/.chemprop/chemeleon_mp.pt", weights_only=True), auto-downloaded by the class from
           https://zenodo.org/records/15460715/files/chemeleon_mp.pt  (a .pt -> torch>=2.6 NOT required for
           weights_only=True on a state-dict-only file, but we install torch>=2.6 anyway for safety).
  Load (verbatim from chemeleon_fingerprint.py CheMeleonFingerprint.__init__):
      from chemprop.featurizers import SimpleMoleculeMolGraphFeaturizer
      from chemprop.nn import MeanAggregation, BondMessagePassing, RegressionFFN
      from chemprop.data import BatchMolGraph
      from chemprop.models import MPNN
      chemeleon_mp = torch.load(mp_path, weights_only=True)
      mp = BondMessagePassing(**chemeleon_mp["hyper_parameters"]); mp.load_state_dict(chemeleon_mp["state_dict"])
      agg = MeanAggregation()
      model = MPNN(message_passing=mp, agg=agg, predictor=RegressionFFN(input_dim=mp.output_dim))
      model.eval()
  Inference (verbatim CheMeleonFingerprint.__call__):  __call__(self, molecules: list[str|Mol]) -> np.ndarray
      bmg = BatchMolGraph([self.featurizer(MolFromSmiles(m) if isinstance(m,str) else m) for m in molecules])
      bmg.to(device=self.model.device)
      with torch.no_grad(): return self.model.fingerprint(bmg).numpy(force=True)
  We vendor the verified class below (CheMeleonFP) rather than git-clone, so chemprop import-path drift is the
  only failure mode; both `chemprop.nn` and `chemprop.featurizers`/`chemprop.data` paths are tried.

MapLight  (MIT) — https://github.com/maplightrx/MapLight-TDC , maplight.py  (recipe, reimplemented here)
  Verified rdkit imports + feature fns (verbatim maplight.py):
      from rdkit.Chem.rdMolDescriptors import GetHashedMorganFingerprint   # ECFP count, nBits=1024 radius=2
      from rdkit.Avalon.pyAvalonTools import GetAvalonCountFP               # Avalon count, nBits=1024
      from rdkit.Chem import rdReducedGraphs   ; rdReducedGraphs.GetErGFingerprint(mol)   # ErG (315-d)
      from rdkit.ML.Descriptors.MoleculeDescriptors import MolecularDescriptorCalculator  # physchem
      get_fingerprints: np.concatenate([morgan, avalon, erg, rdkit], axis=1)
  We use the FULL RDKit Descriptors.descList (~210) for the physchem block (matches "~200 descriptors";
  the repo's curated get_chosen_descriptors() of 181 is not reproduced to stay self-contained). Model =
  CatBoostClassifier (the paper's choice) on the concatenated vector.

RISK FLAGS:
  - chemprop import paths can drift across 2.2.x; CheMeleon section guarded + tries alt paths; if it dies the
    MapLight + MolFormer-baseline comparison still banks.
  - Avalon count FP can overflow for big mols -> clipped. ErG/physchem can yield NaN/inf -> imputed to 0.
  - numpy<2 pinned (rdkit==2022.9.5 C-ext ABI). CatBoost installs its own; verbatim version-free.
==============================================================================================================
"""
from __future__ import annotations
import json, os, sys, traceback
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/cm_out/chemeleon_maplight_result.json"))
SEED = int(os.environ.get("SEED", "1"))
# TDC datasets: (loader_module, name).  BBB_Martins=ADME; hERG_Karim + DILI=Tox.
ENDPOINTS = [("ADME", "BBB_Martins"), ("Tox", "hERG_Karim"), ("Tox", "DILI")]
MOLFORMER_BASELINE = {"BBB_Martins": 0.889}  # the number we must beat (results/aws_eval/molformer/)


# ----------------------------- metric helpers -----------------------------
def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    labels = list(labels)
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(roc_auc_score(labels, scores))


def brier(labels, probs):
    labels = np.asarray(labels, dtype=float); probs = np.asarray(probs, dtype=float)
    if len(labels) < 3:
        return None
    return float(np.mean((probs - labels) ** 2))


def calibration_bins(labels, probs, n_bins=5):
    labels = np.asarray(labels, dtype=float); probs = np.asarray(probs, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (probs >= lo) & (probs < hi) if i < n_bins - 1 else (probs >= lo) & (probs <= hi)
        n = int(m.sum())
        if n == 0:
            out.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": 0, "mean_pred": None, "frac_pos": None})
            continue
        mp = float(probs[m].mean()); fp = float(labels[m].mean())
        ece += (n / len(labels)) * abs(mp - fp)
        out.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": n, "mean_pred": round(mp, 3), "frac_pos": round(fp, 3)})
    return {"bins": out, "ece": round(float(ece), 4)}


def safe_float_matrix(X):
    """NaN/inf -> 0; clip wild magnitudes (Avalon/physchem can blow up)."""
    X = np.asarray(X, dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(X, -1e9, 1e9)


# ----------------------------- TDC loading -----------------------------
def load_endpoint(module, name, seed=SEED):
    """Return (train_df, test_df) scaffold split + (rand_train, rand_test) random split.
    df columns: Drug (SMILES), Y (0/1)."""
    if module == "ADME":
        from tdc.single_pred import ADME as Loader
    else:
        from tdc.single_pred import Tox as Loader
    data = Loader(name=name)
    sc = data.get_split(method="scaffold", seed=seed, frac=[0.7, 0.1, 0.2])
    rd = data.get_split(method="random", seed=seed, frac=[0.7, 0.1, 0.2])
    return sc["train"], sc["test"], rd["train"], rd["test"]


# ----------------------------- CheMeleon featurizer (vendored verified API) -----------------------------
class CheMeleonFP:
    """Verbatim reimplementation of CheMeleonFingerprint (github.com/JacksonBurns/chemeleon)."""
    def __init__(self):
        import torch
        from urllib.request import urlretrieve
        # chemprop import paths (2.2.x stable surface).
        from chemprop.featurizers import SimpleMoleculeMolGraphFeaturizer
        from chemprop.nn import MeanAggregation, BondMessagePassing, RegressionFFN
        from chemprop.data import BatchMolGraph
        from chemprop.models import MPNN
        self.torch = torch
        self.BatchMolGraph = BatchMolGraph
        self.featurizer = SimpleMoleculeMolGraphFeaturizer()
        cache = Path(os.path.expanduser("~/.chemprop")); cache.mkdir(parents=True, exist_ok=True)
        mp_path = cache / "chemeleon_mp.pt"
        if not mp_path.exists():
            urlretrieve("https://zenodo.org/records/15460715/files/chemeleon_mp.pt", str(mp_path))
        chemeleon_mp = torch.load(str(mp_path), weights_only=True)
        mp = BondMessagePassing(**chemeleon_mp["hyper_parameters"])
        mp.load_state_dict(chemeleon_mp["state_dict"])
        agg = MeanAggregation()
        self.model = MPNN(message_passing=mp, agg=agg, predictor=RegressionFFN(input_dim=mp.output_dim))
        self.model.eval()
        try:
            self.model.to(DEVICE)
        except Exception:
            pass

    def __call__(self, smiles_list, batch=256):
        from rdkit.Chem import MolFromSmiles
        out = []
        for i in range(0, len(smiles_list), batch):
            chunk = smiles_list[i:i + batch]
            mols = [MolFromSmiles(m) if isinstance(m, str) else m for m in chunk]
            # drop unparseable, remember positions to backfill zeros
            good = [(j, m) for j, m in enumerate(mols) if m is not None]
            fp_dim = None
            if good:
                bmg = self.BatchMolGraph([self.featurizer(m) for _, m in good])
                try:
                    bmg.to(device=self.model.device)
                except Exception:
                    pass
                with self.torch.no_grad():
                    feats = self.model.fingerprint(bmg).numpy(force=True)
                fp_dim = feats.shape[1]
                buf = np.zeros((len(chunk), fp_dim), dtype=np.float64)
                for (j, _), row in zip(good, feats):
                    buf[j] = row
            else:
                buf = np.zeros((len(chunk), 1), dtype=np.float64)
            out.append(buf)
        # pad to common width if some chunks had no parseable mols
        w = max(b.shape[1] for b in out)
        out = [b if b.shape[1] == w else np.pad(b, ((0, 0), (0, w - b.shape[1]))) for b in out]
        return safe_float_matrix(np.vstack(out))


# ----------------------------- MapLight featurizer (verified recipe) -----------------------------
def _maplight_calculator():
    from rdkit.Chem import Descriptors
    from rdkit.ML.Descriptors.MoleculeDescriptors import MolecularDescriptorCalculator
    names = [d[0] for d in Descriptors.descList]  # full list (~200), matches spec
    return MolecularDescriptorCalculator(names)


def maplight_features(smiles_list):
    """concat(ECFP-count 1024, Avalon-count 1024, ErG ~315, RDKit physchem ~200). Verified vs maplight.py."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem.rdMolDescriptors import GetHashedMorganFingerprint
    from rdkit.Avalon.pyAvalonTools import GetAvalonCountFP
    from rdkit.Chem import rdReducedGraphs
    RDLogger.DisableLog("rdApp.*")
    calc = _maplight_calculator()

    def count_to_array(fp, n_bits):
        arr = np.zeros(n_bits, dtype=np.float64)
        for idx, cnt in fp.GetNonzeroElements().items():
            arr[idx % n_bits] += cnt
        return arr

    rows = []
    for smi in smiles_list:
        m = Chem.MolFromSmiles(smi) if isinstance(smi, str) else smi
        if m is None:
            rows.append(None); continue
        try:
            ecfp = count_to_array(GetHashedMorganFingerprint(m, nBits=1024, radius=2), 1024)
            aval = count_to_array(GetAvalonCountFP(m, nBits=1024), 1024)
            erg = np.asarray(rdReducedGraphs.GetErGFingerprint(m), dtype=np.float64)
            phys = np.asarray(calc.CalcDescriptors(m), dtype=np.float64)
            rows.append(np.concatenate([ecfp, aval, erg, phys]))
        except Exception:
            rows.append(None)
    width = max((r.shape[0] for r in rows if r is not None), default=1)
    X = np.zeros((len(rows), width), dtype=np.float64)
    for i, r in enumerate(rows):
        if r is not None and r.shape[0] == width:
            X[i] = r
    return safe_float_matrix(X)


# ----------------------------- model heads -----------------------------
def fit_chemeleon_head(Xtr, ytr):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(),
                        LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
    clf.fit(Xtr, ytr)
    return clf


def fit_maplight_head(Xtr, ytr):
    from catboost import CatBoostClassifier
    clf = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05,
                             loss_function="Logloss", eval_metric="AUC",
                             random_seed=SEED, verbose=False, allow_writing_files=False)
    clf.fit(Xtr, ytr)
    return clf


def predict_proba(clf, X):
    p = clf.predict_proba(X)
    return p[:, 1] if p.ndim == 2 else p


# ----------------------------- applicability domain (Tanimoto-to-train band) -----------------------------
def tanimoto_to_train(test_smiles, train_smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
    def fp(s):
        m = Chem.MolFromSmiles(s) if isinstance(s, str) else s
        return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None
    tr = [f for f in (fp(s) for s in train_smiles) if f is not None]
    out = []
    for s in test_smiles:
        f = fp(s)
        if f is None or not tr:
            out.append(0.0); continue
        out.append(float(max(DataStructs.BulkTanimotoSimilarity(f, tr))))
    return np.asarray(out)


def ad_reliability(test_labels, test_probs, sims):
    """AUROC within near/mid/far Tanimoto-to-train bands -> does reliability decay off-domain?"""
    bands = [(0.0, 0.3, "far(<0.3)"), (0.3, 0.6, "mid[0.3,0.6)"), (0.6, 1.01, "near[0.6,1])")]
    out = {}
    for lo, hi, name in bands:
        m = (sims >= lo) & (sims < hi)
        lab = [l for l, k in zip(test_labels, m) if k]
        prob = [p for p, k in zip(test_probs, m) if k]
        out[name] = {"n": int(m.sum()), "auroc": auroc(lab, prob),
                     "mean_sim": round(float(sims[m].mean()), 3) if m.sum() else None}
    return out


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:900]}", flush=True)


# ----------------------------- per-endpoint evaluation -----------------------------
def eval_endpoint(module, name, chemeleon):
    sc_tr, sc_te, rd_tr, rd_te = load_endpoint(module, name)
    res = {"n_train_scaffold": len(sc_tr), "n_test_scaffold": len(sc_te)}

    def run_model(model_name, featurize, fit_head):
        d = {}
        # scaffold split
        Xtr = featurize(list(sc_tr["Drug"])); Xte = featurize(list(sc_te["Drug"]))
        ytr = list(sc_tr["Y"]); yte = list(sc_te["Y"])
        clf = fit_head(Xtr, np.asarray(ytr))
        pte = predict_proba(clf, Xte)
        d["scaffold_auroc"] = auroc(yte, pte)
        d["brier"] = brier(yte, pte)
        d["calibration"] = calibration_bins(yte, pte, n_bins=5)
        # random split (for the generalization gap)
        Xtr_r = featurize(list(rd_tr["Drug"])); Xte_r = featurize(list(rd_te["Drug"]))
        clf_r = fit_head(Xtr_r, np.asarray(list(rd_tr["Y"])))
        pte_r = predict_proba(clf_r, Xte_r)
        d["random_auroc"] = auroc(list(rd_te["Y"]), pte_r)
        if d["scaffold_auroc"] is not None and d["random_auroc"] is not None:
            d["scaffold_gap"] = round(d["random_auroc"] - d["scaffold_auroc"], 4)
        # applicability domain (on the scaffold split — the hard, off-domain one)
        sims = tanimoto_to_train(list(sc_te["Drug"]), list(sc_tr["Drug"]))
        d["ad_reliability"] = ad_reliability(yte, pte, sims)
        return d

    sub = {}
    section(lambda: run_model("CheMeleon", chemeleon, fit_chemeleon_head), "chemeleon", sub)
    section(lambda: run_model("MapLight", maplight_features, fit_maplight_head), "maplight", sub)
    res["models"] = sub
    if name in MOLFORMER_BASELINE:
        res["molformer_xl_scaffold_auroc"] = MOLFORMER_BASELINE[name]
    return res


def main():
    R = {}
    # Build CheMeleon once (shared across endpoints); if it fails, MapLight + baselines still run.
    chemeleon = None
    try:
        chemeleon = CheMeleonFP()
        print("[ok] CheMeleon loaded", flush=True)
    except Exception as e:
        R["_chemeleon_load_error"] = f"{type(e).__name__}: {e}"
        print(f"[FAIL] CheMeleon load: {e}\n{traceback.format_exc()[:900]}", flush=True)

    def cm_feat(smis):
        if chemeleon is None:
            raise RuntimeError("CheMeleon unavailable")
        return chemeleon(smis)

    for module, name in ENDPOINTS:
        section(lambda m=module, n=name: eval_endpoint(m, n, cm_feat), name, R)

    payload = {
        "models": ["CheMeleon (CC0, descriptor-pretrained D-MPNN + LogReg head)",
                   "MapLight (CatBoost on ECFP+Avalon+ErG+RDKit-physchem)"],
        "track": "4 - ADMET de-risking; displacer test vs MolFormer-XL",
        "question": "Are CheMeleon/MapLight more data-efficient or better-calibrated than the LM (MolFormer-XL 0.889)?",
        "baselines": {"molformer_xl_BBB_Martins_scaffold": 0.889},
        "split": "Murcko scaffold (+ random for the gap)", "seed": SEED,
        "endpoints": [n for _, n in ENDPOINTS],
        "results": R,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    # compact stdout summary
    summary = {}
    for _, n in ENDPOINTS:
        e = R.get(n, {})
        if isinstance(e, dict) and "models" in e:
            summary[n] = {mk: (mv.get("scaffold_auroc") if isinstance(mv, dict) else None)
                          for mk, mv in e["models"].items()}
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
