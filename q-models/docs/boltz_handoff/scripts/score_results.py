"""Score a Boltz results.json against the binder/decoy labels in the input JSON.

Computes per-target binder-vs-decoy AUROC + off-target Δ. Designed to drop
into the existing Quiver MAMMAL/ConPLex comparison cleanly:

| model                 | Nav1.8 AUROC | mTOR AUROC |
| MAMMAL (PEER)         | 0.43         | 0.54       |
| ConPLex (zero-shot)   | 0.39         | 0.58       |
| ... ConPLex full Nav  | mean 0.44, 0/9 above 0.60 |
| Boltz-2 (this script) | <your numbers>            |

The bar to clear: AUROC ≥ 0.70 on Nav1.8 OR any Nav paralog. If Boltz-2 hits
that, it's the first off-the-shelf DTI tool that actually works on Nav for
Quiver — meaningful, publishable.

USAGE:
    python score_results.py <boltz_results.json> [--complexes <input.json>]

If --complexes isn't passed, labels come from the records inside results.json
(boltz_runner.py preserves them).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


def auroc(pos_scores, neg_scores):
    """Mann-Whitney AUROC with tie-handling. Returns nan if either is empty."""
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for p in pos_scores:
        for n in neg_scores:
            if p > n: wins += 1.0
            elif p == n: wins += 0.5
    return wins / (len(pos_scores) * len(neg_scores))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_json", help="Path to boltz_runner.py's results.json")
    ap.add_argument("--complexes", help="Optional: input complexes.json for labels",
                    default=None)
    args = ap.parse_args()

    data = json.load(open(args.results_json))
    rows = data.get("complexes", data) if isinstance(data, dict) else data

    # If labels are missing on rows, pull from --complexes file.
    if args.complexes and any("label" not in r for r in rows):
        cx = json.load(open(args.complexes))
        labels = {c["name"]: c["label"] for c in cx}
        for r in rows:
            r.setdefault("label", labels.get(r["name"]))

    # Group by target. Compute per-target binder-vs-decoy AUROC.
    by_target = defaultdict(lambda: {"pos": [], "neg": [], "drugs": {}})
    n_skipped = 0
    for r in rows:
        prob = r.get("prob_binder")
        if prob is None:
            n_skipped += 1
            continue
        t = r.get("target") or r["name"].split("_")[0]
        d = r.get("drug")  or r["name"].split("_", 1)[-1]
        by_target[t]["drugs"][d] = prob
        label = r.get("label")
        if label == 1:
            by_target[t]["pos"].append(prob)
        elif label == 0:
            by_target[t]["neg"].append(prob)

    if n_skipped:
        print(f"# Skipped {n_skipped} complexes with prob_binder=None (Boltz failed)")
    print()
    print(f"{'target':10s} {'n_pos':>5s} {'n_neg':>5s} {'AUROC':>8s}  "
          f"{'mean_pos':>10s} {'mean_neg':>10s} {'sep':>8s}")
    print("-" * 70)
    overall = []
    for t in sorted(by_target):
        d = by_target[t]
        a = auroc(d["pos"], d["neg"])
        sep_str = "—"
        mp_str = mn_str = "—"
        if d["pos"]:
            mp_str = f"{mean(d['pos']):.3f}"
        if d["neg"]:
            mn_str = f"{mean(d['neg']):.3f}"
        if d["pos"] and d["neg"]:
            sep_str = f"{mean(d['pos'])-mean(d['neg']):+.3f}"
        print(f"{t:10s} {len(d['pos']):>5d} {len(d['neg']):>5d} "
              f"{a:>8.3f}  {mp_str:>10s} {mn_str:>10s} {sep_str:>8s}")
        if a == a:  # not nan
            overall.append((t, a))

    # Off-target matrix: drug x target (only useful if same drugs hit multiple targets)
    print()
    print("=" * 70)
    print("Off-target matrix (drug × target, prob_binder values)")
    print("=" * 70)
    all_drugs = sorted({d for t in by_target.values() for d in t["drugs"]})
    targets = sorted(by_target)
    header = f"{'drug':18s}  " + " ".join(f"{t:>9s}" for t in targets)
    print(header)
    print("-" * len(header))
    for drug in all_drugs:
        row = [by_target[t]["drugs"].get(drug) for t in targets]
        cells = " ".join(f"{(v if v is not None else float('nan')):>9.3f}" if v is not None else "        —" for v in row)
        print(f"{drug:18s}  {cells}")

    # Headline
    print()
    print("=" * 70)
    print("VERDICT vs baselines")
    print("=" * 70)
    BAR = 0.70
    n_clear = sum(1 for _, a in overall if a >= BAR)
    print(f"  Targets with binder-vs-decoy AUROC ≥ {BAR}: {n_clear} / {len(overall)}")
    if overall:
        mean_auc = mean([a for _, a in overall])
        print(f"  Mean AUROC across targets:           {mean_auc:.3f}")
    print()
    print("  Compare to:")
    print("    MAMMAL Nav1.8 AUROC = 0.43 (chance)")
    print("    ConPLex Nav1.8 AUROC = 0.39 (chance)")
    print("    ConPLex Nav family mean = 0.44, 0/9 above 0.60")
    if any(t == "Nav1.8" and a >= BAR for t, a in overall):
        print("\n  *** Boltz-2 clears the Nav1.8 bar — this is the result Quiver wants ***")


if __name__ == "__main__":
    main()
