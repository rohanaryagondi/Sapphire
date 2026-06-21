"""Shared helpers for the 'where is MAMMAL data-suited' tests.

Used by experiments/datafit_ceiling.py (Quiver-anchored panel) and
experiments/datafit_curve.py (binder-vs-decoy AUROC vs training-pair count).

What it does:
  - Pull binders & per-target pairs from BindingDB_Kd (the dataset the DTI head
    was finetuned on) via PyTDC, harmonized exactly like the MAMMAL data module
    (max_affinity dedup, log-transform).
  - Sample two flavours of decoy: pure random (drawn from BindingDB compounds
    tested on OTHER targets) and property-matched (same, with an MW window per
    binder). Both are 'open-world non-binders' against the queried target.
  - Compute AUROC + Spearman without sklearn/scipy so the script runs in the
    conda 'mammal' env without extra deps. (Tie-aware: half-credit ties.)

We default to the PEER DTI checkpoint (the one Phase 1 found correct for our
problem classes). Norm constants 6.286 / 1.542.

Leakage caveat for the Spearman piece: TDC's default split is cold_split. The
PEER checkpoint trained on a *different* split — so test pairs returned here may
have been seen during PEER training. We report this as an upper bound, and
flag it in the writeup. For the AUROC/off-target tests the question is "did the
head encode binding for this target at all?" and memorization counts.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")


# --------------------------------------------------------------------------- #
# BindingDB_Kd loading (harmonized exactly like MAMMAL's data module).
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _harmonized_kd():
    """Return the harmonized BindingDB_Kd dataframe (cached for the whole process).

    Mirrors mammal/examples/dti_bindingdb_kd/pl_data_module.py:
        data = DTI(name='BindingDB_Kd')
        data.harmonize_affinities(mode='max_affinity')
        data.convert_to_log(form='binding')   # Y -> pKd (-log10 M)
    """
    from tdc.multi_pred import DTI

    d = DTI(name="BindingDB_Kd")
    d.harmonize_affinities(mode="max_affinity")
    d.convert_to_log(form="binding")
    return d.get_data().copy()


@lru_cache(maxsize=1)
def _cold_test_kd():
    """Default cold-split test fold (used by the original cold-split checkpoint).

    Returns the raw test split (Y is Kd in nM there — convert before use).
    """
    from tdc.multi_pred import DTI

    return DTI(name="BindingDB_Kd").get_split()["test"]


def get_pairs_for_target(target_id: str) -> list[tuple[str, float]]:
    """All (SMILES, pKd) pairs in BindingDB_Kd for one target (harmonized pool)."""
    df = _harmonized_kd()
    sub = df[df["Target_ID"].astype(str) == target_id]
    out = [(str(s), float(y)) for s, y in zip(sub["Drug"], sub["Y"]) if y is not None]
    return out


def get_test_pairs_for_target(target_id: str) -> list[tuple[str, float]]:
    """Cold-split test pairs for one target — Y is converted to pKd here.

    CAVEAT: pairs may have been in PEER training (different split). Report as
    upper bound for the PEER checkpoint.
    """
    test = _cold_test_kd()
    sub = test[test["Target_ID"].astype(str) == target_id].dropna(subset=["Y"])
    sub = sub[sub["Y"] > 0]
    rows = []
    for s, y in zip(sub["Drug"], sub["Y"]):
        rows.append((str(s), 9.0 - math.log10(float(y))))  # nM -> pKd
    return rows


# --------------------------------------------------------------------------- #
# Binder selection.
# --------------------------------------------------------------------------- #
def get_binders(target_id: str, pkd_threshold: float = 7.0,
                n_max: int | None = None,
                seed: int = 42) -> list[tuple[str, float]]:
    """Return up to n_max distinct (SMILES, pKd) binders with pKd >= threshold.

    Distinct on SMILES (some target rows duplicate after harmonize, keep best pKd).
    Sorted by pKd desc so n_max keeps the strongest. Deterministic given seed
    (only used to break ties on equal pKd).
    """
    pairs = [(s, p) for s, p in get_pairs_for_target(target_id) if p >= pkd_threshold]
    # Collapse duplicate SMILES (keep max pKd per SMILES)
    best: dict[str, float] = {}
    for s, p in pairs:
        if s not in best or p > best[s]:
            best[s] = p
    items = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    if n_max is not None:
        items = items[:n_max]
    return [(s, p) for s, p in items]


# --------------------------------------------------------------------------- #
# Decoy sampling.
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _smiles_by_target() -> dict[str, set[str]]:
    """target_id -> set of all SMILES ever measured against it (harmonized pool)."""
    df = _harmonized_kd()
    out: dict[str, set[str]] = {}
    for t, s in zip(df["Target_ID"].astype(str), df["Drug"]):
        out.setdefault(t, set()).add(str(s))
    return out


@lru_cache(maxsize=1)
def _all_smiles_with_mw() -> list[tuple[str, float]]:
    """All unique SMILES in BindingDB_Kd with their molecular weight (rdkit)."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    df = _harmonized_kd()
    uniq = sorted(set(str(s) for s in df["Drug"]))
    out: list[tuple[str, float]] = []
    for s in uniq:
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        out.append((s, float(Descriptors.MolWt(m))))
    return out


def sample_random_decoys(target_id: str, n: int, seed: int = 42) -> list[str]:
    """Sample n SMILES uniformly from BindingDB pool that were NEVER measured
    against target_id (so they're 'unknown affinity, treat as non-binder')."""
    rng = random.Random(seed)
    on_target = _smiles_by_target().get(target_id, set())
    pool = [s for s, _mw in _all_smiles_with_mw() if s not in on_target]
    n = min(n, len(pool))
    return rng.sample(pool, n)


def sample_matched_decoys(target_id: str, binder_smiles: Sequence[str],
                          n_per_binder: int = 3, mw_tol: float = 50.0,
                          seed: int = 42) -> list[str]:
    """For each binder SMILES, draw n_per_binder decoys within +/- mw_tol Da MW
    from the off-target SMILES pool. Returns deduplicated flat list."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    rng = random.Random(seed)
    on_target = _smiles_by_target().get(target_id, set())
    pool_with_mw = [(s, mw) for s, mw in _all_smiles_with_mw() if s not in on_target]

    out: set[str] = set()
    for bs in binder_smiles:
        m = Chem.MolFromSmiles(bs)
        if m is None:
            continue
        bmw = float(Descriptors.MolWt(m))
        candidates = [s for s, mw in pool_with_mw if abs(mw - bmw) <= mw_tol and s not in out]
        if not candidates:
            continue
        k = min(n_per_binder, len(candidates))
        for s in rng.sample(candidates, k):
            out.add(s)
    return list(out)


# --------------------------------------------------------------------------- #
# Metrics (no sklearn / scipy — keeps the conda env clean).
# --------------------------------------------------------------------------- #
def auroc(pos_scores: Sequence[float], neg_scores: Sequence[float]) -> float:
    """Tie-aware AUROC via the Mann-Whitney U statistic.
    AUROC = P(score(pos) > score(neg)) + 0.5 * P(tie). NaN if either is empty.
    """
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos_scores) * len(neg_scores))


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = math.sqrt(sum((a - mx) ** 2 for a in x))
    vy = math.sqrt(sum((b - my) ** 2 for b in y))
    return cov / (vx * vy) if vx and vy else float("nan")


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    def rank(v: Sequence[float]) -> list[float]:
        # Average-rank for ties
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                r[idx[k]] = avg
            i = j + 1
        return r

    return pearson(rank(x), rank(y))


def enrichment_factor(scores: Sequence[float], labels: Sequence[int],
                      top_frac: float = 0.05) -> float:
    """Standard enrichment factor at the top fraction.

    scores: predicted pKd (higher = predicted binder); labels: 1 for binder, 0 for decoy.
    EF_x% = (TP rate in top x%) / (total positive rate). 1.0 = no enrichment.
    """
    pairs = sorted(zip(scores, labels), key=lambda t: -t[0])
    n = len(pairs)
    if n == 0:
        return float("nan")
    k = max(1, int(round(n * top_frac)))
    tp_top = sum(l for _s, l in pairs[:k])
    total_pos = sum(labels)
    if total_pos == 0:
        return float("nan")
    return (tp_top / k) / (total_pos / n)


# --------------------------------------------------------------------------- #
# Small data container, used by both experiments.
# --------------------------------------------------------------------------- #
@dataclass
class TargetSpec:
    """One row of the panel / curve sweep."""
    accession: str
    gene: str
    pairs: int           # n training pairs in BindingDB_Kd
    target_class: str    # 'kinase', 'gpcr', 'nuclear_receptor', 'ion_channel', 'other'


def load_per_target_csv(repo_root) -> list[TargetSpec]:
    """Read results/dti_train_data_per_target.csv into TargetSpec rows."""
    import csv
    from pathlib import Path

    path = Path(repo_root) / "results" / "dti_train_data_per_target.csv"
    rows: list[TargetSpec] = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append(TargetSpec(
                    accession=r["accession"],
                    gene=r.get("gene", ""),
                    pairs=int(r["pairs"]),
                    target_class=r.get("class", "other"),
                ))
            except (KeyError, ValueError):
                continue
    return rows


def stratified_curve_targets(rows: Iterable[TargetSpec],
                             bin_edges: Sequence[float],
                             per_bin: int,
                             seed: int = 42,
                             exclude: Iterable[str] = ()) -> list[TargetSpec]:
    """Pick per_bin random targets whose `pairs` count falls inside each bin.

    bin_edges: list of (lo_inclusive, hi_inclusive) tuples, OR a flat list of
    edges turned into consecutive bins.
    Returns flat list, in bin order. Deterministic given seed.
    """
    excluded = set(exclude)
    rng = random.Random(seed)

    if isinstance(bin_edges[0], (tuple, list)):
        bins = [tuple(e) for e in bin_edges]
    else:
        bins = list(zip(bin_edges[:-1], bin_edges[1:]))

    pool = [r for r in rows if r.accession not in excluded]
    picked: list[TargetSpec] = []
    for lo, hi in bins:
        in_bin = [r for r in pool if lo <= r.pairs <= hi]
        rng.shuffle(in_bin)
        picked.extend(in_bin[:per_bin])
    return picked
