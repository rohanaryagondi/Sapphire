"""LigUnity on Track 2 (DTI / binder triage) — the 19-target CNS panel, head-to-head vs BALM/PLAPT.

WHY
===
Our Track-2 verdict is that off-the-shelf DTI is at CHANCE (~0.50) on CNS ion channels and
only good on kinases (~0.80) / mTOR (~0.72). The current sequence-based winners are BALM
(cosine) and PLAPT (affinity). LigUnity (Feng et al., Patterns 2025; IDEA-XL) is a
purpose-built *ranking* foundation model with a DIFFERENT inductive bias (Uni-Mol 3D molecule
encoder + a pocket/protein tower, contrastive rank-softmax). Question: does its ranking bias
beat BALM/PLAPT on the CNS panel, especially the ion channels that are at chance for everyone?

CHECKPOINT / PATH DETERMINATION  (STEP 0 — the key finding)
===========================================================
LigUnity ships three HF checkpoints. We dissected the repo inference code
(unimol/tasks/test_task.py::test_demo + unimol/models/{protein,pocket}_ranking.py) to find the
LEAST toolchain-heavy, pocket-FREE path:

  * fengb/LigUnity_pocket_ranking  -> pocket_forward() consumes pocket_src_tokens /
    pocket_src_distance / pocket_src_edge_type, i.e. a Uni-Mol 3D POCKET (atoms+coords). This is
    POSE/POCKET-GATED — the exact failure mode that sank DrugCLIP (results/drugclip_crossmodal.md)
    and AEV-PLIG (results/aev_plig_characterization.md) on Quiver's no-holo targets. NOT used as
    the primary path.

  * fengb/LigUnity_protein_ranking -> pocket_forward(self, protein_sequences, **kwargs) IGNORES
    the 3D pocket tensors entirely (they fall into **kwargs and are discarded) and encodes the
    protein PURELY from its amino-acid SEQUENCE via an ESM-2 (esm2_t12_35M_UR50D) tower
    (unimol/models/protein_ranking.py L60-61, L184-203). The ligand side is still a Uni-Mol 3D
    conformer (mol_forward). So the PROTEIN side is POCKET-FREE: sequence + ligand-SMILES, the
    same input class as BALM/PLAPT -> a clean, fair head-to-head. >>> THIS IS THE CHOSEN PATH. <<<

POSE-GATE NOTE (loud, per the DrugCLIP/AEV-PLIG playbook): even on the protein_ranking sequence
path, the repo's test_demo() still *loads* a pocket lmdb (load_pockets_dataset) to build the
batch — but the protein_ranking model never reads those tensors. We therefore DO NOT need a real
3D structure. We supply a small PLACEHOLDER pocket lmdb (a few dummy CA atoms) purely to satisfy
the dataloader's shape contract; the binding score is driven entirely by the UniProt sequence +
the ligand conformer. The score is the cosine between the (sequence) protein embedding and the
(Uni-Mol) ligand embedding (both L2-normalized in the model), higher = more likely binder.
If LigUnity_protein_ranking ever fails to load/score, we record the failure verbatim and DO NOT
silently fall back to the pose-gated pocket_ranking path.

HOW WE INVOKE THE REPO'S OWN CODE
=================================
We replicate the repo's exact featurization by calling its own dataloaders + model:
  - ligand: load_mols_dataset(mols.lmdb) -> AffinityMolDataset (RDKit-3D conformer, Uni-Mol tokens)
            -> model.mol_forward(**net_input)  (L2-normalized mol embedding)
  - protein: get_uniprot_seq is bypassed (we already hold the sequence from the panel build);
             we pass our sequence directly to model.pocket_forward(protein_sequences=seq, ...).
  - score = cosine(protein_emb, mol_emb) == dot product since both are unit-normalized.
This mirrors test_demo() but scores in-process (no saved_*.npy round-trip) so we get per-pair
AUROC on the same panel BALM/PLAPT were scored on.

PANEL + DATA  (copied verbatim from aws/cns_dti_benchmark_eval.py)
==================================================================
Same 19-target CNS panel (mtor_pathway / ion_channel / gpcr / kinase), same ChEMBL actives
(pchembl >= 6.0) + ChEMBL-inactive / DUD-E-style property-matched decoys, same rank-sum AUROC,
same per-target -> per-family aggregation. ADDITION vs the BALM/PLAPT script: a per-target
fail-fast socket timeout so an EBI/ChEMBL 500 or stall SKIPS the target instead of hanging the run.

Writes JSON to env OUT (default /root/ligunity_out/ligunity_result.json):
per-target + per-family AUROC, head-to-head vs the hard-coded BALM/PLAPT reference numbers,
and which checkpoint/path was used + whether it needed a pocket.
"""
from __future__ import annotations

import json
import os
import pickle
import shutil
import socket
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Toolchain / runtime knobs.
# ---------------------------------------------------------------------------
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/ligunity_out/ligunity_result.json"))
LIGUNITY_DIR = Path(os.environ.get("LIGUNITY_DIR", "/opt/LigUnity"))
CKPT = os.environ.get("LIGUNITY_CKPT", "/opt/ligunity_ckpt/protein_ranking/checkpoint.pt")
ARCH = os.environ.get("LIGUNITY_ARCH", "protein_ranking")   # the pocket-FREE sequence tower
ESM_MODEL = os.environ.get("LIGUNITY_ESM", "facebook/esm2_t12_35M_UR50D")  # patches repo abs-path
WORK = Path(os.environ.get("LIGUNITY_WORK", "/root/ligunity_work"))
MAX_POCKET_ATOMS = int(os.environ.get("MAX_POCKET_ATOMS", "256"))

# Per-target hard wall-clock budget for the ChEMBL/UniProt build (fail-fast, skip not hang).
TARGET_TIMEOUT_SEC = int(os.environ.get("TARGET_TIMEOUT_SEC", "240"))
# Global socket timeout so an EBI 500/stall raises instead of blocking forever.
socket.setdefaulttimeout(int(os.environ.get("SOCKET_TIMEOUT_SEC", "60")))

# Knobs (env-overridable) — IDENTICAL defaults to aws/cns_dti_benchmark_eval.py.
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "30"))
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "60"))
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))
RNG = np.random.default_rng(int(os.environ.get("SEED", "20260614")))

# ---------------------------------------------------------------------------
# CNS TARGET PANEL — copied verbatim from aws/cns_dti_benchmark_eval.py so LigUnity is
# scored on the SAME 19 targets across the SAME four families as BALM/PLAPT.
# Each entry: gene -> (uniprot_accession, fallback_chembl_id, family).
# Families: "ion_channel" | "mtor_pathway" | "gpcr" | "kinase".
# ---------------------------------------------------------------------------
PANEL = {
    # --- TSC2 / mTOR pathway ---
    "MTOR":    {"uniprot": "P42345", "chembl": "CHEMBL2842",    "family": "mtor_pathway"},
    "PKM":     {"uniprot": "P14618", "chembl": "CHEMBL2107",    "family": "mtor_pathway"},  # PKM2
    "PPARD":   {"uniprot": "Q03181", "chembl": "CHEMBL3979",    "family": "mtor_pathway"},
    "AKT1":    {"uniprot": "P31749", "chembl": "CHEMBL4282",    "family": "mtor_pathway"},
    "RHEB":    {"uniprot": "Q15382", "chembl": None,            "family": "mtor_pathway"},
    "RPS6KB1": {"uniprot": "P23443", "chembl": "CHEMBL4501",    "family": "mtor_pathway"},  # S6K1

    # --- Ion channels (epilepsy / pain / excitability) ---
    "SCN1A":   {"uniprot": "P35498", "chembl": "CHEMBL5277",    "family": "ion_channel"},   # Nav1.1
    "SCN2A":   {"uniprot": "Q99250", "chembl": "CHEMBL4076",    "family": "ion_channel"},   # Nav1.2
    "SCN8A":   {"uniprot": "Q9UQD0", "chembl": "CHEMBL4960",    "family": "ion_channel"},   # Nav1.6
    "SCN9A":   {"uniprot": "Q15858", "chembl": "CHEMBL4296",    "family": "ion_channel"},   # Nav1.7
    "SCN10A":  {"uniprot": "Q9Y5Y9", "chembl": "CHEMBL5451",    "family": "ion_channel"},   # Nav1.8
    "SCN5A":   {"uniprot": "Q14524", "chembl": "CHEMBL1980",    "family": "ion_channel"},   # Nav1.5 (cardiac ref)
    "CACNA1C": {"uniprot": "Q13936", "chembl": "CHEMBL1940",    "family": "ion_channel"},   # Cav1.2
    "KCNQ2":   {"uniprot": "O43526", "chembl": "CHEMBL4304",    "family": "ion_channel"},
    "GRIN1":   {"uniprot": "Q05586", "chembl": "CHEMBL1907594", "family": "ion_channel"},   # NMDA (NR1)
    "GRIN2B":  {"uniprot": "Q13224", "chembl": "CHEMBL1907600", "family": "ion_channel"},   # NMDA (NR2B)

    # --- CNS GPCRs ---
    "DRD2":    {"uniprot": "P14416", "chembl": "CHEMBL217",     "family": "gpcr"},
    "HTR2A":   {"uniprot": "P28223", "chembl": "CHEMBL224",     "family": "gpcr"},

    # --- Neurodegeneration kinases ---
    "GSK3B":   {"uniprot": "P49841", "chembl": "CHEMBL262",     "family": "kinase"},
    "LRRK2":   {"uniprot": "Q5S007", "chembl": "CHEMBL1075104", "family": "kinase"},
    "BACE1":   {"uniprot": "P56817", "chembl": "CHEMBL4822",    "family": "kinase"},        # protease, kept w/ kinases
}

BINDING_TYPES = ["IC50", "Ki", "Kd"]

# Hard-coded reference numbers for the head-to-head (from aws/cns_dti_benchmark + memory).
# Per-FAMILY mean AUROC for the two current sequence-based Track-2 winners.
BASELINE_FAMILY_MEAN = {
    "BALM":  {"kinase": 0.80, "mtor_pathway": 0.72, "gpcr": 0.58, "ion_channel": 0.50},
    "PLAPT": {"kinase": 0.77, "mtor_pathway": 0.74, "gpcr": 0.66, "ion_channel": 0.50},
}


# ---------------------------------------------------------------------------
# AUROC (rank-sum; ties get average rank). Higher score => label 1 (binder).
# Reused verbatim from aws/cns_dti_benchmark_eval.py.
# ---------------------------------------------------------------------------
def auroc(labels, scores):
    labels = np.asarray(labels, dtype=float)
    scores = np.asarray(scores, dtype=float)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        ranks[order[i:j + 1]] = avg
        i = j + 1
    rank_pos = ranks[labels == 1].sum()
    n_pos, n_neg = len(pos), len(neg)
    return float((rank_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


# ---------------------------------------------------------------------------
# Per-target wall-clock guard (signal.alarm) so an EBI/ChEMBL stall SKIPS not hangs.
# ---------------------------------------------------------------------------
class _Timeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _Timeout()


def with_timeout(seconds, fn, *args, **kwargs):
    """Run fn under a SIGALRM wall-clock budget (main thread only)."""
    import signal
    old = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(int(seconds))
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------------------
# UniProt WT-sequence fetch (pattern from aws/cns_dti_benchmark_eval.py).
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "ligunity-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL data access via chembl_webresource_client (verbatim from cns_dti_benchmark_eval).
# ---------------------------------------------------------------------------
def resolve_chembl_id(meta):
    from chembl_webresource_client.new_client import new_client
    acc = meta["uniprot"]
    try:
        hits = list(new_client.target.filter(
            target_components__accession=acc,
            target_type="SINGLE PROTEIN",
            organism="Homo sapiens",
        ).only(["target_chembl_id", "target_type", "organism", "pref_name"]))
        for h in hits:
            tid = h.get("target_chembl_id")
            if tid:
                return tid, "resolved_by_uniprot_accession"
    except Exception as e:
        print(f"[warn] ChEMBL target resolve failed for {acc}: {e}", flush=True)
    if meta.get("chembl"):
        return meta["chembl"], "hardcoded_fallback"
    return None, None


def fetch_activities(chembl_id):
    from chembl_webresource_client.new_client import new_client
    qs = new_client.activity.filter(
        target_chembl_id=chembl_id,
        standard_type__in=BINDING_TYPES,
        pchembl_value__isnull=False,
    ).only(["canonical_smiles", "pchembl_value", "standard_type"])
    best = {}
    for a in qs:
        smi = a.get("canonical_smiles")
        pv = a.get("pchembl_value")
        if not smi or pv is None:
            continue
        try:
            pv = float(pv)
        except (TypeError, ValueError):
            continue
        if smi not in best or pv > best[smi]:
            best[smi] = pv
    return best


# ---------------------------------------------------------------------------
# RDKit property helpers for DUD-E-style property-matched decoys (verbatim).
# ---------------------------------------------------------------------------
def mol_props(smi):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return {
        "mw": Descriptors.MolWt(m),
        "logp": Descriptors.MolLogP(m),
        "hbd": Lipinski.NumHDonors(m),
        "hba": Lipinski.NumHAcceptors(m),
    }


def morgan_fp(smi):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048)


def property_matched_decoys(active_smiles, active_props, candidate_pool, n_needed):
    from rdkit import DataStructs
    if not active_props:
        return []
    mw = np.array([p["mw"] for p in active_props])
    logp = np.array([p["logp"] for p in active_props])
    hbd = np.array([p["hbd"] for p in active_props])
    hba = np.array([p["hba"] for p in active_props])
    env = {
        "mw": (mw.mean(), max(mw.std(), 50.0) * 1.5),
        "logp": (logp.mean(), max(logp.std(), 1.0) * 1.5),
        "hbd": (hbd.mean(), max(hbd.std(), 1.0) * 2.0),
        "hba": (hba.mean(), max(hba.std(), 1.0) * 2.0),
    }
    active_fps = [fp for fp in (morgan_fp(s) for s in active_smiles) if fp is not None]
    picked = []
    pool = list(candidate_pool)
    RNG.shuffle(pool)
    for smi in pool:
        if smi in active_smiles:
            continue
        p = mol_props(smi)
        if p is None:
            continue
        if abs(p["mw"] - env["mw"][0]) > env["mw"][1]:
            continue
        if abs(p["logp"] - env["logp"][0]) > env["logp"][1]:
            continue
        if abs(p["hbd"] - env["hbd"][0]) > env["hbd"][1]:
            continue
        if abs(p["hba"] - env["hba"][0]) > env["hba"][1]:
            continue
        fp = morgan_fp(smi)
        if fp is None:
            continue
        if active_fps:
            sims = DataStructs.BulkTanimotoSimilarity(fp, active_fps)
            if max(sims) >= DECOY_TANIMOTO_MAX:
                continue
        picked.append(smi)
        if len(picked) >= n_needed:
            break
    return picked


# ---------------------------------------------------------------------------
# Build per-target {actives, decoys, seq} sets. Mirrors cns_dti_benchmark_eval.build_panels
# but wraps the per-target ChEMBL/UniProt work in a SIGALRM budget (fail-fast skip).
# ---------------------------------------------------------------------------
def _fetch_one_target(gene, meta):
    cid, src = resolve_chembl_id(meta)
    if not cid:
        return ("dropped", "no ChEMBL target id (resolve + fallback both empty)")
    best = fetch_activities(cid)
    actives = {s: v for s, v in best.items() if v >= ACTIVE_PCHEMBL}
    inactives = {s: v for s, v in best.items() if v <= INACTIVE_PCHEMBL}
    if len(actives) > MAX_ACTIVES:
        top = sorted(actives.items(), key=lambda kv: -kv[1])[:MAX_ACTIVES]
        actives = dict(top)
    return ("ok", {"chembl_id": cid, "chembl_id_source": src,
                   "actives": actives, "inactives": inactives})


def build_panels():
    built, dropped, raw_actives, raw_inactives = {}, {}, {}, {}

    # Pass 1: resolve ids + fetch activities under a per-target wall-clock budget.
    for gene, meta in PANEL.items():
        try:
            status, payload = with_timeout(TARGET_TIMEOUT_SEC, _fetch_one_target, gene, meta)
            if status == "dropped":
                dropped[gene] = payload
                continue
            actives, inactives = payload["actives"], payload["inactives"]
            raw_actives[gene] = actives
            raw_inactives[gene] = inactives
            built[gene] = {"chembl_id": payload["chembl_id"],
                           "chembl_id_source": payload["chembl_id_source"],
                           "family": meta["family"], "uniprot": meta["uniprot"],
                           "n_actives_pre_drop": len(actives),
                           "n_chembl_inactives": len(inactives)}
            print(f"[chembl] {gene} ({payload['chembl_id']}, {payload['chembl_id_source']}): "
                  f"{len(actives)} actives / {len(inactives)} inactives", flush=True)
        except _Timeout:
            dropped[gene] = f"TIMEOUT (>{TARGET_TIMEOUT_SEC}s ChEMBL/UniProt build) — skipped"
            print(f"[warn] {gene} timed out -> skipped", flush=True)
        except Exception as e:
            dropped[gene] = f"fetch error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} fetch failed: {e}", flush=True)

    # Drop sparsity before sequence/decoy building.
    for gene in list(built.keys()):
        n = built[gene]["n_actives_pre_drop"]
        if n < MIN_ACTIVES:
            dropped[gene] = f"sparse: {n} actives < MIN_ACTIVES={MIN_ACTIVES}"
            built.pop(gene)
            raw_actives.pop(gene, None)

    global_pool = []
    for g, acts in raw_actives.items():
        global_pool.extend(acts.keys())

    # Pass 2: build decoys + fetch sequence (also under a per-target budget).
    def _build_one(gene):
        meta = PANEL[gene]
        actives = raw_actives[gene]
        n_act = len(actives)
        n_decoy_cap = int(round(n_act * DECOY_RATIO))

        inactives = raw_inactives.get(gene, {})
        decoy_smiles, decoy_source = [], None
        if len(inactives) >= MIN_DECOYS:
            items = sorted(inactives.items(), key=lambda kv: kv[1])
            decoy_smiles = [s for s, _ in items[:n_decoy_cap]]
            decoy_source = "chembl_inactives_same_target"
        else:
            active_smiles = set(actives.keys())
            active_props = [p for p in (mol_props(s) for s in actives) if p is not None]
            cand = [s for g2, acts in raw_actives.items() if g2 != gene for s in acts.keys()]
            if not cand:
                cand = list(global_pool)
            decoy_smiles = property_matched_decoys(active_smiles, active_props, cand, n_decoy_cap)
            decoy_source = "property_matched_cross_target_decoys"
            for s in inactives:
                if len(decoy_smiles) >= n_decoy_cap:
                    break
                if s not in decoy_smiles:
                    decoy_smiles.append(s)

        if len(decoy_smiles) < MIN_DECOYS:
            return ("dropped", f"no usable decoy set ({len(decoy_smiles)} < MIN_DECOYS={MIN_DECOYS}; "
                               f"source={decoy_source})")
        seq = fetch_uniprot_seq(meta["uniprot"])
        if not seq or len(seq) <= 30:
            return ("dropped", f"no protein sequence (UniProt fetch failed for {meta['uniprot']})")
        return ("ok", {"seq": seq, "decoys": decoy_smiles, "decoy_source": decoy_source})

    for gene in list(built.keys()):
        try:
            status, payload = with_timeout(TARGET_TIMEOUT_SEC, _build_one, gene)
            if status == "dropped":
                dropped[gene] = payload
                built.pop(gene)
                continue
            actives = raw_actives[gene]
            built[gene].update({
                "seq": payload["seq"], "seq_len": len(payload["seq"]), "seq_source": "uniprot_rest",
                "actives": list(actives.keys()),
                "decoys": payload["decoys"], "decoy_source": payload["decoy_source"],
                "n_actives": len(actives), "n_decoys": len(payload["decoys"]),
            })
            print(f"[panel] {gene}: {len(actives)} actives / {len(payload['decoys'])} decoys "
                  f"({payload['decoy_source']}); seq_len={len(payload['seq'])}", flush=True)
        except _Timeout:
            dropped[gene] = f"TIMEOUT (>{TARGET_TIMEOUT_SEC}s decoy/seq build) — skipped"
            built.pop(gene, None)
            print(f"[warn] {gene} build timed out -> skipped", flush=True)
        except Exception as e:
            dropped[gene] = f"decoy/seq build error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} build failed: {e}\n{traceback.format_exc()[:600]}", flush=True)
            built.pop(gene, None)

    return built, dropped


# ---------------------------------------------------------------------------
# LMDB builders in Uni-Mol schema (pattern from aws/drugclip_crossmodal_eval.py).
#   mol entry:    {atoms[list[str]], coordinates[list[np.ndarray]], mol, smi}
#   pocket entry: {pocket_atoms[list[str]], pocket_coordinates[list[xyz]],
#                  pocket_residue_name[list[str]], pocket(name)}
# For the protein_ranking (sequence) path the pocket tensors are DISCARDED by the model, so the
# pocket entry below is a tiny PLACEHOLDER — it only has to be shape-valid for the dataloader.
# ---------------------------------------------------------------------------
def smiles_to_mol_entry(smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    m = Chem.AddHs(m)
    try:
        AllChem.EmbedMultipleConfs(m, numConfs=1, params=AllChem.ETKDGv3())
        for c in range(m.GetNumConformers()):
            try:
                AllChem.MMFFOptimizeMolecule(m, confId=c)
            except Exception:
                pass
    except Exception:
        return None
    if m.GetNumConformers() == 0:
        return None
    m = Chem.RemoveHs(m)
    atoms = [a.GetSymbol() for a in m.GetAtoms()]
    coords = [m.GetConformer(c).GetPositions().astype(np.float32)
              for c in range(m.GetNumConformers())]
    return {"atoms": atoms, "coordinates": coords, "mol": m, "smi": smiles}


def write_lmdb(path, entries):
    import lmdb
    path = Path(path)
    # EVAL FIX (2026-06-15): lmdb.open(subdir=False) needs the PARENT dir to pre-exist; the
    # pocket.lmdb write runs before WORK.mkdir -> 'lmdb.Error: .../pocket.lmdb: No such file or
    # directory'. Ensure the parent exists here so it's robust to call order.
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    env = lmdb.open(str(path), map_size=1 << 31, subdir=False, lock=False)
    with env.begin(write=True) as txn:
        for i, e in enumerate(entries):
            txn.put(str(i).encode(), pickle.dumps(e))
    env.close()


def placeholder_pocket_entry(name):
    """A minimal, shape-valid pocket the protein_ranking model never reads.
    A few carbon 'CA' atoms on a small grid — enough to tokenize + build a distance matrix."""
    n = 8
    rng = np.random.default_rng(0)
    coords = (rng.standard_normal((n, 3)).astype(np.float32)) * 3.0
    return {
        "pocket_atoms": ["C"] * n,
        "pocket_coordinates": [coords[i] for i in range(n)],
        "pocket_residue_name": ["ALA"] * n,
        "pocket": name,
    }


# ---------------------------------------------------------------------------
# LigUnity loader + scorer. Drives the repo's own dataloaders + model in-process.
# protein side = sequence (ESM2) via model.pocket_forward(protein_sequences=...);
# ligand side = Uni-Mol 3D conformer via model.mol_forward(**net_input).
# score = cosine(protein_emb, mol_emb) (both unit-normalized in the model).
# ---------------------------------------------------------------------------
class LigUnity:
    def __init__(self):
        import torch
        sys.path.insert(0, str(LIGUNITY_DIR))
        os.chdir(LIGUNITY_DIR)  # vocab/dict_*.txt + ./vocab are referenced relative to repo root

        # Patch the repo's hard-coded ESM absolute path to a HF id we can download.
        self._patch_esm_path()

        from unicore import checkpoint_utils, options, tasks
        import unicore  # noqa: F401 (registers the framework)

        # Build the same arg namespace test.sh passes (data dir = ./vocab; arch = protein_ranking).
        parser = options.get_validation_parser()
        parser.add_argument("--test-task", type=str, default="DEMO")
        options.add_model_args(parser)
        argv = [
            "./vocab", "--user-dir", "./unimol", "--valid-subset", "test",
            "--task", "test_task", "--loss", "rank_softmax", "--arch", ARCH,
            "--num-workers", "0", "--batch-size", "64", "--seed", "1",
            "--path", CKPT, "--max-pocket-atoms", str(MAX_POCKET_ATOMS),
            "--fp16", "--fp16-init-scale", "4", "--fp16-scale-window", "256",
            "--test-task", "DEMO",
        ]
        args = options.parse_args_and_arch(parser, input_args=argv)
        self.args = args
        self.torch = torch

        state = checkpoint_utils.load_checkpoint_to_cpu(args.path)
        task = tasks.setup_task(args)
        model = task.build_model(args)
        model.load_state_dict(state["model"], strict=False)
        if args.fp16:
            model.half()
        if DEVICE == "cuda":
            model.cuda()
        model.eval()
        self.task = task
        self.model = model
        # The model's protein side is sequence-only for protein_ranking; assert that property.
        self.is_sequence_path = (ARCH == "protein_ranking")

    def _patch_esm_path(self):
        """protein_ranking.py hard-codes /cto_studio/.../esm2_t12_35M_UR50D. Rewrite to a HF id."""
        f = LIGUNITY_DIR / "unimol" / "models" / "protein_ranking.py"
        try:
            txt = f.read_text()
        except Exception as e:
            print(f"[warn] could not read protein_ranking.py to patch ESM path: {e}", flush=True)
            return
        import re
        new = re.sub(r'(["\'])/[^"\']*esm2_t12_35M_UR50D\1',
                     f'"{ESM_MODEL}"', txt)
        if new != txt:
            f.write_text(new)
            print(f"[patch] protein_ranking.py ESM path -> {ESM_MODEL}", flush=True)
        else:
            print("[patch] no ESM abs-path found to rewrite (already patched?)", flush=True)

    def _mol_reps(self, smiles_list):
        """Encode a list of ligand SMILES -> (N, D) L2-normalized Uni-Mol mol embeddings.
        Skips SMILES that fail conformer generation; returns (reps, kept_idx)."""
        import torch
        entries, kept = [], []
        for i, smi in enumerate(smiles_list):
            e = smiles_to_mol_entry(smi)
            if e is not None:
                entries.append(e)
                kept.append(i)
        if not entries:
            return np.zeros((0, 0), dtype=np.float32), []
        lmdb_path = WORK / "mols.lmdb"
        write_lmdb(lmdb_path, entries)
        ds = self.task.load_mols_dataset(str(lmdb_path), "atoms", "coordinates")
        loader = torch.utils.data.DataLoader(ds, batch_size=self.args.batch_size,
                                             collate_fn=ds.collater, num_workers=0)
        import unicore
        reps = []
        for sample in loader:
            if DEVICE == "cuda":
                sample = unicore.utils.move_to_cuda(sample)
            emb = self.model.mol_forward(**sample["net_input"])
            reps.append(emb.detach().float().cpu().numpy())
        return np.concatenate(reps, axis=0), kept

    def _protein_rep(self, seq, name):
        """Encode ONE protein from its sequence -> (D,) L2-normalized embedding.
        Builds a placeholder pocket lmdb (discarded by the protein_ranking model) so the
        repo's load_pockets_dataset/collater shape-contract is satisfied."""
        import torch, unicore
        lmdb_path = WORK / "pocket.lmdb"
        write_lmdb(lmdb_path, [placeholder_pocket_entry(name)])
        ds = self.task.load_pockets_dataset(str(lmdb_path))
        loader = torch.utils.data.DataLoader(ds, batch_size=1, collate_fn=ds.collater,
                                             num_workers=0)
        sample = list(loader)[0]
        if DEVICE == "cuda":
            sample = unicore.utils.move_to_cuda(sample)
        # protein_ranking.pocket_forward(protein_sequences, **kwargs) ignores the pocket tensors.
        emb = self.model.pocket_forward(protein_sequences=seq, **sample["net_input"])
        return emb.detach().float().cpu().numpy().reshape(-1)

    def score_target(self, seq, name, actives, decoys):
        """Return (scores, labels, smiles_kept). score = cosine(protein, mol)."""
        prot = self._protein_rep(seq, name)                 # (D,)
        prot = prot / (np.linalg.norm(prot) + 1e-9)
        all_smiles = list(actives) + list(decoys)
        all_labels = [1] * len(actives) + [0] * len(decoys)
        mol_reps, kept = self._mol_reps(all_smiles)
        if mol_reps.shape[0] == 0:
            return [], [], []
        mol_reps = mol_reps / (np.linalg.norm(mol_reps, axis=1, keepdims=True) + 1e-9)
        scores = mol_reps @ prot                             # cosine == dot (both unit-norm)
        labels = [all_labels[i] for i in kept]
        smiles = [all_smiles[i] for i in kept]
        return scores.tolist(), labels, smiles


def score_ligunity(panels):
    WORK.mkdir(parents=True, exist_ok=True)
    lig = LigUnity()
    out = {}
    for gene, p in panels.items():
        try:
            scores, labels, smiles = lig.score_target(
                p["seq"], gene, p["actives"], p["decoys"])
            a = auroc(labels, scores) if scores else None
            n_act = sum(labels) if labels else 0
            n_dec = len(labels) - n_act if labels else 0
            a_scores = [s for s, l in zip(scores, labels) if l == 1]
            d_scores = [s for s, l in zip(scores, labels) if l == 0]
            out[gene] = {
                "family": p["family"], "chembl_id": p["chembl_id"],
                "auroc": a, "n_actives": n_act, "n_decoys": n_dec,
                "n_dropped_smiles": len(p["actives"]) + len(p["decoys"]) - len(labels),
                "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
                "mean_active_score": round(float(np.mean(a_scores)), 5) if a_scores else None,
                "mean_decoy_score": round(float(np.mean(d_scores)), 5) if d_scores else None,
            }
            print(f"[ligunity] {gene} ({p['family']}): AUROC={a} "
                  f"(n_act={n_act}, n_dec={n_dec})", flush=True)
        except Exception as e:
            out[gene] = {"family": p["family"], "auroc": None,
                         "error": f"{type(e).__name__}: {e}"}
            print(f"[FAIL] {gene}: {e}\n{traceback.format_exc()[:800]}", flush=True)
    return out


# ---------------------------------------------------------------------------
# Family aggregation — mean AUROC + range per family (verbatim from cns benchmark).
# ---------------------------------------------------------------------------
def aggregate_by_family(per_target):
    fams = {}
    for gene, r in per_target.items():
        a = r.get("auroc")
        if a is None:
            continue
        fams.setdefault(r["family"], []).append((gene, a))
    out = {}
    for fam, pairs in fams.items():
        vals = [a for _, a in pairs]
        out[fam] = {
            "n_targets": len(vals),
            "mean_auroc": round(float(np.mean(vals)), 4),
            "median_auroc": round(float(np.median(vals)), 4),
            "min_auroc": round(float(np.min(vals)), 4),
            "max_auroc": round(float(np.max(vals)), 4),
            "range": round(float(np.max(vals) - np.min(vals)), 4),
            "per_target": {g: round(a, 4) for g, a in sorted(pairs, key=lambda x: -x[1])},
        }
    all_vals = [r["auroc"] for r in per_target.values() if r.get("auroc") is not None]
    out["_overall"] = {
        "n_targets": len(all_vals),
        "mean_auroc": round(float(np.mean(all_vals)), 4) if all_vals else None,
        "median_auroc": round(float(np.median(all_vals)), 4) if all_vals else None,
        "min_auroc": round(float(np.min(all_vals)), 4) if all_vals else None,
        "max_auroc": round(float(np.max(all_vals)), 4) if all_vals else None,
    }
    return out


def section(name, fn, store, *args):
    try:
        store[name] = fn(*args)
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        store[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1500]}", flush=True)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    results = {
        "task": ("LigUnity (Patterns 2025) on Track 2 / binder triage: per-target binder-vs-decoy "
                 "AUROC on the 19-target CNS panel -> per-FAMILY aggregate, head-to-head vs the "
                 "BALM/PLAPT sequence-based baselines. Does its ranking inductive bias beat them on "
                 "ion channels (chance for everyone)?"),
        "model": "LigUnity",
        "checkpoint_path_used": CKPT,
        "arch_used": ARCH,
        "checkpoint_determination": {
            "chosen": "fengb/LigUnity_protein_ranking",
            "pocket_free": True,
            "why": ("protein_ranking.pocket_forward(protein_sequences, **kwargs) encodes the protein "
                    "PURELY from its UniProt sequence via ESM2-35M and DISCARDS the 3D pocket tensors. "
                    "Ligand side is a Uni-Mol 3D conformer. So the protein side is pocket-free — same "
                    "input class (sequence+SMILES) as BALM/PLAPT, a fair head-to-head."),
            "rejected_pose_gated_path": ("fengb/LigUnity_pocket_ranking — pocket_forward consumes a "
                    "Uni-Mol 3D pocket (pocket_src_tokens/distance/edge_type). POSE/POCKET-GATED, the "
                    "same failure mode as DrugCLIP + AEV-PLIG on Quiver's no-holo targets. Not run."),
            "placeholder_pocket_note": ("test_demo still loads a pocket lmdb to build the batch; the "
                    "protein_ranking model never reads it, so we feed a tiny dummy CA-atom pocket "
                    "purely for dataloader shape. The score is sequence(protein) vs conformer(ligand)."),
        },
        "device": DEVICE,
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
            "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "binding_types": BINDING_TYPES,
            "target_timeout_sec": TARGET_TIMEOUT_SEC, "esm_model": ESM_MODEL,
            "max_pocket_atoms": MAX_POCKET_ATOMS,
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]}
                             for g, m in PANEL.items()},
        "baselines_family_mean_auroc": BASELINE_FAMILY_MEAN,
    }

    # --- Build per-target sets from ChEMBL (guarded; per-target timeouts inside) ---
    build_store = {}
    section("build", build_panels, build_store)
    built = build_store.get("build")
    if isinstance(built, dict) and "error" in built:
        results["build_error"] = built["error"]
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] build failed; wrote {OUT}", flush=True)
        return
    panels, dropped = built
    results["dropped_targets"] = dropped
    results["built_targets"] = {
        g: {"chembl_id": p["chembl_id"], "chembl_id_source": p["chembl_id_source"],
            "family": p["family"], "uniprot": p["uniprot"],
            "n_actives": p["n_actives"], "n_decoys": p["n_decoys"],
            "decoy_source": p["decoy_source"], "seq_len": p["seq_len"]}
        for g, p in panels.items()}
    results["n_targets_built"] = len(panels)
    print(f"[built] {len(panels)} targets; dropped {len(dropped)}", flush=True)

    # --- Score with LigUnity (guarded) ---
    models = {}
    section("LigUnity", score_ligunity, models, panels)
    results["per_target_auroc"] = models

    # --- Family aggregation ---
    family = {}
    for mname, per_target in models.items():
        if isinstance(per_target, dict) and "error" not in per_target:
            try:
                family[mname] = aggregate_by_family(per_target)
            except Exception as e:
                family[mname] = {"error": f"{type(e).__name__}: {e}"}
    results["family_aggregate"] = family

    # --- Head-to-head: per-family mean AUROC, LigUnity vs BALM vs PLAPT ---
    lig_fam = family.get("LigUnity", {}) if isinstance(family.get("LigUnity"), dict) else {}
    h2h = {}
    for fam in ["ion_channel", "mtor_pathway", "gpcr", "kinase"]:
        h2h[fam] = {
            "LigUnity": (lig_fam.get(fam, {}) or {}).get("mean_auroc"),
            "BALM": BASELINE_FAMILY_MEAN["BALM"].get(fam),
            "PLAPT": BASELINE_FAMILY_MEAN["PLAPT"].get(fam),
        }
    h2h["_overall"] = {"LigUnity": (lig_fam.get("_overall", {}) or {}).get("mean_auroc")}
    results["headline_family_mean_auroc"] = h2h

    results["runtime_sec"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    # Best-effort cleanup of the scratch lmdbs (never fatal).
    try:
        shutil.rmtree(WORK, ignore_errors=True)
    except Exception:
        pass
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("headline_family_mean_auroc", {}), indent=2, default=str),
          flush=True)


if __name__ == "__main__":
    main()
