"""Compare Test 3 — Quiver targets: rank known actives above decoys (Nav1.8, mTOR).

THE DECISIVE TEST. MAMMAL's off-the-shelf DTI gives ≈ chance separation here
(Nav1.8 +0.00, mTOR +0.10 — phase2b). Pre-registered win condition: a challenger
beats MAMMAL iff its actives-vs-decoys AUROC ≥ 0.70 with a 95% CI lower bound > 0.5
on Nav1.8 OR mTOR — i.e. it provides triage signal where MAMMAL has none.

Reuses phase2b's actives/decoys + PubChem SMILES fetcher. Metric = AUROC (scale-free,
replaces phase2b's raw-pKd separation so ConPLex is comparable) + within-model
z-separation as a secondary continuity column. Boltz-2 = N/A (a per-pair oracle,
over the $2 screening budget). n is small (≤7 actives vs 4 decoys) → wide CIs; we
report them honestly.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare3_quiver_targets.py
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
sys.path.insert(0, str(REPO / "experiments"))

from baselines import common, conplex  # noqa: E402
from baselines.mammal_heads import load_dti_peer, dti_scores  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

TARGET_PANELS = [
    ("Nav1.8", "Q9Y5Y9", "NAV_BLOCKERS"),
    ("mTOR", "P42345", "MTOR_INHIB"),
]
WIN_AUROC, WIN_CI_LO = 0.70, 0.50  # pre-registered decisive thresholds


def build_panel(active_attr):
    import phase2b_quiver_targets as p2b
    actives = getattr(p2b, active_attr)
    decoys = p2b.DECOYS
    rows, labels = [], []
    for n in actives:
        s = p2b.smiles(n)
        if s:
            rows.append({"name": n, "smiles": s, "label": 1}); labels.append(1)
    for n in decoys:
        s = p2b.smiles(n)
        if s:
            rows.append({"name": n, "smiles": s, "label": 0}); labels.append(0)
    return rows, labels


def score_cell(name, labels, scores, mammal_scores=None):
    a = common.auroc(labels, scores)
    lo, hi = common.auroc_ci(labels, scores)
    cell = {"auroc": round(a, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "z_separation": round(common.z_separation(scores, labels), 4),
            "verdict": common.auroc_verdict(a),
            "beats_mammal_rule": bool(a >= WIN_AUROC and lo > WIN_CI_LO)}
    if mammal_scores is not None and name != "MAMMAL":
        d, dlo, dhi, p = common.paired_auroc_diff_ci(labels, scores, mammal_scores)
        cell["delta_vs_mammal"] = {"d_auroc": round(d, 4), "ci95": [round(dlo, 4), round(dhi, 4)],
                                    "p_two_sided": round(p, 4), "separable": not (dlo <= 0 <= dhi)}
    return cell


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    m, tok, dev = load_dti_peer()
    print(f"[MAMMAL] PEER DTI on {dev}")

    panels = {}
    for tname, acc, attr in TARGET_PANELS:
        rows, labels = build_panel(attr)
        seq = fetch_uniprot_sequence(acc)
        pairs = [(seq, r["smiles"]) for r in rows]
        n_pos, n_neg = sum(labels), len(labels) - sum(labels)
        print(f"\n[{tname}] {n_pos} actives vs {n_neg} decoys; seq len {len(seq)}")

        scores = {"MAMMAL": dti_scores(m, tok, pairs)}
        try:
            scores["ConPLex"] = conplex.score_batch(pairs)
        except Exception as e:  # noqa: BLE001
            print(f"  ConPLex unavailable: {e}")
            scores["ConPLex"] = None

        cells = {"MAMMAL": score_cell("MAMMAL", labels, scores["MAMMAL"])}
        if scores["ConPLex"] is not None:
            cells["ConPLex"] = score_cell("ConPLex", labels, scores["ConPLex"], scores["MAMMAL"])
        else:
            cells["ConPLex"] = {"verdict": "N/A"}
        cells["Boltz-2"] = {"verdict": "N/A — over compute budget (per-pair oracle)"}

        panels[tname] = {"n_actives": n_pos, "n_decoys": n_neg, "seq_len": len(seq),
                         "compounds": [r["name"] for r in rows], "labels": labels,
                         "cells": cells,
                         "raw_scores": {k: ([round(x, 5) for x in v] if v else None) for k, v in scores.items()}}
        for name, c in cells.items():
            if "auroc" in c:
                print(f"  {name:9s} AUROC={c['auroc']:.3f} CI{c['ci95']} z-sep={c['z_separation']:+.2f} "
                      f"{c['verdict']}{'  ** BEATS MAMMAL **' if c.get('beats_mammal_rule') else ''}")
            else:
                print(f"  {name:9s} {c['verdict']}")
    del m

    decisive = any(panels[t]["cells"].get("ConPLex", {}).get("beats_mammal_rule") for t in panels)
    report = {"timestamp": ts, "test": "quiver_targets_triage", "metric": "auroc_actives_vs_decoys",
              "bar": ">0.6 useful; decisive win = AUROC>=0.70 & CI_lo>0.5 on Nav1.8 or mTOR",
              "decisive_win_fired": decisive, "panels": panels}
    out = REPO / "results" / f"compare3_quiver_targets_{ts}.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n" + "=" * 64)
    print(f"Test 3 decisive-win (ConPLex beats MAMMAL on Nav1.8/mTOR): {decisive}")
    print(f"saved -> {out}")
    print("=" * 64)


if __name__ == "__main__":
    main()
