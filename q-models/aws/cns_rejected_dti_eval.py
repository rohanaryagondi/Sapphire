"""RE-TEST of previously-rejected / under-tested DTI models on the PROPER 19-target
CNS panel — were they dismissed unfairly?

WHY
===
ConPLex, DrugBAN, and PerceiverCPI were all written off as "Nav-blind" — but the
verdict that condemned them rests on TINY panels: ConPLex was judged on an n=11
Nav1.8 binder/decoy set (AUROC ~0.437), and DrugBAN/PerceiverCPI were only ever
*planned* as Nav-panel baseline checks (the wave that closed actually shipped PLAPT
+ DeepPurpose instead — see aws/dti_nav_eval.py). **Nav-blind != CNS-blind.** A
BindingDB-trained DTI model can be chance-level on the data-starved Nav channels yet
genuinely strong on the well-represented CNS kinases / GPCRs. This eval re-runs them
on the SAME broad 19-target CNS panel that BALM + PLAPT were de-anecdoted on
(aws/cns_dti_benchmark_eval.py), so the numbers are directly comparable per FAMILY.

THE QUESTION
============
Per-target binder-vs-decoy AUROC for each rejected model, aggregated BY FAMILY
(ion_channel / mtor_pathway / gpcr / kinase): mean AUROC + range per family. The
family view is the headline — does "Nav-blind" generalize to "CNS-blind", or do these
models actually clear the bar on kinases/GPCRs where BindingDB has dense coverage?
Head-to-head reference numbers (from cns_dti_benchmark_eval.py) are carried in
BALM_PLAPT_FAMILY so the re-test lands next to the incumbents.

PANEL + DATA (reused VERBATIM from aws/cns_dti_benchmark_eval.py)
================================================================
Same 19-target CNS panel, same family labels, same on-instance ChEMBL actives/inactives
pull (chembl_webresource_client) + UniProt REST sequences, same DUD-E-style
property-matched decoy fallback, same sparsity drops. See that file's docstring for the
full data protocol — build_panels()/auroc()/fetch_uniprot_seq()/fetch_activities()/
decoy helpers are copied here unchanged so this eval is self-contained on-instance.

MODELS RE-TESTED (each independently try/except-guarded — one failure can't sink the run)
========================================================================================
  ConPLex  (github.com/samsledje/ConPLex) — contrastive PLM DTI: co-embeds ProtBert
        (Rostlab/prot_bert, max_len 1024 -> N-terminal truncation on big channels) +
        Morgan-FP drug, returns a binding score (higher = more likely binder). We load
        the pretrained ConPLex_v1_BindingDB checkpoint (curl from cb.csail.mit.edu) into
        SimpleCoembeddingNoSigmoid and call it IN-PROCESS via the clean predict-path
        modules (conplex_dti.featurizer / .model.architectures) — the same path our
        baselines/_conplex_predict.py driver reuses (we avoid the CLI, which eagerly
        imports a tdc/wandb/lightning training stack). DOWNLOADABLE WEIGHTS: yes.

  DrugBAN  (github.com/peizhenbai/DrugBAN) — bilinear attention net on a DGL drug graph
        (dgllife smiles_to_bigraph + CanonicalAtom/BondFeaturizer, max 290 nodes) + a
        CNN over an integer-encoded protein (CHARPROTSET, max_len 1200 -> N-terminal
        truncation). The repo ships NO pretrained checkpoint, but it DOES ship the full
        BindingDB random split (datasets/bindingdb/random/{train,val}.csv). So we do a
        BOUNDED on-instance train (DRUGBAN_EPOCHS, default 2 epochs on a capped subset)
        to obtain a genuine BindingDB-trained DrugBAN, then score the panel via the
        eval-mode forward (logit; higher = more likely binder). DOWNLOADABLE WEIGHTS: no
        (train on-instance from bundled BindingDB) — documented as such in the result.

  PerceiverCPI (github.com/dmis-lab/PerceiverCPI) — SKIPPED, documented (not silently
        dropped). Reasons: (1) ships NO pretrained weights and its README requires a
        full train.py run on Davis/KIBA before predict.py works; (2) hard toolchain
        conflict — it pins torch 1.7.1 / python 3.9 + a vendored chemprop fork, which
        cannot coexist in the single torch-2.1 + DGL venv ConPLex and DrugBAN need; and
        (3) CLI-only train->predict (no importable sequence+SMILES scorer). Wiring it
        would mean a second, incompatible instance/venv + a multi-hour KIBA train for a
        baseline check — out of scope for this cheap re-test. See skipped_models in the
        result JSON. If we ever want it: separate g5 instance, torch1.7.1 venv,
        train.py on KIBA, then predict.py per target.

Writes JSON to env OUT (default /root/rej_out/cns_rejected_dti_result.json).
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
OUT = Path(os.environ.get("OUT", "/root/rej_out/cns_rejected_dti_result.json"))
CONPLEX_DIR = Path(os.environ.get("CONPLEX_DIR", "/opt/ConPLex"))
DRUGBAN_DIR = Path(os.environ.get("DRUGBAN_DIR", "/opt/DrugBAN"))
WORK = Path(os.environ.get("WORK", "/root/rej_work"))
# ConPLex pretrained BindingDB checkpoint (the working HTTPS path; README's /cb/ URL
# 301s to a dead http:// path — matches baselines/conplex.py MODEL_URL).
CONPLEX_CKPT_URL = os.environ.get(
    "CONPLEX_CKPT_URL",
    "https://cb.csail.mit.edu/conplex/data/models/BindingDB_ExperimentalValidModel.pt")

# Knobs (env-overridable). The data knobs MATCH cns_dti_benchmark_eval.py defaults so the
# panels are identical; DrugBAN-train knobs keep the on-instance train cheap + bounded.
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))
MIN_ACTIVES = int(os.environ.get("MIN_ACTIVES", "30"))
MAX_ACTIVES = int(os.environ.get("MAX_ACTIVES", "60"))
DECOY_RATIO = float(os.environ.get("DECOY_RATIO", "2.0"))
MIN_DECOYS = int(os.environ.get("MIN_DECOYS", "15"))
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))
DRUGBAN_EPOCHS = int(os.environ.get("DRUGBAN_EPOCHS", "2"))      # bounded on-instance train
DRUGBAN_MAX_TRAIN = int(os.environ.get("DRUGBAN_MAX_TRAIN", "20000"))  # cap BindingDB rows
DRUGBAN_BATCH = int(os.environ.get("DRUGBAN_BATCH", "64"))
RNG = np.random.default_rng(int(os.environ.get("SEED", "20260614")))

# ---------------------------------------------------------------------------
# CNS TARGET PANEL — IDENTICAL to aws/cns_dti_benchmark_eval.py (19 targets, 4 families).
# gene -> (uniprot_accession PRIMARY key, fallback_chembl_id, family).
# Families: "ion_channel" | "mtor_pathway" | "gpcr" | "kinase".
# ---------------------------------------------------------------------------
PANEL = {
    # --- TSC2 / mTOR pathway ---
    "MTOR":    {"uniprot": "P42345", "chembl": "CHEMBL2842",    "family": "mtor_pathway"},
    "PKM":     {"uniprot": "P14618", "chembl": "CHEMBL2107",    "family": "mtor_pathway"},
    "PPARD":   {"uniprot": "Q03181", "chembl": "CHEMBL3979",    "family": "mtor_pathway"},
    "AKT1":    {"uniprot": "P31749", "chembl": "CHEMBL4282",    "family": "mtor_pathway"},
    "RHEB":    {"uniprot": "Q15382", "chembl": None,            "family": "mtor_pathway"},
    "RPS6KB1": {"uniprot": "P23443", "chembl": "CHEMBL4501",    "family": "mtor_pathway"},

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

# Head-to-head reference: per-family mean AUROC of the INCUMBENT Track-2 models on this
# exact panel (from aws/cns_dti_benchmark_eval.py / its result). Carried so the re-test
# lands directly next to BALM + PLAPT. (These are the family means James asked about:
# kinase 0.80/0.77, mtor 0.72/0.74, gpcr 0.58/0.66, ion_channel 0.50/0.50.)
BALM_PLAPT_FAMILY = {
    "kinase":       {"BALM": 0.80, "PLAPT": 0.77},
    "mtor_pathway": {"BALM": 0.72, "PLAPT": 0.74},
    "gpcr":         {"BALM": 0.58, "PLAPT": 0.66},
    "ion_channel":  {"BALM": 0.50, "PLAPT": 0.50},
}


# ===========================================================================
# DATA LAYER — copied VERBATIM from aws/cns_dti_benchmark_eval.py.
# ===========================================================================
def auroc(labels, scores):
    """Rank-sum AUROC (ties get average rank). Higher score => label 1 (binder)."""
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
        avg = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    rank_pos = ranks[labels == 1].sum()
    n_pos, n_neg = len(pos), len(neg)
    return float((rank_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "cns-rej-dti-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


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
    """Pull binding (IC50/Ki/Kd) activities with a non-null pchembl_value.
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
    """DUD-E-style: property-matched (MW/logP/HBD/HBA envelope) but chemically
    DISSIMILAR (max Tanimoto to any active < DECOY_TANIMOTO_MAX) decoys."""
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


def build_panels():
    """Build per-target {actives, decoys, seq} sets. Returns (built, dropped)."""
    built = {}
    dropped = {}
    raw_actives = {}
    raw_inactives = {}

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

    for gene in list(built.keys()):
        n = built[gene]["n_actives_pre_drop"]
        if n < MIN_ACTIVES:
            dropped[gene] = f"sparse: {n} actives < MIN_ACTIVES={MIN_ACTIVES}"
            built.pop(gene)
            raw_actives.pop(gene, None)

    global_pool = []
    for g, acts in raw_actives.items():
        global_pool.extend(acts.keys())

    for gene in list(built.keys()):
        try:
            meta = PANEL[gene]
            actives = raw_actives[gene]
            n_act = len(actives)
            n_decoy_target = max(MIN_DECOYS, int(round(n_act * 1.0)))
            n_decoy_cap = int(round(n_act * DECOY_RATIO))
            n_decoy_target = min(n_decoy_target, n_decoy_cap)

            inactives = raw_inactives.get(gene, {})
            decoy_smiles = []
            decoy_source = None
            if len(inactives) >= MIN_DECOYS:
                items = sorted(inactives.items(), key=lambda kv: kv[1])
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


# ===========================================================================
# MODEL 1 — ConPLex (pretrained BindingDB, scored IN-PROCESS).
# Reuses the clean predict-path of baselines/_conplex_predict.py: ProtBert + Morgan
# featurizers -> SimpleCoembeddingNoSigmoid -> binding score (higher = binder).
# ===========================================================================
class ConplexScorer:
    name = "ConPLex"

    def __init__(self):
        import torch
        sys.path.insert(0, str(CONPLEX_DIR))
        from conplex_dti.featurizer import MorganFeaturizer, ProtBertFeaturizer
        from conplex_dti.model.architectures import SimpleCoembeddingNoSigmoid
        self.torch = torch
        self.dev = torch.device(DEVICE if torch.cuda.is_available() or DEVICE == "cpu" else "cpu")
        cache = str(WORK / "conplex_cache")
        Path(cache).mkdir(parents=True, exist_ok=True)
        # per_tok=False -> one pooled ProtBert vector per sequence (predict path).
        self.tfeat = ProtBertFeaturizer(save_dir=cache, per_tok=False).to(self.dev)
        self.dfeat = MorganFeaturizer(save_dir=cache).to(self.dev)
        ckpt = WORK / "ConPLex_v1_BindingDB.pt"
        if not ckpt.is_file():
            urllib.request.urlretrieve(CONPLEX_CKPT_URL, str(ckpt))
        self.model = SimpleCoembeddingNoSigmoid(
            self.dfeat.shape, self.tfeat.shape, 1024)
        # ConPLex BindingDB checkpoint is a plain tensor state_dict -> weights_only=True
        # is safe (and avoids arbitrary-code unpickling on a downloaded file).
        try:
            state = torch.load(str(ckpt), map_location=self.dev, weights_only=True)
        except Exception:
            # older torch lacks the weights_only kwarg; fall back to default.
            state = torch.load(str(ckpt), map_location=self.dev)
        self.model.load_state_dict(state)
        self.model = self.model.eval().to(self.dev)

    def score_target(self, seq, smiles_list):
        torch = self.torch
        # Pre-load features (featurizers cache by string).
        self.tfeat.preload([seq])
        self.dfeat.preload(list(dict.fromkeys(smiles_list)))
        out = []
        tvec = self.tfeat(seq).to(self.dev)
        with torch.set_grad_enabled(False):
            for smi in smiles_list:
                dvec = self.dfeat(smi).to(self.dev)
                val = self.model(dvec.unsqueeze(0), tvec.unsqueeze(0))
                out.append(float(np.asarray(val.detach().cpu()).ravel()[0]))
        return out


def score_conplex(panels):
    scorer = ConplexScorer()
    out = {}
    for gene, p in panels.items():
        smiles = list(p["actives"]) + list(p["decoys"])
        scores = scorer.score_target(p["seq"], smiles)
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
        print(f"[conplex] {gene} ({p['family']}): AUROC={a}", flush=True)
    return out


# ===========================================================================
# MODEL 2 — DrugBAN (NO shipped weights -> bounded on-instance train on the BUNDLED
# BindingDB random split, then score). DGL drug graph + CNN over int-encoded protein.
# ===========================================================================
def _drugban_imports():
    sys.path.insert(0, str(DRUGBAN_DIR))
    os.chdir(DRUGBAN_DIR)  # configs/datasets referenced relative to repo root
    import torch  # noqa
    from models import DrugBAN
    from configs import get_cfg_defaults
    from dataloader import DTIDataset
    from utils import graph_collate_func, set_seed
    return DrugBAN, get_cfg_defaults, DTIDataset, graph_collate_func, set_seed


def _train_drugban():
    """Bounded on-instance train of DrugBAN on the bundled BindingDB random split.
    Returns (model, cfg, device). Capped to DRUGBAN_MAX_TRAIN rows x DRUGBAN_EPOCHS."""
    import torch
    import pandas as pd
    from torch.utils.data import DataLoader
    DrugBAN, get_cfg_defaults, DTIDataset, graph_collate_func, set_seed = _drugban_imports()

    cfg = get_cfg_defaults()
    cfg_path = DRUGBAN_DIR / "configs" / "DrugBAN.yaml"
    if cfg_path.is_file():
        cfg.merge_from_file(str(cfg_path))
    cfg.freeze()
    set_seed(int(os.environ.get("SEED", "20260614")))
    dev = torch.device(DEVICE if torch.cuda.is_available() or DEVICE == "cpu" else "cpu")

    train_csv = DRUGBAN_DIR / "datasets" / "bindingdb" / "random" / "train.csv"
    df = pd.read_csv(train_csv)
    if len(df) > DRUGBAN_MAX_TRAIN:
        df = df.sample(n=DRUGBAN_MAX_TRAIN, random_state=int(os.environ.get("SEED", "20260614")))
    df = df.reset_index(drop=True)
    ds = DTIDataset(df.index.values, df)
    loader = DataLoader(ds, batch_size=DRUGBAN_BATCH, shuffle=True, drop_last=True,
                        num_workers=2, collate_fn=graph_collate_func)

    model = DrugBAN(**cfg).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.SOLVER.LR)
    bce = torch.nn.BCEWithLogitsLoss()
    model.train()
    for ep in range(DRUGBAN_EPOCHS):
        seen = 0
        for batch in loader:
            v_d, v_p, labels = batch
            v_d, v_p = v_d.to(dev), v_p.to(dev)
            labels = labels.float().to(dev)
            opt.zero_grad()
            _, _, _, score = model(v_d, v_p)
            score = score.squeeze(-1) if score.dim() > 1 else score
            loss = bce(score, labels)
            loss.backward()
            opt.step()
            seen += len(labels)
        print(f"[drugban] train epoch {ep + 1}/{DRUGBAN_EPOCHS} seen={seen} "
              f"last_loss={float(loss):.4f}", flush=True)
    model.eval()
    return model, cfg, dev


def score_drugban(panels):
    """Score each panel target by reusing DrugBAN's OWN DTIDataset + graph_collate_func, so
    the (75-dim node-feat) drug graph + (CHARPROTSET, max_len 1200) protein int-encoding are
    BYTE-IDENTICAL to what the on-instance-trained model saw. SMILES rdkit can't graph are
    dropped (counted in n_smiles_dropped_graph). eval-mode forward -> logit; higher = binder."""
    import torch
    import pandas as pd
    from torch.utils.data import DataLoader
    model, cfg, dev = _train_drugban()
    sys.path.insert(0, str(DRUGBAN_DIR))
    from dataloader import DTIDataset
    from utils import graph_collate_func
    from rdkit import Chem

    out = {}
    for gene, p in panels.items():
        try:
            seq = p["seq"]
            smiles = list(p["actives"]) + list(p["decoys"])
            labels = [1] * len(p["actives"]) + [0] * len(p["decoys"])
            # Pre-filter SMILES that DrugBAN's featurizer would choke on (rdkit-unparseable
            # or >290 heavy atoms), so the dataset never raises mid-batch.
            rows, kept_labels = [], []
            for smi, lab in zip(smiles, labels):
                m = Chem.MolFromSmiles(smi)
                if m is None or m.GetNumAtoms() > cfg.DRUG.MAX_NODES:
                    continue
                rows.append({"SMILES": smi, "Protein": seq, "Y": float(lab)})
                kept_labels.append(lab)
            if not rows:
                out[gene] = {"family": p["family"], "auroc": None,
                             "error": "no DrugBAN-graphable SMILES for this target"}
                continue
            df = pd.DataFrame(rows)
            ds = DTIDataset(df.index.values, df)
            loader = DataLoader(ds, batch_size=DRUGBAN_BATCH, shuffle=False,
                                drop_last=False, num_workers=2, collate_fn=graph_collate_func)
            scores = []
            with torch.no_grad():
                for v_d, v_p, _ in loader:
                    v_d, v_p = v_d.to(dev), v_p.to(dev)
                    _, _, score, _ = model(v_d, v_p, mode="eval")
                    # DECODER.BINARY=1 -> score is (batch, 1) logit; higher = binder.
                    sc = np.asarray(score.detach().cpu(), dtype=float).reshape(-1)
                    scores.extend(float(v) for v in sc)
            a = auroc(kept_labels, scores)
            n_a = sum(1 for l in kept_labels if l == 1)
            n_d = sum(1 for l in kept_labels if l == 0)
            a_scores = [s for s, l in zip(scores, kept_labels) if l == 1]
            d_scores = [s for s, l in zip(scores, kept_labels) if l == 0]
            out[gene] = {
                "family": p["family"], "chembl_id": p["chembl_id"],
                "auroc": a, "n_actives": n_a, "n_decoys": n_d,
                "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
                "n_smiles_dropped_graph": len(smiles) - len(kept_labels),
                "mean_active_score": round(float(np.mean(a_scores)), 5) if a_scores else None,
                "mean_decoy_score": round(float(np.mean(d_scores)), 5) if d_scores else None,
            }
            print(f"[drugban] {gene} ({p['family']}): AUROC={a} "
                  f"(dropped {len(smiles) - len(kept_labels)} graphs)", flush=True)
        except Exception as e:
            out[gene] = {"family": p["family"], "auroc": None,
                         "error": f"{type(e).__name__}: {e}"}
            print(f"[warn] drugban {gene} failed: {e}\n{traceback.format_exc()[:600]}",
                  flush=True)
    return out


# ===========================================================================
# FAMILY AGGREGATION — the headline (mean AUROC + range per family per model).
# Copied VERBATIM from aws/cns_dti_benchmark_eval.py so it's directly comparable.
# ===========================================================================
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
    WORK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    results = {
        "task": ("RE-TEST of previously-rejected/under-tested DTI models (ConPLex, DrugBAN; "
                 "PerceiverCPI documented-skip) on the SAME 19-target CNS panel as "
                 "cns_dti_benchmark_eval.py. Were they dismissed unfairly on tiny Nav panels? "
                 "Per-target binder-vs-decoy AUROC -> per-FAMILY aggregate (headline), head-to-head "
                 "vs BALM/PLAPT. Nav-blind != CNS-blind."),
        "device": DEVICE,
        "config": {
            "active_pchembl_min": ACTIVE_PCHEMBL, "inactive_pchembl_max": INACTIVE_PCHEMBL,
            "min_actives": MIN_ACTIVES, "max_actives": MAX_ACTIVES,
            "decoy_ratio_cap": DECOY_RATIO, "min_decoys": MIN_DECOYS,
            "decoy_tanimoto_max": DECOY_TANIMOTO_MAX, "binding_types": BINDING_TYPES,
            "drugban_epochs": DRUGBAN_EPOCHS, "drugban_max_train": DRUGBAN_MAX_TRAIN,
            "drugban_batch": DRUGBAN_BATCH,
        },
        "panel_definition": {g: {"uniprot": m["uniprot"], "family": m["family"],
                                 "fallback_chembl": m["chembl"]}
                             for g, m in PANEL.items()},
        "incumbent_family_means_for_headtohead": BALM_PLAPT_FAMILY,
        "rejection_history": {
            "ConPLex": ("written off as Nav-blind on n=11 Nav1.8 panel (AUROC ~0.437); "
                        "never run on the broad CNS panel until now"),
            "DrugBAN": ("only PLANNED as a Nav baseline; the wave shipped PLAPT+DeepPurpose "
                        "instead. No shipped weights -> bounded on-instance train on the "
                        "BUNDLED BindingDB random split, then scored on the CNS panel"),
            "PerceiverCPI": ("documented-skip; see skipped_models"),
        },
        "skipped_models": {
            "PerceiverCPI": {
                "repo": "github.com/dmis-lab/PerceiverCPI",
                "reason": ("no pretrained weights (README requires a full train.py run on "
                           "Davis/KIBA before predict.py); CLI-only train->predict (no "
                           "importable seq+SMILES scorer); hard toolchain conflict — pins "
                           "torch 1.7.1 / python 3.9 + a vendored chemprop fork that cannot "
                           "coexist with the torch-2.1 + DGL venv ConPLex and DrugBAN need."),
                "to_revisit": ("separate g5 instance, torch1.7.1 venv, train.py on KIBA "
                               "(~hours), then predict.py per target via toy_dataset CSV format "
                               "(columns: smiles,sequences,label)."),
            },
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

    # --- Score with each rejected model (guarded; one failure can't sink the others) ---
    models = {}
    section("ConPLex", score_conplex, models, panels)
    section("DrugBAN", score_drugban, models, panels)
    results["per_target_auroc"] = models

    # --- Family aggregation per model — THE HEADLINE ---
    family = {}
    for mname, per_target in models.items():
        if isinstance(per_target, dict) and "error" not in per_target:
            try:
                family[mname] = aggregate_by_family(per_target)
            except Exception as e:
                family[mname] = {"error": f"{type(e).__name__}: {e}"}
    results["family_aggregate"] = family

    # --- Head-to-head: per-family mean AUROC, re-tested models + BALM/PLAPT side by side ---
    h2h = {}
    fam_names = set(BALM_PLAPT_FAMILY.keys())
    for m in family.values():
        if isinstance(m, dict):
            fam_names.update(k for k in m if not k.startswith("_"))
    for fam in sorted(fam_names):
        row = {mname: (family.get(mname, {}).get(fam, {}) or {}).get("mean_auroc")
               for mname in models}
        row.update({k: BALM_PLAPT_FAMILY.get(fam, {}).get(k) for k in ("BALM", "PLAPT")})
        h2h[fam] = row
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
