"""Phase 4 — ClinTox-toxicity head: in-distribution vs OUT-of-distribution behavior.

The molnet audit showed ClinTox-tox is ~perfect on its OWN held-out fold (AUROC 1.0, 0% false
alarm on in-distribution non-toxic compounds). But an earlier Quiver test found it over-predicts
toxicity on approved CNS drugs. Reconciliation hypothesis (same as BBBP): great in-distribution,
fails out-of-distribution. This tests it directly with EXTERNAL drugs whose tox status is
clinically unambiguous, mirroring the BBBP literature test.

  SAFE (should score P(toxic) low): widely-used, long-marketed, well-tolerated drugs.
  TOXIC (should score high): drugs withdrawn / black-boxed / failed for toxicity.

Clean neutral-parent SMILES from PubChem; ClinTox membership flagged by InChIKey (so we separate
in-set from genuinely external). Readout = molnet P(<1>)=P(toxic).
Run: /opt/anaconda3/envs/mammal/bin/python experiments/phase4_clintox_literature.py
"""

from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import csv
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rdkit import Chem

# name -> (clinical tox label: 1=toxic/withdrawn-blackbox, 0=safe/well-tolerated)
COMPOUNDS = [
    # SAFE — long-marketed, well tolerated
    ("aspirin", 0), ("ibuprofen", 0), ("acetaminophen", 0), ("metformin", 0),
    ("amoxicillin", 0), ("omeprazole", 0), ("atorvastatin", 0), ("lisinopril", 0),
    ("amlodipine", 0), ("loratadine", 0), ("cetirizine", 0), ("caffeine", 0),
    ("sertraline", 0), ("levothyroxine", 0), ("metoprolol", 0),
    # TOXIC — withdrawn / black-box / failed for toxicity
    ("thalidomide", 1), ("cerivastatin", 1), ("troglitazone", 1), ("terfenadine", 1),
    ("cisapride", 1), ("rofecoxib", 1), ("fenfluramine", 1), ("astemizole", 1),
    ("pemoline", 1), ("bromfenac", 1), ("valdecoxib", 1), ("sibutramine", 1),
    ("phenformin", 1), ("benoxaprofen", 1), ("ximelagatran", 1),
]


def neutral_parent(smi):
    m = Chem.MolFromSmiles(smi)
    if not m:
        return None
    m = max(Chem.GetMolFrags(m, asMols=True, sanitizeFrags=True), key=lambda x: x.GetNumAtoms())
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize
        m = rdMolStandardize.Uncharger().uncharge(m)
    except Exception:
        pass
    return Chem.MolToSmiles(m)


def fetch_smiles(name):
    for prop in ("CanonicalSMILES", "ConnectivitySMILES"):
        for attempt in range(3):
            try:
                url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                       f"{urllib.request.quote(name)}/property/{prop}/JSON")
                with urllib.request.urlopen(url, timeout=30) as r:
                    s = json.load(r)["PropertyTable"]["Properties"][0].get(prop)
                if s:
                    return neutral_parent(s)
            except Exception:
                time.sleep(1.0 + attempt)
    return None


def ikey(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToInchiKey(m) if m else None


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # ClinTox membership (neutral-parent InChIKey -> CT_TOX label)
    key2 = {}
    for r in csv.DictReader(open("/tmp/clintox.csv")):
        np_smi = neutral_parent(r["smiles"])
        k = ikey(np_smi) if np_smi else None
        if k:
            key2[k] = int(float(r["CT_TOX"]))

    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.molnet import molnet_infer
    head = str(REPO / "models" / "moleculenet_clintox_tox")
    model = Mammal.from_pretrained(head).to("mps").eval()
    tok = ModularTokenizerOp.from_pretrained(os.path.join(head, "tokenizer"))
    task = {"task_name": "TOXICITY", "model": model, "tokenizer_op": tok}

    rows = []
    for name, lab in COMPOUNDS:
        smi = fetch_smiles(name)
        if not smi:
            print(f"  !! no SMILES for {name}"); continue
        k = ikey(smi)
        p_tox = float(molnet_infer.task_infer(task_dict=task, smiles_seq=smi)["score"])
        rows.append({"name": name, "clinical_tox": lab, "in_clintox": k in key2,
                     "clintox_label": key2.get(k), "p_toxic": p_tox, "pred": int(p_tox >= 0.5),
                     "correct": int((p_tox >= 0.5) == lab)})

    safe = [r for r in rows if r["clinical_tox"] == 0]
    toxic = [r for r in rows if r["clinical_tox"] == 1]
    safe_ext = [r for r in safe if not r["in_clintox"]]
    tox_ext = [r for r in toxic if not r["in_clintox"]]

    def far(rs):  # false-alarm on safe = predicted toxic
        return sum(r["pred"] for r in rs) / len(rs) if rs else float("nan")

    def sens(rs):  # sensitivity on toxic = predicted toxic
        return sum(r["pred"] for r in rs) / len(rs) if rs else float("nan")

    summary = {
        "timestamp": ts,
        "n_safe": len(safe), "n_toxic": len(toxic),
        "n_safe_external": len(safe_ext), "n_toxic_external": len(tox_ext),
        "safe_falsealarm_rate_all": round(far(safe), 3),
        "safe_falsealarm_rate_EXTERNAL": round(far(safe_ext), 3),
        "toxic_sensitivity_all": round(sens(toxic), 3),
        "toxic_sensitivity_EXTERNAL": round(sens(tox_ext), 3),
        "rows": rows,
    }
    (REPO / "results" / f"phase4_clintox_literature_{ts}.json").write_text(json.dumps(summary, indent=2))

    print("\n========== ClinTox-tox vs literature (external known-safe / known-toxic) ==========")
    print(f"{'compound':16s} {'clin':>4s} {'inSet':>5s} {'ctLbl':>5s} {'P(toxic)':>8s} {'pred':>4s} {'ok':>3s}")
    for r in sorted(rows, key=lambda x: (x["clinical_tox"], -x["p_toxic"])):
        print(f"{r['name']:16s} {('TOX' if r['clinical_tox'] else 'safe'):>4s} "
              f"{str(r['in_clintox']):>5s} {str(r['clintox_label']):>5s} "
              f"{r['p_toxic']:8.3f} {('TOX' if r['pred'] else 'safe'):>4s} {('Y' if r['correct'] else 'N'):>3s}")
    print(f"\nSAFE drugs FALSE-ALARMED as toxic:  all {far(safe)*100:.0f}%  |  EXTERNAL-only {far(safe_ext)*100:.0f}% (n={len(safe_ext)})")
    print(f"TOXIC drugs caught (sensitivity):   all {sens(toxic)*100:.0f}%  |  EXTERNAL-only {sens(tox_ext)*100:.0f}% (n={len(tox_ext)})")
    print("\nInterpretation: high EXTERNAL false-alarm => over-predicts tox out-of-distribution.")
    print(f"wrote results/phase4_clintox_literature_{ts}.json")


if __name__ == "__main__":
    main()
