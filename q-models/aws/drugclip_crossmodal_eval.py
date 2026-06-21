"""DrugCLIP cross-modal (pocket<->molecule shared-embedding) eval on Quiver panels.

DrugCLIP (NeurIPS 2023, MIT) is CLIP for virtual screening: it embeds a protein BINDING-SITE
POCKET (Uni-Mol 3D atom encoder) and a molecule (Uni-Mol 3D conformer encoder) into a shared
space and ranks by cosine. We test the SAME question as BALM — does the pocket<->molecule cosine
separate binders from decoys on Nav1.8 + mTOR — but structure-based (pocket) instead of
sequence-based.

Pipeline (literature-pocket mode, per the user's choice):
  1. AlphaFold PDB -> carve a pocket: all heavy atoms within RADIUS of the literature
     site-residue centroid (Nav1.8 DIV-S6 anesthetic pore; mTOR FRB rapalog site). Cap 256 atoms.
  2. panel SMILES -> RDKit 3D conformers (ETKDG, <=10).
  3. pack pocket.lmdb (1 pocket) + mols.lmdb (the panel) per target in Uni-Mol schema.
  4. run DrugCLIP retrieval.py -> emb_dir/ranked_compounds.txt (mol name \t pocket-cosine score).
  5. join scores to binder/decoy labels -> AUROC + binder/decoy separation, per target.

Heavy deps (installed by the userdata): unicore (Uni-Core), rdkit==2022.9.5, lmdb. Verbose logging
on purpose — unicore/LMDB-schema mismatches are the likely first-run failure mode.
"""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
POCKET_MANIFEST = Path(os.environ.get("POCKET_MANIFEST", "/opt/drugclip_pockets/pocket_manifest.json"))
POCKET_DIR = Path(os.environ.get("POCKET_DIR", "/opt/drugclip_pockets"))
DRUGCLIP_DIR = Path(os.environ.get("DRUGCLIP_DIR", "/opt/DrugCLIP"))
CKPT = os.environ.get("DRUGCLIP_CKPT", "/opt/drugclip_ckpt/checkpoint_best.pt")
WORK = Path(os.environ.get("WORK", "/root/drugclip_work"))
OUT = Path(os.environ.get("OUT", "/root/drugclip_out/drugclip_crossmodal_result.json"))
RADIUS = float(os.environ.get("POCKET_RADIUS", "12.0"))
MAX_POCKET_ATOMS = 256

_ELEM = {  # minimal atomic-number -> symbol for PDB element fallback
    "C": "C", "N": "N", "O": "O", "S": "S", "P": "P", "H": "H", "F": "F", "CL": "Cl", "BR": "Br",
}


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


def parse_pdb_atoms(pdb_text):
    """Return (heavy_atoms[list[(elem,(x,y,z))]], ca_by_res{resnum:(x,y,z)})."""
    heavy, ca = [], {}
    for ln in pdb_text.splitlines():
        if not ln.startswith("ATOM"):
            continue
        try:
            name = ln[12:16].strip()
            resnum = int(ln[22:26])
            x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
        except ValueError:
            continue
        elem = ln[76:78].strip() or name[0]
        elem = _ELEM.get(elem.upper(), elem.capitalize())
        if elem == "H":
            continue
        heavy.append((elem, (x, y, z)))
        if name == "CA":
            ca[resnum] = (x, y, z)
    return heavy, ca


def build_pocket(key, info):
    pdb = (POCKET_DIR / f"{key}.pdb").read_text()
    heavy, ca = parse_pdb_atoms(pdb)
    site = [r for r in info.get("site_residues_present", []) if r in ca]
    if not site:
        raise RuntimeError(f"{key}: no literature site residues found in AlphaFold numbering")
    cx = np.mean([ca[r] for r in site], axis=0)
    near = sorted(heavy, key=lambda a: np.linalg.norm(np.array(a[1]) - cx))
    near = [a for a in near if np.linalg.norm(np.array(a[1]) - cx) <= RADIUS][:MAX_POCKET_ATOMS]
    if len(near) < 8:
        near = heavy[:MAX_POCKET_ATOMS]  # fallback: shouldn't happen
    atoms = [a[0] for a in near]
    coords = np.array([a[1] for a in near], dtype=np.float32)
    print(f"  [{key}] pocket: {len(atoms)} atoms within {RADIUS}A of site centroid", flush=True)
    return {"pocket_atoms": atoms, "pocket_coordinates": coords}


def mol_entry(drug, smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise RuntimeError(f"bad SMILES for {drug}")
    m = Chem.AddHs(m)
    confs = AllChem.EmbedMultipleConfs(m, numConfs=10, params=AllChem.ETKDGv3())
    for c in confs:
        try:
            AllChem.MMFFOptimizeMolecule(m, confId=c)
        except Exception:
            pass
    m = Chem.RemoveHs(m)
    atoms = [a.GetSymbol() for a in m.GetAtoms()]
    coord_list = [m.GetConformer(c).GetPositions().astype(np.float32) for c in range(max(1, m.GetNumConformers()))]
    return {"atoms": atoms, "coordinates": coord_list, "mol": m, "smi": smiles, "drug": drug}


def write_lmdb(path, entries):
    import lmdb
    path.parent.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=1 << 30, subdir=False, lock=False)
    with env.begin(write=True) as txn:
        for i, e in enumerate(entries):
            txn.put(str(i).encode(), pickle.dumps(e))
    env.close()


def run_retrieval(pocket_lmdb, mols_lmdb, emb_dir):
    emb_dir.mkdir(parents=True, exist_ok=True)
    # NOTE: retrieval.py does NOT accept --dict-name (rc=2 'unrecognized arguments'); the atom
    # dictionaries are loaded from the repo's data/dict_mol.txt + data/dict_pkt.txt relative to
    # cwd (=DRUGCLIP_DIR), so we just omit it.
    # unicore requires a positional `data` dir (where it loads the atom dictionaries
    # dict_mol.txt + dict_pkt.txt); the repo ships them under DRUGCLIP_DIR/data. The actual
    # lmdbs are passed via --pocket-path/--mol-path.
    data_dir = str(DRUGCLIP_DIR / "data")
    cmd = [
        sys.executable, str(DRUGCLIP_DIR / "unimol" / "retrieval.py"), data_dir,
        "--path", CKPT, "--pocket-path", str(pocket_lmdb), "--mol-path", str(mols_lmdb),
        "--emb-dir", str(emb_dir), "--task", "drugclip", "--arch", "drugclip",
        "--batch-size", "8", "--max-pocket-atoms", str(MAX_POCKET_ATOMS),
        "--user-dir", str(DRUGCLIP_DIR / "unimol"),
    ]
    print("  [retrieval] " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DRUGCLIP_DIR), timeout=1200)
    print(r.stdout[-2000:], flush=True)
    if r.returncode != 0:
        print("  [retrieval STDERR]\n" + r.stderr[-2000:], flush=True)
    ranked = emb_dir / "ranked_compounds.txt"
    scores = {}
    if ranked.exists():
        for line in ranked.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    scores[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return scores, r.returncode


def main():
    panels = json.loads(PANELS.read_text())
    manifest = json.loads(POCKET_MANIFEST.read_text())
    results = {}
    for key, panel in panels.items():
        if key not in manifest:
            print(f"[skip] {key}: no pocket in manifest", flush=True); continue
        print(f"=== {panel['target']} ===", flush=True)
        pocket = build_pocket(key, manifest[key])
        write_lmdb(WORK / key / "pocket.lmdb", [pocket])
        mols = [mol_entry(c["drug"], c["smiles"]) for c in panel["compounds"]]
        write_lmdb(WORK / key / "mols.lmdb", mols)
        scores, rc = run_retrieval(WORK / key / "pocket.lmdb", WORK / key / "mols.lmdb", WORK / key / "emb")
        # map scores (keyed by smi or drug or index) back to labels
        rows = []
        for i, c in enumerate(panel["compounds"]):
            s = scores.get(c["smiles"], scores.get(c["drug"], scores.get(str(i)))) if scores else None
            rows.append({"drug": c["drug"], "label": c["label"], "score": s, "boltz": c.get("boltz_prob_binder")})
        scored = [r for r in rows if r["score"] is not None]
        ok = len(scored) == len(rows) and len(scored) > 0
        labels = [r["label"] for r in scored]; sc = [r["score"] for r in scored]
        bind = [r["score"] for r in scored if r["label"] == 1]
        decoy = [r["score"] for r in scored if r["label"] == 0]
        results[key] = {
            "target": panel["target"], "retrieval_rc": rc, "n_scored": len(scored), "n_total": len(rows),
            "all_mapped": ok,
            "auroc": auroc(labels, sc) if ok else None,
            "mean_binders": round(float(np.mean(bind)), 4) if bind else None,
            "mean_decoys": round(float(np.mean(decoy)), 4) if decoy else None,
            "separation": round(float(np.mean(bind) - np.mean(decoy)), 4) if bind and decoy else None,
            "pocket_atoms": len(pocket["pocket_atoms"]),
            "rows": sorted(rows, key=lambda r: (r["score"] is not None, r["score"] or -9), reverse=True),
        }
        print(f"  [{key}] AUROC={results[key]['auroc']} sep={results[key]['separation']} "
              f"mapped={len(scored)}/{len(rows)} rc={rc}", flush=True)

    payload = {
        "model": "DrugCLIP (Uni-Mol pocket<->molecule CLIP)", "checkpoint": CKPT,
        "pocket_mode": "literature site residues", "radius": RADIUS,
        "question": "structure-based pocket<->molecule shared cosine space; binder vs decoy?",
        "baselines": {"balm_nav18": 0.857, "balm_mtor": 1.000, "boltz2_nav18": 0.714,
                      "boltz2_mtor": 1.000, "conplex_nav": 0.437},
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
