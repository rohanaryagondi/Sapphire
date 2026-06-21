"""Phase 1b — proper held-out AUROC for MAMMAL's MoleculeNet classification heads.

MAMMAL's molnet heads were finetuned on MoleculeNet's predefined SCAFFOLD splits.
To get a fair number we reproduce deepchem's ScaffoldSplitter exactly and evaluate
only on the TEST fold (the molecules held out of training).

Usage:
  python scripts/phase1b_molnet_eval.py bbbp     # BBBP head, label p_np
  python scripts/phase1b_molnet_eval.py tox      # ClinTox CT_TOX head

Caveat: this reproduces the canonical deepchem scaffold split; if MAMMAL used a
different RDKit version a few molecules could shift folds (minor leakage). The
paper reports BBBP AUROC 0.957, ClinTox 0.986 on these splits.
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
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

# dataset -> (csv path, smiles col, label col, MAMMAL task_name, local head dir)
DATASETS = {
    "bbbp": ("/tmp/BBBP.csv", "smiles", "p_np", "BBBP", REPO / "models" / "moleculenet_bbbp"),
    "tox": ("/tmp/clintox.csv", "smiles", "CT_TOX", "TOXICITY", REPO / "models" / "moleculenet_clintox_tox"),
    "fda": ("/tmp/clintox.csv", "smiles", "FDA_APPROVED", "FDA_APPR", REPO / "models" / "moleculenet_clintox_fda"),
}


def murcko_scaffold(smiles: str) -> str | None:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)


def scaffold_split(smiles_list, frac_train=0.8, frac_valid=0.1):
    """Replicates deepchem ScaffoldSplitter. Returns (train_idx, valid_idx, test_idx).
    Molecules whose scaffold can't be computed are dropped (as deepchem drops featurization failures)."""
    scaffolds = {}
    valid_rows = []
    for i, smi in enumerate(smiles_list):
        sc = murcko_scaffold(smi)
        if sc is None:
            continue
        valid_rows.append(i)
        scaffolds.setdefault(sc, []).append(i)
    n = len(valid_rows)
    sets = [s for _, s in sorted(scaffolds.items(), key=lambda x: (len(x[1]), x[1][0]), reverse=True)]
    train_cut = frac_train * n
    valid_cut = (frac_train + frac_valid) * n
    train, valid, test = [], [], []
    for s in sets:
        if len(train) + len(s) > train_cut:
            if len(train) + len(valid) + len(s) > valid_cut:
                test += s
            else:
                valid += s
        else:
            train += s
    return train, valid, test


def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > nn) + 0.5 * (p == nn) for p in pos for nn in neg)
    return wins / (len(pos) * len(neg))


def main():
    ds = sys.argv[1] if len(sys.argv) > 1 else "bbbp"
    csv_path, smi_col, label_col, task_name, head_dir = DATASETS[ds]
    head_dir = str(head_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows = list(csv.DictReader(open(csv_path)))
    smiles = [r[smi_col] for r in rows]
    labels = [int(float(r[label_col])) for r in rows]
    _, _, test_idx = scaffold_split(smiles)
    print(f"[{ds}] {len(rows)} mols -> test fold {len(test_idx)} "
          f"(pos rate {sum(labels[i] for i in test_idx)/len(test_idx):.2f})")

    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    model = Mammal.from_pretrained(head_dir).to("mps").eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(head_dir, "tokenizer"))
    task_dict = {"task_name": task_name, "model": model, "tokenizer_op": tok}

    y_true, y_score, n_err = [], [], 0
    for k, i in enumerate(test_idx):
        try:
            res = molnet_infer.task_infer(task_dict=task_dict, smiles_seq=smiles[i])
        except Exception:
            n_err += 1
            continue
        y_true.append(labels[i]); y_score.append(res["score"])
        if (k + 1) % 50 == 0:
            print(f"  ...{k+1}/{len(test_idx)}")

    roc = auroc(y_true, y_score)
    # accuracy at 0.5 threshold
    acc = sum(int((s >= 0.5) == bool(t)) for s, t in zip(y_score, y_true)) / len(y_true)
    summary = {"timestamp": ts, "dataset": ds, "task_name": task_name,
               "n_test_scored": len(y_true), "n_errors": n_err,
               "auroc": round(roc, 4), "acc@0.5": round(acc, 4),
               "paper_auroc": 0.957 if ds == "bbbp" else 0.986}
    (REPO / "results" / f"phase1b_molnet_{ds}_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[{ds}] held-out scaffold test: n={len(y_true)} AUROC={roc:.3f} acc@0.5={acc:.3f}"
          f"  (paper {summary['paper_auroc']})")


if __name__ == "__main__":
    main()
