"""1d-(b) — Does chemotype diversity of training binders predict the bimodal AUROC?

The ceiling run found 3/6 well-trained targets at AUROC ≥ 0.80 (RORC, CA2, Adrb2)
and 3/6 at or below chance (BRAF, HRH1, mTOR-matched). Hypothesis: targets where
the head WORKS have a *more diverse* set of training binders (so the head learns a
real binding signal); targets where it FAILS have a *narrow* binder set (so the
head memorises a chemotype and can't generalise to MW-matched off-target compounds).

This experiment computes mean pairwise Tanimoto distance (1 − Tanimoto similarity
on Morgan FP2 radius-2 / 2048-bit) for the top-30 binders of each ceiling target
and correlates that with the AUROC random / AUROC matched / off-target Δ values
from the ceiling run.

Pure analysis (RDKit + arithmetic, no MAMMAL). Fast.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/datafit_chemodiversity.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver import datafit  # noqa: E402

PANEL = [
    ("P42345", "MTOR",  192, "kinase",            {"auc_random": 0.761, "auc_matched": 0.558, "delta_offtarget": -1.124}),
    ("P15056", "BRAF",  532, "kinase",            {"auc_random": 0.468, "auc_matched": 0.463, "delta_offtarget":  1.179}),
    ("Q8K4Z4", "Adrb2", 211, "gpcr",              {"auc_random": 0.871, "auc_matched": 0.881, "delta_offtarget":  0.835}),
    ("P31389", "HRH1",  184, "gpcr",              {"auc_random": 0.400, "auc_matched": 0.330, "delta_offtarget":  0.682}),
    ("P51449", "RORC",  374, "nuclear_receptor",  {"auc_random": 0.970, "auc_matched": 0.952, "delta_offtarget":  0.685}),
    ("P00918", "CA2",   269, "other",             {"auc_random": 0.867, "auc_matched": 0.840, "delta_offtarget":  1.975}),
]
N_BINDERS = 30


def tanimoto_stats(smiles_list, radius=2, n_bits=2048):
    """Return (mean_pair_tanimoto, mean_pair_distance, n_valid) for a list of SMILES."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit import DataStructs

    fps = []
    for smi in smiles_list:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        fps.append(AllChem.GetMorganFingerprintAsBitVect(m, radius, n_bits))
    n = len(fps)
    if n < 2:
        return None, None, n
    # Mean pairwise Tanimoto similarity (i<j)
    pair_sims = []
    for i in range(n):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i + 1 :])
        pair_sims.extend(sims)
    mean_sim = sum(pair_sims) / len(pair_sims)
    return mean_sim, 1.0 - mean_sim, n


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for acc, gene, n_pairs, cls, m in PANEL:
        binders = datafit.get_binders(acc, pkd_threshold=7.0, n_max=N_BINDERS)
        smiles = [s for s, _ in binders]
        sim, dist, n_valid = tanimoto_stats(smiles)
        row = {
            "accession": acc, "gene": gene, "class": cls, "n_pairs_training": n_pairs,
            "n_binders_used": n_valid,
            "mean_pairwise_tanimoto_similarity": round(sim, 3) if sim is not None else None,
            "mean_pairwise_tanimoto_distance":   round(dist, 3) if dist is not None else None,
            **m,
        }
        rows.append(row)
        print(f"{gene:6s} (n_pairs={n_pairs:4d}, class={cls:18s})  "
              f"mean Tanimoto sim={sim:.3f}  diversity={1-sim:.3f}  "
              f"AUROC rand={m['auc_random']:.2f}  matched={m['auc_matched']:.2f}  Δ off={m['delta_offtarget']:+.2f}")

    # Correlate diversity with the three ceiling metrics
    div = [r["mean_pairwise_tanimoto_distance"] for r in rows]
    ar = [r["auc_random"] for r in rows]
    am = [r["auc_matched"] for r in rows]
    do = [r["delta_offtarget"] for r in rows]

    rho_random = datafit.spearman(div, ar)
    rho_matched = datafit.spearman(div, am)
    rho_offtarget = datafit.spearman(div, do)

    print("\n=== Spearman (chemodiversity vs ceiling metric) ===")
    print(f"  diversity vs AUROC random  : ρ = {rho_random:+.3f}")
    print(f"  diversity vs AUROC matched : ρ = {rho_matched:+.3f}")
    print(f"  diversity vs off-target Δ  : ρ = {rho_offtarget:+.3f}")

    # Interpretation
    verdict = (
        "diversity STRONGLY predicts AUROC (ρ>0.7) — chemotype concentration is the bimodality predictor"
        if max(abs(rho_random), abs(rho_matched)) > 0.7 else
        "diversity MODESTLY predicts AUROC (ρ in [0.4,0.7]) — partial signal"
        if max(abs(rho_random), abs(rho_matched)) > 0.4 else
        "diversity DOES NOT predict AUROC (|ρ| < 0.4) — bimodality is driven by something else"
    )
    print(f"\nVerdict: {verdict}")

    out = {
        "timestamp": ts,
        "n_targets": len(rows),
        "n_binders_max_per_target": N_BINDERS,
        "rows": rows,
        "spearman": {
            "diversity_vs_auc_random":  round(rho_random, 3),
            "diversity_vs_auc_matched": round(rho_matched, 3),
            "diversity_vs_delta_offtarget": round(rho_offtarget, 3),
        },
        "verdict": verdict,
    }
    out_path = REPO / "results" / f"datafit_chemodiversity_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
