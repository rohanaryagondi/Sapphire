#!/usr/bin/env python3
"""Rescue the data-poor CNS channels via PubChem qHTS — the large NON-ChEMBL screens the scout
surfaced. Trains per-target binder models for channels ChEMBL alone couldn't fine-tune, in the
same bundle format as cns_pertarget_finetune.py, so the Explorer serves them LIVE. Local, $0, headless.

Targets (confirmed large non-ChEMBL qHTS):
  KCNQ2 / Kv7.2  — AID 2258  (thallium-flux opener screen; epilepsy channel)
  CACNA1H / Cav3.2 — AID 449739 (MLPCN primary, 104,742 cpds / ~4,230 active; T-type, epilepsy/pain)
Negatives = the assay's own measured INACTIVES (real non-binders, better than decoys), sampled.
(Nav1.1/SCN1A + Nav1.6/SCN8A have NO large non-ChEMBL screen -> remain Quiver-data targets, honestly.)
"""
import csv, io, json, os, time, urllib.request
import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, DataStructs
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
import joblib
RDLogger.DisableLog("rdApp.*")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MODELS = os.path.join(REPO, "models", "cns_pertarget")
CACHE = os.path.join(REPO, "data", "pubchem_qhts_cache")
os.makedirs(OUT_MODELS, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# (gene, uniprot, family, AID, max_inactives_to_sample). AIDs verified to serve a real
# compound table with Active/Inactive outcomes (AID 2258 was a summary assay -> 404; use the
# large MLPCN primary screens instead).
TARGETS = [
    ("KCNQ2", "O43526", "kv", 2156, 6000),    # Kv7.2 opener screen: 3,407 active / 302,271 inactive
    ("CACNA1H", "O95180", "cav", 449739, 6000),  # Cav3.2 (T-type): 4,230 active / 100,512 inactive
]


def http(url, tries=5, timeout=90):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quiver-qhts/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if a == tries - 1:
                print(f"[warn] {url[:70]}: {e}"); return None
            time.sleep(2.0 * (a + 1))
    return None


def pull_assay(aid, max_inactives):
    """Return (active_cids, inactive_cids) from the concise CSV, cached."""
    cf = os.path.join(CACHE, f"aid{aid}_concise.csv")
    txt = open(cf).read() if os.path.exists(cf) else http(f"{PUG}/assay/aid/{aid}/concise/CSV")
    if not txt:
        return [], []
    if not os.path.exists(cf):
        open(cf, "w").write(txt)
    rdr = csv.DictReader(io.StringIO(txt))
    cidcol = next((c for c in rdr.fieldnames if c.strip().upper() == "CID"), None)
    outcol = next((c for c in rdr.fieldnames if "OUTCOME" in c.upper()), None)
    if not cidcol or not outcol:
        print(f"[warn] aid{aid}: cols {rdr.fieldnames[:6]}"); return [], []
    act, inact = [], []
    for row in rdr:
        cid = (row.get(cidcol) or "").strip()
        out = (row.get(outcol) or "").strip().lower()
        if not cid:
            continue
        if out == "active":
            act.append(cid)
        elif out == "inactive":
            inact.append(cid)
    # sample inactives
    if len(inact) > max_inactives:
        rng = np.random.RandomState(0)
        inact = [inact[i] for i in rng.choice(len(inact), max_inactives, replace=False)]
    return act, inact


def cids_to_smiles(cids):
    """Batch CID -> SMILES (PubChem rename: isomeric=SMILES). Cached per call set is not needed
    (assay cache covers re-runs of the CID list)."""
    out = {}
    B = 150
    for i in range(0, len(cids), B):
        batch = cids[i:i + B]
        txt = http(f"{PUG}/compound/cid/{','.join(batch)}/property/SMILES/CSV")
        if not txt:
            txt = http(f"{PUG}/compound/cid/{','.join(batch)}/property/ConnectivitySMILES/CSV")
        if not txt:
            continue
        rdr = csv.DictReader(io.StringIO(txt))
        smicol = next((c for c in rdr.fieldnames if "SMILES" in c.upper()), None)
        for row in rdr:
            cid = (row.get("CID") or "").strip()
            smi = (row.get(smicol) or "").strip() if smicol else ""
            if cid and smi:
                out[cid] = smi
        time.sleep(0.25)
        if i % 1500 == 0:
            print(f"    smiles {i}/{len(cids)} ({len(out)} resolved)")
    return out


def fp_bv(smi):
    m = Chem.MolFromSmiles(smi)
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None


def npfp(bv):
    a = np.zeros((2048,), dtype=np.int8); DataStructs.ConvertToNumpyArray(bv, a); return a


def scaf(smi):
    m = Chem.MolFromSmiles(smi)
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m) or smi
    except Exception:
        return smi


def main():
    summary = {"source": "PubChem qHTS (non-ChEMBL); negatives = assay inactives", "targets": {}}
    for gene, uni, fam, aid, maxin in TARGETS:
        print(f"=== {gene} ({fam}) AID {aid} ===")
        act_cids, inact_cids = pull_assay(aid, maxin)
        print(f"  assay: {len(act_cids)} active, {len(inact_cids)} inactive CIDs")
        if len(act_cids) < 30:
            summary["targets"][gene] = {"status": "too_few_actives", "n_active": len(act_cids)}
            continue
        smi = cids_to_smiles(act_cids + inact_cids)
        X, y, grp, act_bvs = [], [], [], []
        for cid in act_cids:
            s = smi.get(cid); bv = fp_bv(s) if s else None
            if bv is not None:
                X.append(npfp(bv)); y.append(1); grp.append(scaf(s)); act_bvs.append(bv)
        for cid in inact_cids:
            s = smi.get(cid); bv = fp_bv(s) if s else None
            if bv is not None:
                X.append(npfp(bv)); y.append(0); grp.append(scaf(s))
        X = np.array(X); y = np.array(y); grp = np.array(grp)
        npos, nneg = int(y.sum()), int((y == 0).sum())
        print(f"  featurized: {npos} active / {nneg} inactive")
        if npos < 30 or nneg < 30:
            summary["targets"][gene] = {"status": "too_few_after_featurize", "n_pos": npos, "n_neg": nneg}
            continue
        aurocs = []
        ng = len(set(grp))
        if ng >= 3:
            for tr, te in GroupKFold(n_splits=min(5, ng)).split(X, y, grp):
                if len(set(y[tr])) < 2 or len(set(y[te])) < 2:
                    continue
                c = HistGradientBoostingClassifier(random_state=0); c.fit(X[tr], y[tr])
                aurocs.append(roc_auc_score(y[te], c.predict_proba(X[te])[:, 1]))
        cv = round(float(np.mean(aurocs)), 4) if aurocs else None
        clf = HistGradientBoostingClassifier(random_state=0); clf.fit(X, y)
        bundle = {"clf": clf, "train_active_fps": act_bvs[:1500], "fp_radius": 2, "fp_bits": 2048,
                  "gene": gene, "uniprot": uni, "family": fam, "source": f"PubChem AID {aid}",
                  "n_pos": npos, "n_neg": nneg, "scaffold_cv_auroc": cv}
        joblib.dump(bundle, os.path.join(OUT_MODELS, f"{gene}.joblib"))
        summary["targets"][gene] = {"status": "trained", "uniprot": uni, "family": fam,
                                    "source": f"PubChem AID {aid}", "n_pos": npos, "n_neg": nneg,
                                    "scaffold_cv_auroc": cv, "model": f"models/cns_pertarget/{gene}.joblib"}
        print(f"  [train] {gene}: scaffold-CV AUROC={cv} -> saved")
    json.dump(summary, open(os.path.join(REPO, "results", "pubchem_qhts_finetune_result.json"), "w"), indent=2)
    print("\nwrote results/pubchem_qhts_finetune_result.json")
    print("trained:", [g for g, t in summary["targets"].items() if t.get("status") == "trained"])


if __name__ == "__main__":
    main()
