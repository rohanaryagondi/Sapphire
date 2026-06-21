"""Phase 4 — calibration + per-direction for the remaining heads: TCR-epitope and solubility.

Completes the cross-head audit. For each: balanced real sample, report AUROC + saturation
(hard 0/1 fraction) + TPR/TNR at 0.5. TCR = TDC Weber test split; solubility = DeepSol test.
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase4_tcr_solubility_calib.py
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


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t == 1]; neg = [x for x, t in zip(s, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def metrics(y, s, tag):
    roc = auroc(y, s)
    sat = sum(1 for x in s if x < 0.01 or x > 0.99) / len(s)
    npos = sum(y); nneg = len(y) - npos
    tpr = sum(1 for a, t in zip(s, y) if t == 1 and a >= 0.5) / npos if npos else float("nan")
    tnr = sum(1 for a, t in zip(s, y) if t == 0 and a < 0.5) / nneg if nneg else float("nan")
    print(f"[{tag}] n={len(y)} posRate={npos/len(y):.2f} AUROC={roc:.3f} sat={sat*100:.0f}% TPR={tpr:.2f} TNR={tnr:.2f}")
    return {"n": len(y), "pos_rate": round(npos/len(y), 3), "auroc": round(roc, 4),
            "saturation_frac": round(sat, 3), "TPR_at_0.5": round(tpr, 3), "TNR_at_0.5": round(tnr, 3)}


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {"timestamp": ts}

    # ---- TCR-epitope (TDC Weber test) ----
    try:
        from tdc.multi_pred import TCREpitopeBinding
        from mammal.examples.tcr_epitope_binding.main_infer import load_model, task_infer
        test = TCREpitopeBinding(name="weber").get_split()["test"]
        tcr_col = "tcr_full" if "tcr_full" in test.columns else "tcr"
        epi_col = "epitope_aa" if "epitope_aa" in test.columns else next(c for c in test.columns if "epitope" in c.lower())
        lab_col = "label" if "label" in test.columns else "Y"
        df = test.dropna(subset=[tcr_col, epi_col, lab_col])
        pos = df[df[lab_col] == 1]; neg = df[df[lab_col] == 0]
        k = min(100, len(pos), len(neg))
        samp = list(pos.head(k).itertuples()) + list(neg.head(k).itertuples())
        tcr_dir = str(REPO / "models" / "tcr_epitope_bind")
        model, tok = load_model(device="mps", model_path=tcr_dir, tokenizer_path=os.path.join(tcr_dir, "tokenizer"))
        y, s = [], []
        for r in samp:
            try:
                res = task_infer(model=model, tokenizer_op=tok,
                                 tcr_beta_seq=str(getattr(r, tcr_col)), epitope_seq=str(getattr(r, epi_col)))
                s.append(res["score"]); y.append(int(getattr(r, lab_col)))
            except Exception:
                pass
        out["TCR_epitope"] = metrics(y, s, "TCR-epitope")
        del model
    except Exception as e:
        print("TCR skipped:", e); out["TCR_epitope"] = {"error": str(e)}

    # ---- protein solubility (DeepSol test) ----
    try:
        from mammal_quiver  import wdr91  # noqa: ensures USE_TF set
    except Exception:
        pass
    try:
        from mammal.examples.protein_solubility.pl_data_module import load_datasets
        from mammal.examples.protein_solubility.task import ProteinSolubilityTask
        from mammal.examples.protein_solubility.main_infer import protein_solubility_infer  # noqa
        from mammal.model import Mammal
        from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
        from mammal.keys import CLS_PRED, SCORES
        import torch
        ds = load_datasets(str(REPO / "data" / "solubility"))["test"]
        sol = str(REPO / "models" / "protein_solubility")
        model = Mammal.from_pretrained(sol).to("mps").eval()
        tok = ModularTokenizerOp.from_pretrained(os.path.join(sol, "tokenizer"))

        @torch.no_grad()
        def predict(seq):
            sd = ProteinSolubilityTask.data_preprocessing(
                sample_dict={"protein_seq": seq}, protein_sequence_key="protein_seq",
                tokenizer_op=tok, device=model.device)
            bd = model.generate([sd], output_scores=True, return_dict_in_generate=True, max_new_tokens=5)
            a = ProteinSolubilityTask.process_model_output(
                tokenizer_op=tok, decoder_output=bd[CLS_PRED][0], decoder_output_scores=bd[SCORES][0])
            return None if a is None else float(a["normalized_scores"])

        idxs = list(range(len(ds)))[:: max(1, len(ds) // 200)][:200]
        y, s = [], []
        for i in idxs:
            try:
                v = predict(ds[i]["data.protein"])
                if v is not None:
                    s.append(v); y.append(int(ds[i]["data.label"]))
            except Exception:
                pass
        out["protein_solubility"] = metrics(y, s, "solubility")
        del model
    except Exception as e:
        print("solubility skipped:", e); out["protein_solubility"] = {"error": str(e)}

    (REPO / "results" / f"phase4_tcr_solubility_calib_{ts}.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote results/phase4_tcr_solubility_calib_{ts}.json")


if __name__ == "__main__":
    main()
