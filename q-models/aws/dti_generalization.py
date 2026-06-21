"""DTI Nav-generalization cross-check (overnight Phase 3) — does a structure-based affinity model
that CLAIMS unseen-protein generalization crack the Nav blind spot that sinks BindingDB-trained DTI?

==========================  CHOSEN MODEL  ==========================
  Model:    GatorAffinity (bioRxiv 2025, AIDD-LiLab)
  Paper:    "Boosting Protein-Ligand Binding Affinity Prediction with Large-Scale Synthetic
            Structural Data", doi:10.1101/2025.09.29.679384 (PMID 41256614)
  Repo:     https://github.com/AIDD-LiLab/GatorAffinity
  License:  CODE = MIT.  CHECKPOINTS = CC BY-NC-SA 4.0 (NON-COMMERCIAL — research/eval only,
            same posture as our other non-commercial evals; flag to Quiver legal before any
            product use).  ATOMICA backbone (HuggingFace ada-f/ATOMICA) — verify its license too.
  Why GatorAffinity over IPBind:
    - IPBind (arXiv 2504.16261) reports the strongest LOW-IDENTITY generalization (Pearson 0.732 at
      30% identity) and is the more on-theme "unseen-protein" claim — BUT it has NO findable public
      inference repo (the arXiv page has no code-availability link; the only "ipbind" GitHub is an
      unrelated socket library). Not runnable unattended.
    - GatorAffinity HAS a public MIT repo with a concrete inference entrypoint (inference.py),
      a reproducible environment.sh, downloadable checkpoints, and ALSO claims strong generalizable
      affinity ranking on a leak-proof benchmark. It is the usable proxy for the Phase-3 question.

  Install (from the repo's environment.sh, adapted for a venv since conda-activate fails in userdata):
      python 3.9-ish; torch==2.1.1+cu118; torch_scatter/torch_cluster (cu118 wheels);
      e3nn==0.5.1 (NOT >0.5.4); rdkit-pypi==2022.9.5; openbabel-wheel; biopython; biotite;
      atom3d; numpy==1.26.4 (numpy<2). ATOMICA backbone ckpt from HF ada-f/ATOMICA.

  Inference API (from the repo README + inference.py):
      1. Build a CSV: pdb_id, protein_pdb (pocket PDB), ligand_pdb (NO hydrogens), protein_chains,
         lig_code, smiles, lig_resi, label.
      2. python data/process_pdbs.py --data_index_file <csv> --out_path <pkl>
      3. python inference.py --model_ckpt <ckpt> --test_set_path <pkl>
      inference.py builds a `results_df` with a 'Predicted_Affinity' column and prints
      RMSE/Pearson/Spearman/CI — but DOES NOT SAVE predictions. So this script imports the repo's
      own model + datamodule the way inference.py does and captures Predicted_Affinity per complex
      directly (falling back to monkeypatching pandas.DataFrame.to_string / re-implementing the
      predict loop if the import surface differs). All paths guarded.

  RISK FLAGS (the main agent should sanity-check before launch — see also the userdata header):
    * STRUCTURE-BASED, not sequence-free. The campaign framed Phase 3 as "structure-free"; no public
      structure-free unseen-protein model with usable inference exists, so we test the best usable
      *generalizable* affinity model instead. It needs a 3D pocket + a 3D ligand pose, which for our
      data-poor targets (Nav1.8, mTOR — no holo crystal) means AlphaFold pocket + an RDKit/obabel
      docked-free conformer placed at the pocket centroid. That pose is APPROXIMATE (no docking),
      so a null/below-Boltz result may reflect pose quality, not the model — recorded as a caveat.
    * Nav1.8 (1956 aa) / mTOR (2549 aa) AlphaFold models are large/low-confidence in the flexible
      linkers; we carve a pocket window (reusing drugclip_pocket_prep's literature-site centroid).
    * ATOMICA backbone + GatorAffinity ckpt are separate downloads; cached to S3 on first run.
    * Toolchain is NEW + fragile -> userdata fails FAST (deps-check gate) under the <=2 relaunch cap.

The eval reads the SAME Nav1.8/mTOR panels Boltz-2 + BALM scored (crossmodal_panels.json), scores
each compound vs the target, computes binder-vs-decoy AUROC + separation per target, and reports
head-to-head vs BALM (0.857/1.000), Boltz-2 (0.714/1.000), ConPLex (0.437).
====================================================================
"""
from __future__ import annotations
import json, os, sys, subprocess, tempfile, traceback, urllib.request
from pathlib import Path
import numpy as np

DEVICE = "cpu" if os.environ.get("FORCE_CPU") == "1" else "cuda"
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/dti_gen_out/dti_generalization_result.json"))
GATOR_DIR = Path(os.environ.get("GATOR_DIR", "/opt/GatorAffinity"))
GATOR_CKPT = os.environ.get("GATOR_CKPT", str(GATOR_DIR / "model_checkpoints" / "Kd+Ki+IC50_experimental_fine_tuning.ckpt"))
WORK = Path(os.environ.get("WORK", "/root/dti_gen_work"))
FRAG = os.environ.get("FRAGMENTATION_METHOD", "PS_300")

# AlphaFold targets + literature binding-site residues (mirrors aws/drugclip_pocket_prep.py).
TARGETS = {
    "nav18": {"uniprot": "Q9Y5Y9", "name": "Nav1.8 (SCN10A)",
              "site_residues": [1399, 1400, 1401, 1402, 1403, 1404, 1405, 1406]},
    "mtor": {"uniprot": "P42345", "name": "mTOR",
             "site_residues": list(range(2025, 2115, 10))},
}
POCKET_RADIUS = 12.0   # Angstroms around the literature-site centroid (CA atoms within radius)

BASELINES = {"balm_nav18": 0.857, "balm_mtor": 1.000, "boltz2_nav18": 0.714,
             "boltz2_mtor": 1.000, "conplex_nav": 0.437}


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    labels = list(labels)
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(roc_auc_score(labels, scores))


# ---------------- AlphaFold structure fetch (AF API; v6 URL, falls back) ----------------
def fetch_alphafold_pdb(uniprot, out: Path) -> Path:
    url = None
    try:
        meta = json.loads(urllib.request.urlopen(
            f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot}", timeout=60).read())
        if meta:
            url = meta[0].get("pdbUrl")
    except Exception as e:
        print(f"[warn] AF API lookup failed for {uniprot}: {e}", flush=True)
    candidates = [url] if url else []
    candidates += [f"https://alphafold.ebi.ac.uk/files/AF-{uniprot}-F1-model_{v}.pdb"
                   for v in ("v6", "v5", "v4")]
    for u in candidates:
        if not u:
            continue
        try:
            print(f"[fetch] {u}", flush=True)
            out.write_bytes(urllib.request.urlopen(u, timeout=120).read())
            return out
        except Exception as e:
            print(f"[warn] fetch failed {u}: {e}", flush=True)
    raise RuntimeError(f"could not fetch AlphaFold PDB for {uniprot}")


def parse_atoms(pdb_text):
    """All protein ATOM lines -> list of (resnum, atomname, x, y, z, raw_line)."""
    atoms = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM"):
            try:
                resnum = int(line[22:26]); x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
                atoms.append((resnum, line[12:16].strip(), x, y, z, line))
            except ValueError:
                continue
    return atoms


def carve_pocket_pdb(pdb_text, site_residues, out_pdb: Path, radius=POCKET_RADIUS):
    """Write a pocket PDB = all atoms within `radius` of the CA centroid of the literature site."""
    atoms = parse_atoms(pdb_text)
    ca = {r: (x, y, z) for (r, name, x, y, z, _) in atoms if name == "CA"}
    present = [r for r in site_residues if r in ca]
    if not present:
        raise RuntimeError("no literature-site residues present in AF numbering")
    cx = np.mean([ca[r][0] for r in present]); cy = np.mean([ca[r][1] for r in present]); cz = np.mean([ca[r][2] for r in present])
    keep_lines = [raw for (r, name, x, y, z, raw) in atoms
                  if (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= radius ** 2]
    out_pdb.write_text("\n".join(keep_lines) + "\nEND\n")
    return {"center": [round(cx, 2), round(cy, 2), round(cz, 2)], "n_atoms": len(keep_lines),
            "site_residues_present": present, "radius": radius,
            "centroid_note": "ligand 3D conformer is translated to this pocket centroid (no docking)"}


# ---------------- 3D ligand pose (RDKit conformer -> pocket centroid), no docking ----------------
def write_ligand_pdb(smiles, center, out_pdb: Path, lig_code="LIG", resi=1):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise RuntimeError(f"unparseable SMILES: {smiles}")
    m = Chem.AddHs(m)
    # NOTE: EmbedMolecule takes maxAttempts (NOT maxIterations) — the bad kwarg failed the C++
    # signature for every ligand last run -> 0 poses built. Use ETKDGv3 params explicitly.
    p = AllChem.ETKDGv3(); p.randomSeed = 42; p.maxIterations = 200
    if AllChem.EmbedMolecule(m, p) != 0:
        p2 = AllChem.ETKDGv3(); p2.randomSeed = 7; p2.useRandomCoords = True; p2.maxIterations = 400
        AllChem.EmbedMolecule(m, p2)
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    m = Chem.RemoveHs(m)   # GatorAffinity wants NO hydrogens on the ligand
    conf = m.GetConformer()
    # translate the conformer centroid to the pocket centroid
    pos = np.array([list(conf.GetAtomPosition(i)) for i in range(m.GetNumAtoms())])
    shift = np.array(center) - pos.mean(0)
    for i in range(m.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (p.x + shift[0], p.y + shift[1], p.z + shift[2]))
    # write a minimal HETATM PDB with the chosen lig_code/resi
    lines = []
    for i, atom in enumerate(m.GetAtoms()):
        p = conf.GetAtomPosition(i)
        el = atom.GetSymbol()
        lines.append(f"HETATM{i+1:>5} {el:<3} {lig_code:>3} A{resi:>4}    "
                     f"{p.x:8.3f}{p.y:8.3f}{p.z:8.3f}  1.00  0.00          {el:>2}")
    out_pdb.write_text("\n".join(lines) + "\nEND\n")
    return out_pdb


# ---------------- GatorAffinity scoring ----------------
def build_index_csv(rows, csv_path: Path):
    import csv
    cols = ["pdb_id", "protein_pdb", "ligand_pdb", "protein_chains", "lig_code", "smiles", "lig_resi", "label"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})
    return csv_path


def gator_predict(pkl_path: Path):
    """Run GatorAffinity inference and return list of Predicted_Affinity in dataset order.

    Strategy A (preferred): import inference.py's machinery and capture results_df.
    Strategy B (fallback): run inference.py as a subprocess, monkeypatching pandas so the
    (otherwise-unsaved) results_df is dumped to a sidecar JSON we then read.
    """
    sys.path.insert(0, str(GATOR_DIR))
    # --- Strategy A: direct import + capture of results_df via a pandas hook ---
    sidecar = WORK / "gator_results.json"
    if sidecar.exists():
        sidecar.unlink()
    runner = WORK / "_gator_runner.py"
    runner.write_text(
        "import sys, json, os\n"
        f"sys.path.insert(0, {str(GATOR_DIR)!r})\n"
        "import pandas as pd\n"
        "_orig_init = pd.DataFrame.__init__\n"
        "def _hook(self, *a, **k):\n"
        "    _orig_init(self, *a, **k)\n"
        "    try:\n"
        "        if 'Predicted_Affinity' in getattr(self, 'columns', []):\n"
        f"            self.to_json({str(sidecar)!r}, orient='records')\n"
        "    except Exception:\n"
        "        pass\n"
        "pd.DataFrame.__init__ = _hook\n"
        "import runpy\n"
        f"sys.argv = ['inference.py', '--model_ckpt', {GATOR_CKPT!r}, '--test_set_path', {str(pkl_path)!r},"
        f" '--device', {DEVICE!r}, '--fragmentation_method', {FRAG!r}]\n"
        "runpy.run_path(os.path.join(" + repr(str(GATOR_DIR)) + ", 'inference.py'), run_name='__main__')\n"
    )
    proc = subprocess.run([sys.executable, str(runner)], cwd=str(GATOR_DIR),
                          capture_output=True, text=True, timeout=2400)
    print("[gator stdout tail]\n" + proc.stdout[-2000:], flush=True)
    if proc.stderr:
        print("[gator stderr tail]\n" + proc.stderr[-2000:], flush=True)
    if sidecar.exists():
        recs = json.loads(sidecar.read_text())
        preds = [float(r["Predicted_Affinity"]) for r in recs if "Predicted_Affinity" in r]
        if preds:
            return preds
    raise RuntimeError(f"GatorAffinity produced no Predicted_Affinity (rc={proc.returncode}); "
                       "check the stderr tail above (likely a dataset/backbone-ckpt mismatch)")


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    panels = json.loads(PANELS.read_text())
    R = {"model": "GatorAffinity (ATOMICA backbone; SE(3) TFN; pretrained on synthetic Boltz-1 complexes)",
         "checkpoint": GATOR_CKPT, "phase": "3 - DTI Nav-generalization cross-check",
         "license": {"code": "MIT", "checkpoints": "CC BY-NC-SA 4.0 (non-commercial)"},
         "baselines": BASELINES, "pose_caveat": ("structure-based: AlphaFold pocket + RDKit/MMFF "
         "conformer translated to the literature-site centroid (NO docking) — a null result may "
         "reflect pose quality, not the model"), "targets": {}, "panels": {}}

    def flush():
        OUT.write_text(json.dumps(R, indent=2, default=str))

    # 1) Prepare AlphaFold pockets per target (guarded).
    prepared = {}
    for key, t in TARGETS.items():
        try:
            pdb = fetch_alphafold_pdb(t["uniprot"], WORK / f"{key}_af.pdb")
            info = carve_pocket_pdb(pdb.read_text(), t["site_residues"], WORK / f"{key}_pocket.pdb")
            info["uniprot"] = t["uniprot"]; info["name"] = t["name"]
            info["pocket_pdb"] = str(WORK / f"{key}_pocket.pdb")
            prepared[key] = info
            R["targets"][key] = {k: v for k, v in info.items() if k != "pocket_pdb"}
            print(f"[pocket] {key}: {info['n_atoms']} atoms @ {info['center']}", flush=True)
        except Exception as e:
            R["targets"][key] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] pocket {key}: {e}\n{traceback.format_exc()[:600]}", flush=True)
        flush()

    # 2) Per panel: build ligand poses + index CSV, process to pkl, run GatorAffinity, score.
    for pkey, panel in panels.items():
        if pkey not in prepared:
            R["panels"][pkey] = {"skip": f"pocket prep failed for {pkey}"}; flush(); continue
        try:
            pocket = prepared[pkey]; center = pocket["center"]
            rows, ok_idx = [], []
            for i, c in enumerate(panel["compounds"]):
                lig_pdb = WORK / f"{pkey}_lig_{i}.pdb"
                try:
                    write_ligand_pdb(c["smiles"], center, lig_pdb)
                    rows.append({"pdb_id": f"{pkey}_{i}", "protein_pdb": pocket["pocket_pdb"],
                                 "ligand_pdb": str(lig_pdb), "protein_chains": "A", "lig_code": "LIG",
                                 "smiles": c["smiles"], "lig_resi": 1, "label": 0.0})
                    ok_idx.append(i)
                except Exception as e:
                    print(f"[warn] ligand {pkey}/{c.get('drug')}: {e}", flush=True)
            if len(rows) < 3:
                R["panels"][pkey] = {"skip": f"only {len(rows)} ligand poses built"}; flush(); continue

            csv_path = build_index_csv(rows, WORK / f"{pkey}_index.csv")
            pkl_path = WORK / f"{pkey}.pkl"
            # process_pdbs.py args are --input_csv / --output_pkl (verified vs repo source);
            # the earlier --data_index_file/--out_path were wrong (rc=2 unrecognized). inference.py's
            # --model_ckpt/--test_set_path (below) are already correct per the same source check.
            proc = subprocess.run([sys.executable, str(GATOR_DIR / "data" / "process_pdbs.py"),
                                   "--input_csv", str(csv_path), "--output_pkl", str(pkl_path)],
                                  cwd=str(GATOR_DIR), capture_output=True, text=True, timeout=1800)
            print(f"[process_pdbs {pkey}] rc={proc.returncode}\n{proc.stdout[-800:]}\n{proc.stderr[-800:]}", flush=True)
            if not pkl_path.exists():
                raise RuntimeError(f"process_pdbs produced no pkl (rc={proc.returncode})")

            preds = gator_predict(pkl_path)
            if len(preds) != len(rows):
                print(f"[warn] {pkey}: {len(preds)} preds vs {len(rows)} rows; aligning by order", flush=True)
            labels = [panel["compounds"][ok_idx[j]]["label"] for j in range(min(len(preds), len(ok_idx)))]
            scores = preds[:len(labels)]
            b = [s for s, l in zip(scores, labels) if l == 1]
            d = [s for s, l in zip(scores, labels) if l == 0]
            R["panels"][pkey] = {
                "target": panel["target"], "n_scored": len(scores),
                "auroc": auroc(labels, scores),
                "mean_pred_binders": round(float(np.mean(b)), 4) if b else None,
                "mean_pred_decoys": round(float(np.mean(d)), 4) if d else None,
                "separation": round(float(np.mean(b) - np.mean(d)), 4) if b and d else None,
                "per_compound": [{"drug": panel["compounds"][ok_idx[j]]["drug"],
                                  "label": labels[j], "pred_affinity": round(float(scores[j]), 4)}
                                 for j in range(len(scores))],
            }
            print(f"[{pkey}] AUROC={R['panels'][pkey]['auroc']} sep={R['panels'][pkey]['separation']}", flush=True)
        except Exception as e:
            R["panels"][pkey] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] panel {pkey}: {e}\n{traceback.format_exc()[:800]}", flush=True)
        flush()

    # 3) Head-to-head summary.
    R["head_to_head"] = {
        "nav18": {"gator": (R["panels"].get("nav18") or {}).get("auroc"),
                  "balm": BASELINES["balm_nav18"], "boltz2": BASELINES["boltz2_nav18"],
                  "conplex": BASELINES["conplex_nav"]},
        "mtor": {"gator": (R["panels"].get("mtor") or {}).get("auroc"),
                 "balm": BASELINES["balm_mtor"], "boltz2": BASELINES["boltz2_mtor"]},
    }
    flush()
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(R["head_to_head"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
