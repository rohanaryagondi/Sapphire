"""ATOMICA Nav1.8 binder-vs-decoy eval via FAST DOCKING (no Boltz).

CANDIDATE NEW CAPABILITY TRACK: "structural interaction embedding". ATOMICA
(mims-harvard, MIT) is a geometric model of *intermolecular interaction
interfaces*. The decisive question is unchanged from the Boltz-based attempt:

    Does ATOMICA's interface embedding carry CNS binder signal BEYOND the raw
    docking score?  (i.e. is the structural-interaction embedding additive?)

WHY THIS FILE EXISTS (option (c)): the Boltz co-fold lane was blocked by a hard
CUDA-13 / cuequivariance-ops toolchain failure on the current AWS DL AMI (see
results/atomica_nav18_characterization.md). Instead of FOLDING the 1956-aa
channel + ligand, we DOCK each ligand into a REAL human Nav1.8 cryo-EM receptor
with smina (AutoDock-Vina-based, CPU, static binary, no compile), take the top
pose, build a complex PDB, and ATOMICA-embed it. The receptor already exists and
docking is cheap, so we feed ATOMICA experimental-receptor + predicted-pose
complexes for all 11 panel compounds.

RECEPTOR: PDB 7WFR — "Human Nav1.8 with A-803467, class III" (Homo sapiens,
3.0 Å, single chain A, 1956 residues, exactly matching the panel protein_seq
length). The selective pore blocker A-803467 is resolved in the central cavity
as ligand code 95T. We autobox the docking search around 95T — i.e. dock every
panel ligand into the SAME experimentally-validated pore-blocker site. This is
the cleanest box choice (no hand-picked coordinates). Caveat: Nav1.8 has
MULTIPLE drug sites (central pore for A-803467/local anesthetics vs the VSD-II
fenestration for suzetrigine); docking everything into the pore is a DIRECTIONAL
first look, not a per-drug site-aware prediction.

PIPELINE (two isolated envs; structures handed off as files):
  0. Receptor prep    : download 7WFR.pdb from RCSB; strip waters + the lipid /
       sugar / cholesterol HETATMs; KEEP one channel chain (A) and the bound 95T
       (used only as the autobox reference, then removed from the docked receptor).
       Add hydrogens with obabel. Produce receptor.pdbqt + a 95T-only ref.pdb.
  1. Ligand prep      : RDKit/obabel SMILES -> 3D ligand -> ligand.pdbqt.
  2. Dock             : smina --receptor receptor.pdbqt --ligand ligand.pdbqt
       --autobox_ligand ref.pdb -> top pose + its smina affinity (kcal/mol; more
       negative = better). We take pose #1 and its score.
  3. Complex          : merge receptor (chain A) + top pose (chain B, HETATM
       resname UNL/LIG) into a single complex PDB for ATOMICA; read the ligand
       resname/resi BACK OUT of the file (never hardcoded), as the Boltz eval did.
  4. ATOMICA embed    : build the data_index_file CSV (pdb_id, pdb_path,
       chain1=A, chain2=B, lig_code, lig_smiles, lig_resi), run
       `python -m atomica.data.process_pdbs` then `python -m atomica.get_embeddings`
       IN ATOMICA'S OWN ENV (torch 2.1.1; never shares a process with anything
       else). Read the per-complex `graph_embedding` (interface-level vector).
  5. Readout          :
       - atomica_auroc     : binder-vs-decoy AUROC via LEAVE-ONE-OUT cosine-to-
           binder-centroid. For each held-out compound i, centroid = mean of the
           OTHER binders' L2-normalised graph embeddings; score = cosine(emb_i,
           centroid). Never leaks i into its own centroid; needs no label for the
           held-out point.
       - atomica_knn_auroc : LOO cosine k-NN cross-check (binder-minus-decoy).
       - smina_auroc       : AUROC of -(best smina affinity) on the SAME labels =
           the docking-score baseline ATOMICA must beat or complement. (More
           negative affinity = stronger predicted binding, so we negate so that
           "higher score => more binder-like".)
       - per-complex rows, n_binders/n_decoys, fold/embed failure notes.

Robustness: a compound that fails to dock OR fails to embed is SKIPPED (recorded
in `skipped`), never fatal. Per-compound dock timeout. Atomic result write.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------- env
PANEL_PATH = Path(os.environ.get("PANEL", "/opt/crossmodal_panels.json"))
PANEL_KEY = os.environ.get("PANEL_KEY", "nav18")
OUT = Path(os.environ.get("OUT", "/tmp/atomica_dock_nav18_result.json"))
WORK = Path(os.environ.get("WORK", "/root/atomica_dock_nav18_work"))

# Receptor / docking.
PDB_ID = os.environ.get("RECEPTOR_PDB_ID", "7WFR")          # human Nav1.8 + A-803467 (95T)
REF_LIG_CODE = os.environ.get("REF_LIG_CODE", "95T")        # autobox reference (the bound blocker)
KEEP_CHAIN = os.environ.get("KEEP_CHAIN", "A")              # 7WFR is a single chain A
SMINA_BIN = os.environ.get("SMINA_BIN", "/opt/smina/smina")
OBABEL_BIN = os.environ.get("OBABEL_BIN", "obabel")
SMINA_EXHAUSTIVENESS = os.environ.get("SMINA_EXHAUSTIVENESS", "8")
SMINA_AUTOBOX_ADD = os.environ.get("SMINA_AUTOBOX_ADD", "6")  # angstrom padding around ref ligand
DOCK_TIMEOUT_S = int(os.environ.get("DOCK_TIMEOUT_S", "600"))   # 10 min/compound CPU dock
PREP_TIMEOUT_S = int(os.environ.get("PREP_TIMEOUT_S", "600"))

# ATOMICA (its OWN env): shell out to this interpreter so torch 2.1.1 never shares a
# process with the docking tools. ATOMICA_DIR is the cloned repo (cwd for -m calls).
ATOMICA_PY = os.environ.get("ATOMICA_PY", "/opt/atomica-env/bin/python")
ATOMICA_DIR = Path(os.environ.get("ATOMICA_DIR", "/opt/ATOMICA"))
ATOMICA_MODEL_CONFIG = os.environ.get(
    "ATOMICA_MODEL_CONFIG",
    "/opt/ATOMICA/checkpoints/ATOMICA_checkpoints/pretrain/pretrain_model_config.json",
)
ATOMICA_MODEL_WEIGHTS = os.environ.get(
    "ATOMICA_MODEL_WEIGHTS",
    "/opt/ATOMICA/checkpoints/ATOMICA_checkpoints/pretrain/pretrain_model_weights.pt",
)
ATOMICA_EMBED_TIMEOUT_S = int(os.environ.get("ATOMICA_EMBED_TIMEOUT_S", "1800"))

RCSB_URL = f"https://files.rcsb.org/download/{PDB_ID}.pdb"

# HETATM residue names we strip from the receptor (waters + the membrane / sugar
# environment of a cryo-EM channel + the reference blocker itself). Anything that is
# NOT a standard amino acid and not on this list is also dropped when we keep only the
# polymer; this list is just the explicit "obvious junk" for clarity/logging.
STRIP_HETS = {
    "HOH", "WAT",                       # waters
    "NAG", "BMA", "MAN", "FUC", "GAL",  # glycans
    "CLR", "CHL", "CHS",                # cholesterol
    "PCW", "P5S", "LPE", "POV", "PLM",  # lipids / phospholipids
    "SO4", "PO4", "CL", "NA", "K", "ZN", "MG", "CA",  # ions / buffer
}

_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U", "PYL": "O",
}


# --------------------------------------------------------------------------- metrics
def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score

    labels = list(labels)
    scores = list(scores)
    if len(set(labels)) < 2 or len(labels) != len(scores):
        return None
    if any(s is None for s in scores):
        return None
    return float(roc_auc_score(labels, scores))


def _l2norm(v):
    v = np.asarray(v, dtype=np.float64).reshape(-1)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def loo_centroid_scores(embs, labels):
    """Leave-one-out cosine-to-binder-centroid. For each i, centroid = mean of the
    OTHER binders' normalised embeddings; score = cosine(emb_i, centroid). Never
    leaks i into its own centroid; needs no label for the held-out point."""
    embs = [_l2norm(e) for e in embs]
    labels = list(labels)
    scores = []
    for i in range(len(embs)):
        other_binders = [embs[j] for j in range(len(embs)) if j != i and labels[j] == 1]
        if not other_binders:
            scores.append(None)
            continue
        centroid = _l2norm(np.mean(np.stack(other_binders), axis=0))
        scores.append(float(np.dot(embs[i], centroid)))
    return scores


def loo_knn_scores(embs, labels, k=3):
    """Cross-check probe: LOO cosine k-NN. score_i = mean cosine to its k nearest
    BINDER neighbours minus mean cosine to its k nearest DECOY neighbours (LOO)."""
    embs = [_l2norm(e) for e in embs]
    labels = list(labels)
    scores = []
    for i in range(len(embs)):
        sims_b, sims_d = [], []
        for j in range(len(embs)):
            if j == i:
                continue
            s = float(np.dot(embs[i], embs[j]))
            (sims_b if labels[j] == 1 else sims_d).append(s)
        sims_b.sort(reverse=True)
        sims_d.sort(reverse=True)
        if not sims_b or not sims_d:
            scores.append(None)
            continue
        mb = float(np.mean(sims_b[:k]))
        md = float(np.mean(sims_d[:k]))
        scores.append(mb - md)
    return scores


def _run(cmd, log_path, timeout_s, cwd=None, env=None):
    """Run a subprocess, tee to log_path. Returns (rc, tail)."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as lf:
        try:
            rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                timeout=timeout_s, cwd=cwd, env=env).returncode
        except subprocess.TimeoutExpired:
            lf.write(f"\nTIMEOUT after {timeout_s}s\n")
            rc = 124
        except FileNotFoundError as e:
            lf.write(f"\nNOT_FOUND: {e}\n")
            rc = 127
    tail = log_path.read_text()[-3000:] if log_path.exists() else ""
    return rc, tail


# --------------------------------------------------------------------- receptor prep
def download_receptor(dst: Path) -> bool:
    """Download the receptor PDB from RCSB (urllib; no extra deps)."""
    import urllib.request

    try:
        urllib.request.urlretrieve(RCSB_URL, str(dst))
        return dst.exists() and dst.stat().st_size > 1000
    except Exception as e:
        print(f"[receptor] download failed: {e}", flush=True)
        return False


def split_receptor(raw_pdb: Path, receptor_pdb: Path, ref_pdb: Path):
    """From the raw RCSB PDB:
      - receptor_pdb : ATOM records of the kept polymer chain (waters/lipids/sugar/
          ions and the reference ligand REMOVED) — the docking target.
      - ref_pdb      : HETATM records of the reference ligand (REF_LIG_CODE) on the
          kept chain — the smina --autobox_ligand reference (defines the box).
    Returns (n_protein_atoms, n_ref_atoms, protein_seq_str)."""
    prot_lines, ref_lines = [], []
    seq_by_resi = {}  # resseq -> one-letter (first model only; protein chain)
    n_prot = n_ref = 0
    in_model = True  # only count the first MODEL if MODEL/ENDMDL present
    for line in raw_pdb.read_text().splitlines():
        rec = line[:6].strip()
        if rec == "MODEL":
            # if a second model starts, stop accepting atoms
            try:
                mid = int(line[10:14])
            except ValueError:
                mid = 1
            in_model = (mid == 1)
            continue
        if rec == "ENDMDL":
            in_model = False
            continue
        if rec not in ("ATOM", "HETATM"):
            continue
        if not in_model:
            continue
        chain = line[21:22]
        resname = line[17:20].strip()
        if rec == "ATOM" and chain == KEEP_CHAIN and resname in _THREE_TO_ONE:
            prot_lines.append(line)
            n_prot += 1
            try:
                resseq = int(line[22:26])
            except ValueError:
                resseq = None
            if resseq is not None and resseq not in seq_by_resi:
                seq_by_resi[resseq] = _THREE_TO_ONE[resname]
        elif rec == "HETATM" and resname == REF_LIG_CODE and chain == KEEP_CHAIN:
            ref_lines.append(line)
            n_ref += 1
        # everything else (waters, lipids, glycans, ions, other chains) dropped
    receptor_pdb.write_text("\n".join(prot_lines) + "\nEND\n")
    ref_pdb.write_text("\n".join(ref_lines) + "\nEND\n")
    seq = "".join(seq_by_resi[k] for k in sorted(seq_by_resi))
    return n_prot, n_ref, seq


def prepare_receptor_pdbqt(receptor_pdb: Path, receptor_pdbqt: Path) -> bool:
    """Add hydrogens + write a rigid-receptor PDBQT with obabel."""
    rc, _ = _run(
        [OBABEL_BIN, str(receptor_pdb), "-O", str(receptor_pdbqt),
         "-xr", "-h", "-p", "7.4"],
        WORK / "obabel_receptor.log", PREP_TIMEOUT_S,
    )
    return rc == 0 and receptor_pdbqt.exists() and receptor_pdbqt.stat().st_size > 100


# ----------------------------------------------------------------------- ligand prep
def prepare_ligand_pdbqt(smi: str, lig_pdbqt: Path, tag: str) -> bool:
    """SMILES -> 3D (gen3d) -> add H at pH 7.4 -> PDBQT, via obabel."""
    rc, _ = _run(
        [OBABEL_BIN, f"-:{smi}", "-O", str(lig_pdbqt),
         "--gen3d", "-h", "-p", "7.4"],
        WORK / f"obabel_lig_{tag}.log", PREP_TIMEOUT_S,
    )
    return rc == 0 and lig_pdbqt.exists() and lig_pdbqt.stat().st_size > 50


# ----------------------------------------------------------------------------- dock
def smina_dock(receptor_pdbqt: Path, lig_pdbqt: Path, ref_pdb: Path,
               out_pose: Path, tag: str):
    """Dock one ligand into the autobox around the reference ligand. Returns
    (rc, best_affinity_or_None, tail)."""
    cmd = [
        SMINA_BIN,
        "--receptor", str(receptor_pdbqt),
        "--ligand", str(lig_pdbqt),
        "--autobox_ligand", str(ref_pdb),
        "--autobox_add", SMINA_AUTOBOX_ADD,
        "--exhaustiveness", SMINA_EXHAUSTIVENESS,
        "--num_modes", "9",
        "--out", str(out_pose),
        "--cpu", os.environ.get("SMINA_CPU", "4"),
        "--seed", "42",
    ]
    log = WORK / f"smina_{tag}.log"
    rc, tail = _run(cmd, log, DOCK_TIMEOUT_S)
    aff = parse_smina_affinity(tail)
    return rc, aff, tail


def parse_smina_affinity(log_text: str):
    """Parse the best (mode 1) affinity (kcal/mol) from smina stdout. The results
    table looks like:
        mode |   affinity | dist from best mode
             | (kcal/mol) | rmsd l.b.| rmsd u.b.
        -----+------------+----------+----------
           1       -7.8        0.000      0.000
    We take the first data row's affinity (most negative / best)."""
    best = None
    for line in log_text.splitlines():
        m = re.match(r"\s*(\d+)\s+(-?\d+\.\d+)\s+", line)
        if m:
            try:
                aff = float(m.group(2))
            except ValueError:
                continue
            if best is None or aff < best:  # most negative is best
                best = aff
    return best


# --------------------------------------------------------------------- build complex
def pose_to_pdb(pose_pdbqt: Path, pose_pdb: Path, tag: str) -> bool:
    """Convert the top docked pose (first model of the PDBQT) to PDB with obabel.
    obabel emits all modes; we take the first model only downstream."""
    rc, _ = _run(
        [OBABEL_BIN, str(pose_pdbqt), "-O", str(pose_pdb), "-f", "1", "-l", "1"],
        WORK / f"obabel_pose_{tag}.log", PREP_TIMEOUT_S,
    )
    return rc == 0 and pose_pdb.exists() and pose_pdb.stat().st_size > 50


def build_complex(receptor_pdb: Path, pose_pdb: Path, complex_pdb: Path,
                  lig_resname: str = "LIG"):
    """Merge receptor (chain A, ATOM) + ligand pose (chain B, HETATM). The ligand
    atoms from obabel come as HETATM/ATOM with assorted resnames; we FORCE chain B
    + a single ligand residue (resname `lig_resname`, resi 1) so the downstream
    ligand discovery is unambiguous. Returns the complex path or None."""
    out = []
    # receptor: keep its ATOM records, force chain A
    for line in receptor_pdb.read_text().splitlines():
        if line[:6].strip() in ("ATOM", "HETATM"):
            line = line[:21] + KEEP_CHAIN + line[22:]
            out.append(line)
    out.append("TER")
    # ligand pose: first model only, force HETATM + chain B + resname + resi 1
    started = False
    for line in pose_pdb.read_text().splitlines():
        rec = line[:6].strip()
        if rec == "ENDMDL" and started:
            break
        if rec in ("ATOM", "HETATM"):
            started = True
            atom = "HETATM" + line[6:]
            atom = atom[:17] + f"{lig_resname:>3}" + " " + "B" + "   1" + atom[26:]
            out.append(atom)
    out.append("TER")
    out.append("END")
    complex_pdb.write_text("\n".join(out) + "\n")
    return complex_pdb if complex_pdb.exists() else None


def discover_ligand(pdb_path: Path, lig_chain: str = "B"):
    """Read back the ligand residue NAME + residue NUMBER from chain B's HETATM/ATOM
    records (we do NOT hardcode the name even though build_complex sets it). Returns
    (lig_code, lig_resi) or (None, None)."""
    lig_code, lig_resi = None, None
    try:
        for line in pdb_path.read_text().splitlines():
            rec = line[:6].strip()
            if rec not in ("ATOM", "HETATM"):
                continue
            chain = line[21:22].strip()
            if chain != lig_chain:
                continue
            resname = line[17:20].strip()
            try:
                resseq = int(line[22:26])
            except ValueError:
                resseq = None
            if rec == "HETATM" or lig_code is None:
                lig_code, lig_resi = resname, resseq
                if rec == "HETATM":
                    break
    except Exception:
        return None, None
    return lig_code, lig_resi


# ----------------------------------------------------------------------- atomica embed
def run_atomica_embed(csv_path: Path, processed_path: Path, emb_path: Path):
    """Two-step ATOMICA call in its OWN interpreter. Returns (ok, note)."""
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc_log = csv_path.parent / "atomica_process.log"
    emb_log = csv_path.parent / "atomica_embed.log"

    proc_cmd = [
        ATOMICA_PY, "-m", "atomica.data.process_pdbs",
        "--data_index_file", str(csv_path),
        "--out_path", str(processed_path),
    ]
    try:
        with open(proc_log, "w") as lf:
            rc = subprocess.run(proc_cmd, stdout=lf, stderr=subprocess.STDOUT,
                                cwd=str(ATOMICA_DIR), env=env,
                                timeout=ATOMICA_EMBED_TIMEOUT_S).returncode
    except subprocess.TimeoutExpired:
        return False, "process_pdbs_timeout"
    except FileNotFoundError as e:
        return False, f"atomica_py_not_found:{e}"
    if rc != 0 or not processed_path.exists():
        tail = proc_log.read_text()[-600:] if proc_log.exists() else ""
        return False, f"process_pdbs_rc={rc}; {tail}"

    emb_cmd = [
        ATOMICA_PY, "-m", "atomica.get_embeddings",
        "--model_config", ATOMICA_MODEL_CONFIG,
        "--model_weights", ATOMICA_MODEL_WEIGHTS,
        "--data_path", str(processed_path),
        "--output_path", str(emb_path),
        "--batch_size", "1",
    ]
    try:
        with open(emb_log, "w") as lf:
            rc = subprocess.run(emb_cmd, stdout=lf, stderr=subprocess.STDOUT,
                                cwd=str(ATOMICA_DIR), env=env,
                                timeout=ATOMICA_EMBED_TIMEOUT_S).returncode
    except subprocess.TimeoutExpired:
        return False, "get_embeddings_timeout"
    if rc != 0 or not emb_path.exists():
        tail = emb_log.read_text()[-600:] if emb_log.exists() else ""
        return False, f"get_embeddings_rc={rc}; {tail}"
    return True, "ok"


def load_graph_embeddings(emb_path: Path) -> dict:
    """Map ATOMICA's id -> graph_embedding (interface-level vector). Default parquet;
    the .pkl branch reads ATOMICA's OWN self-generated output (trusted)."""
    import pickle

    out = {}
    if emb_path.suffix == ".parquet":
        import pandas as pd

        df = pd.read_parquet(emb_path)
        for _, row in df.iterrows():
            out[str(row["id"])] = np.asarray(row["graph_embedding"], dtype=np.float64).reshape(-1)
    else:
        with open(emb_path, "rb") as f:
            recs = pickle.load(f)
        for r in recs:
            out[str(r["id"])] = np.asarray(r["graph_embedding"], dtype=np.float64).reshape(-1)
    return out


def _atomic_write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ------------------------------------------------------------------------------ main
def main() -> int:
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)

    panel = json.loads(PANEL_PATH.read_text())[PANEL_KEY]
    compounds = panel["compounds"]

    skipped = []     # {drug, label, stage, reason}
    rows = []        # one per compound that produced an embedding
    csv_rows = []    # data_index_file rows for ATOMICA
    pdb_by_id = {}   # atomica_id -> info, to map embeddings back

    # ---- stage 0: receptor prep (FATAL if it fails — there is nothing to dock into) ----
    raw_pdb = WORK / f"{PDB_ID}.pdb"
    if not download_receptor(raw_pdb):
        _atomic_write(OUT, {"track": "structural interaction embedding (ATOMICA, docked)",
                            "target": panel.get("target"),
                            "error": f"receptor_download_failed:{PDB_ID}",
                            "wall_time_sec": round(time.time() - t0, 1)})
        print(f"FATAL: could not download receptor {PDB_ID}", flush=True)
        return 1

    receptor_pdb = WORK / "receptor.pdb"
    ref_pdb = WORK / "ref_ligand.pdb"
    n_prot, n_ref, rec_seq = split_receptor(raw_pdb, receptor_pdb, ref_pdb)
    print(f"[receptor] {PDB_ID} chain {KEEP_CHAIN}: {n_prot} protein atoms, "
          f"{n_ref} ref-ligand({REF_LIG_CODE}) atoms, seq_len={len(rec_seq)}", flush=True)
    if n_prot < 100 or n_ref < 5:
        _atomic_write(OUT, {"track": "structural interaction embedding (ATOMICA, docked)",
                            "target": panel.get("target"),
                            "error": f"receptor_split_bad: n_prot={n_prot} n_ref={n_ref}",
                            "wall_time_sec": round(time.time() - t0, 1)})
        print("FATAL: receptor split produced too few atoms", flush=True)
        return 1

    receptor_pdbqt = WORK / "receptor.pdbqt"
    if not prepare_receptor_pdbqt(receptor_pdb, receptor_pdbqt):
        _atomic_write(OUT, {"track": "structural interaction embedding (ATOMICA, docked)",
                            "target": panel.get("target"),
                            "error": "receptor_pdbqt_prep_failed",
                            "wall_time_sec": round(time.time() - t0, 1)})
        print("FATAL: obabel receptor->pdbqt failed", flush=True)
        return 1

    # ---- stage 1-3: per compound dock + build complex ----
    smina_by_drug = {}
    for i, comp in enumerate(compounds):
        drug = comp["drug"]
        smi = comp["smiles"]
        label = comp["label"]
        tag = "".join(ch if ch.isalnum() else "_" for ch in drug)

        lig_pdbqt = WORK / f"lig_{tag}.pdbqt"
        if not prepare_ligand_pdbqt(smi, lig_pdbqt, tag):
            skipped.append({"drug": drug, "label": label, "stage": "ligand_prep",
                            "reason": "obabel_smiles_to_pdbqt_failed"})
            print(f"[dock {i+1}/{len(compounds)}] {drug}: ligand prep FAIL", flush=True)
            continue

        pose_pdbqt = WORK / f"pose_{tag}.pdbqt"
        rc, aff, tail = smina_dock(receptor_pdbqt, lig_pdbqt, ref_pdb, pose_pdbqt, tag)
        if rc != 0 or not pose_pdbqt.exists() or aff is None:
            skipped.append({"drug": drug, "label": label, "stage": "dock",
                            "reason": f"smina_rc={rc}_aff={aff}", "err_tail": tail[-300:]})
            print(f"[dock {i+1}/{len(compounds)}] {drug}: dock FAIL rc={rc} aff={aff}", flush=True)
            continue
        smina_by_drug[drug] = aff

        pose_pdb = WORK / f"pose_{tag}.pdb"
        if not pose_to_pdb(pose_pdbqt, pose_pdb, tag):
            skipped.append({"drug": drug, "label": label, "stage": "pose_convert",
                            "reason": "obabel_pose_to_pdb_failed", "smina_score": aff})
            print(f"[dock {i+1}/{len(compounds)}] {drug}: pose->pdb FAIL", flush=True)
            continue

        complex_pdb = WORK / f"complex_{tag}.pdb"
        if build_complex(receptor_pdb, pose_pdb, complex_pdb, lig_resname="LIG") is None:
            skipped.append({"drug": drug, "label": label, "stage": "build_complex",
                            "reason": "merge_failed", "smina_score": aff})
            print(f"[dock {i+1}/{len(compounds)}] {drug}: build complex FAIL", flush=True)
            continue

        lig_code, lig_resi = discover_ligand(complex_pdb, lig_chain="B")
        if not lig_code:
            skipped.append({"drug": drug, "label": label, "stage": "ligand_parse",
                            "reason": "no_chainB_ligand_in_complex", "smina_score": aff})
            print(f"[dock {i+1}/{len(compounds)}] {drug}: no chain-B ligand", flush=True)
            continue

        atom_id = f"{tag}_A_B_{lig_code}"  # mirrors process_pdbs id construction
        csv_rows.append({
            "pdb_id": tag, "pdb_path": str(complex_pdb),
            "chain1": KEEP_CHAIN, "chain2": "B",
            "lig_code": lig_code, "lig_smiles": smi,
            "lig_resi": "" if lig_resi is None else lig_resi,
        })
        pdb_by_id[atom_id] = {"drug": drug, "label": label, "pdb_id": tag,
                              "lig_code": lig_code, "lig_resi": lig_resi,
                              "smina_score": aff}
        print(f"[dock {i+1}/{len(compounds)}] {drug}: ok aff={aff} lig={lig_code}/{lig_resi}",
              flush=True)
        _atomic_write(OUT, {"status": "docking", "done": i + 1, "total": len(compounds),
                            "skipped": skipped})

    if not csv_rows:
        _atomic_write(OUT, {"track": "structural interaction embedding (ATOMICA, docked)",
                            "target": panel.get("target"), "error": "no_complexes_docked",
                            "receptor_pdb": PDB_ID, "skipped": skipped,
                            "wall_time_sec": round(time.time() - t0, 1)})
        print("FATAL: no complexes docked", flush=True)
        return 1

    # ---- stage 4: ATOMICA embed (its own env) ----
    csv_path = WORK / "atomica_inputs.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pdb_id", "pdb_path", "chain1", "chain2",
                                          "lig_code", "lig_smiles", "lig_resi"])
        w.writeheader()
        w.writerows(csv_rows)

    processed_path = WORK / "atomica_processed.parquet"
    emb_path = WORK / "atomica_embeddings.parquet"  # parquet avoids pickle deserialization
    ok, note = run_atomica_embed(csv_path, processed_path, emb_path)
    if not ok:
        _atomic_write(OUT, {"track": "structural interaction embedding (ATOMICA, docked)",
                            "target": panel.get("target"),
                            "error": f"atomica_embed_failed: {note}",
                            "receptor_pdb": PDB_ID, "n_docked": len(csv_rows),
                            "smina_by_drug": smina_by_drug, "skipped": skipped,
                            "wall_time_sec": round(time.time() - t0, 1)})
        print(f"FATAL: ATOMICA embed failed: {note}", flush=True)
        return 1

    id2emb = load_graph_embeddings(emb_path)

    # ---- map embeddings back to compounds (ATOMICA may skip empty interfaces) ----
    for atom_id, info in pdb_by_id.items():
        emb = id2emb.get(atom_id)
        if emb is None:
            cand = [k for k in id2emb if k.startswith(info["pdb_id"] + "_")]
            emb = id2emb[cand[0]] if cand else None
        if emb is None:
            skipped.append({"drug": info["drug"], "label": info["label"],
                            "stage": "embed", "reason": "no_embedding_for_id",
                            "atomica_id": atom_id, "smina_score": info["smina_score"]})
            continue
        rows.append({"drug": info["drug"], "label": info["label"],
                     "smina_score": info["smina_score"],
                     "atomica_id": atom_id, "emb": emb,
                     "emb_dim": int(emb.shape[0]),
                     "lig_code": info["lig_code"], "lig_resi": info["lig_resi"]})

    # ---- stage 5: metrics ----
    n_bind = sum(1 for r in rows if r["label"] == 1)
    n_decoy = sum(1 for r in rows if r["label"] == 0)
    labels = [r["label"] for r in rows]
    embs = [r["emb"] for r in rows]

    centroid_scores = loo_centroid_scores(embs, labels) if rows else []
    knn_scores = loo_knn_scores(embs, labels) if rows else []
    # smina: more negative affinity = stronger binder -> negate so higher = binder-like.
    smina_scores = [(-r["smina_score"] if r["smina_score"] is not None else None) for r in rows]

    atomica_auroc = auroc(labels, centroid_scores) if rows else None
    atomica_knn_auroc = auroc(labels, knn_scores) if rows else None
    smina_auroc = auroc(labels, smina_scores) if rows else None

    out_rows = []
    for r, cs, ks in zip(rows, centroid_scores, knn_scores):
        out_rows.append({
            "name": r["drug"], "label": r["label"],
            "smina_score": r["smina_score"],
            "atomica_score": (round(cs, 6) if cs is not None else None),
            "atomica_knn_score": (round(ks, 6) if ks is not None else None),
            "emb_dim": r["emb_dim"], "lig_code": r["lig_code"], "lig_resi": r["lig_resi"],
        })
    out_rows.sort(key=lambda x: (x["atomica_score"] is None, -(x["atomica_score"] or 0)))

    payload = {
        "track": "structural interaction embedding (ATOMICA, docked) — CANDIDATE NEW CAPABILITY",
        "model": "ATOMICA pretrained (ada-f/ATOMICA, geometric interaction model)",
        "pose_source": "smina (AutoDock-Vina) docking into a real cryo-EM receptor (NO Boltz)",
        "receptor_pdb": PDB_ID,
        "receptor_desc": "Human Nav1.8 (SCN10A) cryo-EM, A-803467/95T bound, chain A, 1956 aa",
        "dock_box": (f"smina --autobox_ligand around bound blocker {REF_LIG_CODE} "
                     f"(A-803467, central pore site); autobox_add={SMINA_AUTOBOX_ADD} A"),
        "target": panel.get("target"), "panel_key": PANEL_KEY,
        "question": ("Does ATOMICA's interface embedding carry CNS binder signal "
                     "BEYOND the raw docking score?"),
        "atomica_auroc": atomica_auroc,
        "atomica_probe": "leave-one-out cosine-to-binder-centroid on graph_embedding",
        "atomica_knn_auroc": atomica_knn_auroc,
        "atomica_knn_probe": "leave-one-out cosine kNN (k=3) binder-minus-decoy",
        "smina_auroc": smina_auroc,
        "smina_readout": "AUROC of -(best smina affinity, kcal/mol) = docking-score baseline to beat",
        "n": len(rows), "n_binders": n_bind, "n_decoys": n_decoy,
        "n_compounds_in_panel": len(compounds),
        "complexes": out_rows,
        "skipped": skipped,
        "caveats": [
            "n is small (~11 compounds); AUROC has wide CIs at this n.",
            "Poses are PREDICTED (smina/Vina docking into one cryo-EM receptor), not "
            "experimental complexes; ATOMICA was trained on experimental PDB/CSD interfaces.",
            f"All ligands docked into a SINGLE site (the {REF_LIG_CODE}/A-803467 central-pore "
            "blocker pocket of 7WFR). Nav1.8 has MULTIPLE drug sites — the central pore (local "
            "anesthetics / A-803467) vs the VSD-II fenestration (suzetrigine). Forcing every "
            "compound into the pore is a DIRECTIONAL first look, not a site-aware prediction; "
            "drugs that bind elsewhere may be mis-posed.",
            "Single target (Nav1.8, 1956 aa); not a multi-target generalisation claim.",
            "ATOMICA graph_embedding is unsupervised here (no binder head); the LOO "
            "centroid/kNN probes are label-light proximity readouts, not a trained classifier.",
            "Rigid-receptor docking (no induced fit); receptor protonation via obabel pH 7.4.",
        ],
        "wall_time_sec": round(time.time() - t0, 1),
    }
    _atomic_write(OUT, payload)
    print(json.dumps({"atomica_auroc": atomica_auroc,
                      "atomica_knn_auroc": atomica_knn_auroc,
                      "smina_auroc": smina_auroc,
                      "n": len(rows), "n_binders": n_bind, "n_decoys": n_decoy,
                      "n_skipped": len(skipped)}, indent=2), flush=True)
    print(f"[done] wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
