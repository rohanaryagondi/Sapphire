"""Phase 4 — calibration + per-direction audit of the MoleculeNet classification heads.

Completes the fine-tuned-head picture for BBBP, ClinTox-toxicity, ClinTox-FDA. For each head,
on its held-out deepchem scaffold TEST fold, report:
  - AUROC (ranking, the benchmark-style number)
  - saturation: fraction of scores at ~0 or ~1 (is the output a hard label, not a probability?)
  - TPR and TNR at 0.5 (per-direction reliability — exposes one-sided failure that AUROC hides)
  - positive rate of the fold (to read TPR/TNR fairly)
Plus, for ClinTox-toxicity, the deployment-critical number: among truly NON-toxic compounds,
what fraction does the model FALSE-ALARM as toxic (over-prediction rate)?

Readout = molnet generative P(<1>) = P(positive class) [BBBP: penetrant; TOXICITY: toxic;
FDA_APPR: approved].
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase4_molnet_audit.py
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

# head -> (csv, smiles col, label col, molnet task name, model dir, positive_means)
HEADS = [
    ("BBBP",        "/tmp/BBBP.csv",    "smiles", "p_np",         "BBBP",     "moleculenet_bbbp",         "penetrant"),
    ("ClinTox-tox", "/tmp/clintox.csv", "smiles", "CT_TOX",       "TOXICITY", "moleculenet_clintox_tox",  "toxic"),
    ("ClinTox-FDA", "/tmp/clintox.csv", "smiles", "FDA_APPROVED", "FDA_APPR", "moleculenet_clintox_fda",  "approved"),
]


def murcko(smi):
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    m = Chem.MolFromSmiles(smi)
    return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False) if m else None


def scaffold_test_idx(smiles, frac_train=0.8, frac_valid=0.1):
    scaf = {}
    valid_rows = []
    for i, smi in enumerate(smiles):
        sc = murcko(smi)
        if sc is None:
            continue
        valid_rows.append(i); scaf.setdefault(sc, []).append(i)
    n = len(valid_rows)
    sets = [s for _, s in sorted(scaf.items(), key=lambda x: (len(x[1]), x[1][0]), reverse=True)]
    tr_cut, va_cut = frac_train * n, (frac_train + frac_valid) * n
    train, valid, test = [], [], []
    for s in sets:
        if len(train) + len(s) > tr_cut:
            test_or_valid = valid if len(train) + len(valid) + len(s) <= va_cut else test
            test_or_valid += s
        else:
            train += s
    return set(test), set(train) | set(valid)


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    out = {"timestamp": ts, "heads": {}}
    for label, csv_path, scol, lcol, task_name, mdir, pos_means in HEADS:
        rows = list(csv.DictReader(open(csv_path)))
        smiles = [r[scol] for r in rows]
        y_all = [int(float(r[lcol])) for r in rows]
        test_idx, train_idx = scaffold_test_idx(smiles)

        head = str(REPO / "models" / mdir)
        model = Mammal.from_pretrained(head).to("mps").eval()
        tok = ModularTokenizerOp.from_pretrained(os.path.join(head, "tokenizer"))
        task = {"task_name": task_name, "model": model, "tokenizer_op": tok}

        def score(smi):
            return float(molnet_infer.task_infer(task_dict=task, smiles_seq=smi)["score"])

        # evaluate on test fold (cap at 300 for speed, even stride)
        ti = sorted(test_idx)
        ti = ti[:: max(1, len(ti) // 300)][:300]
        y, s = [], []
        for k, i in enumerate(ti):
            try:
                s.append(score(smiles[i])); y.append(y_all[i])
            except Exception:
                pass
        roc = auroc(y, s)
        sat = sum(1 for x in s if x < 0.01 or x > 0.99) / len(s)
        pos_rate = sum(y) / len(y)
        # per-direction at 0.5
        tp = sum(1 for a, t in zip(s, y) if t == 1 and a >= 0.5)
        tn = sum(1 for a, t in zip(s, y) if t == 0 and a < 0.5)
        npos = sum(y); nneg = len(y) - npos
        tpr = tp / npos if npos else float("nan")
        tnr = tn / nneg if nneg else float("nan")

        rec = {"task": task_name, "positive_means": pos_means, "n_test": len(y),
               "pos_rate": round(pos_rate, 3), "auroc": round(roc, 4),
               "saturation_frac": round(sat, 3),
               "TPR_at_0.5": round(tpr, 3), "TNR_at_0.5": round(tnr, 3)}

        # ClinTox-tox: over-prediction (false-alarm) rate on truly NON-toxic compounds
        if task_name == "TOXICITY":
            nontox = [i for i in range(len(rows)) if y_all[i] == 0]
            nontox = nontox[:: max(1, len(nontox) // 200)][:200]
            fa = 0; m = 0
            for i in nontox:
                try:
                    if score(smiles[i]) >= 0.5:
                        fa += 1
                    m += 1
                except Exception:
                    pass
            rec["nontoxic_falsealarm_rate"] = round(fa / m, 3)
            rec["nontoxic_n"] = m

        out["heads"][label] = rec
        del model
        print(f"[{label}] AUROC {roc:.3f} | sat {sat*100:.0f}% | posRate {pos_rate:.2f} | "
              f"TPR {tpr:.2f} TNR {tnr:.2f}" +
              (f" | non-toxic FALSE-ALARM {rec.get('nontoxic_falsealarm_rate')}" if task_name == "TOXICITY" else ""))

    (REPO / "results" / f"phase4_molnet_audit_{ts}.json").write_text(json.dumps(out, indent=2))
    print("\n================= MoleculeNet head audit =================")
    print(f"{'head':12s} {'AUROC':>6s} {'sat%':>5s} {'posRate':>7s} {'TPR':>5s} {'TNR':>5s}")
    for label, r in out["heads"].items():
        print(f"{label:12s} {r['auroc']:6.3f} {r['saturation_frac']*100:4.0f}% {r['pos_rate']:7.2f} "
              f"{r['TPR_at_0.5']:5.2f} {r['TNR_at_0.5']:5.2f}")
    tox = out["heads"].get("ClinTox-tox", {})
    if "nontoxic_falsealarm_rate" in tox:
        print(f"\nClinTox-tox over-prediction: {tox['nontoxic_falsealarm_rate']*100:.0f}% of truly "
              f"NON-toxic compounds (n={tox['nontoxic_n']}) are FALSE-ALARMED as toxic")
    print(f"\nwrote results/phase4_molnet_audit_{ts}.json")


if __name__ == "__main__":
    main()
