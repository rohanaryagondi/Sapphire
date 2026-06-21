"""TxGemma-9B-predict on Quiver's Track-4/5 panels — runs on a GPU instance.

*** NON-COMMERCIAL RESEARCH USE ONLY (TxGemma HAI-DEF license). Not shippable without a
commercial agreement with Google. ***

TxGemma-predict is an instruction-tuned Gemma-2-9B that answers TDC therapeutic questions
as (A)/(B) multiple choice. We score with the standard "(" trick: append " (" to the prompt
and read the next-token logits over {A, B} -> P(B) = P(positive). All 4 templates use the
convention (A)=negative, (B)=positive (verified). Gives a graded score (AUROC) + a hard call.

Tasks (templates + panels bundled in txgemma_panels.json):
  - BBB_Martins (Track 4) vs MolFormer-XL 0.889
  - hERG_Karim  (Track 5) vs the weak rule (bal-acc 0.65)
  - DILI        (Track 5) vs ADMET-AI 0.83
  - ClinTox     (Track 5) vs MAMMAL 0.08 / MolFormer-probe (in-dist 0.897, external 0.244)
Each TDC test split (in-distribution) + the external 30-drug withdrawn-vs-safe panel
(scored under DILI and ClinTox templates) for the generalization comparison.

Usage: HF_TOKEN=... python txgemma_eval.py txgemma_panels.json out_dir
"""
from __future__ import annotations
import os, json, sys, time
from datetime import datetime
import numpy as np

MODEL = "google/txgemma-9b-predict"


def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort"); ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # tie-correct
    uniq, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    avg = {}; start = 0
    for k, c in enumerate(cnt):
        avg[k] = (start + 1 + start + c) / 2; start += c
    rb = np.array([avg[i] for i in inv])
    return float((rb[y == 1].sum() - p * (p + 1) / 2) / (p * n))


def metrics(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    tp = int(((pred==1)&(y==1)).sum()); tn=int(((pred==0)&(y==0)).sum())
    fp = int(((pred==1)&(y==0)).sum()); fn=int(((pred==0)&(y==1)).sum())
    tpr = tp/(tp+fn) if (tp+fn) else float("nan")
    tnr = tn/(tn+fp) if (tn+fp) else float("nan")
    return {"TPR": tpr, "TNR": tnr, "acc": (tp+tn)/len(y), "n": len(y), "pos": int((y==1).sum())}


def main():
    t0 = datetime.now()
    panels = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "txgemma_panels.json"))
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    templates = panels["templates"]

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, token=os.environ["HF_TOKEN"])
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, token=os.environ["HF_TOKEN"], torch_dtype=torch.bfloat16, device_map="auto"
    ).eval()
    DEV = next(model.parameters()).device
    print(f"loaded {MODEL} on {DEV}", flush=True)

    # token ids for the option letters (after "(")
    A_id = tok.encode("A", add_special_tokens=False)[-1]
    B_id = tok.encode("B", add_special_tokens=False)[-1]
    print(f"A_id={A_id} B_id={B_id}", flush=True)

    @torch.no_grad()
    def p_positive(smiles_list, template):
        scores = []
        for smi in smiles_list:
            prompt = template.replace("{Drug SMILES}", smi) + " ("
            ids = tok(prompt, return_tensors="pt").to(DEV)
            logits = model(**ids).logits[0, -1, :]
            la, lb = logits[A_id].float().item(), logits[B_id].float().item()
            m = max(la, lb)
            pb = np.exp(lb - m) / (np.exp(la - m) + np.exp(lb - m))
            scores.append(float(pb))
        return np.array(scores)

    results = {"test": "txgemma_9b_predict", "timestamp": t0.isoformat(), "model": MODEL,
               "LICENSE": "NON-COMMERCIAL RESEARCH ONLY (TxGemma HAI-DEF). Not shippable.",
               "scoring": "P(B) via '(' trick on next-token logits; (B)=positive for all 4 templates",
               "in_distribution": {}, "external_30drug": {},
               "baselines": {"BBB_Martins_MolFormer": 0.889, "DILI_ADMET_AI_TPR": 0.83,
                             "ClinTox_MAMMAL_TPR": 0.08, "hERG_rule_balacc": 0.65}}

    # in-distribution TDC test splits
    for task, rows in panels["tdc_test"].items():
        if task not in templates:
            continue
        smis = [r["smiles"] for r in rows]; y = [r["y"] for r in rows]
        s = p_positive(smis, templates[task])
        au = auroc(y, s)
        pred = (s >= 0.5).astype(int)
        results["in_distribution"][task] = {"auroc": au, **metrics(y, pred)}
        print(f"  [in-dist] {task}: AUROC {au:.3f}  TPR {results['in_distribution'][task]['TPR']:.2f} "
              f"TNR {results['in_distribution'][task]['TNR']:.2f}  (n={len(y)})", flush=True)
        with open(os.path.join(out_dir, "txgemma_results.json"), "w") as f:
            json.dump(results, f, indent=2)

    # external 30-drug withdrawn-vs-safe panel under DILI + ClinTox templates
    ext = panels["external_tox_30"]
    esmi = [r["smiles"] for r in ext]; ey = [r["toxic"] for r in ext]
    for task in ["DILI", "ClinTox"]:
        if task not in templates:
            continue
        s = p_positive(esmi, templates[task])
        au = auroc(ey, s)
        pred = (s >= 0.5).astype(int)
        results["external_30drug"][task] = {"auroc": au, **metrics(ey, pred)}
        print(f"  [external] {task}: AUROC {au:.3f}  TPR {results['external_30drug'][task]['TPR']:.2f} "
              f"TNR {results['external_30drug'][task]['TNR']:.2f}", flush=True)
        with open(os.path.join(out_dir, "txgemma_results.json"), "w") as f:
            json.dump(results, f, indent=2)

    print(f"\nDONE in {(datetime.now()-t0).total_seconds():.0f}s", flush=True)


if __name__ == "__main__":
    main()
