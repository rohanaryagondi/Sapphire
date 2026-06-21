"""Live LOCAL per-target CNS binder predictions for the DTI track.

These are the per-target Morgan-FP + GradientBoosting fine-tunes trained by
`experiments/cns_pertarget_finetune.py` (one joblib per data-rich CNS target under
`models/cns_pertarget/`). They are CPU-only and lightweight, so — unlike the GPU models
(ESM-2 / Boltz-2 / MAMMAL) that need the AWS endpoint — they run IN this FastAPI process.

This is gated behind EXPLORER_LOCAL_MODELS=1 so the default app + the test-suite stay in
stub mode (green). When enabled, the DTI track returns a REAL binder probability for the
data-rich CNS targets, with a Tanimoto-to-train applicability-domain confidence flag; any
target without a local model (or an unparseable SMILES) falls through to stub/AWS.
"""
from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

# repo root = .../ui/explorer/backend/local_models.py -> parents[3]
_REPO = Path(__file__).resolve().parents[3]
_MODEL_DIR = _REPO / "models" / "cns_pertarget"

# UniProt accession -> gene (the data-rich CNS targets we fine-tuned). Mirrors
# experiments/cns_pertarget_finetune.py.
_UNIPROT_TO_GENE = {
    "P42345": "MTOR", "P14618": "PKM", "Q03181": "PPARD", "P31749": "AKT1", "P23443": "RPS6KB1",
    "Q15858": "SCN9A", "Q9Y5Y9": "SCN10A", "Q99250": "SCN2A", "Q14524": "SCN5A",
    "Q13936": "CACNA1C", "Q05586": "GRIN1", "Q13224": "GRIN2B",
    "P14416": "DRD2", "P28223": "HTR2A", "P49841": "GSK3B", "Q5S007": "LRRK2", "P56817": "BACE1",
    # rescued from PubChem qHTS (non-ChEMBL) — epilepsy channels ChEMBL alone couldn't fine-tune
    "O43526": "KCNQ2", "O95180": "CACNA1H",
}
# also accept gene symbols / common aliases typed directly
_ALIAS_TO_GENE = {g: g for g in _UNIPROT_TO_GENE.values()}
_ALIAS_TO_GENE.update({"PKM2": "PKM", "NAV1.7": "SCN9A", "NAV1.8": "SCN10A", "NAV1.2": "SCN2A",
                       "NAV1.5": "SCN5A", "CAV1.2": "CACNA1C", "S6K1": "RPS6KB1",
                       "KV7.2": "KCNQ2", "CAV3.2": "CACNA1H"})


def enabled() -> bool:
    return os.environ.get("EXPLORER_LOCAL_MODELS", "").strip() in ("1", "true", "yes")


# Tracks served by a live LOCAL model when EXPLORER_LOCAL_MODELS=1 (CPU, in-process, no AWS).
LOCAL_TRACKS = ("dti", "bbbp", "toxicity")


def live_tracks() -> list:
    """Track ids currently served live-local (empty unless enabled + the model dir exists)."""
    if not enabled():
        return []
    live = []
    if (_MODEL_DIR.exists() and any(_MODEL_DIR.glob("*.joblib"))):
        live.append("dti")
    for tid, name in (("bbbp", "BBB_Martins"), ("toxicity", "hERG_Karim")):
        if (_DERISK_DIR / f"{name}.joblib").is_file():
            live.append(tid)
    return live


def _resolve_gene(payload: dict) -> str | None:
    for key in ("uniprot_acc", "uniprot", "accession"):
        v = (payload.get(key) or "").strip().upper()
        if v in _UNIPROT_TO_GENE:
            return _UNIPROT_TO_GENE[v]
    for key in ("gene", "target", "target_name"):
        v = (payload.get(key) or "").strip().upper()
        if v in _ALIAS_TO_GENE:
            return _ALIAS_TO_GENE[v]
    return None


@lru_cache(maxsize=64)
def _load(gene: str):
    # SECURITY: joblib.load is pickle-based, but these artifacts are produced ONLY by our own
    # experiments/cns_pertarget_finetune.py on this same machine (not untrusted input) and live
    # under the repo's models/ dir — so this is trusted, local deserialization, not external data.
    p = _MODEL_DIR / f"{gene}.joblib"
    if not p.is_file():
        return None
    import joblib
    return joblib.load(p)


def predict_dti(payload: dict) -> dict | None:
    """Return a live DTI prediction for a data-rich CNS target, or None to fall through.

    Output matches the dti track's score_kind='affinity' shape + adds the binder
    probability, the model's held-out scaffold AUROC, and a Tanimoto-to-train confidence flag.
    """
    if not enabled():
        return None
    gene = _resolve_gene(payload)
    if not gene:
        return None
    smiles = (payload.get("smiles") or "").strip()
    if not smiles:
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, DataStructs
        import numpy as np
    except Exception:
        return None
    bundle = _load(gene)
    if bundle is None:
        return None
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    bv = AllChem.GetMorganFingerprintAsBitVect(m, bundle.get("fp_radius", 2),
                                               nBits=bundle.get("fp_bits", 2048))
    arr = np.zeros((bundle.get("fp_bits", 2048),), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(bv, arr)
    p_bind = float(bundle["clf"].predict_proba([arr])[0, 1])
    # Tanimoto-to-train applicability-domain flag (max sim to any training active)
    train_fps = bundle.get("train_active_fps") or []
    max_tan = max((DataStructs.TanimotoSimilarity(bv, t) for t in train_fps), default=0.0)
    # Thresholds per the de-risking finding (far-OOD < ~0.35 is where ligand-QSAR collapses).
    if max_tan >= 0.5:
        conf = "high (in training domain)"
    elif max_tan >= 0.35:
        conf = "medium (partial similarity to training actives — treat the call as a weak prior)"
    else:
        conf = "low (novel chemotype, out-of-domain — QSAR unreliable here; confirm with Boltz-2/Track 3)"
    cv = bundle.get("scaffold_cv_auroc")
    return {
        "score_kind": "affinity",
        "value": round(p_bind, 3),
        "units": "P(binder) — per-target fine-tune (Morgan-FP+GBT)",
        "binder_call": "likely binder" if p_bind >= 0.5 else "unlikely binder",
        "target_gene": gene,
        "model": f"cns_pertarget/{gene} (scaffold-split CV AUROC {cv})",
        "confidence": conf,
        "tanimoto_to_train": round(float(max_tan), 3),
        "note": ("LIVE local per-target fine-tune (CPU, no AWS). Per-target binder model; "
                 "trust within the applicability domain (see confidence). For structure/"
                 "selectivity hand to Boltz-2 (Track 3)."),
        "_local": True,
    }


# ---- De-risking (BBBP / hERG / DILI): MapLight-class FP+GBT, live local ---------------------
_DERISK_DIR = _REPO / "models" / "derisking_local"


@lru_cache(maxsize=8)
def _load_derisk(name: str):
    # SECURITY: same as _load — these joblibs are produced by our own
    # experiments/derisking_local_train.py on this machine; trusted local deserialization.
    p = _DERISK_DIR / f"{name}.joblib"
    if not p.is_file():
        return None
    import joblib
    return joblib.load(p)


def _derisk_features(smiles: str, bundle):
    """Reproduce derisking_local_train.featurize EXACTLY using the bundle's desc_names."""
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs, MACCSkeys
    from rdkit.ML.Descriptors import MoleculeDescriptors
    import numpy as np
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None, None
    mbv = AllChem.GetMorganFingerprintAsBitVect(m, bundle.get("fp_radius", 2),
                                                nBits=bundle.get("fp_bits", 2048))
    morgan = np.zeros((bundle.get("fp_bits", 2048),), dtype=np.float32)
    DataStructs.ConvertToNumpyArray(mbv, morgan)
    maccs = np.zeros((167,), dtype=np.float32)
    DataStructs.ConvertToNumpyArray(MACCSkeys.GenMACCSKeys(m), maccs)
    calc = MoleculeDescriptors.MolecularDescriptorCalculator(bundle["desc_names"])
    try:
        desc = np.array(calc.CalcDescriptors(m), dtype=np.float32)
        desc = np.nan_to_num(desc, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception:
        desc = np.zeros((len(bundle["desc_names"]),), dtype=np.float32)
    return np.concatenate([morgan, maccs, desc]), mbv


def _score_one(smiles: str, model_name: str):
    bundle = _load_derisk(model_name)
    if bundle is None:
        return None
    try:
        from rdkit.Chem import DataStructs
        import numpy as np  # noqa
    except Exception:
        return None
    feats, bv = _derisk_features(smiles, bundle)
    if feats is None:
        return None
    p = float(bundle["clf"].predict_proba([feats])[0, 1])
    # applicability domain = similarity to ANY training compound (both classes)
    train_fps = bundle.get("train_all_fps") or bundle.get("train_active_fps") or []
    max_tan = max((DataStructs.TanimotoSimilarity(bv, t) for t in train_fps), default=0.0)
    return p, max_tan, bundle


def _conf(max_tan: float) -> str:
    if max_tan >= 0.5:
        return "high (in domain)"
    if max_tan >= 0.35:
        return "medium"
    return "low (novel chemotype — out-of-domain)"


def predict_bbbp(payload: dict) -> dict | None:
    """Live BBB-penetrance prediction (Track 4) — MapLight-class FP+GBT, local."""
    if not enabled():
        return None
    smiles = (payload.get("smiles") or "").strip()
    if not smiles:
        return None
    r = _score_one(smiles, "BBB_Martins")
    if r is None:
        return None
    p, tan, b = r
    return {
        "score_kind": "probability", "value": round(p, 3),
        "call": "BBB+" if p >= 0.5 else "BBB-",
        "model": f"derisking_local/BBB_Martins (scaffold-test AUROC {b.get('test_scaffold_auroc')})",
        "confidence": _conf(tan), "tanimoto_to_train": round(float(tan), 3),
        "note": "LIVE local MapLight-class BBBP model (Morgan+MACCS+RDKit-desc -> GBT, CPU). "
                "Gate by Tanimoto-to-train; far-OOD is low-confidence.",
        "_local": True,
    }


def predict_toxicity(payload: dict) -> dict | None:
    """Live tox panel (Track 5): hERG + DILI — MapLight-class FP+GBT, local."""
    if not enabled():
        return None
    smiles = (payload.get("smiles") or "").strip()
    if not smiles:
        return None
    endpoints = []
    for label, name in [("hERG", "hERG_Karim"), ("DILI", "DILI")]:
        r = _score_one(smiles, name)
        if r is None:
            continue
        p, tan, b = r
        endpoints.append({"name": label, "value": round(p, 3),
                          "call": "flag" if p >= 0.5 else "low risk",
                          "confidence": _conf(tan),
                          "auroc": b.get("test_scaffold_auroc")})
    if not endpoints:
        return None
    return {
        "score_kind": "panel", "endpoints": endpoints,
        "model": "derisking_local/hERG_Karim + DILI (MapLight-class FP+GBT, CPU)",
        "note": "LIVE local de-risking (hERG + DILI). ClinTox intentionally omitted (dead). "
                "Treat a flag as a liability signal, not a kill; gate by Tanimoto-to-train.",
        "_local": True,
    }
