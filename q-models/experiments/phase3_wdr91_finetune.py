"""Phase 3 — does FINE-TUNED MAMMAL do target-specific binder discrimination?

The decisive test for Quiver (Q14: should we fine-tune per target). Off-the-shelf DTI
cannot triage candidates for a single target (Nav1.8/mTOR binder-vs-decoy AUROC ~0.5).
IBM's `wdr91_asms` head is MAMMAL fine-tuned on ONE target's screening data. If it ranks
known WDR91 binders above drug-like decoys, fine-tuning is the path around the DTI failure.

Test set:
  actives  = 27 WDR91 binders from ChEMBL (target CHEMBL5465256), reported in the WDR91
             DEL paper (Ahmad et al., J Med Chem 2023, doi:10.1021/acs.jmedchem.3c01471,
             PMID 37996079). 18 have a measured SPR Kd (6-99 uM, pKd 4.0-5.22).
  decoys   = 500 random drug-like ChEMBL molecules (MW 250-500, 0 Ro5 violations).

CAVEAT (honesty): the head is `_asms` (affinity-selection MS); the ChEMBL actives are
DEL-derived. Overlap with the (unpublished) ASMS training set is UNKNOWN, so a positive
result is an existence proof that the fine-tuned head encodes WDR91 SAR — not proof of
generalization to novel chemotypes. The within-active Kd correlation below guards against
trivial "one chemotype = high score" memorization: graded affinity ranking needs real signal.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase3_wdr91_finetune.py
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

from mammal_quiver.wdr91 import load_wdr91_model, score_smiles


# ----------------------------- small stats helpers -----------------------------
def auroc(y_true, y_score):
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))  # == Mann-Whitney U / (n_pos*n_neg)


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(xs, p):
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    return s[lo] if lo + 1 >= len(s) else s[lo] + (k - lo) * (s[lo + 1] - s[lo])


def enrichment_factor(y_true, y_score, frac):
    order = sorted(range(len(y_score)), key=lambda i: -y_score[i])
    n_top = max(1, int(round(len(order) * frac)))
    top = order[:n_top]
    hits_top = sum(y_true[i] for i in top)
    base = sum(y_true) / len(y_true)
    return (hits_top / n_top) / base, hits_top, n_top


def mol_weight(smi):
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        m = Chem.MolFromSmiles(smi)
        return Descriptors.MolWt(m) if m else None
    except Exception:
        return None


# ----------------------------------- main -----------------------------------
def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    print(f"actives={len(actives)} (measured Kd: {sum(1 for a in actives if a['kd_nM'])}) "
          f"| decoys={len(decoys)}")

    model, tok, dev = load_wdr91_model()
    print(f"loaded wdr91_asms on {dev}; scoring {len(actives)+len(decoys)} molecules...")

    for a in actives:
        a["score"] = score_smiles(model, tok, a["smiles"])
    for i, d in enumerate(decoys):
        d["score"] = score_smiles(model, tok, d["smiles"])
        if (i + 1) % 100 == 0:
            print(f"  decoys {i+1}/{len(decoys)}")

    act_scores = [a["score"] for a in actives]
    dec_scores = [d["score"] for d in decoys]
    y_true = [1] * len(actives) + [0] * len(decoys)
    y_score = act_scores + dec_scores

    # measured-Kd subset (cleaner binders, enables affinity correlation)
    kd = [a for a in actives if a["pchembl"] is not None]
    kd_scores = [a["score"] for a in kd]
    kd_pchembl = [a["pchembl"] for a in kd]
    auroc_kd = auroc([1] * len(kd) + [0] * len(decoys), kd_scores + dec_scores)

    ef5 = enrichment_factor(y_true, y_score, 0.05)
    ef10 = enrichment_factor(y_true, y_score, 0.10)
    dec_p95 = percentile(dec_scores, 95)
    frac_above_p95 = sum(s > dec_p95 for s in act_scores) / len(act_scores)
    sp_kd = spearman(kd_scores, kd_pchembl)

    # property sanity check: are actives just bigger than decoys?
    act_mw = [w for w in (mol_weight(a["smiles"]) for a in actives) if w]
    dec_mw = [w for w in (mol_weight(d["smiles"]) for d in decoys) if w]

    summary = {
        "timestamp": ts,
        "checkpoint": "michalozeryflato/...ma-ted-458m.wdr91_asms",
        "n_actives": len(actives), "n_actives_measured_kd": len(kd), "n_decoys": len(decoys),
        "auroc_all_actives": round(auroc(y_true, y_score), 4),
        "auroc_measured_kd_actives": round(auroc_kd, 4),
        "median_score_active": round(median(act_scores), 4),
        "median_score_decoy": round(median(dec_scores), 4),
        "decoy_p95": round(dec_p95, 4),
        "frac_actives_above_decoy_p95": round(frac_above_p95, 3),
        "enrichment_factor_top5pct": [round(ef5[0], 2), f"{ef5[1]}/{ef5[2]}"],
        "enrichment_factor_top10pct": [round(ef10[0], 2), f"{ef10[1]}/{ef10[2]}"],
        "spearman_score_vs_pKd_within_actives": round(sp_kd, 3),
        "mw_active_median": round(median(act_mw), 1) if act_mw else None,
        "mw_decoy_median": round(median(dec_mw), 1) if dec_mw else None,
        "per_active": sorted(
            [{"id": a["molecule_chembl_id"], "pKd": a["pchembl"], "kd_nM": a["kd_nM"],
              "score": round(a["score"], 4)} for a in actives],
            key=lambda r: -r["score"]),
    }
    out = REPO / "results" / f"phase3_wdr91_finetune_{ts}.json"
    out.write_text(json.dumps(summary, indent=2))

    print("\n================= WDR91 fine-tuned binder discrimination =================")
    print(f"AUROC (all 27 actives vs 500 decoys) : {summary['auroc_all_actives']}")
    print(f"AUROC (18 measured-Kd actives)        : {summary['auroc_measured_kd_actives']}")
    print(f"median score  active {summary['median_score_active']:+.4f}  vs  "
          f"decoy {summary['median_score_decoy']:+.4f}")
    print(f"actives above decoy 95th pctile       : {frac_above_p95*100:.0f}%  "
          f"(decoy p95={dec_p95:+.4f})")
    print(f"enrichment factor  top-5%={ef5[0]:.1f}x ({ef5[1]}/{ef5[2]})   "
          f"top-10%={ef10[0]:.1f}x ({ef10[1]}/{ef10[2]})")
    print(f"Spearman(score, pKd) within actives   : {sp_kd:+.3f}   "
          f"(control vs chemotype-only memorization)")
    print(f"MW median  active {summary['mw_active_median']}  vs  decoy {summary['mw_decoy_median']}  "
          f"(overlap => separation isn't just size)")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
