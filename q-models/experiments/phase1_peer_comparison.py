"""Phase 1 follow-up — does the PEER checkpoint transfer to our pairs?

The paper's headline DTI numbers come from the PEER benchmark, which holds out
GPCRs, ion channels, receptor tyrosine kinases, and ER to test generalization to
exactly those classes. Its checkpoint is dti_bindingdb_pkd_peer (norms 6.286 /
1.542) — NOT the dti_bindingdb_pkd cold-split checkpoint we first tested.

Our 10 pairs ARE those classes. So this re-runs them on the PEER checkpoint and
compares Spearman to the cold-split result (which was -0.03).

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1_peer_comparison.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable
sys.path.insert(0, str(REPO / "experiments"))  # to reuse phase1_correlation helpers

from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import DRUGS, fetch_uniprot_sequence  # noqa: E402
# reuse the curated pairs + ChEMBL/stat helpers from the correlation script
from phase1_correlation import (  # noqa: E402
    PAIRS, resolve_molecule, resolve_target, experimental_pchembl, spearman, pearson,
)

PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_MEAN, PEER_STD = 6.286291085593906, 1.5422950906208512


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("resolving ChEMBL ids + affinities (same 10 pairs as cold-split run) ...")
    rows = []
    for drug, tname, acc in PAIRS:
        try:
            mol_id, smiles = resolve_molecule(drug)
            tgt_id = resolve_target(acc)
            exp = experimental_pchembl(mol_id, tgt_id)
            seq = fetch_uniprot_sequence(acc)
            if exp is None or not smiles:
                continue
            rows.append({"drug": drug, "target": tname, "smiles": smiles,
                         "seq": seq, "exp_pchembl": round(exp, 3)})
        except Exception as e:
            print(f"  ERROR {drug}/{tname}: {e}")

    model, tok, device = load_dti_model(source=PEER_SOURCE)
    print(f"loaded PEER checkpoint on {device}; predicting ...")
    for r in rows:
        r["pred_pKd"] = round(predict_pkd(model, tok, r["seq"], r["smiles"],
                                          norm_y_mean=PEER_MEAN, norm_y_std=PEER_STD), 4)
        print(f"  {r['drug']:12s} x {r['target']:7s}  exp={r['exp_pchembl']:.2f}  pred_PEER={r['pred_pKd']:.2f}")

    # named test
    nav18 = fetch_uniprot_sequence("Q9Y5Y9")
    named = round(predict_pkd(model, tok, nav18, DRUGS["suzetrigine"],
                              norm_y_mean=PEER_MEAN, norm_y_std=PEER_STD), 4)
    print(f"\n  suzetrigine x Nav1.8 (PEER) pred_pKd = {named:.3f}")

    exp = [r["exp_pchembl"] for r in rows]
    pred = [r["pred_pKd"] for r in rows]
    rho, rp = spearman(exp, pred), pearson(exp, pred)
    verdict = "STRONG PASS" if rho > 0.6 else "PASS" if rho > 0.4 else "FAIL"

    for r in rows:
        r.pop("seq", None)
    summary = {"timestamp": ts, "checkpoint": "dti_bindingdb_pkd_peer", "device": device,
               "n_pairs": len(rows), "spearman": round(rho, 4), "pearson": round(rp, 4),
               "verdict_vs_our_pairs": verdict, "named_suzetrigine_nav18": named,
               "cold_split_spearman_for_reference": -0.03, "pred_range": [min(pred), max(pred)],
               "pairs": rows}
    out = REPO / "results" / f"phase1_peer_comparison_{ts}.json"
    out.write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 60)
    print(f"PEER checkpoint on OUR pairs: n={len(rows)} Spearman={rho:.3f} Pearson={rp:.3f} -> {verdict}")
    print(f"(cold-split checkpoint was Spearman -0.03 on the same pairs)")
    print(f"saved -> {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
