"""Compare Test 1 — correlation on 10 known drug-target pairs (MAMMAL vs ConPLex vs Boltz-2).

Reuses the EXACT pairs + ChEMBL/UniProt fetchers from phase1_correlation, so the
ground truth (median pChEMBL) is identical to MAMMAL's original run. Each model
predicts the 10 pairs; we compare by SPEARMAN ρ only (ranks — ConPLex emits a
probability and Boltz an affinity, neither calibrated to pChEMBL). A challenger
"wins" only if the PAIRED Δρ bootstrap CI vs MAMMAL excludes 0 (n=10 is tiny — the
honest expectation is that 0.43-vs-X is not separable, and we say so).

Bar (MAMMAL's own): Spearman > 0.4 PASS, > 0.6 STRONG.
Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare1_correlation.py
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

from baselines import common, conplex, boltz  # noqa: E402
from baselines.mammal_heads import load_dti_peer, dti_scores  # noqa: E402

CACHE = REPO / "results" / "compare_pairs_cache.json"


def resolve_pairs():
    """Resolve the 10 PAIRS to (drug, target, smiles, seq, exp_pchembl), cached to disk."""
    if CACHE.is_file():
        cached = json.loads(CACHE.read_text())
        print(f"using cached resolved pairs ({len(cached)}) -> {CACHE.name}")
        return cached
    import phase1_correlation as p1
    from mammal_quiver.sequences import fetch_uniprot_sequence
    rows = []
    print("resolving ChEMBL ids + experimental affinities (one-time, cached) ...")
    for drug, tname, acc in p1.PAIRS:
        try:
            mol_id, smiles = p1.resolve_molecule(drug)
            tgt_id = p1.resolve_target(acc)
            exp = p1.experimental_pchembl(mol_id, tgt_id)
            seq = fetch_uniprot_sequence(acc)
            if exp is None or not smiles:
                print(f"  skip {drug}/{tname}: missing affinity or smiles")
                continue
            rows.append({"drug": drug, "target": tname, "accession": acc, "smiles": smiles,
                         "seq": seq, "seq_len": len(seq), "exp_pchembl": round(exp, 3)})
            print(f"  {drug:12s} x {tname:7s}  exp_pChEMBL={exp:.2f}  seq_len={len(seq)}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {drug}/{tname}: {e}")
    CACHE.write_text(json.dumps(rows, indent=2))
    return rows


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = resolve_pairs()
    pairs = [(r["seq"], r["smiles"]) for r in rows]
    exp = [r["exp_pchembl"] for r in rows]

    model_scores: dict[str, list] = {}

    # --- MAMMAL DTI (PEER) ---
    m, tok, dev = load_dti_peer()
    print(f"\n[MAMMAL] PEER DTI on {dev}; scoring {len(pairs)} pairs ...")
    model_scores["MAMMAL"] = dti_scores(m, tok, pairs, progress="T1")
    del m

    # --- ConPLex ---
    try:
        print("\n[ConPLex] scoring (subprocess) ...")
        model_scores["ConPLex"] = conplex.score_batch(pairs)
    except Exception as e:  # noqa: BLE001
        print(f"  ConPLex unavailable: {e}")
        model_scores["ConPLex"] = None

    # --- Boltz-2 (from precomputed AWS run, if any) ---
    bz = boltz.boltz_scores(pairs)
    model_scores["Boltz-2"] = bz if any(v is not None for v in bz) else None

    # --- metrics ---
    report = {"timestamp": ts, "test": "correlation_10pair", "metric": "spearman_vs_pchembl",
              "bar": ">0.4 PASS / >0.6 STRONG", "n": len(rows), "seed": 0,
              "pairs": [{k: r[k] for k in ("drug", "target", "exp_pchembl", "seq_len")} for r in rows],
              "cells": {}}
    for name, s in model_scores.items():
        if s is None or all(v is None for v in s):
            report["cells"][name] = {"value": None, "verdict": "N/A — pending AWS" if name == "Boltz-2" else "N/A"}
            continue
        # Boltz may cover only a subset; correlate on the pairs it scored.
        idx = [i for i, v in enumerate(s) if v is not None]
        sub_exp = [exp[i] for i in idx]
        sub_s = [s[i] for i in idx]
        rho = common.spearman(sub_exp, sub_s)
        lo, hi = common.spearman_ci(sub_exp, sub_s)
        cell = {"value": round(rho, 4), "ci95": [round(lo, 4), round(hi, 4)],
                "n_scored": len(idx), "verdict": common.correlation_verdict(rho),
                "raw_scores": [round(v, 5) for v in s] if len(s) <= 20 else None}
        # paired Δρ vs MAMMAL (same pairs)
        if name != "MAMMAL" and model_scores.get("MAMMAL") and len(idx) == len(rows):
            d, dlo, dhi, p = common.paired_spearman_diff_ci(exp, s, model_scores["MAMMAL"])
            cell["delta_vs_mammal"] = {"d_rho": round(d, 4), "ci95": [round(dlo, 4), round(dhi, 4)],
                                        "p_two_sided": round(p, 4),
                                        "separable": not (dlo <= 0 <= dhi)}
        report["cells"][name] = cell

    out = REPO / "results" / f"compare1_correlation_{ts}.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n" + "=" * 64)
    print(f"Test 1 — correlation (n={len(rows)})   [bar: ρ>0.4 PASS, >0.6 STRONG]")
    for name, cell in report["cells"].items():
        if cell.get("value") is None:
            print(f"  {name:9s}  {cell['verdict']}")
        else:
            d = cell.get("delta_vs_mammal")
            dtxt = f"   Δρ vs MAMMAL={d['d_rho']:+.3f} (sep={d['separable']})" if d else ""
            print(f"  {name:9s}  ρ={cell['value']:+.3f}  CI95={cell['ci95']}  {cell['verdict']}{dtxt}")
    print(f"saved -> {out}")
    print("=" * 64)


if __name__ == "__main__":
    main()
