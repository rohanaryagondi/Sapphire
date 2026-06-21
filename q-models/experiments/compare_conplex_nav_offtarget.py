"""ConPLex on the full Nav family + off-target sanity check.

Two gaps in the prior compare suite:
  (1) ConPLex was tested only on Nav1.8 (single paralog). If it works on ANY
      other Nav (Nav1.1–Nav1.9) we'd learn the failure isn't pan-Nav. If it
      fails on all 9, the BindingDB-trained DTI tooling is genuinely Nav-blind.
  (2) ConPLex was never given Graham's off-target sanity check — does it
      emit specific predictions, or "binds everything" like MAMMAL did?

Same protocol as the existing MAMMAL runs so the numbers are apples-to-apples:
  - Nav family: 7 Nav blockers (suzetrigine, A-803467, lidocaine, mexiletine,
    ranolazine, carbamazepine, lacosamide) vs 4 decoys (metformin, caffeine,
    ibuprofen, atenolol) → AUROC for each of Nav1.1–Nav1.9.
  - Off-target: same 5 drugs (2 Nav + 3 background) × 3 targets (Nav1.8 on,
    UBE3A off, TUBB off) → per-target score table + spread analysis.

ConPLex scoring path: subprocess into the `conplex` env via baselines/conplex.py.
Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare_conplex_nav_offtarget.py
"""

from __future__ import annotations

import functools
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from baselines import conplex  # noqa: E402
from mammal_quiver import datafit  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

# --- Nav family (9 paralogs) ---
NAV_FAMILY = [
    ("Nav1.1", "P35498", "SCN1A"),
    ("Nav1.2", "Q99250", "SCN2A"),
    ("Nav1.3", "Q9NY46", "SCN3A"),
    ("Nav1.4", "P35499", "SCN4A"),
    ("Nav1.5", "Q14524", "SCN5A"),
    ("Nav1.6", "Q9UQD0", "SCN8A"),
    ("Nav1.7", "Q15858", "SCN9A"),
    ("Nav1.8", "Q9Y5Y9", "SCN10A"),
    ("Nav1.9", "Q9UI33", "SCN11A"),
]

# --- Drugs ---
NAV_BLOCKERS = ["suzetrigine", "A-803467", "lidocaine", "mexiletine", "ranolazine",
                "carbamazepine", "lacosamide"]
DECOYS = ["metformin", "caffeine", "ibuprofen", "atenolol"]

# --- Off-target panel (Graham's sanity check, applied to ConPLex this time) ---
OFFTARGET_TARGETS = [
    ("UBE3A",  "Q05086", "E3 ubiquitin ligase (~875 aa — OFF-target)"),
    ("Nav1.8", "Q9Y5Y9", "voltage-gated Na channel (ON-target baseline)"),
    ("TUBB",   "P07437", "tubulin beta (~444 aa — OFF-target)"),
]
OFFTARGET_DRUGS = ["suzetrigine", "vixotrigine", "metformin", "caffeine", "ibuprofen"]


@functools.lru_cache(maxsize=256)
def smiles_for(name: str) -> str | None:
    # PubChem deprecated IsomericSMILES/CanonicalSMILES — current API returns
    # `SMILES` (and `ConnectivitySMILES`). Ask for SMILES; fall back to the
    # old field names in case of revert.
    url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
           f"{urllib.parse.quote(name)}/property/SMILES,IsomericSMILES,CanonicalSMILES/JSON")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES")
    except Exception:  # noqa: BLE001
        return None


def _round(x, n=3):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return round(float(x), n)


# --------------------------------------------------------------------------- #
def part1_nav_family() -> dict:
    print("\n" + "=" * 70)
    print("PART 1 — ConPLex on Nav1.1 ... Nav1.9 (full SCN family)")
    print("=" * 70)

    # Resolve SMILES + sequences once.
    print("Resolving SMILES + sequences ...")
    pos_smiles = []
    for n in NAV_BLOCKERS:
        s = smiles_for(n)
        if s:
            pos_smiles.append((n, s))
        else:
            print(f"  [drop] {n}: no SMILES")
    neg_smiles = []
    for n in DECOYS:
        s = smiles_for(n)
        if s:
            neg_smiles.append((n, s))
        else:
            print(f"  [drop] {n}: no SMILES")
    print(f"  binders: {len(pos_smiles)}; decoys: {len(neg_smiles)}")

    nav_seqs = {}
    for display, acc, gene in NAV_FAMILY:
        seq = fetch_uniprot_sequence(acc)
        nav_seqs[display] = (acc, gene, seq, len(seq))
        print(f"  {display:6s} {acc} ({gene}): {len(seq)} aa "
              f"{'(truncated to 1250)' if len(seq) > 1250 else ''}")

    # Build the batched (seq, smi) list (paralogs × drugs).
    pairs = []
    pair_index = []  # (paralog, drug_name, label)
    for display, (acc, gene, seq, _) in nav_seqs.items():
        for n, s in pos_smiles:
            pairs.append((seq, s))
            pair_index.append((display, n, 1))
        for n, s in neg_smiles:
            pairs.append((seq, s))
            pair_index.append((display, n, 0))

    print(f"\nScoring {len(pairs)} (paralog × drug) pairs with ConPLex ...")
    t0 = time.time()
    scores = conplex.score_batch(pairs)
    print(f"  done in {time.time() - t0:.1f}s")

    # Per-paralog AUROC + score-table
    by_paralog: dict[str, dict] = {}
    for (display, _drug, label), s in zip(pair_index, scores):
        d = by_paralog.setdefault(display, {"pos": [], "neg": [], "drugs": {}})
        if label == 1:
            d["pos"].append(s)
        else:
            d["neg"].append(s)
        d["drugs"][_drug] = s

    print("\n" + "-" * 70)
    print(f"{'paralog':8s} {'acc':8s} {'AUROC':>7s} {'sep(pos-neg)':>14s}  scores (pos | neg)")
    print("-" * 70)
    out_rows = []
    for display, (acc, gene, seq, slen) in nav_seqs.items():
        d = by_paralog[display]
        auc = datafit.auroc(d["pos"], d["neg"])
        sep = mean(d["pos"]) - mean(d["neg"])
        pos_str = ", ".join(f"{s:.2f}" for s in d["pos"])
        neg_str = ", ".join(f"{s:.2f}" for s in d["neg"])
        print(f"{display:8s} {acc:8s} {auc:>7.3f} {sep:>+14.3f}  ({pos_str} | {neg_str})")
        out_rows.append({
            "paralog": display, "accession": acc, "gene": gene, "seq_len": slen,
            "auroc": _round(auc), "separation": _round(sep),
            "mean_pos": _round(mean(d["pos"])), "mean_neg": _round(mean(d["neg"])),
            "per_drug": {k: _round(v) for k, v in d["drugs"].items()},
        })

    # Bin-summary
    aurocs = [r["auroc"] for r in out_rows]
    n_pass = sum(1 for a in aurocs if a >= 0.70)
    n_useful = sum(1 for a in aurocs if 0.60 <= a < 0.70)
    n_chance = sum(1 for a in aurocs if a < 0.60)

    return {
        "n_pos": len(pos_smiles), "n_neg": len(neg_smiles),
        "per_paralog": out_rows,
        "summary": {
            "n_paralogs_tested": len(NAV_FAMILY),
            "n_auroc_ge_0.70_STRONG": n_pass,
            "n_auroc_0.60_to_0.70_USEFUL": n_useful,
            "n_auroc_below_0.60_CHANCE": n_chance,
            "mean_auroc_across_family": _round(mean(aurocs)),
            "max_auroc": _round(max(aurocs)),
            "min_auroc": _round(min(aurocs)),
        },
        "verdict": (
            "ConPLex works on at least one Nav paralog"
            if n_pass >= 1 else
            "ConPLex provides modest signal on >=1 Nav paralog"
            if n_useful >= 1 else
            "ConPLex is pan-Nav blind (every paralog at chance)"
        ),
    }


# --------------------------------------------------------------------------- #
def part2_offtarget() -> dict:
    print("\n" + "=" * 70)
    print("PART 2 — ConPLex off-target sanity (Graham's protocol)")
    print("=" * 70)

    # Resolve drug SMILES.
    drug_pairs = []
    for n in OFFTARGET_DRUGS:
        s = smiles_for(n)
        if s:
            drug_pairs.append((n, s))
        else:
            print(f"  [drop] {n}")
    print(f"  drugs: {len(drug_pairs)}")

    target_seqs = {}
    for display, acc, note in OFFTARGET_TARGETS:
        seq = fetch_uniprot_sequence(acc)
        target_seqs[display] = (acc, seq, note)
        print(f"  {display:8s} {acc} ({len(seq)} aa) {note}")

    # Build pair list (target × drug)
    pairs = []
    idx = []  # (target_display, drug_name)
    for display, (acc, seq, _) in target_seqs.items():
        for n, s in drug_pairs:
            pairs.append((seq, s))
            idx.append((display, n))

    print(f"\nScoring {len(pairs)} pairs with ConPLex ...")
    t0 = time.time()
    scores = conplex.score_batch(pairs)
    print(f"  done in {time.time() - t0:.1f}s")

    # Tabulate
    table: dict[str, dict[str, float]] = {}
    for (display, drug), s in zip(idx, scores):
        table.setdefault(display, {})[drug] = s

    print("\n" + "-" * 80)
    header = f"{'target':10s} " + " ".join(f"{n:>13s}" for n, _ in drug_pairs) + f"  {'spread':>8s}"
    print(header)
    print("-" * 80)
    rows_out = []
    for display, (acc, seq, note) in target_seqs.items():
        row = table[display]
        vals = [row[n] for n, _ in drug_pairs]
        spread = max(vals) - min(vals)
        row_str = " ".join(f"{row[n]:>13.4f}" for n, _ in drug_pairs)
        print(f"{display:10s} {row_str}  {spread:>+8.4f}")
        rows_out.append({
            "target": display, "accession": acc,
            "drugs": {n: _round(v, 4) for n, v in row.items()},
            "max": _round(max(vals), 4), "min": _round(min(vals), 4),
            "mean": _round(mean(vals), 4), "spread_max_minus_min": _round(spread, 4),
            "std": _round(pstdev(vals), 4),
        })

    # Specificity diagnostics: for each Nav drug, on-target − mean(off-target)
    on_t = "Nav1.8"
    off_ts = [d for d, _, _ in OFFTARGET_TARGETS if d != on_t]
    specificity = []
    for n, _ in drug_pairs:
        on = table[on_t][n]
        off_mean = mean(table[t][n] for t in off_ts)
        specificity.append({
            "drug": n,
            "on_target_Nav1.8": _round(on, 4),
            "mean_offtarget": _round(off_mean, 4),
            "delta_on_minus_off": _round(on - off_mean, 4),
        })

    print("\n" + "-" * 70)
    print("Per-drug specificity: Nav1.8 score − mean(UBE3A, TUBB)")
    print("-" * 70)
    for s in specificity:
        d = s["delta_on_minus_off"]
        mark = "OK" if d > 0.15 else ("weak" if d > 0 else "INVERTED")
        print(f"  {s['drug']:18s} on={s['on_target_Nav1.8']:.4f}  "
              f"off_mean={s['mean_offtarget']:.4f}  Δ={d:+.4f}  [{mark}]")

    # Verdict
    nav_drug_deltas = [s["delta_on_minus_off"] for s in specificity if s["drug"] in NAV_BLOCKERS + ["vixotrigine"]]
    if nav_drug_deltas and max(nav_drug_deltas) < 0.05:
        verdict = "ConPLex shows NO target specificity off-the-shelf (Nav drugs score essentially the same on Nav1.8 vs unrelated proteins)"
    elif nav_drug_deltas and mean(nav_drug_deltas) > 0.15:
        verdict = "ConPLex shows real target specificity for Nav drugs"
    else:
        verdict = "ConPLex shows weak/inconsistent target specificity off-the-shelf"

    return {
        "n_drugs": len(drug_pairs), "n_targets": len(OFFTARGET_TARGETS),
        "per_target_scores": rows_out,
        "per_drug_specificity": specificity,
        "verdict": verdict,
    }


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"ConPLex Nav-family + off-target run @ {ts}")

    part1 = part1_nav_family()
    part2 = part2_offtarget()

    out = {
        "timestamp": ts,
        "model": "ConPLex_v1_BindingDB (zero-shot)",
        "nav_family": part1,
        "offtarget_sanity": part2,
    }
    out_path = REPO / "results" / f"compare_conplex_nav_offtarget_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2))

    print("\n" + "=" * 70)
    print("VERDICTS")
    print("=" * 70)
    print(f"  Nav family    : {part1['verdict']}")
    print(f"                  ({part1['summary']['n_auroc_ge_0.70_STRONG']}/9 strong, "
          f"{part1['summary']['n_auroc_0.60_to_0.70_USEFUL']}/9 useful, "
          f"mean AUROC = {part1['summary']['mean_auroc_across_family']})")
    print(f"  Off-target    : {part2['verdict']}")
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
