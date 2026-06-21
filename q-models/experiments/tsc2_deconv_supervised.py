#!/usr/bin/env python3
"""Supervised PKM2-vs-PPARD deconvolution of Ben's TSC2 screen hits — local, headless, $0.

Zero-shot BALM/PLAPT FAILED to deconvolve which target Ben's TSC2-Optopatch hits bind
(PKM2 0.50 / PPARD 0.53, controls outscored binders; results/tsc2_deconv_characterization.md).
This applies the SUPERVISED per-target approach that works everywhere else in the campaign
(trunc_test 0.92, ion-channel fine-tune 0.98): train a per-target binder classifier from ChEMBL
(Morgan-FP + GradientBoosting — per-target, the ligand FP does the discrimination), validate by
Murcko scaffold-split AUROC, then score the 9 panel compounds -> P(PKM2), P(PPARD).

Targets: PKM2 = CHEMBL2107 (P14618); PPARD = CHEMBL3979 (Q03181). ChEMBL activity REST (headless;
status.json is down but the data endpoint works). RDKit + sklearn, CPU, no AWS.

Output: results/tsc2_deconv_supervised_result.json + console summary.
"""
import csv, json, os, time, urllib.request, urllib.error
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = json.load(open(os.path.join(REPO, "aws", "tsc2_deconv_panel.json")))
TARGETS = {"PKM2": "CHEMBL2107", "PPARD": "CHEMBL3979"}
BASE = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
ACTIVE_PCHEMBL, INACTIVE_PCHEMBL = 6.0, 5.0
MAX_RECORDS = 4000  # per target cap


def fetch(url, tries=4, timeout=30):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "quiver-tsc2/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if a == tries - 1:
                print(f"[warn] give up {url[:80]}: {e}"); return None
            time.sleep(2.0 * (a + 1))
    return None


def pull_target(chembl_id):
    """Return {canonical_smiles: best_pchembl} for a target (max pchembl per compound)."""
    out = {}
    url = (f"{BASE}?target_chembl_id={chembl_id}&pchembl_value__isnull=false"
           f"&limit=1000&offset=0")
    n = 0
    while url and n < MAX_RECORDS:
        d = fetch(url)
        if not d:
            break
        for a in d.get("activities", []):
            smi = a.get("canonical_smiles"); pv = a.get("pchembl_value")
            if not smi or pv is None:
                continue
            try:
                pv = float(pv)
            except (TypeError, ValueError):
                continue
            out[smi] = max(out.get(smi, -1), pv)
            n += 1
        nxt = d.get("page_meta", {}).get("next")
        url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
        time.sleep(0.2)
    return out


def fp(smiles):
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    bv = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
    arr = np.zeros((2048,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(bv, arr)
    return arr


def scaffold(smiles):
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return smiles
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) or smiles
    except Exception:
        return smiles


def main():
    print("=== pulling ChEMBL PKM2 + PPARD ===")
    raw = {}
    for name, cid in TARGETS.items():
        d = pull_target(cid)
        raw[name] = d
        nact = sum(1 for v in d.values() if v >= ACTIVE_PCHEMBL)
        ninact = sum(1 for v in d.values() if v <= INACTIVE_PCHEMBL)
        print(f"[chembl] {name} ({cid}): {len(d)} cpds | actives>={ACTIVE_PCHEMBL}: {nact} | inactives<={INACTIVE_PCHEMBL}: {ninact}")

    # Build per-target binary datasets. Negatives = this target's inactives
    # + the OTHER target's actives (PKM2 & PPARD are unrelated -> cross-actives are
    # near-certain non-binders) -> the classifier learns to DISCRIMINATE the targets,
    # which is exactly deconvolution.
    results = {"targets": TARGETS, "active_pchembl": ACTIVE_PCHEMBL,
               "n_raw": {k: len(v) for k, v in raw.items()}, "models": {}, "panel_scores": {}}
    models = {}
    for name in TARGETS:
        other = "PPARD" if name == "PKM2" else "PKM2"
        pos = [s for s, v in raw[name].items() if v >= ACTIVE_PCHEMBL]
        neg = [s for s, v in raw[name].items() if v <= INACTIVE_PCHEMBL]
        cross = [s for s, v in raw[other].items() if v >= ACTIVE_PCHEMBL
                 and s not in raw[name]]  # other-target actives not measured on this target
        neg_all = list(dict.fromkeys(neg + cross))
        # featurize
        X, y, groups = [], [], []
        for s in pos:
            f = fp(s)
            if f is not None:
                X.append(f); y.append(1); groups.append(scaffold(s))
        for s in neg_all:
            f = fp(s)
            if f is not None:
                X.append(f); y.append(0); groups.append(scaffold(s))
        X = np.array(X); y = np.array(y); groups = np.array(groups)
        npos, nneg = int(y.sum()), int((y == 0).sum())
        print(f"[model {name}] pos={npos} neg={nneg} (inact {len(neg)} + cross {len(cross)})")
        # scaffold-split CV AUROC
        aurocs = []
        if npos >= 10 and nneg >= 10:
            ngrp = len(set(groups))
            nsplits = min(5, ngrp)
            gkf = GroupKFold(n_splits=nsplits)
            for tr, te in gkf.split(X, y, groups):
                if len(set(y[tr])) < 2 or len(set(y[te])) < 2:
                    continue
                clf = GradientBoostingClassifier(random_state=0)
                clf.fit(X[tr], y[tr])
                p = clf.predict_proba(X[te])[:, 1]
                aurocs.append(roc_auc_score(y[te], p))
        cv_auroc = float(np.mean(aurocs)) if aurocs else None
        # fit final model on all data for panel scoring
        clf = GradientBoostingClassifier(random_state=0)
        clf.fit(X, y)
        models[name] = clf
        results["models"][name] = {"n_pos": npos, "n_neg": nneg,
                                   "n_inactives": len(neg), "n_cross_decoys": len(cross),
                                   "scaffold_cv_auroc": cv_auroc, "cv_folds": len(aurocs)}
        print(f"[model {name}] scaffold-split CV AUROC = {cv_auroc} ({len(aurocs)} folds)")

    # Score the 9 panel compounds
    print("\n=== panel deconvolution ===")
    rows = []
    for c in PANEL["compounds"]:
        f = fp(c["smiles"])
        if f is None:
            continue
        ppkm = float(models["PKM2"].predict_proba([f])[0, 1])
        pppar = float(models["PPARD"].predict_proba([f])[0, 1])
        row = {"qs_id": c["qs_id"], "name": c["name"], "role": c.get("role"),
               "true_PKM2": c.get("binds_PKM2"), "true_PPARD": c.get("binds_PPARD"),
               "P_PKM2": round(ppkm, 3), "P_PPARD": round(pppar, 3)}
        rows.append(row)
        print(f"  {c['name']:26s} true(PKM2/PPARD)={c.get('binds_PKM2')}/{c.get('binds_PPARD')}  "
              f"P_PKM2={ppkm:.3f}  P_PPARD={pppar:.3f}")
    results["panel_scores"] = rows

    # Panel-level AUROC: can the PKM2 model rank true PKM2-binders above non-binders (n is tiny)?
    def panel_auroc(target_key, pkey):
        ys = [r["true_" + target_key] for r in rows if r["true_" + target_key] is not None]
        ss = [r[pkey] for r in rows if r["true_" + target_key] is not None]
        if len(set(ys)) < 2:
            return None
        return round(float(roc_auc_score(ys, ss)), 3)
    results["panel_auroc"] = {"PKM2": panel_auroc("PKM2", "P_PKM2"),
                              "PPARD": panel_auroc("PPARD", "P_PPARD")}
    print("\npanel AUROC (supervised):", results["panel_auroc"],
          "| zero-shot BALM/PLAPT was PKM2 0.50/0.40, PPARD 0.53/0.67")

    out = os.path.join(REPO, "results", "tsc2_deconv_supervised_result.json")
    json.dump(results, open(out, "w"), indent=2)
    print(f"\n=== wrote {out} ===")


if __name__ == "__main__":
    main()
