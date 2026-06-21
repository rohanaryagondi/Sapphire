"""Phase 3 — test pgk2_del_cdd IN-DISTRIBUTION on its own CACHE #7 PGK2 DEL data.

Our WDR91 number (AUROC 0.63) was out-of-distribution (DEL-derived ChEMBL actives vs an
ASMS-style head). Here we test the PGK2 head on the EXACT public DEL data it was built around:
CACHE Challenge #7 "DEL_hit_candidates_1.csv" = 1388 hPGK2 DEL hits with read counts (count_PGK2).

Two tests:
  A) hits vs drug-like decoys -> AUROC (OPTIMISTIC upper bound: the model was likely trained on
     these exact hits, so this is closer to a train-set check than generalization).
  B) FAITHFUL in-distribution metric: does the model's P(active) track the DEL read count
     (count_PGK2)? Spearman over the 1388 hits + mean score of high-count vs low-count hits.
     This is confound-free (all are DEL hits; only the enrichment magnitude differs).

Readout: generative binder_prob with the <PGK2_DEL> task token (validated approach).
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_pgk2_indist.py
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


def rankdata(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5; vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    hits = list(csv.DictReader(open(REPO / "data" / "pgk2" / "DEL_hit_candidates_1.csv")))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    print(f"PGK2 DEL hits: {len(hits)} | decoys: {len(decoys)}")

    model, tok, task, dev = load_target_model("pgk2_del")
    print(f"loaded pgk2_del_cdd on {dev}, task token <{task}>")

    hit_scores, counts = [], []
    for i, r in enumerate(hits):
        hit_scores.append(binder_prob(model, tok, r["SMILES"], task=task))
        counts.append(int(r["count_PGK2"]))
        if (i + 1) % 200 == 0:
            print(f"  hits {i+1}/{len(hits)}")
    dec_scores = []
    for i, d in enumerate(decoys):
        dec_scores.append(binder_prob(model, tok, d["smiles"], task=task))
        if (i + 1) % 200 == 0:
            print(f"  decoys {i+1}/{len(decoys)}")

    # Test A: hits vs decoys
    y = [1] * len(hit_scores) + [0] * len(dec_scores)
    rocA = auroc(y, hit_scores + dec_scores)
    # Test B: graded within-hit vs DEL count
    spB = spearman(hit_scores, counts)
    # high vs low count separation
    thr = sorted(counts)[int(len(counts) * 0.9)]  # top-decile count threshold
    hi = [s for s, c in zip(hit_scores, counts) if c >= max(thr, 7)]
    lo = [s for s, c in zip(hit_scores, counts) if c <= 5]
    sep = (median(hi) - median(lo)) if hi and lo else float("nan")
    rocB = auroc([1] * len(hi) + [0] * len(lo), hi + lo) if hi and lo else float("nan")

    summary = {
        "timestamp": ts, "target": "PGK2", "data": "CACHE #7 DEL_hit_candidates_1.csv",
        "readout": f"generative P(<1>) via <{task}>",
        "n_hits": len(hit_scores), "n_decoys": len(dec_scores),
        "A_auroc_hits_vs_decoys": round(rocA, 4),
        "A_note": "optimistic upper bound (likely train-set overlap)",
        "B_spearman_score_vs_DELcount": round(spB, 3),
        "B_auroc_highcount_vs_lowcount": round(rocB, 4) if rocB == rocB else None,
        "B_n_highcount": len(hi), "B_n_lowcount(=5)": len(lo),
        "B_median_score_high": round(median(hi), 5) if hi else None,
        "B_median_score_low": round(median(lo), 5) if lo else None,
        "B_note": "faithful in-distribution: does score track DEL enrichment (confound-free)",
    }
    (REPO / "results" / f"phase3_pgk2_indist_{ts}.json").write_text(json.dumps(summary, indent=2))
    print("\n===== PGK2 head, in-distribution (CACHE #7 DEL data) =====")
    print(f"  A) hits vs decoys AUROC = {rocA:.4f}  (optimistic; likely train overlap)")
    print(f"  B) Spearman(score, DEL count) = {spB:+.3f}  (faithful in-dist signal)")
    print(f"     high-count vs low-count AUROC = {rocB:.4f}  "
          f"(n_hi={len(hi)} count>={max(thr,7)}, n_lo={len(lo)} count=5)")
    print(f"     median score: high-count {median(hi) if hi else '?'} vs low-count {median(lo) if lo else '?'}")
    print(f"\nwrote results/phase3_pgk2_indist_{ts}.json")


if __name__ == "__main__":
    main()
