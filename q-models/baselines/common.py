"""baselines.common — the model-agnostic scoring contract + cross-model statistics.

THE GOVERNING RULE (why this file exists):
    A ConPLex probability, a MAMMAL pKd, and a Boltz-2 affinity live on three
    different scales. Comparing their raw values is meaningless. So every model,
    for a fixed ordered list of (protein_seq, SMILES) pairs, produces a list of
    floats, and we compare ONLY rank-derived statistics computed identically for
    every model:
        - Spearman ρ            (correlation tests; rank-only)
        - Mann-Whitney AUROC    (binder-vs-decoy / selectivity)
        - enrichment factor     (top-k% triage)
        - within-model z-separation  (actives vs decoys, scale-free)
    Confidence intervals are bootstrap (stratified by class for AUROC/EF so the
    27-vs-500 and 38-vs-201 imbalances are respected); model-vs-model comparisons
    use a PAIRED bootstrap (same resampled compounds scored by both models) so the
    Δ accounts for the correlation between two models scoring the same molecules.

These are simple pure-numpy implementations so the file has no heavy deps and can
run in any env (the `mammal` env, a plain python). Metric definitions match the
existing phase scripts (phase3_realdata_specificity.auroc, phase5_wdr91_spr EF).
"""

from __future__ import annotations

from typing import Callable, Protocol, Sequence, runtime_checkable

import numpy as np


# --------------------------------------------------------------------------- #
# The scoring contract                                                         #
# --------------------------------------------------------------------------- #
@runtime_checkable
class Scorer(Protocol):
    """A model that scores (protein_seq, SMILES) pairs.

    `kind` documents what the raw score means ("pkd" | "probability" | "affinity")
    — used only for labelling; it is deliberately NOT used in any cross-model
    number (see the governing rule above). `runs_full_screen` is False for models
    that are per-pair oracles too expensive to screen large decoy sets (Boltz-2).
    """

    name: str
    kind: str
    runs_full_screen: bool

    def score_pair(self, protein_seq: str, smiles: str) -> float: ...

    def score_batch(self, pairs: Sequence[tuple[str, str]]) -> list[float]: ...


# --------------------------------------------------------------------------- #
# Rank / scale helpers                                                          #
# --------------------------------------------------------------------------- #
def rankdata(x: Sequence[float]) -> np.ndarray:
    """Average-rank of x (ties get the mean rank), matching scipy's default."""
    a = np.asarray(x, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    sa = a[order]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and sa[j + 1] == sa[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def zscore(x: Sequence[float]) -> np.ndarray:
    """Standardise within a model's own score distribution (robust to scale)."""
    a = np.asarray(x, dtype=float)
    sd = a.std(ddof=1) if len(a) > 1 else 0.0
    return (a - a.mean()) / sd if sd > 0 else a - a.mean()


# --------------------------------------------------------------------------- #
# Core metrics (pure numpy; definitions match the existing phase scripts)       #
# --------------------------------------------------------------------------- #
def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    rx, ry = rankdata(x), rankdata(y)
    return _pearson(rx, ry)


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def auroc(y_true: Sequence[int], scores: Sequence[float]) -> float:
    """Mann-Whitney AUROC; ties contribute 0.5. NaN if one class is empty."""
    y = np.asarray(y_true)
    s = np.asarray(scores, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # rank-based form: (sum of ranks of positives - n_pos*(n_pos+1)/2) / (n_pos*n_neg)
    ranks = rankdata(np.concatenate([pos, neg]))
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)))


def enrichment_factor(y_true: Sequence[int], scores: Sequence[float], frac: float) -> float:
    """EF at the top `frac` (e.g. 0.05) = (hit-rate in top bin) / (overall hit-rate)."""
    y = np.asarray(y_true)
    s = np.asarray(scores, dtype=float)
    n_total = len(y)
    n_pos = int(y.sum())
    if n_pos == 0 or n_total == 0:
        return float("nan")
    k = max(1, int(round(n_total * frac)))
    top = y[np.argsort(s)[::-1][:k]]
    return float(top.mean() / (n_pos / n_total))


def z_separation(scores: Sequence[float], labels: Sequence[int]) -> float:
    """(mean_active - mean_decoy) / pooled_SD — a scale-free separation in z-units."""
    z = zscore(scores)
    y = np.asarray(labels)
    pos, neg = z[y == 1], z[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float(pos.mean() - neg.mean())


# --------------------------------------------------------------------------- #
# Bootstrap confidence intervals                                                #
# --------------------------------------------------------------------------- #
def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def auroc_ci(y_true, scores, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Stratified bootstrap CI for AUROC (resample positives and negatives separately)."""
    y = np.asarray(y_true)
    s = np.asarray(scores, dtype=float)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return (float("nan"), float("nan"))
    rng = _rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        pi = rng.choice(pos_idx, size=len(pos_idx), replace=True)
        ni = rng.choice(neg_idx, size=len(neg_idx), replace=True)
        idx = np.concatenate([pi, ni])
        stats[b] = auroc(y[idx], s[idx])
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))


def paired_auroc_diff_ci(y_true, scores_a, scores_b, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Paired stratified bootstrap of (AUROC_a - AUROC_b) on the SAME compounds.

    Returns (delta, lo, hi, p_two_sided). The CI excluding 0 ⇒ a real difference.
    The two models are resampled with identical indices each iteration, so the Δ
    accounts for their correlation (they score the same molecules)."""
    y = np.asarray(y_true)
    sa = np.asarray(scores_a, dtype=float)
    sb = np.asarray(scores_b, dtype=float)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    delta = auroc(y, sa) - auroc(y, sb)
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    rng = _rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        pi = rng.choice(pos_idx, size=len(pos_idx), replace=True)
        ni = rng.choice(neg_idx, size=len(neg_idx), replace=True)
        idx = np.concatenate([pi, ni])
        diffs[b] = auroc(y[idx], sa[idx]) - auroc(y[idx], sb[idx])
    lo, hi = np.nanpercentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    # two-sided bootstrap p-value for H0: delta == 0
    p = 2.0 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    return (float(delta), float(lo), float(hi), float(min(1.0, p)))


def spearman_ci(x, y, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Bootstrap CI for Spearman ρ (resample the paired observations)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    rng = _rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        stats[b] = spearman(x[idx], y[idx])
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))


def paired_spearman_diff_ci(x, y_a, y_b, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Paired bootstrap of (ρ(x,y_a) - ρ(x,y_b)) — same resampled pairs for both models.

    Use when two models predict the same `len(x)` pairs against shared truth `x`:
    a model 'wins' the correlation test only if this Δρ CI excludes 0.
    Returns (delta, lo, hi, p_two_sided)."""
    x = np.asarray(x, dtype=float)
    ya = np.asarray(y_a, dtype=float)
    yb = np.asarray(y_b, dtype=float)
    n = len(x)
    delta = spearman(x, ya) - spearman(x, yb)
    rng = _rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        diffs[b] = spearman(x[idx], ya[idx]) - spearman(x[idx], yb[idx])
    lo, hi = np.nanpercentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    p = 2.0 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    return (float(delta), float(lo), float(hi), float(min(1.0, p)))


def permutation_pvalue_spearman(x, y, n_perm: int = 10000, seed: int = 0) -> float:
    """Two-sided permutation p-value for Spearman ρ (shuffle y against x)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    obs = abs(spearman(x, y))
    rng = _rng(seed)
    count = 0
    for _ in range(n_perm):
        if abs(spearman(x, rng.permutation(y))) >= obs:
            count += 1
    return (count + 1) / (n_perm + 1)


def holm_correction(pvals: Sequence[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, preserving input order."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return adj.tolist()


# --------------------------------------------------------------------------- #
# Empirical bars (from MAMMAL's own evaluation — see CLAUDE.md / success_criteria) #
# --------------------------------------------------------------------------- #
def correlation_verdict(rho: float) -> str:
    return "STRONG PASS" if rho > 0.6 else "PASS" if rho > 0.4 else "FAIL"


def auroc_verdict(a: float, useful: float = 0.6) -> str:
    """Triage usefulness bar. >0.6 = useful signal; ~0.5 = chance."""
    if a != a:  # nan
        return "N/A"
    return "STRONG" if a >= 0.8 else "USEFUL" if a >= useful else "CHANCE"
