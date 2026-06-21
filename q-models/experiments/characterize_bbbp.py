"""Characterize what the BBBP head is actually doing.

Question (NEXT_STEPS #5, Graham's flag): BBBP scores AUROC 0.97 but over-predicts
"penetrant" (TNR ~0.70). Graham suspects it's effectively a molecular-weight
heuristic ("below ~300 Da -> brain"), too permissive to trust on a "yes."
Mahdi's usable rule: trust the no's, investigate the yes's.

This script:
  1. Builds a ~50-drug panel: phase4 BBBP-literature panel + CNS/peripheral
     drugs from phase2b_quiver_targets (sirolimus, everolimus, suzetrigine,
     vixotrigine, etc.).
  2. Scores each with the MAMMAL BBBP head (molnet_infer P(<1>)).
  3. Computes RDKit physchem: MW, logP, TPSA, HBD, HBA, rotatable bonds.
  4. Spearman(BBBP score, each physchem feature).
  5. Asymmetry: of compounds with BBBP < 0.3 ("no"), what fraction are truly
     non-penetrant? Of BBBP > 0.7 ("yes"), what fraction are truly penetrant?
  6. Scatter: BBBP vs MW, coloured by logP.

Run: /opt/anaconda3/envs/mammal/bin/python experiments/characterize_bbbp.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski


# ---- Panel ---------------------------------------------------------------
# (name, label in {1=CNS-active/penetrant, 0=peripheral/non-penetrant, None=unknown}, group)
# phase4 set is duplicated wholesale; phase2b CNS/peripheral drugs are appended.
# Labels are textbook clinical pharmacology, not BBBP dataset labels.
PANEL = [
    # ---- phase4 literature panel ----
    ("morphine", 1, "opioid"),
    ("loperamide", 0, "opioid"),           # P-gp substrate, peripherally restricted
    ("diphenhydramine", 1, "antihistamine"),
    ("hydroxyzine", 1, "antihistamine"),
    ("cetirizine", 0, "antihistamine"),
    ("fexofenadine", 0, "antihistamine"),
    ("loratadine", 0, "antihistamine"),    # non-sedating (clinical) though label is debatable
    ("metoclopramide", 1, "antiemetic"),
    ("domperidone", 0, "antiemetic"),
    ("diazepam", 1, "cns_drug"),
    ("caffeine", 1, "cns_drug"),
    ("haloperidol", 1, "cns_drug"),
    ("fluoxetine", 1, "cns_drug"),
    ("donepezil", 1, "cns_drug"),
    ("carbamazepine", 1, "cns_drug"),
    ("phenytoin", 1, "cns_drug"),
    ("atenolol", 0, "peripheral_drug"),
    ("sulpiride", 0, "peripheral_drug"),
    ("sirolimus", 0, "peripheral_drug"),   # large macrocycle
    ("vancomycin", 0, "peripheral_drug"),

    # ---- phase2b Quiver targets — mTOR inhibitors (peripheral macrocycles) ----
    ("everolimus", 0, "mtor_inhibitor"),
    ("temsirolimus", 0, "mtor_inhibitor"),
    ("dactolisib", 0, "mtor_inhibitor"),    # peripheral (large kinase inhibitor)
    ("sapanisertib", 0, "mtor_inhibitor"),  # peripheral

    # ---- phase2b Nav blockers (CNS use except the peripheral-by-design ones) ----
    ("suzetrigine", 0, "nav_blocker"),     # peripherally-restricted by design (VX-548)
    ("vixotrigine", 1, "nav_blocker"),     # CNS-active (trigeminal neuralgia, crosses BBB)
    ("lidocaine", 1, "nav_blocker"),       # crosses BBB (local anesthetic / antiarrhythmic)
    ("mexiletine", 1, "nav_blocker"),
    ("ranolazine", 0, "nav_blocker"),      # peripheral cardiac use, limited CNS exposure
    ("lacosamide", 1, "nav_blocker"),      # antiepileptic, CNS

    # ---- additional clearly-CNS drugs (broaden signal) ----
    ("amitriptyline", 1, "cns_drug"),
    ("imipramine", 1, "cns_drug"),
    ("clozapine", 1, "cns_drug"),
    ("risperidone", 1, "cns_drug"),
    ("olanzapine", 1, "cns_drug"),
    ("sertraline", 1, "cns_drug"),
    ("citalopram", 1, "cns_drug"),
    ("venlafaxine", 1, "cns_drug"),
    ("zolpidem", 1, "cns_drug"),
    ("lamotrigine", 1, "cns_drug"),
    ("valproate", 1, "cns_drug"),
    ("levetiracetam", 1, "cns_drug"),
    ("gabapentin", 1, "cns_drug"),
    ("pregabalin", 1, "cns_drug"),

    # ---- additional peripheral/non-penetrant drugs ----
    ("aspirin", 0, "peripheral_drug"),
    ("ibuprofen", 0, "peripheral_drug"),
    ("metformin", 0, "peripheral_drug"),
    ("ceftriaxone", 0, "peripheral_drug"),   # large, polar, limited BBB
    ("digoxin", 0, "peripheral_drug"),
    ("furosemide", 0, "peripheral_drug"),
    ("hydrochlorothiazide", 0, "peripheral_drug"),
]


# ---- helpers --------------------------------------------------------------

def neutral_parent(smi: str) -> str | None:
    m = Chem.MolFromSmiles(smi)
    if not m:
        return None
    frags = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=True)
    m = max(frags, key=lambda x: x.GetNumAtoms())
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize
        m = rdMolStandardize.Uncharger().uncharge(m)
    except Exception:
        pass
    return Chem.MolToSmiles(m)


def fetch_smiles(name: str) -> str | None:
    # PubChem; prefer CanonicalSMILES (neutral); retry w/ backoff.
    for prop in ("CanonicalSMILES", "ConnectivitySMILES", "IsomericSMILES"):
        for attempt in range(3):
            try:
                url = (
                    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                    f"{urllib.parse.quote(name)}/property/{prop}/JSON"
                )
                with urllib.request.urlopen(url, timeout=30) as r:
                    d = json.loads(r.read().decode())
                s = d["PropertyTable"]["Properties"][0].get(prop)
                if s:
                    np_smi = neutral_parent(s)
                    if np_smi:
                        return np_smi
            except Exception:
                time.sleep(1.0 + attempt)
        time.sleep(0.3)
    return None


def physchem(smi: str) -> dict | None:
    m = Chem.MolFromSmiles(smi)
    if not m:
        return None
    return {
        "MW": float(Descriptors.MolWt(m)),
        "logP": float(Crippen.MolLogP(m)),
        "TPSA": float(Descriptors.TPSA(m)),
        "HBD": int(Lipinski.NumHDonors(m)),
        "HBA": int(Lipinski.NumHAcceptors(m)),
        "RotB": int(Lipinski.NumRotatableBonds(m)),
    }


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    from scipy.stats import spearmanr
    r, p = spearmanr(xs, ys)
    return float(r), float(p)


# ---- main -----------------------------------------------------------------

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cache_path = REPO / "results" / "_bbbp_char_smiles_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except Exception:
            cache = {}

    print(f"Building panel — {len(PANEL)} drugs (cached: {len(cache)})")
    rows = []
    for name, label, group in PANEL:
        smi = cache.get(name) or fetch_smiles(name)
        if not smi:
            print(f"  !! no SMILES for {name}; skipping")
            continue
        cache[name] = smi
        pc = physchem(smi)
        if not pc:
            print(f"  !! RDKit failed for {name}; skipping")
            continue
        rows.append({"name": name, "label": label, "group": group, "smiles": smi, **pc})

    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True))
    print(f"  resolved {len(rows)}/{len(PANEL)} drugs")

    # ---- load MAMMAL BBBP once, batch score -----
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    head = str(REPO / "models" / "moleculenet_bbbp")
    print(f"Loading BBBP head from {head} ...")
    model = Mammal.from_pretrained(head).to("mps").eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(head, "tokenizer"))
    task = {"task_name": "BBBP", "model": model, "tokenizer_op": tok}

    print("Scoring ...")
    t0 = time.time()
    for r in rows:
        try:
            r["p_bbb"] = float(
                molnet_infer.task_infer(task_dict=task, smiles_seq=r["smiles"])["score"]
            )
        except Exception as e:
            print(f"  !! score failed for {r['name']}: {e}")
            r["p_bbb"] = None
    rows = [r for r in rows if r["p_bbb"] is not None]
    print(f"  done in {time.time() - t0:.1f}s; n={len(rows)}")

    # ---- physchem correlations -----
    feats = ["MW", "logP", "TPSA", "HBD", "HBA", "RotB"]
    scores = [r["p_bbb"] for r in rows]
    corr = {}
    for f in feats:
        xs = [r[f] for r in rows]
        r, p = spearman(xs, scores)
        corr[f] = {"spearman": round(r, 3), "p_value": round(p, 4)}

    # ---- MW thresholds: where does BBBP stay reliably low / high? -----
    sorted_by_mw = sorted(rows, key=lambda r: r["MW"])
    # MW under which BBBP < 0.3 holds; MW above which BBBP > 0.7 holds
    mw_low_thresh = None
    for r in sorted_by_mw[::-1]:
        if r["p_bbb"] < 0.3:
            mw_low_thresh = round(r["MW"], 1)
            break
    mw_high_thresh = None
    for r in sorted_by_mw:
        if r["p_bbb"] > 0.7:
            mw_high_thresh = round(r["MW"], 1)
            break

    # ---- binarized predictions @ 0.5 + the no/yes asymmetry -----
    labeled = [r for r in rows if r["label"] is not None]
    tp = sum(1 for r in labeled if r["p_bbb"] >= 0.5 and r["label"] == 1)
    fp = sum(1 for r in labeled if r["p_bbb"] >= 0.5 and r["label"] == 0)
    tn = sum(1 for r in labeled if r["p_bbb"] < 0.5 and r["label"] == 0)
    fn = sum(1 for r in labeled if r["p_bbb"] < 0.5 and r["label"] == 1)
    tpr = tp / (tp + fn) if (tp + fn) else None
    tnr = tn / (tn + fp) if (tn + fp) else None
    acc = (tp + tn) / len(labeled) if labeled else None

    no_band = [r for r in labeled if r["p_bbb"] < 0.3]
    yes_band = [r for r in labeled if r["p_bbb"] > 0.7]
    no_correct = sum(1 for r in no_band if r["label"] == 0)
    yes_correct = sum(1 for r in yes_band if r["label"] == 1)
    no_frac = no_correct / len(no_band) if no_band else None
    yes_frac = yes_correct / len(yes_band) if yes_band else None

    # ---- scatter plot: BBBP vs MW, coloured by logP ------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_png = REPO / "results" / "bbbp_vs_physchem.png"
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    mws = [r["MW"] for r in rows]
    bbbp = [r["p_bbb"] for r in rows]
    logps = [r["logP"] for r in rows]
    sc = ax.scatter(mws, bbbp, c=logps, cmap="coolwarm", s=70, edgecolor="black",
                    linewidth=0.4, alpha=0.85)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.6)
    ax.axhline(0.3, color="green", linestyle=":", linewidth=0.7, alpha=0.5)
    ax.axhline(0.7, color="red", linestyle=":", linewidth=0.7, alpha=0.5)
    # label a few extremes / interesting cases
    annot = {"suzetrigine", "sirolimus", "vancomycin", "everolimus", "loperamide",
             "cetirizine", "atenolol", "caffeine", "fexofenadine", "morphine"}
    for r in rows:
        if r["name"] in annot:
            ax.annotate(r["name"], (r["MW"], r["p_bbb"]), fontsize=7,
                        xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("MW (Da)")
    ax.set_ylabel("P(BBB+) from MAMMAL BBBP head")
    ax.set_title("MAMMAL BBBP score vs. molecular weight (colour = logP)")
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("logP")
    ax.set_ylim(-0.05, 1.05)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f"Saved scatter -> {out_png}")

    # ---- summary -----
    summary = {
        "timestamp": ts,
        "n_panel": len(rows),
        "n_labeled": len(labeled),
        "spearman_bbbp_vs_physchem": corr,
        "binarized_at_0.5": {
            "tpr": round(tpr, 3) if tpr is not None else None,
            "tnr": round(tnr, 3) if tnr is not None else None,
            "accuracy": round(acc, 3) if acc is not None else None,
            "confusion": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
        },
        "no_vs_yes_asymmetry": {
            "n_in_no_band_lt_0.3": len(no_band),
            "frac_truly_nonpenetrant_in_no_band": round(no_frac, 3) if no_frac is not None else None,
            "n_in_yes_band_gt_0.7": len(yes_band),
            "frac_truly_penetrant_in_yes_band": round(yes_frac, 3) if yes_frac is not None else None,
        },
        "mw_thresholds": {
            "max_MW_with_bbbp_lt_0.3": mw_low_thresh,
            "min_MW_with_bbbp_gt_0.7": mw_high_thresh,
            "note": ("Above max_MW_with_bbbp_lt_0.3 every drug scored >= 0.3; "
                     "below min_MW_with_bbbp_gt_0.7 every drug scored <= 0.7. "
                     "Use to inspect the MW heuristic Graham suspected."),
        },
        "rows": rows,
    }
    out_json = REPO / "results" / f"bbbp_characterization_{ts}.json"
    out_json.write_text(json.dumps(summary, indent=2))

    # ---- pretty print --------
    print("\n=== Spearman( BBBP score , physchem feature ) ===")
    print(f"  {'feat':6s} {'rho':>7s} {'p':>10s}")
    for f in feats:
        c = corr[f]
        print(f"  {f:6s} {c['spearman']:+7.3f} {c['p_value']:10.4f}")

    print("\n=== Binarized @ 0.5 ===")
    print(f"  TPR={tpr:.3f}  TNR={tnr:.3f}  acc={acc:.3f}  (TP={tp} FP={fp} TN={tn} FN={fn})")

    print("\n=== No-vs-Yes asymmetry ===")
    print(f"  BBBP < 0.3  -> {no_correct}/{len(no_band)} = "
          f"{(no_frac*100 if no_frac is not None else 0):.0f}% truly non-penetrant")
    print(f"  BBBP > 0.7  -> {yes_correct}/{len(yes_band)} = "
          f"{(yes_frac*100 if yes_frac is not None else 0):.0f}% truly penetrant")

    print("\n=== MW thresholds ===")
    print(f"  max MW with BBBP<0.3: {mw_low_thresh}")
    print(f"  min MW with BBBP>0.7: {mw_high_thresh}")

    print("\nrows by p_bbb:")
    for r in sorted(rows, key=lambda x: x["p_bbb"]):
        lab = "+" if r["label"] == 1 else ("-" if r["label"] == 0 else "?")
        print(f"  {r['name']:18s} lab={lab} MW={r['MW']:6.1f} logP={r['logP']:+5.2f} "
              f"TPSA={r['TPSA']:5.1f} HBD={r['HBD']} HBA={r['HBA']} -> P(BBB+)={r['p_bbb']:.3f}")

    print(f"\nwrote {out_json}")
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()
