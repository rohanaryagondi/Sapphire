"""De-risking deep operating-envelope characterization (overnight Phase 2) — Tracks 4 & 5.

The de-risking winners (MolFormer-XL on BBB, ChemBERTa-2 on hERG/DILI, ADMET-AI cross-check) get
Boltz-level depth on big EXTERNAL TDC panels (fetched on-instance via PyTDC; never to the laptop):
where each model is reliable vs not, and WHY. Extends aws/comprehensive_admet_char.py with TDC data
fetched in-script, a per-bin applicability-domain reliability table, calibration, descriptor-based
failure-mode tags, and a dedicated hERG head-to-head (Morgan-FP + XGBoost, the TDC-leaderboard recipe).

For EACH (model x endpoint):
  1. Murcko SCAFFOLD-split held-out AUROC vs random-split AUROC (the honest generalization gap).
  2. Applicability domain — bin test compounds by max-Tanimoto-to-train; AUROC + accuracy per bin.
  3. Calibration — Brier score + a 5-bin reliability table (are the probabilities trustworthy?).
  4. Failure-mode tags — for the worst-scored actives/decoys, record simple rdkit descriptors
     (MW, logP, #rings, formal charge, #rot-bonds, #aromatic-rings) to surface which chemotypes fail.

Plus (5): a dedicated hERG head-to-head — a Morgan-FP + XGBoost hERG classifier trained on hERG_Karim
train, eval on test, compared to ChemBERTa's hERG AUROC (is the LM edge real OOD, or a mirage?).
Optionally cross-checks ADMET-AI on DILI/BBB if it installs.

Every (model x endpoint) is independently guarded in try/except, and the result JSON is rewritten
after each one, so partial failures still bank everything that finished — important for an
unattended run.

Config via env vars (mirrors balm_characterization.py's env style):
  OUT             output JSON (default /root/derisking_out/derisking_characterization_result.json)
  FORCE_CPU=1     force CPU
  MAX_PER_EP      cap rows per endpoint per class (default 4000; keeps LM embedding time bounded)
  RUN_ADMET_AI=0  skip the ADMET-AI cross-check (default 1 = attempt it best-effort)
"""
from __future__ import annotations
import os, json, time, traceback
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
from datetime import datetime
import numpy as np

OUT = os.environ.get("OUT", "/root/derisking_out/derisking_characterization_result.json")
FORCE_CPU = os.environ.get("FORCE_CPU") == "1"
MAX_PER_EP = int(os.environ.get("MAX_PER_EP", "4000"))
RUN_ADMET_AI = os.environ.get("RUN_ADMET_AI", "1") != "0"

# (display name, HF repo, MoLFormer-style kwarg?) — MoLFormer needs deterministic_eval + trust_remote_code.
MODELS = [
    ("MolFormer-XL", "ibm/MoLFormer-XL-both-10pct"),
    ("ChemBERTa-2", "DeepChem/ChemBERTa-77M-MTR"),
]
# TDC single-pred ADME/Tox endpoints. (name -> (TDC group, TDC dataset name, higher_label_is_active)).
ENDPOINTS = {
    "BBB_Martins": ("ADME", "BBB_Martins"),
    "hERG_Karim": ("Tox", "hERG_Karim"),
    "DILI": ("Tox", "DILI"),
}


# ---------------- metrics ----------------
def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); rk = np.empty(len(s)); rk[o] = np.arange(1, len(s) + 1)
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    avg = {}; st = 0
    for k, c in enumerate(cnt):
        avg[k] = (st + 1 + st + c) / 2; st += c
    rb = np.array([avg[i] for i in inv])
    return float((rb[y == 1].sum() - p * (p + 1) / 2) / (p * n))


def calibration(y, p, bins=5):
    y = np.asarray(y); p = np.asarray(p, float)
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


# ---------------- rdkit helpers ----------------
def scaffold(smi):
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    try:
        m = Chem.MolFromSmiles(smi)
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) if m else None
    except Exception:
        return None


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
            out.append(0.0); continue
        sims = DataStructs.BulkTanimotoSimilarity(f, tr)
        out.append(max(sims) if sims else 0.0)
    return np.array(out)


def descriptors(smi):
    """Simple interpretable descriptors for failure-mode tagging."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    try:
        return {"mw": round(float(Descriptors.MolWt(m)), 1),
                "logp": round(float(Descriptors.MolLogP(m)), 2),
                "n_rings": int(rdMolDescriptors.CalcNumRings(m)),
                "n_aromatic_rings": int(rdMolDescriptors.CalcNumAromaticRings(m)),
                "n_rot_bonds": int(rdMolDescriptors.CalcNumRotatableBonds(m)),
                "formal_charge": int(Chem.GetFormalCharge(m)),
                "tpsa": round(float(Descriptors.TPSA(m)), 1)}
    except Exception:
        return None


def applicability_domain(yte, p, te_fp, tr_fp):
    """AUROC + accuracy per Tanimoto-to-train band; where does it silently degrade?"""
    mt = max_tanimoto(te_fp, tr_fp)
    pred = (np.asarray(p) >= 0.5).astype(int)
    bands = []
    for lo, hi, lab in [(0.0, 0.3, "far/OOD"), (0.3, 0.5, "mid"), (0.5, 1.01, "near")]:
        m = (mt >= lo) & (mt < hi)
        if m.sum() >= 10:
            acc = float((pred[m] == np.asarray(yte)[m]).mean())
            au = auroc(np.asarray(yte)[m], np.asarray(p)[m]) if len(set(np.asarray(yte)[m])) == 2 else float("nan")
            bands.append({"band": lab, "tanimoto": f"{lo}-{hi}", "n": int(m.sum()),
                          "auroc": None if au != au else round(au, 3), "accuracy": round(acc, 3)})
    return {"mean_tanimoto_to_train": round(float(mt.mean()), 3),
            "frac_OOD_<0.3": round(float((mt < 0.3).mean()), 3), "bands": bands}


def failure_modes(yte, p, te_s, k=8):
    """Worst-scored actives (low prob) + worst-scored decoys (high prob); tag with descriptors."""
    y = np.asarray(yte); p = np.asarray(p, float)
    act_idx = [i for i in range(len(y)) if y[i] == 1]
    dec_idx = [i for i in range(len(y)) if y[i] == 0]
    worst_act = sorted(act_idx, key=lambda i: p[i])[:k]            # actives the model called inactive
    worst_dec = sorted(dec_idx, key=lambda i: -p[i])[:k]          # decoys the model called active
    def pack(idxs):
        out = []
        for i in idxs:
            out.append({"smiles": te_s[i], "pred": round(float(p[i]), 3),
                        "true": int(y[i]), "descriptors": descriptors(te_s[i])})
        return out
    return {"worst_scored_actives": pack(worst_act), "worst_scored_decoys": pack(worst_dec)}


# ---------------- TDC loading (on-instance) ----------------
def load_tdc_endpoint(name, max_per_class):
    """Return dict with random + scaffold splits as {'train':[{smiles,y}],'test':[...]}.

    PyTDC labels: ADME/Tox single-pred sets are already binary (0/1). We pull the default split for
    'random' and the scaffold split for 'scaffold'. Capped per class to keep LM embedding bounded.
    """
    grp, ds = ENDPOINTS[name]
    if grp == "ADME":
        from tdc.single_pred import ADME as Loader
    else:
        from tdc.single_pred import Tox as Loader
    data = Loader(name=ds)

    def to_rows(split):
        rows = []
        for _, r in split.iterrows():
            smi = r.get("Drug"); y = r.get("Y")
            if smi is None or y is None:
                continue
            rows.append({"smiles": str(smi), "y": int(round(float(y)))})
        # cap per class
        pos = [x for x in rows if x["y"] == 1][:max_per_class]
        neg = [x for x in rows if x["y"] == 0][:max_per_class]
        return pos + neg

    rnd = data.get_split(method="random", seed=42)
    out = {"random": {"train": to_rows(rnd["train"]), "test": to_rows(rnd["test"])}}
    try:
        sc = data.get_split(method="scaffold", seed=42)
        out["scaffold"] = {"train": to_rows(sc["train"]), "test": to_rows(sc["test"])}
    except Exception as e:
        out["scaffold"] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ---------------- LM embedding heads ----------------
def make_embedder(repo, device):
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
    kw = {"deterministic_eval": True} if "MoLFormer" in repo else {}
    model = AutoModel.from_pretrained(repo, trust_remote_code=True, **kw).to(device).eval()

    @torch.no_grad()
    def embed(smis, bs=64):
        out = []
        for i in range(0, len(smis), bs):
            inp = tok(smis[i:i + bs], padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
            h = model(**inp).last_hidden_state
            m = inp["attention_mask"].unsqueeze(-1).float()
            out.append(((h * m).sum(1) / m.sum(1).clamp(min=1)).cpu().numpy().astype(np.float64))
        return np.concatenate(out, 0)
    return embed, model, tok


def eval_lm_on_endpoint(embed, ep_data):
    """LM features -> logistic regression. Returns the full operating-envelope dict for one endpoint."""
    from sklearn.linear_model import LogisticRegression
    rnd = ep_data["random"]
    tr, te = rnd["train"], rnd["test"]
    tr_s = [r["smiles"] for r in tr]; ytr = np.array([r["y"] for r in tr])
    te_s = [r["smiles"] for r in te]; yte = np.array([r["y"] for r in te])
    Xtr, Xte = embed(tr_s), embed(te_s)
    clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    rand_auroc = auroc(yte, p)

    # scaffold-held-out: fit on the TDC scaffold-split train, eval on its scaffold-split test
    sc_auroc = None
    sc = ep_data.get("scaffold")
    if isinstance(sc, dict) and "train" in sc:
        s_tr, s_te = sc["train"], sc["test"]
        s_tr_s = [r["smiles"] for r in s_tr]; s_ytr = np.array([r["y"] for r in s_tr])
        s_te_s = [r["smiles"] for r in s_te]; s_yte = np.array([r["y"] for r in s_te])
        if len(set(s_ytr)) == 2 and len(set(s_yte)) == 2 and len(s_tr_s) > 30:
            Xs_tr, Xs_te = embed(s_tr_s), embed(s_te_s)
            clf2 = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xs_tr, s_ytr)
            sc_auroc = auroc(s_yte, clf2.predict_proba(Xs_te)[:, 1])

    tr_fp = morgan(tr_s); te_fp = morgan(te_s)
    return {
        "n_train": len(ytr), "n_test": len(yte), "test_pos": int(yte.sum()),
        "random_split_auroc": round(rand_auroc, 4) if rand_auroc == rand_auroc else None,
        "scaffold_held_out_auroc": round(sc_auroc, 4) if (sc_auroc is not None and sc_auroc == sc_auroc) else None,
        "generalization_gap": (round(rand_auroc - sc_auroc, 4)
                               if (sc_auroc is not None and rand_auroc == rand_auroc and sc_auroc == sc_auroc) else None),
        "applicability_domain": applicability_domain(yte, p, te_fp, tr_fp),
        "calibration": calibration(yte, p),
        "failure_modes": failure_modes(yte, p, te_s),
    }


# ---------------- dedicated hERG head-to-head ----------------
def herg_morgan_xgb(ep_data, lm_auroc_for_compare):
    """Morgan-FP + XGBoost hERG classifier (TDC-leaderboard recipe) on hERG_Karim. Head-to-head
    vs the ChemBERTa LM AUROC on the same random-split test."""
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem
    def fp_matrix(smis):
        X = np.zeros((len(smis), 2048), dtype=np.float32)
        for i, s in enumerate(smis):
            m = Chem.MolFromSmiles(s)
            if m is None:
                continue
            bv = AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048)
            arr = np.zeros((2048,), dtype=np.int8)
            from rdkit import DataStructs
            DataStructs.ConvertToNumpyArray(bv, arr)
            X[i] = arr
        return X
    rnd = ep_data["random"]
    tr, te = rnd["train"], rnd["test"]
    Xtr = fp_matrix([r["smiles"] for r in tr]); ytr = np.array([r["y"] for r in tr])
    Xte = fp_matrix([r["smiles"] for r in te]); yte = np.array([r["y"] for r in te])
    out = {"recipe": "Morgan2048-FP + XGBoost", "n_train": len(ytr), "n_test": len(yte),
           "chemberta_lm_auroc_for_compare": lm_auroc_for_compare}
    try:
        import xgboost as xgb
        pos = max(int((ytr == 1).sum()), 1); neg = max(int((ytr == 0).sum()), 1)
        clf = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                                subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
                                scale_pos_weight=neg / pos, n_jobs=4)
        clf.fit(Xtr, ytr)
        p = clf.predict_proba(Xte)[:, 1]
        au = auroc(yte, p)
        out["xgb_auroc"] = round(au, 4) if au == au else None
        out["calibration"] = calibration(yte, p)
        if lm_auroc_for_compare is not None and au == au:
            out["delta_xgb_minus_lm"] = round(au - lm_auroc_for_compare, 4)
            out["verdict"] = ("dedicated FP+XGB beats LM on hERG" if au > lm_auroc_for_compare
                              else "ChemBERTa LM holds vs dedicated FP+XGB")
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# ---------------- ADMET-AI cross-check ----------------
def admet_ai_crosscheck():
    """Best-effort: ADMET-AI predictions on the TDC test sets it covers (DILI, BBB_Martins)."""
    from admet_ai import ADMETModel
    model = ADMETModel()
    out = {}
    for ep in ["DILI", "BBB_Martins"]:
        try:
            grp, ds = ENDPOINTS[ep]
            if grp == "ADME":
                from tdc.single_pred import ADME as Loader
            else:
                from tdc.single_pred import Tox as Loader
            split = Loader(name=ds).get_split(method="random", seed=42)["test"]
            smis = [str(s) for s in split["Drug"].tolist()]
            yte = np.array([int(round(float(y))) for y in split["Y"].tolist()])
            preds = model.predict(smiles=smis)  # DataFrame indexed by smiles
            # ADMET-AI emits many columns; match the closest endpoint column by name.
            cols = list(preds.columns)
            key = next((c for c in cols if ep.split("_")[0].lower() in c.lower()), None)
            if key is None:
                out[ep] = {"skip": f"no ADMET-AI column matched {ep}; cols={cols[:8]}..."}
                continue
            s = preds[key].to_numpy(dtype=float)
            au = auroc(yte, s)
            out[ep] = {"matched_column": key, "n_test": len(yte),
                       "auroc": round(au, 4) if au == au else None}
        except Exception as e:
            out[ep] = {"error": f"{type(e).__name__}: {e}"}
    return out


def main():
    t0 = datetime.now()
    import torch
    device = "cpu" if FORCE_CPU or not torch.cuda.is_available() else "cuda"
    print(f"[start] device={device} max_per_ep={MAX_PER_EP}", flush=True)

    res = {"test": "derisking_deep_characterization (Tracks 4/5)",
           "timestamp": t0.isoformat(),
           "phase": "2 - de-risking operating envelope",
           "baselines": {"molformer_xl_bbbp": 0.889, "mammal_bbbp": 0.833,
                         "chemberta2_herg": 0.726, "admet_ai_dili": 0.83},
           "dims": ["random_split_auroc", "scaffold_held_out_auroc", "applicability_domain",
                    "calibration", "failure_modes"],
           "endpoints_loaded": {}, "models": {}, "herg_head_to_head": {}, "admet_ai_crosscheck": {}}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    def flush():
        json.dump(res, open(OUT, "w"), indent=2, default=str)

    # 1) Load all TDC endpoints once (cached on-instance), guarded individually.
    ep_cache = {}
    for ep in ENDPOINTS:
        try:
            ep_cache[ep] = load_tdc_endpoint(ep, MAX_PER_EP)
            rnd = ep_cache[ep]["random"]
            res["endpoints_loaded"][ep] = {"n_train": len(rnd["train"]), "n_test": len(rnd["test"]),
                                           "scaffold_split": "scaffold" in ep_cache[ep] and "train" in ep_cache[ep].get("scaffold", {})}
            print(f"[tdc] {ep}: {len(rnd['train'])} train / {len(rnd['test'])} test", flush=True)
        except Exception as e:
            res["endpoints_loaded"][ep] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] tdc {ep}: {e}\n{traceback.format_exc()[:600]}", flush=True)
        flush()

    # 2) Each LM model x endpoint, independently guarded; rewrite JSON after each.
    chemberta_herg_auroc = None
    for mname, repo in MODELS:
        res["models"][mname] = {}
        try:
            embed, model, tok = make_embedder(repo, device)
        except Exception as e:
            res["models"][mname] = {"status": "MODEL_LOAD_FAILED", "error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] load {mname}: {e}\n{traceback.format_exc()[:600]}", flush=True)
            flush(); continue
        for ep in ENDPOINTS:
            if ep not in ep_cache or "random" not in ep_cache[ep]:
                res["models"][mname][ep] = {"skip": "endpoint not loaded"}; flush(); continue
            try:
                res["models"][mname][ep] = eval_lm_on_endpoint(embed, ep_cache[ep])
                r = res["models"][mname][ep]
                if mname == "ChemBERTa-2" and ep == "hERG_Karim":
                    chemberta_herg_auroc = r.get("random_split_auroc")
                print(f"  {mname}/{ep}: rand {r.get('random_split_auroc')} | "
                      f"scaffold {r.get('scaffold_held_out_auroc')} | gap {r.get('generalization_gap')} | "
                      f"brier {r['calibration']['brier']}", flush=True)
            except Exception as e:
                res["models"][mname][ep] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}"}
                print(f"  {mname}/{ep} FAILED: {str(e)[:160]}\n{traceback.format_exc()[:500]}", flush=True)
            flush()
        try:
            del model, tok
            import gc; gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
        except Exception:
            pass

    # 3) Dedicated hERG head-to-head (Morgan-FP + XGBoost vs ChemBERTa LM).
    try:
        if "hERG_Karim" in ep_cache and "random" in ep_cache["hERG_Karim"]:
            res["herg_head_to_head"] = herg_morgan_xgb(ep_cache["hERG_Karim"], chemberta_herg_auroc)
            print(f"[herg-h2h] {res['herg_head_to_head'].get('xgb_auroc')} vs LM {chemberta_herg_auroc} "
                  f"-> {res['herg_head_to_head'].get('verdict')}", flush=True)
        else:
            res["herg_head_to_head"] = {"skip": "hERG_Karim not loaded"}
    except Exception as e:
        res["herg_head_to_head"] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] herg-h2h: {e}\n{traceback.format_exc()[:600]}", flush=True)
    flush()

    # 4) ADMET-AI cross-check (best-effort; allowed to be absent).
    if RUN_ADMET_AI:
        try:
            res["admet_ai_crosscheck"] = admet_ai_crosscheck()
            print(f"[admet-ai] {res['admet_ai_crosscheck']}", flush=True)
        except Exception as e:
            res["admet_ai_crosscheck"] = {"status": "UNAVAILABLE", "error": f"{type(e).__name__}: {e}"}
            print(f"[skip] admet-ai unavailable: {str(e)[:160]}", flush=True)
    else:
        res["admet_ai_crosscheck"] = {"skip": "RUN_ADMET_AI=0"}
    flush()

    res["elapsed_s"] = round((datetime.now() - t0).total_seconds(), 1)
    flush()
    print(f"[done] {res['elapsed_s']}s -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
