"""BALM deep operating-envelope characterization (overnight Phase 1).

BALM (ESM-2-150M + ChemBERTa-77M two-tower, cosine=pKd) won the compound<->target shared-embedding
question on n=11/7 (Nav1.8 0.857, mTOR 1.000). This makes it Boltz-level: where does the shared
cosine space work, where does it fail, and WHY. Every analysis is independently guarded so a single
failure (e.g. ChEMBL API hiccup) still yields the rest — important for an unattended run.

Analyses:
  A. Per-target binder/decoy cosine-AUROC + separation on the Quiver panels (Nav1.8, mTOR).
  B. Cross-paralog SELECTIVITY (the Boltz test): score each Nav1.8 binder vs Nav1.8/1.7/1.5/1.1 --
     does Nav1.8 rank highest? Resolution at the paralog level is the hard test.
  C. Multi-family generalization: ChEMBL actives/inactives for DRD2, ADRB2, EGFR, BRAF, MTOR
     (fetched on-instance) -> per-target & per-family AUROC + calibration (pKd vs pChEMBL).
  D. Applicability-domain / leakage: Morgan-Tanimoto of each compound to the rest of the compound
     pool; AUROC stratified by novelty -> is 0.857 real generalization or famous-drug memorization?
  E. Truncation probe: Nav1.8 (1956 aa, ESM-2 1024 cap) full-N-terminal vs a pore-domain window.
"""
from __future__ import annotations
import json, os, sys, urllib.request, traceback
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/balm_out/balm_characterization_result.json"))
BALM_DIR = Path(os.environ.get("BALM_DIR", "/opt/BALM"))
CKPT = os.environ.get("BALM_CKPT", "BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse")
CONFIG = os.environ.get("BALM_CONFIG", str(BALM_DIR / "default_configs" / "balm_peft.yaml"))

NAV_PARALOGS = {"Nav1.8/SCN10A": "Q9Y5Y9", "Nav1.7/SCN9A": "Q15858",
                "Nav1.5/SCN5A": "Q14524", "Nav1.1/SCN1A": "P35498"}
CHEMBL_TARGETS = {  # gene -> (chembl target id, uniprot, family)
    "DRD2": ("CHEMBL217", "P14416", "gpcr"), "ADRB2": ("CHEMBL210", "P07550", "gpcr"),
    "EGFR": ("CHEMBL203", "P00533", "kinase"), "BRAF": ("CHEMBL5145", "P15056", "kinase"),
    "MTOR": ("CHEMBL2842", "P42345", "kinase_lipid"),
}
MAX_PER_CLASS = 40  # cap actives/inactives per ChEMBL target (BALM runtime + API politeness)


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(roc_auc_score(labels, scores))


def fetch_uniprot(acc):
    fa = urllib.request.urlopen(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta", timeout=60).read().decode()
    return "".join(fa.splitlines()[1:])


# ---------------- BALM loader ----------------
class Balm:
    def __init__(self):
        import torch
        sys.path.insert(0, str(BALM_DIR))
        from balm import common_utils
        from balm.configs import Configs
        from balm.models import BALM
        from balm.models.utils import load_trained_model, load_pretrained_pkd_bounds
        from transformers import AutoTokenizer
        cfg = Configs(**common_utils.load_yaml(CONFIG))
        try: cfg.model_configs.checkpoint_path = CKPT
        except Exception: pass
        m = BALM(cfg.model_configs); m = load_trained_model(m, cfg.model_configs, is_training=False)
        m.to(DEVICE).eval()
        self.m, self.torch = m, torch
        self.lo, self.hi = load_pretrained_pkd_bounds(cfg.model_configs.checkpoint_path)
        self.pt = AutoTokenizer.from_pretrained(cfg.model_configs.protein_model_name_or_path)
        self.dt = AutoTokenizer.from_pretrained(cfg.model_configs.drug_model_name_or_path)
        self.pmax = 1024

    def score(self, seq, smi):
        import torch
        p = self.pt(seq.strip().replace(" ", ""), return_tensors="pt", truncation=True, max_length=self.pmax).to(DEVICE)
        d = self.dt(smi, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            o = self.m({"protein_input_ids": p["input_ids"], "protein_attention_mask": p["attention_mask"],
                        "drug_input_ids": d["input_ids"], "drug_attention_mask": d["attention_mask"]})
        cos = float(o["cosine_similarity"].reshape(-1)[0])
        pkd = float(self.m.cosine_similarity_to_pkd(o["cosine_similarity"], pkd_upper_bound=self.hi, pkd_lower_bound=self.lo).reshape(-1)[0])
        return cos, pkd


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:800]}", flush=True)


def main():
    balm = Balm()
    panels = json.loads(PANELS.read_text())
    R = {}

    # A. per-target on Quiver panels
    def quiver():
        out = {}
        for key, p in panels.items():
            rows = [{"drug": c["drug"], "label": c["label"], "smiles": c["smiles"],
                     "cos": balm.score(p["protein_seq"], c["smiles"])[0]} for c in p["compounds"]]
            lab = [r["label"] for r in rows]; cs = [r["cos"] for r in rows]
            b = [r["cos"] for r in rows if r["label"] == 1]; d = [r["cos"] for r in rows if r["label"] == 0]
            out[key] = {"target": p["target"], "n": len(rows), "auroc": auroc(lab, cs),
                        "sep": round(np.mean(b) - np.mean(d), 4) if b and d else None,
                        "rows": rows}
        return out
    section(quiver, "A_quiver_panels", R)

    # B. cross-paralog selectivity (Nav1.8 binders vs all Nav paralogs)
    def selectivity():
        nav = panels.get("nav18", {})
        binders = [c for c in nav.get("compounds", []) if c["label"] == 1]
        seqs = {k: fetch_uniprot(a) for k, a in NAV_PARALOGS.items()}
        rows = []
        for c in binders:
            cosines = {k: balm.score(seqs[k], c["smiles"])[0] for k in seqs}
            top = max(cosines, key=cosines.get)
            rows.append({"drug": c["drug"], "cosines": {k: round(v, 4) for k, v in cosines.items()},
                         "argmax": top, "nav18_is_top": top.startswith("Nav1.8")})
        return {"n_binders": len(rows), "frac_nav18_top": round(np.mean([r["nav18_is_top"] for r in rows]), 3) if rows else None,
                "rows": rows, "note": "can BALM cosine resolve the correct paralog? (Boltz selectivity test)"}
    section(selectivity, "B_paralog_selectivity", R)

    # C. multi-family ChEMBL panels + calibration
    def chembl():
        out = {}
        for gene, (cid, acc, fam) in CHEMBL_TARGETS.items():
            try:
                url = (f"https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id={cid}"
                       f"&pchembl_value__isnull=false&standard_type__in=IC50,Ki,Kd&limit=1000")
                acts = json.loads(urllib.request.urlopen(url, timeout=90).read())["activities"]
                seen = {}
                for a in acts:
                    smi = a.get("canonical_smiles"); pv = a.get("pchembl_value")
                    if smi and pv and smi not in seen:
                        seen[smi] = float(pv)
                actives = [(s, v) for s, v in seen.items() if v >= 6.5][:MAX_PER_CLASS]
                decoys = [(s, v) for s, v in seen.items() if v <= 5.0][:MAX_PER_CLASS]
                if len(actives) < 5 or len(decoys) < 5:
                    out[gene] = {"family": fam, "skip": f"insufficient ({len(actives)}a/{len(decoys)}d)"}; continue
                seq = fetch_uniprot(acc)
                rows = []
                for s, v in actives: rows.append((s, 1, v, balm.score(seq, s)))
                for s, v in decoys: rows.append((s, 0, v, balm.score(seq, s)))
                lab = [r[1] for r in rows]; cs = [r[3][0] for r in rows]
                pkd = [r[3][1] for r in rows]; pv = [r[2] for r in rows]
                from scipy.stats import spearmanr
                sp = spearmanr(pkd, pv)[0]
                b = [c for c, l in zip(cs, lab) if l == 1]; d = [c for c, l in zip(cs, lab) if l == 0]
                out[gene] = {"family": fam, "n_act": len(actives), "n_dec": len(decoys),
                             "auroc": auroc(lab, cs), "sep": round(np.mean(b) - np.mean(d), 4),
                             "calib_spearman_pkd_vs_pchembl": None if np.isnan(sp) else round(float(sp), 3)}
            except Exception as e:
                out[gene] = {"family": fam, "error": f"{type(e).__name__}: {e}"}
        # per-family aggregate
        fams = {}
        for g, r in out.items():
            if r.get("auroc") is not None:
                fams.setdefault(r["family"], []).append(r["auroc"])
        out["_by_family"] = {f: round(float(np.mean(v)), 3) for f, v in fams.items()}
        return out
    section(chembl, "C_chembl_multifamily", R)

    # D. applicability domain / leakage on the Quiver panels
    def ad():
        from rdkit import Chem, DataStructs
        from rdkit.Chem import AllChem
        all_rows = []
        for key, p in panels.items():
            for c in p["compounds"]:
                all_rows.append({"key": key, "smiles": c["smiles"], "label": c["label"],
                                 "cos": balm.score(p["protein_seq"], c["smiles"])[0]})
        fps = []
        for r in all_rows:
            m = Chem.MolFromSmiles(r["smiles"]); fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None)
        for i, r in enumerate(all_rows):
            sims = [DataStructs.TanimotoSimilarity(fps[i], fps[j]) for j in range(len(fps)) if j != i and fps[i] and fps[j]]
            r["max_tanimoto_to_others"] = round(max(sims), 3) if sims else None
        # stratify AUROC by novelty (max-Tanimoto < 0.3 = novel vs >= 0.3 = similar)
        strata = {}
        for cut, name in [(0.3, "novel(<0.3)"), (1.1, "all")]:
            sub = [r for r in all_rows if (r["max_tanimoto_to_others"] or 0) < cut]
            strata[name] = {"n": len(sub), "auroc": auroc([r["label"] for r in sub], [r["cos"] for r in sub])}
        return {"strata": strata, "note": "if AUROC holds on low-Tanimoto (novel) compounds, the signal is generalization not memorization"}
    section(ad, "D_applicability_domain", R)

    # E. truncation probe on Nav1.8
    def truncation():
        nav = panels.get("nav18")
        if not nav: return {"skip": "no nav18"}
        seq = nav["protein_seq"]; comps = nav["compounds"]
        full = [(c["label"], balm.score(seq, c["smiles"])[0]) for c in comps]          # N-terminal 1024
        # pore/DIV window: residues ~900-1924 (the C-terminal half incl. DIII-DIV pore the blockers hit)
        win = seq[900:1924]
        wro = [(c["label"], balm.score(win, c["smiles"])[0]) for c in comps]
        return {"auroc_full_Nterm1024": auroc([x[0] for x in full], [x[1] for x in full]),
                "auroc_pore_window_900_1924": auroc([x[0] for x in wro], [x[1] for x in wro]),
                "note": "does feeding the pore/DIV window (vs default N-terminal truncation) change Nav1.8 discrimination?"}
    section(truncation, "E_truncation_probe", R)

    payload = {"model": "BALM (ESM-2-150M + ChemBERTa-77M, cosine=pKd)", "checkpoint": CKPT,
               "phase": "1 - BALM deep characterization",
               "baselines": {"balm_nav18_n11": 0.857, "balm_mtor_n7": 1.000, "boltz2_nav18": 0.714, "conplex_nav": 0.437},
               "results": R}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps({k: (v.get("auroc") if isinstance(v, dict) else None) for k, v in R.items()}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
