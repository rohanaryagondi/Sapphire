"""CNS-BROAD DTI benchmark: do our binder-triage winners (BALM + PLAPT) hold up
across a panel of CNS-relevant targets spanning FAMILIES — not just Nav1.8?

WHY
===
Our Track-2 / selectivity verdict ("BALM is the binder-triage tool", Nav1.8 cosine
AUROC 0.857 > Boltz-2 0.714 > ConPLex 0.437; mTOR 1.000) rests on a tiny n=11 Nav1.8
panel + n=7 mTOR panel. That is too narrow to claim a general Track-2 winner. Quiver
is a CNS company currently focused on the TSC2/mTOR pathway, so we de-anecdote the
verdict on a broad CNS benchmark: ~15-20 CNS-relevant targets across four families,
weighted toward the TSC2/mTOR pathway + epilepsy/excitability ion channels.

THE QUESTION
============
Per-target binder-vs-decoy AUROC for BALM (cosine) and PLAPT (affinity), then
aggregated BY FAMILY (ion-channel / mTOR-pathway / GPCR / kinase): mean AUROC + range
per family per model. The family view is the headline — does the "BALM wins" story
hold across CNS, or is it target-specific (e.g. only the well-represented kinases)?

DATA (fetched on-instance from ChEMBL; sequences from UniProt REST)
==================================================================
For each target we resolve a single-protein human ChEMBL target id (by UniProt
accession, falling back to a hardcoded id), then pull binding activities
(IC50/Ki/Kd):
  ACTIVES  = pchembl_value >= ACTIVE_PCHEMBL (default 6.0; ~<=1 uM), capped MAX_ACTIVES.
  DECOYS, in priority order:
    (1) ChEMBL INACTIVES for the SAME target: pchembl_value <= INACTIVE_PCHEMBL
        (default 5.0). True experimental non-binders — the cleanest decoys.
    (2) If too few same-target inactives: property-matched decoys (DUD-E-style)
        sampled from OTHER targets' actives — match MW / logP / HBD / HBA within
        tolerance and require a DISSIMILAR Morgan fingerprint (Tanimoto < 0.35) to
        the target's actives, so a decoy is property-plausible but chemically unlike
        a known binder. Cross-target actives are presumed non-binders of THIS target.
  Active:decoy ratio targeted ~1:1 to 1:3 (decoys capped at DECOY_RATIO x n_actives).

Targets with fewer than MIN_ACTIVES (default 30) usable actives, or with no usable
decoy set, are DROPPED for sparsity and reported in `dropped_targets`.

MODELS (both: pretrained weights, protein SEQUENCE + ligand SMILES, NO 3D structure)
====================================================================================
  BALM  (github.com/meyresearch/BALM) — ESM-2-150M + ChemBERTa-77M two-tower; the
        cosine(protein, drug) in the shared space IS the binding score (higher =
        more likely binder), also mapped to a pKd. Loader/API reused VERBATIM from
        aws/balm_characterization.py / aws/tsc2_deconv_eval.py (Balm class; checkpoint
        BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse, balm_peft.yaml config).
        CAVEAT: ESM-2 truncates protein input at 1024 tokens — the big Nav/Cav channels
        (~1900-2000+ aa) are truncated to the N-terminal 1024; we record seq_len so the
        truncation is never silent (matches the Nav1.8 operating-envelope caveat).
  PLAPT (github.com/Bindwell/PLAPT) — branched transformer on frozen ProtBERT +
        ChemBERTa embeddings; affinity head ships as models/affinity_predictor.onnx.
        API reused VERBATIM from aws/dti_nav_eval.py / aws/tsc2_deconv_eval.py:
          from plapt import Plapt; Plapt(...).predict_affinity(prots, smiles)
        -> list of dicts, key `neg_log10_affinity_M` (pKd-like; higher = stronger binder).
        ProtBERT max_length ~3200, so most CNS targets fit without truncation.

Every target build, model load, scoring pass, and aggregation is independently
try/except-guarded so a single ChEMBL/UniProt hiccup or one bad target cannot sink
the run — partial results still upload. Writes JSON to env OUT
(default /root/cns_out/cns_dti_result.json).
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
OUT = Path(os.environ.get("OUT", "/root/cns_out/cns_dti_result.json"))
BALM_DIR = Path(os.environ.get("BALM_DIR", "/opt/BALM"))
PLAPT_DIR = Path(os.environ.get("PLAPT_DIR", "/opt/PLAPT"))
CKPT = os.environ.get("BALM_CKPT", "BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse")
CONFIG = os.environ.get("BALM_CONFIG", str(BALM_DIR / "default_configs" / "balm_peft.yaml"))

# Knobs (env-overridable so the panel can be tuned without editing the file).
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))    # >= this = active (~<=1 uM)
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))  # <= this = ChEMBL inactive
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "30"))            # drop target below this
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "60"))            # cap actives/target (runtime)
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))         # decoys <= ratio x n_actives
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))              # need at least this many decoys
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))  # matched-decoy dissimilarity
RNG = np.random.default_rng(int(os.environ.get("SEED", "20260614")))

# ---------------------------------------------------------------------------
# CNS TARGET PANEL. Weighted toward TSC2/mTOR pathway + epilepsy/excitability
# channels. Each entry: gene -> (uniprot_accession, fallback_chembl_id, family).
# UniProt accession is the PRIMARY key (we resolve the single-protein human ChEMBL
# target by accession at runtime); the chembl id is a documented FALLBACK only.
# Families: "ion_channel" | "mtor_pathway" | "gpcr" | "kinase".
# (SCN5A/Nav1.5 included as the CARDIAC selectivity reference — off-CNS-target.)
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


# ---------------------------------------------------------------------------
# AUROC (rank-sum; ties get average rank). Higher score => label 1 (binder).
# Reused verbatim from aws/dti_nav_eval.py / aws/tsc2_deconv_eval.py.
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
# UniProt WT-sequence fetch (pattern from aws/tsc2_deconv_eval.py).
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "cns-dti-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL data access via chembl_webresource_client (Django-QuerySet style).
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
    """DUD-E-style: pick decoys from candidate_pool that match the active-set property
    envelope (MW/logP/HBD/HBA within tolerance of the active means) but are
    chemically DISSIMILAR (max Tanimoto to any active < DECOY_TANIMOTO_MAX)."""
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
# Build per-target {actives, decoys, seq} sets. Returns built panels + dropped log.
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

            # Sequence (truncation recorded via seq_len; BALM caps at 1024 tokens).
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
# BALM loader (reused VERBATIM from aws/balm_characterization.py / tsc2_deconv_eval.py).
# cosine = binding score (higher = more likely binder); also mapped to pKd.
# ---------------------------------------------------------------------------
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
        try:
            cfg.model_configs.checkpoint_path = CKPT
        except Exception as e:
            print(f"[warn] could not set checkpoint_path: {e}", flush=True)
        m = BALM(cfg.model_configs)
        m = load_trained_model(m, cfg.model_configs, is_training=False)
        m.to(DEVICE).eval()
        self.m, self.torch = m, torch
        self.lo, self.hi = load_pretrained_pkd_bounds(cfg.model_configs.checkpoint_path)
        self.pt = AutoTokenizer.from_pretrained(cfg.model_configs.protein_model_name_or_path)
        self.dt = AutoTokenizer.from_pretrained(cfg.model_configs.drug_model_name_or_path)
        self.pmax = 1024

    def score(self, seq, smi):
        import torch
        p = self.pt(seq.strip().replace(" ", ""), return_tensors="pt",
                    truncation=True, max_length=self.pmax).to(DEVICE)
        d = self.dt(smi, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            o = self.m({"protein_input_ids": p["input_ids"],
                        "protein_attention_mask": p["attention_mask"],
                        "drug_input_ids": d["input_ids"],
                        "drug_attention_mask": d["attention_mask"]})
        cos = float(o["cosine_similarity"].reshape(-1)[0])
        return cos


# ---------------------------------------------------------------------------
# Scoring blocks. Each returns {gene: {auroc, n_actives, n_decoys, family, ...}}.
# ---------------------------------------------------------------------------
def score_balm(panels):
    balm = Balm()
    out = {}
    for gene, p in panels.items():
        seq = p["seq"]
        a_scores = [balm.score(seq, s) for s in p["actives"]]
        d_scores = [balm.score(seq, s) for s in p["decoys"]]
        labels = [1] * len(a_scores) + [0] * len(d_scores)
        scores = a_scores + d_scores
        a = auroc(labels, scores)
        out[gene] = {
            "family": p["family"], "chembl_id": p["chembl_id"],
            "auroc": a, "n_actives": len(a_scores), "n_decoys": len(d_scores),
            "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
            "mean_active_score": round(float(np.mean(a_scores)), 5) if a_scores else None,
            "mean_decoy_score": round(float(np.mean(d_scores)), 5) if d_scores else None,
        }
        print(f"[balm] {gene} ({p['family']}): AUROC={a}", flush=True)
    return out


def score_plapt(panels):
    sys.path.insert(0, str(PLAPT_DIR))
    os.chdir(PLAPT_DIR)  # affinity_predictor.onnx referenced relative to repo root
    from plapt import Plapt
    plapt = Plapt(device=DEVICE, use_tqdm=False)
    out = {}
    for gene, p in panels.items():
        smiles = list(p["actives"]) + list(p["decoys"])
        prots = [p["seq"]] * len(smiles)  # strict 1:1 pairing
        preds = plapt.predict_affinity(prots, smiles)
        scores = [float(x["neg_log10_affinity_M"]) for x in preds]
        labels = [1] * len(p["actives"]) + [0] * len(p["decoys"])
        a = auroc(labels, scores)
        a_scores = scores[:len(p["actives"])]
        d_scores = scores[len(p["actives"]):]
        out[gene] = {
            "family": p["family"], "chembl_id": p["chembl_id"],
            "auroc": a, "n_actives": len(p["actives"]), "n_decoys": len(p["decoys"]),
            "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
            "mean_active_score": round(float(np.mean(a_scores)), 5) if a_scores else None,
            "mean_decoy_score": round(float(np.mean(d_scores)), 5) if d_scores else None,
        }
        print(f"[plapt] {gene} ({p['family']}): AUROC={a}", flush=True)
    return out


# ---------------------------------------------------------------------------
# Family aggregation — THE HEADLINE. mean AUROC + range per family per model.
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
    # overall (micro over all targets)
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
        "task": ("CNS-broad DTI benchmark: do BALM (cosine) + PLAPT (affinity) hold as "
                 "binder-triage tools across CNS families, or is the verdict target-specific? "
                 "Per-target binder-vs-decoy AUROC -> per-FAMILY aggregate (headline)."),
        "device": DEVICE,
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
            "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "binding_types": BINDING_TYPES,
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]}
                             for g, m in PANEL.items()},
        "baselines_narrow": {  # the n=11/7 verdict we are de-anecdoting
            "BALM":    {"nav18_n11": 0.857, "mtor_n7": 1.000},
            "Boltz-2": {"nav18_n11": 0.714, "mtor_n7": 1.000},
            "ConPLex": {"nav18_n11": 0.437},
        },
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

    # --- Score with each model (guarded) ---
    models = {}
    section("BALM", score_balm, models, panels)
    section("PLAPT", score_plapt, models, panels)
    results["per_target_auroc"] = models

    # --- Family aggregation per model — the headline ---
    family = {}
    for mname, per_target in models.items():
        if isinstance(per_target, dict) and "error" not in per_target:
            try:
                family[mname] = aggregate_by_family(per_target)
            except Exception as e:
                family[mname] = {"error": f"{type(e).__name__}: {e}"}
    results["family_aggregate"] = family

    # --- Compact head-to-head: per-family mean AUROC, both models side by side ---
    h2h = {}
    fam_names = set()
    for m in family.values():
        if isinstance(m, dict):
            fam_names.update(k for k in m if not k.startswith("_"))
    for fam in sorted(fam_names):
        h2h[fam] = {mname: (family.get(mname, {}).get(fam, {}) or {}).get("mean_auroc")
                    for mname in models}
    h2h["_overall"] = {mname: (family.get(mname, {}).get("_overall", {}) or {}).get("mean_auroc")
                       for mname in models}
    results["headline_family_mean_auroc"] = h2h

    results["runtime_sec"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("headline_family_mean_auroc", {}), indent=2, default=str),
          flush=True)


if __name__ == "__main__":
    main()
