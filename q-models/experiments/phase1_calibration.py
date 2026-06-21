"""Phase 1 — Calibration on grounded ground truth.

Headline test from the 5/28 meeting: Jernabix -> Nav1.8.
  Jernabix == Journavx == suzetrigine (VX-548), a SELECTIVE Nav1.8 inhibitor.

This script runs the parts that need no external affinity DB:
  1. suzetrigine -> Nav1.8 (SCN10A)            [the named known binder]
  2. negative controls:
       - suzetrigine x unrelated proteins        (drug held fixed)
       - unrelated drugs x Nav1.8                 (target held fixed)
  3. pass/fail per success_criteria.md:
       PASS  = suzetrigine->Nav1.8 pKd is higher than every negative-control pair
       FAIL  = real binder scores at or below the random pairs

The 5-10 pair Spearman-correlation test uses real experimental affinities and
lives in scripts/phase1_correlation.py (reads data/ground_truth_dti.csv).

Caveat recorded automatically: Nav1.8 is 1960 aa but the DTI head truncates the
target to 1250 residues, so the C-terminal ~710 residues are not seen.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1_calibration.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

from mammal_quiver.dti import DTI_MODEL_ID, load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import DRUGS, TARGETS, fetch_uniprot_sequence  # noqa: E402

TARGET_MAX_SEQ_LENGTH = 1250  # from DtiBindingdbKdTask.data_preprocessing default


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = REPO / "results"
    results_dir.mkdir(exist_ok=True)

    model, tok, device = load_dti_model()
    print(f"loaded {DTI_MODEL_ID} on {device}")

    # Resolve sequences
    seqs = {name: fetch_uniprot_sequence(acc) for name, (acc, _g, _n) in TARGETS.items()}
    nav18 = seqs["Nav1.8"]
    truncation_note = (
        f"Nav1.8 length={len(nav18)} aa; DTI head truncates target to "
        f"{TARGET_MAX_SEQ_LENGTH} aa -> {max(0, len(nav18) - TARGET_MAX_SEQ_LENGTH)} "
        f"C-terminal residues not seen by the model."
    )
    print(truncation_note)

    suze = DRUGS["suzetrigine"]
    records = []

    def run(drug_name, drug_smiles, target_name, target_seq, kind):
        t0 = time.time()
        pkd = predict_pkd(model, tok, target_seq, drug_smiles)
        dt = time.time() - t0
        rec = {
            "kind": kind,
            "drug": drug_name,
            "target": target_name,
            "target_len": len(target_seq),
            "pred_pKd": round(pkd, 4),
            "infer_s": round(dt, 2),
        }
        records.append(rec)
        print(f"  [{kind:9s}] {drug_name:12s} x {target_name:8s}  pKd={pkd:7.3f}  ({dt:.1f}s)")
        return pkd

    print("\n--- named test ---")
    named = run("suzetrigine", suze, "Nav1.8", nav18, "named")

    print("\n--- negative controls: suzetrigine x unrelated proteins ---")
    for tname in [t for t in TARGETS if t != "Nav1.8"]:
        run("suzetrigine", suze, tname, seqs[tname], "neg_target")

    print("\n--- negative controls: unrelated drugs x Nav1.8 ---")
    for dname in [d for d in DRUGS if d != "suzetrigine"]:
        run(dname, DRUGS[dname], "Nav1.8", nav18, "neg_drug")

    negatives = [r["pred_pKd"] for r in records if r["kind"].startswith("neg")]
    max_neg = max(negatives)
    verdict = "PASS" if named > max_neg else "FAIL"
    margin = named - max_neg

    summary = {
        "timestamp": ts,
        "model": DTI_MODEL_ID,
        "device": device,
        "named_test": {"drug": "suzetrigine (Jernabix/Journavx/VX-548)", "target": "Nav1.8 (SCN10A)", "pred_pKd": round(named, 4)},
        "negatives_pKd": negatives,
        "max_negative_pKd": max_neg,
        "margin_over_max_negative": round(margin, 4),
        "verdict": verdict,
        "truncation_note": truncation_note,
        "records": records,
    }
    out_json = results_dir / f"phase1_calibration_{ts}.json"
    out_json.write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 60)
    print(f"VERDICT: {verdict}  (named pKd={named:.3f}, max negative={max_neg:.3f}, margin={margin:+.3f})")
    print(f"saved -> {out_json}")
    print("=" * 60)


if __name__ == "__main__":
    main()
