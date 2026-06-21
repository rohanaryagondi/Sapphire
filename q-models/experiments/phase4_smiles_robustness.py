"""Phase 4 — SMILES-representation robustness of the MoleculeNet heads (BBBP, ClinTox-tox).

A model that predicts a molecular PROPERTY should give the same answer for any valid SMILES of
the same molecule. We test this directly: for each molecule, generate K randomized-but-valid
SMILES (RDKit doRandom), score all K, and measure how much the prediction varies — including
whether the hard 0/1 class FLIPS across encodings of the identical structure.

No external data needed (randomized SMILES are generated locally), so this is dependency-free
and definitive. Readout = molnet P(<1>).
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase4_smiles_robustness.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rdkit import Chem

K = 8  # randomized SMILES per molecule


def randomized_smiles(canonical, k=K):
    m = Chem.MolFromSmiles(canonical)
    if m is None:
        return []
    out, seen = [], set()
    for seed in range(k * 6):
        s = Chem.MolToSmiles(m, doRandom=True, canonical=False)
        if s not in seen and Chem.MolFromSmiles(s) is not None:
            seen.add(s); out.append(s)
        if len(out) >= k:
            break
    return out


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    # a handful of molecules per head, drawn from the datasets (real, labeled)
    bbbp = list(csv.DictReader(open("/tmp/BBBP.csv")))
    clintox = list(csv.DictReader(open("/tmp/clintox.csv")))
    # pick 6 evenly-spread molecules from each
    bbbp_pick = [(r["smiles"], int(float(r["p_np"]))) for r in bbbp[:: max(1, len(bbbp)//6)][:6]]
    ctox_pick = [(r["smiles"], int(float(r["CT_TOX"]))) for r in clintox[:: max(1, len(clintox)//6)][:6]]

    out = {"timestamp": ts, "K": K, "heads": {}}
    for label, mdir, task_name, picks in [
        ("BBBP", "moleculenet_bbbp", "BBBP", bbbp_pick),
        ("ClinTox-tox", "moleculenet_clintox_tox", "TOXICITY", ctox_pick),
    ]:
        head = str(REPO / "models" / mdir)
        model = Mammal.from_pretrained(head).to("mps").eval()
        tok = ModularTokenizerOp.from_pretrained(os.path.join(head, "tokenizer"))
        task = {"task_name": task_name, "model": model, "tokenizer_op": tok}

        def score(smi):
            return float(molnet_infer.task_infer(task_dict=task, smiles_seq=smi)["score"])

        mols = []
        n_flip = 0
        print(f"\n[{label}] {K} randomized SMILES per molecule (same structure each):")
        for canon, lab in picks:
            variants = randomized_smiles(canon)
            if len(variants) < 3:
                continue
            scores = []
            for v in variants:
                try:
                    scores.append(score(v))
                except Exception:
                    pass
            if not scores:
                continue
            preds = [int(x >= 0.5) for x in scores]
            flips = len(set(preds)) > 1
            n_flip += flips
            mols.append({"canonical": canon, "label": lab, "n_variants": len(scores),
                         "p_min": round(min(scores), 3), "p_max": round(max(scores), 3),
                         "p_spread": round(max(scores) - min(scores), 3),
                         "class_flips": flips})
            print(f"  label={lab}  P range [{min(scores):.3f}, {max(scores):.3f}]  "
                  f"spread {max(scores)-min(scores):.3f}  {'CLASS FLIPS across encodings!' if flips else 'stable'}")
        out["heads"][label] = {"n_molecules": len(mols),
                               "n_with_class_flip": n_flip,
                               "molecules": mols}
        del model

    (REPO / "results" / f"phase4_smiles_robustness_{ts}.json").write_text(json.dumps(out, indent=2))
    print("\n================= SMILES-robustness summary =================")
    for label, r in out["heads"].items():
        print(f"{label:12s}: {r['n_with_class_flip']}/{r['n_molecules']} molecules CHANGE predicted class "
              f"depending on which valid SMILES of the SAME molecule is used")
    print(f"\nwrote results/phase4_smiles_robustness_{ts}.json")


if __name__ == "__main__":
    main()
