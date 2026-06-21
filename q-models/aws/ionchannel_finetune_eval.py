"""ION-CHANNEL BINDER FINE-TUNE: train a real CROSS-CHANNEL DTI model on a pooled
ONLINE corpus (ChEMBL + Guide-to-PHARMACOLOGY) and test genuine generalization.

WHY — "the fine-tune is the lever"
==================================
`results/cns_dti_characterization.md` found off-the-shelf zero-shot sequence-DTI at
CHANCE (ion-channel family-mean AUROC 0.499 BALM cosine / 0.501 PLAPT affinity) on
the CNS ion-channel family (Nav/Cav/NMDA/Kv, 1956-2221 aa). `results/trunc_test_
characterization.md` then showed a per-target SUPERVISED probe (ESM-2-650M + Morgan-FP,
scaffold-split CV) recovers the signal cleanly (family mean 0.919, e.g. Cav1.2 0.20->0.95,
NMDA 0.32->0.95) on a SMALL 9-target panel. Two clean conclusions there: truncation is
NOT the cause (truncated == full-length to 4 decimals in a per-target probe), and the
zero-shot failure is the lack of TARGET-SPECIFIC SUPERVISION.

That per-target probe is QSAR (one target, many ligands; the protein embedding is constant
within a target and contributes nothing to within-target discrimination). This run scales
that finding into a genuine CROSS-CHANNEL DTI MODEL: the protein-side ESM-2 embedding VARIES
across targets, so a single pooled model must learn channel-conditioned binder chemistry,
and we test whether that knowledge GENERALIZES to (a) unseen scaffolds and (b) an entirely
unseen channel. This is the concrete "the fine-tune is the lever" demonstration, and a
deployable public-data ion-channel binder model.

THE MODEL (a genuine cross-channel DTI head, NOT per-target QSAR)
================================================================
Features per (target, compound):
  ESM-2-650M target-SEQUENCE embedding (mean-pooled over residues, the PROTEIN tower; frozen,
    chunk-pooled so the full 1956-2221 aa channel is represented, no 1024-token cap)
  CONCAT Morgan-FP(2048) of the ligand (the LIGAND tower).
The protein half VARIES across the ~19-target ion-channel panel -> real DTI generalization.

Head = an MLP classifier (torch, 2-3 layers + dropout) trained on the pooled ion-channel
corpus (binder vs decoy/inactive). This trained head on a frozen ESM-2 target tower + FP
ligand tower IS the "fine-tune". A Morgan-FP + GradientBoosting model (ligand-only) is
trained as the BASELINE for comparison (does the protein tower buy cross-channel transfer
over a pure ligand QSAR?).

TWO HELD-OUT EVALS (both reported)
==================================
(1) MURCKO SCAFFOLD SPLIT — GroupKFold over Bemis-Murcko scaffolds, pooled across ALL
    channels. Per-family + overall AUROC + EF5% (5% enrichment factor). Tests novel-scaffold
    generalization (the standard fine-tune success metric).
(2) LEAVE-ONE-CHANNEL-OUT (LOCO) — for each of {SCN10A/Nav1.8, CACNA1C/Cav1.2, GRIN2B/NMDA,
    SCN9A/Nav1.7}, train on ALL OTHER channels and test on the held-out channel. Does
    cross-channel knowledge transfer to a channel the model has NEVER seen? Per-held-out-
    channel AUROC + EF5. This is the real DTI-generalization test (not QSAR).

CORPUS — pooled ChEMBL + Guide-to-PHARMACOLOGY (deduped by canonical SMILES)
===========================================================================
ChEMBL (pulled on-instance, same puller as aws/cns_dti_benchmark_eval.py): the FULL CNS
ion-channel panel (Nav SCN1A/2A/3A/4A/5A/8A/9A/10A/11A; Cav CACNA1A/1B/1C/1G/1H/1S; NMDA
GRIN1/2A/2B; Kv/KCNQ KCNQ2/3/5). Per target: ALL actives (pChEMBL>=6.0) + ALL inactives
(pChEMBL<5.0) -- NO cap -- plus DUD-E-style property-matched decoys to top up targets with
few inactives. A per-target socket timeout (signal.alarm) SKIPS a stalled/500ing target
rather than hanging (ChEMBL is back up but flaky).

GtoPdb anchor corpus (staged by the launcher to s3://BUCKET/ionchannel_finetune/gtopdb_
ionchannel_affinities.csv; userdata pulls it to GTOPDB_CSV): rows give smiles +
target_name + family (nav/cav/kv/nmda/...). affinity_median is the pX value; pX>=ACTIVE_
PCHEMBL -> active, pX<=INACTIVE_PCHEMBL -> inactive (rows in between are dropped). These
rows are merged into the training pool, mapped onto our family/channel taxonomy, and deduped
against the ChEMBL pool by CANONICAL SMILES (RDKit), keeping the stronger label on conflict.

Every section is try/except-guarded so one ChEMBL/UniProt/GtoPdb hiccup cannot sink the run;
partial results still upload. Writes JSON to env OUT (default
/root/ionchannel_out/ionchannel_finetune_result.json). USE_TF=0 USE_FLAX=0; CUDA.
"""
from __future__ import annotations

import csv
import json
import os
import signal
import sys
import time
import traceback
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/ionchannel_out/ionchannel_finetune_result.json"))
ESM2_REPO = os.environ.get("ESM2_REPO", "facebook/esm2_t33_650M_UR50D")
GTOPDB_CSV = Path(os.environ.get("GTOPDB_CSV", "/opt/gtopdb_ionchannel_affinities.csv"))

# Knobs (env-overridable). Mirror the CNS benchmark so the panel build is comparable.
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))      # >= this = active (~<=1 uM)
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))  # <= this = inactive
# NOTE: NO MAX_ACTIVES cap -- we want the FULL corpus per target (this is a training run).
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "20"))              # drop target below this many actives
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))           # property-matched decoys <= ratio x n_actives
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "10"))               # need at least this many decoys/target
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))  # matched-decoy dissimilarity
CHEMBL_TIMEOUT = int(os.environ.get("CHEMBL_TIMEOUT", "300"))      # per-target fail-fast (signal.alarm), seconds

CHUNK_AA = int(os.environ.get("CHUNK_AA", "1022"))                 # residues per ESM-2 chunk-pool window
N_FOLDS = int(os.environ.get("N_FOLDS", "5"))
MORGAN_BITS = int(os.environ.get("MORGAN_BITS", "2048"))
MORGAN_RADIUS = int(os.environ.get("MORGAN_RADIUS", "2"))
EF_FRAC = float(os.environ.get("EF_FRAC", "0.05"))                 # EF5% top fraction
SEED = int(os.environ.get("SEED", "20260615"))
RNG = np.random.default_rng(SEED)

# MLP head hyperparameters.
MLP_HIDDEN = [int(x) for x in os.environ.get("MLP_HIDDEN", "512,128").split(",")]
MLP_DROPOUT = float(os.environ.get("MLP_DROPOUT", "0.3"))
MLP_EPOCHS = int(os.environ.get("MLP_EPOCHS", "60"))
MLP_LR = float(os.environ.get("MLP_LR", "1e-3"))
MLP_WD = float(os.environ.get("MLP_WD", "1e-4"))
MLP_BATCH = int(os.environ.get("MLP_BATCH", "256"))

# Success criterion (the scorecard's fine-tune bar) + reference points.
SUCCESS_AUROC = float(os.environ.get("SUCCESS_AUROC", "0.80"))
SUCCESS_EF = float(os.environ.get("SUCCESS_EF", "5.0"))
ZEROSHOT_REF = 0.50   # BALM/PLAPT ion-channel family-mean zero-shot
PROBE_REF = 0.92      # trunc_test per-target supervised probe (small panel)

# ---------------------------------------------------------------------------
# FULL CNS ION-CHANNEL PANEL. gene -> (uniprot accession PRIMARY key,
# fallback_chembl_id, family). UniProt accession resolves the single-protein human
# ChEMBL target at runtime; the chembl id is a documented FALLBACK only.
# Families: nav | cav | nmda | kv. (Lengths annotated for the truncation context.)
# ---------------------------------------------------------------------------
PANEL = {
    # --- Nav (voltage-gated sodium) ---
    "SCN1A":   {"uniprot": "P35498", "chembl": "CHEMBL5277",    "family": "nav"},   # Nav1.1 ~2009 aa
    "SCN2A":   {"uniprot": "Q99250", "chembl": "CHEMBL4076",    "family": "nav"},   # Nav1.2 ~2005 aa
    "SCN3A":   {"uniprot": "Q9NY46", "chembl": "CHEMBL4828",    "family": "nav"},   # Nav1.3 ~2000 aa
    "SCN4A":   {"uniprot": "P35499", "chembl": "CHEMBL4329",    "family": "nav"},   # Nav1.4 ~1836 aa
    "SCN5A":   {"uniprot": "Q14524", "chembl": "CHEMBL1980",    "family": "nav"},   # Nav1.5 ~2016 aa (cardiac)
    "SCN8A":   {"uniprot": "Q9UQD0", "chembl": "CHEMBL4960",    "family": "nav"},   # Nav1.6 ~1980 aa
    "SCN9A":   {"uniprot": "Q15858", "chembl": "CHEMBL4296",    "family": "nav"},   # Nav1.7 ~1988 aa
    "SCN10A":  {"uniprot": "Q9Y5Y9", "chembl": "CHEMBL5451",    "family": "nav"},   # Nav1.8 ~1956 aa
    "SCN11A":  {"uniprot": "Q9UI33", "chembl": "CHEMBL4153",    "family": "nav"},   # Nav1.9 ~1791 aa

    # --- Cav (voltage-gated calcium, alpha-1 subunits) ---
    "CACNA1A": {"uniprot": "O00555", "chembl": "CHEMBL4137",    "family": "cav"},   # Cav2.1 ~2505 aa
    "CACNA1B": {"uniprot": "Q00975", "chembl": "CHEMBL4478",    "family": "cav"},   # Cav2.2 ~2339 aa
    "CACNA1C": {"uniprot": "Q13936", "chembl": "CHEMBL1940",    "family": "cav"},   # Cav1.2 ~2221 aa
    "CACNA1G": {"uniprot": "O43497", "chembl": "CHEMBL4198",    "family": "cav"},   # Cav3.1 ~2377 aa
    "CACNA1H": {"uniprot": "O95180", "chembl": "CHEMBL3729",    "family": "cav"},   # Cav3.2 ~2353 aa
    "CACNA1S": {"uniprot": "Q13698", "chembl": "CHEMBL4202",    "family": "cav"},   # Cav1.1 ~1873 aa

    # --- NMDA (ionotropic glutamate) ---
    "GRIN1":   {"uniprot": "Q05586", "chembl": "CHEMBL1907594", "family": "nmda"},  # GluN1 ~938 aa
    "GRIN2A":  {"uniprot": "Q12879", "chembl": "CHEMBL1907595", "family": "nmda"},  # GluN2A ~1464 aa
    "GRIN2B":  {"uniprot": "Q13224", "chembl": "CHEMBL1907600", "family": "nmda"},  # GluN2B ~1484 aa

    # --- Kv / KCNQ (voltage-gated potassium) ---
    "KCNQ2":   {"uniprot": "O43526", "chembl": "CHEMBL4304",    "family": "kv"},    # Kv7.2 ~872 aa
    "KCNQ3":   {"uniprot": "O43525", "chembl": "CHEMBL4798",    "family": "kv"},    # Kv7.3 ~872 aa
    "KCNQ5":   {"uniprot": "Q9NR82", "chembl": "CHEMBL4304157", "family": "kv"},    # Kv7.5 ~932 aa
}

# LOCO held-out channels (must be present in PANEL keys). Each is trained-out and tested.
LOCO_CHANNELS = [c for c in os.environ.get(
    "LOCO_CHANNELS", "SCN10A,CACNA1C,GRIN2B,SCN9A").split(",") if c]

BINDING_TYPES = ["IC50", "Ki", "Kd"]

# GtoPdb family-tag -> our taxonomy. GtoPdb tags: nav/cav/kv/nmda/other_channel/other_lgic.
GTOPDB_FAMILY_MAP = {"nav": "nav", "cav": "cav", "kv": "kv", "nmda": "nmda"}


# ---------------------------------------------------------------------------
# AUROC (rank-sum; ties get average rank). Higher score => label 1 (binder).
# Reused verbatim from aws/cns_dti_benchmark_eval.py / aws/trunc_test_eval.py.
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


def enrichment_factor(labels, scores, frac=EF_FRAC):
    """EF at top `frac` (e.g. 5%): (hit rate in top-frac) / (overall hit rate)."""
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    n = len(labels)
    n_pos = int(labels.sum())
    if n == 0 or n_pos == 0:
        return None
    k = max(1, int(round(n * frac)))
    top = np.argsort(-scores, kind="mergesort")[:k]
    hits_top = int(labels[top].sum())
    base_rate = n_pos / n
    return float((hits_top / k) / base_rate)


# ---------------------------------------------------------------------------
# Per-target fail-fast: a signal.alarm-based timeout so an EBI 500/stall SKIPS a
# target instead of hanging the whole run (ChEMBL is back up but flaky).
# ---------------------------------------------------------------------------
class TargetTimeout(Exception):
    pass


class alarm_timeout:
    """Context manager raising TargetTimeout after `seconds` (SIGALRM, main thread)."""
    def __init__(self, seconds):
        self.seconds = int(seconds)

    def _handler(self, signum, frame):
        raise TargetTimeout(f"timed out after {self.seconds}s")

    def __enter__(self):
        self._old = signal.signal(signal.SIGALRM, self._handler)
        signal.alarm(self.seconds)
        return self

    def __exit__(self, *exc):
        signal.alarm(0)
        signal.signal(signal.SIGALRM, self._old)
        return False


# ---------------------------------------------------------------------------
# UniProt WT-sequence fetch (verbatim from aws/cns_dti_benchmark_eval.py).
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "ionchannel-finetune/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL data access (verbatim from aws/cns_dti_benchmark_eval.py).
# ---------------------------------------------------------------------------
def resolve_chembl_id(meta):
    """Resolve a single-protein human ChEMBL target id by UniProt accession.
    Falls back to the hardcoded id. Returns (chembl_id, source)."""
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
    """Pull binding (IC50/Ki/Kd) activities with a non-null pchembl_value for a target.
    Returns {smiles: max_pchembl} (best/strongest pchembl per unique compound).
    NO cap -- this is a training run; we want the full corpus."""
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
# RDKit helpers (verbatim from aws/cns_dti_benchmark_eval.py + canonical SMILES + ECFP4).
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


def canonical_smiles(smi):
    """RDKit canonical SMILES for dedup; None if unparseable."""
    try:
        from rdkit import Chem
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def ecfp4(smi):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit import DataStructs
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    bv = AllChem.GetMorganFingerprintAsBitVect(m, MORGAN_RADIUS, MORGAN_BITS)
    arr = np.zeros((MORGAN_BITS,), dtype=np.float64)
    DataStructs.ConvertToNumpyArray(bv, arr)
    return arr


def murcko_scaffold(smi):
    """Bemis-Murcko scaffold SMILES (for scaffold-aware grouping). None on failure."""
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        scaf = MurckoScaffold.GetScaffoldForMol(m)
        s = Chem.MolToSmiles(scaf)
        return s if s else None
    except Exception:
        return None


def property_matched_decoys(active_smiles, active_props, candidate_pool, n_needed):
    """DUD-E-style property-matched, chemically-dissimilar decoys (verbatim logic)."""
    from rdkit import DataStructs
    if not active_props or n_needed <= 0:
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
                continue  # too similar to a known binder -> not a clean decoy
        picked.append(smi)
        if len(picked) >= n_needed:
            break
    return picked


# ---------------------------------------------------------------------------
# Load + merge the GtoPdb anchor corpus. Columns (CSV with quoting -> use csv module):
#   family, target_name, smiles, affinity_type, affinity_median (the pX value), ...
# pX>=ACTIVE -> active; pX<=INACTIVE -> inactive; in-between dropped. Map family tag onto
# our taxonomy (nav/cav/kv/nmda). Returns list of {smiles, family, channel, pchembl, label}.
# ---------------------------------------------------------------------------
def load_gtopdb():
    rows = []
    if not GTOPDB_CSV.exists():
        print(f"[gtopdb] {GTOPDB_CSV} not found -- skipping anchor corpus", flush=True)
        return rows, {"present": False}
    n_total = n_kept = n_active = n_inactive = n_dropmid = n_badfam = n_badaff = 0
    with open(GTOPDB_CSV, newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            n_total += 1
            fam_raw = (r.get("family") or "").strip().lower()
            fam = GTOPDB_FAMILY_MAP.get(fam_raw)
            if fam is None:
                n_badfam += 1
                continue  # other_channel / other_lgic -> not in our CNS taxonomy
            smi = (r.get("smiles") or "").strip()
            if not smi:
                continue
            try:
                pv = float((r.get("affinity_median") or "").strip())
            except (TypeError, ValueError):
                n_badaff += 1
                continue
            if pv >= ACTIVE_PCHEMBL:
                label = 1
                n_active += 1
            elif pv <= INACTIVE_PCHEMBL:
                label = 0
                n_inactive += 1
            else:
                n_dropmid += 1
                continue  # ambiguous middle band -> drop
            channel = (r.get("target_name") or fam).strip()  # e.g. Nav1.8, GluN2B
            rows.append({"smiles": smi, "family": fam, "channel": f"gtopdb:{channel}",
                         "pchembl": pv, "label": label})
            n_kept += 1
    stats = {"present": True, "n_rows_total": n_total, "n_kept": n_kept,
             "n_active": n_active, "n_inactive": n_inactive,
             "n_dropped_mid_band": n_dropmid, "n_off_taxonomy_family": n_badfam,
             "n_bad_affinity": n_badaff}
    print(f"[gtopdb] {stats}", flush=True)
    return rows, stats


# ---------------------------------------------------------------------------
# Build the pooled corpus: per-target ChEMBL actives/inactives (NO cap) + property-
# matched decoy top-up, fetch full sequence, then merge GtoPdb rows. Dedup by canonical
# SMILES *within a channel* (keep stronger label on conflict). Returns:
#   targets: gene -> {family, seq, seq_len, chembl_id, ...}
#   pairs  : list of {gene, family, smiles, canon, label, source, pchembl}
#   dropped: gene -> reason
# ---------------------------------------------------------------------------
def build_corpus():
    targets = {}
    dropped = {}
    raw_actives = {}    # gene -> {smiles: pchembl}
    raw_inactives = {}  # gene -> {smiles: pchembl}

    # Pass 1: ChEMBL pull per target, fail-fast guarded (signal.alarm).
    for gene, meta in PANEL.items():
        try:
            with alarm_timeout(CHEMBL_TIMEOUT):
                cid, src = resolve_chembl_id(meta)
                if not cid:
                    dropped[gene] = "no ChEMBL target id (resolve + fallback both empty)"
                    continue
                best = fetch_activities(cid)
            actives = {s: v for s, v in best.items() if v >= ACTIVE_PCHEMBL}
            inactives = {s: v for s, v in best.items() if v <= INACTIVE_PCHEMBL}
            raw_actives[gene] = actives
            raw_inactives[gene] = inactives
            targets[gene] = {"chembl_id": cid, "chembl_id_source": src,
                             "family": meta["family"], "uniprot": meta["uniprot"],
                             "n_chembl_actives": len(actives),
                             "n_chembl_inactives": len(inactives)}
            print(f"[chembl] {gene} ({cid}, {src}): {len(actives)} actives / "
                  f"{len(inactives)} inactives", flush=True)
        except TargetTimeout as e:
            dropped[gene] = f"chembl timeout: {e}"
            print(f"[skip] {gene} ChEMBL pull timed out ({e}) -- SKIPPING target", flush=True)
        except Exception as e:
            dropped[gene] = f"fetch error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} fetch failed: {e}", flush=True)

    # Global cross-target active pool for property-matched fallback decoys.
    global_pool = []
    for g, acts in raw_actives.items():
        global_pool.extend(acts.keys())

    # Pass 2: per surviving target build decoys + fetch full sequence.
    for gene in list(targets.keys()):
        try:
            meta = PANEL[gene]
            actives = raw_actives.get(gene, {})
            inactives = raw_inactives.get(gene, {})
            n_act = len(actives)
            n_decoy_cap = int(round(n_act * DECOY_RATIO)) if n_act else MIN_DECOYS

            # Decoys: prefer same-target ChEMBL inactives; top up with property-matched.
            decoy_smiles = list(inactives.keys())
            decoy_source = "chembl_inactives_same_target" if decoy_smiles else None
            if len(decoy_smiles) < max(MIN_DECOYS, n_decoy_cap) and actives:
                active_smiles = set(actives.keys())
                active_props = [p for p in (mol_props(s) for s in actives) if p is not None]
                cand = [s for g2, acts in raw_actives.items() if g2 != gene
                        for s in acts.keys()]
                if not cand:
                    cand = list(global_pool)
                need = max(MIN_DECOYS, n_decoy_cap) - len(decoy_smiles)
                extra = property_matched_decoys(active_smiles, active_props, cand, need)
                extra = [s for s in extra if s not in inactives]
                decoy_smiles = decoy_smiles + extra
                decoy_source = ("chembl_inactives+property_matched" if inactives
                                else "property_matched_cross_target")

            # Full sequence (chunk-pool over the whole channel; no truncation).
            seq, seq_source = None, None
            try:
                with alarm_timeout(120):
                    seq = fetch_uniprot_seq(meta["uniprot"])
                if seq and len(seq) > 30:
                    seq_source = "uniprot_rest"
            except Exception as e:
                print(f"[warn] UniProt fetch failed for {gene} ({meta['uniprot']}): {e}",
                      flush=True)
            if not seq:
                dropped[gene] = f"no protein sequence (UniProt fetch failed for {meta['uniprot']})"
                targets.pop(gene, None)
                continue

            targets[gene].update({
                "seq": seq, "seq_len": len(seq), "seq_source": seq_source,
                "n_chunks": int(np.ceil(len(seq) / CHUNK_AA)),
                "decoy_source": decoy_source,
                "_actives": list(actives.keys()),
                "_decoys": list(decoy_smiles),
            })
            print(f"[target] {gene} ({meta['family']}): {len(actives)} actives / "
                  f"{len(decoy_smiles)} decoys ({decoy_source}); seq_len={len(seq)}",
                  flush=True)
        except Exception as e:
            dropped[gene] = f"decoy/seq build error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} build failed: {e}\n{traceback.format_exc()[:500]}",
                  flush=True)
            targets.pop(gene, None)

    # Merge GtoPdb rows onto the channel taxonomy. Each GtoPdb family attaches to the
    # corresponding PANEL targets (one logical channel per GtoPdb target_name), so the
    # protein side is carried by the matching family's representative sequence(s). We
    # attach a GtoPdb row to the FIRST surviving PANEL gene of its family (representative
    # protein) -- this keeps the protein embedding family-consistent while expanding the
    # ligand corpus. Deduped by canonical SMILES per gene.
    gtopdb_rows, gtopdb_stats = load_gtopdb()
    fam_to_genes = defaultdict(list)
    for g, t in targets.items():
        fam_to_genes[t["family"]].append(g)

    # Assemble pooled pairs. Start with ChEMBL actives/decoys per surviving gene.
    pairs = []
    seen = set()  # (gene, canon)
    for gene, t in targets.items():
        for smi in t.get("_actives", []):
            c = canonical_smiles(smi)
            if c is None:
                continue
            key = (gene, c)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"gene": gene, "family": t["family"], "smiles": smi,
                          "canon": c, "label": 1, "source": "chembl"})
        for smi in t.get("_decoys", []):
            c = canonical_smiles(smi)
            if c is None:
                continue
            key = (gene, c)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"gene": gene, "family": t["family"], "smiles": smi,
                          "canon": c, "label": 0, "source": "chembl"})

    # Merge GtoPdb: route each row to its family's representative gene. Dedup by
    # (gene, canon); on a label conflict keep the stronger (active wins).
    n_gtopdb_added = n_gtopdb_dup = n_gtopdb_nofamily = 0
    label_by_key = {(p["gene"], p["canon"]): i for i, p in enumerate(pairs)}
    for row in gtopdb_rows:
        genes = fam_to_genes.get(row["family"])
        if not genes:
            n_gtopdb_nofamily += 1
            continue
        gene = genes[0]  # representative protein for this family
        c = canonical_smiles(row["smiles"])
        if c is None:
            continue
        key = (gene, c)
        if key in label_by_key:
            idx = label_by_key[key]
            # active wins on conflict
            if row["label"] == 1 and pairs[idx]["label"] == 0:
                pairs[idx]["label"] = 1
                pairs[idx]["source"] = pairs[idx]["source"] + "+gtopdb"
            n_gtopdb_dup += 1
            continue
        pairs.append({"gene": gene, "family": row["family"], "smiles": row["smiles"],
                      "canon": c, "label": row["label"], "source": "gtopdb"})
        label_by_key[key] = len(pairs) - 1
        n_gtopdb_added += 1

    # Drop targets that now have too few actives to be useful in pooled training.
    per_gene_actives = defaultdict(int)
    for p in pairs:
        if p["label"] == 1:
            per_gene_actives[p["gene"]] += 1
    for gene in list(targets.keys()):
        if per_gene_actives.get(gene, 0) < MIN_ACTIVES:
            reason = f"sparse after merge: {per_gene_actives.get(gene,0)} actives < MIN_ACTIVES={MIN_ACTIVES}"
            dropped[gene] = reason
            targets.pop(gene, None)
    # keep only pairs whose gene survived
    pairs = [p for p in pairs if p["gene"] in targets]

    gtopdb_stats.update({"n_added": n_gtopdb_added, "n_dup_with_chembl": n_gtopdb_dup,
                         "n_no_matching_family": n_gtopdb_nofamily})
    return targets, pairs, dropped, gtopdb_stats


# ---------------------------------------------------------------------------
# ESM-2-650M protein encoder. Mean-pool residue embeddings EXCLUDING CLS/EOS
# (verbatim protocol from aws/trunc_test_eval.py / aws/big_panel_sweep.py:
#  hs[0, 1:-1, :].mean(0)). FULL-length CHUNK-POOL so the entire channel is represented.
# ---------------------------------------------------------------------------
class Esm2Encoder:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(ESM2_REPO)
        self.m = AutoModel.from_pretrained(
            ESM2_REPO, torch_dtype=torch.float32).to(DEVICE).eval()
        self.dim = int(self.m.config.hidden_size)

    def _embed_window(self, residues):
        torch = self.torch
        inp = self.tok(residues, return_tensors="pt", add_special_tokens=True,
                       truncation=True, max_length=CHUNK_AA + 2)
        inp = {k: v.to(DEVICE) for k, v in inp.items()}
        with torch.no_grad():
            out = self.m(**inp)
        return out.last_hidden_state[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)

    def encode_full(self, seq):
        """CHUNK-POOL: residue-weighted mean over <=CHUNK_AA windows (no residue lost)."""
        chunks = [seq[i:i + CHUNK_AA] for i in range(0, len(seq), CHUNK_AA)]
        vecs, weights = [], []
        for c in chunks:
            if len(c) < 1:
                continue
            vecs.append(self._embed_window(c))
            weights.append(len(c))
        if not vecs:
            return None
        V = np.vstack(vecs)
        w = np.asarray(weights, dtype=np.float64)
        return (V * w[:, None]).sum(0) / w.sum()


# ---------------------------------------------------------------------------
# Feature assembly: per-target ESM-2 embedding (cached) CONCAT per-ligand ECFP4.
# Returns X (n x [prot_dim + MORGAN_BITS]), y, groups (scaffold), genes, families.
# ---------------------------------------------------------------------------
def assemble_features(targets, pairs, enc):
    # cache target protein embeddings
    prot_emb = {}
    for gene, t in targets.items():
        try:
            v = enc.encode_full(t["seq"])
            if v is None:
                print(f"[warn] protein embed failed for {gene}", flush=True)
                continue
            prot_emb[gene] = v
            print(f"[prot] {gene}: emb dim {v.shape[0]} (chunks={t.get('n_chunks')})",
                  flush=True)
        except Exception as e:
            print(f"[warn] protein embed error {gene}: {e}", flush=True)

    # cache ligand fingerprints
    lig_cache = {}
    rows = []
    n_bad = 0
    for p in pairs:
        if p["gene"] not in prot_emb:
            continue
        smi = p["smiles"]
        v = lig_cache.get(smi)
        if v is None:
            v = ecfp4(smi)
            if v is None:
                n_bad += 1
                continue
            lig_cache[smi] = v
        rows.append(p)
    print(f"[feat] {len(rows)} usable pairs ({n_bad} unparseable ligands); "
          f"{len(prot_emb)} target embeddings", flush=True)

    X = np.vstack([np.concatenate([prot_emb[p["gene"]], lig_cache[p["smiles"]]])
                   for p in rows]) if rows else np.zeros((0, 0))
    X_lig = np.vstack([lig_cache[p["smiles"]] for p in rows]) if rows else np.zeros((0, 0))
    y = np.array([p["label"] for p in rows], dtype=int)
    genes = np.array([p["gene"] for p in rows])
    families = np.array([p["family"] for p in rows])
    scaffolds = np.array([murcko_scaffold(p["smiles"]) or f"__none_{i}"
                          for i, p in enumerate(rows)])
    return X, X_lig, y, genes, families, scaffolds, rows


# ---------------------------------------------------------------------------
# MLP classifier (torch). 2-3 layers + dropout on [prot_emb (+) ECFP4]. This is
# the trained DTI head on a frozen ESM-2 protein tower + FP ligand tower = the fine-tune.
# ---------------------------------------------------------------------------
def train_mlp(Xtr, ytr, Xte, in_dim):
    import torch
    import torch.nn as nn
    torch.manual_seed(SEED)
    layers, prev = [], in_dim
    for h in MLP_HIDDEN:
        layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(MLP_DROPOUT)]
        prev = h
    layers += [nn.Linear(prev, 1)]
    model = nn.Sequential(*layers).to(DEVICE)

    # standardize features on train stats
    mu = Xtr.mean(0, keepdims=True)
    sd = Xtr.std(0, keepdims=True) + 1e-6
    Xtr_n = (Xtr - mu) / sd
    Xte_n = (Xte - mu) / sd

    xb = torch.tensor(Xtr_n, dtype=torch.float32, device=DEVICE)
    yb = torch.tensor(ytr, dtype=torch.float32, device=DEVICE).unsqueeze(1)
    # class weighting for imbalance
    n_pos = float(ytr.sum())
    n_neg = float(len(ytr) - n_pos)
    pos_weight = torch.tensor([n_neg / max(n_pos, 1.0)], dtype=torch.float32, device=DEVICE)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(model.parameters(), lr=MLP_LR, weight_decay=MLP_WD)

    n = xb.shape[0]
    model.train()
    for ep in range(MLP_EPOCHS):
        perm = torch.randperm(n, device=DEVICE)
        for i in range(0, n, MLP_BATCH):
            idx = perm[i:i + MLP_BATCH]
            opt.zero_grad()
            out = model(xb[idx])
            loss = loss_fn(out, yb[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(
            torch.tensor(Xte_n, dtype=torch.float32, device=DEVICE))).cpu().numpy().reshape(-1)
    return scores


def train_gbt(Xtr_lig, ytr, Xte_lig):
    """Morgan-FP + GradientBoosting ligand-only BASELINE."""
    from sklearn.ensemble import GradientBoostingClassifier
    clf = GradientBoostingClassifier(random_state=SEED)
    clf.fit(Xtr_lig, ytr)
    return clf.predict_proba(Xte_lig)[:, 1]


# ---------------------------------------------------------------------------
# EVAL 1 — Murcko scaffold split (GroupKFold over scaffolds, pooled across channels).
# Pooled out-of-fold predictions -> per-family + overall AUROC + EF5, MLP vs FP-GBT.
# ---------------------------------------------------------------------------
def eval_scaffold_split(X, X_lig, y, genes, families, scaffolds):
    from sklearn.model_selection import GroupKFold
    n = len(y)
    folds = max(2, min(N_FOLDS, int(y.sum()), int(n - y.sum())))
    uniq = sorted(set(scaffolds))
    if len(uniq) < folds:
        folds = max(2, len(uniq))
    gmap = {s: i for i, s in enumerate(uniq)}
    groups = np.array([gmap[s] for s in scaffolds])

    oof_mlp = np.full(n, np.nan)
    oof_gbt = np.full(n, np.nan)
    gkf = GroupKFold(n_splits=folds)
    for fold, (tr, te) in enumerate(gkf.split(X, y, groups)):
        if y[tr].sum() == 0 or y[tr].sum() == len(tr):
            continue
        oof_mlp[te] = train_mlp(X[tr], y[tr], X[te], X.shape[1])
        try:
            oof_gbt[te] = train_gbt(X_lig[tr], y[tr], X_lig[te])
        except Exception as e:
            print(f"[warn] GBT fold {fold} failed: {e}", flush=True)
        print(f"[scaffold] fold {fold}: train {len(tr)} / test {len(te)} "
              f"(pos_test={int(y[te].sum())})", flush=True)

    def summarize(oof):
        mask = ~np.isnan(oof)
        out = {"overall": {}, "per_family": {}}
        if mask.sum() >= 4 and 0 < y[mask].sum() < mask.sum():
            out["overall"] = {"auroc": auroc(y[mask], oof[mask]),
                              "ef5": enrichment_factor(y[mask], oof[mask]),
                              "n": int(mask.sum()), "n_pos": int(y[mask].sum())}
        for fam in sorted(set(families)):
            fm = mask & (families == fam)
            if fm.sum() >= 4 and 0 < y[fm].sum() < fm.sum():
                out["per_family"][fam] = {
                    "auroc": auroc(y[fm], oof[fm]),
                    "ef5": enrichment_factor(y[fm], oof[fm]),
                    "n": int(fm.sum()), "n_pos": int(y[fm].sum())}
        return out

    return {"folds": folds, "n_scaffolds": len(uniq),
            "mlp": summarize(oof_mlp), "fp_gbt_baseline": summarize(oof_gbt)}


# ---------------------------------------------------------------------------
# EVAL 2 — Leave-One-Channel-Out (LOCO). For each held-out channel: train on ALL
# OTHER channels, test on the held-out channel. Per-channel AUROC + EF5 (MLP + baseline).
# This is the real cross-channel DTI-generalization test (not within-channel QSAR).
# ---------------------------------------------------------------------------
def eval_loco(X, X_lig, y, genes, families):
    out = {}
    present = sorted(set(genes))
    for ch in LOCO_CHANNELS:
        if ch not in present:
            out[ch] = {"note": "channel not in built corpus -- skipped"}
            continue
        te = genes == ch
        tr = ~te
        if y[tr].sum() < 5 or (len(tr) - y[tr].sum()) < 5:
            out[ch] = {"note": "too few train examples after holding out channel"}
            continue
        if y[te].sum() == 0 or y[te].sum() == te.sum():
            out[ch] = {"note": "held-out channel has only one class"}
            continue
        try:
            s_mlp = train_mlp(X[tr], y[tr], X[te], X.shape[1])
            rec = {"family": families[te][0] if te.sum() else None,
                   "n_test": int(te.sum()), "n_test_pos": int(y[te].sum()),
                   "n_train": int(tr.sum()),
                   "mlp": {"auroc": auroc(y[te], s_mlp),
                           "ef5": enrichment_factor(y[te], s_mlp)}}
            try:
                s_gbt = train_gbt(X_lig[tr], y[tr], X_lig[te])
                rec["fp_gbt_baseline"] = {"auroc": auroc(y[te], s_gbt),
                                          "ef5": enrichment_factor(y[te], s_gbt)}
            except Exception as e:
                rec["fp_gbt_baseline"] = {"error": str(e)}
            out[ch] = rec
            print(f"[loco] held-out {ch} ({rec['family']}): "
                  f"MLP AUROC={rec['mlp']['auroc']} EF5={rec['mlp']['ef5']} "
                  f"(test n={rec['n_test']}, pos={rec['n_test_pos']})", flush=True)
        except Exception as e:
            out[ch] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[warn] LOCO {ch} failed: {e}\n{traceback.format_exc()[:500]}", flush=True)
    return out


def section(name, fn, store, *args):
    try:
        store[name] = fn(*args)
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        store[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1500]}", flush=True)


# ---------------------------------------------------------------------------
# Success criterion: does the fine-tuned MLP clear the scorecard bar
# (AUROC>=0.80 OR EF5>=5x on held-out) on the scaffold split AND/OR LOCO?
# ---------------------------------------------------------------------------
def evaluate_success(scaffold, loco):
    def clears(auc, ef):
        return bool((auc is not None and auc >= SUCCESS_AUROC) or
                    (ef is not None and ef >= SUCCESS_EF))

    checks = {"criterion": f"AUROC>={SUCCESS_AUROC} OR EF5>={SUCCESS_EF} on held-out",
              "reference_zeroshot_balm_plapt": ZEROSHOT_REF,
              "reference_trunc_test_probe_small_panel": PROBE_REF}

    # scaffold-split overall (MLP)
    ov = (((scaffold or {}).get("mlp") or {}).get("overall") or {})
    sc_auc, sc_ef = ov.get("auroc"), ov.get("ef5")
    checks["scaffold_overall"] = {"auroc": sc_auc, "ef5": sc_ef,
                                  "clears": clears(sc_auc, sc_ef)}

    # LOCO per channel (MLP)
    loco_pass = {}
    for ch, rec in (loco or {}).items():
        if isinstance(rec, dict) and "mlp" in rec:
            a, e = rec["mlp"].get("auroc"), rec["mlp"].get("ef5")
            loco_pass[ch] = {"auroc": a, "ef5": e, "clears": clears(a, e)}
    checks["loco_per_channel"] = loco_pass
    n_loco_pass = sum(1 for v in loco_pass.values() if v["clears"])
    checks["loco_channels_cleared"] = f"{n_loco_pass}/{len(loco_pass)}"

    overall_pass = checks["scaffold_overall"]["clears"] or n_loco_pass > 0
    checks["HEADLINE"] = (
        f"Fine-tuned cross-channel MLP {'CLEARS' if overall_pass else 'does NOT clear'} the "
        f"scorecard success bar (AUROC>={SUCCESS_AUROC} OR EF5>={SUCCESS_EF}). "
        f"Scaffold-split overall AUROC={sc_auc} EF5={sc_ef}; "
        f"LOCO channels cleared {n_loco_pass}/{len(loco_pass)}. "
        f"Reference: zero-shot BALM/PLAPT ion_channel = {ZEROSHOT_REF}; "
        f"trunc_test per-target probe (small panel) = {PROBE_REF}.")
    checks["pass"] = overall_pass
    return checks


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    results = {
        "task": ("Ion-channel binder FINE-TUNE: train a cross-channel DTI model (frozen "
                 "ESM-2-650M protein tower + Morgan-FP ligand tower -> MLP head) on a pooled "
                 "ChEMBL+GtoPdb ion-channel corpus; test genuine generalization via Murcko "
                 "scaffold split and Leave-One-Channel-Out. 'The fine-tune is the lever.'"),
        "device": DEVICE,
        "esm2_repo": ESM2_REPO,
        "model": {
            "protein_tower": "ESM-2-650M mean-pooled residue embedding (frozen, chunk-pooled, full length)",
            "ligand_tower": f"Morgan-FP ECFP4 (radius {MORGAN_RADIUS}, {MORGAN_BITS} bit)",
            "head": f"MLP {MLP_HIDDEN} + ReLU + dropout {MLP_DROPOUT} (BCEWithLogits, pos-weighted)",
            "baseline": "Morgan-FP + GradientBoostingClassifier (ligand-only)",
            "is_real_dti": "protein embedding VARIES across the ion-channel panel -> cross-channel DTI, not per-target QSAR",
        },
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "chembl_timeout_s": CHEMBL_TIMEOUT,
            "binding_types": BINDING_TYPES, "no_max_actives_cap": True,
            "chunk_aa": CHUNK_AA, "n_folds": N_FOLDS, "ef_frac": EF_FRAC, "seed": SEED,
            "mlp": {"hidden": MLP_HIDDEN, "dropout": MLP_DROPOUT, "epochs": MLP_EPOCHS,
                    "lr": MLP_LR, "weight_decay": MLP_WD, "batch": MLP_BATCH},
            "success_auroc": SUCCESS_AUROC, "success_ef": SUCCESS_EF,
            "loco_channels": LOCO_CHANNELS,
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]} for g, m in PANEL.items()},
        "references": {"zeroshot_balm_plapt_ion_channel": ZEROSHOT_REF,
                       "trunc_test_per_target_probe_small_panel": PROBE_REF},
    }

    # --- Build pooled corpus (ChEMBL + GtoPdb), guarded ---
    build_store = {}
    section("build", build_corpus, build_store)
    built = build_store.get("build")
    if isinstance(built, dict) and "error" in built:
        results["build_error"] = built["error"]
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] build failed; wrote {OUT}", flush=True)
        return
    targets, pairs, dropped, gtopdb_stats = built
    results["dropped_targets"] = dropped
    results["gtopdb_merge"] = gtopdb_stats

    # corpus summary
    per_chan = defaultdict(lambda: {"actives": 0, "decoys": 0})
    per_fam = defaultdict(lambda: {"actives": 0, "decoys": 0})
    src_counts = defaultdict(int)
    for p in pairs:
        slot = "actives" if p["label"] == 1 else "decoys"
        per_chan[p["gene"]][slot] += 1
        per_fam[p["family"]][slot] += 1
        src_counts[p["source"]] += 1
    n_compounds = len({p["canon"] for p in pairs})
    results["corpus"] = {
        "n_targets_built": len(targets),
        "n_pairs": len(pairs),
        "n_unique_compounds": n_compounds,
        "per_channel": {g: dict(v) for g, v in sorted(per_chan.items())},
        "per_family": {f: dict(v) for f, v in sorted(per_fam.items())},
        "source_counts": dict(src_counts),
        "built_targets": {g: {"family": t["family"], "chembl_id": t.get("chembl_id"),
                              "seq_len": t.get("seq_len"), "n_chunks": t.get("n_chunks"),
                              "decoy_source": t.get("decoy_source")}
                          for g, t in targets.items()},
    }
    print(f"[corpus] {len(targets)} targets, {len(pairs)} pairs, "
          f"{n_compounds} unique compounds; sources={dict(src_counts)}", flush=True)

    if len(targets) < 2 or len(pairs) < 50:
        results["runtime_sec"] = round(time.time() - t0, 1)
        results["abort"] = "too few targets/pairs to train a cross-channel model"
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] {results['abort']}; wrote {OUT}", flush=True)
        return

    # --- Load ESM-2 + assemble features (guarded) ---
    enc_store = {}
    section("encoder", Esm2Encoder, enc_store)
    enc = enc_store.get("encoder")
    if not isinstance(enc, Esm2Encoder):
        results["encoder_error"] = enc_store.get("encoder")
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] ESM-2 load failed; wrote {OUT}", flush=True)
        return

    feat_store = {}
    section("features", assemble_features, feat_store, targets, pairs, enc)
    feats = feat_store.get("features")
    if isinstance(feats, dict) and "error" in feats:
        results["feature_error"] = feats["error"]
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] feature assembly failed; wrote {OUT}", flush=True)
        return
    X, X_lig, y, genes, families, scaffolds, rows = feats
    results["feature_matrix"] = {"n": int(X.shape[0]),
                                 "dim_full": int(X.shape[1]) if X.ndim == 2 else None,
                                 "dim_ligand": int(X_lig.shape[1]) if X_lig.ndim == 2 else None,
                                 "n_pos": int(y.sum()), "n_neg": int(len(y) - y.sum())}
    if X.shape[0] < 50:
        results["runtime_sec"] = round(time.time() - t0, 1)
        results["abort"] = "too few usable feature rows"
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] {results['abort']}; wrote {OUT}", flush=True)
        return

    # --- EVAL 1: Murcko scaffold split (guarded) ---
    sc_store = {}
    section("scaffold_split", eval_scaffold_split, sc_store, X, X_lig, y, genes, families, scaffolds)
    results["scaffold_split"] = sc_store.get("scaffold_split")

    # --- EVAL 2: Leave-One-Channel-Out (guarded) ---
    loco_store = {}
    section("loco", eval_loco, loco_store, X, X_lig, y, genes, families)
    results["loco"] = loco_store.get("loco")

    # --- Success criterion check (the headline) ---
    try:
        results["success_check"] = evaluate_success(
            results.get("scaffold_split"), results.get("loco"))
    except Exception as e:
        results["success_check_error"] = f"{type(e).__name__}: {e}"

    results["runtime_sec"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("success_check", {}), indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
