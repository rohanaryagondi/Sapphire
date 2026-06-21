"""Data-fit CEILING — does MAMMAL's DTI head work where the training data IS?

NEXT_STEPS item 1b. The Nav1.8 binding test failed (AUROC ~0.5) and the data
audit (results/dti_train_data_distribution.md) showed BindingDB_Kd has ZERO Nav
training pairs. Question: is the failure a *data gap* or a *model limitation*?

Decision rule: test the head on 6 targets that ARE well represented in BindingDB_Kd.
If AUROC is high there, the Nav failure is a data gap (and a Quiver Nav fine-tune
is the move). If it's bad here too, the model itself is the bottleneck.

Panel (chosen to span class + sample-size with mTOR as the Quiver-relevant kinase):
  P42345 MTOR  192 pairs kinase            (Quiver target)
  P15056 BRAF  532 pairs kinase            (most-represented target in the pool)
  Q8K4Z4 Adrb2 211 pairs gpcr
  P31389 HRH1  184 pairs gpcr
  P51449 RORC  374 pairs nuclear_receptor
  P00918 CA2   269 pairs other (carbonic anhydrase, classic small-molecule target)

Per target: 4 readouts.
  (1) AUROC binder-vs-random-decoy        (open-world non-binder, easier)
  (2) AUROC binder-vs-property-matched    (MW-matched off-target compound, harder)
  (3) Spearman on cold-split test pKd     (potentially leaked into PEER training -> upper bound)
  (4) EF@5% on binder+matched-decoy pool

Then build the off-target matrix: top-3 binders per target (18 binders) scored
against all 6 panel proteins. Per-binder Δ = on-target pKd − mean off-target pKd.

Checkpoint: PEER (the correct one for our problem classes), norms 6.286 / 1.542.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/datafit_ceiling.py
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

# (accession, gene, n_pairs, class)
PANEL = [
    ("P42345", "MTOR",  192, "kinase"),
    ("P15056", "BRAF",  532, "kinase"),
    ("Q8K4Z4", "Adrb2", 211, "gpcr"),
    ("P31389", "HRH1",  184, "gpcr"),
    ("P51449", "RORC",  374, "nuclear_receptor"),
    ("P00918", "CA2",   269, "other"),
]

PKD_THRESHOLD = 7.0   # binder definition: pKd >= 7 (Kd <= 100 nM)
N_BINDERS = 30
N_RANDOM_DECOYS = 30
N_MATCHED_PER_BINDER = 3
MW_TOL = 50.0
SEED = 42
TOP_FRAC = 0.05


def round3(x):
    if x is None or (isinstance(x, float) and (x != x)):  # nan
        return None
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return x


def score_many(model, tok, seq, smiles_list, label=""):
    """Predict pKd for many SMILES against one protein seq. Returns list of floats
    (skipping any SMILES that error out)."""
    preds = []
    t0 = time.time()
    for i, smi in enumerate(smiles_list):
        try:
            pk = predict_pkd(model, tok, seq, smi, PEER_M, PEER_S)
            preds.append(pk)
        except Exception as e:  # noqa: BLE001
            print(f"    [warn] skipped {label} idx={i}: {type(e).__name__}: {e}")
    dt = time.time() - t0
    if smiles_list:
        print(f"    {label}: scored {len(preds)}/{len(smiles_list)} in {dt:.1f}s "
              f"({dt / max(1, len(smiles_list)):.2f}s/pair)")
    return preds


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def run_target(model, tok, acc, gene, n_pairs, cls):
    """Run all 4 readouts for one target. Returns a dict (and the top-3 binders)."""
    print(f"\n=== {acc} {gene} ({cls}, n_pairs={n_pairs}) ===")
    seq = fetch_uniprot_sequence(acc)
    trunc = len(seq) > 1250
    print(f"  seq_len={len(seq)} {'(>1250 -> TRUNCATED to 1250)' if trunc else '(<=1250 fully visible)'}")

    # --- Binders ---
    binders = datafit.get_binders(acc, pkd_threshold=PKD_THRESHOLD, n_max=N_BINDERS)
    if not binders:
        print(f"  [skip] no binders at pKd>={PKD_THRESHOLD}")
        return {"accession": acc, "gene": gene, "n_pairs": n_pairs, "class": cls,
                "seq_len": len(seq), "truncated": trunc, "skipped": "no_binders"}, []
    binder_smiles = [s for s, _ in binders]
    binder_pkds_true = [p for _, p in binders]
    print(f"  binders pulled: n={len(binders)}  pKd top={binder_pkds_true[0]:.2f} bottom={binder_pkds_true[-1]:.2f}")

    # --- Decoys ---
    random_decoys = datafit.sample_random_decoys(acc, N_RANDOM_DECOYS, seed=SEED)
    matched_decoys = datafit.sample_matched_decoys(
        acc, binder_smiles, n_per_binder=N_MATCHED_PER_BINDER, mw_tol=MW_TOL, seed=SEED
    )
    print(f"  random decoys: n={len(random_decoys)} ; matched decoys: n={len(matched_decoys)}")

    # --- Score binders & decoys with PEER ---
    print(f"  scoring on {acc}...")
    binder_preds = score_many(model, tok, seq, binder_smiles, label="binders")
    random_decoy_preds = score_many(model, tok, seq, random_decoys, label="random decoys")
    matched_decoy_preds = score_many(model, tok, seq, matched_decoys, label="matched decoys")

    # --- (1) AUROC binder vs random ---
    auc_random = datafit.auroc(binder_preds, random_decoy_preds)
    sep_random = mean(binder_preds) - mean(random_decoy_preds)

    # --- (2) AUROC binder vs matched ---
    auc_matched = datafit.auroc(binder_preds, matched_decoy_preds)
    sep_matched = mean(binder_preds) - mean(matched_decoy_preds)

    # --- (3) Spearman on cold-split test fold ---
    test_pairs = datafit.get_test_pairs_for_target(acc)
    spearman_block = {"n": len(test_pairs)}
    if len(test_pairs) < 8:
        spearman_block["status"] = "insufficient (<8 test pairs)"
        print(f"  Spearman: insufficient (n={len(test_pairs)})")
    else:
        test_smi = [s for s, _ in test_pairs]
        test_y = [y for _, y in test_pairs]
        test_pred = score_many(model, tok, seq, test_smi, label="test fold")
        # Truncate y to whatever survived prediction (same index alignment because
        # score_many preserves order and we don't skip in this loop in practice)
        if len(test_pred) == len(test_y) and len(test_pred) >= 8:
            sp = datafit.spearman(test_y, test_pred)
            pe = datafit.pearson(test_y, test_pred)
            spearman_block.update({
                "status": "ok (potential PEER leakage — upper bound)",
                "spearman": round3(sp),
                "pearson": round3(pe),
                "pkd_range_true": [round3(min(test_y)), round3(max(test_y))],
                "pkd_range_pred": [round3(min(test_pred)), round3(max(test_pred))],
            })
            print(f"  Spearman (n={len(test_y)}, leakage caveat): {sp:.3f}  Pearson: {pe:.3f}")
        else:
            spearman_block["status"] = f"alignment_mismatch (pred={len(test_pred)}, y={len(test_y)})"

    # --- (4) Enrichment factor on binder + matched-decoy pool ---
    pool_scores = binder_preds + matched_decoy_preds
    pool_labels = [1] * len(binder_preds) + [0] * len(matched_decoy_preds)
    ef5 = datafit.enrichment_factor(pool_scores, pool_labels, top_frac=TOP_FRAC)

    print(f"  AUROC random  : {auc_random:.3f}   (mean_binder={mean(binder_preds):.2f}  mean_decoy={mean(random_decoy_preds):.2f}  sep={sep_random:+.2f})")
    print(f"  AUROC matched : {auc_matched:.3f}   (mean_binder={mean(binder_preds):.2f}  mean_decoy={mean(matched_decoy_preds):.2f}  sep={sep_matched:+.2f})")
    print(f"  EF@{int(TOP_FRAC*100)}%      : {ef5:.3f}")

    # --- Top-3 binders (for off-target matrix later) ---
    top3 = binders[:3]  # already sorted desc

    result = {
        "accession": acc,
        "gene": gene,
        "n_pairs": n_pairs,
        "class": cls,
        "seq_len": len(seq),
        "truncated": trunc,
        "binders": {
            "n": len(binders),
            "pkd_range": [round3(min(binder_pkds_true)), round3(max(binder_pkds_true))],
            "mean_true_pkd": round3(mean(binder_pkds_true)),
            "mean_predicted_pkd": round3(mean(binder_preds)),
        },
        "decoys_random": {
            "n": len(random_decoys),
            "mean_predicted_pkd": round3(mean(random_decoy_preds)),
        },
        "decoys_matched": {
            "n": len(matched_decoys),
            "mean_predicted_pkd": round3(mean(matched_decoy_preds)),
            "n_per_binder": N_MATCHED_PER_BINDER,
            "mw_tol_da": MW_TOL,
        },
        "auroc_random": round3(auc_random),
        "auroc_matched": round3(auc_matched),
        "separation_random_pkd": round3(sep_random),
        "separation_matched_pkd": round3(sep_matched),
        "spearman_test_fold": spearman_block,
        "ef_top5pct": round3(ef5),
        "top3_binders": [{"smiles": s, "true_pkd": round3(p)} for s, p in top3],
    }
    return result, top3


def offtarget_matrix(model, tok, panel_seqs, top3_by_target):
    """For each target's top-3 binders (18 total), score against all 6 proteins.

    Returns dict with:
      per_binder: list of {accession, gene, smiles, on_target_pkd,
                           off_target_pkds: {acc: pkd, ...},
                           mean_off_target_pkd, delta}
      per_target_mean_delta: {accession: mean delta over its 3 binders}
    """
    print("\n=== Off-target matrix (top-3 binders/target × 6 proteins) ===")
    accs = [a for a, *_ in PANEL]
    per_binder = []
    delta_by_target = {a: [] for a in accs}

    for acc, _gene, _n, _cls in PANEL:
        top = top3_by_target.get(acc, [])
        for smi, true_pkd in top:
            row = {"accession": acc, "smiles": smi, "true_pkd_on_target": round3(true_pkd)}
            scored = {}
            for other_acc in accs:
                try:
                    pk = predict_pkd(model, tok, panel_seqs[other_acc], smi, PEER_M, PEER_S)
                    scored[other_acc] = round3(pk)
                except Exception as e:  # noqa: BLE001
                    print(f"    [warn] {acc} binder vs {other_acc}: {e}")
                    scored[other_acc] = None
            on = scored.get(acc)
            offs = [v for k, v in scored.items() if k != acc and v is not None]
            mean_off = sum(offs) / len(offs) if offs else float("nan")
            delta = (on - mean_off) if (on is not None and offs) else float("nan")
            row["pkd_vs_panel"] = scored
            row["mean_offtarget_pkd"] = round3(mean_off)
            row["delta_on_minus_meanoff"] = round3(delta)
            per_binder.append(row)
            if delta == delta:  # not nan
                delta_by_target[acc].append(delta)
            print(f"  {acc} {smi[:40]:40s} on={on}  meanOff={round3(mean_off)}  Δ={round3(delta)}")

    per_target_mean_delta = {a: round3(sum(v)/len(v)) if v else None for a, v in delta_by_target.items()}
    return {"per_binder": per_binder, "per_target_mean_delta": per_target_mean_delta}


def write_markdown(result, md_path):
    """Render the writeup. Style modeled on results/offtarget_ube3a.md."""
    ts = result["timestamp"]
    json_name = result["_json_basename"]

    # Per-target rows
    panel_rows = []
    for tg in result["per_target"]:
        if tg.get("skipped"):
            panel_rows.append(f"| {tg['accession']} | {tg['gene']} | {tg['class']} | {tg['n_pairs']} | "
                              f"skipped ({tg['skipped']}) | – | – | – |")
            continue
        sp = tg["spearman_test_fold"]
        if sp.get("status", "").startswith("ok"):
            sp_str = f"{sp['spearman']:.2f} (n={sp['n']})"
        else:
            sp_str = f"– (n={sp['n']})"
        panel_rows.append(
            f"| {tg['accession']} | {tg['gene']} | {tg['class']} | {tg['n_pairs']} | "
            f"**{tg['auroc_random']:.2f}** | **{tg['auroc_matched']:.2f}** | "
            f"{sp_str} | {tg['ef_top5pct']:.2f} |"
        )

    # Off-target Δ rows
    off_rows = []
    for acc in [a for a, *_ in PANEL]:
        gene = next(g for a, g, _, _ in PANEL if a == acc)
        d = result["offtarget_matrix"]["per_target_mean_delta"].get(acc)
        off_rows.append(f"| {acc} | {gene} | {d if d is not None else '–'} |")

    # Verdict logic
    aurocs_r = [tg.get("auroc_random") for tg in result["per_target"] if tg.get("auroc_random") is not None]
    aurocs_m = [tg.get("auroc_matched") for tg in result["per_target"] if tg.get("auroc_matched") is not None]
    n_strong_r = sum(1 for a in aurocs_r if a >= 0.8)
    n_strong_m = sum(1 for a in aurocs_m if a >= 0.7)
    n_targets = len(aurocs_r)

    if n_strong_r >= max(4, n_targets - 1) and n_strong_m >= max(3, n_targets - 2):
        verdict_one = (
            f"**Yes — the head works where the data is.** {n_strong_r}/{n_targets} "
            f"targets clear AUROC 0.80 on random decoys and {n_strong_m}/{n_targets} clear 0.70 on "
            f"property-matched decoys, so the Nav1.8 failure is a **data gap, not a model limit** — "
            f"consistent with the BindingDB audit's zero-Nav-pairs finding. The path to "
            f"Quiver Nav binding is a fine-tune on Quiver ion-channel data, not a different architecture."
        )
    elif n_strong_r >= n_targets // 2:
        verdict_one = (
            f"**Partial — modest triage signal where the data is.** Only {n_strong_r}/{n_targets} "
            f"targets clear AUROC 0.80 on random decoys and {n_strong_m}/{n_targets} clear 0.70 on "
            f"property-matched decoys. Some data-rich targets work, others don't — the head has a "
            f"capacity ceiling that is independent of data volume."
        )
    else:
        verdict_one = (
            f"**No — head doesn't separate binders even with abundant training data.** "
            f"Only {n_strong_r}/{n_targets} targets clear AUROC 0.80 on random decoys. "
            f"The Nav1.8 failure is consistent with a **model limitation**, not just a data gap — "
            f"throwing more Quiver data at the same architecture probably won't rescue it."
        )

    md = f"""# Datafit ceiling — does MAMMAL's DTI head work where the training data IS?

**NEXT_STEPS item 1b.** The Nav1.8 binding test failed (binder-vs-decoy AUROC ≈ 0.5)
and the [data-distribution audit](dti_train_data_distribution.md) showed `BindingDB_Kd`
has **zero Nav training pairs**. This experiment tests the same PEER DTI head on 6
targets that **are** well-represented in the BindingDB_Kd pool — if it works here, the
Nav failure is a data gap; if not, the model itself is the bottleneck.

Run: `experiments/datafit_ceiling.py` · raw: `results/{json_name}` · {ts}.

## The question (decision rule)

Same head, same PEER checkpoint, same protocol as the Nav test — only the target changes.

- **AUROC ≥ 0.80** on random OR matched decoys → head clearly encodes target-specific binding here.
- **AUROC 0.60–0.80** → modest triage signal.
- **AUROC < 0.60** → head doesn't separate binders for that target.

If most/all 6 land at AUROC 0.80+ on random and 0.70+ on matched, the Nav failure is a
**data gap** and the move is a Quiver Nav fine-tune. If they fail here too, MAMMAL's DTI
head is itself the bottleneck.

## Setup

- **Checkpoint:** PEER (`models/dti_bindingdb_pkd_peer`). Norms **6.286291085593906 / 1.5422950906208512**.
- **Binders:** `datafit.get_binders(acc, pkd_threshold=7.0, n_max=30)` — top {N_BINDERS} BindingDB_Kd
  pairs by pKd (Kd ≤ 100 nM), distinct SMILES, harmonized exactly like the MAMMAL data module.
- **Random decoys:** `datafit.sample_random_decoys(acc, 30, seed=42)` — {N_RANDOM_DECOYS} SMILES drawn
  uniformly from compounds tested against *other* BindingDB targets (open-world non-binders).
- **Matched decoys:** `datafit.sample_matched_decoys(acc, binder_smiles, n_per_binder=3, mw_tol=50)` —
  for each binder, up to 3 off-target SMILES within ±50 Da MW (harder negative set).
- **Test pairs (Spearman):** `datafit.get_test_pairs_for_target(acc)` — the cold-split test fold,
  pKd-converted. **Leakage caveat:** the PEER checkpoint used a different split, so these pairs may
  have been seen during PEER training — report as an *upper bound*, not a real generalization number.
- **EF@5%:** standard enrichment factor at the top 5% of the binder+matched-decoy pool.

Panel:

| accession | gene | class | n_pairs in BindingDB_Kd |
|---|---|---|---|
| P42345 | MTOR | kinase | 192 (Quiver target) |
| P15056 | BRAF | kinase | 532 (most-represented target) |
| Q8K4Z4 | Adrb2 | gpcr | 211 |
| P31389 | HRH1 | gpcr | 184 |
| P51449 | RORC | nuclear_receptor | 374 |
| P00918 | CA2 | other | 269 |

Device: {result['device']}. Total wall time: {result['wall_time_sec']:.1f}s.

## Results — per-target

| accession | gene | class | n_pairs | AUROC random | AUROC matched | Spearman (test fold) | EF@5% |
|---|---|---|---|---|---|---|---|
{chr(10).join(panel_rows)}

(Bold AUROCs are the decision-rule numbers. Spearman has the leakage caveat above; it's
an upper bound for the PEER checkpoint, not a clean generalization measure.)

## Off-target matrix — top-3 binders/target × 6 proteins

For each target, the 3 highest-pKd binders are scored against all 6 panel proteins.
**Δ = on-target pKd − mean off-target pKd.** Positive Δ means the head ranks the binder
higher against its real target than against the 5 others. (Per-binder rows are in the JSON.)

| accession | gene | mean Δ (on − mean off) |
|---|---|---|
{chr(10).join(off_rows)}

## Verdict

{verdict_one}
"""
    md_path.write_text(md)
    print(f"\nwriteup -> {md_path}")


def main():
    t_start = time.time()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load PEER once; reuse across all targets.
    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"PEER DTI on {dev}\n")

    # Fetch all sequences up front (cheap, cached).
    panel_seqs = {}
    for acc, gene, n_pairs, cls in PANEL:
        panel_seqs[acc] = fetch_uniprot_sequence(acc)

    per_target_results = []
    top3_by_target = {}
    for acc, gene, n_pairs, cls in PANEL:
        res, top3 = run_target(model, tok, acc, gene, n_pairs, cls)
        per_target_results.append(res)
        top3_by_target[acc] = top3

    off = offtarget_matrix(model, tok, panel_seqs, top3_by_target)

    wall = time.time() - t_start
    out = {
        "timestamp": ts,
        "checkpoint": "dti_bindingdb_pkd_peer",
        "checkpoint_path": PEER_SOURCE,
        "norm_constants": [PEER_M, PEER_S],
        "device": dev,
        "wall_time_sec": round(wall, 1),
        "panel": [{"accession": a, "gene": g, "n_pairs": n, "class": c} for a, g, n, c in PANEL],
        "params": {
            "pkd_threshold": PKD_THRESHOLD,
            "n_binders": N_BINDERS,
            "n_random_decoys": N_RANDOM_DECOYS,
            "n_matched_per_binder": N_MATCHED_PER_BINDER,
            "mw_tol_da": MW_TOL,
            "seed": SEED,
            "top_frac": TOP_FRAC,
        },
        "per_target": per_target_results,
        "offtarget_matrix": off,
    }

    json_path = REPO / "results" / f"datafit_ceiling_{ts}.json"
    json_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {json_path}")

    # --- Stdout summary table (so you don't need to open the JSON) ---
    print("\n=== SUMMARY ===")
    print(f"{'acc':8s} {'gene':6s} {'class':18s} {'n':>4s} {'AUC_rand':>9s} {'AUC_match':>10s} {'Spearman':>9s} {'EF@5%':>6s}  meanΔ")
    for tg in per_target_results:
        if tg.get("skipped"):
            print(f"{tg['accession']:8s} {tg['gene']:6s} {tg['class']:18s} {tg['n_pairs']:>4d}  skipped ({tg['skipped']})")
            continue
        sp = tg["spearman_test_fold"].get("spearman")
        sp_str = f"{sp:>9.3f}" if sp is not None else f"{'-':>9s}"
        d = out["offtarget_matrix"]["per_target_mean_delta"].get(tg["accession"])
        d_str = f"{d:+.3f}" if d is not None else "-"
        print(f"{tg['accession']:8s} {tg['gene']:6s} {tg['class']:18s} {tg['n_pairs']:>4d} "
              f"{tg['auroc_random']:>9.3f} {tg['auroc_matched']:>10.3f} {sp_str} "
              f"{tg['ef_top5pct']:>6.2f}  {d_str}")
    print(f"\nwall time: {wall:.1f}s")

    # --- Writeup ---
    md_path = REPO / "results" / "datafit_ceiling.md"
    out["_json_basename"] = json_path.name
    write_markdown(out, md_path)


if __name__ == "__main__":
    main()
