#!/usr/bin/env python3
"""TxGemma-9B-predict far-OOD head-to-head vs MapLight — the fair shot.

Scores TxGemma on the IDENTICAL far/mid/near Tanimoto bands MapLight was scored on (BBB B3DB,
hERG scaffold split), so the comparison is apples-to-apples on novel chemotypes — the band where
de-risking models must hold and where LMs historically collapse (Phase-2 LMs 0.56-0.61).

*** NON-CLINICAL R&D USE (TxGemma HAI-DEF terms permit non-clinical drug-discovery R&D; clinical/
medical-device use is barred). ***

Scoring = the validated "(" trick: prompt + " (", read next-token logits over {A,B} -> P(B)=positive.
MapLight refs: BBB far<0.3 AUROC 0.674, hERG far<0.3 AUROC 0.809.

Usage: HF_TOKEN=... python txgemma_farood_eval.py txgemma_farood_panels.json out_dir
"""
import json, os, sys, time
from datetime import datetime, timezone
import numpy as np

MODEL = "google/txgemma-9b-predict"


def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    p = int((y == 1).sum()); n = int((y == 0).sum())
    if p == 0 or n == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    uniq, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    avg = {}; start = 0
    for k, c in enumerate(cnt):
        avg[k] = (start + 1 + start + c) / 2.0; start += c
    rb = np.array([avg[i] for i in inv])
    return float((rb[y == 1].sum() - p * (p + 1) / 2.0) / (p * n))


def main():
    panel = json.load(open(sys.argv[1]))
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(MODEL, token=os.environ.get("HF_TOKEN"))
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto", token=os.environ.get("HF_TOKEN"))
    model.eval()
    A_id = tok.encode("A", add_special_tokens=False)[-1]
    B_id = tok.encode("B", add_special_tokens=False)[-1]

    @torch.no_grad()
    def p_positive(smiles_list, template):
        out = []
        for i, smi in enumerate(smiles_list):
            prompt = template.replace("{Drug SMILES}", smi) + " ("
            ids = tok(prompt, return_tensors="pt").to(model.device)
            logits = model(**ids).logits[0, -1, :]
            la, lb = logits[A_id].float().item(), logits[B_id].float().item()
            m = max(la, lb)
            out.append(float(np.exp(lb - m) / (np.exp(la - m) + np.exp(lb - m))))
            if (i + 1) % 500 == 0:
                print(f"    scored {i+1}/{len(smiles_list)}", flush=True)
        return out

    tmpl = {"BBB": panel["templates"]["BBB_Martins"], "hERG": panel["templates"]["hERG_Karim"]}
    res = {"test": "txgemma_9b_farood_vs_maplight", "model": MODEL,
           "timestamp": datetime.now(timezone.utc).isoformat(),
           "license": "HAI-DEF: non-clinical R&D permitted; clinical/device use barred",
           "refs_maplight": panel.get("refs", {}), "bands": {}}
    for endp in ("BBB", "hERG"):
        res["bands"][endp] = {}
        for band in ("far", "mid", "near"):
            items = panel["farood"][endp][band]
            if not items:
                continue
            t0 = time.time()
            y = [it["y"] for it in items]
            s = p_positive([it["smiles"] for it in items], tmpl[endp])
            res["bands"][endp][band] = {"n": len(items), "pos": int(sum(y)),
                                        "auroc": round(auroc(y, s), 4), "sec": round(time.time() - t0, 1)}
            print(f"  {endp} {band}: n={len(items)} AUROC={res['bands'][endp][band]['auroc']}", flush=True)
            json.dump(res, open(os.path.join(outdir, "txgemma_farood_results.json"), "w"), indent=2)
    # head-to-head verdict
    bf = res["bands"]["BBB"].get("far", {}).get("auroc")
    hf = res["bands"]["hERG"].get("far", {}).get("auroc")
    res["headtohead"] = {
        "BBB_far": {"txgemma": bf, "maplight": 0.674, "txgemma_wins": (bf or 0) > 0.674},
        "hERG_far": {"txgemma": hf, "maplight": 0.809, "txgemma_wins": (hf or 0) > 0.809}}
    json.dump(res, open(os.path.join(outdir, "txgemma_farood_results.json"), "w"), indent=2)
    print("HEAD-TO-HEAD:", json.dumps(res["headtohead"]), flush=True)


if __name__ == "__main__":
    main()
