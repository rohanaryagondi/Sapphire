"""Phase 2c — do MAMMAL protein embeddings recover functional family structure?

Relevant to Quiver's CRISPR-N gene clustering ("cluster genes by functional state")
and the Sapphire KG idea (gene/drug nodes embedded in a shared space). We embed
proteins from 5 distinct families and check whether nearest neighbors are same-family
and whether intra-family similarity exceeds inter-family.

Base-model encoder embedding (masked mean-pool, 768-d). Note: very long targets
(ion channels ~2000 aa) are truncated by the tokenizer — flagged.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/phase2c_protein_embedding.py
"""

from __future__ import annotations

import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")

import json
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver.embed import load_base_model, embed  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

FAMILIES = {
    "kinase":     ["P00519", "P00533", "P12931", "P28482", "P24941"],   # ABL1 EGFR SRC MAPK1 CDK2
    "gpcr":       ["P14416", "P07550", "P28223", "P35372", "P21554"],   # DRD2 ADRB2 HTR2A OPRM1 CNR1
    "ion_channel":["Q9Y5Y9", "Q14524", "P51787", "Q13936", "Q05586"],   # Nav1.8 Nav1.5 KCNQ1 Cav1.2 GRIN1
    "protease":   ["P07477", "P00734", "P08246", "P42574", "P09958"],   # TRY1 thrombin NE CASP3 FURIN
    "nuclear_rec":["P03372", "P04150", "P37231", "P10275", "P11473"],   # ESR1 NR3C1 PPARG AR VDR
}


def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x) ** 0.5; vy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    import torch
    names, fams, embs = [], [], []
    model, tok, dev = load_base_model()
    print(f"base model on {dev}; embedding proteins ...")
    for fam, accs in FAMILIES.items():
        for acc in accs:
            try:
                seq = fetch_uniprot_sequence(acc)
            except Exception as e:
                print(f"  fetch fail {acc}: {e}"); continue
            names.append(acc); fams.append(fam); embs.append(embed(model, tok, seq, kind="protein"))
            print(f"  {fam:12s} {acc} len={len(seq)}{'  [truncated]' if len(seq) > 1250 else ''}")
    E = torch.stack(embs)
    n = len(names)
    sim = {(i, j): float(E[i] @ E[j]) for i, j in combinations(range(n), 2)}

    # nearest-neighbor same-family rate
    correct = 0
    print("\nnearest neighbor per protein:")
    for i in range(n):
        j = max((k for k in range(n) if k != i), key=lambda k: sim[(min(i, k), max(i, k))])
        ok = fams[i] == fams[j]; correct += ok
        print(f"  {names[i]} ({fams[i]:11s}) -> {names[j]} ({fams[j]:11s}) {'OK' if ok else 'x'}")
    nn = correct / n

    pairs = list(combinations(range(n), 2))
    intra = [sim[p] for p in pairs if fams[p[0]] == fams[p[1]]]
    inter = [sim[p] for p in pairs if fams[p[0]] != fams[p[1]]]
    sep = sum(intra) / len(intra) - sum(inter) / len(inter)

    summary = {"timestamp": ts, "n": n, "n_families": len(FAMILIES),
               "nn_same_family": round(nn, 3),
               "intra_minus_inter_cosine": round(sep, 3),
               "random_baseline_nn": round((5 - 1) / (n - 1), 3)}
    (REPO / "results" / f"phase2c_protein_embedding_{ts}.json").write_text(json.dumps(summary, indent=2))
    print(f"\nNN same-family: {nn:.2f}  (random ~{(5-1)/(n-1):.2f})   "
          f"intra−inter cosine: {sep:+.3f}")


if __name__ == "__main__":
    main()
