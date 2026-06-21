"""Compare ADMET-AI vs MAMMAL on the de-risking layer (NEXT_STEPS item 2 — model #3).

Slide 9 (June-4 deck) flagged ADMET-AI as the replacement for MAMMAL's
unusable-out-of-distribution ClinTox head — 41 calibrated ADMET endpoints in one
shot. This compares them head-to-head on the same 30-drug panel (15 safe + 15
withdrawn/black-box toxic) used in `phase5_tox_alternatives.py`, where MAMMAL's
ClinTox head clocked 0 % TPR (missed every external toxic).

ADMET-AI endpoints we score: ClinTox (direct), DILI (the phase5 panel is
DILI-heavy), hERG (terfenadine/cisapride/mibefradil), AMES (mutagenicity),
BBB_Martins (vs MAMMAL BBBP). For each binary endpoint we report TPR / TNR at the
0.5 threshold (standard).

For MAMMAL we score BBBP and ClinTox via the molnet_infer path that the existing
phase scripts use. Comparison criterion: does ADMET-AI flag the toxics MAMMAL
missed?

Run: /opt/anaconda3/envs/mammal/bin/python experiments/compare_admet_ai.py
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

# Reuse the phase5 panel — exact same compounds for apples-to-apples.
COMPOUNDS = [
    # safe=0
    {"name": "aspirin",        "smiles": "CC(=O)Oc1ccccc1C(=O)O",                   "toxic": 0},
    {"name": "ibuprofen",      "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",              "toxic": 0},
    {"name": "metformin",      "smiles": "CN(C)C(=N)NC(N)=N",                        "toxic": 0},
    {"name": "atorvastatin",   "smiles": "CC(C)c1n(CC(O)CC(O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2F)c1C(C)C", "toxic": 0},
    {"name": "omeprazole",     "smiles": "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1", "toxic": 0},
    {"name": "metoprolol",     "smiles": "COCCc1ccc(OCC(O)CNC(C)C)cc1",              "toxic": 0},
    {"name": "amlodipine",     "smiles": "CCOC(=O)C1=C(COCCN)NC(C)=C(C(=O)OC)C1c1ccccc1Cl", "toxic": 0},
    {"name": "gabapentin",     "smiles": "NCC1(CC(=O)O)CCCCC1",                      "toxic": 0},
    {"name": "citalopram",     "smiles": "CN(C)CCCC1(OCC#N)c2ccc(F)cc2-c2ccccc21",  "toxic": 0},
    {"name": "donepezil",      "smiles": "COc1cc2c(cc1OC)CC(CC(=O)Cc1ccc(OC)c(OC)c1)N(C)CC2", "toxic": 0},
    {"name": "memantine",      "smiles": "CC12CC(C)(CC(C1)(CC2)N)C",                 "toxic": 0},
    {"name": "caffeine",       "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",            "toxic": 0},
    {"name": "diphenhydramine","smiles": "CN(C)CCOC(c1ccccc1)c1ccccc1",              "toxic": 0},
    {"name": "lidocaine",      "smiles": "CCN(CC)CC(=O)Nc1c(C)cccc1C",               "toxic": 0},
    {"name": "fluoxetine",     "smiles": "CNCCC(OC1=CC=C(C=C1)C(F)(F)F)c1ccccc1",   "toxic": 0},
    # toxic=1 (withdrawn / black-box)
    {"name": "cerivastatin",   "smiles": "OC(CC(O)CC(=O)O)C=CC1=C(C(C)C)N(C)C(=C1C(=O)OCC)c1ccc(F)cc1", "toxic": 1},
    {"name": "troglitazone",   "smiles": "O=C1CSC(=O)N1Cc1ccc(OCC(C)(C)c2ccc(C)cc2-c2ccc(C)cc2O)cc1", "toxic": 1},
    {"name": "terfenadine",    "smiles": "OC(CCN1CCC(CC1)c1ccccc1)c1ccc(C(C)(C)C)cc1", "toxic": 1},
    {"name": "thalidomide",    "smiles": "O=C1CCC(=O)N1C1CC(=O)Nc2ccccc21",          "toxic": 1},
    {"name": "cisapride",      "smiles": "COc1cc(NC(=O)c2cc(Cl)c(N)c(OC)c2)ccc1N1CCCCC1", "toxic": 1},
    {"name": "bromfenac",      "smiles": "NC1=C(CC(=O)c2ccc(Br)cc2)C(=O)c2ccccc21", "toxic": 1},
    {"name": "mibefradil",     "smiles": "COC(=O)N1CCN(C)CC1CC(=O)Oc1cccc2c1CCC1(CCCC1)c1ccccc1", "toxic": 1},
    {"name": "trovafloxacin",  "smiles": "OC(=O)c1cn2c(nc1=O)c(C1CC1)cc2N1CC(F)(F)C1", "toxic": 1},
    {"name": "grepafloxacin",  "smiles": "CC1COc2c(N3CCN(C)CC3)c(F)cc3c(=O)c(C(=O)O)cn1c23", "toxic": 1},
    {"name": "alosetron",      "smiles": "CN1C(=O)Nc2ccc3[nH]cnc3c21",               "toxic": 1},
    {"name": "valdecoxib",     "smiles": "Cc1ccc(-c2cc(=O)no2)cc1-c1ccc(S(N)(=O)=O)cc1", "toxic": 1},
    {"name": "ximelagatran",   "smiles": "CCOC(=O)/N=C/c1ccc(CNC(=O)CN2CCC(N)CC2)cc1", "toxic": 1},
    {"name": "pemoline",       "smiles": "NC1=NC(=O)C(c2ccccc2)O1",                  "toxic": 1},
    {"name": "rofecoxib",      "smiles": "CS(=O)(=O)c1ccc(-c2ccoc2-c2ccccc2)cc1",    "toxic": 1},
    {"name": "tegaserod",      "smiles": "CCCCCNC(=N)NN=Cc1c[nH]c2cc(OC)ccc12",      "toxic": 1},
]


def confusion(y_true, y_pred01):
    """Returns (TP, FP, FN, TN, TPR, TNR, accuracy)."""
    TP = FP = FN = TN = 0
    for t, p in zip(y_true, y_pred01):
        if t == 1 and p == 1: TP += 1
        elif t == 0 and p == 1: FP += 1
        elif t == 1 and p == 0: FN += 1
        elif t == 0 and p == 0: TN += 1
    n = TP + FP + FN + TN
    tpr = TP / (TP + FN) if (TP + FN) else float("nan")
    tnr = TN / (TN + FP) if (TN + FP) else float("nan")
    acc = (TP + TN) / n if n else float("nan")
    return {"TP": TP, "FP": FP, "FN": FN, "TN": TN,
            "TPR": round(tpr, 3), "TNR": round(tnr, 3), "accuracy": round(acc, 3),
            "n": n}


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Filter out SMILES that RDKit can't parse — ADMET-AI silently drops those
    # and the index mismatch breaks the per-compound table.
    from rdkit import Chem
    valid = []
    for c in COMPOUNDS:
        m = Chem.MolFromSmiles(c["smiles"])
        if m is None:
            print(f"  [drop] invalid SMILES for {c['name']}: {c['smiles']}")
            continue
        valid.append({**c, "smiles_canonical": Chem.MolToSmiles(m)})
    print(f"valid compounds: {len(valid)}/{len(COMPOUNDS)}")
    smiles = [c["smiles_canonical"] for c in valid]
    names = [c["name"] for c in valid]
    y = [c["toxic"] for c in valid]
    COMPOUNDS_VALID = valid  # local alias used below

    # --- ADMET-AI (one call, full panel) ---
    print(f"\n[ADMET-AI] scoring {len(smiles)} compounds ...")
    t0 = time.time()
    from admet_ai import ADMETModel
    admet = ADMETModel()
    df = admet.predict(smiles=smiles)
    if len(df) != len(smiles):
        # ADMET-AI's own validator may still drop a few. Re-align.
        kept = set(df.index)
        print(f"  ADMET-AI kept {len(df)}/{len(smiles)} compounds (indices: {sorted(kept)[:5]}...)")
        valid_idx = sorted(kept)
        COMPOUNDS_VALID = [valid[i] for i in valid_idx]
        smiles = [smiles[i] for i in valid_idx]
        names = [names[i] for i in valid_idx]
        y = [y[i] for i in valid_idx]
        df = df.iloc[range(len(valid_idx))].reset_index(drop=True)
    print(f"  ADMET-AI scored in {time.time() - t0:.1f}s ({df.shape[1]} endpoints)")

    # --- MAMMAL BBBP + ClinTox (via molnet_infer) ---
    BBBP_SRC = str(REPO / "models" / "moleculenet_bbbp")
    CTOX_SRC = str(REPO / "models" / "moleculenet_clintox_tox")
    print(f"\n[MAMMAL] scoring BBBP + ClinTox ...")
    t0 = time.time()
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer

    mammal_scores = {}
    for label, src, task in (("MAMMAL_BBBP", BBBP_SRC, "BBBP"),
                              ("MAMMAL_ClinTox", CTOX_SRC, "TOXICITY")):
        m = Mammal.from_pretrained(src).to("mps").eval()
        t = ModularTokenizerOp.from_pretrained(f"{src}/tokenizer")
        td = {"task_name": task, "model": m, "tokenizer_op": t}
        vals = []
        for s in smiles:
            try:
                v = molnet_infer.task_infer(task_dict=td, smiles_seq=s)["score"]
            except Exception as e:  # noqa: BLE001
                print(f"  [warn] {label} on '{s[:30]}...': {e}")
                v = None
            vals.append(v)
        mammal_scores[label] = vals
        del m
    print(f"  MAMMAL scored in {time.time() - t0:.1f}s")

    # --- Assemble per-compound table ---
    rows = []
    for i, c in enumerate(COMPOUNDS_VALID):
        row = {"name": c["name"], "smiles": c["smiles"], "toxic": c["toxic"],
               "admet_ClinTox": float(df["ClinTox"].iloc[i]),
               "admet_DILI":    float(df["DILI"].iloc[i]),
               "admet_hERG":    float(df["hERG"].iloc[i]),
               "admet_AMES":    float(df["AMES"].iloc[i]),
               "admet_Carcinogens": float(df["Carcinogens_Lagunin"].iloc[i]),
               "admet_BBB_Martins": float(df["BBB_Martins"].iloc[i]),
               "mammal_BBBP":   mammal_scores["MAMMAL_BBBP"][i],
               "mammal_ClinTox":mammal_scores["MAMMAL_ClinTox"][i]}
        rows.append(row)

    # --- Binarise at 0.5 ---
    def binarise(name):
        return [1 if r[name] is not None and r[name] >= 0.5 else 0 for r in rows]

    metrics = {}
    for col in ("admet_ClinTox", "admet_DILI", "admet_hERG", "admet_AMES", "admet_Carcinogens", "mammal_ClinTox"):
        metrics[col] = confusion(y, binarise(col))

    # --- AUROC (rank-based) for each predictor vs toxic label ---
    def auroc_col(col):
        scores = [r[col] for r in rows]
        if any(s is None for s in scores):
            valid = [(s, t) for s, t in zip(scores, y) if s is not None]
            if not valid: return None
            s_, y_ = zip(*valid)
            return datafit.auroc([s_[i] for i in range(len(s_)) if y_[i]==1], [s_[i] for i in range(len(s_)) if y_[i]==0])
        return datafit.auroc([rows[i][col] for i in range(len(rows)) if y[i]==1],
                              [rows[i][col] for i in range(len(rows)) if y[i]==0])

    aurocs = {col: round(auroc_col(col), 3) if auroc_col(col) is not None else None
              for col in ("admet_ClinTox", "admet_DILI", "admet_hERG", "admet_AMES", "admet_Carcinogens", "mammal_ClinTox")}

    # --- BBBP head-to-head Spearman ---
    bbb_a = [r["admet_BBB_Martins"] for r in rows]
    bbb_m = [r["mammal_BBBP"] for r in rows if r["mammal_BBBP"] is not None]
    valid_idx = [i for i, v in enumerate([r["mammal_BBBP"] for r in rows]) if v is not None]
    rho_bbb = datafit.spearman([bbb_a[i] for i in valid_idx],
                                [rows[i]["mammal_BBBP"] for i in valid_idx])

    # --- Print summary ---
    print("\n" + "=" * 75)
    print(f"Per-compound predictions (panel = {sum(y)} toxic / {len(y)-sum(y)} safe)")
    print("=" * 75)
    print(f"{'name':18s} {'tox':>3s} {'aCT':>4s} {'aDLI':>4s} {'aHRG':>4s} {'aAME':>4s} {'mCT':>5s}")
    for r in rows:
        print(f"{r['name']:18s} {r['toxic']:>3d} "
              f"{r['admet_ClinTox']:>4.2f} {r['admet_DILI']:>4.2f} {r['admet_hERG']:>4.2f} "
              f"{r['admet_AMES']:>4.2f} "
              f"{(r['mammal_ClinTox'] if r['mammal_ClinTox'] is not None else float('nan')):>5.2f}")

    print("\n" + "=" * 75)
    print("AUROC (vs `toxic` label) — higher = better separator")
    print("=" * 75)
    for col, a in aurocs.items():
        print(f"  {col:20s} AUROC = {a}")

    print("\n" + "=" * 75)
    print("Binary TPR/TNR at threshold 0.5")
    print("=" * 75)
    for col, m in metrics.items():
        print(f"  {col:20s}  TPR={m['TPR']:.2f}  TNR={m['TNR']:.2f}  acc={m['accuracy']:.2f}  ({m['TP']}TP/{m['FP']}FP/{m['FN']}FN/{m['TN']}TN)")

    print("\n" + "=" * 75)
    print(f"BBBP head-to-head: Spearman(admet BBB_Martins, MAMMAL BBBP) = {rho_bbb:+.3f}  (n={len(valid_idx)})")

    out = {"timestamp": ts, "panel_n": len(rows), "panel_n_toxic": sum(y), "panel_n_safe": len(y) - sum(y),
           "per_compound": rows, "binary_metrics": metrics, "aurocs": aurocs,
           "bbb_spearman_admet_vs_mammal": round(rho_bbb, 3),
           "bbb_n_valid": len(valid_idx)}
    out_path = REPO / "results" / f"compare_admet_ai_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
