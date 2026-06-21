"""1d-(a) — mTOR kinase-domain window re-test.

The ceiling run (`experiments/datafit_ceiling.py`) found mTOR collapses on MW-matched
decoys (AUROC 0.56) and inverts off-target (Δ −1.12). The obvious suspect is the
1250-aa truncation: mTOR is 2549 aa and its kinase domain sits at ~aa 2182–2516,
*outside* the truncation window — the head reads HEAT-repeat / FAT / FRB regions
instead of the active site.

This experiment re-scores the same mTOR binders + decoys against the kinase-domain
window only (aa 1975–2549, the FRB+kinase region that fits under 1250 aa). If the
AUROC rises substantially, mTOR's failure was truncation; if it stays at ~0.56, the
model itself cannot model mTOR binding (the next BRAF — a top-10 target it can't
learn). One-script answer.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/datafit_mtor_window.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver import datafit  # noqa: E402
from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_M, PEER_S = 6.286291085593906, 1.5422950906208512

MTOR_ACC = "P42345"
# Kinase domain in MTOR (UniProt P42345 features): ~aa 2182-2516.
# FRB domain (rapamycin/FKBP12 binding): ~aa 2025-2114.
# We test two windows: kinase-only (2099-2549) and FRB+kinase (1975-2549).
# Both fit under the 1250-aa cap so the head sees them in full.
WINDOWS = {
    "full_truncated_1250":  (None, None),     # full sequence (will be truncated to 1250)
    "frb_kinase_1975_2549": (1974, 2549),
    "kinase_2099_2549":     (2098, 2549),
}

PKD_THRESHOLD = 7.0
N_BINDERS = 30
N_MATCHED_PER_BINDER = 3
MW_TOL = 50.0
SEED = 42


def score_many(model, tok, seq, smiles_list, label=""):
    preds = []
    t0 = time.time()
    for smi in smiles_list:
        try:
            preds.append(predict_pkd(model, tok, seq, smi, PEER_M, PEER_S))
        except Exception as e:  # noqa: BLE001
            print(f"    [warn] skipped {label}: {e}")
    dt = time.time() - t0
    print(f"    {label}: scored {len(preds)}/{len(smiles_list)} in {dt:.1f}s")
    return preds


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"PEER DTI on {dev}\n")

    full_seq = fetch_uniprot_sequence(MTOR_ACC)
    print(f"mTOR full sequence: {len(full_seq)} aa")

    # Reuse exactly the same binders + matched decoys as the ceiling run so the
    # AUROC comparison is apples-to-apples.
    binders = datafit.get_binders(MTOR_ACC, pkd_threshold=PKD_THRESHOLD, n_max=N_BINDERS)
    binder_smiles = [s for s, _ in binders]
    matched_decoys = datafit.sample_matched_decoys(
        MTOR_ACC, binder_smiles, n_per_binder=N_MATCHED_PER_BINDER, mw_tol=MW_TOL, seed=SEED
    )
    print(f"binders: {len(binders)}; matched decoys: {len(matched_decoys)}")

    results = {}
    for name, (lo, hi) in WINDOWS.items():
        if lo is None:
            seq = full_seq
            wlen = len(full_seq)
            note = f"full ({wlen} aa, head truncates to 1250)"
        else:
            seq = full_seq[lo:hi]
            wlen = len(seq)
            note = f"aa {lo+1}-{hi} ({wlen} aa, fully visible)"
        print(f"\n=== window: {name} -- {note} ===")
        binder_preds = score_many(model, tok, seq, binder_smiles, label=f"{name}/binders")
        decoy_preds = score_many(model, tok, seq, matched_decoys, label=f"{name}/decoys")
        auc = datafit.auroc(binder_preds, decoy_preds)
        sep = (sum(binder_preds) / len(binder_preds)) - (sum(decoy_preds) / len(decoy_preds))
        print(f"  AUROC vs matched decoys: {auc:.3f}   sep (binder mean − decoy mean): {sep:+.3f} pKd")
        results[name] = {
            "window": [lo, hi],
            "window_len": wlen,
            "note": note,
            "auroc_matched": round(auc, 3),
            "separation_pkd": round(sep, 3),
            "mean_binder_pkd": round(sum(binder_preds) / len(binder_preds), 3),
            "mean_decoy_pkd": round(sum(decoy_preds) / len(decoy_preds), 3),
            "binder_preds": [round(x, 3) for x in binder_preds],
            "decoy_preds": [round(x, 3) for x in decoy_preds],
        }

    out = {
        "timestamp": ts,
        "accession": MTOR_ACC,
        "checkpoint": "dti_bindingdb_pkd_peer",
        "norm_constants": [PEER_M, PEER_S],
        "device": dev,
        "n_binders": len(binders),
        "n_matched_decoys": len(matched_decoys),
        "results": results,
    }
    out_path = REPO / "results" / f"datafit_mtor_window_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {out_path}")

    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    base = results["full_truncated_1250"]["auroc_matched"]
    for name, r in results.items():
        if name == "full_truncated_1250":
            continue
        diff = r["auroc_matched"] - base
        verdict = "TRUNCATION EXPLAINS IT" if diff >= 0.20 else \
                  "TRUNCATION PARTIALLY EXPLAINS IT" if diff >= 0.10 else \
                  "TRUNCATION DOES NOT EXPLAIN IT — model limit"
        print(f"  {name}: AUROC {base:.2f} -> {r['auroc_matched']:.2f}  Δ={diff:+.2f}  {verdict}")


if __name__ == "__main__":
    main()
