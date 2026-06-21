"""CardioGenAI tri-channel cardiac-blockade characterization (Track 5 tox, overnight AWS).

CardioGenAI (Kyro et al., J. Cheminformatics 2025; MIT) ships three DISCRIMINATIVE
cardiac ion-channel classifiers -- hERG, NaV1.5, CaV1.2 -- built on a fused
graph(GAT) + Morgan-FP + bidirectional-SMILES-transformer-embedding representation.
Our current Track-5 cardiac gate is single-channel (hERG only: FP+XGBoost 0.89,
ChemBERTa-LM 0.815). CardioGenAI adds NaV1.5 + CaV1.2 channels. The Quiver angle:
run the Nav1.8 panel drugs through the NaV1.5 head -- does it flag the cardiac
off-target? That is the selectivity story (an Nav1.8 blocker that ALSO hits
cardiac NaV1.5 is the dangerous one).

============================ VERIFIED REPO API ============================
Repo:    https://github.com/gregory-kyro/CardioGenAI   (commit: main)
License: MIT
Paper:   https://doi.org/10.1186/s13321-025-00976-8

WEIGHTS (all discriminative .pt files are COMMITTED IN THE REPO -- no download
needed for scoring):
  model_parameters/discriminative_model_parameters/
      hERG_Classification_parameters.pt  Nav_Classification_parameters.pt  Cav_Classification_parameters.pt
      hERG_Regression_parameters.pt      Nav_Regression_parameters.pt      Cav_Regression_parameters.pt
  model_parameters/transformer_model_parameters/Bidirectional_Transformer_parameters.pt   (committed)

REQUIRED DOWNLOAD (Google Drive, gdown) -- the ONE external file:
  data/prepared_transformer_datasets/prepared_transformer_data.csv   (gdown id 1l2Osk7zFj4rTyrjAi7EJ1GMrsYMbcRHI)
  WHY: src/Transformer.py Transformer_Dataset builds a DATA-DEPENDENT char-level
  vocab by sorting the unique regex tokens found in the CSV's "SMILES" column
  (stoi = {ch:i for i,ch in enumerate(sorted(special|chars))}). The trained
  embedding rows are tied to THAT exact index order, so we MUST use the official
  full CSV -- a substitute/subset CSV would give a wrong vocab->index mapping and
  silently corrupt every embedding. (We do NOT need the autoregressive transformer
  or train_hERG.h5; those are only for the generative re-engineering framework.)

EXACT LOAD + PREDICT API (src/Discriminator.py, verified from source):
  from src.Discriminator import predict_cardiac_ion_channel_activity
  df = predict_cardiac_ion_channel_activity(
           input_data,                       # str SMILES | list[str] | path to .h5
           prediction_type="classification", # 'classification' -> sigmoid P(blocker); 'regression' -> pIC50
           predict_hERG=True, predict_Nav=True, predict_Cav=True,
           device="gpu",                     # 'gpu' or 'cpu'
           save_path=...)                    # writes results/.../predictions.json
  -> returns a pandas.DataFrame with columns ["smiles", "hERG", "NaV1.5", "CaV1.2"]
     (only the requested channels appear). Internally:
       load_discriminative_model(params, device): Discriminator_Model(n_gat_heads=1,
         dropout=0.5, batch_norm=True); torch.load(params, map_location=device);
         load_state_dict(d["model_state_dict"], strict=False); .eval()
       features = graph(get_graph_features) + fingerprint(get_fingerprint_features)
         + transformer(Transformer_Feature_Extractor(bidir_params, training_data=CSV).extract_features)
       classification path applies torch.sigmoid to logits -> probability in [0,1].

GOTCHAS baked in:
  * env: python 3.11, pytorch 2.1.0 + cu121, pyg(torch-geometric) 2.4.0, rdkit 2023.03.3,
    numpy 1.26 (so numpy<2 is automatic), gdown, transformers, xgboost. We rebuild this
    in a venv (conda-activate does NOT work in userdata) -- see userdata .sh.
  * .pt checkpoints are torch state-dicts -> torch>=2.1 loads them fine (these were
    saved as plain dicts; we still install a torch>=2.2 so torch.load weights_only
    default is satisfied for the .pt state dicts).
  * NaV1.5 head probability is OUR P(cardiac-Nav-block) signal -- distinct from
    the Nav1.8 (neuronal) binding the panel labels were built for. That separation
    is the selectivity readout, not a contradiction.
==========================================================================

Analyses (every section independently guarded so one failure banks the rest):
  A. TDC hERG_Karim head-to-head: AUROC of the CardioGenAI hERG head on the scaffold-split
     TEST set vs our baselines (FP-XGBoost 0.89, ChemBERTa-LM 0.815). Per-channel we also
     score NaV1.5/CaV1.2 on the same compounds (no labels -> report score distribution only).
  B. Calibration of the hERG head on TDC test: Brier + reliability bins (is the probability
     trustworthy, or just a ranker?).
  C. Applicability domain: AUROC/accuracy of the hERG head stratified by max-Tanimoto-to-train
     band (far/OOD <0.3, mid, near) -- where does it silently degrade?
  D. QUIVER SELECTIVITY (the key angle): run the Nav1.8-panel binders
     (suzetrigine, lidocaine, mexiletine, ranolazine, A-803467, carbamazepine, lacosamide)
     through ALL THREE heads. Does the NaV1.5 head flag the cardiac off-target? Rank/separate.
  E. Quiver panel discrimination: per-channel AUROC of each head as a binder/decoy ranker on
     our Nav1.8 + mTOR panels (sanity: a cardiac head should NOT cleanly separate mTOR binders).
"""
from __future__ import annotations
import json, os, sys, traceback
from pathlib import Path
import numpy as np

DEVICE = "gpu" if os.environ.get("FORCE_CPU") != "1" else "cpu"   # CardioGenAI API wants 'gpu'/'cpu'
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/cardiogenai_out/cardiogenai_result.json"))
CG_DIR = Path(os.environ.get("CG_DIR", "/opt/CardioGenAI"))
MAX_TDC = int(os.environ.get("MAX_TDC", "4000"))   # cap TDC test scoring (graph+FP+transformer fwd is slow)

CHANNELS = ["hERG", "NaV1.5", "CaV1.2"]
# Nav1.8-panel drugs to push through the NaV1.5 cardiac head (the selectivity story).
NAV_SELECTIVITY_DRUGS = {"suzetrigine", "lidocaine", "mexiletine", "ranolazine",
                         "A-803467", "carbamazepine", "lacosamide"}


# ---------------- metrics (self-contained; no sklearn dependency for core) ----------------
def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0 or len(y) < 3:
        return None
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


# ---------------- rdkit helpers (numpy<2 + rdkit 2023.03.3) ----------------
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


# ---------------- CardioGenAI loader (verified API) ----------------
class CardioGenAI:
    """Thin wrapper around src.Discriminator.predict_cardiac_ion_channel_activity.

    Batches a list of SMILES through all 3 classification heads at once and returns
    {channel: np.array(P_blocker)} aligned to the input order. NaN-fills any SMILES the
    pipeline rejects so caller alignment is preserved.
    """

    def __init__(self):
        sys.path.insert(0, str(CG_DIR))
        os.chdir(CG_DIR)   # the API uses RELATIVE default paths for the committed .pt files + CSV
        from src.Discriminator import predict_cardiac_ion_channel_activity  # verified import
        self._predict = predict_cardiac_ion_channel_activity
        self._scratch = CG_DIR / "results" / "discriminative_results"
        self._scratch.mkdir(parents=True, exist_ok=True)

    def predict(self, smiles_list, prediction_type="classification"):
        smiles_list = list(smiles_list)
        save_path = str(self._scratch / "predictions.json")
        df = self._predict(
            input_data=smiles_list,
            prediction_type=prediction_type,
            predict_hERG=True, predict_Nav=True, predict_Cav=True,
            device=DEVICE,
            save_path=save_path,
        )
        # df has columns ["smiles", "hERG", "NaV1.5", "CaV1.2"] (verified). Map back by SMILES,
        # tolerant of column-name drift (e.g. 'Nav'/'NaV1.5').
        import pandas as pd  # noqa: F401
        cols = {c.lower(): c for c in df.columns}
        def pick(*names):
            for nm in names:
                if nm.lower() in cols:
                    return cols[nm.lower()]
            return None
        chan_col = {"hERG": pick("hERG", "herg"),
                    "NaV1.5": pick("NaV1.5", "Nav", "nav1.5", "nav"),
                    "CaV1.2": pick("CaV1.2", "Cav", "cav1.2", "cav")}
        smi_col = pick("smiles", "Smiles", "SMILES") or df.columns[0]
        by_smi = {str(r[smi_col]): r for _, r in df.iterrows()}
        out = {ch: np.full(len(smiles_list), np.nan) for ch in CHANNELS}
        for i, s in enumerate(smiles_list):
            row = by_smi.get(str(s))
            if row is None:
                continue
            for ch in CHANNELS:
                col = chan_col[ch]
                if col is not None:
                    try:
                        out[ch][i] = float(row[col])
                    except Exception:
                        pass
        return out


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1000]}", flush=True)


# ---------------- TDC hERG_Karim (scaffold split) ----------------
def load_tdc_herg(max_test):
    """Return ({'train':[{smiles,y}], 'test':[...]} for scaffold split, plus random test for AD).
    hERG_Karim Y is binary (1 = blocker)."""
    from tdc.single_pred import Tox
    data = Tox(name="hERG_Karim")
    out = {}
    sc = data.get_split(method="scaffold", seed=42)

    def rows(df):
        r = []
        for s, y in zip(df["Drug"], df["Y"]):
            try:
                r.append({"smiles": str(s), "y": int(round(float(y)))})
            except Exception:
                continue
        return r
    tr = rows(sc["train"]); te = rows(sc["test"])
    if max_test and len(te) > max_test:
        # keep class balance when capping
        pos = [x for x in te if x["y"] == 1]; neg = [x for x in te if x["y"] == 0]
        k = max_test // 2
        te = pos[:k] + neg[:k]
    out["train"] = tr; out["test"] = te
    return out


def main():
    panels = json.loads(PANELS.read_text())
    cg = CardioGenAI()
    R = {}

    # ---- shared: load + score TDC scaffold test once (reused by A/B/C) ----
    tdc_state = {}

    def tdc_score():
        d = load_tdc_herg(MAX_TDC)
        te_smi = [r["smiles"] for r in d["test"]]
        te_y = [r["y"] for r in d["test"]]
        preds = cg.predict(te_smi, "classification")           # {channel: P_blocker}
        tdc_state["d"] = d; tdc_state["te_smi"] = te_smi
        tdc_state["te_y"] = te_y; tdc_state["preds"] = preds
        return d, te_smi, te_y, preds

    # A. TDC hERG_Karim head-to-head AUROC (+ NaV1.5/CaV1.2 score dists on same compounds)
    def a_tdc_auroc():
        d, te_smi, te_y, preds = tdc_score()
        herg_p = preds["hERG"]
        valid = ~np.isnan(herg_p)
        au = auroc(np.asarray(te_y)[valid], herg_p[valid])
        chan = {}
        for ch in CHANNELS:
            p = preds[ch]; v = p[~np.isnan(p)]
            chan[ch] = {"n_scored": int(v.size),
                        "score_mean": round(float(v.mean()), 4) if v.size else None,
                        "score_std": round(float(v.std()), 4) if v.size else None}
        return {"dataset": "TDC hERG_Karim (scaffold split, seed=42)",
                "n_train": len(d["train"]), "n_test_scored": int(valid.sum()),
                "label_note": "Y=1 = hERG blocker (positive class)",
                "cardiogenai_hERG_auroc": round(au, 4) if au is not None else None,
                "baselines": {"FP_XGBoost": 0.89, "ChemBERTa_LM": 0.815},
                "delta_vs_FP_XGB": (round(au - 0.89, 4) if au is not None else None),
                "delta_vs_ChemBERTa": (round(au - 0.815, 4) if au is not None else None),
                "verdict": (None if au is None else
                            ("beats_FP_XGB" if au > 0.89 else
                             "between_ChemBERTa_and_FP_XGB" if au > 0.815 else "below_both")),
                "per_channel_score_dist": chan,
                "note": "hERG head is the labeled head-to-head; NaV1.5/CaV1.2 score dists are unlabeled context."}
    section(a_tdc_auroc, "A_tdc_herg_headtohead", R)

    # B. calibration of hERG head on TDC test
    def b_calibration():
        if "preds" not in tdc_state:
            tdc_score()
        p = tdc_state["preds"]["hERG"]; y = np.asarray(tdc_state["te_y"])
        v = ~np.isnan(p)
        if v.sum() < 10:
            return {"skip": "too few scored"}
        out = calibration(y[v], p[v], bins=5)
        out["note"] = "Brier + reliability of CardioGenAI hERG P(blocker) vs observed blocker rate on scaffold-test."
        return out
    section(b_calibration, "B_herg_calibration", R)

    # C. applicability domain: hERG AUROC by Tanimoto-to-train band
    def c_applicability():
        if "preds" not in tdc_state:
            tdc_score()
        d = tdc_state["d"]; te_smi = tdc_state["te_smi"]
        y = np.asarray(tdc_state["te_y"]); p = tdc_state["preds"]["hERG"]
        tr_fp = morgan([r["smiles"] for r in d["train"]])
        te_fp = morgan(te_smi)
        mt = max_tanimoto(te_fp, tr_fp)
        bands = []
        for lo, hi, lab in [(0.0, 0.3, "far/OOD"), (0.3, 0.5, "mid"), (0.5, 1.01, "near")]:
            m = (mt >= lo) & (mt < hi) & (~np.isnan(p))
            if m.sum() >= 10:
                pred = (p[m] >= 0.5).astype(int)
                acc = float((pred == y[m]).mean())
                au = auroc(y[m], p[m])
                bands.append({"band": lab, "tanimoto": f"{lo}-{hi}", "n": int(m.sum()),
                              "auroc": (round(au, 3) if au is not None else None),
                              "accuracy": round(acc, 3)})
        return {"mean_tanimoto_to_train": round(float(mt.mean()), 3),
                "frac_OOD_<0.3": round(float((mt < 0.3).mean()), 3), "bands": bands,
                "note": "If hERG AUROC holds in the far/OOD band, the head generalizes; if it collapses, it memorizes."}
    section(c_applicability, "C_applicability_domain", R)

    # D. QUIVER SELECTIVITY: Nav1.8-panel binders through all 3 heads.
    def d_nav_selectivity():
        nav = panels.get("nav18", {})
        comps = [c for c in nav.get("compounds", [])
                 if c["drug"] in NAV_SELECTIVITY_DRUGS or c.get("label") == 1]
        # dedup, keep order
        seen = set(); ordered = []
        for c in comps:
            if c["drug"] not in seen:
                seen.add(c["drug"]); ordered.append(c)
        smis = [c["smiles"] for c in ordered]
        preds = cg.predict(smis, "classification")
        rows = []
        for i, c in enumerate(ordered):
            rows.append({"drug": c["drug"], "label_nav18_binder": c.get("label"),
                         "P_hERG_block": (None if np.isnan(preds["hERG"][i]) else round(float(preds["hERG"][i]), 4)),
                         "P_NaV1.5_block": (None if np.isnan(preds["NaV1.5"][i]) else round(float(preds["NaV1.5"][i]), 4)),
                         "P_CaV1.2_block": (None if np.isnan(preds["CaV1.2"][i]) else round(float(preds["CaV1.2"][i]), 4))})
        nav15 = [r["P_NaV1.5_block"] for r in rows if r["P_NaV1.5_block"] is not None]
        flagged = [r["drug"] for r in rows if (r["P_NaV1.5_block"] or 0) >= 0.5]
        return {"n_drugs": len(rows), "rows": rows,
                "nav15_flagged_at_0.5": flagged,
                "nav15_mean": round(float(np.mean(nav15)), 4) if nav15 else None,
                "interpretation": ("Lidocaine/mexiletine/ranolazine are known class-Ib/late-Na cardiac NaV1.5 "
                                   "blockers -> high P_NaV1.5 is the CORRECT off-target flag. Suzetrigine "
                                   "(Nav1.8-selective by design) SHOULD score low on NaV1.5 if the head resolves "
                                   "the selectivity. This is the cardiac-off-target readout, not Nav1.8 binding."),
                "note": "NaV1.5 head = cardiac sodium channel; distinct from neuronal Nav1.8 the panel labels target."}
    section(d_nav_selectivity, "D_quiver_nav_selectivity", R)

    # E. per-channel AUROC of each head as binder/decoy ranker on Quiver panels (sanity)
    def e_panel_discrimination():
        out = {}
        for key, p in panels.items():
            comps = p["compounds"]
            smis = [c["smiles"] for c in comps]
            labs = [c["label"] for c in comps]
            preds = cg.predict(smis, "classification")
            ch_au = {}
            for ch in CHANNELS:
                sc = preds[ch]
                v = ~np.isnan(sc)
                au = auroc(np.asarray(labs)[v], sc[v]) if v.sum() >= 3 else None
                ch_au[ch] = round(au, 4) if au is not None else None
            out[key] = {"target": p["target"], "n": len(comps), "per_channel_auroc": ch_au}
        out["_note"] = ("These heads predict CARDIAC channel block, not Nav1.8/mTOR binding. High AUROC here "
                        "would mean the panel's binders happen to be cardiac-active; near-0.5 is the expected/clean "
                        "result for mTOR. Reported as a confound/sanity check, not a binding metric.")
        return out
    section(e_panel_discrimination, "E_quiver_panel_discrimination", R)

    payload = {"model": "CardioGenAI discriminative heads (hERG + NaV1.5 + CaV1.2; GAT+FP+SMILES-transformer)",
               "repo": "https://github.com/gregory-kyro/CardioGenAI", "license": "MIT",
               "prediction_type": "classification (sigmoid P_blocker)",
               "phase": "Track-5 tox tri-channel characterization",
               "baselines_herg": {"FP_XGBoost": 0.89, "ChemBERTa_LM": 0.815},
               "results": R}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    summ = {}
    a = R.get("A_tdc_herg_headtohead", {})
    if isinstance(a, dict):
        summ["herg_auroc"] = a.get("cardiogenai_hERG_auroc"); summ["herg_verdict"] = a.get("verdict")
    d = R.get("D_quiver_nav_selectivity", {})
    if isinstance(d, dict):
        summ["nav15_flagged"] = d.get("nav15_flagged_at_0.5")
    print(json.dumps(summ, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
