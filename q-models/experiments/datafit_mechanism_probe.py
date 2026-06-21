"""Mechanism probe — what explains the diversity-vs-AUROC ρ = -0.83 (memorisation refuted)?

Background. The bimodality probe found Spearman(binder-diversity, AUROC) = -0.83 across
6 ceiling targets. The first-guess explanation was chemotype memorisation; the scaffold-
shift test refuted that. This script tests two simpler alternative mechanisms:

  (1) Decoy-distance hypothesis. AUROC is easier when the MW-matched decoys are
      chemically FARTHER from the binders. Targets with narrow binder sets sit in a
      small chemical region, so MW-matched off-target decoys (drawn from the wider
      BindingDB pool) end up further away → easier separation. Targets with diverse
      binder sets occupy more chemical space, so decoys overlap with at least some
      binders → harder. Test: per target, compute mean(min-Tanimoto-to-decoy) for the
      binders, correlate with ceiling AUROC.

  (2) Predicted-pKd variance hypothesis. The head may simply produce wider predicted
      ranges on some targets than others (more "discriminative room"). Test: per
      target, compute std of predicted pKd over binders+decoys, correlate with AUROC.

These are not mutually exclusive — both can contribute. We report Spearman ρ for each.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/datafit_mechanism_probe.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver import datafit  # noqa: E402
from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_M, PEER_S = 6.286291085593906, 1.5422950906208512

# The 6 ceiling targets + their published-ceiling AUROCs (from datafit_ceiling).
PANEL = [
    ("P42345", "MTOR",  192, "kinase",            {"auc_random": 0.761, "auc_matched": 0.558, "diversity": 0.796}),
    ("P15056", "BRAF",  532, "kinase",            {"auc_random": 0.468, "auc_matched": 0.463, "diversity": 0.842}),
    ("Q8K4Z4", "Adrb2", 211, "gpcr",              {"auc_random": 0.871, "auc_matched": 0.881, "diversity": 0.664}),
    ("P31389", "HRH1",  184, "gpcr",              {"auc_random": 0.400, "auc_matched": 0.330, "diversity": 0.759}),
    ("P51449", "RORC",  374, "nuclear_receptor",  {"auc_random": 0.970, "auc_matched": 0.952, "diversity": 0.523}),
    ("P00918", "CA2",   269, "other",             {"auc_random": 0.867, "auc_matched": 0.840, "diversity": 0.746}),
]

PKD_THRESHOLD = 7.0
N_BINDERS = 30
N_MATCHED_PER_BINDER = 3
MW_TOL = 50.0
SEED = 42


def tanimoto_matrix(smiles_a, smiles_b):
    """Pairwise Tanimoto similarity matrix between two SMILES lists (Morgan FP r=2 2048b)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit import DataStructs

    def fp(s):
        m = Chem.MolFromSmiles(s)
        return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None

    fps_a = [fp(s) for s in smiles_a]
    fps_b = [fp(s) for s in smiles_b]
    out = []
    for fa in fps_a:
        if fa is None:
            out.append([None] * len(fps_b))
            continue
        row = [DataStructs.TanimotoSimilarity(fa, fb) if fb is not None else None for fb in fps_b]
        out.append(row)
    return out


def score_many(model, tok, seq, smiles_list, label=""):
    preds = []
    t0 = time.time()
    for smi in smiles_list:
        try:
            preds.append(predict_pkd(model, tok, seq, smi, PEER_M, PEER_S))
        except Exception as e:  # noqa: BLE001
            print(f"    [warn] skip {label}: {e}")
    print(f"    {label}: {len(preds)} in {time.time() - t0:.1f}s")
    return preds


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"PEER DTI on {dev}\n")

    rows = []
    for acc, gene, n_pairs, cls, m in PANEL:
        print(f"\n=== {acc} {gene} ({cls}) ===")
        seq = fetch_uniprot_sequence(acc)
        binders = datafit.get_binders(acc, pkd_threshold=PKD_THRESHOLD, n_max=N_BINDERS)
        binder_smiles = [s for s, _ in binders]
        matched = datafit.sample_matched_decoys(
            acc, binder_smiles, n_per_binder=N_MATCHED_PER_BINDER, mw_tol=MW_TOL, seed=SEED
        )
        print(f"  binders: {len(binders)}; matched decoys: {len(matched)}")

        # ----- (1) Decoy distance -----
        sim = tanimoto_matrix(binder_smiles, matched)
        # For each binder, find the nearest matched decoy (max Tanimoto sim → min distance).
        # mean_min_dist_to_decoy: average over binders of (1 − max sim to any decoy)
        min_dists, mean_dists = [], []
        for row in sim:
            row_valid = [v for v in row if v is not None]
            if not row_valid:
                continue
            min_dists.append(1.0 - max(row_valid))
            mean_dists.append(1.0 - (sum(row_valid) / len(row_valid)))
        avg_min_dist = mean(min_dists) if min_dists else float("nan")
        avg_mean_dist = mean(mean_dists) if mean_dists else float("nan")
        print(f"  mean min-Tanimoto-distance(binder, decoys) = {avg_min_dist:.3f}")
        print(f"  mean mean-Tanimoto-distance(binder, decoys) = {avg_mean_dist:.3f}")

        # ----- (2) Predicted pKd variance -----
        binder_preds = score_many(model, tok, seq, binder_smiles, label="binders")
        decoy_preds = score_many(model, tok, seq, matched, label="matched decoys")
        all_preds = binder_preds + decoy_preds
        sd_all = pstdev(all_preds) if len(all_preds) > 1 else 0.0
        sd_bind = pstdev(binder_preds) if len(binder_preds) > 1 else 0.0
        sd_dec = pstdev(decoy_preds) if len(decoy_preds) > 1 else 0.0
        sep = (sum(binder_preds) / len(binder_preds)) - (sum(decoy_preds) / len(decoy_preds))
        print(f"  std(predicted pKd) over binder+decoy = {sd_all:.3f}")
        print(f"  std(binder preds) = {sd_bind:.3f}; std(decoy preds) = {sd_dec:.3f}")
        print(f"  binder mean − decoy mean = {sep:+.3f}")

        rows.append({
            "accession": acc, "gene": gene, "class": cls, "n_pairs": n_pairs,
            "n_binders": len(binders), "n_decoys": len(matched),
            "mean_min_tanimoto_dist_binder_to_decoy": round(avg_min_dist, 3),
            "mean_mean_tanimoto_dist_binder_to_decoy": round(avg_mean_dist, 3),
            "std_predicted_pkd_all": round(sd_all, 3),
            "std_predicted_pkd_binders": round(sd_bind, 3),
            "std_predicted_pkd_decoys": round(sd_dec, 3),
            "binder_minus_decoy_mean_pkd": round(sep, 3),
            "auroc_matched_ceiling": m["auc_matched"],
            "auroc_random_ceiling": m["auc_random"],
            "diversity_prior": m["diversity"],
        })

    # ----- Cross-target correlations -----
    auc_m = [r["auroc_matched_ceiling"] for r in rows]
    auc_r = [r["auroc_random_ceiling"] for r in rows]
    min_d = [r["mean_min_tanimoto_dist_binder_to_decoy"] for r in rows]
    mean_d = [r["mean_mean_tanimoto_dist_binder_to_decoy"] for r in rows]
    sd_all = [r["std_predicted_pkd_all"] for r in rows]
    div = [r["diversity_prior"] for r in rows]
    sep_pkd = [r["binder_minus_decoy_mean_pkd"] for r in rows]

    res = {
        "rho_min_decoy_dist_vs_auc_matched": round(datafit.spearman(min_d, auc_m), 3),
        "rho_min_decoy_dist_vs_auc_random":  round(datafit.spearman(min_d, auc_r), 3),
        "rho_mean_decoy_dist_vs_auc_matched": round(datafit.spearman(mean_d, auc_m), 3),
        "rho_std_predicted_pkd_vs_auc_matched": round(datafit.spearman(sd_all, auc_m), 3),
        "rho_std_predicted_pkd_vs_auc_random":  round(datafit.spearman(sd_all, auc_r), 3),
        "rho_sep_pkd_vs_auc_matched": round(datafit.spearman(sep_pkd, auc_m), 3),
        "rho_diversity_vs_min_decoy_dist": round(datafit.spearman(div, min_d), 3),
        "rho_diversity_vs_std_pkd": round(datafit.spearman(div, sd_all), 3),
    }

    print("\n" + "=" * 70)
    print("MECHANISM SUMMARY (Spearman across 6 targets)")
    print("=" * 70)
    for k, v in res.items():
        print(f"  {k:50s} = {v:+.3f}")

    # Heuristic verdict
    decoy_explains = abs(res["rho_min_decoy_dist_vs_auc_matched"]) > 0.7
    pkd_explains = abs(res["rho_std_predicted_pkd_vs_auc_matched"]) > 0.7

    verdict = []
    if decoy_explains:
        verdict.append(f"DECOY-DISTANCE explains AUROC (ρ={res['rho_min_decoy_dist_vs_auc_matched']:+.2f}) — narrow binder sets have decoys further away by construction")
    if pkd_explains:
        verdict.append(f"PREDICTED-PKD VARIANCE explains AUROC (ρ={res['rho_std_predicted_pkd_vs_auc_matched']:+.2f}) — head produces wider predicted ranges on some targets")
    if not verdict:
        verdict.append("Neither candidate mechanism explains the bimodality on its own (|ρ| < 0.7 for both). Pattern remains open.")

    print("\nVerdict: " + " | ".join(verdict))

    out = {"timestamp": ts, "checkpoint": "dti_bindingdb_pkd_peer", "device": dev,
           "per_target": rows, "cross_target_spearman": res, "verdict": verdict}
    out_path = REPO / "results" / f"datafit_mechanism_probe_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
