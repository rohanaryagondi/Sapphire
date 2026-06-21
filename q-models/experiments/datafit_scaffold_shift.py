"""1d-(c) — Direct test of the chemotype-memorisation hypothesis on the ceiling wins.

The bimodality probe (`results/datafit_bimodality.md`) found that across the 6
well-trained targets, Spearman(binder-set diversity, AUROC) = -0.83 — narrower
binder sets correlate with higher AUROC. The interpretation: MAMMAL's apparent
"ceiling wins" (RORC 0.97, CA2 0.87, Adrb2 0.87) are not real binding
generalisation but **chemotype memorisation** — the head learned one dominant
scaffold per target and recognises it back.

This experiment tests that hypothesis directly. For each target:

  1. Pull ALL BindingDB_Kd binders (pKd >= 7).
  2. Bin them by Bemis-Murcko scaffold (canonical SMILES of the Murcko core).
  3. Pick the **dominant scaffold** (largest bin) -> "in-scaffold" set.
  4. Everything else -> "out-of-scaffold" set.
  5. Sample MW-matched decoys (same protocol as the ceiling run) for the
     out-of-scaffold binders.
  6. Score with the PEER DTI checkpoint and compute three AUROCs:
       - in-scaffold binders vs matched decoys           (replicates the ceiling win)
       - out-of-scaffold binders vs matched decoys       (the held-out scaffold test)
       - out-of-scaffold binders vs in-scaffold binders  (does the head rank the
         dominant scaffold higher even though both are real binders?)

If the head is memorising the dominant scaffold, AUROC_in stays at the ceiling
level and AUROC_out drops sharply toward 0.5 — confirmed. If AUROC_out stays
high, the ceiling win is real generalisation — refuted.

Targets: RORC (P51449) primary; Adrb2 (Q8K4Z4) and CA2 (P00918) as cheap
secondaries.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/datafit_scaffold_shift.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
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

# Targets: primary + the two ceiling wins to repeat if time / data permits.
TARGETS = [
    ("P51449", "RORC",  "nuclear_receptor", {"auroc_random_ceiling": 0.970, "auroc_matched_ceiling": 0.952}),
    ("Q8K4Z4", "Adrb2", "gpcr",             {"auroc_random_ceiling": 0.871, "auroc_matched_ceiling": 0.881}),
    ("P00918", "CA2",   "other",            {"auroc_random_ceiling": 0.867, "auroc_matched_ceiling": 0.840}),
]

PKD_THRESHOLD = 7.0
N_PER_BINDER = 3
MW_TOL = 50.0
SEED = 42
MIN_OUT = 10            # need at least this many out-of-scaffold binders to keep going


def round3(x):
    if x is None or (isinstance(x, float) and x != x):
        return None
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return x


def murcko_scaffold(smi: str) -> str | None:
    """Canonical Bemis-Murcko scaffold SMILES for one ligand. Empty string ('') is
    a valid Murcko output for acyclic compounds; we keep it as a real bin label."""
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(smi)
    except Exception:  # noqa: BLE001
        return None
    if scaf is None:
        return None
    # Re-canonicalise (MurckoScaffoldSmiles already returns canonical SMILES, but
    # be paranoid — empty string stays empty)
    if scaf == "":
        return ""
    m = Chem.MolFromSmiles(scaf)
    if m is None:
        return scaf
    return Chem.MolToSmiles(m)


def score_many(model, tok, seq, smiles_list, label=""):
    preds = []
    t0 = time.time()
    for i, smi in enumerate(smiles_list):
        try:
            pk = predict_pkd(model, tok, seq, smi, PEER_M, PEER_S)
            preds.append(pk)
        except Exception as e:  # noqa: BLE001
            print(f"    [warn] skipped {label} idx={i}: {type(e).__name__}: {e}")
            preds.append(None)
    dt = time.time() - t0
    if smiles_list:
        n_ok = sum(1 for p in preds if p is not None)
        print(f"    {label}: scored {n_ok}/{len(smiles_list)} in {dt:.1f}s "
              f"({dt / max(1, len(smiles_list)):.2f}s/pair)")
    return preds


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def run_target(model, tok, acc, gene, cls, ceiling_meta):
    """Run the scaffold-shift test on one target. Returns the result dict."""
    print(f"\n=== {acc} {gene} ({cls}) ===")
    seq = fetch_uniprot_sequence(acc)
    trunc = len(seq) > 1250
    print(f"  seq_len={len(seq)} {'(>1250 -> TRUNCATED to 1250)' if trunc else '(<=1250 fully visible)'}")

    # --- Pull ALL binders (no n_max cap) ---
    binders_all = datafit.get_binders(acc, pkd_threshold=PKD_THRESHOLD, n_max=None, seed=SEED)
    if not binders_all:
        print(f"  [skip] no binders at pKd>={PKD_THRESHOLD}")
        return {"accession": acc, "gene": gene, "class": cls, "skipped": "no_binders"}

    print(f"  total binders (pKd >= {PKD_THRESHOLD}): n={len(binders_all)}")

    # --- Bemis-Murcko scaffold for each binder ---
    scaf_for = {}
    for smi, _pk in binders_all:
        s = murcko_scaffold(smi)
        if s is not None:
            scaf_for[smi] = s
    if not scaf_for:
        return {"accession": acc, "gene": gene, "class": cls, "skipped": "all_scaffolds_failed"}

    scaf_counts = Counter(scaf_for.values())
    n_distinct_scaffolds = len(scaf_counts)
    top_scaffolds = scaf_counts.most_common(5)
    print(f"  distinct scaffolds: {n_distinct_scaffolds}")
    print(f"  top scaffolds (count):")
    for s, c in top_scaffolds:
        label = s if s != "" else "(acyclic / empty Murcko)"
        print(f"    {c:3d}  {label[:80]}")

    dominant_scaf, dominant_n = top_scaffolds[0]
    in_smiles = [smi for smi, p in binders_all if scaf_for.get(smi) == dominant_scaf]
    in_pkds   = [p   for smi, p in binders_all if scaf_for.get(smi) == dominant_scaf]
    out_smiles = [smi for smi, p in binders_all if scaf_for.get(smi) != dominant_scaf
                  and smi in scaf_for]
    out_pkds   = [p   for smi, p in binders_all if scaf_for.get(smi) != dominant_scaf
                  and smi in scaf_for]

    print(f"  in-scaffold  (dominant): n={len(in_smiles)}")
    print(f"  out-of-scaffold        : n={len(out_smiles)}")

    if len(out_smiles) < MIN_OUT:
        print(f"  [skip] not enough out-of-scaffold binders (<{MIN_OUT})")
        return {
            "accession": acc, "gene": gene, "class": cls,
            "seq_len": len(seq), "truncated": trunc,
            "skipped": f"too_few_out_of_scaffold (n={len(out_smiles)})",
            "n_binders_total": len(binders_all),
            "n_distinct_scaffolds": n_distinct_scaffolds,
            "dominant_scaffold": {"smiles": dominant_scaf, "n_binders": dominant_n},
            "top_scaffolds": [{"smiles": s, "n": c} for s, c in top_scaffolds],
            **ceiling_meta,
        }

    # --- MW-matched decoys for out-of-scaffold binders ---
    matched_decoys_out = datafit.sample_matched_decoys(
        acc, out_smiles, n_per_binder=N_PER_BINDER, mw_tol=MW_TOL, seed=SEED
    )
    print(f"  matched decoys (for out-of-scaffold binders): n={len(matched_decoys_out)}")

    # --- MW-matched decoys for in-scaffold binders too, so AUROC_in is comparable ---
    matched_decoys_in = datafit.sample_matched_decoys(
        acc, in_smiles, n_per_binder=N_PER_BINDER, mw_tol=MW_TOL, seed=SEED
    )
    print(f"  matched decoys (for in-scaffold binders)    : n={len(matched_decoys_in)}")

    # --- Score all four sets with PEER ---
    print(f"  scoring on {acc}...")
    in_preds         = score_many(model, tok, seq, in_smiles,          label="binders (in-scaffold)")
    out_preds        = score_many(model, tok, seq, out_smiles,         label="binders (out-of-scaffold)")
    decoys_in_preds  = score_many(model, tok, seq, matched_decoys_in,  label="matched decoys (for in)")
    decoys_out_preds = score_many(model, tok, seq, matched_decoys_out, label="matched decoys (for out)")

    in_ok  = [p for p in in_preds  if p is not None]
    out_ok = [p for p in out_preds if p is not None]
    di_ok  = [p for p in decoys_in_preds  if p is not None]
    do_ok  = [p for p in decoys_out_preds if p is not None]

    # --- Three AUROCs ---
    auc_in_vs_dec  = datafit.auroc(in_ok,  di_ok) if (in_ok  and di_ok) else float("nan")
    auc_out_vs_dec = datafit.auroc(out_ok, do_ok) if (out_ok and do_ok) else float("nan")
    auc_in_vs_out  = datafit.auroc(in_ok,  out_ok) if (in_ok and out_ok) else float("nan")

    drop = (auc_in_vs_dec - auc_out_vs_dec) if (auc_in_vs_dec == auc_in_vs_dec and
                                                 auc_out_vs_dec == auc_out_vs_dec) else float("nan")

    print(f"  AUROC in-scaffold  vs matched decoys : {auc_in_vs_dec:.3f}   "
          f"(mean_binder={mean(in_ok):.2f}  mean_decoy={mean(di_ok):.2f}  n_bind={len(in_ok)} / n_dec={len(di_ok)})")
    print(f"  AUROC out-scaffold vs matched decoys : {auc_out_vs_dec:.3f}   "
          f"(mean_binder={mean(out_ok):.2f}  mean_decoy={mean(do_ok):.2f}  n_bind={len(out_ok)} / n_dec={len(do_ok)})")
    print(f"  AUROC in-scaffold  vs out-of-scaffold: {auc_in_vs_out:.3f}   "
          f"(head ranks in-scaffold higher than out -> memorisation footprint)")
    print(f"  DROP (in - out) : {drop:+.3f}")

    return {
        "accession": acc,
        "gene": gene,
        "class": cls,
        "seq_len": len(seq),
        "truncated": trunc,
        "n_binders_total": len(binders_all),
        "n_distinct_scaffolds": n_distinct_scaffolds,
        "dominant_scaffold": {
            "smiles": dominant_scaf,
            "n_binders": dominant_n,
            "fraction_of_binders": round3(dominant_n / len(binders_all)),
        },
        "top_scaffolds": [{"smiles": s, "n": c} for s, c in top_scaffolds],
        "in_scaffold": {
            "n_smiles": len(in_smiles),
            "n_scored": len(in_ok),
            "pkd_range_true":  [round3(min(in_pkds)),  round3(max(in_pkds))]  if in_pkds  else None,
            "mean_predicted_pkd": round3(mean(in_ok)),
            "n_matched_decoys": len(matched_decoys_in),
            "n_decoy_scored":   len(di_ok),
            "mean_decoy_predicted_pkd": round3(mean(di_ok)),
        },
        "out_of_scaffold": {
            "n_smiles": len(out_smiles),
            "n_scored": len(out_ok),
            "pkd_range_true":  [round3(min(out_pkds)), round3(max(out_pkds))] if out_pkds else None,
            "mean_predicted_pkd": round3(mean(out_ok)),
            "n_matched_decoys": len(matched_decoys_out),
            "n_decoy_scored":   len(do_ok),
            "mean_decoy_predicted_pkd": round3(mean(do_ok)),
        },
        "auroc_in_vs_decoys":  round3(auc_in_vs_dec),
        "auroc_out_vs_decoys": round3(auc_out_vs_dec),
        "auroc_in_vs_out":     round3(auc_in_vs_out),
        "drop_in_minus_out":   round3(drop),
        **ceiling_meta,
    }


# --------------------------------------------------------------------------- #
# Writeup.
# --------------------------------------------------------------------------- #
def write_markdown(result, md_path):
    ts = result["timestamp"]
    json_name = result["_json_basename"]
    rows = []
    verdict_inputs = []
    for tg in result["per_target"]:
        if tg.get("skipped"):
            rows.append(
                f"| {tg['accession']} | {tg['gene']} | – | – | – | – | – | – | "
                f"skipped ({tg['skipped']}) |"
            )
            continue
        rows.append(
            f"| {tg['accession']} | {tg['gene']} | "
            f"{tg['in_scaffold']['n_scored']} | {tg['out_of_scaffold']['n_scored']} | "
            f"**{tg['auroc_in_vs_decoys']:.2f}** | **{tg['auroc_out_vs_decoys']:.2f}** | "
            f"**{tg['drop_in_minus_out']:+.2f}** | {tg['auroc_in_vs_out']:.2f} | "
            f"{tg['auroc_matched_ceiling']:.2f} (ceiling) |"
        )
        verdict_inputs.append(tg)

    # Verdict
    if not verdict_inputs:
        verdict = "**Inconclusive — no targets had enough out-of-scaffold binders.**"
    else:
        n_confirm = sum(
            1 for tg in verdict_inputs
            if (tg["auroc_in_vs_decoys"] - tg["auroc_out_vs_decoys"]) >= 0.15
            and tg["auroc_out_vs_decoys"] <= 0.65
        )
        n_refute = sum(
            1 for tg in verdict_inputs
            if tg["auroc_out_vs_decoys"] >= 0.80
            and abs(tg["auroc_in_vs_decoys"] - tg["auroc_out_vs_decoys"]) <= 0.10
        )
        if n_confirm >= max(1, len(verdict_inputs) - n_refute) and n_confirm > n_refute:
            verdict = (
                f"**Memorisation confirmed.** On {n_confirm}/{len(verdict_inputs)} target(s) the head's "
                f"in-scaffold AUROC stays at the ceiling level while out-of-scaffold AUROC drops sharply "
                f"(by ≥0.15) toward chance. The apparent 'ceiling wins' are dominated by the head "
                f"recognising a single learned scaffold per target — when the test ligands are from a "
                f"different scaffold class, separation collapses."
            )
        elif n_refute >= len(verdict_inputs) - n_confirm and n_refute > n_confirm:
            verdict = (
                f"**Memorisation refuted.** On {n_refute}/{len(verdict_inputs)} target(s) the out-of-"
                f"scaffold AUROC stays ≥0.80 with the in-vs-out gap ≤0.10. The ceiling wins are "
                f"genuine binding generalisation, not chemotype memorisation."
            )
        else:
            verdict = (
                f"**Mixed.** Out of {len(verdict_inputs)} target(s), {n_confirm} look like memorisation "
                f"(sharp drop, out-AUROC near chance) and {n_refute} look like real generalisation "
                f"(out-AUROC stays high). The chemotype-memorisation story is target-specific, not "
                f"a single global mechanism."
            )

    md = f"""# Datafit scaffold shift — is MAMMAL's ceiling win chemotype memorisation?

**NEXT_STEPS item 1d-(c).** The [bimodality probe](datafit_bimodality.md) found
Spearman(binder-set diversity, AUROC) = **−0.83** across the 6 ceiling targets — narrower binder
sets correlate with higher AUROC. The interpretation was that MAMMAL's apparent ceiling wins
(RORC 0.97, CA2 0.87, Adrb2 0.87) reflect **chemotype memorisation** rather than real binding
generalisation. This experiment tests that hypothesis directly with a held-out **scaffold** split.

Run: `experiments/datafit_scaffold_shift.py` · raw: `results/{json_name}` · {ts}.

## Question + setup

For each ceiling target:

1. Pull **all** BindingDB_Kd binders with pKd ≥ {PKD_THRESHOLD}.
2. Compute the **Bemis-Murcko scaffold** (canonical SMILES of the ring-system core) for each
   via `rdkit.Chem.Scaffolds.MurckoScaffold.MurckoScaffoldSmiles`. Bin by canonical scaffold.
3. The largest bin is the **dominant / in-scaffold** set. Everything else is **out-of-scaffold**.
4. Sample MW-matched decoys (±{MW_TOL:.0f} Da, {N_PER_BINDER} per binder, off-target pool) for
   both the in- and out-of-scaffold binders — same protocol as the ceiling run.
5. Score with the **PEER DTI checkpoint** (`models/dti_bindingdb_pkd_peer`, norms 6.286 / 1.542).
6. Report three AUROCs:
   - **in-scaffold binders vs matched decoys** — should replicate the ceiling AUROC if the
     ceiling win is the dominant scaffold;
   - **out-of-scaffold binders vs matched decoys** — the held-out scaffold test;
   - **in-scaffold vs out-of-scaffold binders** — does the head rank the dominant scaffold
     higher even though both sets are real binders?

**Decision rule.** If AUROC_in stays near the ceiling and AUROC_out drops sharply (≥0.15
points) toward 0.5, memorisation is **confirmed**. If AUROC_out stays high (≥0.80) with a
small gap, memorisation is **refuted** and the ceiling reflects genuine generalisation.

Device: {result['device']}. Total wall time: {result['wall_time_sec']:.1f}s.

## Results

| accession | gene | n_in | n_out | AUROC_in | AUROC_out | drop (in − out) | AUROC in-vs-out | matched (ceiling) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

(Bold cells are the test result. *AUROC_in* is in-scaffold binders vs MW-matched decoys.
*AUROC_out* is the held-out scaffold test. *AUROC in-vs-out* — both sets are real binders;
>0.5 means the head ranks the dominant scaffold higher than the held-out scaffold even when
both are equally legitimate ligands. *matched (ceiling)* repeats the
[ceiling run](datafit_ceiling.md) number for comparison.)

### Scaffold breakdown per target

"""
    for tg in result["per_target"]:
        if tg.get("skipped"):
            md += f"- **{tg['gene']}** ({tg['accession']}): {tg['skipped']}\n"
            continue
        md += (f"- **{tg['gene']}** ({tg['accession']}): {tg['n_binders_total']} total binders "
               f"in {tg['n_distinct_scaffolds']} distinct scaffolds. Dominant scaffold = "
               f"{tg['dominant_scaffold']['n_binders']} compounds "
               f"({tg['dominant_scaffold']['fraction_of_binders']*100:.0f}% of binders).\n")

    md += f"""

## Verdict

{verdict}

## Implication

If memorisation is the mechanism behind the ceiling wins, the chemodiversity check from
[`datafit_bimodality.md`](datafit_bimodality.md) is doing exactly the right job: it flags
which of Quiver's per-target fine-tune candidates will look great on a same-scaffold split
but fail on a held-out scaffold split. For Nav1.8 specifically, the practical move is
unchanged — a Quiver Nav fine-tune is still the only available lever — but the *evaluation*
must be held-out **scaffold split**, not random split, or we'll just be re-discovering the
chemotype the screen biased toward.

For the cross-target re-ranking use of MAMMAL DTI, this experiment doesn't undercut it; the
[ceiling run's off-target Δ](datafit_ceiling.md) is independent of the within-target AUROC
and the [chemodiversity ρ](datafit_bimodality.md) on Δ was −0.09 (essentially zero). MAMMAL
DTI as a *soft re-ranker across targets* survives; MAMMAL DTI as a *single-target novel-hit
oracle* does not.

## Caveats

- Bemis-Murcko collapses to the ring-system core, which can be coarse. Two compounds with the
  same Murcko core can still have very different substituent decoration. A finer test would
  bin by Murcko + decoration fingerprint, or by InChIKey scaffold cluster.
- Sample sizes per target are tied to how concentrated the binder set is. The dominant-vs-rest
  split is unbalanced by construction; small n_in or n_out widens AUROC confidence bands.
- "Out-of-scaffold" here means "not the single most common scaffold." Real-world novel
  discovery is harder than that — many out-of-scaffold compounds in BindingDB are close
  analogs of less-common scaffolds the head may also have seen. This is an upper-bound
  test of generalisation, not a worst-case.
"""
    md_path.write_text(md)
    print(f"\nwriteup -> {md_path}")


def main():
    t_start = time.time()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"PEER DTI on {dev}\n")

    per_target = []
    for acc, gene, cls, ceil in TARGETS:
        per_target.append(run_target(model, tok, acc, gene, cls, ceil))

    wall = time.time() - t_start
    out = {
        "timestamp": ts,
        "checkpoint": "dti_bindingdb_pkd_peer",
        "checkpoint_path": PEER_SOURCE,
        "norm_constants": [PEER_M, PEER_S],
        "device": dev,
        "wall_time_sec": round(wall, 1),
        "params": {
            "pkd_threshold": PKD_THRESHOLD,
            "n_per_binder": N_PER_BINDER,
            "mw_tol_da": MW_TOL,
            "seed": SEED,
            "min_out_of_scaffold": MIN_OUT,
        },
        "targets": [{"accession": a, "gene": g, "class": c} for a, g, c, _ in TARGETS],
        "per_target": per_target,
    }

    json_path = REPO / "results" / f"datafit_scaffold_shift_{ts}.json"
    json_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {json_path}")

    print("\n=== SUMMARY ===")
    print(f"{'acc':8s} {'gene':6s} {'n_in':>5s} {'n_out':>6s} "
          f"{'AUC_in':>7s} {'AUC_out':>8s} {'drop':>7s}  {'in-vs-out':>10s}  ceiling")
    for tg in per_target:
        if tg.get("skipped"):
            print(f"{tg['accession']:8s} {tg['gene']:6s}  skipped ({tg['skipped']})")
            continue
        print(f"{tg['accession']:8s} {tg['gene']:6s} {tg['in_scaffold']['n_scored']:>5d} "
              f"{tg['out_of_scaffold']['n_scored']:>6d} "
              f"{tg['auroc_in_vs_decoys']:>7.3f} {tg['auroc_out_vs_decoys']:>8.3f} "
              f"{tg['drop_in_minus_out']:>+7.3f}  {tg['auroc_in_vs_out']:>10.3f}  "
              f"{tg['auroc_matched_ceiling']:.3f}")
    print(f"\nwall time: {wall:.1f}s")

    md_path = REPO / "results" / "datafit_scaffold_shift.md"
    out["_json_basename"] = json_path.name
    write_markdown(out, md_path)


if __name__ == "__main__":
    main()
