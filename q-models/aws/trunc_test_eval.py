"""TRUNCATION HYPOTHESIS test: is sequence-DTI at chance on CNS ion channels because
the protein encoder TRUNCATES the channel to its N-terminal 1024 tokens?

WHY
===
`results/cns_dti_characterization.md` found BALM (cosine) + PLAPT (affinity) at CHANCE
(ion-channel family-mean AUROC 0.499 / 0.501) on the 9-target CNS ion-channel family
(Nav/Cav/NMDA, 1956-2221 aa), while reliable on kinases (0.80). Two suspects were named:
  (a) TRUNCATION — BALM caps protein input at 1024 ESM-2 tokens, so on a 2000+ aa channel
      it only ever sees the N-terminus; the pore / drug-binding domains are cut off.
  (b) DATA DISTRIBUTION — BindingDB pretraining is kinase/GPCR-rich, ion-channel-poor.
The characterization argued truncation "contributes but isn't decisive" (MTOR @ 2549 aa and
LRRK2 @ 2527 aa are also truncated yet score 0.83/0.77) — but that conflated the BALM
*shared-space* representation with the encoder. This eval ISOLATES suspect (a) cleanly:
holding the encoder (ESM-2-650M), the ligand rep (ECFP4), and the probe (logistic reg)
fixed, does a FULL-LENGTH protein embedding (no 1024 cap, via chunk-pooling) recover
above-chance binder-vs-decoy signal on the ion channels that a TRUNCATED (first-1024-only)
embedding cannot?

THE QUESTION
============
Per-target + ion-channel-family-mean 5-fold-CV AUROC for a supervised probe on
[protein_emb (+) ligand_emb] -> binder/decoy, computed TWICE:
  - TRUNCATED  protein emb: ESM-2-650M on the first 1024 tokens (1022 residues) only.
  - FULL-LENGTH protein emb: ESM-2-650M chunk-pool (every residue embedded, mean-pooled).
vs the BALM baseline 0.50 (family mean).
  * FULL >> TRUNC and clears chance  => TRUNCATION is the culprit; fix = long-context DTI.
  * BOTH stay ~chance                => signal isn't in static seq+ligand; need structure/
                                        dynamics (state/use-dependent channel pharmacology).
Note: the protein embedding is CONSTANT per target (one channel, many ligands), so within a
single target the protein rep cannot by itself separate binders from decoys at the PROBE
level UNLESS it interacts with the ligand rep. The discriminative signal therefore lives in
the joint [protein (+) ligand] feature space; the truncated vs full-length protein half is
the variable under test, and the family-mean across targets is the headline (a per-target
probe still tests whether the channel's representation lets the ligand features generalize
binder-vs-decoy within that target, and the truncated-vs-full delta is the truncation effect).

DATA (fetched on-instance; identical pull to aws/cns_dti_benchmark_eval.py)
==========================================================================
The 9 ion-channel targets from the CNS benchmark panel (SCN1A/2A/8A/9A/10A/5A, CACNA1C,
GRIN1, GRIN2B). For each: resolve a single-protein human ChEMBL target id by UniProt
accession (hardcoded fallback), pull IC50/Ki/Kd actives (pChEMBL >= 6.0, capped 60), build
decoys (same-target ChEMBL inactives pChEMBL <= 5.0 if >=15, else DUD-E-style property-matched
cross-target decoys), fetch the FULL UniProt sequence. Targets with <30 actives or no usable
decoy set are dropped (RHEB/KCNQ2-style) and reported.

MODELS / REPS
=============
  Protein encoder: facebook/esm2_t33_650M_UR50D (transformers EsmModel), float32, GPU.
    Mean-pool residue embeddings excluding CLS/EOS (verbatim protocol from
    aws/big_panel_sweep.py / aws/esm2_big_layer_sweep.py: hs[0, 1:-1, :].mean(0)).
    TRUNCATED  rep: tokenize first TRUNC_AA (=1022) residues only -> 1 forward pass.
    FULL-LENGTH rep (CHUNK-POOL): split the sequence into consecutive <=1022-residue windows,
      embed each window independently (each gets its own CLS/EOS), mean-pool the per-window
      residue-means, weighted by residues per window -> one full-length embedding. No residue
      is lost; the pore/binding domains beyond residue 1022 are now represented.
  Ligand rep: ECFP4 (Morgan radius 2, 2048 bit) -> float vector. Simplest + robust; RDKit.
  Probe: sklearn LogisticRegression (max_iter 2000, C=1.0), 5-fold stratified CV, scoring on
    held-out probability -> pooled-out-of-fold AUROC per target. Scaffold-aware split if RDKit
    Murcko scaffolds give >=2 groups with both classes present (GroupKFold over scaffolds);
    else StratifiedKFold. Feature vector = [protein_emb (+) ligand_emb], protein half identical
    within a target (truncated OR full), ligand half varies per compound.

Every section is try/except-guarded so one ChEMBL/UniProt hiccup or one bad target cannot
sink the run — partial results still upload. Writes JSON to env OUT
(default /root/trunc_out/trunc_test_result.json).
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
OUT = Path(os.environ.get("OUT", "/root/trunc_out/trunc_test_result.json"))
ESM2_REPO = os.environ.get("ESM2_REPO", "facebook/esm2_t33_650M_UR50D")

# Knobs (env-overridable). Mirror the CNS benchmark so the panel build is identical.
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))      # >= this = active (~<=1 uM)
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))  # <= this = ChEMBL inactive
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "30"))              # drop target below this
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "60"))             # cap actives/target (runtime)
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))          # decoys <= ratio x n_actives
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))               # need at least this many decoys
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))  # matched-decoy dissimilarity

# Truncation cap: ESM-2 caps at 1024 TOKENS = 1022 residues + CLS + EOS. The truncated rep
# mimics BALM's first-1024-tokens behaviour; the chunk-pool window is the same 1022 residues.
TRUNC_AA = int(os.environ.get("TRUNC_AA", "1022"))
CHUNK_AA = int(os.environ.get("CHUNK_AA", "1022"))   # residues per chunk-pool window
N_FOLDS = int(os.environ.get("N_FOLDS", "5"))
MORGAN_BITS = int(os.environ.get("MORGAN_BITS", "2048"))
MORGAN_RADIUS = int(os.environ.get("MORGAN_RADIUS", "2"))
RNG = np.random.default_rng(int(os.environ.get("SEED", "20260614")))
SEED = int(os.environ.get("SEED", "20260614"))

# ---------------------------------------------------------------------------
# ION-CHANNEL PANEL (the 9 CNS ion channels from aws/cns_dti_benchmark_eval.py).
# gene -> (uniprot_accession PRIMARY key, fallback_chembl_id, family). All ion_channel.
# Lengths annotated for context (the >1024-token truncation targets).
# ---------------------------------------------------------------------------
PANEL = {
    "SCN1A":   {"uniprot": "P35498", "chembl": "CHEMBL5277",    "family": "ion_channel"},  # Nav1.1 ~2009 aa
    "SCN2A":   {"uniprot": "Q99250", "chembl": "CHEMBL4076",    "family": "ion_channel"},  # Nav1.2 ~2005 aa
    "SCN8A":   {"uniprot": "Q9UQD0", "chembl": "CHEMBL4960",    "family": "ion_channel"},  # Nav1.6 ~1980 aa
    "SCN9A":   {"uniprot": "Q15858", "chembl": "CHEMBL4296",    "family": "ion_channel"},  # Nav1.7 ~1988 aa
    "SCN10A":  {"uniprot": "Q9Y5Y9", "chembl": "CHEMBL5451",    "family": "ion_channel"},  # Nav1.8 ~1956 aa
    "SCN5A":   {"uniprot": "Q14524", "chembl": "CHEMBL1980",    "family": "ion_channel"},  # Nav1.5 ~2016 aa (cardiac ref)
    "CACNA1C": {"uniprot": "Q13936", "chembl": "CHEMBL1940",    "family": "ion_channel"},  # Cav1.2 ~2221 aa
    "GRIN1":   {"uniprot": "Q05586", "chembl": "CHEMBL1907594", "family": "ion_channel"},  # NMDA NR1 ~938 aa
    "GRIN2B":  {"uniprot": "Q13224", "chembl": "CHEMBL1907600", "family": "ion_channel"},  # NMDA NR2B ~1484 aa
}

BINDING_TYPES = ["IC50", "Ki", "Kd"]

# BALM baseline (ion-channel family mean) from results/cns_dti_characterization.md.
BALM_BASELINE = {
    "ion_channel_family_mean": {"BALM_cosine": 0.499, "PLAPT_affinity": 0.501},
    "per_target_balm_cosine": {
        "SCN9A": 0.845, "SCN10A": 0.780, "SCN2A": 0.710, "SCN8A": 0.556,
        "SCN5A": 0.459, "SCN1A": 0.292, "GRIN1": 0.32, "GRIN2B": 0.33, "CACNA1C": 0.204,
    },
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
# UniProt WT-sequence fetch (verbatim from aws/cns_dti_benchmark_eval.py).
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "trunc-test-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL data access (verbatim from aws/cns_dti_benchmark_eval.py).
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
    """DUD-E-style property-matched, chemically-dissimilar decoys (verbatim)."""
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
# Build per-target {actives, decoys, seq} sets (verbatim ChEMBL/decoy logic from
# aws/cns_dti_benchmark_eval.py, restricted to the 9-target ion-channel panel).
# ---------------------------------------------------------------------------
def build_panels():
    built = {}
    dropped = {}
    raw_actives = {}
    raw_inactives = {}

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

    # Pass 2: build decoys + fetch FULL sequence for surviving targets.
    for gene in list(built.keys()):
        try:
            meta = PANEL[gene]
            actives = raw_actives[gene]
            n_act = len(actives)
            n_decoy_cap = int(round(n_act * DECOY_RATIO))

            inactives = raw_inactives.get(gene, {})
            decoy_smiles = []
            decoy_source = None
            if len(inactives) >= MIN_DECOYS:
                items = sorted(inactives.items(), key=lambda kv: kv[1])  # weakest first
                decoy_smiles = [s for s, _ in items[:n_decoy_cap]]
                decoy_source = "chembl_inactives_same_target"
            else:
                active_smiles = set(actives.keys())
                active_props = [p for p in (mol_props(s) for s in actives) if p is not None]
                cand = [s for g2, acts in raw_actives.items() if g2 != gene
                        for s in acts.keys()]
                if not cand:
                    cand = list(global_pool)
                decoy_smiles = property_matched_decoys(
                    active_smiles, active_props, cand, n_decoy_cap)
                decoy_source = "property_matched_cross_target_decoys"
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

            # FULL sequence (this eval's whole point: chunk-pool uses every residue).
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
                "truncated": len(seq) > TRUNC_AA,
                "n_chunks": int(np.ceil(len(seq) / CHUNK_AA)),
                "actives": list(actives.keys()),
                "decoys": decoy_smiles,
                "decoy_source": decoy_source,
                "n_actives": len(actives), "n_decoys": len(decoy_smiles),
            })
            print(f"[panel] {gene}: {len(actives)} actives / {len(decoy_smiles)} decoys "
                  f"({decoy_source}); seq_len={len(seq)} "
                  f"truncated={len(seq) > TRUNC_AA} n_chunks={int(np.ceil(len(seq)/CHUNK_AA))}",
                  flush=True)
        except Exception as e:
            dropped[gene] = f"decoy/seq build error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} build failed: {e}\n{traceback.format_exc()[:600]}",
                  flush=True)
            built.pop(gene, None)

    return built, dropped


# ---------------------------------------------------------------------------
# ESM-2-650M protein encoder. Mean-pool residue embeddings EXCLUDING CLS/EOS
# (verbatim protocol from aws/big_panel_sweep.py / aws/esm2_big_layer_sweep.py:
#  hs[0, 1:-1, :].mean(0)). Two representations per target:
#   - encode_truncated: first TRUNC_AA residues only (mimics BALM's 1024-token cap).
#   - encode_full     : CHUNK-POOL over <=CHUNK_AA windows, residue-weighted mean.
# ---------------------------------------------------------------------------
class Esm2Encoder:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(ESM2_REPO)
        self.m = AutoModel.from_pretrained(
            ESM2_REPO, torch_dtype=torch.float32).to(DEVICE).eval()

    def _embed_window(self, residues):
        """One forward pass over a residue string (<= CHUNK_AA). Returns the
        mean-pooled residue embedding (ex CLS/EOS) as float64 numpy."""
        torch = self.torch
        # max_length = residues + CLS + EOS; truncation guards over-length defensively.
        inp = self.tok(residues, return_tensors="pt", add_special_tokens=True,
                       truncation=True, max_length=CHUNK_AA + 2)
        inp = {k: v.to(DEVICE) for k, v in inp.items()}
        with torch.no_grad():
            out = self.m(**inp)
        h = out.last_hidden_state[0, 1:-1, :].float().mean(0).cpu().numpy().astype(np.float64)
        return h

    def encode_truncated(self, seq):
        """ESM-2 on the FIRST TRUNC_AA residues only (the BALM-style truncation)."""
        return self._embed_window(seq[:TRUNC_AA])

    def encode_full(self, seq):
        """CHUNK-POOL: split into consecutive <=CHUNK_AA windows, embed each, and
        mean-pool the per-window residue-means WEIGHTED by residues per window so the
        result equals the residue-mean over the whole sequence (no residue lost; the
        pore/binding domains beyond residue 1022 are now represented)."""
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
# Ligand rep: ECFP4 (Morgan radius 2, 2048 bit) -> float vector.
# ---------------------------------------------------------------------------
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
    """Bemis-Murcko scaffold SMILES (for scaffold-aware CV grouping). None on failure."""
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


# ---------------------------------------------------------------------------
# Supervised probe: LogisticRegression, 5-fold CV, pooled out-of-fold AUROC.
# Scaffold-aware GroupKFold if scaffolds give a usable grouping, else StratifiedKFold.
# Feature = [protein_emb (+) ligand_emb]; protein half is constant per target (the
# variable under test: truncated vs full-length); ligand half varies per compound.
# ---------------------------------------------------------------------------
def cv_auroc(prot_vec, lig_vecs, labels, scaffolds):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, GroupKFold
    from sklearn.preprocessing import StandardScaler

    labels = np.asarray(labels, dtype=int)
    X_lig = np.vstack(lig_vecs)
    prot = np.asarray(prot_vec, dtype=np.float64)[None, :]
    X = np.hstack([np.repeat(prot, len(labels), axis=0), X_lig])

    n = len(labels)
    n_pos = int(labels.sum())
    n_neg = int(n - n_pos)
    if n_pos < 2 or n_neg < 2:
        return {"auroc": None, "note": "too few of one class for CV", "split": None}

    # Decide split strategy. Scaffold-aware only if it yields >= 2 groups AND >= N_FOLDS
    # distinct groups AND each fold can carry both classes (heuristic: >= N_FOLDS groups).
    split_kind = None
    folds = max(2, min(N_FOLDS, n_pos, n_neg))
    use_groups = False
    groups = None
    if scaffolds is not None and all(s is not None for s in scaffolds):
        uniq = sorted(set(scaffolds))
        if len(uniq) >= folds:
            gmap = {s: i for i, s in enumerate(uniq)}
            groups = np.array([gmap[s] for s in scaffolds])
            # need both classes present overall and enough groups for GroupKFold
            use_groups = True
    try:
        oof = np.full(n, np.nan, dtype=np.float64)
        if use_groups:
            split_kind = "scaffold_group_kfold"
            gkf = GroupKFold(n_splits=folds)
            iterator = gkf.split(X, labels, groups)
        else:
            split_kind = "stratified_kfold"
            skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=SEED)
            iterator = skf.split(X, labels)
        for tr, te in iterator:
            if labels[tr].sum() == 0 or labels[tr].sum() == len(tr):
                # degenerate training fold (one class) -> skip; leaves NaNs handled below
                continue
            sc = StandardScaler().fit(X[tr])
            clf = LogisticRegression(max_iter=2000, C=1.0)
            clf.fit(sc.transform(X[tr]), labels[tr])
            oof[te] = clf.predict_proba(sc.transform(X[te]))[:, 1]
        mask = ~np.isnan(oof)
        if mask.sum() < 4 or labels[mask].sum() == 0 or labels[mask].sum() == mask.sum():
            return {"auroc": None, "note": "CV produced no usable out-of-fold preds",
                    "split": split_kind}
        a = auroc(labels[mask], oof[mask])
        return {"auroc": a, "split": split_kind, "n_folds": folds,
                "n_scored": int(mask.sum())}
    except Exception as e:
        return {"auroc": None, "note": f"{type(e).__name__}: {e}", "split": split_kind}


# ---------------------------------------------------------------------------
# Score one rep ("truncated" or "full") across all targets.
# ---------------------------------------------------------------------------
def score_rep(panels, enc, lig_cache, rep):
    out = {}
    for gene, p in panels.items():
        try:
            seq = p["seq"]
            prot = enc.encode_truncated(seq) if rep == "truncated" else enc.encode_full(seq)
            if prot is None:
                out[gene] = {"auroc": None, "note": "protein embed failed",
                             "family": p["family"], "seq_len": p["seq_len"]}
                continue
            smiles = list(p["actives"]) + list(p["decoys"])
            labels = [1] * len(p["actives"]) + [0] * len(p["decoys"])
            lig_vecs, kept_labels, kept_scaf = [], [], []
            for smi, lab in zip(smiles, labels):
                v = lig_cache.get(smi)
                if v is None:
                    continue
                lig_vecs.append(v)
                kept_labels.append(lab)
                kept_scaf.append(murcko_scaffold(smi))
            if len(lig_vecs) < 8:
                out[gene] = {"auroc": None, "note": "too few valid ligand reps",
                             "family": p["family"], "seq_len": p["seq_len"]}
                continue
            res = cv_auroc(prot, lig_vecs, kept_labels, kept_scaf)
            res.update({
                "family": p["family"], "chembl_id": p["chembl_id"],
                "seq_len": p["seq_len"], "truncated": p.get("truncated"),
                "n_chunks": p.get("n_chunks"),
                "n_actives": int(np.sum(kept_labels)),
                "n_decoys": int(len(kept_labels) - np.sum(kept_labels)),
                "decoy_source": p["decoy_source"],
            })
            out[gene] = res
            print(f"[{rep}] {gene}: AUROC={res.get('auroc')} "
                  f"(split={res.get('split')}, seq_len={p['seq_len']}, "
                  f"chunks={p.get('n_chunks')})", flush=True)
        except Exception as e:
            out[gene] = {"auroc": None, "note": f"{type(e).__name__}: {e}",
                         "family": p.get("family"), "seq_len": p.get("seq_len")}
            print(f"[warn] {rep} {gene} failed: {e}\n{traceback.format_exc()[:600]}",
                  flush=True)
    return out


def family_mean(per_target):
    vals = [r["auroc"] for r in per_target.values()
            if isinstance(r, dict) and r.get("auroc") is not None]
    if not vals:
        return None
    return round(float(np.mean(vals)), 4)


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
        "task": ("TRUNCATION HYPOTHESIS test for CNS ion-channel sequence-DTI being at chance. "
                 "Holding encoder (ESM-2-650M), ligand rep (ECFP4), and probe (LogReg 5-fold CV) "
                 "fixed, compare TRUNCATED (first-1022-residue) vs FULL-LENGTH (chunk-pool) protein "
                 "embeddings on binder-vs-decoy AUROC. Headline = ion-channel family mean, "
                 "truncated vs full, vs BALM 0.50."),
        "device": DEVICE,
        "esm2_repo": ESM2_REPO,
        "hypothesis": {
            "suspect_a_truncation": "BALM caps protein at 1024 ESM-2 tokens; channels are "
                                    "1956-2221 aa so only the N-terminal 1022 residues are seen.",
            "suspect_b_data": "BindingDB pretraining is kinase/GPCR-rich, ion-channel-poor.",
            "this_eval_isolates": "suspect_a (truncation) by giving FULL-length representation "
                                  "via chunk-pool; if FULL >> TRUNC and clears chance, truncation "
                                  "is the culprit; if both ~chance, signal isn't in static seq+ligand.",
        },
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
            "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "binding_types": BINDING_TYPES,
            "trunc_aa": TRUNC_AA, "chunk_aa": CHUNK_AA, "n_folds": N_FOLDS,
            "morgan_radius": MORGAN_RADIUS, "morgan_bits": MORGAN_BITS, "seed": SEED,
            "ligand_rep": "ECFP4 (Morgan r2, 2048 bit)",
            "probe": "LogisticRegression(max_iter=2000, C=1.0) on StandardScaler "
                     "[protein_emb (+) ligand_emb]; pooled out-of-fold AUROC",
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]}
                             for g, m in PANEL.items()},
        "balm_baseline": BALM_BASELINE,
    }

    # --- Build per-target sets from ChEMBL (guarded) ---
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
            "seq_source": p["seq_source"], "truncated": p.get("truncated"),
            "n_chunks": p.get("n_chunks")}
        for g, p in panels.items()}
    results["n_targets_built"] = len(panels)
    print(f"[built] {len(panels)} ion-channel targets; dropped {len(dropped)}", flush=True)

    if not panels:
        results["runtime_sec"] = round(time.time() - t0, 1)
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] no targets built; wrote {OUT}", flush=True)
        return

    # --- Precompute ECFP4 ligand cache (shared across both reps; guarded) ---
    lig_store = {}

    def build_lig_cache(panels):
        cache = {}
        n_bad = 0
        for p in panels.values():
            for smi in list(p["actives"]) + list(p["decoys"]):
                if smi in cache:
                    continue
                v = ecfp4(smi)
                if v is None:
                    n_bad += 1
                    continue
                cache[smi] = v
        print(f"[ecfp4] cached {len(cache)} ligands ({n_bad} unparseable)", flush=True)
        return cache

    section("lig_cache", build_lig_cache, lig_store, panels)
    lig_cache = lig_store.get("lig_cache")
    if not isinstance(lig_cache, dict) or not lig_cache:
        results["lig_cache_error"] = lig_store.get("lig_cache")
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] ligand cache failed; wrote {OUT}", flush=True)
        return

    # --- Load ESM-2 encoder once; score both reps (guarded) ---
    enc_store = {}
    section("encoder", Esm2Encoder, enc_store)
    enc = enc_store.get("encoder")
    if not isinstance(enc, Esm2Encoder):
        results["encoder_error"] = enc_store.get("encoder")
        OUT.write_text(json.dumps(results, indent=2, default=str))
        print(f"[done-early] ESM-2 load failed; wrote {OUT}", flush=True)
        return

    reps = {}
    section("truncated", score_rep, reps, panels, enc, lig_cache, "truncated")
    section("full", score_rep, reps, panels, enc, lig_cache, "full")
    results["per_target_auroc"] = reps

    # --- HEADLINE: ion-channel family-mean AUROC, truncated vs full, vs BALM 0.50 ---
    headline = {}
    for rep in ("truncated", "full"):
        pt = reps.get(rep)
        if isinstance(pt, dict) and "error" not in pt:
            headline[rep] = family_mean(pt)
    headline["balm_cosine_baseline"] = BALM_BASELINE["ion_channel_family_mean"]["BALM_cosine"]
    headline["plapt_affinity_baseline"] = BALM_BASELINE["ion_channel_family_mean"]["PLAPT_affinity"]
    if headline.get("truncated") is not None and headline.get("full") is not None:
        headline["full_minus_truncated"] = round(headline["full"] - headline["truncated"], 4)
    results["headline_ion_channel_family_mean_auroc"] = headline

    # --- Per-target side-by-side truncated vs full (+ delta + BALM cosine) ---
    side = {}
    pt_t = reps.get("truncated") if isinstance(reps.get("truncated"), dict) else {}
    pt_f = reps.get("full") if isinstance(reps.get("full"), dict) else {}
    for gene in panels:
        t = (pt_t.get(gene) or {}).get("auroc")
        f = (pt_f.get(gene) or {}).get("auroc")
        side[gene] = {
            "truncated": round(t, 4) if t is not None else None,
            "full": round(f, 4) if f is not None else None,
            "delta_full_minus_trunc": round(f - t, 4) if (t is not None and f is not None) else None,
            "balm_cosine": BALM_BASELINE["per_target_balm_cosine"].get(gene),
            "seq_len": panels[gene]["seq_len"],
            "truncated_flag": panels[gene].get("truncated"),
            "n_chunks": panels[gene].get("n_chunks"),
        }
    results["per_target_truncated_vs_full"] = side

    # --- Verdict string (cheap, defensive) ---
    try:
        ft = headline.get("full")
        tt = headline.get("truncated")
        if ft is not None and tt is not None:
            if ft >= 0.65 and (ft - tt) >= 0.10:
                v = ("FULL-LENGTH clears chance and beats TRUNCATED by a clear margin => "
                     "TRUNCATION is a (the) culprit; fix = long-context protein DTI.")
            elif ft < 0.60 and tt < 0.60:
                v = ("BOTH truncated and full-length stay ~chance => truncation is NOT the "
                     "fix; the signal isn't in static seq+ligand (need structure/dynamics).")
            else:
                v = ("Mixed: full-length helps modestly but doesn't decisively clear chance => "
                     "truncation contributes but is not the sole cause (data distribution + "
                     "static-rep limits remain).")
            results["verdict"] = v
    except Exception as e:
        results["verdict_error"] = f"{type(e).__name__}: {e}"

    results["runtime_sec"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("headline_ion_channel_family_mean_auroc", {}),
                     indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
