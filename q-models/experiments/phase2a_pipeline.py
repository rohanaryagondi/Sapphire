"""Phase 2a — end-to-end hit-list de-risking funnel (the meeting's use case 2a /
"how fast can we get to molecules"). Uses MAMMAL only where it's validated:
  expand by Morgan/Tanimoto (MAMMAL loses here) -> de-risk with BBBP + ClinTox heads.

Library = the MoleculeNet BBBP set (2050 cpds) so we can CHECK the BBBP filter's
precision against the real p_np labels. Seed = a CNS drug (diazepam). Funnel:
  library -> top-K Tanimoto-similar to seed -> predicted BBB+ -> predicted non-toxic
            -> ranked shortlist. Reports counts, timing, and filter precision.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/phase2a_pipeline.py
"""

from __future__ import annotations

import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
BBBP_HEAD = str(REPO / "models" / "moleculenet_bbbp")
CTOX_HEAD = str(REPO / "models" / "moleculenet_clintox_tox")
LIBRARY_CSV = "/tmp/BBBP.csv"           # smiles,p_np,name  (fetched in phase1b)
SEED_SMILES = "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21"   # diazepam (CNS-penetrant benzodiazepine)
TOPK = 150
TOX_KEEP = 0.5   # keep predicted P(toxic) < this (caveat: head over-predicts; see writeup)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    rows = [r for r in csv.DictReader(open(LIBRARY_CSV))]
    lib = []
    for r in rows:
        m = Chem.MolFromSmiles(r["smiles"])
        if m is None:
            continue
        lib.append((r["smiles"], int(r["p_np"]), r.get("name", ""),
                    AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)))
    seed_fp = AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(SEED_SMILES), 2, nBits=2048)

    # 1. expand by Tanimoto similarity
    scored = sorted(lib, key=lambda x: DataStructs.TanimotoSimilarity(seed_fp, x[3]), reverse=True)
    expanded = scored[:TOPK]
    true_pen = sum(p for _, p, _, _ in expanded)
    print(f"library {len(lib)} -> expanded top-{TOPK} (true BBB+ in set: {true_pen}/{TOPK} = {true_pen/TOPK:.0%})")

    def run_head(head, task, smiles_list):
        m = Mammal.from_pretrained(head).to("mps").eval()
        t = ModularTokenizerOp.from_pretrained(f"{head}/tokenizer")
        td = {"task_name": task, "model": m, "tokenizer_op": t}
        out = {}
        for s in smiles_list:
            try:
                out[s] = molnet_infer.task_infer(task_dict=td, smiles_seq=s)["score"]
            except Exception:
                out[s] = None
        del m
        return out

    t0 = time.time()
    bbbp = run_head(BBBP_HEAD, "BBBP", [e[0] for e in expanded])
    # 2. BBB filter (predicted penetrant) + precision vs true labels
    bbb_pass = [e for e in expanded if bbbp.get(e[0]) is not None and bbbp[e[0]] >= 0.5]
    prec = (sum(p for _, p, _, _ in bbb_pass) / len(bbb_pass)) if bbb_pass else float("nan")
    print(f"  BBBP filter -> {len(bbb_pass)}/{TOPK} predicted penetrant; "
          f"precision vs true label = {prec:.0%}")

    # 3. ClinTox filter (predicted non-toxic) on the BBB survivors
    tox = run_head(CTOX_HEAD, "TOXICITY", [e[0] for e in bbb_pass])
    final = [e for e in bbb_pass if tox.get(e[0]) is not None and tox[e[0]] < TOX_KEEP]
    dt = time.time() - t0
    tox_scores = sorted(v for v in tox.values() if v is not None)
    print(f"  ClinTox filter (P_tox<{TOX_KEEP}) -> {len(final)}/{len(bbb_pass)} survive "
          f"(tox score median {tox_scores[len(tox_scores)//2]:.2f} — head over-predicts, see writeup)")

    # 4. ranked shortlist
    shortlist = sorted(final, key=lambda e: bbbp[e[0]], reverse=True)[:20]
    print(f"\nFunnel: {len(lib)} -> {TOPK} expanded -> {len(bbb_pass)} BBB+ -> {len(final)} non-toxic "
          f"-> top {len(shortlist)}. Inference {dt:.0f}s for {TOPK + len(bbb_pass)} predictions.")
    print("Top survivors (name / true_BBB+ / P(pen) / P(tox)):")
    for smi, p, name, _ in shortlist[:10]:
        print(f"  {name[:34]:34s} true={p}  pen={bbbp[smi]:.2f}  tox={tox[smi]:.2f}")

    summary = {"timestamp": ts, "library": len(lib), "topk": TOPK, "seed": "diazepam",
               "expanded_true_penetrant_frac": round(true_pen / TOPK, 3),
               "bbb_pass": len(bbb_pass), "bbb_precision_vs_label": round(prec, 3),
               "final_after_tox": len(final), "inference_s": round(dt, 1),
               "tox_caveat": "ClinTox head over-predicts toxicity; absolute threshold unreliable"}
    (REPO / "results" / f"phase2a_pipeline_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\nsaved -> results/phase2a_pipeline_{ts}.json")


if __name__ == "__main__":
    main()
