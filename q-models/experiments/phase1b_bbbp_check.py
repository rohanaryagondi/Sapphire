"""Phase 1b — sanity-check the off-the-shelf BBBP (blood-brain barrier) head.

Different head from DTI: a classification head used via model.generate(). Output
is pred in {0,1} (1 = BBB-penetrant) plus score = P(penetrant). Relevant to
Phase 2a de-risking (BBB filter on expanded hit lists).

We test on unambiguous known compounds: CNS drugs that clearly cross the BBB vs
peripheral/hydrophilic drugs that clearly do not. SMILES pulled from PubChem.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1b_bbbp_check.py
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
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

BBBP_LOCAL = str(REPO / "models" / "moleculenet_bbbp")

# Known labels: 1 = crosses BBB (CNS-active), 0 = peripheral / poor BBB.
COMPOUNDS = [
    ("caffeine", 1), ("diazepam", 1), ("haloperidol", 1),
    ("donepezil", 1), ("carbamazepine", 1), ("nicotine", 1),
    ("atenolol", 0), ("domperidone", 0), ("loperamide", 0),
    ("cetirizine", 0), ("vancomycin", 0),
]


def pubchem_smiles(name: str) -> str | None:
    q = urllib.parse.quote(name)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q}/property/IsomericSMILES,CanonicalSMILES/JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            props = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return props.get("IsomericSMILES") or props.get("CanonicalSMILES") or props.get("SMILES")
    except Exception as e:
        print(f"  PubChem fail {name}: {e}")
        return None


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    import torch  # noqa
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    dev = "mps"
    model = Mammal.from_pretrained(BBBP_LOCAL).to(dev).eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(BBBP_LOCAL, "tokenizer"))
    task_dict = {"task_name": "BBBP", "model": model, "tokenizer_op": tok}

    rows, y_true, y_score, correct = [], [], [], 0
    for name, label in COMPOUNDS:
        smi = pubchem_smiles(name)
        if not smi:
            continue
        res = molnet_infer.task_infer(task_dict=task_dict, smiles_seq=smi)
        pred, score = res["pred"], res["score"]
        ok = int(pred == label)
        correct += ok
        rows.append({"compound": name, "true": label, "pred": pred, "score_penetrant": round(score, 4), "ok": ok})
        y_true.append(label); y_score.append(score)
        print(f"  {name:14s} true={label} pred={pred} P(penetrant)={score:.3f} {'OK' if ok else 'MISS'}")

    # simple AUROC
    def auroc(yt, ys):
        pos = [s for s, t in zip(ys, yt) if t == 1]
        neg = [s for s, t in zip(ys, yt) if t == 0]
        if not pos or not neg:
            return float("nan")
        wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
        return wins / (len(pos) * len(neg))

    acc = correct / len(rows)
    roc = auroc(y_true, y_score)
    summary = {"timestamp": ts, "head": "moleculenet_bbbp", "n": len(rows),
               "accuracy": round(acc, 3), "auroc": round(roc, 3), "rows": rows}
    (REPO / "results" / f"phase1b_bbbp_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\nBBBP on {len(rows)} known compounds: accuracy={acc:.2f}  AUROC={roc:.2f}")


if __name__ == "__main__":
    main()
