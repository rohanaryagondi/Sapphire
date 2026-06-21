"""MapLight held-out BBB validation on B3DB (Track-4 follow-up; independent confirmation).

Phase 1 (aws/chemeleon_maplight_eval.py) found MapLight BBBP scaffold-AUROC 0.905 > MolFormer-XL
0.889 on TDC BBB_Martins. Before we retire MolFormer-XL as the Explorer BBB head, we need an
INDEPENDENT held-out confirmation on a DIFFERENT dataset. This run does exactly that:

  TRAIN  both models on the FULL TDC BBB_Martins set (same recipe as Phase 1).
  TEST   on B3DB (the largest public BBB dataset, CC0), with TRUE held-out dedup:
         RDKit-canonicalize SMILES on both sides and DROP any B3DB molecule whose canonical
         SMILES is also in the TDC BBB_Martins train set. (No scaffold overlap removal — B3DB is
         already a different curation; the canonical-SMILES dedup guarantees no exact leakage.)

Two CLASSICAL/LM contenders, reusing the EXACT Phase-1 / derisking recipes (imported verbatim,
not reinvented):
  - MapLight (MIT) — CatBoost on concat(ECFP count 1024, Avalon count 1024, ErG ~315, RDKit
    physchem ~200). Featurizer + CatBoost recipe lifted verbatim from aws/chemeleon_maplight_eval.py.
  - MolFormer-XL (ibm/MoLFormer-XL-both-10pct) — mean-pooled last_hidden_state + LogisticRegression
    head. Embedder + head lifted verbatim from aws/derisking_characterization.py make_embedder().

Reported per model: AUROC, AUPRC, Brier, accuracy, n_test. Plus an applicability-domain (OOD)
breakdown by max Tanimoto (ECFP4) to the TDC train set in near(>=0.4)/mid/far(<0.3) bands — this
is MapLight's claimed strength (does its classical featurization stay reliable off-domain where the
LM degrades?). Every section is independently try/except-guarded so one failure still banks the rest.

================================ DATA SOURCE / COLUMN ASSUMPTIONS ============================
B3DB (CC0) — https://github.com/theochem/B3DB
  Classification table: B3DB/B3DB_classification.tsv  (TAB-separated).
  Columns we use:
    - "SMILES"     : molecule SMILES.
    - "BBB+/BBB-"  : label, string values "BBB+" / "BBB-". Map BBB+ -> 1 (penetrant), BBB- -> 0.
  ASSUMPTION: exact column names "SMILES" and "BBB+/BBB-" per the repo's published schema. If the
  upstream header drifts, adjust B3DB_SMILES_COL / B3DB_LABEL_COL below — the loader also falls back
  to a case-insensitive / fuzzy match and records what it actually used in the result JSON under
  results["b3db_load"]["columns_used"].
=============================================================================================

TDC BBB_Martins: column "Drug" (SMILES), "Y" (0/1). Same loader as Phase 1.
"""
from __future__ import annotations
import json, os, sys, traceback
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/ml_out/maplight_b3db_result.json"))
SEED = int(os.environ.get("SEED", "1"))

# B3DB classification table (CC0). The userdata pre-fetches this to B3DB_LOCAL as a backup; the eval
# tries the local copy first, then the remote URL.
B3DB_URL = os.environ.get(
    "B3DB_URL",
    "https://raw.githubusercontent.com/theochem/B3DB/main/B3DB/B3DB_classification.tsv",
)
B3DB_LOCAL = os.environ.get("B3DB_LOCAL", "/root/B3DB_classification.tsv")
B3DB_SMILES_COL = "SMILES"       # adjust here if upstream header drifts
B3DB_LABEL_COL = "BBB+/BBB-"     # values "BBB+"/"BBB-"

MOLFORMER_TDC_SCAFFOLD = 0.889   # the Phase-1 baseline we are independently checking
MAPLIGHT_TDC_SCAFFOLD = 0.905    # Phase-1 MapLight scaffold AUROC (context only)


# ============================= metric helpers =============================
def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    labels = list(labels)
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(roc_auc_score(labels, scores))


def auprc(labels, scores):
    from sklearn.metrics import average_precision_score
    labels = list(labels)
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(average_precision_score(labels, scores))


def brier(labels, probs):
    labels = np.asarray(labels, dtype=float); probs = np.asarray(probs, dtype=float)
    if len(labels) < 3:
        return None
    return float(np.mean((probs - labels) ** 2))


def accuracy(labels, probs, thr=0.5):
    labels = np.asarray(labels, dtype=float); probs = np.asarray(probs, dtype=float)
    if len(labels) < 1:
        return None
    return float(np.mean((probs >= thr).astype(float) == labels))


def safe_float_matrix(X):
    """NaN/inf -> 0; clip wild magnitudes (Avalon/physchem can blow up). Verbatim from Phase 1."""
    X = np.asarray(X, dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(X, -1e9, 1e9)


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:900]}", flush=True)


# ============================= canonicalization =============================
def canonicalize(smi):
    """RDKit-canonical SMILES (None on parse failure). Used for both dedup and featurizer parsing."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    if not isinstance(smi, str):
        return None
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    try:
        return Chem.MolToSmiles(m)
    except Exception:
        return None


# ============================= TDC train loading =============================
def load_tdc_train():
    """FULL TDC BBB_Martins as the training set. Returns (smiles_list, y_array). No split — we use
    every labeled molecule, since the held-out test comes from B3DB."""
    from tdc.single_pred import ADME as Loader
    data = Loader(name="BBB_Martins")
    df = data.get_data()  # columns: Drug_ID, Drug (SMILES), Y
    smis = [str(s) for s in df["Drug"].tolist()]
    y = np.array([int(round(float(v))) for v in df["Y"].tolist()], dtype=int)
    return smis, y


# ============================= B3DB held-out loading + dedup =============================
def _pick_column(cols, preferred, contains_any):
    """Resolve a column name: exact preferred -> case-insensitive -> fuzzy 'contains' match."""
    if preferred in cols:
        return preferred
    low = {c.lower(): c for c in cols}
    if preferred.lower() in low:
        return low[preferred.lower()]
    for c in cols:
        cl = c.lower()
        if any(tok in cl for tok in contains_any):
            return c
    return None


def load_b3db_held_out(train_canon_set):
    """Load B3DB classification TSV, map BBB+/BBB- -> 1/0, canonicalize, and REMOVE any molecule whose
    canonical SMILES is in train_canon_set (true held-out). Returns dict with smiles/labels/canon +
    bookkeeping (n_total, n_dropped_overlap, n_test, columns_used)."""
    import pandas as pd
    src = None
    if os.path.exists(B3DB_LOCAL):
        try:
            df = pd.read_csv(B3DB_LOCAL, sep="\t")
            src = f"local:{B3DB_LOCAL}"
        except Exception:
            df = None
    else:
        df = None
    if df is None:
        df = pd.read_csv(B3DB_URL, sep="\t")
        src = f"url:{B3DB_URL}"

    cols = list(df.columns)
    smi_col = _pick_column(cols, B3DB_SMILES_COL, contains_any=["smiles", "smile"])
    lab_col = _pick_column(cols, B3DB_LABEL_COL, contains_any=["bbb+/bbb-", "bbb+", "bbb-", "bbb_class", "bbb class"])
    if smi_col is None or lab_col is None:
        raise RuntimeError(f"could not resolve B3DB columns; have {cols[:12]} "
                           f"(smi={smi_col}, lab={lab_col})")

    raw_smis = [str(s) for s in df[smi_col].tolist()]
    raw_labs = df[lab_col].tolist()

    def to_label(v):
        s = str(v).strip().lower()
        if s in ("bbb+", "+", "1", "1.0", "penetrant", "true", "yes"):
            return 1
        if s in ("bbb-", "-", "0", "0.0", "non-penetrant", "false", "no"):
            return 0
        # numeric fallback
        try:
            return int(round(float(s)))
        except Exception:
            return None

    n_total = len(raw_smis)
    n_unparseable = 0
    n_unlabeled = 0
    kept_smi, kept_lab, kept_canon = [], [], []
    n_dropped_overlap = 0
    for s, lv in zip(raw_smis, raw_labs):
        lab = to_label(lv)
        if lab is None:
            n_unlabeled += 1
            continue
        c = canonicalize(s)
        if c is None:
            n_unparseable += 1
            continue
        if c in train_canon_set:
            n_dropped_overlap += 1
            continue
        kept_smi.append(s)
        kept_lab.append(int(lab))
        kept_canon.append(c)

    return {
        "smiles": kept_smi,
        "labels": np.array(kept_lab, dtype=int),
        "canon": kept_canon,
        "n_total": int(n_total),
        "n_unparseable": int(n_unparseable),
        "n_unlabeled": int(n_unlabeled),
        "n_dropped_overlap": int(n_dropped_overlap),
        "n_test": int(len(kept_smi)),
        "n_pos": int(sum(kept_lab)),
        "n_neg": int(len(kept_lab) - sum(kept_lab)),
        "columns_used": {"smiles": smi_col, "label": lab_col},
        "source": src,
    }


# ============================= MapLight featurizer (verbatim from Phase 1) =============================
def _maplight_calculator():
    from rdkit.Chem import Descriptors
    from rdkit.ML.Descriptors.MoleculeDescriptors import MolecularDescriptorCalculator
    names = [d[0] for d in Descriptors.descList]  # full list (~200), matches spec
    return MolecularDescriptorCalculator(names)


def maplight_features(smiles_list):
    """concat(ECFP-count 1024, Avalon-count 1024, ErG ~315, RDKit physchem ~200).
    Verbatim from aws/chemeleon_maplight_eval.py (verified vs maplight.py)."""
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


def fit_maplight_head(Xtr, ytr):
    """CatBoost recipe verbatim from aws/chemeleon_maplight_eval.py."""
    from catboost import CatBoostClassifier
    clf = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05,
                             loss_function="Logloss", eval_metric="AUC",
                             random_seed=SEED, verbose=False, allow_writing_files=False)
    clf.fit(Xtr, ytr)
    return clf


def predict_proba(clf, X):
    p = clf.predict_proba(X)
    return p[:, 1] if p.ndim == 2 else p


# ============================= MolFormer-XL embedder (verbatim from derisking_characterization.py) =====
def make_embedder(repo, device):
    """mean-pooled last_hidden_state. Verbatim from aws/derisking_characterization.py make_embedder()."""
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
    kw = {"deterministic_eval": True} if "MoLFormer" in repo else {}
    model = AutoModel.from_pretrained(repo, trust_remote_code=True, **kw).to(device).eval()

    @torch.no_grad()
    def embed(smis, bs=64):
        out = []
        for i in range(0, len(smis), bs):
            inp = tok(smis[i:i + bs], padding=True, truncation=True, max_length=256,
                      return_tensors="pt").to(device)
            h = model(**inp).last_hidden_state
            m = inp["attention_mask"].unsqueeze(-1).float()
            out.append(((h * m).sum(1) / m.sum(1).clamp(min=1)).cpu().numpy().astype(np.float64))
        return np.concatenate(out, 0)
    return embed, model, tok


def fit_lm_head(Xtr, ytr):
    """LogisticRegression head, verbatim recipe from derisking_characterization.eval_lm_on_endpoint."""
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)


# ============================= applicability domain (Tanimoto-to-train band, ECFP4) ===================
def max_tanimoto_to_train(test_smiles, train_smiles):
    """Max Tanimoto (ECFP4 = Morgan radius 2, 2048 bits) of each test molecule to the train set.
    ECFP4 per spec. Mirrors the Phase-1 tanimoto_to_train logic."""
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


def ad_breakdown(labels, probs, sims):
    """AUROC within far(<0.3) / mid[0.3,0.4) / near(>=0.4) Tanimoto-to-train bands. Per spec the cut
    points are near>=0.4 and far<0.3 (mid is the [0.3,0.4) gap between them)."""
    bands = [(0.0, 0.3, "far(<0.3)"), (0.3, 0.4, "mid[0.3,0.4)"), (0.4, 1.01, "near(>=0.4)")]
    labels = np.asarray(labels); probs = np.asarray(probs)
    out = {}
    for lo, hi, name in bands:
        m = (sims >= lo) & (sims < hi)
        lab = labels[m].tolist()
        prob = probs[m].tolist()
        out[name] = {
            "n": int(m.sum()),
            "auroc": auroc(lab, prob),
            "auprc": auprc(lab, prob),
            "mean_sim": round(float(sims[m].mean()), 3) if m.sum() else None,
            "n_pos": int(np.asarray(lab).sum()) if m.sum() else 0,
        }
    return out


# ============================= per-model scoring on B3DB =============================
def score_model(model_name, train_smis, ytr, b3db, sims):
    """Train on TDC BBB_Martins (train_smis/ytr), score on deduped B3DB. Returns the metric dict +
    AD-band breakdown. Featurizer/head dispatched by model_name."""
    te_smis = b3db["smiles"]; yte = b3db["labels"]
    if model_name == "maplight":
        Xtr = maplight_features(train_smis)
        Xte = maplight_features(te_smis)
        clf = fit_maplight_head(Xtr, np.asarray(ytr))
        pte = predict_proba(clf, Xte)
    elif model_name == "molformer_xl":
        embed, _, _ = make_embedder("ibm/MoLFormer-XL-both-10pct", DEVICE)
        Xtr = embed(train_smis)
        Xte = embed(te_smis)
        clf = fit_lm_head(Xtr, np.asarray(ytr))
        pte = clf.predict_proba(Xte)[:, 1]
    else:
        raise ValueError(f"unknown model {model_name}")
    d = {
        "n_test": int(len(yte)),
        "n_pos": int(np.asarray(yte).sum()),
        "auroc": auroc(list(yte), pte),
        "auprc": auprc(list(yte), pte),
        "brier": brier(list(yte), pte),
        "accuracy": accuracy(list(yte), pte),
    }
    d["ad_reliability"] = ad_breakdown(yte, pte, sims)
    return d


def main():
    R = {}

    # 1) FULL TDC BBB_Martins train set (shared by both models).
    train_state = {}
    def _load_train():
        smis, y = load_tdc_train()
        canon = set()
        for s in smis:
            c = canonicalize(s)
            if c is not None:
                canon.add(c)
        train_state["smiles"] = smis
        train_state["y"] = y
        train_state["canon"] = canon
        return {"n_train": int(len(smis)), "n_train_pos": int(y.sum()),
                "n_train_canon": int(len(canon))}
    section(_load_train, "tdc_train", R)

    # 2) Load + dedup B3DB held-out.
    b3db_state = {}
    def _load_b3db():
        canon_set = train_state.get("canon", set())
        b = load_b3db_held_out(canon_set)
        b3db_state.update(b)
        # JSON-safe view (drop the big arrays/lists)
        return {k: v for k, v in b.items() if k not in ("smiles", "labels", "canon")}
    section(_load_b3db, "b3db_load", R)

    # 3) Tanimoto-to-train (ECFP4) for the AD bands — computed once, shared across models.
    sims_holder = {}
    def _sims():
        if not b3db_state.get("smiles") or "smiles" not in train_state:
            raise RuntimeError("B3DB or TDC train not loaded")
        s = max_tanimoto_to_train(b3db_state["smiles"], train_state["smiles"])
        sims_holder["sims"] = s
        return {"n": int(s.size),
                "near(>=0.4)": int((s >= 0.4).sum()),
                "mid[0.3,0.4)": int(((s >= 0.3) & (s < 0.4)).sum()),
                "far(<0.3)": int((s < 0.3).sum()),
                "mean": round(float(s.mean()), 3) if s.size else None}
    section(_sims, "ad_bins", R)

    # 4) Score both models on the deduped B3DB test set.
    results = {}
    def _need():
        if "smiles" not in train_state or not b3db_state.get("smiles") or "sims" not in sims_holder:
            raise RuntimeError("prerequisites missing (train/b3db/sims)")
    section(lambda: (_need(), score_model("maplight", train_state["smiles"], train_state["y"],
                                          b3db_state, sims_holder["sims"]))[1],
            "maplight", results)
    section(lambda: (_need(), score_model("molformer_xl", train_state["smiles"], train_state["y"],
                                          b3db_state, sims_holder["sims"]))[1],
            "molformer_xl", results)

    payload = {
        "dataset": "B3DB held-out",
        "track": "4 - BBB de-risking; independent held-out confirmation before retiring MolFormer-XL",
        "question": "Does Phase-1's MapLight > MolFormer-XL on BBB hold out-of-sample on B3DB, "
                    "especially off-domain (low Tanimoto-to-train)?",
        "train": "FULL TDC BBB_Martins (every labeled molecule)",
        "test": "B3DB classification (CC0), canonical-SMILES dedup vs TDC train",
        "models": ["MapLight (CatBoost on ECFP+Avalon+ErG+RDKit-physchem)",
                   "MolFormer-XL (ibm/MoLFormer-XL-both-10pct, mean-pool + LogReg)"],
        "baselines": {"molformer_tdc_scaffold": MOLFORMER_TDC_SCAFFOLD,
                      "maplight_tdc_scaffold": MAPLIGHT_TDC_SCAFFOLD},
        "seed": SEED,
        "b3db_load": R.get("b3db_load"),
        "tdc_train": R.get("tdc_train"),
        "ad_bins": R.get("ad_bins"),
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)

    # compact stdout summary
    summary = {m: (results.get(m, {}).get("auroc") if isinstance(results.get(m), dict) else None)
               for m in ("maplight", "molformer_xl")}
    print(json.dumps({"b3db_n_test": b3db_state.get("n_test"),
                      "n_dropped_overlap": b3db_state.get("n_dropped_overlap"),
                      "auroc": summary}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
