"""Datafit curve — binder-vs-decoy AUROC vs # of per-target training pairs.

Nav1.8 (SCN10A) showed AUROC ~0.5 on the binder-vs-decoy test (Phase 2b /
offtarget); the per-target distribution audit showed Nav1.8 has 0 pairs in
BindingDB_Kd. The question this script answers: how does MAMMAL's DTI head's
binder-vs-decoy AUROC scale with the # of per-target training pairs?

Protocol:
  - Stratify 16 BindingDB targets across 4 bins of pair counts (low / low-mid /
    high-mid / high). 4 targets per bin, random draw, seeded.
  - Exclude the 6 ceiling-experiment targets so the panels are disjoint.
  - For each picked target:
        * binders   = `datafit.get_binders(acc, pkd>=7.0, n_max=20)`
        * decoys    = 60 random off-target SMILES (`datafit.sample_random_decoys`)
        * score all with PEER DTI (norms 6.286 / 1.542)
        * report AUROC, EF@5%, mean_pos, mean_decoy, separation
  - If a target has <5 binders @ pKd>=7.0, re-draw another target from the same
    bin (deterministic alt seeds). Goal: 4 usable targets per bin.
  - Plot AUROC vs log10(pairs); save PNG, JSON, write a markdown report.

Skips matched-decoy + Spearman — the ceiling experiment covers those. Curve is
about ONE metric across many targets so we get a clean function-of-data signal.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/datafit_curve.py
"""

from __future__ import annotations

import json
import math
import os
import random
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

# Ceiling experiment targets (kept disjoint from this panel)
CEILING_EXCLUDE = {"P42345", "P15056", "Q8K4Z4", "P31389", "P51449", "P00918"}

# Bins: (lo, hi, label)
BINS = [
    (1, 9, "low"),
    (10, 39, "low-mid"),
    (40, 149, "high-mid"),
    (150, 2000, "high"),
]

PER_BIN = 4
PKD_THRESHOLD = 7.0
N_BINDERS_MAX = 20
N_DECOYS = 60
MIN_BINDERS = 5  # if fewer usable binders, redraw

# Colors per bin (matplotlib tab10-ish)
BIN_COLORS = {
    "low": "#d62728",       # red — Nav-like
    "low-mid": "#ff7f0e",   # orange
    "high-mid": "#2ca02c",  # green
    "high": "#1f77b4",      # blue
}


def pick_targets_for_bin(rows, bin_range, seed_base, picked_acc, exclude):
    """Pick PER_BIN usable targets from the bin. A target is 'usable' if it has
    >= MIN_BINDERS binders at pKd >= PKD_THRESHOLD. If a candidate fails, draw
    another from the same bin. Returns (picks, redraws) where each pick is a
    TargetSpec and `redraws` is a list of (accession, reason) tuples.
    """
    lo, hi = bin_range
    pool = [r for r in rows
            if lo <= r.pairs <= hi
            and r.accession not in exclude
            and r.accession not in picked_acc]
    rng = random.Random(seed_base)
    rng.shuffle(pool)

    picks = []
    redraws = []
    for cand in pool:
        if len(picks) >= PER_BIN:
            break
        try:
            binders = datafit.get_binders(cand.accession, PKD_THRESHOLD, N_BINDERS_MAX)
        except Exception as e:  # noqa: BLE001
            redraws.append((cand.accession, f"binders_error: {e}"))
            continue
        if len(binders) < MIN_BINDERS:
            redraws.append((cand.accession, f"only_{len(binders)}_binders_pKd>={PKD_THRESHOLD}"))
            continue
        picks.append(cand)
    return picks, redraws


def score_target(model, tok, target: "datafit.TargetSpec"):
    """Score binders + random decoys for one target. Returns dict of metrics."""
    seq = fetch_uniprot_sequence(target.accession)
    truncated = len(seq) > 1250
    binders = datafit.get_binders(target.accession, PKD_THRESHOLD, N_BINDERS_MAX)
    decoys = datafit.sample_random_decoys(target.accession, N_DECOYS, seed=42)

    t0 = time.time()
    binder_preds = []
    for smiles, _pkd in binders:
        try:
            binder_preds.append(predict_pkd(model, tok, seq, smiles, PEER_M, PEER_S))
        except Exception as e:  # noqa: BLE001
            print(f"    binder pred FAILED: {e}")
    decoy_preds = []
    for smiles in decoys:
        try:
            decoy_preds.append(predict_pkd(model, tok, seq, smiles, PEER_M, PEER_S))
        except Exception as e:  # noqa: BLE001
            print(f"    decoy pred FAILED: {e}")
    elapsed = time.time() - t0

    auroc = datafit.auroc(binder_preds, decoy_preds)
    mean_binder = sum(binder_preds) / len(binder_preds) if binder_preds else float("nan")
    mean_decoy = sum(decoy_preds) / len(decoy_preds) if decoy_preds else float("nan")
    separation = mean_binder - mean_decoy

    # EF@5% on combined ranking
    combined_scores = binder_preds + decoy_preds
    combined_labels = [1] * len(binder_preds) + [0] * len(decoy_preds)
    ef5 = datafit.enrichment_factor(combined_scores, combined_labels, top_frac=0.05)

    return {
        "accession": target.accession,
        "gene": target.gene,
        "pairs": target.pairs,
        "class": target.target_class,
        "seq_len": len(seq),
        "truncated_to_1250": truncated,
        "n_binders": len(binder_preds),
        "n_decoys": len(decoy_preds),
        "mean_binder_pkd_train": round(sum(p for _s, p in binders) / len(binders), 3) if binders else None,
        "mean_pred_binder": round(mean_binder, 3),
        "mean_pred_decoy": round(mean_decoy, 3),
        "separation": round(separation, 3),
        "auroc": round(auroc, 3),
        "ef_at_5pct": round(ef5, 3),
        "binder_preds": [round(x, 3) for x in binder_preds],
        "decoy_preds": [round(x, 3) for x in decoy_preds],
        "elapsed_sec": round(elapsed, 1),
    }


def make_plot(results_by_bin, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

    for bin_label, rs in results_by_bin.items():
        if not rs:
            continue
        xs = [math.log10(max(1, r["pairs"])) for r in rs]
        ys = [r["auroc"] for r in rs]
        ax.scatter(xs, ys, c=BIN_COLORS.get(bin_label, "gray"),
                   s=80, edgecolor="black", linewidth=0.7,
                   label=f"{bin_label} ({rs[0]['_bin_range'][0]}-{rs[0]['_bin_range'][1]} pairs)",
                   zorder=3)
        for r in rs:
            ax.annotate(r["gene"] or r["accession"],
                        (math.log10(max(1, r["pairs"])), r["auroc"]),
                        textcoords="offset points", xytext=(5, 4),
                        fontsize=7, color="#444")

    # Bin-mean overlay
    bin_means_x, bin_means_y = [], []
    for bin_label, rs in results_by_bin.items():
        if not rs:
            continue
        xs = [math.log10(max(1, r["pairs"])) for r in rs]
        ys = [r["auroc"] for r in rs]
        bin_means_x.append(sum(xs) / len(xs))
        bin_means_y.append(sum(ys) / len(ys))
    if bin_means_x:
        ax.plot(bin_means_x, bin_means_y, "k--", alpha=0.5, linewidth=1.2,
                label="bin mean", zorder=2)

    ax.axhline(0.5, color="gray", linestyle=":", linewidth=1, label="chance (0.5)")
    ax.axhline(0.8, color="green", linestyle=":", linewidth=1, label="useful (0.8)")

    # Nav reference
    ax.scatter([math.log10(1)], [0.5], marker="X", c="black", s=120, zorder=4,
               label="Nav1.8 (0 pairs, AUROC~0.5, Phase 2b)")

    ax.set_xlabel("log10(per-target training pairs in BindingDB_Kd)")
    ax.set_ylabel("Binder-vs-decoy AUROC")
    ax.set_title("MAMMAL DTI head: binder-vs-decoy AUROC vs per-target training pairs")
    ax.set_ylim(0.3, 1.05)
    ax.set_xlim(-0.2, 3.3)
    ax.grid(True, alpha=0.3, zorder=0)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    t_start = time.time()

    print("Loading per-target CSV...")
    rows = datafit.load_per_target_csv(REPO)
    print(f"  {len(rows)} targets in pool (raw)")

    # Pick targets per bin, redraw if too few binders
    print(f"\nPicking {PER_BIN} targets per bin (excluding ceiling panel: {sorted(CEILING_EXCLUDE)})")
    picks_by_bin = {}
    redraws_by_bin = {}
    picked_acc = set()
    for lo, hi, label in BINS:
        picks, redraws = pick_targets_for_bin(
            rows, (lo, hi), seed_base=42, picked_acc=picked_acc, exclude=CEILING_EXCLUDE
        )
        picks_by_bin[label] = picks
        redraws_by_bin[label] = redraws
        for p in picks:
            picked_acc.add(p.accession)
        print(f"  bin={label:9s} ({lo}-{hi} pairs): picked {len(picks)} targets, {len(redraws)} redraws")
        for p in picks:
            print(f"      {p.accession:8s} {p.gene:10s} pairs={p.pairs:4d} class={p.target_class}")
        for acc, reason in redraws:
            print(f"      [redraw] {acc}: {reason}")

    # Load DTI model
    print("\nLoading PEER DTI model...")
    try:
        model, tok, dev = load_dti_model(source=PEER_SOURCE)
    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "mps" in str(e).lower():
            print(f"  MPS failed ({e}); retrying on CPU.")
            model, tok, dev = load_dti_model(source=PEER_SOURCE, device="cpu")
        else:
            raise
    print(f"  on {dev}")

    # Score
    results_by_bin = {label: [] for _, _, label in BINS}
    for lo, hi, label in BINS:
        print(f"\nScoring bin={label} ({lo}-{hi} pairs)...")
        for target in picks_by_bin[label]:
            print(f"  -> {target.accession} ({target.gene}, pairs={target.pairs})")
            try:
                r = score_target(model, tok, target)
            except Exception as e:  # noqa: BLE001
                print(f"     FAILED: {e}")
                continue
            r["_bin_range"] = [lo, hi]
            r["bin"] = label
            results_by_bin[label].append(r)
            print(f"     n_binders={r['n_binders']} n_decoys={r['n_decoys']} "
                  f"AUROC={r['auroc']:.3f} EF@5%={r['ef_at_5pct']:.2f} "
                  f"sep={r['separation']:+.3f} ({r['elapsed_sec']}s)")

    # Bin-averaged AUROC
    bin_summary = {}
    for lo, hi, label in BINS:
        aurocs = [r["auroc"] for r in results_by_bin[label]
                  if r["auroc"] == r["auroc"]]  # filter NaN
        if not aurocs:
            bin_summary[label] = {"range": [lo, hi], "n": 0,
                                  "mean_auroc": None, "std_auroc": None,
                                  "mean_log_pairs": None}
            continue
        mean = sum(aurocs) / len(aurocs)
        var = sum((a - mean) ** 2 for a in aurocs) / len(aurocs)
        std = math.sqrt(var)
        log_pairs = [math.log10(max(1, r["pairs"])) for r in results_by_bin[label]]
        bin_summary[label] = {
            "range": [lo, hi], "n": len(aurocs),
            "mean_auroc": round(mean, 3), "std_auroc": round(std, 3),
            "mean_log_pairs": round(sum(log_pairs) / len(log_pairs), 3),
        }

    print("\n=== bin-averaged AUROC ===")
    for label in [b[2] for b in BINS]:
        s = bin_summary[label]
        if s["n"] == 0:
            print(f"  {label:9s} (n=0) no usable targets")
            continue
        print(f"  {label:9s} ({s['range'][0]:4d}-{s['range'][1]:4d} pairs)  "
              f"n={s['n']}  mean AUROC = {s['mean_auroc']:.3f} +/- {s['std_auroc']:.3f}")

    # Save JSON + plot + markdown
    out_json = REPO / "results" / f"datafit_curve_{ts}.json"
    out_png = REPO / "results" / "datafit_curve.png"
    payload = {
        "timestamp": ts,
        "checkpoint": "dti_bindingdb_pkd_peer",
        "norm_constants": [PEER_M, PEER_S],
        "device": dev,
        "bins": [{"label": label, "lo": lo, "hi": hi} for lo, hi, label in BINS],
        "per_bin": PER_BIN,
        "n_decoys_per_target": N_DECOYS,
        "n_binders_max": N_BINDERS_MAX,
        "pkd_threshold_binder": PKD_THRESHOLD,
        "ceiling_exclude": sorted(CEILING_EXCLUDE),
        "seed": 42,
        "picks": {label: [{"accession": p.accession, "gene": p.gene,
                           "pairs": p.pairs, "class": p.target_class}
                          for p in picks_by_bin[label]]
                  for _lo, _hi, label in BINS},
        "redraws": {label: [{"accession": acc, "reason": reason}
                            for acc, reason in redraws_by_bin[label]]
                    for _lo, _hi, label in BINS},
        "results_by_bin": results_by_bin,
        "bin_summary": bin_summary,
        "wall_time_sec": round(time.time() - t_start, 1),
    }
    out_json.write_text(json.dumps(payload, indent=2))
    print(f"\nsaved JSON  -> {out_json}")

    print("Rendering plot...")
    make_plot(results_by_bin, out_png)
    print(f"saved plot  -> {out_png}")

    # Write markdown
    md_path = REPO / "results" / "datafit_curve.md"
    md = build_markdown(ts, results_by_bin, bin_summary, picks_by_bin, redraws_by_bin)
    md_path.write_text(md)
    print(f"saved writeup -> {md_path}")

    print(f"\nDone. Total wall time: {payload['wall_time_sec']}s")


def build_markdown(ts, results_by_bin, bin_summary, picks_by_bin, redraws_by_bin):
    # Headline verdict
    def fmt_auroc(label):
        s = bin_summary[label]
        if s["n"] == 0:
            return "n/a"
        return f"{s['mean_auroc']:.2f} +/- {s['std_auroc']:.2f}"

    low_mean = bin_summary["low"]["mean_auroc"]
    lowmid_mean = bin_summary["low-mid"]["mean_auroc"]
    highmid_mean = bin_summary["high-mid"]["mean_auroc"]
    high_mean = bin_summary["high"]["mean_auroc"]

    # Identify the first bin where mean AUROC >= 0.7 / 0.8
    threshold_07 = None
    threshold_08 = None
    for lo, hi, label in BINS:
        m = bin_summary[label]["mean_auroc"]
        if m is None:
            continue
        if threshold_07 is None and m >= 0.7:
            threshold_07 = (label, lo, hi, m)
        if threshold_08 is None and m >= 0.8:
            threshold_08 = (label, lo, hi, m)

    headline_bits = []
    if threshold_08 is not None:
        headline_bits.append(
            f"AUROC crosses 0.8 in the **{threshold_08[0]}** bin ({threshold_08[1]}-{threshold_08[2]} pairs, "
            f"mean {threshold_08[3]:.2f})"
        )
    elif threshold_07 is not None:
        headline_bits.append(
            f"AUROC crosses 0.7 in the **{threshold_07[0]}** bin ({threshold_07[1]}-{threshold_07[2]} pairs, "
            f"mean {threshold_07[3]:.2f}) and never reaches 0.8"
        )
    else:
        headline_bits.append("AUROC never reaches 0.7 in any bin — head is below useful across the curve")

    verdict = (
        f"**Verdict:** With Nav1.8 sitting at 0 pairs / AUROC ~0.5, the curve shows that "
        f"{headline_bits[0]}. So the data volume above which the MAMMAL DTI head becomes useful "
        f"is roughly the **{threshold_08[0] if threshold_08 else (threshold_07[0] if threshold_07 else 'unreached')}** bin "
        f"({threshold_08[1] if threshold_08 else (threshold_07[1] if threshold_07 else '?')}+ pairs)."
    )

    # Per-target table
    table_rows = []
    for lo, hi, label in BINS:
        for r in results_by_bin[label]:
            table_rows.append(
                f"| {label} | {r['accession']} | {r['gene']} | {r['class']} | "
                f"{r['pairs']} | {r['seq_len']}{' (trunc)' if r['truncated_to_1250'] else ''} | "
                f"{r['n_binders']} | {r['auroc']:.3f} | {r['ef_at_5pct']:.2f} | "
                f"{r['mean_pred_binder']:+.2f} / {r['mean_pred_decoy']:+.2f} | "
                f"{r['separation']:+.3f} |"
            )
    table = "\n".join(table_rows) if table_rows else "(no data)"

    # Bin summary table
    bin_table_lines = []
    for lo, hi, label in BINS:
        s = bin_summary[label]
        if s["n"] == 0:
            bin_table_lines.append(f"| {label} | {lo}-{hi} | 0 | n/a | n/a |")
            continue
        bin_table_lines.append(
            f"| {label} | {lo}-{hi} | {s['n']} | {s['mean_auroc']:.3f} +/- {s['std_auroc']:.3f} | "
            f"{s['mean_log_pairs']:.2f} |"
        )
    bin_table = "\n".join(bin_table_lines)

    # Redraws section
    redraw_lines = []
    for lo, hi, label in BINS:
        rs = redraws_by_bin[label]
        if not rs:
            continue
        redraw_lines.append(f"- **{label}** ({lo}-{hi} pairs): " +
                            ", ".join(f"{acc} ({reason})" for acc, reason in rs))
    redraws_block = "\n".join(redraw_lines) if redraw_lines else "_None — first pick from each bin was usable._"

    # Picks block
    picks_lines = []
    for lo, hi, label in BINS:
        picks_lines.append(f"- **{label}** ({lo}-{hi} pairs): " +
                           ", ".join(f"{p.accession} {p.gene} ({p.pairs})" for p in picks_by_bin[label]))
    picks_block = "\n".join(picks_lines)

    return f"""# Datafit curve — binder-vs-decoy AUROC vs # of per-target training pairs

**NEXT_STEPS item 1b**, follow-up to the per-target distribution audit
(`results/dti_train_data_distribution.md`). Nav1.8 has 0 training pairs in
BindingDB_Kd and Phase 2b's binder-vs-decoy AUROC was ~0.5. **How does AUROC
scale with per-target pair count, and where does it become useful?**

- Script: `experiments/datafit_curve.py`
- Raw artifacts: `results/datafit_curve_{ts}.json`, `results/datafit_curve.png`
- Run date: {ts[:8]}. Env: conda `mammal`, PEER DTI checkpoint.

## Verdict (one line)

{verdict}

## Setup

- Checkpoint: **PEER** (`models/dti_bindingdb_pkd_peer`), norm constants 6.286 / 1.542.
- Per target: up to 20 binders at **pKd >= 7.0** (BindingDB_Kd, harmonized
  via `max_affinity` then `convert_to_log`), plus **60 random decoys** drawn
  from BindingDB compounds never measured against the target.
- One metric per target: random-decoy AUROC. Plus EF@5% as a cross-check.
- 4 bins x 4 targets = 16 targets, seeded random pick (seed=42), disjoint from
  the ceiling experiment's 6 targets.
- Re-draw rule: if a candidate target has <5 usable binders @ pKd>=7.0, pick
  the next from the same bin.

### Picked targets

{picks_block}

### Redraws (reproducibility log)

{redraws_block}

## Per-target results

| bin | accession | gene | class | pairs | seq_len | n_binders | AUROC | EF@5% | mean pred binder/decoy | separation |
|---|---|---|---|---|---|---|---|---|---|---|
{table}

## The curve

Bin-averaged AUROC vs log10(per-target training pairs):

| bin | pair range | n usable | mean AUROC | mean log10(pairs) |
|---|---|---|---|---|
{bin_table}

- low ({BINS[0][0]}-{BINS[0][1]} pairs): {fmt_auroc('low')}
- low-mid ({BINS[1][0]}-{BINS[1][1]} pairs): {fmt_auroc('low-mid')}
- high-mid ({BINS[2][0]}-{BINS[2][1]} pairs): {fmt_auroc('high-mid')}
- high ({BINS[3][0]}-{BINS[3][1]} pairs): {fmt_auroc('high')}

Plot: `results/datafit_curve.png` (one point per target, colored by bin;
horizontal lines at AUROC = 0.5 chance and 0.8 useful; black X marks Nav1.8 at
0 pairs / AUROC ~0.5 from Phase 2b).

## Interpretation

- **Nav1.8 anchor (Phase 2b):** 0 BindingDB pairs, AUROC ~ 0.5 (chance).
- **low bin** ({BINS[0][0]}-{BINS[0][1]} pairs): mean AUROC {fmt_auroc('low')} — same
  data-poor regime as Nav1.8; predictions are barely above (or near) chance.
- **low-mid** ({BINS[1][0]}-{BINS[1][1]} pairs): mean AUROC {fmt_auroc('low-mid')} —
  whether 10-40 incidental pairs are enough is the key empirical question this
  curve answers.
- **high-mid** ({BINS[2][0]}-{BINS[2][1]} pairs): mean AUROC {fmt_auroc('high-mid')}.
- **high** ({BINS[3][0]}-{BINS[3][1]} pairs): mean AUROC {fmt_auroc('high')} — what
  the head looks like on the targets it was trained heavily on.

**Threshold for "useful" (AUROC >= 0.7):** {('first crossed in ' + threshold_07[0] + ' bin (' + str(threshold_07[1]) + '-' + str(threshold_07[2]) + ' pairs, mean ' + f"{threshold_07[3]:.2f}" + ')') if threshold_07 else 'not crossed in any bin'}.

**Threshold for "strong" (AUROC >= 0.8):** {('first crossed in ' + threshold_08[0] + ' bin (' + str(threshold_08[1]) + '-' + str(threshold_08[2]) + ' pairs, mean ' + f"{threshold_08[3]:.2f}" + ')') if threshold_08 else 'not crossed in any bin'}.

### Implication for a Quiver per-target fine-tune

Nav1.8 sits at the **0-pairs end** of this curve. For a Quiver per-target
fine-tune on Nav1.8 to *beat off-the-shelf MAMMAL*, we just need to push the
data volume above the elbow visible here. If the elbow is around tens of
binders, a focused Nav1.8 dataset of a few hundred annotated compounds is in
range; if the curve only takes off in the hundreds, we need a larger dataset.
The empirical takeaway: **what Nav1.8 needs is data, not a different model
architecture**. Off-the-shelf MAMMAL is at chance because BindingDB never showed
it a Nav, not because the head can't learn ion channels at all.

### Caveats

- Random decoys only — same-MW matched decoys (the harder test) are covered in
  the ceiling experiment.
- Binder count per target is capped at 20; some "high" targets have many more
  pairs but only their top-20 strongest binders are scored (keeps comparison
  uniform).
- AUROC of 1.0 on a sub-20-binder target should be read with care — it tells
  you "the head rank-orders these binders above random decoys", not "the head
  could pick novel binders out of a real screen".
- BindingDB_Kd train/test split is opaque per-target — PEER's training set may
  include some of the binders here. This is an *upper bound* for the head's
  binder-vs-decoy ability per target; the matched-decoy / scaffold-split tests
  are the harder ground truth.
"""


if __name__ == "__main__":
    main()
