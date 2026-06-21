"""Phase 1 — correlation on 5-10 known drug-target pairs with real affinities.

Pulls experimental affinity (median pChEMBL value = -log10(molar Ki/Kd/IC50),
ChEMBL-standardized) for each curated pair straight from the ChEMBL REST API, so
nothing is hand-transcribed. SMILES come from ChEMBL, sequences from UniProt.
Then runs the MAMMAL DTI head and correlates predicted pKd vs experimental.

Success bar (success_criteria.md):
  PASS         Spearman > 0.4 between predicted and experimental affinity
  STRONG PASS  Spearman > 0.6
  FAIL         no correlation

Caveat: assay types are mixed (Ki/Kd/IC50 via pChEMBL); the DTI head was trained
on BindingDB Kd. pChEMBL is a reasonable common scale but not identical to pKd.
Targets > 1250 aa (e.g. Nav1.5) are truncated by the head — flagged per row.

Run:  /opt/anaconda3/envs/mammal/bin/python scripts/phase1_correlation.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable

from mammal_quiver.dti import DTI_MODEL_ID, load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"

# Curated known drug-target pairs: good ChEMBL coverage, single-chain targets,
# spanning kinases / CNS transporters & receptors / an ion channel (Nav1.5).
PAIRS = [
    ("imatinib", "ABL1", "P00519"),
    ("dasatinib", "ABL1", "P00519"),
    ("gefitinib", "EGFR", "P00533"),
    ("erlotinib", "EGFR", "P00533"),
    ("fluoxetine", "SERT", "P31645"),
    ("paroxetine", "SERT", "P31645"),
    ("haloperidol", "DRD2", "P14416"),
    ("risperidone", "DRD2", "P14416"),
    ("propranolol", "ADRB2", "P07550"),
    ("lidocaine", "Nav1.5", "Q14524"),
]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def resolve_molecule(name: str):
    """Return (molecule_chembl_id, canonical_smiles) for a drug name."""
    q = urllib.parse.quote(name)
    data = _get(f"{CHEMBL}/molecule?pref_name__iexact={q}&format=json&limit=5")
    mols = data.get("molecules", [])
    if not mols:
        raise RuntimeError(f"no ChEMBL molecule for {name!r}")
    m = mols[0]
    smiles = (m.get("molecule_structures") or {}).get("canonical_smiles")
    return m["molecule_chembl_id"], smiles


def resolve_target(accession: str) -> str:
    data = _get(f"{CHEMBL}/target?target_components__accession={accession}&format=json&limit=5")
    targets = data.get("targets", [])
    single = [t for t in targets if t.get("target_type") == "SINGLE PROTEIN"]
    chosen = (single or targets)[0]
    return chosen["target_chembl_id"]


def experimental_pchembl(mol_id: str, tgt_id: str) -> float | None:
    url = (
        f"{CHEMBL}/activity?molecule_chembl_id={mol_id}&target_chembl_id={tgt_id}"
        f"&pchembl_value__isnull=false&format=json&limit=1000"
    )
    vals = [float(a["pchembl_value"]) for a in _get(url).get("activities", []) if a.get("pchembl_value")]
    return statistics.median(vals) if vals else None


def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(rank(x), rank(y))


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x) ** 0.5
    vy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = REPO / "results"
    results_dir.mkdir(exist_ok=True)

    print("resolving ChEMBL ids + experimental affinities ...")
    rows = []
    for drug, tname, acc in PAIRS:
        try:
            mol_id, smiles = resolve_molecule(drug)
            tgt_id = resolve_target(acc)
            exp = experimental_pchembl(mol_id, tgt_id)
            seq = fetch_uniprot_sequence(acc)
            if exp is None or not smiles:
                print(f"  skip {drug}/{tname}: missing affinity or smiles")
                continue
            rows.append({"drug": drug, "target": tname, "accession": acc,
                         "mol_id": mol_id, "tgt_id": tgt_id, "smiles": smiles,
                         "seq_len": len(seq), "truncated": len(seq) > 1250,
                         "exp_pchembl": round(exp, 3), "seq": seq})
            print(f"  {drug:12s} x {tname:7s}  exp_pChEMBL={exp:.2f}  seq_len={len(seq)}")
        except Exception as e:
            print(f"  ERROR {drug}/{tname}: {e}")

    model, tok, device = load_dti_model()
    print(f"\nloaded {DTI_MODEL_ID} on {device}; predicting ...")
    for r in rows:
        r["pred_pKd"] = round(predict_pkd(model, tok, r["seq"], r["smiles"]), 4)
        print(f"  {r['drug']:12s} x {r['target']:7s}  exp={r['exp_pchembl']:.2f}  pred={r['pred_pKd']:.2f}")

    exp = [r["exp_pchembl"] for r in rows]
    pred = [r["pred_pKd"] for r in rows]
    rho = spearman(exp, pred)
    rp = pearson(exp, pred)
    verdict = "STRONG PASS" if rho > 0.6 else "PASS" if rho > 0.4 else "FAIL"

    for r in rows:
        r.pop("seq", None)  # don't dump full sequences into the json
    summary = {"timestamp": ts, "model": DTI_MODEL_ID, "device": device,
               "n_pairs": len(rows), "spearman": round(rho, 4),
               "pearson": round(rp, 4), "verdict": verdict, "pairs": rows}
    out = results_dir / f"phase1_correlation_{ts}.json"
    out.write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 60)
    print(f"n={len(rows)}  Spearman={rho:.3f}  Pearson={rp:.3f}  -> {verdict}")
    print(f"saved -> {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
