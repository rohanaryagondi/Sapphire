"""Phase 2b — MAMMAL on real Quiver targets named in the 5/28 meeting.

Uses the CORRECT PEER DTI checkpoint + the validated de-risking heads to probe:
  1. Nav1.8 (SCN10A)  — rank known Na-channel blockers vs decoys.
  2. TSC -> mTOR (MTOR) — rank mTOR inhibitors vs decoys (the TSC rescue use case).
  3. Truncation workaround — re-run with the binding-domain window instead of the
     full (1250-truncated) sequence, to test whether truncation is the cause.
  4. De-risking — BBBP penetrance + ClinTox toxicity on the CNS-relevant drugs.

Finding (see results/phase2b_quiver_targets.md): DTI gives NO single-target
binder-vs-decoy separation on these targets (Nav1.8 +0.00, mTOR +0.10), and the
binding-domain window does NOT rescue it (mTOR window -0.05/-0.08) — so it's the
model's intrinsic DTI resolution, not just truncation. BBBP is useful; ClinTox
over-predicts toxicity off-the-shelf.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/phase2b_quiver_targets.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import functools
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mammal_quiver.dti import load_dti_model, predict_pkd  # noqa: E402
from mammal_quiver.sequences import fetch_uniprot_sequence  # noqa: E402

PEER_SOURCE = str(REPO / "models" / "dti_bindingdb_pkd_peer")
PEER_M, PEER_S = 6.286291085593906, 1.5422950906208512
BBBP_SRC = str(REPO / "models" / "moleculenet_bbbp")
CTOX_SRC = str(REPO / "models" / "moleculenet_clintox_tox")

NAV_BLOCKERS = ["suzetrigine", "A-803467", "lidocaine", "mexiletine", "ranolazine", "carbamazepine", "lacosamide"]
MTOR_INHIB = ["sirolimus", "everolimus", "temsirolimus", "dactolisib", "sapanisertib", "AZD8055"]
DECOYS = ["metformin", "caffeine", "ibuprofen", "atenolol"]


@functools.lru_cache(maxsize=256)
def smiles(name):
    u = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
         f"{urllib.parse.quote(name)}/property/IsomericSMILES,CanonicalSMILES/JSON")
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return p.get("IsomericSMILES") or p.get("CanonicalSMILES") or p.get("SMILES")
    except Exception:
        return None


def separation(model, tok, seq, pos_names, neg_names):
    ps = [predict_pkd(model, tok, seq, smiles(n), PEER_M, PEER_S) for n in pos_names if smiles(n)]
    ns = [predict_pkd(model, tok, seq, smiles(n), PEER_M, PEER_S) for n in neg_names if smiles(n)]
    mp, mn = sum(ps) / len(ps), sum(ns) / len(ns)
    return {"mean_pos": round(mp, 3), "mean_decoy": round(mn, 3), "separation": round(mp - mn, 3),
            "pos": [round(x, 3) for x in ps], "decoy": [round(x, 3) for x in ns]}


def derisk(names):
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer
    out = {}
    for label, src, task in (("BBBP", BBBP_SRC, "BBBP"), ("CT_TOX", CTOX_SRC, "TOXICITY")):
        m = Mammal.from_pretrained(src).to("mps").eval()
        t = ModularTokenizerOp.from_pretrained(f"{src}/tokenizer")
        td = {"task_name": task, "model": m, "tokenizer_op": t}
        for n in names:
            s = smiles(n)
            if s:
                try:
                    out.setdefault(n, {})[label] = round(molnet_infer.task_infer(task_dict=td, smiles_seq=s)["score"], 3)
                except Exception:
                    out.setdefault(n, {})[label] = "err"
        del m
    return out


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model, tok, dev = load_dti_model(source=PEER_SOURCE)
    print(f"PEER DTI on {dev}")

    nav = fetch_uniprot_sequence("Q9Y5Y9")    # Nav1.8, 1956 aa
    mtor = fetch_uniprot_sequence("P42345")   # mTOR, 2549 aa; FRB ~2025-2114, kinase ~2182-2516

    res = {"timestamp": ts, "checkpoint": "dti_bindingdb_pkd_peer", "device": dev, "dti": {}}
    res["dti"]["nav1.8_full"] = separation(model, tok, nav, NAV_BLOCKERS, DECOYS)
    res["dti"]["nav1.8_window_1000_1956"] = separation(model, tok, nav[999:1956], NAV_BLOCKERS, DECOYS)
    res["dti"]["mtor_full"] = separation(model, tok, mtor, MTOR_INHIB, DECOYS)
    res["dti"]["mtor_FRB_kinase_1975_2549"] = separation(model, tok, mtor[1974:2549], MTOR_INHIB, DECOYS)
    res["dti"]["mtor_kinase_2100_2549"] = separation(model, tok, mtor[2099:2549], MTOR_INHIB, DECOYS)
    for k, v in res["dti"].items():
        print(f"  {k:34s} sep={v['separation']:+.2f}  (pos {v['mean_pos']} vs decoy {v['mean_decoy']})")
    del model

    res["derisk"] = derisk(NAV_BLOCKERS + MTOR_INHIB)
    print("\nDe-risking (P penetrant / P toxic):")
    for n in NAV_BLOCKERS + MTOR_INHIB:
        d = res["derisk"].get(n, {})
        print(f"  {n:16s} BBB+={d.get('BBBP','-')}  toxic={d.get('CT_TOX','-')}")

    out = REPO / "results" / f"phase2b_quiver_targets_{ts}.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
