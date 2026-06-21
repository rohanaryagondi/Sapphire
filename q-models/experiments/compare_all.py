"""Compare orchestrator — consolidate the latest compare{1,2,3,4} runs into one
scorecard JSON + render results/compare_dti_models.md.

Reads the most-recent results/compareN_*.json (run those first), builds the unified
head-to-head scorecard that answers David/James's question — "is anything better
than MAMMAL for our binder triage?" — and renders the authoritative writeup. The
decisive verdict is computed from the data (Test 3's pre-registered rule), not
narrative, so the conclusion can't be reverse-engineered.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/compare_all.py
"""

from __future__ import annotations

import glob
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
MODELS = ["MAMMAL", "ConPLex", "Boltz-2"]


def latest(pattern: str):
    hits = sorted(glob.glob(str(RESULTS / pattern)))
    return json.loads(Path(hits[-1]).read_text()) if hits else None


def _fmt_auroc(cell):
    if not cell or "auroc" not in cell:
        return cell.get("verdict", "—") if cell else "—"
    ci = cell.get("ci95", [None, None])
    s = f"{cell['auroc']:.2f} [{ci[0]:.2f},{ci[1]:.2f}]"
    if cell.get("beats_mammal_rule"):
        s += " **WIN**"
    return s


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    t1, t2, t3, t4 = (latest(f"compare1_correlation_*.json"), latest("compare2_named_test_*.json"),
                      latest("compare3_quiver_targets_*.json"), latest("compare4_wdr91_pgk2_*.json"))

    rows = []  # unified scorecard rows

    if t1:
        rows.append({"test": "1. Correlation (n=%d)" % t1["n"], "metric": "Spearman ρ vs pChEMBL",
                     "bar": "ρ>0.4 PASS", "kind": "apples-to-apples (off-the-shelf DTI)",
                     "cells": {m: (f"{c['value']:+.2f} [{c['ci95'][0]:+.2f},{c['ci95'][1]:+.2f}] {c['verdict']}"
                                   if c.get("value") is not None else c.get("verdict", "—"))
                               for m, c in t1["cells"].items()}})
    if t2:
        rows.append({"test": "2. Named (suze→Nav1.8)", "metric": "named > all 6 negatives",
                     "bar": "binary", "kind": "apples-to-apples (off-the-shelf DTI)",
                     "cells": {m: (f"{c['value']} (z {c['z_margin']:+.2f})" if c.get("z_margin") is not None
                                   else str(c.get("value", "—"))) for m, c in t2["cells"].items()}})
    if t3:
        for tname, panel in t3["panels"].items():
            rows.append({"test": f"3. {tname} triage", "metric": "AUROC actives vs decoys",
                         "bar": "AUROC>0.6 useful", "kind": "apples-to-apples (off-the-shelf DTI)",
                         "cells": {m: _fmt_auroc(panel["cells"].get(m)) for m in MODELS}})
    if t4:
        for key, sub in t4["subtests"].items():
            rows.append({"test": f"4. {key}", "metric": "AUROC (+EF5/10)",
                         "bar": "AUROC>0.6", "kind": "ZERO-SHOT challengers vs FINE-TUNED MAMMAL",
                         "cells": {m: _fmt_auroc(sub["cells"].get(m)) for m in MODELS}})

    decisive = bool(t3 and t3.get("decisive_win_fired"))
    scorecard = {"timestamp": ts, "models": MODELS, "decisive_win_fired": decisive,
                 "sources": {"t1": t1 and t1["timestamp"], "t2": t2 and t2["timestamp"],
                             "t3": t3 and t3["timestamp"], "t4": t4 and t4["timestamp"]},
                 "rows": rows}
    (RESULTS / f"compare_scorecard_{ts}.json").write_text(json.dumps(scorecard, indent=2))

    render_markdown(scorecard, ts)
    print(f"decisive win fired: {decisive}")
    print(f"saved -> results/compare_scorecard_{ts}.json and results/compare_dti_models.md")


def render_markdown(sc, ts):
    L = []
    L.append("# Compare — ConPLex & Boltz-2 vs MAMMAL on DTI / binder triage\n")
    L.append(f"_Generated {ts} from experiments/compare{{1,2,3,4}}_*.py. "
             f"Scorecard JSON: results/compare_scorecard_{ts}.json._\n")
    L.append("**Models:** MAMMAL (DTI PEER for Tests 1–3; wdr91/pgk2 fine-tuned heads for Test 4) | "
             "ConPLex v1 BindingDB (zero-shot) | Boltz-2 affinity (zero-shot, $2-capped subset).\n")
    verdict = ("a challenger BEAT MAMMAL on a Quiver target (see Test 3)" if sc["decisive_win_fired"]
               else "no challenger beat MAMMAL on the pre-registered decisive cell")
    L.append("## Bottom line\n")
    L.append(f"Decisive pre-registered win condition (Test 3: ConPLex AUROC ≥0.70 & CI lower bound >0.5 on "
             f"Nav1.8 or mTOR) — **{'FIRED' if sc['decisive_win_fired'] else 'did NOT fire'}**: "
             f"{verdict}. _(Narrative interpretation to be written in by hand.)_\n")

    L.append("## The scorecard\n")
    L.append("| Test | Metric | " + " | ".join(sc["models"]) + " | Comparison kind |")
    L.append("|---|---|" + "---|" * len(sc["models"]) + "---|")
    for r in sc["rows"]:
        cells = " | ".join(str(r["cells"].get(m, "—")) for m in sc["models"])
        L.append(f"| {r['test']} | {r['metric']} | {cells} | {r['kind']} |")
    L.append("")
    L.append("> **Banner:** Test 4 rows compare a *target-fine-tuned* MAMMAL head against *zero-shot* "
             "challengers — deliberately in MAMMAL's favour. Boltz-2 cells marked over-budget are a "
             "stated compute limitation (per-pair oracle under a $2 cap), not a failure.\n")

    L.append("## Methodology (apples-to-apples)\n")
    L.append("- Raw scores are never compared across models (ConPLex probability ≠ MAMMAL pKd ≠ Boltz "
             "affinity). Only rank-derived stats: Spearman, Mann-Whitney AUROC, enrichment, within-model "
             "z-separation. (`baselines/common.py`.)\n"
             "- CIs are stratified bootstrap; model-vs-MAMMAL uses a paired bootstrap on the same compounds "
             "(`delta_vs_mammal` in the per-test JSON), with Holm correction across the test family.\n"
             "- Tests 1–3 use MAMMAL's off-the-shelf DTI (PEER) — the apples-to-apples analog of the "
             "challengers. Test 4 uses MAMMAL's fine-tuned heads vs zero-shot challengers (labelled).\n")

    L.append("## Limitations\n")
    L.append("- n is small throughout (Test 1 n=10; Test 3 ≤7 vs 4) → wide CIs; a 0.43-vs-X gap is often "
             "not statistically separable, and the paired Δ CI is the arbiter.\n"
             "- Boltz-2 ran a $2-capped subset (binding-domain construct for Nav1.8; full-length OOMs).\n"
             "- Sequence handling differs per model (MAMMAL DTI truncates to 1250 aa; ConPLex own cap; "
             "Boltz folds the construct) — recorded per pair in the JSON.\n")

    L.append("## Implication for Quiver\n")
    L.append("_To be written by hand:_ does the commodity-enrichment + V1-T-moat thesis change? Does "
             "ConPLex earn a slot in the binder-triage stack, or does MAMMAL remain the default and nothing "
             "off-the-shelf beats it on our targets?\n")

    (RESULTS / "compare_dti_models.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
