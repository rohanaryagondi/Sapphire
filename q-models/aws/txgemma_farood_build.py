#!/usr/bin/env python3
"""Build the TxGemma far-OOD panel — IDENTICAL bands to the MapLight head-to-head.

BBB : full TDC BBB_Martins train; B3DB classification test, canonical-SMILES dedup vs train;
      bin by max ECFP4 (Morgan r2, 2048) Tanimoto-to-train into near>=0.4 / mid[0.3,0.4) / far<0.3.
      (MapLight B3DB far<0.3 AUROC = 0.674, n=824.)
hERG: TDC hERG_Karim, scaffold split seed=1 frac[0.7,0.1,0.2] (same as MapLight); test set binned
      the same way. (MapLight hERG far<0.3 AUROC = 0.809.)

Emits txgemma_farood_panels.json: {templates, farood:{BBB:{near,mid,far},hERG:{near,mid,far}}, refs}.
Each item {smiles, y}. Reuses the existing TxGemma templates verbatim.
Run locally (rdkit + PyTDC); no GPU, no HF token needed.
"""
import json, os, sys, urllib.request
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs

OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("aws/txgemma_farood_panels.json")
TEMPLATES_SRC = "/tmp/txg/txgemma_panels.json"
B3DB_URL = "https://raw.githubusercontent.com/theochem/B3DB/main/B3DB/B3DB_classification.tsv"
SEED = 1


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


def fp(s):
    m = Chem.MolFromSmiles(s)
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None


def max_tan_to_train(test_smiles, train_fps):
    f = fp(test_smiles)
    if f is None or not train_fps:
        return None
    return float(max(DataStructs.BulkTanimotoSimilarity(f, train_fps)))


def band(sim):
    if sim is None:
        return None
    return "near" if sim >= 0.4 else ("mid" if sim >= 0.3 else "far")


def bin_items(items, train_fps):
    """items: list of (smiles, y). -> {near:[{smiles,y}], mid:[...], far:[...]} by Tanimoto-to-train."""
    out = {"near": [], "mid": [], "far": []}
    for smi, y in items:
        b = band(max_tan_to_train(smi, train_fps))
        if b:
            out[b].append({"smiles": smi, "y": int(y)})
    return out


def build_bbb():
    from tdc.single_pred import ADME
    d = ADME(name="BBB_Martins")
    df = d.get_data()
    train_smiles = list(df["Drug"])               # full set as "train" (MapLight recipe)
    train_canon = {canon(s) for s in train_smiles if canon(s)}
    train_fps = [f for f in (fp(s) for s in train_smiles) if f is not None]
    # B3DB test
    txt = urllib.request.urlopen(B3DB_URL, timeout=90).read().decode()
    rows = [l.split("\t") for l in txt.splitlines()]
    hdr = rows[0]
    si, li = hdr.index("SMILES"), hdr.index("BBB+/BBB-")
    seen, items = set(), []
    for r in rows[1:]:
        if len(r) <= max(si, li):
            continue
        c = canon(r[si])
        if not c or c in train_canon or c in seen:
            continue
        seen.add(c)
        y = 1 if r[li].strip() == "BBB+" else 0
        items.append((c, y))
    return bin_items(items, train_fps), len(train_canon)


def build_herg():
    from tdc.single_pred import Tox
    d = Tox(name="hERG_Karim")
    sp = d.get_split(method="scaffold", seed=SEED, frac=[0.7, 0.1, 0.2])
    tr, te = sp["train"], sp["test"]
    train_fps = [f for f in (fp(s) for s in tr["Drug"]) if f is not None]
    items = [(s, int(y)) for s, y in zip(te["Drug"], te["Y"])]
    return bin_items(items, train_fps), len(train_fps)


def main():
    templates = json.load(open(TEMPLATES_SRC))["templates"]
    bbb, nbbb = build_bbb()
    herg, nherg = build_herg()
    panel = {
        "templates": {"BBB_Martins": templates["BBB_Martins"], "hERG_Karim": templates["hERG_Karim"]},
        "farood": {"BBB": bbb, "hERG": herg},
        "refs": {"BBB_far_maplight": 0.674, "BBB_mid_maplight": 0.721,
                 "hERG_far_maplight": 0.809, "BBB_train_n": nbbb, "hERG_train_n": nherg},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(panel))
    for endp in ("BBB", "hERG"):
        c = {k: len(v) for k, v in panel["farood"][endp].items()}
        pos = {k: sum(i["y"] for i in v) for k, v in panel["farood"][endp].items()}
        print(f"{endp}: counts {c} | pos {pos}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
