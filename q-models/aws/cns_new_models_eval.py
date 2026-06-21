"""CNS-NEW-MODELS DTI benchmark: does a NEW, broader-pretrained DTI model beat the
BALM/PLAPT zero-shot CHANCE result on ion channels?

WHY (the gap we are attacking)
==============================
On the 19-target CNS panel (aws/cns_dti_benchmark_eval.py) the two current
binder-triage winners are ZERO-SHOT and BindingDB-pretrained:
  family       BALM   PLAPT
  kinase       0.80   0.77   <- well represented in BindingDB
  mtor_pathway 0.72   0.74
  gpcr         0.58   0.66
  ion_channel  0.50   0.50   <- CHANCE. Nav/Cav/NMDA are BindingDB-poor.
And results/trunc_test_characterization.md showed the ion-channel signal IS
learnable (a supervised scaffold-split probe hits ~0.92) -- so the gap is
TRAINING-DATA COVERAGE / SUPERVISION, not protein-sequence truncation. So we
do NOT chase long-context protein encoders. We test a model that plausibly
transfers BETTER to ion channels:

  DTIAM (CSUBioGroup, Nature Communications 2025; Apache-2.0)
  -----------------------------------------------------------
  github.com/CSUBioGroup/DTIAM. Self-supervised dual-tower DTI foundation model:
    * DRUG tower = BerMol, self-supervised PRETRAINED ON 1.6M ChEMBL COMPOUNDS
      (GuacaMol) via MLM + molecular-descriptor + functional-group prediction
      -> BROADER bioactivity-chemistry coverage than BindingDB pairs (category a).
    * PROTEIN tower = ESM-2 (UniRef; ~138M sequences) embeddings of the raw
      amino-acid sequence.
  Inputs are SMILES + protein sequence ONLY (no 3D structure). This is a
  genuinely-new 2025 DTI FM (category c) AND, used as a per-target probe below,
  a few-shot/target-conditioned adapter (category b) -- the three transfer
  levers the scouting brief asked for.

HOW WE SCORE IT (honest about the API)
======================================
DTIAM ships pretrained encoder weights (BerMolModel_base.pkl) but its public
DTI path (training_validation.py dti <dataset> <setting>) trains an AutoGluon
head on a FIXED benchmark (yamanishi_08 / hetionet); there is no portable
zero-shot score(seq, smiles). So we use DTIAM as a FEATURE EXTRACTOR and run
the readout the trunc_test finding endorses -- a per-target FEW-SHOT, SCAFFOLD-
SPLIT probe:
  for each target:
    x = concat[ BerMol(SMILES) , ESM2_meanpool(sequence) ]   (protein vec is
        constant per target, so it is the molecule features that carry the
        per-target signal; we keep the protein block so the design matches a
        true two-tower adapter and generalizes if multiple targets are pooled)
    y = 1 for actives, 0 for decoys
    Murcko-scaffold-grouped CV (GroupKFold over scaffolds; folds collapse to
        leave-scaffold-out) -> out-of-fold P(active) -> AUROC.
This is a TARGET-CONDITIONED few-shot probe (a handful of that target's actives
lift the model), which is exactly the supervised lever the brief favors. It is
NOT zero-shot, so the head-to-head is labeled: DTIAM-fewshot vs BALM/PLAPT-zeroshot.
A target needs >= MIN_PROBE_PER_CLASS in each class after scaffold grouping or it
is reported as probe_skipped (never silently 0.5).

We ALSO compute a ZERO-SHOT readout for a fair like-for-like line: cosine
similarity between the (mean-pooled) BerMol drug vector and the ESM-2 protein
vector projected to a shared dim is NOT meaningful out of the box (the towers
are not contrastively aligned in the released base encoders), so we do NOT
fabricate a zero-shot DTIAM number -- we only report what the released weights
actually support (the few-shot probe). If a future aligned DTIAM checkpoint is
dropped in, add a score_dtiam_zeroshot() block; the harness already guards it.

DATA / PANEL / DECOYS / AUROC / FAMILY-AGGREGATE machinery is reused VERBATIM
from aws/cns_dti_benchmark_eval.py (same 19-target panel, same ChEMBL pull,
same DUD-E-style property-matched decoys, same rank-sum AUROC, same per-family
aggregate). Every build / load / scoring / aggregation step is try/except-guarded
so a single ChEMBL/UniProt/weights hiccup cannot sink the run -- partial results
still upload. Writes JSON to env OUT (default /root/cnsnew_out/cns_new_models_result.json).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/cnsnew_out/cns_new_models_result.json"))
DTIAM_DIR = Path(os.environ.get("DTIAM_DIR", "/opt/DTIAM"))
BERMOL_CKPT = Path(os.environ.get("BERMOL_CKPT", "/opt/weights/BerMolModel_base.pkl"))
ESM2_MODEL = os.environ.get("ESM2_MODEL", "facebook/esm2_t33_650M_UR50D")

# Knobs (env-overridable so the panel can be tuned without editing the file).
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))    # >= this = active (~<=1 uM)
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))  # <= this = ChEMBL inactive
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "30"))            # drop target below this
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "60"))            # cap actives/target (runtime)
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))         # decoys <= ratio x n_actives
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))              # need at least this many decoys
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))  # matched-decoy dissimilarity
PROBE_FOLDS = int(os.environ.get("PROBE_FOLDS", "5"))             # scaffold-grouped CV folds
MIN_PROBE_PER_CLASS = int(os.environ.get("MIN_PROBE_PER_CLASS", "8"))  # need >= this actives & decoys
ESM2_MAXLEN = int(os.environ.get("ESM2_MAXLEN", "1022"))         # ESM-2 context (truncation recorded)
SEED = int(os.environ.get("SEED", "20260614"))
RNG = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# CNS TARGET PANEL -- reused VERBATIM from aws/cns_dti_benchmark_eval.py.
# 19 CNS-relevant targets across four families, weighted toward TSC2/mTOR +
# epilepsy/excitability ion channels. gene -> (uniprot, fallback_chembl, family).
# Families: "ion_channel" | "mtor_pathway" | "gpcr" | "kinase".
# (SCN5A/Nav1.5 included as the CARDIAC selectivity reference -- off-CNS-target.)
# ---------------------------------------------------------------------------
PANEL = {
    # --- TSC2 / mTOR pathway ---
    "MTOR":    {"uniprot": "P42345", "chembl": "CHEMBL2842",    "family": "mtor_pathway"},
    "PKM":     {"uniprot": "P14618", "chembl": "CHEMBL2107",    "family": "mtor_pathway"},  # PKM2
    "PPARD":   {"uniprot": "Q03181", "chembl": "CHEMBL3979",    "family": "mtor_pathway"},
    "AKT1":    {"uniprot": "P31749", "chembl": "CHEMBL4282",    "family": "mtor_pathway"},
    "RHEB":    {"uniprot": "Q15382", "chembl": None,            "family": "mtor_pathway"},  # likely sparse
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

# Zero-shot reference baselines from the BALM/PLAPT CNS run (per-family mean AUROC).
# DTIAM is FEW-SHOT (per-target probe), so the head-to-head is labeled accordingly.
ZEROSHOT_REFERENCE = {
    "BALM_zeroshot":  {"kinase": 0.80, "mtor_pathway": 0.72, "gpcr": 0.58, "ion_channel": 0.50},
    "PLAPT_zeroshot": {"kinase": 0.77, "mtor_pathway": 0.74, "gpcr": 0.66, "ion_channel": 0.50},
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
# UniProt WT-sequence fetch (pattern from aws/cns_dti_benchmark_eval.py).
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "cns-new-models-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL data access via chembl_webresource_client (Django-QuerySet style).
# Reused verbatim from aws/cns_dti_benchmark_eval.py.
# ---------------------------------------------------------------------------
def resolve_chembl_id(meta):
    """Resolve a single-protein human ChEMBL target id by UniProt accession.
    Falls back to the hardcoded id in the panel. Returns (chembl_id, source)."""
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
    Returns {smiles: max_pchembl} (best/strongest pchembl per unique compound)."""
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
# RDKit property helpers for DUD-E-style property-matched decoys.
# Reused verbatim from aws/cns_dti_benchmark_eval.py.
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


def murcko_scaffold(smi):
    """Bemis-Murcko scaffold SMILES (for scaffold-grouped CV). None if RDKit fails."""
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
        return scaf if scaf else "EMPTY"
    except Exception:
        return None


def property_matched_decoys(active_smiles, active_props, candidate_pool, n_needed):
    """DUD-E-style: pick decoys from candidate_pool that match the active-set property
    envelope (MW/logP/HBD/HBA within tolerance of the active means) but are
    chemically DISSIMILAR (max Tanimoto to any active < DECOY_TANIMOTO_MAX).
    Reused verbatim from aws/cns_dti_benchmark_eval.py."""
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
                continue  # too similar to a known binder -> not a clean decoy
        picked.append(smi)
        if len(picked) >= n_needed:
            break
    return picked


# ---------------------------------------------------------------------------
# Build per-target {actives, decoys, seq} sets. Reused verbatim from
# aws/cns_dti_benchmark_eval.py (returns built panels + dropped log).
# ---------------------------------------------------------------------------
def build_panels():
    built = {}        # gene -> {chembl_id, family, seq, seq_len, seq_source, actives[], decoys[], decoy_source}
    dropped = {}      # gene -> reason
    raw_actives = {}  # gene -> {smiles: pchembl} (kept for cross-target decoy pool)
    raw_inactives = {}  # gene -> {smiles: pchembl}

    # Pass 1: resolve ids + fetch activities, partition into actives / inactives.
    for gene, meta in PANEL.items():
        try:
            cid, src = resolve_chembl_id(meta)
            if not cid:
                dropped[gene] = "no ChEMBL target id (resolve + fallback both empty)"
                continue
            best = fetch_activities(cid)
            actives = {s: v for s, v in best.items() if v >= ACTIVE_PCHEMBL}
            inactives = {s: v for s, v in best.items() if v <= INACTIVE_PCHEMBL}
            # cap actives to MAX_ACTIVES (strongest first)
            if len(actives) > MAX_ACTIVES:
                top = sorted(actives.items(), key=lambda kv: -kv[1])[:MAX_ACTIVES]
                actives = dict(top)
            raw_actives[gene] = actives
            raw_inactives[gene] = inactives
            built[gene] = {"chembl_id": cid, "chembl_id_source": src,
                           "family": meta["family"], "uniprot": meta["uniprot"],
                           "n_actives_pre_drop": len(actives),
                           "n_chembl_inactives": len(inactives)}
            print(f"[chembl] {gene} ({cid}, {src}): "
                  f"{len(actives)} actives / {len(inactives)} inactives", flush=True)
        except Exception as e:
            dropped[gene] = f"fetch error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} fetch failed: {e}", flush=True)

    # Drop sparsity (too few actives) before any sequence fetch / decoy building.
    for gene in list(built.keys()):
        n = built[gene]["n_actives_pre_drop"]
        if n < MIN_ACTIVES:
            dropped[gene] = f"sparse: {n} actives < MIN_ACTIVES={MIN_ACTIVES}"
            built.pop(gene)
            raw_actives.pop(gene, None)

    # Global cross-target active pool (for property-matched fallback decoys).
    global_pool = []
    for g, acts in raw_actives.items():
        global_pool.extend(acts.keys())

    # Pass 2: build decoys + fetch sequence for surviving targets.
    for gene in list(built.keys()):
        try:
            meta = PANEL[gene]
            actives = raw_actives[gene]
            n_act = len(actives)
            n_decoy_target = max(MIN_DECOYS, int(round(n_act * 1.0)))  # aim ~1:1
            n_decoy_cap = int(round(n_act * DECOY_RATIO))              # never exceed ratio
            n_decoy_target = min(n_decoy_target, n_decoy_cap)

            inactives = raw_inactives.get(gene, {})
            decoy_smiles = []
            decoy_source = None
            if len(inactives) >= MIN_DECOYS:
                # (1) true ChEMBL inactives for this target (cleanest).
                items = sorted(inactives.items(), key=lambda kv: kv[1])  # weakest first
                decoy_smiles = [s for s, _ in items[:n_decoy_cap]]
                decoy_source = "chembl_inactives_same_target"
            else:
                # (2) property-matched cross-target decoys (DUD-E-style).
                active_smiles = set(actives.keys())
                active_props = [p for p in (mol_props(s) for s in actives) if p is not None]
                cand = [s for g2, acts in raw_actives.items() if g2 != gene
                        for s in acts.keys()]
                if not cand:
                    cand = list(global_pool)
                decoy_smiles = property_matched_decoys(
                    active_smiles, active_props, cand, n_decoy_cap)
                decoy_source = "property_matched_cross_target_decoys"
                # top up with any same-target inactives we did have
                for s in inactives:
                    if len(decoy_smiles) >= n_decoy_cap:
                        break
                    if s not in decoy_smiles:
                        decoy_smiles.append(s)

            if len(decoy_smiles) < MIN_DECOYS:
                dropped[gene] = (f"no usable decoy set "
                                 f"({len(decoy_smiles)} < MIN_DECOYS={MIN_DECOYS}; "
                                 f"source={decoy_source})")
                built.pop(gene)
                continue

            # Sequence (truncation recorded via seq_len; ESM-2 caps at ESM2_MAXLEN).
            seq, seq_source = None, None
            try:
                seq = fetch_uniprot_seq(meta["uniprot"])
                if seq and len(seq) > 30:
                    seq_source = "uniprot_rest"
            except Exception as e:
                print(f"[warn] UniProt fetch failed for {gene} ({meta['uniprot']}): {e}",
                      flush=True)
            if not seq:
                dropped[gene] = f"no protein sequence (UniProt fetch failed for {meta['uniprot']})"
                built.pop(gene)
                continue

            built[gene].update({
                "seq": seq, "seq_len": len(seq), "seq_source": seq_source,
                "actives": list(actives.keys()),
                "decoys": decoy_smiles,
                "decoy_source": decoy_source,
                "n_actives": len(actives), "n_decoys": len(decoy_smiles),
            })
            print(f"[panel] {gene}: {len(actives)} actives / {len(decoy_smiles)} decoys "
                  f"({decoy_source}); seq_len={len(seq)}", flush=True)
        except Exception as e:
            dropped[gene] = f"decoy/seq build error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} build failed: {e}\n{traceback.format_exc()[:600]}",
                  flush=True)
            built.pop(gene, None)

    return built, dropped


# ---------------------------------------------------------------------------
# DTIAM feature towers.
#   DrugTower  = BerMol (self-supervised on 1.6M ChEMBL compounds) -> per-SMILES vec.
#   ProtTower  = ESM-2 mean-pooled embedding -> per-sequence vec (constant per target).
# Loaders are defensive: BerMol's repo layout has shifted across commits, so we try a
# few import / call shapes and fall back to a Morgan-FP drug vector ONLY if BerMol cannot
# be loaded (recorded explicitly in the result so a fallback is never silent).
# ---------------------------------------------------------------------------
class DrugTower:
    """BerMol drug encoder from the cloned DTIAM repo + released BerMolModel_base.pkl.
    Exposes .embed(list_of_smiles) -> np.ndarray [n, d]. Records .backend / .dim."""

    def __init__(self):
        self.backend = None
        self.dim = None
        self._impl = None
        sys.path.insert(0, str(DTIAM_DIR))
        sys.path.insert(0, str(DTIAM_DIR / "code"))
        sys.path.insert(0, str(DTIAM_DIR / "code" / "BerMol"))
        self._try_bermol()
        if self._impl is None:
            self._try_morgan_fallback()

    def _try_bermol(self):
        """Try the BerMol API. Guarded across plausible entry points; on any failure
        we leave self._impl=None so the Morgan fallback engages (recorded)."""
        try:
            import torch  # noqa: F401
            from importlib import import_module
            mod = None
            for name in ("BerMol", "bermol", "model", "models", "infer", "inference"):
                try:
                    mod = import_module(name)
                    break
                except Exception:
                    continue
            if mod is None:
                print("[bermol] no importable BerMol module; using Morgan fallback", flush=True)
                return
            loader = None
            for attr in ("load_model", "load_pretrained", "BerMol", "get_model",
                         "load_bermol", "Model"):
                if hasattr(mod, attr):
                    loader = getattr(mod, attr)
                    break
            if loader is None:
                print("[bermol] module found but no loader attr; Morgan fallback", flush=True)
                return
            if not BERMOL_CKPT.exists():
                print(f"[bermol] checkpoint missing at {BERMOL_CKPT}; Morgan fallback",
                      flush=True)
                return
            # Try a few constructor signatures.
            model = None
            for call in (
                lambda: loader(str(BERMOL_CKPT)),
                lambda: loader(ckpt=str(BERMOL_CKPT)),
                lambda: loader(model_path=str(BERMOL_CKPT)),
                lambda: loader(),
            ):
                try:
                    model = call()
                    break
                except Exception:
                    continue
            if model is None:
                print("[bermol] loader present but no signature worked; Morgan fallback",
                      flush=True)
                return
            self._impl = model
            self.backend = "bermol"
            print("[bermol] loaded BerMol drug encoder", flush=True)
        except Exception as e:
            print(f"[bermol] load failed ({type(e).__name__}: {e}); Morgan fallback",
                  flush=True)
            self._impl = None

    def _try_morgan_fallback(self):
        # 2048-bit Morgan FP as a transparent, recorded fallback drug featurization so the
        # probe still runs and the result is honest about NOT using BerMol weights.
        self.backend = "morgan_fp_fallback"
        self.dim = 2048
        print("[drug] using Morgan-FP fallback drug featurization "
              "(BerMol weights/API unavailable on-instance)", flush=True)

    def embed(self, smiles_list):
        if self.backend == "bermol":
            # Try a couple of common embed call shapes; if all fail, raise (the section
            # guard records the error -- we do NOT silently swap featurizers mid-run).
            for call in (
                lambda: self._impl.embed(smiles_list),
                lambda: self._impl.encode(smiles_list),
                lambda: self._impl(smiles_list),
                lambda: self._impl.get_features(smiles_list),
            ):
                try:
                    out = call()
                    arr = np.asarray(out, dtype=float)
                    if arr.ndim == 1:
                        arr = arr.reshape(len(smiles_list), -1)
                    self.dim = arr.shape[1]
                    return arr
                except Exception:
                    continue
            raise RuntimeError("BerMol loaded but no embed signature returned features")
        # Morgan fallback
        from rdkit import Chem
        from rdkit.Chem import AllChem
        import numpy as _np
        feats = []
        for smi in smiles_list:
            m = Chem.MolFromSmiles(smi)
            if m is None:
                feats.append(_np.zeros(self.dim, dtype=float))
                continue
            fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, self.dim)
            a = _np.zeros(self.dim, dtype=float)
            from rdkit.DataStructs import ConvertToNumpyArray
            ConvertToNumpyArray(fp, a)
            feats.append(a)
        return _np.vstack(feats)


class ProtTower:
    """ESM-2 mean-pooled embedding for a protein sequence. Records truncation."""

    def __init__(self):
        import torch
        from transformers import AutoTokenizer, AutoModel
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(ESM2_MODEL)
        self.model = AutoModel.from_pretrained(ESM2_MODEL).to(DEVICE).eval()
        self.dim = self.model.config.hidden_size

    def embed_one(self, seq):
        seq = seq.strip().replace(" ", "")
        truncated = len(seq) > ESM2_MAXLEN
        enc = self.tok(seq, return_tensors="pt", truncation=True,
                       max_length=ESM2_MAXLEN + 2).to(DEVICE)  # +2 for BOS/EOS
        with self.torch.no_grad():
            out = self.model(**enc)
        h = out.last_hidden_state[0]           # [L, d]
        mask = enc["attention_mask"][0].unsqueeze(-1).float()
        vec = (h * mask).sum(0) / mask.sum().clamp(min=1.0)
        return vec.detach().cpu().numpy().astype(float), truncated


# ---------------------------------------------------------------------------
# Per-target FEW-SHOT, SCAFFOLD-SPLIT probe over DTIAM features.
#   x = [ BerMol(SMILES) | ESM2(seq) ];  y = active(1)/decoy(0).
#   Murcko-scaffold-grouped CV -> out-of-fold P(active) -> AUROC.
# Returns {gene: {auroc, n_actives, n_decoys, family, drug_backend, ...}}.
# ---------------------------------------------------------------------------
def score_dtiam_fewshot(panels):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import GroupKFold

    drug = DrugTower()
    prot = ProtTower()
    out = {}
    for gene, p in panels.items():
        try:
            actives = list(p["actives"])
            decoys = list(p["decoys"])
            smiles = actives + decoys
            y = np.array([1] * len(actives) + [0] * len(decoys), dtype=int)

            # Scaffold groups (for grouped CV); compounds with a None scaffold get
            # unique singleton groups so they never leak across folds.
            scafs = [murcko_scaffold(s) for s in smiles]
            groups, gmap, nxt = [], {}, 0
            for i, sc in enumerate(scafs):
                key = sc if sc is not None else f"__none_{i}"
                if key not in gmap:
                    gmap[key] = nxt
                    nxt += 1
                groups.append(gmap[key])
            groups = np.array(groups)

            # Drug features (towers).
            dfeat = drug.embed(smiles)                       # [n, dd]
            pvec, truncated = prot.embed_one(p["seq"])       # [dp]
            pfeat = np.tile(pvec, (len(smiles), 1))          # [n, dp]
            X = np.hstack([dfeat, pfeat])

            # Need enough of each class AND >= 2 scaffold groups to do grouped CV.
            n_pos = int((y == 1).sum())
            n_neg = int((y == 0).sum())
            n_groups = len(set(groups.tolist()))
            if n_pos < MIN_PROBE_PER_CLASS or n_neg < MIN_PROBE_PER_CLASS or n_groups < 2:
                out[gene] = {
                    "family": p["family"], "chembl_id": p["chembl_id"],
                    "auroc": None, "probe_skipped": True,
                    "reason": (f"insufficient for scaffold-CV: n_pos={n_pos}, "
                               f"n_neg={n_neg}, n_scaffold_groups={n_groups}, "
                               f"min_per_class={MIN_PROBE_PER_CLASS}"),
                    "n_actives": n_pos, "n_decoys": n_neg,
                    "drug_backend": drug.backend, "seq_len": p["seq_len"],
                    "seq_truncated_for_esm2": bool(truncated),
                }
                print(f"[dtiam] {gene} ({p['family']}): probe skipped "
                      f"(pos={n_pos}, neg={n_neg}, groups={n_groups})", flush=True)
                continue

            n_splits = max(2, min(PROBE_FOLDS, n_groups))
            gkf = GroupKFold(n_splits=n_splits)
            oof = np.full(len(y), np.nan, dtype=float)
            for tr, te in gkf.split(X, y, groups):
                # A fold with only one class in train is uninformative -> skip (leaves NaN).
                if len(set(y[tr].tolist())) < 2:
                    continue
                sc = StandardScaler()
                Xtr = sc.fit_transform(X[tr])
                Xte = sc.transform(X[te])
                clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
                clf.fit(Xtr, y[tr])
                oof[te] = clf.predict_proba(Xte)[:, 1]

            mask = ~np.isnan(oof)
            a = auroc(y[mask], oof[mask]) if mask.sum() > 0 else None
            out[gene] = {
                "family": p["family"], "chembl_id": p["chembl_id"],
                "auroc": a, "probe_skipped": False,
                "n_actives": n_pos, "n_decoys": n_neg,
                "n_scaffold_groups": n_groups, "cv_folds": n_splits,
                "n_scored": int(mask.sum()),
                "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
                "seq_truncated_for_esm2": bool(truncated),
                "drug_backend": drug.backend, "drug_dim": int(dfeat.shape[1]),
                "prot_dim": int(pvec.shape[0]),
            }
            print(f"[dtiam] {gene} ({p['family']}): AUROC={a} "
                  f"[scaffold-CV {n_splits}f, drug={drug.backend}]", flush=True)
        except Exception as e:
            out[gene] = {"family": p["family"], "chembl_id": p["chembl_id"],
                         "auroc": None, "error": f"{type(e).__name__}: {e}"}
            print(f"[dtiam] {gene} FAILED: {e}\n{traceback.format_exc()[:500]}", flush=True)
    out["_drug_backend"] = drug.backend  # surfaced at top of the model block
    return out


# ---------------------------------------------------------------------------
# Family aggregation -- THE HEADLINE. mean AUROC + range per family per model.
# Reused verbatim from aws/cns_dti_benchmark_eval.py (ignores meta keys like
# _drug_backend / non-target entries).
# ---------------------------------------------------------------------------
def aggregate_by_family(per_target):
    fams = {}
    for gene, r in per_target.items():
        if not isinstance(r, dict) or "family" not in r:
            continue
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
    all_vals = [r["auroc"] for r in per_target.values()
                if isinstance(r, dict) and r.get("auroc") is not None]
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
        "task": ("CNS-NEW-MODELS DTI benchmark: does DTIAM (Nat. Commun. 2025; BerMol drug "
                 "tower pretrained on 1.6M ChEMBL compounds + ESM-2 protein tower) transfer "
                 "BETTER to ion channels than the zero-shot BindingDB-pretrained BALM/PLAPT? "
                 "DTIAM is scored as a per-target FEW-SHOT scaffold-split probe over its "
                 "feature towers (the supervised lever endorsed by trunc_test). Per-target "
                 "binder-vs-decoy AUROC -> per-FAMILY aggregate (headline)."),
        "model_under_test": {
            "name": "DTIAM",
            "source": "github.com/CSUBioGroup/DTIAM (Nat. Commun. 2025)",
            "license": "Apache-2.0",
            "drug_tower": ("BerMol, self-supervised on 1.6M ChEMBL compounds (GuacaMol) via "
                           "MLM + descriptor + functional-group prediction"),
            "protein_tower": f"ESM-2 mean-pool ({ESM2_MODEL})",
            "why_cns_relevant": ("broader-than-BindingDB chemistry coverage (category a) + a new "
                                 "2025 DTI FM (category c); used as a target-conditioned few-shot "
                                 "probe (category b) -- the exact transfer levers for the ion-channel "
                                 "coverage gap where BALM/PLAPT sit at chance."),
            "readout": ("per-target scaffold-grouped CV logistic probe over [BerMol(SMILES) | "
                        "ESM2(seq)]; FEW-SHOT not zero-shot, labeled accordingly."),
        },
        "device": DEVICE,
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
            "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "binding_types": BINDING_TYPES,
            "probe_folds": PROBE_FOLDS, "min_probe_per_class": MIN_PROBE_PER_CLASS,
            "esm2_maxlen": ESM2_MAXLEN, "seed": SEED,
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]}
                             for g, m in PANEL.items()},
        "zeroshot_reference_baselines": ZEROSHOT_REFERENCE,
    }

    # --- Build the per-target sets from ChEMBL (guarded) ---
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
            "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
            "seq_source": p["seq_source"]}
        for g, p in panels.items()}
    results["n_targets_built"] = len(panels)
    print(f"[built] {len(panels)} targets; dropped {len(dropped)}", flush=True)

    # --- Score with DTIAM few-shot probe (guarded) ---
    models = {}
    section("DTIAM_fewshot", score_dtiam_fewshot, models, panels)
    # Surface which drug featurization actually ran (bermol vs morgan_fp_fallback).
    dt = models.get("DTIAM_fewshot")
    if isinstance(dt, dict):
        results["drug_backend_used"] = dt.get("_drug_backend")
    results["per_target_auroc"] = models

    # --- Family aggregation per model -- the headline ---
    family = {}
    for mname, per_target in models.items():
        if isinstance(per_target, dict) and "error" not in per_target:
            try:
                family[mname] = aggregate_by_family(per_target)
            except Exception as e:
                family[mname] = {"error": f"{type(e).__name__}: {e}"}
    results["family_aggregate"] = family

    # --- Head-to-head: per-family mean AUROC, DTIAM(few-shot) vs BALM/PLAPT(zero-shot) ---
    h2h = {}
    fam_names = ["ion_channel", "mtor_pathway", "gpcr", "kinase"]
    for fam in fam_names:
        row = {
            "DTIAM_fewshot": (family.get("DTIAM_fewshot", {}).get(fam, {}) or {}).get("mean_auroc"),
            "BALM_zeroshot": ZEROSHOT_REFERENCE["BALM_zeroshot"].get(fam),
            "PLAPT_zeroshot": ZEROSHOT_REFERENCE["PLAPT_zeroshot"].get(fam),
        }
        h2h[fam] = row
    results["headline_family_mean_auroc"] = h2h

    # --- Did DTIAM beat CHANCE on ion channels? (the central question) ---
    ic = (family.get("DTIAM_fewshot", {}).get("ion_channel", {}) or {})
    ic_mean = ic.get("mean_auroc")
    results["ion_channel_verdict"] = {
        "dtiam_fewshot_mean_auroc": ic_mean,
        "balm_plapt_zeroshot": 0.50,
        "beats_chance": (ic_mean is not None and ic_mean > 0.55),
        "beats_chance_threshold": 0.55,
        "per_ion_channel_target": ic.get("per_target"),
        "note": ("DTIAM here is FEW-SHOT (per-target scaffold-split probe), so a win over "
                 "0.50 shows the BerMol+ESM2 features carry per-target ion-channel signal that "
                 "supervision unlocks -- consistent with trunc_test's ~0.92 supervised probe. It "
                 "is NOT a like-for-like zero-shot comparison; flagged for the scorecard."),
    }

    results["runtime_sec"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("headline_family_mean_auroc", {}), indent=2, default=str),
          flush=True)
    print(json.dumps(results.get("ion_channel_verdict", {}), indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
