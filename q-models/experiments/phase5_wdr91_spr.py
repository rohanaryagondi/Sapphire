"""
Phase 5 — WDR91 head on Ahmad 2023 SPR real data.

The ChEMBL actives test used 27 known binders + synthetic drug-like decoys.
This test uses the Ahmad 2023 J Med Chem SI (240 compounds, real SPR measurements):
  - KD_microM == 0  → confirmed non-binder (202 compounds)
  - KD_microM  > 0  → measured binder (38 compounds, KD 4–270 µM)
  - KD_microM == '>10' or '>217' → censored/weak binder (treated as binder, excluded from graded)

Key questions:
  1. Can the WDR91 head separate real SPR binders from real SPR non-binders?
     (vs. the decoy test, which used synthetic diversity-filtered non-binders)
  2. Among the binders, does P(active) correlate with KD (potency ranking)?
"""
import os, sys, json
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPR_CSV = os.path.join(REPO, "data", "wdr91", "ahmad2023_si_002.csv")
OUT = os.path.join(REPO, "results", f"phase5_wdr91_spr_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")


def neutral_parent(smi: str) -> str | None:
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    lfc = rdMolStandardize.LargestFragmentChooser()
    mol = lfc.choose(mol)
    uc = rdMolStandardize.Uncharger()
    mol = uc.uncharge(mol)
    return Chem.MolToSmiles(mol)


def load_spr_data():
    df = pd.read_csv(SPR_CSV)
    rows = []
    for _, r in df.iterrows():
        smi_raw = str(r["SMILES"]).strip()
        kd_raw = str(r["KD_microM"]).strip()
        if not smi_raw or smi_raw in ("nan", ""):
            continue
        smi = neutral_parent(smi_raw)
        if smi is None:
            continue
        # parse KD
        if kd_raw == "0":
            is_binder = False
            kd_num = None
        elif kd_raw.startswith(">"):
            is_binder = True
            kd_num = None  # censored — binder but excluded from graded ranking
        else:
            try:
                kd_num = float(kd_raw)
                is_binder = kd_num > 0
            except ValueError:
                continue
        rows.append({"smiles": smi, "smiles_raw": smi_raw, "kd_raw": kd_raw,
                     "is_binder": is_binder, "kd_num": kd_num})
    df2 = pd.DataFrame(rows).drop_duplicates(subset=["smiles"])
    print(f"Loaded {len(df2)} unique SMILES: {df2['is_binder'].sum()} binders, "
          f"{(~df2['is_binder']).sum()} non-binders")
    return df2


def main():
    from mammal_quiver.wdr91 import load_target_model, binder_prob

    df = load_spr_data()
    model, tok, task, device = load_target_model("wdr91")
    print(f"Model on {device}")

    scores = []
    for i, row in df.iterrows():
        p = binder_prob(model, tok, row["smiles"], task=task)
        scores.append(p)
        if (len(scores) % 20) == 0:
            print(f"  {len(scores)}/{len(df)}  last={p:.3f}  smi={row['smiles'][:40]}")

    df["score"] = scores

    # --- Classification AUROC: binders vs non-binders ---
    from sklearn.metrics import roc_auc_score, average_precision_score
    y = df["is_binder"].astype(int).values
    s = df["score"].values
    auroc = roc_auc_score(y, s)
    ap = average_precision_score(y, s)

    # enrichment factors
    n_total = len(df)
    n_pos = int(y.sum())
    sorted_idx = np.argsort(s)[::-1]
    y_sorted = y[sorted_idx]
    ef5 = (y_sorted[:max(1, n_total // 20)].mean()) / (n_pos / n_total)
    ef10 = (y_sorted[:max(1, n_total // 10)].mean()) / (n_pos / n_total)

    # --- Graded ranking among binders (KD available + not censored) ---
    binder_df = df[df["is_binder"] & df["kd_num"].notna()].copy()
    from scipy.stats import spearmanr
    if len(binder_df) >= 5:
        # Higher KD = weaker = should have lower score → expect negative correlation
        rho, pval = spearmanr(binder_df["score"], binder_df["kd_num"])
        # Invert: score vs 1/KD (tight binders should score high)
        rho_inv, pval_inv = spearmanr(binder_df["score"], 1.0 / binder_df["kd_num"])
    else:
        rho, pval, rho_inv, pval_inv = None, None, None, None

    print("\n=== WDR91 head — Ahmad 2023 SPR (real data) ===")
    print(f"  n_binders={n_pos}, n_nonbinders={n_total - n_pos}, n_total={n_total}")
    print(f"  Binary AUROC:       {auroc:.4f}")
    print(f"  Avg Precision:      {ap:.4f}")
    print(f"  Top-5%  EF:         {ef5:.2f}×")
    print(f"  Top-10% EF:         {ef10:.2f}×")
    print(f"  Graded n (KD known): {len(binder_df)}")
    if rho is not None:
        print(f"  Spearman(score, KD):     {rho:.4f}  p={pval:.3f}")
        print(f"  Spearman(score, 1/KD):   {rho_inv:.4f}  p={pval_inv:.3f}")

    # top scores
    top = df.nlargest(10, "score")[["smiles", "is_binder", "kd_raw", "score"]]
    print("\n  Top-10 highest-scoring compounds:")
    print(top.to_string(index=False))

    # scores by class
    print(f"\n  Mean score | binders:     {df[df['is_binder']]['score'].mean():.4f}")
    print(f"  Mean score | non-binders: {df[~df['is_binder']]['score'].mean():.4f}")

    result = {
        "test": "wdr91_spr_real_data",
        "n_binders": int(n_pos),
        "n_nonbinders": int(n_total - n_pos),
        "n_total": int(n_total),
        "auroc": float(auroc),
        "avg_precision": float(ap),
        "ef5": float(ef5),
        "ef10": float(ef10),
        "graded_n": int(len(binder_df)),
        "spearman_score_kd": float(rho) if rho is not None else None,
        "spearman_score_inv_kd": float(rho_inv) if rho_inv is not None else None,
        "mean_score_binders": float(df[df["is_binder"]]["score"].mean()),
        "mean_score_nonbinders": float(df[~df["is_binder"]]["score"].mean()),
        "per_compound": df[["smiles_raw", "kd_raw", "is_binder", "score"]].to_dict(orient="records"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
