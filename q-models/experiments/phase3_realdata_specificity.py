"""Phase 3 — per-target heads tested with REAL binders only (no decoys).

Random decoys conflate "binds my target" with "looks like a screening compound." Here every
molecule is a real, experimentally-identified binder of a real protein, so the tests isolate
TARGET-SPECIFICITY:

  W    = 27 WDR91 actives (ChEMBL CHEMBL5465256 / Ahmad 2023 DEL paper)
  P    = PGK2 DEL hits (CACHE #7, real DEL-enriched; subsampled by read count for speed)
  PGK1 = 99 PGK1 ligands (ChEMBL CHEMBL2886) — PGK2's homolog / selectivity counter-target

Tests:
  1. Cross-target (real-vs-real): WDR91 head should score W > P; PGK2 head should score P > W.
  2. Homolog selectivity (real-vs-real): PGK2 head should score P > PGK1.
  3. Paired specificity: for each real binder, does its COGNATE head score it higher than the
     other target's head? (each molecule is its own control — the cleanest possible test)

Readout: generative binder_prob (P(<1>)@pos1) with the head's task token. One model in memory
at a time.
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_realdata_specificity.py [N_PGK2]
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

from mammal_quiver.wdr91 import binder_prob, load_target_model


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def main():
    n_pgk2 = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    W = [a["smiles"] for a in json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))]
    pgk2_rows = list(csv.DictReader(open(REPO / "data" / "pgk2" / "DEL_hit_candidates_1.csv")))
    pgk2_rows.sort(key=lambda r: -int(r["count_PGK2"]))           # stratify: keep strongest hits
    P = [r["SMILES"] for r in pgk2_rows[:: max(1, len(pgk2_rows) // n_pgk2)]][:n_pgk2]
    PGK1 = [m["smiles"] for m in json.load(open(REPO / "data" / "pgk2" / "pgk1_chembl_ligands.json"))]
    print(f"WDR91 actives={len(W)} | PGK2 hits={len(P)} | PGK1 ligands={len(PGK1)}")

    # score every set with BOTH heads (load one model at a time)
    scores = {}  # scores[head][set] = list
    for head_key, task_for in (("wdr91", "wdr91"), ("pgk2_del", "pgk2_del")):
        model, tok, task, dev = load_target_model(head_key)
        print(f"\n[{head_key}] loaded on {dev}, task <{task}> — scoring W, P, PGK1 ...")
        scores[head_key] = {}
        for name, mols in (("W", W), ("P", P), ("PGK1", PGK1)):
            vals = []
            for i, smi in enumerate(mols):
                vals.append(binder_prob(model, tok, smi, task=task))
                if (i + 1) % 200 == 0:
                    print(f"    {head_key} {name} {i+1}/{len(mols)}")
            scores[head_key][name] = vals
        del model

    wdr, pgk = scores["wdr91"], scores["pgk2_del"]

    # 1. cross-target
    t1 = auroc([1] * len(wdr["W"]) + [0] * len(wdr["P"]), wdr["W"] + wdr["P"])   # WDR91 head: W>P?
    t2 = auroc([1] * len(pgk["P"]) + [0] * len(pgk["W"]), pgk["P"] + pgk["W"])   # PGK2 head: P>W?
    # 2. homolog selectivity
    t3 = auroc([1] * len(pgk["P"]) + [0] * len(pgk["PGK1"]), pgk["P"] + pgk["PGK1"])  # PGK2 head: P>PGK1?
    # 3. paired specificity (each molecule its own control)
    w_pref = sum(a > b for a, b in zip(wdr["W"], pgk["W"])) / len(W)   # WDR91 actives: wdr head > pgk head?
    p_pref = sum(a > b for a, b in zip(pgk["P"], wdr["P"])) / len(P)   # PGK2 hits: pgk head > wdr head?

    summary = {
        "timestamp": ts, "n_W": len(W), "n_P": len(P), "n_PGK1": len(PGK1),
        "cross_target": {
            "wdr91_head_AUROC_W_over_P": round(t1, 4),
            "pgk2_head_AUROC_P_over_W": round(t2, 4),
        },
        "homolog_selectivity": {"pgk2_head_AUROC_P_over_PGK1": round(t3, 4)},
        "paired_specificity": {
            "frac_WDR91actives_prefer_wdr91head": round(w_pref, 3),
            "frac_PGK2hits_prefer_pgk2head": round(p_pref, 3),
        },
        "median_scores": {
            "wdr91_head": {k: round(median(v), 5) for k, v in wdr.items()},
            "pgk2_head": {k: round(median(v), 5) for k, v in pgk.items()},
        },
    }
    (REPO / "results" / f"phase3_realdata_specificity_{ts}.json").write_text(json.dumps(summary, indent=2))

    print("\n================= REAL-DATA target specificity (no decoys) =================")
    print(f"1. Cross-target (real binders of one protein vs another):")
    print(f"   WDR91 head: WDR91 actives > PGK2 hits   AUROC = {t1:.3f}  ({'PASS' if t1>0.5 else 'fail'})")
    print(f"   PGK2  head: PGK2 hits > WDR91 actives    AUROC = {t2:.3f}  ({'PASS' if t2>0.5 else 'fail'})")
    print(f"2. Homolog selectivity (real counter-target):")
    print(f"   PGK2  head: PGK2 hits > PGK1 ligands     AUROC = {t3:.3f}  ({'PASS' if t3>0.5 else 'fail'})")
    print(f"3. Paired specificity (each molecule its own control — cognate head higher?):")
    print(f"   {w_pref*100:.0f}% of WDR91 actives score higher on the WDR91 head than the PGK2 head")
    print(f"   {p_pref*100:.0f}% of PGK2 hits   score higher on the PGK2 head than the WDR91 head")
    print(f"\nmedian scores: {summary['median_scores']}")
    print(f"wrote results/phase3_realdata_specificity_{ts}.json")


if __name__ == "__main__":
    main()
