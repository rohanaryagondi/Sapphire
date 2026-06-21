#!/usr/bin/env python
"""Build a public PGK2 per-target binder train/val set for the fine-tune pilot.

Positives = PGK2 DEL hits (data/pgk2/DEL_hit_candidates_1.csv).
Negatives = PGK1-homolog ChEMBL ligands (hard negatives) + drug-like decoys.
Output: aws/data/pgk2_binder_{train,val}.csv with columns Drug,label  (the
carcinogenicity data-module shape: SMILES + binary label).

Deterministic split (no RNG seed drift): sort by a hash of the SMILES, take the
last 20% as val. No network, no model. Run locally before launch.
"""
import csv, json, hashlib, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "pgk2"
OUT = ROOT / "aws" / "data"
OUT.mkdir(parents=True, exist_ok=True)

def h(s):  # stable hash for a deterministic split
    return int(hashlib.md5(s.encode()).hexdigest(), 16)

# positives: PGK2 DEL hits
pos = []
with open(DATA / "DEL_hit_candidates_1.csv") as f:
    for row in csv.DictReader(f):
        smi = row["SMILES"].strip()
        if smi:
            pos.append(smi)

# negatives: PGK1 homolog ligands (hard) + wdr91 drug-like decoys (generic)
neg = []
for lig in json.load(open(DATA / "pgk1_chembl_ligands.json")):
    if lig.get("smiles"):
        neg.append(lig["smiles"].strip())
for dec in json.load(open(ROOT / "data" / "wdr91" / "wdr91_decoys.json")):
    if dec.get("smiles"):
        neg.append(dec["smiles"].strip())

# dedup, drop any SMILES that appears in both classes
pos = list(dict.fromkeys(pos))
neg = [s for s in dict.fromkeys(neg) if s not in set(pos)]

rows = [(s, 1) for s in pos] + [(s, 0) for s in neg]
# deterministic 80/20 split by hash bucket, stratified by holding the ratio per class
train, val = [], []
for smi, lab in rows:
    (val if h(smi) % 5 == 0 else train).append((smi, lab))

def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Drug", "label"])
        w.writerows(rows)

write(OUT / "pgk2_binder_train.csv", train)
write(OUT / "pgk2_binder_val.csv", val)

def stats(name, rows):
    n = len(rows); p = sum(l for _, l in rows)
    print(f"{name:6s} n={n:4d}  pos={p:4d} ({p/n:.0%})  neg={n-p:4d}")

print(f"positives={len(pos)}  negatives={len(neg)}  total={len(rows)}")
stats("train", train)
stats("val", val)
print("wrote:", OUT / "pgk2_binder_train.csv", "and", OUT / "pgk2_binder_val.csv")
