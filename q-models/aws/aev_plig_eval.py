"""AEV-PLIG (oxpig) structure-based binding-affinity scorer on the Quiver Nav1.8 + mTOR panels.

WHAT AEV-PLIG IS
  AEV-PLIG (Communications Chemistry 2025, "Narrowing the gap between ML scoring functions and
  FEP using augmented data"; https://github.com/oxpig/AEV-PLIG) is an attention GNN scoring
  function. It is an FEP-SURROGATE-STYLE *re-scorer*: given a BOUND 3D protein-ligand COMPLEX it
  predicts pK (affinity). It is ligand-centric — ligand atoms are graph nodes; the protein context
  is encoded as radial Atomic Environment Vectors (AEVs, TorchANI) over protein atoms within ~5.1 A
  of each ligand atom. Inference (process_and_predict.py) consumes a CSV with columns
  {unique_id, sdf_file, pdb_file} — i.e. a DOCKED/BOUND LIGAND POSE (.sdf) + a PROTEIN STRUCTURE
  (.pdb). There is NO sequence+SMILES path.

THE HONESTY PROBLEM (read this before trusting any number below)
  We have ZERO holo (ligand-bound) crystal structures for Nav1.8 or mTOR, and no co-crystal poses
  for the panel compounds. AEV-PLIG is therefore POSE-GATED for our targets, exactly like the prior
  GatorAffinity attempt that scored 0 pairs. The AEV radial terms are only meaningful if the ligand
  sits in a physically plausible pose inside the pocket; a conformer floating in empty space yields
  ~zero protein-ligand contacts and a meaningless score.

  This eval makes the BEST HONEST ATTEMPT rather than fabricating poses:
    Tier A (preferred): smina/gnina blind-or-pocket dock each panel SMILES into the AlphaFold model
       (Nav1.8 AF-Q9Y5Y9, mTOR AF-P42345), take the top pose -> real protein-ligand contacts.
    Tier B (fallback):  RDKit ETKDG conformer translated to the literature pocket centroid
       (Nav1.8 DIV-S6 anesthetic site; mTOR FRB rapalog site). Crude, un-minimized, NO clash
       resolution -> flagged low-fidelity.
    Tier C (no pose):   if neither yields a pose with real ligand<->protein contacts, the pair is
       SKIPPED and recorded (n_skipped + reason). We do NOT invent a number.

  Whichever tier produced each pose is recorded per-compound ("pose_source") and per-target
  ("pose_tier", "n_scored", "n_skipped", "skip_reason") so the AUROC carries its own asterisk.

  AlphaFold apo models also have a closed/ungated pocket for a big channel like Nav1.8 — even a real
  dock into an apo model is a weak proxy for the holo site. That caveat is recorded too.

OUTPUT
  Per target: AUROC(predicted pK, binder vs decoy) over the SCORABLE pairs only, n_scored /
  n_skipped, pose tier, vs the BALM (0.857 / 1.000) and Boltz-2 (0.714 / 1.000) baselines.
  Every section is try/except-guarded; partial results are always written to OUT.

ENV
  PANELS        /opt/crossmodal_panels.json
  OUT           /root/aev_out/aev_plig_result.json
  AEV_DIR       /opt/AEV-PLIG                (cloned on-instance)
  AEV_MODEL     model name in output/trained_models (default the FEP-benchmark ensemble)
  STRUCT_DIR    /opt/aev_struct              (AlphaFold PDBs land here)
  WORK          /root/aev_work               (scratch: poses, per-target predict CSVs)
  FORCE_CPU     1 -> CPU
  SMINA_BIN     path to smina/gnina if pre-installed (else we try PATH, else Tier B)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

import numpy as np

PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/aev_out/aev_plig_result.json"))
AEV_DIR = Path(os.environ.get("AEV_DIR", "/opt/AEV-PLIG"))
AEV_MODEL = os.environ.get("AEV_MODEL", "model_GATv2Net_ligsim90_fep_benchmark")
STRUCT_DIR = Path(os.environ.get("STRUCT_DIR", "/opt/aev_struct"))
WORK = Path(os.environ.get("WORK", "/root/aev_work"))
DEVICE = "cpu" if os.environ.get("FORCE_CPU") == "1" else "auto"
SMINA_BIN = os.environ.get("SMINA_BIN", "")

# Targets: AlphaFold accessions + literature pocket residues (mirror aws/drugclip_pocket_prep.py).
TARGETS = {
    "nav18": {
        "uniprot": "Q9Y5Y9",  # SCN10A / Nav1.8
        # DIV-S6 local-anesthetic / pore-blocker site (approx; verify vs AF numbering)
        "site_residues": [1399, 1400, 1401, 1402, 1403, 1404, 1405, 1406],
    },
    "mtor": {
        "uniprot": "P42345",  # mTOR
        # FRB domain (rapamycin/FKBP12 site); rapalogs bind here
        "site_residues": list(range(2025, 2115, 5)),
    },
}
AF_PDB_URL = "https://alphafold.ebi.ac.uk/files/AF-{acc}-F1-model_v4.pdb"

# Baselines for apples-to-apples context (same panels).
BASELINES = {
    "balm_nav18_auroc": 0.857, "balm_mtor_auroc": 1.000,
    "boltz2_nav18_auroc": 0.714, "boltz2_mtor_auroc": 1.000,
    "conplex_nav_auroc": 0.437, "mammal_crossmodal_cosine": 0.08,
}

# AEV-PLIG's radial cutoff is ~5.0 A (RcR); a pose is only meaningful if >=1 ligand heavy atom is
# within CONTACT_CUTOFF of a protein heavy atom. We use a slightly looser gate to admit a pose.
CONTACT_CUTOFF = 5.0


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    labels = list(labels)
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


# --------------------------------------------------------------------------------------------------
# Structure fetch
# --------------------------------------------------------------------------------------------------
def fetch_alphafold(acc: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    url = AF_PDB_URL.format(acc=acc)
    print(f"[struct] fetching {url}", flush=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def parse_pdb_heavy(pdb_path: Path):
    """Return (heavy_atoms[(elem,(x,y,z))], ca_by_res{resnum:(x,y,z)}) for ATOM records."""
    heavy, ca = [], {}
    for ln in pdb_path.read_text().splitlines():
        if not ln.startswith("ATOM"):
            continue
        try:
            elem = (ln[76:78].strip() or ln[12:16].strip()[0]).upper()
            if elem == "H":
                continue
            x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
            heavy.append((elem, (x, y, z)))
            if ln[12:16].strip() == "CA":
                ca[int(ln[22:26])] = (x, y, z)
        except Exception:
            continue
    return heavy, ca


def pocket_centroid(ca_by_res, site_residues):
    pts = [ca_by_res[r] for r in site_residues if r in ca_by_res]
    if not pts:
        return None, 0
    arr = np.array(pts, dtype=float)
    return arr.mean(axis=0), len(pts)


# --------------------------------------------------------------------------------------------------
# Pose generation
# --------------------------------------------------------------------------------------------------
def which_smina():
    if SMINA_BIN and Path(SMINA_BIN).exists():
        return SMINA_BIN
    for name in ("smina", "gnina", "smina.static"):
        try:
            p = subprocess.run(["which", name], capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout.strip()
        except Exception:
            continue
    return None


def smiles_to_3d_sdf(smiles: str, out_sdf: Path, translate_to=None) -> bool:
    """RDKit ETKDG 3D conformer -> SDF. Optionally translate centroid to `translate_to` (pocket)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return False
    m = Chem.AddHs(m)
    if AllChem.EmbedMolecule(m, AllChem.ETKDGv3()) != 0:
        if AllChem.EmbedMolecule(m, useRandomCoords=True) != 0:
            return False
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    if translate_to is not None:
        conf = m.GetConformer()
        coords = np.array([list(conf.GetAtomPosition(i)) for i in range(m.GetNumAtoms())])
        shift = np.asarray(translate_to, float) - coords.mean(axis=0)
        for i in range(m.GetNumAtoms()):
            x, y, z = coords[i] + shift
            conf.SetAtomPosition(i, Chem.rdGeometry.Point3D(float(x), float(y), float(z)))
    out_sdf.parent.mkdir(parents=True, exist_ok=True)
    w = Chem.SDWriter(str(out_sdf))
    w.write(m)
    w.close()
    return out_sdf.exists() and out_sdf.stat().st_size > 0


def dock_smina(smina_bin: str, smiles: str, receptor_pdb: Path, center, out_sdf: Path,
               box=22.0) -> bool:
    """Best-effort smina dock: SMILES -> 3D sdf ligand -> smina into a box at `center`.
    smina reads SMILES-derived sdf; receptor needs to be a pdb/pdbqt. We pass the raw .pdb and let
    smina add its own; if that fails the caller falls back to Tier B."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    lig_in = out_sdf.with_suffix(".in.sdf")
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return False
    m = Chem.AddHs(m)
    if AllChem.EmbedMolecule(m, AllChem.ETKDGv3()) != 0:
        if AllChem.EmbedMolecule(m, useRandomCoords=True) != 0:
            return False
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    lig_in.parent.mkdir(parents=True, exist_ok=True)
    w = Chem.SDWriter(str(lig_in)); w.write(m); w.close()
    cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
    cmd = [smina_bin, "-r", str(receptor_pdb), "-l", str(lig_in),
           "--center_x", str(cx), "--center_y", str(cy), "--center_z", str(cz),
           "--size_x", str(box), "--size_y", str(box), "--size_z", str(box),
           "--exhaustiveness", "8", "--num_modes", "1", "-o", str(out_sdf)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        ok = p.returncode == 0 and out_sdf.exists() and out_sdf.stat().st_size > 0
        if not ok:
            print(f"[dock] smina rc={p.returncode} stderr={p.stderr[-300:]}", flush=True)
        return ok
    except Exception as e:
        print(f"[dock] smina exception: {e}", flush=True)
        return False


def sdf_protein_contacts(sdf_path: Path, heavy_atoms) -> int:
    """Count ligand heavy atoms with >=1 protein heavy atom within CONTACT_CUTOFF. 0 -> bad pose."""
    from rdkit import Chem
    suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=True)
    m = suppl[0] if len(suppl) else None
    if m is None or m.GetNumConformers() == 0:
        return 0
    conf = m.GetConformer()
    lig = np.array([list(conf.GetAtomPosition(i)) for i in range(m.GetNumAtoms())])
    prot = np.array([xyz for _, xyz in heavy_atoms], dtype=float)
    if len(prot) == 0 or len(lig) == 0:
        return 0
    # chunked distance to avoid a huge dense matrix on the big channel
    contacts = 0
    cc2 = CONTACT_CUTOFF ** 2
    for la in lig:
        d2 = ((prot - la) ** 2).sum(axis=1)
        if (d2 <= cc2).any():
            contacts += 1
    return contacts


# --------------------------------------------------------------------------------------------------
# AEV-PLIG inference
# --------------------------------------------------------------------------------------------------
def run_aev_plig(predict_csv: Path, data_name: str) -> dict:
    """Run process_and_predict.py from AEV_DIR; return {unique_id: pred_pK}. Raises on hard failure."""
    py = sys.executable
    cmd = [py, "process_and_predict.py",
           f"--dataset_csv={predict_csv}",
           f"--data_name={data_name}",
           f"--trained_model_name={AEV_MODEL}",
           f"--device={DEVICE}",
           "--skip_validation"]
    print(f"[aev] {' '.join(cmd)} (cwd={AEV_DIR})", flush=True)
    p = subprocess.run(cmd, cwd=str(AEV_DIR), capture_output=True, text=True, timeout=3000)
    print(f"[aev] rc={p.returncode}\n[aev][stdout tail]\n{p.stdout[-1500:]}\n"
          f"[aev][stderr tail]\n{p.stderr[-1500:]}", flush=True)
    pred_path = AEV_DIR / "output" / "predictions" / f"{data_name}_predictions.csv"
    if not pred_path.exists():
        raise RuntimeError(f"no predictions written (rc={p.returncode}); stderr tail: {p.stderr[-400:]}")
    import csv
    out = {}
    with pred_path.open() as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            pred_col = "preds" if "preds" in r else next((c for c in r if c.startswith("pred")), None)
            if pred_col is None:
                continue
            try:
                out[r["unique_id"]] = float(r[pred_col])
            except Exception:
                continue
    return out


# --------------------------------------------------------------------------------------------------
# Per-target driver
# --------------------------------------------------------------------------------------------------
def score_target(key: str, panel: dict) -> dict:
    res = {
        "target": panel["target"], "seq_len": panel.get("seq_len"),
        "pose_tier": None, "n_scored": 0, "n_skipped": 0, "skip_reason": None,
        "auroc_pred_pk": None, "compounds": [], "caveats": [],
    }
    tcfg = TARGETS.get(key)
    if tcfg is None:
        res["skip_reason"] = f"no target config for {key}"
        res["n_skipped"] = len(panel["compounds"])
        return res

    # 1. structure + pocket
    try:
        pdb = fetch_alphafold(tcfg["uniprot"], STRUCT_DIR / f"AF-{tcfg['uniprot']}.pdb")
        heavy, ca = parse_pdb_heavy(pdb)
        center, n_site = pocket_centroid(ca, tcfg["site_residues"])
        if center is None:
            res["skip_reason"] = ("AlphaFold model lacks the literature site residues "
                                  f"{tcfg['site_residues'][:3]}... in CA records; cannot place a pose")
            res["n_skipped"] = len(panel["compounds"])
            res["caveats"].append("pocket residues absent from AF numbering")
            return res
        res["caveats"].append(
            f"apo AlphaFold model AF-{tcfg['uniprot']} (NO holo structure exists for {panel['target']}); "
            f"pocket = centroid of {n_site} site-residue CAs at "
            f"({center[0]:.1f},{center[1]:.1f},{center[2]:.1f})")
    except Exception as e:
        res["skip_reason"] = f"structure/pocket prep failed: {e}"
        res["n_skipped"] = len(panel["compounds"])
        res["caveats"].append(traceback.format_exc()[-600:])
        return res

    smina_bin = which_smina()
    tier = "A_smina_dock" if smina_bin else "B_rdkit_centroid_placement"
    res["pose_tier"] = tier
    if not smina_bin:
        res["caveats"].append(
            "NO smina/gnina on PATH -> Tier B: RDKit ETKDG conformer translated to pocket centroid, "
            "un-minimized, no clash resolution. AEV radial terms from this pose are LOW FIDELITY; "
            "treat AUROC as a sanity floor, not a real dock.")
    else:
        res["caveats"].append(f"Tier A: smina dock into AF pocket box via {smina_bin}")

    # 2. per-compound pose -> contacts gate -> rows for the predict CSV
    twork = WORK / key
    twork.mkdir(parents=True, exist_ok=True)
    rows, meta = [], []  # rows -> predict CSV; meta aligns unique_id -> (drug,label,pose_source)
    for comp in panel["compounds"]:
        uid = f"{key}_{comp['drug']}".replace(" ", "_")
        sdf = twork / f"{uid}.sdf"
        pose_source = None
        try:
            made = False
            if smina_bin:
                made = dock_smina(smina_bin, comp["smiles"], pdb, center, sdf)
                pose_source = "smina_dock" if made else None
            if not made:  # Tier B fallback (also the path when no smina)
                made = smiles_to_3d_sdf(comp["smiles"], sdf, translate_to=center)
                pose_source = "rdkit_centroid" if made else None
            if not made:
                comp_rec = {"drug": comp["drug"], "label": comp["label"],
                            "scored": False, "reason": "pose generation failed (RDKit embed)"}
                res["compounds"].append(comp_rec); res["n_skipped"] += 1
                continue
            contacts = sdf_protein_contacts(sdf, heavy)
            if contacts == 0:
                comp_rec = {"drug": comp["drug"], "label": comp["label"], "scored": False,
                            "pose_source": pose_source,
                            "reason": f"pose has 0 ligand-protein contacts within {CONTACT_CUTOFF}A "
                                      "(AEVs would be meaningless)"}
                res["compounds"].append(comp_rec); res["n_skipped"] += 1
                continue
            # writable pdb copy per row (process_and_predict reads pdb_file per row)
            rows.append({"unique_id": uid, "sdf_file": str(sdf), "pdb_file": str(pdb)})
            meta.append({"unique_id": uid, "drug": comp["drug"], "label": comp["label"],
                         "pose_source": pose_source, "contacts": contacts})
        except Exception as e:
            res["compounds"].append({"drug": comp["drug"], "label": comp["label"], "scored": False,
                                     "reason": f"pose pipeline error: {e}"})
            res["n_skipped"] += 1

    if not rows:
        res["skip_reason"] = ("POSE-GATED: no panel compound produced a pose with real "
                              f"ligand-protein contacts on the apo AF model. AEV-PLIG scored 0 "
                              f"pairs for {panel['target']} (same failure mode as GatorAffinity).")
        return res

    # 3. write the AEV-PLIG predict CSV and run inference
    import csv
    predict_csv = twork / f"{key}_predict.csv"
    with predict_csv.open("w", newline="") as fh:
        wri = csv.DictWriter(fh, fieldnames=["unique_id", "sdf_file", "pdb_file"])
        wri.writeheader()
        for r in rows:
            wri.writerow(r)

    try:
        preds = run_aev_plig(predict_csv, f"aev_{key}")
    except Exception as e:
        res["skip_reason"] = f"AEV-PLIG inference failed after posing {len(rows)} pairs: {e}"
        res["caveats"].append(traceback.format_exc()[-800:])
        res["n_skipped"] += len(rows)
        return res

    # 4. join predictions -> labels, compute AUROC over the scored subset
    labels, scores = [], []
    for m in meta:
        pk = preds.get(m["unique_id"])
        if pk is None:
            res["compounds"].append({"drug": m["drug"], "label": m["label"], "scored": False,
                                     "pose_source": m["pose_source"],
                                     "reason": "AEV-PLIG dropped the pair (validation/featurization)"})
            res["n_skipped"] += 1
            continue
        res["compounds"].append({"drug": m["drug"], "label": m["label"], "scored": True,
                                 "pred_pk": round(pk, 3), "pose_source": m["pose_source"],
                                 "contacts": m["contacts"]})
        res["n_scored"] += 1
        labels.append(m["label"]); scores.append(pk)

    res["auroc_pred_pk"] = auroc(labels, scores)
    res["compounds"].sort(key=lambda r: (r.get("scored", False), r.get("pred_pk", -999)), reverse=True)
    print(f"[{key}] {panel['target']}: tier={tier} scored={res['n_scored']} "
          f"skipped={res['n_skipped']} AUROC={res['auroc_pred_pk']}", flush=True)
    return res


def main() -> int:
    payload = {
        "model": "AEV-PLIG (oxpig; GATv2 attention GNN, AEV-encoded protein context)",
        "repo": "https://github.com/oxpig/AEV-PLIG",
        "trained_model": AEV_MODEL,
        "input_requirement": ("3D BOUND protein-ligand COMPLEX: CSV {unique_id, sdf_file (docked "
                              "ligand pose), pdb_file (protein)}. NO sequence+SMILES path."),
        "honest_assessment": ("POSE-GATED for Nav1.8/mTOR: no holo structures or co-crystal poses "
                              "exist. We dock/place into apo AlphaFold models as a best effort and "
                              "record pose tier + contacts; pairs with no real ligand-protein "
                              "contact are SKIPPED, not fabricated."),
        "question": "Does an FEP-surrogate re-scorer beat BALM/Boltz-2 on no-holo Quiver targets?",
        "baselines_for_context": BASELINES,
        "results": {},
        "errors": {},
    }
    try:
        panels = json.loads(PANELS.read_text())
    except Exception as e:
        payload["errors"]["panels"] = f"could not load panels: {e}"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2))
        print(f"[fatal] {e}", flush=True)
        return 1

    for key, panel in panels.items():
        try:
            payload["results"][key] = score_target(key, panel)
        except Exception as e:
            payload["errors"][key] = traceback.format_exc()[-1200:]
            payload["results"][key] = {"target": panel.get("target", key), "auroc_pred_pk": None,
                                       "n_scored": 0, "n_skipped": len(panel.get("compounds", [])),
                                       "skip_reason": f"unhandled error: {e}"}
        # write incrementally so a later crash never loses an earlier target
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"[done] wrote {OUT}", flush=True)
    summ = {k: {"auroc_pred_pk": v.get("auroc_pred_pk"), "n_scored": v.get("n_scored"),
                "n_skipped": v.get("n_skipped"), "pose_tier": v.get("pose_tier")}
            for k, v in payload["results"].items()}
    print(json.dumps(summ, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
