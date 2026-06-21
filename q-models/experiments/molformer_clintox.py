"""MolFormer-XL on ClinTox — Track 5. Does the BBBP winner also fix MAMMAL's broken
ClinTox (TPR 0.08, AUROC 0.28 on the external panel) and rival ADMET-AI DILI (TPR 0.83)?

MolFormer-XL has no public ClinTox head, so: embed with `ibm/MoLFormer-XL-both-10pct`
(ungated, ~47M, runs local CPU), train a logistic-regression probe on TDC ClinTox train,
then evaluate (a) in-distribution on TDC ClinTox test (AUROC) and (b) on the SAME 30-drug
external withdrawn-vs-safe panel used by phase5 + the ADMET-AI comparison — apples-to-apples
with MAMMAL ClinTox 0.08 and ADMET-AI DILI 0.83.

Run: /private/tmp/esmc-venv/bin/python experiments/molformer_clintox.py
Out: results/molformer_clintox.json
"""
from __future__ import annotations
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
import json
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "molformer_clintox.json"
MODEL = "ibm/MoLFormer-XL-both-10pct"

# external panel: 15 safe + 15 withdrawn/black-box toxic (identical to compare_admet_ai.py)
PANEL = [
    ("aspirin","CC(=O)Oc1ccccc1C(=O)O",0),("ibuprofen","CC(C)Cc1ccc(cc1)C(C)C(=O)O",0),
    ("metformin","CN(C)C(=N)NC(N)=N",0),
    ("atorvastatin","CC(C)c1n(CC(O)CC(O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2F)c1C(C)C",0),
    ("omeprazole","COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1",0),
    ("metoprolol","COCCc1ccc(OCC(O)CNC(C)C)cc1",0),
    ("amlodipine","CCOC(=O)C1=C(COCCN)NC(C)=C(C(=O)OC)C1c1ccccc1Cl",0),
    ("gabapentin","NCC1(CC(=O)O)CCCCC1",0),
    ("citalopram","CN(C)CCCC1(OCC#N)c2ccc(F)cc2-c2ccccc21",0),
    ("donepezil","COc1cc2c(cc1OC)CC(CC(=O)Cc1ccc(OC)c(OC)c1)N(C)CC2",0),
    ("memantine","CC12CC(C)(CC(C1)(CC2)N)C",0),("caffeine","CN1C=NC2=C1C(=O)N(C(=O)N2C)C",0),
    ("diphenhydramine","CN(C)CCOC(c1ccccc1)c1ccccc1",0),
    ("lidocaine","CCN(CC)CC(=O)Nc1c(C)cccc1C",0),
    ("fluoxetine","CNCCC(OC1=CC=C(C=C1)C(F)(F)F)c1ccccc1",0),
    ("cerivastatin","OC(CC(O)CC(=O)O)C=CC1=C(C(C)C)N(C)C(=C1C(=O)OCC)c1ccc(F)cc1",1),
    ("troglitazone","O=C1CSC(=O)N1Cc1ccc(OCC(C)(C)c2ccc(C)cc2-c2ccc(C)cc2O)cc1",1),
    ("terfenadine","OC(CCN1CCC(CC1)c1ccccc1)c1ccc(C(C)(C)C)cc1",1),
    ("thalidomide","O=C1CCC(=O)N1C1CC(=O)Nc2ccccc21",1),
    ("cisapride","COc1cc(NC(=O)c2cc(Cl)c(N)c(OC)c2)ccc1N1CCCCC1",1),
    ("bromfenac","NC1=C(CC(=O)c2ccc(Br)cc2)C(=O)c2ccccc21",1),
    ("mibefradil","COC(=O)N1CCN(C)CC1CC(=O)Oc1cccc2c1CCC1(CCCC1)c1ccccc1",1),
    ("trovafloxacin","OC(=O)c1cn2c(nc1=O)c(C1CC1)cc2N1CC(F)(F)C1",1),
    ("grepafloxacin","CC1COc2c(N3CCN(C)CC3)c(F)cc3c(=O)c(C(=O)O)cn1c23",1),
    ("alosetron","CN1C(=O)Nc2ccc3[nH]cnc3c21",1),
    ("valdecoxib","Cc1ccc(-c2cc(=O)no2)cc1-c1ccc(S(N)(=O)=O)cc1",1),
    ("ximelagatran","CCOC(=O)/N=C/c1ccc(CNC(=O)CN2CCC(N)CC2)cc1",1),
    ("pemoline","NC1=NC(=O)C(c2ccccc2)O1",1),
    ("rofecoxib","CS(=O)(=O)c1ccc(-c2ccoc2-c2ccccc2)cc1",1),
    ("tegaserod","CCCCCNC(=N)NN=Cc1c[nH]c2cc(OC)ccc12",1),
]


def embed_smiles(smis, tok, model, torch, bs=32):
    embs = []
    for i in range(0, len(smis), bs):
        batch = smis[i:i + bs]
        inp = tok(batch, padding=True, truncation=True, max_length=202, return_tensors="pt")
        with torch.no_grad():
            out = model(**inp)
        h = out.last_hidden_state            # [B, L, D]
        m = inp["attention_mask"].unsqueeze(-1).float()
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1)
        embs.append(pooled.cpu().numpy().astype(np.float64))
    return np.concatenate(embs, 0)


def metrics(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    tp = int(((pred==1)&(y==1)).sum()); tn=int(((pred==0)&(y==0)).sum())
    fp = int(((pred==1)&(y==0)).sum()); fn=int(((pred==0)&(y==1)).sum())
    tpr = tp/(tp+fn) if (tp+fn) else float("nan")
    tnr = tn/(tn+fp) if (tn+fp) else float("nan")
    return {"tp":tp,"tn":tn,"fp":fp,"fn":fn,"TPR":tpr,"TNR":tnr,"acc":(tp+tn)/len(y)}


def auroc(y, s):
    y=np.asarray(y); s=np.asarray(s,float)
    np_=int((y==1).sum()); nn=int((y==0).sum())
    if np_==0 or nn==0: return float("nan")
    order=np.argsort(s,kind="mergesort"); ranks=np.empty(len(s)); ranks[order]=np.arange(1,len(s)+1)
    return float((ranks[y==1].sum()-np_*(np_+1)/2)/(np_*nn))


def main():
    t0=datetime.now()
    import torch
    from transformers import AutoModel, AutoTokenizer
    from sklearn.linear_model import LogisticRegression

    print("loading MolFormer-XL ...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL, trust_remote_code=True, deterministic_eval=True).eval()

    print("loading ClinTox split (pre-dumped from TDC; esmc-venv lacks PyTDC) ...", flush=True)
    # fixture committed at results/clintox_split.json (dumped from TDC ClinTox in the mammal env)
    split_path = REPO / "results" / "clintox_split.json"
    split = json.load(open(split_path if split_path.is_file() else "/private/tmp/clintox_split.json"))
    tr, te = split["train"], split["test"]
    Xtr = embed_smiles([r["smiles"] for r in tr], tok, model, torch); ytr=np.array([r["y"] for r in tr])
    Xte = embed_smiles([r["smiles"] for r in te], tok, model, torch); yte=np.array([r["y"] for r in te])
    print(f"  train {len(ytr)} (pos {int(ytr.sum())}), test {len(yte)} (pos {int(yte.sum())})", flush=True)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Xtr, ytr)
    te_prob = clf.predict_proba(Xte)[:,1]
    test_auroc = auroc(yte, te_prob)
    test_m = metrics(yte, (te_prob>=0.5).astype(int))

    # external panel
    pnames=[p[0] for p in PANEL]; psmi=[p[1] for p in PANEL]; py=[p[2] for p in PANEL]
    Xp = embed_smiles(psmi, tok, model, torch)
    p_prob = clf.predict_proba(Xp)[:,1]
    panel_auroc = auroc(py, p_prob)
    panel_m = metrics(py, (p_prob>=0.5).astype(int))

    result={
        "test":"molformer_xl_clintox","timestamp":t0.isoformat(),"model":MODEL,
        "approach":"MolFormer-XL mean-pooled embeddings + balanced logistic-regression probe on TDC ClinTox train",
        "clintox_test":{"n":len(yte),"auroc":test_auroc,**test_m},
        "external_panel_30drug":{"n":len(py),"auroc":panel_auroc,**panel_m,
            "compare":{"MAMMAL_ClinTox_TPR":0.08,"MAMMAL_ClinTox_AUROC":0.28,"ADMET_AI_DILI_TPR":0.83}},
        "per_drug":[{"name":n,"toxic":t,"prob":float(pr)} for n,t,pr in zip(pnames,py,p_prob)],
    }
    OUT.write_text(json.dumps(result,indent=2))
    print("\n=== MolFormer-XL ClinTox ===",flush=True)
    print(f"  in-distribution ClinTox test: AUROC {test_auroc:.3f}",flush=True)
    print(f"  external 30-drug panel: AUROC {panel_auroc:.3f}  TPR {panel_m['TPR']:.3f}  TNR {panel_m['TNR']:.3f}",flush=True)
    print(f"  vs MAMMAL ClinTox TPR 0.08 / AUROC 0.28 ; ADMET-AI DILI TPR 0.83",flush=True)
    print(f"  Saved -> {OUT}  ({(datetime.now()-t0).total_seconds():.0f}s)",flush=True)


if __name__ == "__main__":
    main()
