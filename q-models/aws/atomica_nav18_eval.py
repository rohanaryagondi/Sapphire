"""ATOMICA Nav1.8 binder-vs-decoy eval (on-instance, g5.xlarge / A10G 24GB).

CANDIDATE NEW CAPABILITY TRACK: "structural interaction embedding". This does NOT
fit the existing seq-DTI / cross-modal / KG tracks — ATOMICA is a geometric model of
*intermolecular interaction interfaces*. The decisive question:

    Does ATOMICA's interface embedding carry CNS binder signal BEYOND Boltz-2's own
    affinity readout?  (i.e. is the structural-interaction embedding additive?)

PIPELINE (two isolated envs; structures handed off as files):
  1. Boltz-2 co-fold  : Nav1.8 (Q9Y5Y9, 1956 aa) + each ligand SMILES -> predicted
       protein-ligand complex. We invoke Boltz with --output_format pdb so the
       complex lands as a PDB directly (ATOMICA's process_pdbs also accepts .cif,
       but PDB sidesteps a separate CIF->PDB step). Reuses the PROVEN Boltz stack
       from aws/boltz_cns_userdata.sh (cuequivariance-torch + cuequivariance-ops-cu13).
  2. CIF/PDB handoff  : we discover the ligand's residue NAME + residue NUMBER in
       Boltz's chain B by scanning HETATM records — Boltz names SMILES ligands "LIG"
       in current releases, but we never hardcode it; we read it back from the file.
       If Boltz emitted only .cif we convert with gemmi (fallback: biotite).
  3. ATOMICA embed    : build the data_index_file CSV (pdb_id, pdb_path, chain1=A,
       chain2=B, lig_code, lig_smiles, lig_resi), run `python -m atomica.data.process_pdbs`
       then `python -m atomica.get_embeddings` IN ATOMICA'S OWN ENV (torch 2.1.1; must
       not collide with Boltz's torch). We shell out to $ATOMICA_PY so the two torch
       builds never share a process. We read the per-complex `graph_embedding`
       (the interface-level vector) from the embeddings parquet/pickle.
  4. Readout          :
       - atomica_auroc : binder-vs-decoy AUROC via LEAVE-ONE-OUT cosine-to-binder-
           centroid. For each held-out compound i, centroid = mean of the OTHER
           binders' L2-normalised graph embeddings; score_i = cosine(emb_i, centroid).
           Simplest defensible unsupervised probe that needs no labels for the held-out
           point and never leaks i into its own centroid. (We also report a LOO cosine
           k-NN score for cross-check.)
       - boltz_auroc   : AUROC of the panel's precomputed `boltz_prob_binder` on the
           SAME labels = the baseline ATOMICA must beat (or complement).
       - per-complex rows, n_binders/n_decoys, fold/embed failure notes.
       - honest caveats: n is small (~11), poses are PREDICTED not experimental,
           single target.

Robustness: a compound that fails to fold OR fails to embed is SKIPPED (recorded in
`skipped`), never fatal. Per-compound fold timeout (PAIR_TIMEOUT_S). Atomic result write.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------- env
PANEL_PATH = Path(os.environ.get("PANEL", "/opt/crossmodal_panels.json"))
PANEL_KEY = os.environ.get("PANEL_KEY", "nav18")
OUT = Path(os.environ.get("OUT", "/tmp/atomica_nav18_result.json"))
WORK = Path(os.environ.get("WORK", "/root/atomica_nav18_work"))

# Boltz (its OWN env / venv): we run `boltz` from PATH (the boltz venv is on PATH when
# the userdata activates it for this step). BOLTZ_CACHE/OUT are local disk.
BOLTZ_CACHE = os.environ.get("BOLTZ_CACHE", "/root/boltz_cache")
BOLTZ_OUT = Path(os.environ.get("BOLTZ_OUT", "/root/boltz_out"))
BOLTZ_BIN = os.environ.get("BOLTZ_BIN", "boltz")
PREFLIGHT_TIMEOUT_S = int(os.environ.get("PREFLIGHT_TIMEOUT_S", "3600"))  # cold weights+MSA
PAIR_TIMEOUT_S = int(os.environ.get("PAIR_TIMEOUT_S", "900"))            # 15 min/complex
SAMPLING_STEPS = os.environ.get("BOLTZ_SAMPLING_STEPS", "100")           # speed; struct only

# ATOMICA (its OWN env): we shell out to this interpreter so torch 2.1.1 never shares a
# process with Boltz's torch. ATOMICA_DIR is the cloned repo (cwd for the -m calls).
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


# ------------------------------------------------------------------------ boltz fold
def write_boltz_yaml(seq: str, smi: str, path: Path) -> None:
    try:
        import yaml  # type: ignore

        yaml.safe_dump(
            {
                "version": 1,
                "sequences": [
                    {"protein": {"id": "A", "sequence": seq}},
                    {"ligand": {"id": "B", "smiles": smi}},
                ],
            },
            open(path, "w"),
            sort_keys=False,
        )
    except ImportError:
        path.write_text(
            "version: 1\n"
            "sequences:\n"
            "  - protein:\n      id: A\n      sequence: %s\n"
            "  - ligand:\n      id: B\n      smiles: '%s'\n" % (seq, smi)
        )


def run_boltz(yml: Path, odir: Path, timeout_s: int):
    """Fold one complex -> PDB. Returns (rc, tail). We request PDB output directly so
    no CIF->PDB conversion is needed; we still keep a CIF fallback in find_structure."""
    cmd = [
        BOLTZ_BIN, "predict", str(yml),
        "--out_dir", str(odir),
        "--cache", BOLTZ_CACHE,
        "--use_msa_server",
        "--accelerator", "gpu", "--devices", "1",
        "--output_format", "pdb",
        "--sampling_steps", SAMPLING_STEPS,
        "--diffusion_samples", "1",
    ]
    log = odir / "boltz_run.log"
    odir.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as lf:
        try:
            rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                timeout=timeout_s).returncode
        except subprocess.TimeoutExpired:
            lf.write(f"\nTIMEOUT after {timeout_s}s\n")
            rc = 124
        except FileNotFoundError as e:
            lf.write(f"\nBOLTZ_NOT_FOUND: {e}\n")
            rc = 127
    return rc, (log.read_text()[-3000:] if log.exists() else "")


def find_structure(odir: Path):
    """Locate Boltz's top model. Prefer PDB; fall back to CIF (then convert)."""
    for pat in ("**/*_model_0.pdb", "**/predictions/**/*model_0*.pdb", "**/*.pdb"):
        hits = sorted(glob.glob(str(odir / pat), recursive=True))
        if hits:
            return Path(hits[0]), "pdb"
    for pat in ("**/*_model_0.cif", "**/predictions/**/*model_0*.cif", "**/*.cif"):
        hits = sorted(glob.glob(str(odir / pat), recursive=True))
        if hits:
            return Path(hits[0]), "cif"
    return None, None


def cif_to_pdb(cif_path: Path, pdb_path: Path) -> bool:
    """Convert CIF->PDB. gemmi first (most reliable for Boltz output), biotite fallback."""
    try:
        import gemmi  # type: ignore

        st = gemmi.read_structure(str(cif_path))
        st.setup_entities()
        st.write_pdb(str(pdb_path))
        return pdb_path.exists()
    except Exception:
        pass
    try:
        import biotite.structure.io.pdbx as pdbx  # type: ignore
        import biotite.structure.io.pdb as pdb  # type: ignore

        f = pdbx.CIFFile.read(str(cif_path))
        arr = pdbx.get_structure(f, model=1)
        out = pdb.PDBFile()
        out.set_structure(arr)
        out.write(str(pdb_path))
        return pdb_path.exists()
    except Exception:
        return False


def discover_ligand(pdb_path: Path, lig_chain: str = "B"):
    """Read back the ligand residue NAME + residue NUMBER from chain B's HETATM/ATOM
    records (we do NOT hardcode 'LIG'). Returns (lig_code, lig_resi) or (None, None)."""
    lig_code, lig_resi = None, None
    try:
        for line in pdb_path.read_text().splitlines():
            rec = line[:6].strip()
            if rec not in ("ATOM", "HETATM"):
                continue
            # PDB fixed columns: resName 18-20 (0-idx 17:20), chainID 22 (21), resSeq 23-26 (22:26)
            chain = line[21:22].strip()
            if chain != lig_chain:
                continue
            resname = line[17:20].strip()
            try:
                resseq = int(line[22:26])
            except ValueError:
                resseq = None
            # prefer HETATM (the small molecule) over any polymer atoms on the chain
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
        # fragmentation default None is fine; lig_smiles only used for fragmentation.
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
    """Map ATOMICA's id -> graph_embedding (interface-level vector).

    NOTE on pickle: the .pkl path here is ATOMICA's OWN embedding output, produced by
    get_embeddings on THIS instance moments earlier — it is a trusted, self-generated
    file, not third-party data. We default to .parquet anyway (see emb_path below)."""
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
    BOLTZ_OUT.mkdir(parents=True, exist_ok=True)

    panel = json.loads(PANEL_PATH.read_text())[PANEL_KEY]
    seq = panel["protein_seq"]
    compounds = panel["compounds"]

    rows = []        # one per compound that produced an embedding
    skipped = []     # {drug, label, stage, reason}
    csv_rows = []    # data_index_file rows for ATOMICA
    pdb_by_id = {}   # atomica_id -> info, to map embeddings back

    # ---- stage 1+2: fold each compound, get a PDB, discover ligand code/resi ----
    for i, comp in enumerate(compounds):
        drug = comp["drug"]
        smi = comp["smiles"]
        label = comp["label"]
        safe = "".join(ch if ch.isalnum() else "_" for ch in drug)
        odir = BOLTZ_OUT / safe
        yml = odir / "in.yaml"
        odir.mkdir(parents=True, exist_ok=True)
        write_boltz_yaml(seq, smi, yml)

        timeout_s = PREFLIGHT_TIMEOUT_S if i == 0 else PAIR_TIMEOUT_S
        rc, tail = run_boltz(yml, odir, timeout_s)
        if rc != 0:
            skipped.append({"drug": drug, "label": label, "stage": "fold",
                            "reason": f"boltz_rc={rc}", "err_tail": tail[-400:]})
            print(f"[fold {i+1}/{len(compounds)}] {drug}: FAIL rc={rc}", flush=True)
            continue

        struct, kind = find_structure(odir)
        if struct is None:
            skipped.append({"drug": drug, "label": label, "stage": "fold",
                            "reason": "no_structure_file"})
            print(f"[fold {i+1}/{len(compounds)}] {drug}: no structure file", flush=True)
            continue

        pdb_path = struct
        if kind == "cif":
            pdb_path = odir / f"{safe}_model_0.pdb"
            if not cif_to_pdb(struct, pdb_path):
                skipped.append({"drug": drug, "label": label, "stage": "convert",
                                "reason": "cif_to_pdb_failed"})
                print(f"[fold {i+1}/{len(compounds)}] {drug}: CIF->PDB failed", flush=True)
                continue

        lig_code, lig_resi = discover_ligand(pdb_path, lig_chain="B")
        if not lig_code:
            skipped.append({"drug": drug, "label": label, "stage": "ligand_parse",
                            "reason": "no_chainB_ligand_in_pdb"})
            print(f"[fold {i+1}/{len(compounds)}] {drug}: no chain-B ligand found", flush=True)
            continue

        atom_id = f"{safe}_A_B_{lig_code}"  # mirrors process_pdbs id construction
        csv_rows.append({
            "pdb_id": safe, "pdb_path": str(pdb_path),
            "chain1": "A", "chain2": "B",
            "lig_code": lig_code, "lig_smiles": smi,
            "lig_resi": "" if lig_resi is None else lig_resi,
        })
        pdb_by_id[atom_id] = {"drug": drug, "label": label, "pdb_id": safe,
                              "lig_code": lig_code, "lig_resi": lig_resi,
                              "boltz_prob_binder": comp.get("boltz_prob_binder")}
        print(f"[fold {i+1}/{len(compounds)}] {drug}: ok ({kind}) lig={lig_code}/{lig_resi}",
              flush=True)
        _atomic_write(OUT, {"status": "folding", "done": i + 1, "total": len(compounds),
                            "skipped": skipped})

    if not csv_rows:
        payload = {"track": "structural interaction embedding (ATOMICA)",
                   "target": panel.get("target"), "error": "no_complexes_folded",
                   "skipped": skipped, "wall_time_sec": round(time.time() - t0, 1)}
        _atomic_write(OUT, payload)
        print("FATAL: no complexes folded", flush=True)
        return 1

    # ---- stage 3: ATOMICA embed (its own env) ----
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
        payload = {"track": "structural interaction embedding (ATOMICA)",
                   "target": panel.get("target"),
                   "error": f"atomica_embed_failed: {note}",
                   "n_folded": len(csv_rows), "skipped": skipped,
                   "wall_time_sec": round(time.time() - t0, 1)}
        _atomic_write(OUT, payload)
        print(f"FATAL: ATOMICA embed failed: {note}", flush=True)
        return 1

    id2emb = load_graph_embeddings(emb_path)

    # ---- map embeddings back to compounds (ATOMICA may skip empty interfaces) ----
    for atom_id, info in pdb_by_id.items():
        emb = id2emb.get(atom_id)
        if emb is None:
            # tolerate id-suffix drift: match by pdb_id prefix
            cand = [k for k in id2emb if k.startswith(info["pdb_id"] + "_")]
            emb = id2emb[cand[0]] if cand else None
        if emb is None:
            skipped.append({"drug": info["drug"], "label": info["label"],
                            "stage": "embed", "reason": "no_embedding_for_id",
                            "atomica_id": atom_id})
            continue
        rows.append({"drug": info["drug"], "label": info["label"],
                     "boltz_prob_binder": info["boltz_prob_binder"],
                     "atomica_id": atom_id, "emb": emb,
                     "emb_dim": int(emb.shape[0]),
                     "lig_code": info["lig_code"], "lig_resi": info["lig_resi"]})

    # ---- stage 4: metrics ----
    n_bind = sum(1 for r in rows if r["label"] == 1)
    n_decoy = sum(1 for r in rows if r["label"] == 0)
    labels = [r["label"] for r in rows]
    embs = [r["emb"] for r in rows]

    centroid_scores = loo_centroid_scores(embs, labels) if rows else []
    knn_scores = loo_knn_scores(embs, labels) if rows else []
    boltz_scores = [r["boltz_prob_binder"] for r in rows]

    atomica_auroc = auroc(labels, centroid_scores) if rows else None
    atomica_knn_auroc = auroc(labels, knn_scores) if rows else None
    boltz_auroc = auroc(labels, boltz_scores) if rows else None

    out_rows = []
    for r, cs, ks in zip(rows, centroid_scores, knn_scores):
        out_rows.append({
            "name": r["drug"], "label": r["label"],
            "boltz_prob": r["boltz_prob_binder"],
            "atomica_score": (round(cs, 6) if cs is not None else None),
            "atomica_knn_score": (round(ks, 6) if ks is not None else None),
            "emb_dim": r["emb_dim"], "lig_code": r["lig_code"], "lig_resi": r["lig_resi"],
        })
    out_rows.sort(key=lambda x: (x["atomica_score"] is None, -(x["atomica_score"] or 0)))

    payload = {
        "track": "structural interaction embedding (ATOMICA) — CANDIDATE NEW CAPABILITY",
        "model": "ATOMICA pretrained (ada-f/ATOMICA, geometric interaction model)",
        "target": panel.get("target"), "panel_key": PANEL_KEY,
        "question": ("Does ATOMICA's interface embedding carry CNS binder signal "
                     "BEYOND Boltz-2's own affinity readout?"),
        "atomica_auroc": atomica_auroc,
        "atomica_probe": "leave-one-out cosine-to-binder-centroid on graph_embedding",
        "atomica_knn_auroc": atomica_knn_auroc,
        "atomica_knn_probe": "leave-one-out cosine kNN (k=3) binder-minus-decoy",
        "boltz_auroc": boltz_auroc,
        "boltz_readout": "panel precomputed boltz_prob_binder (baseline to beat)",
        "n": len(rows), "n_binders": n_bind, "n_decoys": n_decoy,
        "n_compounds_in_panel": len(compounds),
        "complexes": out_rows,
        "skipped": skipped,
        "caveats": [
            "n is small (~11 compounds); AUROC has wide CIs at this n.",
            "Poses are PREDICTED (Boltz-2 co-folds), not experimental structures; "
            "ATOMICA was trained on experimental PDB/CSD interfaces.",
            "Single target (Nav1.8, 1956 aa); not a multi-target generalisation claim.",
            "ATOMICA graph_embedding is unsupervised here (no binder head); the LOO "
            "centroid/kNN probes are label-light proximity readouts, not a trained classifier.",
            "Boltz baseline AUROC is computed from the panel's precomputed prob_binder, "
            "not re-folded in this run.",
        ],
        "wall_time_sec": round(time.time() - t0, 1),
    }
    _atomic_write(OUT, payload)
    print(json.dumps({"atomica_auroc": atomica_auroc,
                      "atomica_knn_auroc": atomica_knn_auroc,
                      "boltz_auroc": boltz_auroc,
                      "n": len(rows), "n_binders": n_bind, "n_decoys": n_decoy,
                      "n_skipped": len(skipped)}, indent=2), flush=True)
    print(f"[done] wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
