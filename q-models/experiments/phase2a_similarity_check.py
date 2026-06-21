"""Phase 2a — validate the hit-expansion step: are MAMMAL compound embeddings
chemically sensible for SMILES-similarity nearest-neighbor search?

Test: take known drug classes (members are structurally/functionally related).
Embed each with the base model. For each molecule, check whether its nearest
neighbor (by cosine) is the same class. Compare against the standard cheminformatics
baseline — Morgan fingerprint Tanimoto — and measure whether MAMMAL similarity
agrees with Tanimoto (Spearman over all pairs).

If MAMMAL neighbors are same-class at a rate comparable to fingerprints, the
expansion step is sound. If neighbors are random w.r.t. class, it isn't.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase2a_similarity_check.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

CLASSES = {
    "statin": ["atorvastatin", "simvastatin", "pravastatin", "rosuvastatin", "lovastatin"],
    "beta_blocker": ["propranolol", "atenolol", "metoprolol", "bisoprolol", "nadolol"],
    "ssri": ["fluoxetine", "sertraline", "paroxetine", "citalopram", "fluvoxamine"],
    "benzodiazepine": ["diazepam", "lorazepam", "alprazolam", "clonazepam", "midazolam"],
    "nsaid": ["ibuprofen", "naproxen", "ketoprofen", "diclofenac", "indomethacin"],
}


def pubchem_smiles(name):
    q = urllib.parse.quote(name)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q}/property/IsomericSMILES,CanonicalSMILES/JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return p.get("IsomericSMILES") or p.get("CanonicalSMILES") or p.get("SMILES")
    except Exception as e:
        print(f"  pubchem fail {name}: {e}")
        return None


def nn_same_class_rate(names, classes, sim):
    """sim: dict (i,j)->similarity. For each i, is argmax_j sim same class?"""
    n = len(names)
    correct = 0
    for i in range(n):
        best_j, best_s = None, -1e9
        for j in range(n):
            if i == j:
                continue
            s = sim[(min(i, j), max(i, j))]
            if s > best_s:
                best_s, best_j = s, j
        correct += int(classes[i] == classes[best_j])
    return correct / n


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    import torch
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
    from mammal_quiver.embed import load_base_model, embed

    names, classes, smiles = [], [], []
    for cls, members in CLASSES.items():
        for nm in members:
            smi = pubchem_smiles(nm)
            if smi:
                names.append(nm); classes.append(cls); smiles.append(smi)
    print(f"{len(names)} molecules across {len(set(classes))} classes")

    model, tok, dev = load_base_model()
    print(f"base model on {dev}; embedding ...")
    embs = [embed(model, tok, s, kind="smiles") for s in smiles]
    E = torch.stack(embs)  # (N,768), already L2-normalized

    # Morgan fingerprints
    fps = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(s), 2, nBits=2048) for s in smiles]

    n = len(names)
    mam_sim, tan_sim = {}, {}
    for i, j in combinations(range(n), 2):
        mam_sim[(i, j)] = float(E[i] @ E[j])
        tan_sim[(i, j)] = DataStructs.TanimotoSimilarity(fps[i], fps[j])

    mam_nn = nn_same_class_rate(names, classes, mam_sim)
    tan_nn = nn_same_class_rate(names, classes, tan_sim)

    # agreement between the two similarity measures (Spearman over all pairs)
    pairs = list(combinations(range(n), 2))
    mv = [mam_sim[p] for p in pairs]; tv = [tan_sim[p] for p in pairs]
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for k, i in enumerate(o): r[i] = k
        return r
    def pearson(x, y):
        m = len(x); mx = sum(x)/m; my = sum(y)/m
        cov = sum((a-mx)*(b-my) for a, b in zip(x, y))
        vx = sum((a-mx)**2 for a in x)**.5; vy = sum((b-my)**2 for b in y)**.5
        return cov/(vx*vy) if vx and vy else float("nan")
    rho = pearson(rank(mv), rank(tv))

    # same-class vs cross-class mean cosine (separation)
    same = [mam_sim[p] for p in pairs if classes[p[0]] == classes[p[1]]]
    cross = [mam_sim[p] for p in pairs if classes[p[0]] != classes[p[1]]]
    sep = sum(same)/len(same) - sum(cross)/len(cross)

    # show each molecule's MAMMAL nearest neighbor
    print("\nMAMMAL nearest neighbor per molecule:")
    for i in range(n):
        j = max((k for k in range(n) if k != i), key=lambda k: mam_sim[(min(i, k), max(i, k))])
        flag = "OK" if classes[i] == classes[j] else "x"
        print(f"  {names[i]:14s}({classes[i]:13s}) -> {names[j]:14s}({classes[j]:13s}) {flag}")

    summary = {"timestamp": ts, "n": n, "n_classes": len(set(classes)),
               "mammal_nn_same_class": round(mam_nn, 3),
               "tanimoto_nn_same_class": round(tan_nn, 3),
               "mammal_vs_tanimoto_spearman": round(rho, 3),
               "mammal_sameclass_minus_crossclass_cosine": round(sep, 3)}
    (REPO / "results" / f"phase2a_similarity_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\nMAMMAL NN same-class: {mam_nn:.2f}   Tanimoto NN same-class: {tan_nn:.2f}")
    print(f"MAMMAL vs Tanimoto agreement (Spearman): {rho:.2f}")
    print(f"same-class minus cross-class mean cosine: {sep:+.3f}")


if __name__ == "__main__":
    main()
