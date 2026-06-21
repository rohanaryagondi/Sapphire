"""Compare Test 2 — the named test: suzetrigine → Nav1.8 must beat 6 negative controls.

The control set is MAMMAL's own (mammal_quiver.sequences.TARGETS/DRUGS):
  positive : suzetrigine × Nav1.8 (SCN10A)
  negatives: suzetrigine × {CA2, DHFR, ACHE}  and  {metformin, caffeine, ibuprofen} × Nav1.8
PASS = within a model's own 7 scores, the named pair is strictly the highest.
MAMMAL FAILS this off-the-shelf. We report PASS/FAIL + the margin (named − best
negative) in within-model z-units. n=1 named pair → indicative, not a CI.

Caveat logged per model: Nav1.8 is 1956 aa. MAMMAL DTI truncates to 1250; ConPLex
applies its own cap; Boltz-2 (AWS) uses a binding-domain construct (full-length OOMs).
Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare2_named_test.py
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
sys.path.insert(0, str(REPO))

from baselines import common, conplex, boltz  # noqa: E402
from baselines.mammal_heads import load_dti_peer, dti_scores  # noqa: E402
from mammal_quiver.sequences import TARGETS, DRUGS, fetch_uniprot_sequence  # noqa: E402

# (label, drug_name, target_name) — index 0 is the named positive pair.
NAMED = ("suzetrigine→Nav1.8", "suzetrigine", "Nav1.8")
NEGATIVES = [
    ("suzetrigine→CA2", "suzetrigine", "CA2"),
    ("suzetrigine→DHFR", "suzetrigine", "DHFR"),
    ("suzetrigine→ACHE", "suzetrigine", "ACHE"),
    ("metformin→Nav1.8", "metformin", "Nav1.8"),
    ("caffeine→Nav1.8", "caffeine", "Nav1.8"),
    ("ibuprofen→Nav1.8", "ibuprofen", "Nav1.8"),
]


def build_pairs():
    rows = []
    for label, drug, tgt in [NAMED] + NEGATIVES:
        acc = TARGETS[tgt][0]
        rows.append({"label": label, "drug": drug, "target": tgt,
                     "smiles": DRUGS[drug], "seq": fetch_uniprot_sequence(acc),
                     "is_named": label == NAMED[0]})
    return rows


def evaluate(rows, scores):
    """Within-model PASS/FAIL + z-margin (named − best negative)."""
    z = common.zscore(scores)
    named_i = next(i for i, r in enumerate(rows) if r["is_named"])
    neg_z = [z[i] for i in range(len(rows)) if i != named_i]
    margin = float(z[named_i] - max(neg_z))
    return {"value": "PASS" if margin > 0 else "FAIL", "z_margin": round(margin, 3),
            "named_raw": round(float(scores[named_i]), 5),
            "max_negative_raw": round(float(max(scores[i] for i in range(len(rows)) if i != named_i)), 5),
            "per_pair": {rows[i]["label"]: round(float(scores[i]), 5) for i in range(len(rows))}}


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = build_pairs()
    pairs = [(r["seq"], r["smiles"]) for r in rows]
    print(f"named test: 1 positive + {len(NEGATIVES)} negatives; Nav1.8 len={len(rows[0]['seq'])}")

    cells = {}

    m, tok, dev = load_dti_peer()
    print(f"[MAMMAL] PEER DTI on {dev}")
    cells["MAMMAL"] = evaluate(rows, dti_scores(m, tok, pairs))
    cells["MAMMAL"]["seq_handling"] = "DTI truncates target to 1250 aa"
    del m

    try:
        print("[ConPLex] scoring ...")
        cs = conplex.score_batch(pairs)
        cells["ConPLex"] = evaluate(rows, cs)
        cells["ConPLex"]["seq_handling"] = "ConPLex internal cap"
    except Exception as e:  # noqa: BLE001
        print(f"  ConPLex unavailable: {e}")
        cells["ConPLex"] = {"value": "N/A"}

    bz = boltz.boltz_scores(pairs)
    if any(v is not None for v in bz) and all(v is not None for v in bz):
        cells["Boltz-2"] = evaluate(rows, bz)
        cells["Boltz-2"]["seq_handling"] = "binding-domain construct (AWS)"
    else:
        cells["Boltz-2"] = {"value": "N/A — pending AWS"}

    report = {"timestamp": ts, "test": "named_suze_nav18", "metric": "named_beats_all_negatives",
              "bar": "binary (named strictly > all 6 negatives)", "n_named": 1, "n_negatives": len(NEGATIVES),
              "cells": cells}
    out = REPO / "results" / f"compare2_named_test_{ts}.json"
    out.write_text(json.dumps(report, indent=2))

    print("\n" + "=" * 64)
    print("Test 2 — named test (suzetrigine→Nav1.8 vs 6 controls)")
    for name, c in cells.items():
        if c.get("value") in (None, "N/A", "N/A — pending AWS"):
            print(f"  {name:9s}  {c.get('value')}")
        else:
            print(f"  {name:9s}  {c['value']}  (z-margin {c['z_margin']:+.2f})")
    print(f"saved -> {out}")
    print("=" * 64)


if __name__ == "__main__":
    main()
