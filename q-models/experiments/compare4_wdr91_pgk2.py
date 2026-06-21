"""Compare Test 4 — WDR91 & PGK2 binder triage: ZERO-SHOT challengers vs FINE-TUNED MAMMAL.

The asymmetry that MUST be labelled: MAMMAL uses its per-target FINE-TUNED heads
(wdr91_asms / pgk2_del_cdd via generative binder_prob), while ConPLex / Boltz-2 run
ZERO-SHOT (a general DTI model given the target sequence + SMILES, no target-specific
training). This is deliberately unfavourable to the challengers. A zero-shot challenger
getting anywhere near the fine-tuned head is itself a strong result.

Sub-tests:
  4a  WDR91 ChEMBL — 27 actives vs 500 synthetic decoys      → AUROC + EF5/EF10
  4b  WDR91 SPR    — Ahmad 2023 real SPR (38 bind / ~201 non) → AUROC + EF5/EF10  [cleaner truth]
  4c  PGK2 vs PGK1 — DEL hits vs PGK1 homolog ligands         → AUROC (selectivity)

All SMILES are standardized (neutral_parent, from phase5) so every model scores
identical inputs. ConPLex needs the target sequence (WDR91 A4D1P6 / PGK2 P07205);
the fine-tuned MAMMAL head has the target baked in. Boltz-2 scores only a small
fixed subset (over the $2 screening budget) if a precomputed run exists.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare4_wdr91_pgk2.py [n_decoys] [n_pgk2]
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
sys.path.insert(0, str(REPO / "experiments"))

from baselines import common, conplex, boltz  # noqa: E402
from baselines.mammal_heads import load_finetuned, finetuned_scores  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

WDR91_SEQ = json.loads((REPO / "data" / "wdr91" / "wdr91_sequence.json").read_text())["sequence"]
PGK2_ACC = "P07205"  # human phosphoglycerate kinase 2 (PGK2)


def _std(smi):
    from phase5_wdr91_spr import neutral_parent
    return neutral_parent(smi)


def _auroc_cell(name, labels, scores, mammal_scores=None, with_ef=True):
    a = common.auroc(labels, scores)
    lo, hi = common.auroc_ci(labels, scores)
    cell = {"auroc": round(a, 4), "ci95": [round(lo, 4), round(hi, 4)], "verdict": common.auroc_verdict(a)}
    if with_ef:
        cell["ef5"] = round(common.enrichment_factor(labels, scores, 0.05), 3)
        cell["ef10"] = round(common.enrichment_factor(labels, scores, 0.10), 3)
    if mammal_scores is not None and name != "MAMMAL" and len(scores) == len(mammal_scores):
        d, dlo, dhi, p = common.paired_auroc_diff_ci(labels, scores, mammal_scores)
        cell["delta_vs_mammal"] = {"d_auroc": round(d, 4), "ci95": [round(dlo, 4), round(dhi, 4)],
                                    "p_two_sided": round(p, 4), "separable": not (dlo <= 0 <= dhi)}
    return cell


def run_subtest(title, target_seq, mammal_target, mammal_task, smiles_list, labels, n_boltz=8):
    """Score one (actives/decoys) set with fine-tuned MAMMAL + zero-shot ConPLex (+Boltz subset)."""
    print(f"\n=== {title}: {sum(labels)} positives / {len(labels)-sum(labels)} negatives ===")
    cells, raw = {}, {}

    # MAMMAL — fine-tuned head (target baked in; SMILES only)
    m, tok, task, dev = load_finetuned(mammal_target)
    print(f"  [MAMMAL {mammal_target}] fine-tuned head on {dev}, task <{task}>")
    raw["MAMMAL"] = finetuned_scores(m, tok, mammal_task or task, smiles_list, progress=title)
    cells["MAMMAL"] = _auroc_cell("MAMMAL", labels, raw["MAMMAL"])
    cells["MAMMAL"]["model_kind"] = "fine-tuned"
    del m

    # ConPLex — zero-shot (target sequence + SMILES)
    try:
        print("  [ConPLex] zero-shot scoring ...")
        raw["ConPLex"] = conplex.score_batch([(target_seq, s) for s in smiles_list])
        cells["ConPLex"] = _auroc_cell("ConPLex", labels, raw["ConPLex"], raw["MAMMAL"])
        cells["ConPLex"]["model_kind"] = "zero-shot"
    except Exception as e:  # noqa: BLE001
        print(f"    ConPLex unavailable: {e}")
        cells["ConPLex"] = {"verdict": "N/A", "model_kind": "zero-shot"}; raw["ConPLex"] = None

    # Boltz-2 — small fixed subset only (over budget for the full screen)
    bz = boltz.boltz_scores([(target_seq, s) for s in smiles_list])
    idx = [i for i, v in enumerate(bz) if v is not None]
    if len(idx) >= 6:
        sub_lab = [labels[i] for i in idx]; sub_s = [bz[i] for i in idx]
        cells["Boltz-2"] = _auroc_cell("Boltz-2", sub_lab, sub_s, with_ef=False)
        cells["Boltz-2"].update({"model_kind": "zero-shot", "n_scored": len(idx), "note": "subset (indicative, small n)"})
    else:
        cells["Boltz-2"] = {"verdict": "N/A — over budget / pending AWS", "model_kind": "zero-shot"}

    for name, c in cells.items():
        if "auroc" in c:
            ef = f" EF5={c.get('ef5')}" if "ef5" in c else ""
            print(f"    {name:9s} [{c['model_kind']:10s}] AUROC={c['auroc']:.3f} CI{c['ci95']} {c['verdict']}{ef}")
        else:
            print(f"    {name:9s} [{c.get('model_kind','')}] {c['verdict']}")
    return {"n_pos": sum(labels), "n_neg": len(labels) - sum(labels), "cells": cells,
            "raw_scores": {k: ([round(x, 5) for x in v] if v else None) for k, v in raw.items()}}


def load_4a(n_decoys):
    actives = json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))
    decoys = json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))
    decoys = decoys[:: max(1, len(decoys) // n_decoys)][:n_decoys]
    smis, labs = [], []
    for a in actives:
        s = _std(a["smiles"])
        if s: smis.append(s); labs.append(1)
    for d in decoys:
        s = _std(d if isinstance(d, str) else d.get("smiles"))
        if s: smis.append(s); labs.append(0)
    return smis, labs


def load_4b():
    from phase5_wdr91_spr import load_spr_data
    df = load_spr_data()  # already neutral_parent-standardized
    smis = df["smiles"].tolist()
    labs = df["is_binder"].astype(int).tolist()
    return smis, labs


def load_4c(n_pgk2):
    rows = list(csv.DictReader(open(REPO / "data" / "pgk2" / "DEL_hit_candidates_1.csv")))
    rows.sort(key=lambda r: -int(r["count_PGK2"]))
    hits = [r["SMILES"] for r in rows[:: max(1, len(rows) // n_pgk2)]][:n_pgk2]
    pgk1 = [m["smiles"] for m in json.load(open(REPO / "data" / "pgk2" / "pgk1_chembl_ligands.json"))]
    smis, labs = [], []
    for s in hits:
        st = _std(s)
        if st: smis.append(st); labs.append(1)
    for s in pgk1:
        st = _std(s)
        if st: smis.append(st); labs.append(0)
    return smis, labs


def main():
    n_decoys = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    n_pgk2 = int(sys.argv[2]) if len(sys.argv) > 2 else 99
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    subtests = {}
    s4a, l4a = load_4a(n_decoys)
    subtests["4a_wdr91_chembl"] = run_subtest("4a WDR91-ChEMBL", WDR91_SEQ, "wdr91", "WDR91_ASMS", s4a, l4a)
    s4b, l4b = load_4b()
    subtests["4b_wdr91_spr"] = run_subtest("4b WDR91-SPR", WDR91_SEQ, "wdr91", "WDR91_ASMS", s4b, l4b)
    pgk2_seq = fetch_uniprot_sequence(PGK2_ACC)
    s4c, l4c = load_4c(n_pgk2)
    subtests["4c_pgk2_selectivity"] = run_subtest("4c PGK2-vs-PGK1", pgk2_seq, "pgk2_del", "PGK2_DEL", s4c, l4c)

    report = {"timestamp": ts, "test": "wdr91_pgk2_finetuned_vs_zeroshot",
              "note": "MAMMAL = target-fine-tuned head; ConPLex/Boltz = zero-shot general DTI",
              "wdr91_seq_len": len(WDR91_SEQ), "pgk2_seq_len": len(pgk2_seq), "subtests": subtests}
    out = REPO / "results" / f"compare4_wdr91_pgk2_{ts}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
