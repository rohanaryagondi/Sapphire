"""Phase 4 (v2) — validate the BBBP head against textbook BBB pharmacology, done rigorously.

v1 had a SMILES-quality bug: PubChem IsomericSMILES returned protonated/salt forms (RDKit
valence errors) that the tokenizer scores as different molecules. v2 fixes this and adds the
checks that make the result trustworthy:
  - clean neutral parent SMILES (strip salts, uncharge) via RDKit;
  - cross-check each compound against the MoleculeNet BBBP set by neutral-parent InChIKey, and
    determine its scaffold-split FOLD (train/val/test) so we separate memorization from
    generalization (deepchem-style ScaffoldSplitter, as in phase1b);
  - a calibration view: score distribution on a balanced dataset sample + AUROC, to show the
    head emits saturated hard 0/1 calls (so "P(BBB+)" is a label, not a calibrated probability).

Readout: BBBP head generative P(<1>) = P(BBB-penetrant) via mammal.examples.molnet.
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase4_bbbp_literature.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import csv
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold

# name -> (literature BBB label 1=centrally active / 0=peripherally restricted, group)
COMPOUNDS = [
    ("morphine", 1, "opioid"), ("loperamide", 0, "opioid"),
    ("diphenhydramine", 1, "antihistamine"), ("hydroxyzine", 1, "antihistamine"),
    ("cetirizine", 0, "antihistamine"), ("fexofenadine", 0, "antihistamine"),
    ("loratadine", 0, "antihistamine"),
    ("metoclopramide", 1, "antiemetic"), ("domperidone", 0, "antiemetic"),
    ("diazepam", 1, "control+"), ("caffeine", 1, "control+"), ("haloperidol", 1, "control+"),
    ("fluoxetine", 1, "control+"), ("donepezil", 1, "control+"), ("carbamazepine", 1, "control+"),
    ("phenytoin", 1, "control+"),
    ("atenolol", 0, "control-"), ("sulpiride", 0, "control-"),
    ("sirolimus", 0, "control-"), ("vancomycin", 0, "control-"),
]


def neutral_parent(smi):
    m = Chem.MolFromSmiles(smi)
    if not m:
        return None
    frags = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=True)
    m = max(frags, key=lambda x: x.GetNumAtoms())
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize
        m = rdMolStandardize.Uncharger().uncharge(m)
    except Exception:
        pass
    return Chem.MolToSmiles(m)


def fetch_smiles(name):
    # CanonicalSMILES (neutral, no stereo salts) preferred; retry w/ backoff (avoid rate-limit n/a)
    for prop in ("CanonicalSMILES", "ConnectivitySMILES", "IsomericSMILES"):
        for attempt in range(3):
            try:
                url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                       f"{urllib.request.quote(name)}/property/{prop}/JSON")
                with urllib.request.urlopen(url, timeout=30) as r:
                    d = json.load(r)
                s = d["PropertyTable"]["Properties"][0].get(prop)
                if s:
                    return neutral_parent(s)
            except Exception:
                time.sleep(1.0 + attempt)
        time.sleep(0.3)
    return None


def ikey(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToInchiKey(m) if m else None


def murcko(smi):
    m = Chem.MolFromSmiles(smi)
    return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False) if m else None


def scaffold_split(smiles_list, frac_train=0.8, frac_valid=0.1):
    scaffolds = {}
    for i, smi in enumerate(smiles_list):
        sc = murcko(smi)
        if sc is None:
            continue
        scaffolds.setdefault(sc, []).append(i)
    n = len(smiles_list)
    sets = [s for _, s in sorted(scaffolds.items(), key=lambda x: (len(x[1]), x[1][0]), reverse=True)]
    tr_cut, va_cut = frac_train * n, (frac_train + frac_valid) * n
    train, valid, test = [], [], []
    for s in sets:
        if len(train) + len(s) > tr_cut:
            if len(train) + len(valid) + len(s) > va_cut:
                test += s
            else:
                valid += s
        else:
            train += s
    fold = {}
    for f, idxs in (("train", train), ("valid", valid), ("test", test)):
        for i in idxs:
            fold[i] = f
    return fold


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- dataset: neutral-parent InChIKey -> (label, fold) ---
    drows = list(csv.DictReader(open("/tmp/BBBP.csv")))
    dsmiles = [r["smiles"] for r in drows]
    fold = scaffold_split(dsmiles)
    key2 = {}
    for i, r in enumerate(drows):
        np_smi = neutral_parent(r["smiles"])
        k = ikey(np_smi) if np_smi else None
        if k:
            key2[k] = (int(float(r["p_np"])), fold.get(i, "?"))

    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer
    head = str(REPO / "models" / "moleculenet_bbbp")
    model = Mammal.from_pretrained(head).to("mps").eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(head, "tokenizer"))
    task = {"task_name": "BBBP", "model": model, "tokenizer_op": tok}

    def p_bbb(smi):
        return float(molnet_infer.task_infer(task_dict=task, smiles_seq=smi)["score"])

    # --- calibration view: balanced dataset sample, show saturation + AUROC ---
    pos = [r for r in drows if int(float(r["p_np"])) == 1]
    neg = [r for r in drows if int(float(r["p_np"])) == 0]
    samp = pos[:: max(1, len(pos)//75)][:75] + neg[:: max(1, len(neg)//75)][:75]
    ys, ss = [], []
    for r in samp:
        try:
            ss.append(p_bbb(r["smiles"])); ys.append(int(float(r["p_np"])))
        except Exception:
            pass
    sat = sum(1 for x in ss if x < 0.01 or x > 0.99) / len(ss)
    cal_auroc = auroc(ys, ss)

    # --- literature panel ---
    print(f"fetching clean neutral SMILES for {len(COMPOUNDS)} compounds...")
    rows = []
    for name, lab, grp in COMPOUNDS:
        smi = fetch_smiles(name)
        if not smi:
            print(f"  !! no SMILES for {name}"); continue
        k = ikey(smi)
        lab_fold = key2.get(k)
        in_train = (lab_fold is not None and lab_fold[1] in ("train", "valid"))
        held_out = (lab_fold is not None and lab_fold[1] == "test")
        not_in = lab_fold is None
        rows.append({"name": name, "label": lab, "group": grp, "smiles": smi,
                     "dataset_label": (lab_fold[0] if lab_fold else None),
                     "fold": (lab_fold[1] if lab_fold else "not_in_set"),
                     "in_train": in_train, "held_out": held_out, "not_in_set": not_in})

    for r in rows:
        r["p_bbb"] = p_bbb(r["smiles"])
        r["pred"] = int(r["p_bbb"] >= 0.5)
        r["correct"] = int(r["pred"] == r["label"])

    # honest accuracy: only compounds the model did NOT see in training
    fair = [r for r in rows if not r["in_train"]]
    n_fair_corr = sum(r["correct"] for r in fair)

    summary = {
        "timestamp": ts,
        "calibration": {"n": len(ss), "auroc": round(cal_auroc, 3),
                        "frac_saturated_0or1": round(sat, 3),
                        "note": "scores are near-deterministic 0/1 -> hard labels, not calibrated probs"},
        "n_panel": len(rows),
        "accuracy_all": round(sum(r["correct"] for r in rows)/len(rows), 3),
        "n_in_train": sum(r["in_train"] for r in rows),
        "n_fair": len(fair), "accuracy_fair": round(n_fair_corr/len(fair), 3) if fair else None,
        "rows": [{k: r[k] for k in ("name","group","label","dataset_label","fold","pred","p_bbb","correct","in_train")} for r in rows],
    }
    (REPO / "results" / f"phase4_bbbp_literature_{ts}.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== calibration (balanced dataset sample n={len(ss)}) ===")
    print(f"  AUROC {cal_auroc:.3f} | fraction of scores saturated to ~0 or ~1: {sat*100:.0f}%")
    print(f"  -> the head emits HARD 0/1 calls; P(BBB+) is a label, not a tunable probability\n")
    print("=== BBBP vs textbook BBB pharmacology (clean neutral SMILES) ===")
    print(f"{'compound':16s} {'grp':13s} {'lit':>3s} {'data':>4s} {'fold':>6s} {'P(BBB+)':>8s} {'pred':>4s} {'ok':>3s}")
    for r in sorted(rows, key=lambda x: (x["group"], x["name"])):
        dl = '+' if r["dataset_label"] == 1 else '-' if r["dataset_label"] == 0 else '?'
        print(f"{r['name']:16s} {r['group']:13s} {('+' if r['label'] else '-'):>3s} {dl:>4s} "
              f"{r['fold']:>6s} {r['p_bbb']:8.3f} {('+' if r['pred'] else '-'):>4s} {('Y' if r['correct'] else 'N'):>3s}")
    print(f"\noverall: {sum(r['correct'] for r in rows)}/{len(rows)} match literature "
          f"({summary['accuracy_all']:.2f}); {summary['n_in_train']} were in the train/val fold")
    if fair:
        print(f"FAIR (held-out test fold + not-in-set only): {n_fair_corr}/{len(fair)} = {summary['accuracy_fair']:.2f}")
        for r in fair:
            print(f"    {r['name']:16s} lit {('+' if r['label'] else '-')} pred {('+' if r['pred'] else '-')} "
                  f"({'OK' if r['correct'] else 'MISS'}) fold={r['fold']}")
    print(f"\nwrote results/phase4_bbbp_literature_{ts}.json")


if __name__ == "__main__":
    main()
