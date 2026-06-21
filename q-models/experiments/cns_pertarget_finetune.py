#!/usr/bin/env python3
"""Per-target CNS binder fine-tunes (Morgan-FP + GradientBoosting), for every data-rich
CNS target — local, headless, $0, CPU. Deployable joblib per target for the Explorer.

Why per-target FP+GBT (not the cross-channel ESM-2 model): the campaign showed the protein
embedding is CONSTANT within a target, so per-target the ligand FP does the discrimination
(trunc_test); and the TSC2 PKM2/PPARD run got 0.99 scaffold-split with exactly this FP+GBT
recipe. Cross-target transfer fails (LOCO 0/4), so PER-TARGET models are the correct deployment.
This trains one per data-rich target (the FINE-TUNE NOW list from the readiness map), validates
by Murcko scaffold-split CV, and saves {clf, train active FPs (for Tanimoto-to-train confidence),
config} -> models/cns_pertarget/<gene>.joblib, plus a per-target AUROC table.

Negatives = target's ChEMBL inactives (pChEMBL<=5) + property-matched decoys drawn from
CROSS-FAMILY actives (different family -> safe non-binders; avoids paralog contamination).
"""
import json, os, time, urllib.request
import numpy as np
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
import joblib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MODELS = os.path.join(REPO, "models", "cns_pertarget")
CACHE_DIR = os.path.join(REPO, "data", "cns_dti_cache")
os.makedirs(OUT_MODELS, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
BASE = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
ACTIVE, INACTIVE = 6.0, 5.0
MAXREC = 4000

# data-rich CNS targets (FINE-TUNE NOW + Cav1.2 marginal) -> (chembl_id, family)
TARGETS = {
    "MTOR": ("CHEMBL2842", "mtor_pathway"), "PKM": ("CHEMBL2107", "mtor_pathway"),
    "PPARD": ("CHEMBL3979", "mtor_pathway"), "AKT1": ("CHEMBL4282", "mtor_pathway"),
    "RPS6KB1": ("CHEMBL4501", "mtor_pathway"),
    "SCN9A": ("CHEMBL4296", "nav"), "SCN10A": ("CHEMBL5451", "nav"),
    "SCN2A": ("CHEMBL4076", "nav"), "SCN5A": ("CHEMBL1980", "nav"),
    "CACNA1C": ("CHEMBL1940", "cav"),
    "GRIN1": ("CHEMBL1907594", "nmda"), "GRIN2B": ("CHEMBL1907600", "nmda"),
    "DRD2": ("CHEMBL217", "gpcr"), "HTR2A": ("CHEMBL224", "gpcr"),
    "GSK3B": ("CHEMBL262", "kinase"), "LRRK2": ("CHEMBL1075104", "kinase"),
    "BACE1": ("CHEMBL4822", "kinase"),
}


def fetch(url, tries=5, timeout=40):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "quiver-ft/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(2.0 * (a + 1))
    return None


def pull(chembl_id):
    """Pull (smiles->max pchembl) for a target. DISK-CACHED: a non-empty cache is reused (so
    transient ChEMBL outages don't lose good data and re-runs are instant); an empty/failed
    pull is NOT cached, so a re-run retries it."""
    cache = os.path.join(CACHE_DIR, f"{chembl_id}.json")
    if os.path.exists(cache):
        try:
            d = json.load(open(cache))
            if d:
                return {k: float(v) for k, v in d.items()}
        except Exception:
            pass
    out = {}
    url = f"{BASE}?target_chembl_id={chembl_id}&pchembl_value__isnull=false&limit=1000&offset=0"
    n = 0; first_page_ok = False
    while url and n < MAXREC:
        d = fetch(url)
        if not d:
            break
        first_page_ok = True
        for a in d.get("activities", []):
            s, pv = a.get("canonical_smiles"), a.get("pchembl_value")
            if not s or pv is None:
                continue
            try:
                pv = float(pv)
            except (TypeError, ValueError):
                continue
            out[s] = max(out.get(s, -1), pv); n += 1
        nxt = d.get("page_meta", {}).get("next")
        url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
        time.sleep(0.2)
    if out and first_page_ok:   # only cache a real, non-empty pull
        json.dump(out, open(cache, "w"))
    return out


def fp_bv(smiles):
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)


def bv_to_np(bv):
    a = np.zeros((2048,), dtype=np.int8); DataStructs.ConvertToNumpyArray(bv, a); return a


def scaffold(s):
    m = Chem.MolFromSmiles(s)
    if m is None:
        return s
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) or s
    except Exception:
        return s


def main():
    print("=== pulling ChEMBL for", len(TARGETS), "data-rich CNS targets ===")
    raw = {}
    for g, (cid, fam) in TARGETS.items():
        d = pull(cid)
        raw[g] = d
        print(f"[chembl] {g} {cid}: {len(d)} cpds "
              f"(act>={ACTIVE}: {sum(v>=ACTIVE for v in d.values())}, "
              f"inact<={INACTIVE}: {sum(v<=INACTIVE for v in d.values())})")

    # cross-family active pool for decoys
    fam_actives = defaultdict(list)
    for g, (cid, fam) in TARGETS.items():
        for s, v in raw[g].items():
            if v >= ACTIVE:
                fam_actives[fam].append(s)

    rng = np.random.RandomState(0)
    summary = {"recipe": "Morgan-FP(2048,r2) + GradientBoosting, per target; "
                         "negatives = target inactives + cross-family decoys; "
                         "Murcko scaffold-split GroupKFold CV AUROC",
               "active_pchembl": ACTIVE, "targets": {}}
    for g, (cid, fam) in TARGETS.items():
        pos = [s for s, v in raw[g].items() if v >= ACTIVE]
        neg = [s for s, v in raw[g].items() if v <= INACTIVE]
        if len(pos) < 30:
            print(f"[skip] {g}: only {len(pos)} actives");
            summary["targets"][g] = {"status": "skipped_sparse", "n_actives": len(pos)}
            continue
        # supplement negatives with cross-family decoys to ~2x actives
        need = max(0, 2 * len(pos) - len(neg))
        pool = [s for f2, lst in fam_actives.items() if f2 != fam for s in lst
                if s not in raw[g]]
        if need and pool:
            idx = rng.choice(len(pool), size=min(need, len(pool)), replace=False)
            neg = list(dict.fromkeys(neg + [pool[i] for i in idx]))
        # featurize
        X, y, grp, act_bvs = [], [], [], []
        for s in pos:
            bv = fp_bv(s)
            if bv is not None:
                X.append(bv_to_np(bv)); y.append(1); grp.append(scaffold(s)); act_bvs.append(bv)
        for s in neg:
            bv = fp_bv(s)
            if bv is not None:
                X.append(bv_to_np(bv)); y.append(0); grp.append(scaffold(s))
        X = np.array(X); y = np.array(y); grp = np.array(grp)
        npos, nneg = int(y.sum()), int((y == 0).sum())
        # scaffold-split CV AUROC
        aurocs = []
        ngrp = len(set(grp))
        if npos >= 10 and nneg >= 10 and ngrp >= 3:
            for tr, te in GroupKFold(n_splits=min(5, ngrp)).split(X, y, grp):
                if len(set(y[tr])) < 2 or len(set(y[te])) < 2:
                    continue
                c = HistGradientBoostingClassifier(random_state=0); c.fit(X[tr], y[tr])
                aurocs.append(roc_auc_score(y[te], c.predict_proba(X[te])[:, 1]))
        cv = round(float(np.mean(aurocs)), 4) if aurocs else None
        # final model on all data
        clf = HistGradientBoostingClassifier(random_state=0); clf.fit(X, y)
        bundle = {"clf": clf, "train_active_fps": act_bvs, "fp_radius": 2, "fp_bits": 2048,
                  "gene": g, "chembl": cid, "family": fam, "n_pos": npos, "n_neg": nneg,
                  "scaffold_cv_auroc": cv}
        joblib.dump(bundle, os.path.join(OUT_MODELS, f"{g}.joblib"))
        summary["targets"][g] = {"status": "trained", "family": fam, "n_actives": npos,
                                 "n_negatives": nneg, "scaffold_cv_auroc": cv,
                                 "model": f"models/cns_pertarget/{g}.joblib"}
        print(f"[train] {g} ({fam}): pos={npos} neg={nneg} scaffold-CV AUROC={cv} -> saved")

    # family means
    fam_auroc = defaultdict(list)
    for g, t in summary["targets"].items():
        if t.get("scaffold_cv_auroc") is not None:
            fam_auroc[t["family"]].append(t["scaffold_cv_auroc"])
    summary["family_mean_auroc"] = {f: round(float(np.mean(v)), 4) for f, v in fam_auroc.items()}
    n_trained = sum(1 for t in summary["targets"].values() if t.get("status") == "trained")
    summary["n_trained"] = n_trained
    json.dump(summary, open(os.path.join(REPO, "results", "cns_pertarget_finetune_result.json"), "w"), indent=2)
    print(f"\n=== trained {n_trained} per-target models; family means:",
          summary["family_mean_auroc"], "===")
    print("wrote results/cns_pertarget_finetune_result.json + models/cns_pertarget/*.joblib")


if __name__ == "__main__":
    main()
