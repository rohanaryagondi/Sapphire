"""
visualization.py — pipeline v17, lean visual library.

One example per plot type, no metadata-driven plate-level views beyond a
simple per-condition bar. Designed to be called from the merged notebook
after both SCS and STA have run on a single FOV.

Plot list:
    plot_consensus_heatmap   — per-pair consensus tier matrix
    plot_top_scs_pair        — single SCS event-pairing example
    plot_top_sta_pair        — single STA mean +/- SD example with onset gate
    plot_ap_waveform_sample  — one neuron's AP waveform (mean +/- SD)
    plot_psp_waveform_sample — one EPSP and one IPSP waveform sample
    plot_p1_p2_sta           — same pair shown for P1 (strict) and P2 (relaxed)
    plot_neuron_tier_bar     — confident/putative/ambiguous/no_valid_outgoing_connections counts
    plot_condition_summary   — per-drug-condition validation rate (batch only)
    plot_spaghetti_overlay   — spatial connectivity arrows over a base image
                               (DLX or Quasr); centroids from savefast
                               (vendored from Hongkang's pipeline_v11.1)

Plate-level heatmaps (batch + metadata join required):
    plot_well_heatmap        — 96-well plate layout for any per-FOV/well metric
    build_validated_pct_df   — % validated connections per FOV
    build_exc_balance_df     — % EXC among validated connections per FOV
    build_active_neuron_df   — % non-silent neurons per FOV
"""

from __future__ import annotations

import glob
import math
import os
import re
from collections import defaultdict
from typing import Dict, Optional
from utils.quiver_style import QUIVER_NEURON_COLORS
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Rectangle

from .sta_utils import (
    FS,
    MIN_ONSET_MS,
    POST_AP_WIN,
    PRE_AP_BLANK,
    RESP_END,
    VAL_ONSET_MS,
    WIN_LEN,
    _classify_sta_windows,
    _noise_std,
)
from .scs_utils import (
    EPSP_WINDOW,
    IPSP_WINDOW,
    _psp_props_from_window,
)

# Colour palette — single source of truth for plots in this module.
# Edit these hex codes once to recolour every plot consistently.
_EXC = "#9C02FA"  # Quiver purple — excitatory
_INH = "#F51D3F"  # Quiver red    — inhibitory
_EXC_LIGHT = "#CAA1FF"  # Quiver lilac  — putative_exc, spaghetti edges
_INH_LIGHT = "#F9788B"  # Quiver salmon — putative_inh, spaghetti edges
_BOTH = "#1e8449"  # consensus tier color (kept distinct from _EXC)
_SCS_ONLY = "#f39c12"
_STA_ONLY = "#9b59b6"
_CONFLICT = "#7f8c8d"
_GREY = "#888888"

# Quiver Bioscience brand colours — used for condition/drug palettes
_QUIVER_PURPLE       = "#9C02FA"  # corrected to exact brand hex
_QUIVER_PURPLE_LIGHT = "#C96BFF"  # lighter tint for ramp start
_QUIVER_RED          = "#f51d3d"
_QUIVER_PINK         = "#cc3ea4"

import matplotlib.colors as _mcolors
_QUIVER_CMAP = _mcolors.LinearSegmentedColormap.from_list(
    'quiver', [_QUIVER_PURPLE_LIGHT, _QUIVER_PURPLE, _QUIVER_RED]
)


def _quiver_colors(n):
    """Return n colours spaced along the Quiver ramp (light purple → purple → red)."""
    if n == 1:
        return [_QUIVER_PURPLE]
    return [_mcolors.to_hex(_QUIVER_CMAP(i / (n - 1))) for i in range(n)]


def build_condition_colors(df_features, control_labels=None, condition_order=None):
    """Return a {condition: hex_color} dict for all conditions in df_features.

    Call once in the notebook and pass to plot_network_fingerprint,
    plot_pharmacology_comparison, etc. to keep drug colors consistent.
    Control conditions map to _GREY; drug conditions are spaced along the
    Quiver ramp in the order given by condition_order (or DataFrame order if None).

    condition_order : list, optional
        Explicit ordering of ALL conditions (including control), e.g.
        ['No Drug', 'GABAzine', 'DAP5', 'Ketamine', 'Forskolin', 'Cyclothiazide'].
        Only the drug conditions within this list affect color assignment order.
    """
    ctrl_set  = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    all_conds = df_features['condition'].unique().tolist()
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in all_conds and c not in ctrl_set]
        # append any drugs not mentioned in condition_order at the end
        drug_conds += [c for c in all_conds if c not in ctrl_set and c not in drug_conds]
    else:
        drug_conds = [c for c in all_conds if c not in ctrl_set]
    palette   = _quiver_colors(max(len(drug_conds), 1))
    colors    = {c: _GREY for c in all_conds if c in ctrl_set}
    colors.update({c: palette[i] for i, c in enumerate(drug_conds)})
    return colors


# ============================================================================
# Drug-condition helpers
# ============================================================================

_DRUG_CONTROL_LABELS = {
    'No Drug', 'NoDrug', 'no drug', 'no_drug',
    'DMSO', 'dmso', 'control', 'Control', '',
}


def _fov_drug_map(
    df: pd.DataFrame,
    drug_col: str = 'drug1',
    drug_map: Optional[dict] = None,
    fov_col: str = 'fov',
) -> dict:
    """
    Return {fov: drug_label} from an explicit dict or from a column in df.
    The explicit drug_map takes priority; falls back to df[drug_col] if present.
    Returns {} when neither source is available.
    """
    if drug_map:
        return dict(drug_map)
    if drug_col and drug_col in df.columns and fov_col in df.columns:
        return (
            df.groupby(fov_col)[drug_col]
            .first()
            .fillna('No Drug')
            .astype(str)
            .str.strip()
            .to_dict()
        )
    return {}


def _drug_subtitle(drug_map: dict, fovs=None) -> str:
    """
    Build a title subtitle string from a {fov: drug} mapping.
    Returns '' when all mapped FOVs are on a control/no-drug condition
    (so purely-control experiments get no extra clutter).
    Single drug  -> '\\n(Drug: X)'
    Multiple     -> '\\n(Conditions: X, Y, Z)'
    """
    if not drug_map:
        return ''
    lookup = fovs if fovs is not None else list(drug_map.keys())
    relevant = {
        drug_map[f]
        for f in lookup
        if f in drug_map and drug_map[f] not in _DRUG_CONTROL_LABELS
    }
    if not relevant:
        return ''
    if len(relevant) == 1:
        return f'\n(Drug: {next(iter(relevant))})'
    return f'\n(Conditions: {", ".join(sorted(relevant))})'


# ============================================================================
# Helper — evoked-AP overlay
# ============================================================================
def _overlay_evoked_ap_traces(
    ax,
    sta_res,
    pre,
    post,
    color: str = "#333333",
    individual_alpha: float = 0.18,
    individual_lw: float = 0.5,
    draw_mean: bool = True,
):
    """
    Overlay the evoked-AP windows for (pre, post) as faint background traces
    on `ax`, in addition to whatever the caller already plotted. Returns the
    count of evoked-AP windows actually drawn (0 if none).

    These are the windows that `_classify_sta_windows` puts into `ap_wins` —
    i.e. ones where the post-neuron fired in the response zone. They were
    excluded from the subthreshold STA mean. Showing them here lets the
    reader see both the subthreshold drive and the AP-evoking trials on the
    same time axis without confounding the mean.

    Recomputes via `_classify_sta_windows` from the trace + AP arrays in
    `sta_res`, so it works on both `run_sta_pipeline` and
    `run_sta_pipeline_interleaved` results.
    """
    if pre not in sta_res.get("traces_all", {}) or post not in sta_res.get(
        "traces_all", {}
    ):
        return 0
    post_trace = sta_res["traces_all"][post]
    pre_aps = sta_res.get("aps_for_sta", sta_res.get("aps_all", {})).get(pre, [])
    post_aps = sta_res.get("aps_all", {}).get(post, [])
    segs = sta_res["segs"]
    if len(pre_aps) == 0:
        return 0
    noise = _noise_std(post_trace, segs)

    _psp, ap_wins, _drop = _classify_sta_windows(
        post_trace, pre_aps, post_aps, segs, noise=noise
    )
    if not ap_wins:
        return 0

    arr = np.array(ap_wins)
    t_ms = (np.arange(arr.shape[1]) - PRE_AP_BLANK) / FS * 1000

    for w in arr:
        ax.plot(
            t_ms, w, color=color, lw=individual_lw, alpha=individual_alpha, zorder=1
        )
    if draw_mean:
        ax.plot(
            t_ms,
            arr.mean(0),
            color=color,
            lw=1.4,
            ls=":",
            alpha=0.7,
            zorder=2,
            label=f"evoked-AP mean (n={len(arr)})",
        )
    return len(arr)


# ============================================================================
# 1. Consensus heatmap
# ============================================================================
def plot_consensus_heatmap(
    merged_df: pd.DataFrame,
    all_traces,
    output_path: Optional[str] = None,
    title: str = "Consensus connectivity (v17)",
):
    """One cell per (pre, post). Colour encodes tier x type."""
    if merged_df.empty:
        print("No connections to plot.")
        return

    n = len(all_traces)
    idx = {t: i for i, t in enumerate(all_traces)}
    mat = np.zeros((n, n))

    # Encode: positive = EXC, negative = INH; magnitude = consensus tier weight
    weight = {
        "both": 3.0,
        "scs_only": 1.5,
        "sta_only": 1.5,
        "conflict": 1.0,
        "unvalidated": 0.0,
    }
    for _, r in merged_df.iterrows():
        if int(r["pre"]) not in idx or int(r["post"]) not in idx:
            continue
        w = weight.get(r["consensus_tier"], 0.0)
        if w == 0:
            continue
        sign = 1.0 if r["type"] == "EXC" else -1.0
        mat[idx[int(r["pre"])], idx[int(r["post"])]] = sign * w

    fig, ax = plt.subplots(figsize=(10, 9))
    vmax = max(abs(mat).max(), 1.0)
    # Orange (INH, negative) -> white (zero) -> green (EXC, positive).
    # Edit the hex codes here to recolour the heatmap.
    from matplotlib.colors import LinearSegmentedColormap

    inh_green_cmap = LinearSegmentedColormap.from_list(
        "orange_white_green", ["#e67e22", "#ffffff", "#27ae60"]
    )
    im = ax.imshow(
        mat,
        cmap=inh_green_cmap,
        aspect="auto",
        vmin=-vmax,
        vmax=vmax,
        interpolation="nearest",
    )
    ticks = list(range(0, n, max(1, n // 12)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(all_traces[i]) for i in ticks], rotation=90, fontsize=8)
    ax.set_yticks(ticks)
    ax.set_yticklabels([str(all_traces[i]) for i in ticks], fontsize=8)
    ax.set_xlabel("Post-synaptic neuron")
    ax.set_ylabel("Pre-synaptic neuron")
    ax.set_title(title, fontsize=11)
    cbar = plt.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label(
        "<- IPSP (orange)   tier weight (|3| both, |1.5| single-method)   "
        "EPSP (green) ->",
        fontsize=9,
    )
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 2. Top SCS event-pairing example
# ============================================================================
def plot_top_scs_pair(
    scs_res: dict, conn_type: str = "exc", output_path: Optional[str] = None
):
    """Single example: post-trace with pre-AP and PSP-event ticks overlaid."""
    scores = scs_res["exc_scores"] if conn_type == "exc" else scs_res["inh_scores"]
    if not scores:
        print("No SCS connections to plot.")
        return

    (pre, post), score = max(scores.items(), key=lambda kv: kv[1])
    if score < scs_res["score_thresh"]:
        print("No SCS connection above threshold.")
        return

    aps_pre = scs_res["aps_all"][pre]
    aps_post = scs_res["aps_all"][post]
    psp_d = (scs_res["epsps_all"] if conn_type == "exc" else scs_res["ipsps_all"]).get(
        post, np.array([], dtype=int)
    )
    trace = scs_res["traces_all"][post]
    fs = FS
    t = np.arange(len(trace)) / fs

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t, trace, color="#444", lw=0.7, alpha=0.85)
    color = _EXC if conn_type == "exc" else _INH
    for ap in aps_pre:
        ax.axvline(ap / fs, color=color, lw=0.8, alpha=0.4)
    for ev in psp_d:
        ax.scatter(
            ev / fs,
            trace[ev],
            color=color,
            s=40,
            zorder=5,
            edgecolor="white",
            linewidth=0.8,
        )
    ax.set_title(
        f"SCS top {conn_type.upper()}  T{pre} -> T{post}  " f"score={score:.2f}",
        color=color,
        fontsize=11,
    )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("dF/F (post)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 3. Top STA pair (single panel)
# ============================================================================
def plot_top_sta_pair(
    sta_res: dict,
    conn_type: str = "exc",
    output_path: Optional[str] = None,
    onset_label_ms: float = MIN_ONSET_MS,
    show_evoked_aps: bool = True,
):
    scores = sta_res["exc_scores"] if conn_type == "exc" else sta_res["inh_scores"]
    win_p1 = sta_res.get("win_counts_p1", {})
    cands = [
        (k, v)
        for k, v in scores.items()
        if v >= sta_res["score_thresh"] and win_p1.get(k, 0) >= 2
    ]
    if not cands:
        print("No qualifying STA connections.")
        return
    (pre, post), score = max(cands, key=lambda kv: kv[1])
    result = sta_res["all_results"].get((pre, post))
    if result is None:
        print("Result not found.")
        return

    # Unpack first 9 fields positionally (backward-compat with old tuple shape);
    # absorb the remaining StaResult fields with `*_`. We pull AP-rate info
    # by attribute access below — works on the v16 NamedTuple.
    (
        signed,
        p_val,
        direction,
        n_sig,
        n_ctrl,
        sta_mean,
        sta_sd,
        ctrl_mean,
        ctrl_sd,
        *_,
    ) = result
    if sta_mean is None:
        print(f"STA mean unavailable for T{pre} -> T{post} (no PSP-only windows).")
        return

    t_ms = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000
    fig, ax = plt.subplots(figsize=(8, 5))
    color = _EXC if direction == "exc" else _INH if direction == "inh" else _GREY

    # PSP-only count (post-AP free) — used for the STA legend label.
    n_psp = int(getattr(result, "n_psp", n_sig))
    n_ap_evoked = int(getattr(result, "n_ap_evoked", 0))

    # Optionally overlay the evoked-AP windows (faint individual traces +
    # dashed mean) BEFORE the subthreshold STA so the STA mean stays on top
    # visually.
    if show_evoked_aps:
        _overlay_evoked_ap_traces(
            ax, sta_res, pre, post, color="#444444", individual_alpha=0.18
        )

    post_trace = sta_res["traces_all"].get(post)
    pre_aps_plot = sta_res.get("aps_for_sta", sta_res.get("aps_all", {})).get(pre, [])
    post_aps_plot = sta_res.get("aps_all", {}).get(post, [])
    if post_trace is not None and len(pre_aps_plot) > 0:
        _noise = _noise_std(post_trace, sta_res["segs"])
        psp_wins, ap_wins, _ = _classify_sta_windows(
            post_trace, pre_aps_plot, post_aps_plot, sta_res["segs"], noise=_noise
        )
        all_wins = (psp_wins or []) + (ap_wins or [])
    else:
        all_wins = []
    if all_wins:
        combined = np.array(all_wins).mean(0)
        combined_sd = np.array(all_wins).std(0)
        ax.fill_between(
            t_ms,
            combined - combined_sd,
            combined + combined_sd,
            alpha=0.22,
            color=color,
            lw=0,
        )
        ax.plot(
            t_ms,
            combined,
            color=color,
            lw=2.2,
            label=f"Combined STA (n={len(all_wins)})",
        )
    elif sta_mean is not None:
        ax.fill_between(
            t_ms, sta_mean - sta_sd, sta_mean + sta_sd, alpha=0.22, color=color, lw=0
        )
        ax.plot(
            t_ms, sta_mean, color=color, lw=2.2, label=f"Subthreshold STA (n={n_psp})"
        )
    if ctrl_mean is not None:
        ax.fill_between(
            t_ms,
            ctrl_mean - ctrl_sd,
            ctrl_mean + ctrl_sd,
            alpha=0.13,
            color=_GREY,
            lw=0,
        )
        ax.plot(
            t_ms, ctrl_mean, color=_GREY, lw=1.8, ls="--", label=f"Control (n={n_ctrl})"
        )
    ax.axvline(0, color="black", lw=1.0, ls=":", label=f"Presynaptic AP")

    ax.set_title(
        f"STA top {conn_type.upper()}  T{pre} -> T{post}  "
        f"|log10 p|={abs(signed):.2f}  p={p_val:.3g}",
        color=color,
    )
    ax.set_xlabel("Time relative to pre-AP (ms)")
    ax.set_ylabel("dF/F (baseline-corrected)")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    # Evoked-AP annotation (sub-axis text, safe when fields are missing).
    n_total = n_psp + n_ap_evoked
    if n_total > 0 and hasattr(result, "ap_rate_sig"):
        rate_sig = result.ap_rate_sig
        rate_ctrl = result.ap_rate_ctrl
        ap_pval = result.ap_pval
        ap_dir = result.ap_direction
        ap_score = result.ap_score
        ap_color = _EXC if ap_dir == "exc" else _INH if ap_dir == "inh" else _GREY
        annotation = (
            f"evoked AP: {n_ap_evoked}/{n_total} "
            f"({rate_sig*100:.0f}%) "
            f"vs ctrl {rate_ctrl*100:.0f}%  "
            f"p={ap_pval:.3g}"
        )
        if ap_score >= sta_res["score_thresh"]:
            annotation += f"  (ap_score={ap_score:.2f}, {ap_dir.upper()})"
        ax.text(
            0.02,
            -0.18,
            annotation,
            transform=ax.transAxes,
            fontsize=9,
            color=ap_color,
            fontweight="bold" if ap_score >= sta_res["score_thresh"] else "normal",
        )

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 3b. All validated STA connections — grid of mean ± SD traces (batch-friendly)
# ============================================================================

def plot_all_sta_connections(
    R: dict,
    conn_type: str = "exc",
    output_path: Optional[str] = None,
    max_pages: int = 5,
) -> None:
    """
    Grid of mean ± SEM STA traces for every validated EXC or INH connection
    in one FOV.  Up to 30 pairs per page; capped at max_pages images per FOV.

    Parameters
    ----------
    R           : per-FOV result dict from run_one_fov / batch loop.
    conn_type   : 'exc' or 'inh'.
    output_path : base path for saved figure(s).  When there are multiple
                  pages the page number is appended before the extension,
                  e.g. 'sta_all_exc_p1.png', 'sta_all_exc_p2.png'.
                  Pass None to skip saving.
    """
    from scipy.signal import savgol_filter

    sta_res = R.get("sta1")
    merged  = R.get("merged")
    fov     = R.get("fov", "unknown")

    if sta_res is None or merged is None or merged.empty:
        print(f"[{fov}] plot_all_sta_connections: missing sta1 or merged — skipping.")
        return

    VALIDATED = {"both", "scs_only", "sta_only"}
    val = merged[
        merged["consensus_tier"].isin(VALIDATED)
        & (merged["type"].str.upper() == conn_type.upper())
    ]

    all_results = sta_res.get("all_results", {})
    pairs = [
        (int(r["pre"]), int(r["post"]))
        for _, r in val.iterrows()
        if (int(r["pre"]), int(r["post"])) in all_results
    ]

    if not pairs:
        print(f"[{fov}] No validated {conn_type.upper()} STA connections — skipping.")
        return

    n     = len(pairs)
    color = _EXC if conn_type.lower() == "exc" else _INH
    t_ms  = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000
    segs  = sta_res["segs"]
    win_sg = max(5, int(0.02 * FS))
    win_sg = win_sg if win_sg % 2 == 1 else win_sg + 1

    MAX_PER_FIG = 30
    n_pages = min(max_pages, max(1, math.ceil(n / MAX_PER_FIG)))

    for page in range(n_pages):
        subset = pairs[page * MAX_PER_FIG : (page + 1) * MAX_PER_FIG]
        n_sub  = len(subset)
        ncols  = min(4, n_sub)
        nrows  = math.ceil(n_sub / ncols)

        fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
        axes = np.array(axes).reshape(-1)

        for i, (pre, post) in enumerate(subset):
            ax = axes[i]

            post_trace = sta_res["traces_all"][post]
            pre_aps    = sta_res.get("aps_for_sta", sta_res.get("aps_all", {})).get(pre, [])
            post_aps   = sta_res.get("aps_all", {}).get(post, [])
            noise      = _noise_std(post_trace, segs)

            psp_wins, ap_wins, _ = _classify_sta_windows(
                post_trace, pre_aps, post_aps, segs, noise=noise
            )
            all_wins = np.array(psp_wins + ap_wins)

            if len(all_wins) < 2:
                ax.text(
                    0.5, 0.5, "no windows",
                    ha="center", va="center", transform=ax.transAxes,
                )
            else:
                mean_s = savgol_filter(all_wins.mean(axis=0), win_sg, 2)
                sem    = all_wins.std(axis=0) / np.sqrt(len(all_wins))
                ax.fill_between(t_ms, mean_s - sem, mean_s + sem,
                                alpha=0.22, color=color, lw=0)
                ax.plot(t_ms, mean_s, color=color, lw=1.5)
                ax.axvline(0, color="#666666", lw=0.8, ls="--")

            result = all_results[(pre, post)]
            row    = val[(val["pre"] == pre) & (val["post"] == post)].iloc[0]
            score  = float(row.get("sta_score_p1", 0) or 0)
            ax.set_title(
                f"T{pre}→T{post}  {score:.2f}"
                f"  (psp={result.n_psp} ap={result.n_ap_evoked})",
                fontsize=7,
            )
            ax.tick_params(labelsize=6)
            ax.spines[["top", "right"]].set_visible(False)

        for j in range(n_sub, nrows * ncols):
            axes[j].set_visible(False)

        page_label = f" — page {page + 1}/{n_pages}" if n_pages > 1 else ""
        fig.suptitle(
            f"{fov} — {conn_type.upper()} validated STA ({n}){page_label}",
            fontsize=11,
        )
        plt.tight_layout()

        if output_path:
            stem, ext = os.path.splitext(output_path)
            save_path = f"{stem}_p{page + 1}{ext}" if n_pages > 1 else output_path
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()


def compute_mean_psp_waveforms(R: dict) -> dict:
    """
    Pool all PSP-only windows across validated EXC and INH connections for one
    FOV and return mean ± SD waveforms.

    Returns a dict with keys 'exc' and 'inh', each containing:
        'mean'  : np.ndarray of shape (WIN_LEN,)
        'sd'    : np.ndarray of shape (WIN_LEN,)
        'n_wins': int  (total windows pooled)
        't_ms'  : np.ndarray  (time axis in ms)
    Returns an empty dict if sta1 or merged are missing.
    """
    from scipy.signal import savgol_filter

    sta_res = R.get("sta1")
    merged  = R.get("merged")
    fov     = R.get("fov", "unknown")

    if sta_res is None or merged is None or merged.empty:
        return {}

    VALIDATED = {"both", "scs_only", "sta_only"}
    all_results = sta_res.get("all_results", {})
    segs = sta_res["segs"]
    t_ms = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000
    win_sg = max(5, int(0.02 * FS))
    win_sg = win_sg if win_sg % 2 == 1 else win_sg + 1

    output = {}
    for conn_type in ("exc", "inh"):
        val = merged[
            merged["consensus_tier"].isin(VALIDATED)
            & (merged["type"].str.upper() == conn_type.upper())
        ]
        pairs = [
            (int(r["pre"]), int(r["post"]))
            for _, r in val.iterrows()
            if (int(r["pre"]), int(r["post"])) in all_results
        ]

        all_psp_wins = []
        for pre, post in pairs:
            post_trace = sta_res["traces_all"][post]
            pre_aps    = sta_res.get("aps_for_sta", sta_res.get("aps_all", {})).get(pre, [])
            post_aps   = sta_res.get("aps_all", {}).get(post, [])
            noise      = _noise_std(post_trace, segs)
            psp_wins, _, _ = _classify_sta_windows(
                post_trace, pre_aps, post_aps, segs, noise=noise
            )
            all_psp_wins.extend(psp_wins)

        if len(all_psp_wins) < 2:
            output[conn_type] = {'mean': None, 'sem': None, 'n_wins': len(all_psp_wins), 't_ms': t_ms}
            continue

        arr      = np.array(all_psp_wins)
        mean_raw = arr.mean(axis=0)
        mean     = mean_raw.copy()
        mean[PRE_AP_BLANK:] = savgol_filter(mean_raw[PRE_AP_BLANK:], win_sg, 2)
        sem      = arr.std(axis=0) / np.sqrt(len(all_psp_wins))

        # Compute PSP properties from individual windows (all PSPs, regardless of connection)
        polarity   = 1 if conn_type == 'exc' else -1
        win_props  = [_psp_props_from_window(w, polarity, FS) for w in arr]
        win_props  = [p for p in win_props if p is not None]
        _prop_keys = ('amplitude', 'auc', 'peak_time_ms', 'onset_delay_ms',
                      'rise_time_ms', 'half_width_ms', 'snr', 'decay_time_ms', 'duration_ms')
        props = (pd.DataFrame(win_props).mean().to_dict() if win_props
                 else {k: np.nan for k in _prop_keys})

        output[conn_type] = {'mean': mean, 'sem': sem, 'n_wins': len(all_psp_wins),
                             't_ms': t_ms, 'props': props}

    return output


def compute_all_psp_waveforms(R: dict) -> dict:
    """
    Compute mean PSP waveforms from ALL detected PSP events across scs1+scs2,
    regardless of connection validation. Returns the same structure as
    compute_mean_psp_waveforms — keys 'exc' and 'inh', each with
    'mean', 'sem', 'n_wins', 't_ms', 'props'.
    """
    from scipy.signal import savgol_filter

    t_ms   = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000
    win_sg = max(5, int(0.02 * FS))
    win_sg = win_sg if win_sg % 2 == 1 else win_sg + 1

    _prop_keys = ('amplitude', 'auc', 'peak_time_ms', 'onset_delay_ms',
                  'rise_time_ms', 'half_width_ms', 'snr', 'decay_time_ms', 'duration_ms')

    output = {}
    for conn_type in ('exc', 'inh'):
        psp_key  = 'epsps_all' if conn_type == 'exc' else 'ipsps_all'
        polarity = 1           if conn_type == 'exc' else -1
        win      = EPSP_WINDOW if conn_type == 'exc' else IPSP_WINDOW
        all_wins = []

        for src_key in ('scs1', 'scs2'):
            src = R.get(src_key)
            if src is None or psp_key not in src:
                continue
            traces   = src.get('traces_all', {})
            aps_all  = src.get('aps_all', {})
            evts_all = src[psp_key]
            all_aps  = (np.sort(np.concatenate(list(aps_all.values())))
                        if any(len(v) for v in aps_all.values())
                        else np.array([], dtype=int))

            for post, evts in evts_all.items():
                if post not in traces or len(evts) == 0:
                    continue
                trace    = traces[post]
                own_aps  = aps_all.get(post, np.array([], dtype=int))
                other_aps = np.setdiff1d(all_aps, own_aps)
                n = len(trace)

                for evt in evts:
                    cands = other_aps[(other_aps < evt) & (other_aps >= evt - win)]
                    if len(cands) == 0:
                        continue
                    ap = int(cands[-1])
                    w_start = ap - PRE_AP_BLANK
                    w_end   = ap + POST_AP_WIN
                    if w_start < 0 or w_end > n:
                        continue
                    all_wins.append(trace[w_start:w_end].copy())

        if len(all_wins) < 2:
            output[conn_type] = {'mean': None, 'sem': None, 'n_wins': len(all_wins),
                                 't_ms': t_ms,
                                 'props': {k: np.nan for k in _prop_keys}}
            continue

        arr      = np.array(all_wins)
        mean_raw = arr.mean(axis=0)
        mean     = mean_raw.copy()
        mean[PRE_AP_BLANK:] = savgol_filter(mean_raw[PRE_AP_BLANK:], win_sg, 2)
        sem      = arr.std(axis=0) / np.sqrt(len(all_wins))

        win_props = [_psp_props_from_window(w, polarity, FS) for w in arr]
        win_props = [p for p in win_props if p is not None]
        props = (pd.DataFrame(win_props).mean().to_dict() if win_props
                 else {k: np.nan for k in _prop_keys})

        output[conn_type] = {'mean': mean, 'sem': sem, 'n_wins': len(all_wins),
                             't_ms': t_ms, 'props': props}
    return output


def plot_mean_psp_waveforms(R: dict, output_path: Optional[str] = None) -> None:
    """
    Two-panel figure (EPSP left, IPSP right) showing the mean ± SD PSP waveform
    pooled across all validated connections for one FOV.
    """
    waveforms = compute_mean_psp_waveforms(R)
    if not waveforms:
        print(f"[{R.get('fov', '?')}] plot_mean_psp_waveforms: no data — skipping.")
        return

    fov = R.get("fov", "unknown")
    panels = [("exc", "EPSP", _EXC), ("inh", "IPSP", _INH)]

    fig, axes = plt.subplots(1, 2, figsize=(7, 3))
    for ax, (conn_type, label, color) in zip(axes, panels):
        w = waveforms.get(conn_type, {})
        mean, sem, n_wins, t_ms = w.get('mean'), w.get('sem'), w.get('n_wins', 0), w.get('t_ms')

        if mean is None or t_ms is None:
            ax.text(0.5, 0.5, f'no validated\n{label}s',
                    ha='center', va='center', transform=ax.transAxes, fontsize=9)
        else:
            ax.fill_between(t_ms, mean - sem, mean + sem, alpha=0.22, color=color, lw=0)
            ax.plot(t_ms, mean, color=color, lw=1.8)
            ax.axvline(0, color='#666666', lw=0.8, ls='--')
            ax.axhline(0, color='#cccccc', lw=0.6)

        ax.set_title(f'{label}  (n={n_wins} windows)', fontsize=9)
        ax.set_xlabel('Time (ms)', fontsize=8)
        ax.set_ylabel('ΔF/F', fontsize=8)
        ax.tick_params(labelsize=7)
        ax.spines[['top', 'right']].set_visible(False)

    fig.suptitle(f'{fov} — mean PSP waveforms (validated connections)', fontsize=10)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


def _nice_scale(val):
    """Round val up to a nearest 1/2/5 × 10^n for scale bars."""
    from math import log10, floor
    if val <= 0:
        return 0.001
    exp = floor(log10(val))
    frac = val / 10 ** exp
    nice = 1 if frac <= 1 else 2 if frac <= 2 else 5 if frac <= 5 else 10
    return nice * 10 ** exp


def _draw_scalebar(ax, t_ms, ymin, ymax, scale_val, time_ms=100):
    """L-shaped scale bar at the bottom-right edge of ax, drawn outside the box."""
    x_end   = t_ms[-1]
    x_start = x_end - time_ms
    y_bot   = ymin + (ymax - ymin) * 0.05
    y_top   = y_bot + abs(scale_val)
    x_pad   = (t_ms[-1] - t_ms[0]) * 0.04

    kw = dict(color='black', lw=1.5, clip_on=False, transform=ax.transData)
    ax.plot([x_start, x_end], [y_bot,  y_bot ], **kw)   # horizontal
    ax.plot([x_end,   x_end ], [y_bot,  y_top ], **kw)   # vertical

    ax.text(x_end + x_pad, (y_bot + y_top) / 2,
            f'{abs(scale_val):.3f}\ndF/F',
            fontsize=7, va='center', ha='left', clip_on=False)
    ax.text((x_start + x_end) / 2, y_bot - (ymax - ymin) * 0.08,
            f'{time_ms} ms',
            fontsize=7, va='top', ha='center', clip_on=False)


# Called in the plate comparison notebook.
def plot_condition_psp_waveforms(condition_fov_map, output_path=None):
    """
    Grid of mean PSP waveforms: rows = EPSP (top) / IPSP (bottom),
    columns = one condition each. One representative FOV per condition.

    Parameters
    ----------
    condition_fov_map : dict or list of (str, dict)
        {condition_name: R} or [(condition_name, R), ...].
        R is a per-FOV result dict (must contain 'sta1' and 'merged').
    """
    items      = list(condition_fov_map.items() if isinstance(condition_fov_map, dict)
                      else condition_fov_map)
    conditions = [c for c, _ in items]
    n_conds    = len(conditions)

    psp_rows = [
        ('exc', 'Mean EPSP', QUIVER_NEURON_COLORS['Excitatory']),
        ('inh', 'Mean IPSP', QUIVER_NEURON_COLORS['Inhibitory']),
    ]

    # Compute waveforms for every condition
    waveforms = {cond: compute_mean_psp_waveforms(R) for cond, R in items}

    # Shared y-range per row (across all conditions)
    row_ylim = {}
    for psp_key, _, _ in psp_rows:
        vals = []
        for cond in conditions:
            w = waveforms[cond].get(psp_key, {})
            if w.get('mean') is not None:
                vals.append(w['mean'] - w['sem'])
                vals.append(w['mean'] + w['sem'])
        if vals:
            arr  = np.concatenate(vals)
            span = arr.max() - arr.min()
            row_ylim[psp_key] = (arr.min() - span * 0.15, arr.max() + span * 0.15)
        else:
            row_ylim[psp_key] = (-0.01, 0.01)

    fig, axes = plt.subplots(2, n_conds,
                             figsize=(max(4, n_conds * 3.5) + 1.5, 4),
                             sharex=True)
    if n_conds == 1:
        axes = axes.reshape(2, 1)

    fig.subplots_adjust(left=0.12, right=0.82, top=0.88, bottom=0.05,
                        hspace=0.08, wspace=0.12)

    for row_i, (psp_key, row_label, color) in enumerate(psp_rows):
        ymin, ymax = row_ylim[psp_key]
        scale_val  = _nice_scale((ymax - ymin) * 0.3)

        for col_i, cond in enumerate(conditions):
            ax   = axes[row_i, col_i]
            w    = waveforms[cond].get(psp_key, {})
            t_ms = w.get('t_ms')
            mean = w.get('mean')
            sem  = w.get('sem')

            ax.axhline(0, color='#cccccc', lw=0.6, zorder=0)

            if mean is not None and t_ms is not None:
                mask = t_ms >= 0
                t_plot, mean_plot, sem_plot = t_ms[mask], mean[mask], sem[mask]
                ax.fill_between(t_plot, mean_plot - sem_plot, mean_plot + sem_plot,
                                alpha=0.2, color=color, lw=0)
                ax.plot(t_plot, mean_plot, color=color, lw=1.8)
                ax.axvline(0, color='#888888', lw=0.8, ls='--', zorder=1)
            else:
                ax.text(0.5, 0.5, 'no data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=8, color='#999999')

            ax.set_ylim(ymin, ymax)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_xticks([])
            ax.set_yticks([])

            # Condition name as column header (top row only)
            if row_i == 0:
                ax.set_title(cond, fontsize=12, fontweight='bold', pad=8)

            # Scale bar on last column only
            if col_i == n_conds - 1 and mean is not None and t_ms is not None:
                _draw_scalebar(ax, t_ms, ymin, ymax, scale_val)

        # Row label flush-left
        axes[row_i, 0].text(-0.18, 0.5, row_label,
                            transform=axes[row_i, 0].transAxes,
                            fontsize=11, fontweight='bold', color=color,
                            va='center', ha='right')

    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_condition_psp_waveforms_all(condition_fov_map, output_path=None):
    """
    Same grid layout as plot_condition_psp_waveforms but shows mean waveforms
    from ALL detected PSP events (scs1+scs2), regardless of connection validation.
    """
    items      = list(condition_fov_map.items() if isinstance(condition_fov_map, dict)
                      else condition_fov_map)
    conditions = [c for c, _ in items]
    n_conds    = len(conditions)

    psp_rows = [
        ('exc', 'Mean EPSP\n(all)', QUIVER_NEURON_COLORS['Excitatory']),
        ('inh', 'Mean IPSP\n(all)', QUIVER_NEURON_COLORS['Inhibitory']),
    ]

    waveforms = {cond: compute_all_psp_waveforms(R) for cond, R in items}

    row_ylim = {}
    for psp_key, _, _ in psp_rows:
        vals = []
        for cond in conditions:
            w = waveforms[cond].get(psp_key, {})
            if w.get('mean') is not None:
                vals.append(w['mean'][PRE_AP_BLANK:] - w['sem'][PRE_AP_BLANK:])
                vals.append(w['mean'][PRE_AP_BLANK:] + w['sem'][PRE_AP_BLANK:])
        if vals:
            arr  = np.concatenate(vals)
            span = arr.max() - arr.min()
            row_ylim[psp_key] = (arr.min() - span * 0.15, arr.max() + span * 0.15)
        else:
            row_ylim[psp_key] = (-0.01, 0.01)

    fig, axes = plt.subplots(2, n_conds,
                             figsize=(max(4, n_conds * 3.5) + 1.5, 4),
                             sharex=True)
    if n_conds == 1:
        axes = axes.reshape(2, 1)

    fig.subplots_adjust(left=0.12, right=0.82, top=0.88, bottom=0.05,
                        hspace=0.08, wspace=0.12)

    for row_i, (psp_key, row_label, color) in enumerate(psp_rows):
        ymin, ymax = row_ylim[psp_key]
        scale_val  = _nice_scale((ymax - ymin) * 0.3)

        for col_i, cond in enumerate(conditions):
            ax   = axes[row_i, col_i]
            w    = waveforms[cond].get(psp_key, {})
            t_ms = w.get('t_ms')
            mean = w.get('mean')
            sem  = w.get('sem')

            ax.axhline(0, color='#cccccc', lw=0.6, zorder=0)

            if mean is not None and t_ms is not None:
                mask = t_ms >= 0
                t_p, m_p, s_p = t_ms[mask], mean[mask], sem[mask]
                ax.fill_between(t_p, m_p - s_p, m_p + s_p, alpha=0.2, color=color, lw=0)
                ax.plot(t_p, m_p, color=color, lw=1.8)
                ax.axvline(0, color='#888888', lw=0.8, ls='--', zorder=1)
                n_wins = w.get('n_wins', 0)
                ax.text(0.97, 0.95, f'n={n_wins}', transform=ax.transAxes,
                        fontsize=7, ha='right', va='top', color='#666666')
            else:
                ax.text(0.5, 0.5, 'no data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=8, color='#999999')

            ax.set_ylim(ymin, ymax)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_xticks([])
            ax.set_yticks([])

            if row_i == 0:
                ax.set_title(cond, fontsize=12, fontweight='bold', pad=8)

            if col_i == n_conds - 1 and mean is not None and t_ms is not None:
                _draw_scalebar(ax, t_ms[t_ms >= 0], ymin, ymax, scale_val)

        axes[row_i, 0].text(-0.18, 0.5, row_label,
                            transform=axes[row_i, 0].transAxes,
                            fontsize=11, fontweight='bold', color=color,
                            va='center', ha='right')

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# ============================================================================
# 4. AP waveform sample (one neuron)
# ============================================================================
def plot_ap_waveform_sample(
    res: dict, win_pre: int = 20, win_post: int = 40, output_path: Optional[str] = None
):
    """Mean +/- SD AP waveform for the most-active neuron in `res`."""
    aps_all = res["aps_all"]
    traces_all = res["traces_all"]

    # pick the neuron with the most APs
    best_t, best_n = None, 0
    for t, aps in aps_all.items():
        if len(aps) > best_n:
            best_t, best_n = t, len(aps)
    if best_t is None or best_n == 0:
        print("No APs to plot.")
        return

    tr = traces_all[best_t]
    ws = []
    for ap in aps_all[best_t]:
        ws_lo, ws_hi = ap - win_pre, ap + win_post
        if ws_lo < 0 or ws_hi >= len(tr):
            continue
        seg = tr[ws_lo:ws_hi]
        if not np.any(np.isnan(seg)):
            ws.append(seg)
    if not ws:
        print("No clean AP windows.")
        return
    arr = np.array(ws)
    t = (np.arange(arr.shape[1]) - win_pre) / FS * 1000

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.fill_between(
        t, arr.mean(0) - arr.std(0), arr.mean(0) + arr.std(0), alpha=0.25, color="#444"
    )
    ax.plot(
        t, arr.mean(0), color="#444", lw=2.0, label=f"T{best_t} mean of {len(arr)} APs"
    )
    ax.axvline(0, color="black", lw=0.8, ls=":")
    ax.set_title(f"AP waveform — T{best_t}")
    ax.set_xlabel("Time relative to AP peak (ms)")
    ax.set_ylabel("dF/F")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 5. PSP waveform sample (one EPSP + one IPSP from SCS)
# ============================================================================
def plot_psp_waveform_sample(
    scs_res: dict,
    win_pre: int = 25,
    win_post: int = 100,
    output_path: Optional[str] = None,
):
    """
    EPSP / IPSP waveform sample, ALIGNED TO THE PRE-AP that triggered each PSP.

    Earlier versions of this plot averaged windows centered on the PSP event
    itself, which collapsed onto the peak and discarded latency information.
    v16 anchors each trace at t=0 = pre-AP (using the (pre, post, ap_idx,
    event_idx) tuples from get_all_pairs) so the temporal onset distribution
    is preserved.

    Picks the post-neuron with the most paired events and plots all of its
    paired pre-AP -> post-trace windows. Individual PSP detection times are
    marked as small dots on each trace; the mean +/- SD is overlaid.
    """
    from .scs_utils import get_all_pairs, PSP_WINDOW

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    aps_all = scs_res["aps_all"]
    traces_all = scs_res["traces_all"]
    all_traces = scs_res["all_traces"]
    segs = scs_res["segs"]
    psp_window = scs_res.get("psp_window", PSP_WINDOW)

    for ax, ev_kind, color, label in [
        (axes[0], "epsps_all", _EXC, "EPSP"),
        (axes[1], "ipsps_all", _INH, "IPSP"),
    ]:
        events_dict = scs_res.get(ev_kind, {})
        if not events_dict or all(len(v) == 0 for v in events_dict.values()):
            ax.text(
                0.5,
                0.5,
                f"No {label} events",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            continue

        # Build (pre, post, ap_idx, event_idx) pairs, then pick the post-neuron
        # with the most paired events.
        pairs = get_all_pairs(
            aps_all, events_dict, all_traces, segs, psp_window=psp_window
        )
        if not pairs:
            ax.text(
                0.5,
                0.5,
                f"No paired {label} events",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            continue

        post_counts = {}
        for _, post_id, _, _ in pairs:
            post_counts[post_id] = post_counts.get(post_id, 0) + 1
        best_post = max(post_counts, key=post_counts.get)
        # among all pre-neurons driving best_post, pick the one with most pairings
        pre_counts = {}
        for pre_id, post_id, _, _ in pairs:
            if post_id == best_post:
                pre_counts[pre_id] = pre_counts.get(pre_id, 0) + 1
        best_pre = max(pre_counts, key=pre_counts.get)
        relevant = [p for p in pairs if p[1] == best_post and p[0] == best_pre]

        tr = traces_all[best_post]
        wins = []
        ev_offs = []  # PSP detection sample offset relative to pre-AP
        for pre_id, _, ap_idx, ev_idx in relevant:
            lo, hi = ap_idx - win_pre, ap_idx + win_post
            if lo < 0 or hi >= len(tr):
                continue
            seg = tr[lo:hi]
            if np.any(np.isnan(seg)):
                continue
            wins.append(seg)
            ev_offs.append(ev_idx - ap_idx)
        if not wins:
            ax.text(
                0.5,
                0.5,
                f"No clean {label} windows",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            continue

        arr = np.array(wins)
        ev_t = np.array(ev_offs) / FS * 1000.0
        t_ms = (np.arange(arr.shape[1]) - win_pre) / FS * 1000.0

        # Faint individual traces give a sense of trial-to-trial jitter.
        for w in arr:
            ax.plot(t_ms, w, color=color, lw=0.5, alpha=0.18)

        # Mean +/- SD on top.
        ax.fill_between(
            t_ms,
            arr.mean(0) - arr.std(0),
            arr.mean(0) + arr.std(0),
            alpha=0.28,
            color=color,
            lw=0,
        )
        ax.plot(
            t_ms,
            arr.mean(0),
            color=color,
            lw=2.0,
            label=f"T{best_post}  mean of {len(arr)}",
        )

        # Mark each detected PSP time on its own trace (small dot).
        for w, ev_off_ms in zip(arr, ev_t):
            sample_idx = int(round(ev_off_ms / 1000.0 * FS) + win_pre)
            if 0 <= sample_idx < len(w):
                ax.scatter(
                    ev_off_ms,
                    w[sample_idx],
                    color=color,
                    s=14,
                    zorder=4,
                    edgecolor="white",
                    linewidth=0.5,
                    alpha=0.7,
                )

        # Median PSP latency annotation.
        med_lat = float(np.median(ev_t))
        ax.axvline(0, color="black", lw=0.8, ls=":")
        ax.axvline(
            med_lat,
            color=color,
            lw=1.0,
            ls="--",
            alpha=0.6,
            label=f"median PSP latency = {med_lat:.0f} ms",
        )
        ax.set_title(f"{label} mean (SCS) — aligned to pre-AP at t=0")
        ax.set_xlabel("Time relative to pre-AP (ms)")
        ax.set_ylabel("dF/F (post)")
        ax.legend(fontsize=8, loc="best")
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 6. P1/P2 STA comparison
# ============================================================================
def plot_p1_p2_sta(
    sta_res1: dict,
    sta_res2: dict,
    pre: int,
    post: int,
    output_path: Optional[str] = None,
    show_evoked_aps: bool = True,
):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, res, label, onset in [
        (axes[0], sta_res1, "P1 (strict)", MIN_ONSET_MS),
        (axes[1], sta_res2, "P2 (relaxed)", VAL_ONSET_MS),
    ]:
        result = res["all_results"].get((pre, post))
        if result is None:
            ax.text(
                0.5, 0.5, "Not scored", ha="center", va="center", transform=ax.transAxes
            )
            continue
        # First 9 fields are positional (backward-compat); rest absorbed.
        (
            signed,
            p_val,
            direction,
            n_sig,
            n_ctrl,
            sta_mean,
            sta_sd,
            ctrl_mean,
            ctrl_sd,
            *_,
        ) = result
        n_psp = int(getattr(result, "n_psp", n_sig))
        n_ap_evoked = int(getattr(result, "n_ap_evoked", 0))
        if sta_mean is None:
            # Still annotate AP rate when subthreshold STA is empty but
            # evoked APs were observed.
            msg = "Insufficient windows"
            if n_ap_evoked > 0:
                msg += f"\n(but {n_ap_evoked} evoked AP windows)"
            ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
            continue
        t_ms = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000
        c = _EXC if direction == "exc" else _INH if direction == "inh" else _GREY

        # Overlay evoked-AP windows BEFORE the subthreshold STA so the STA
        # mean stays prominent visually.
        if show_evoked_aps:
            _overlay_evoked_ap_traces(
                ax, res, pre, post, color="#444444", individual_alpha=0.18
            )

        ax.fill_between(
            t_ms, sta_mean - sta_sd, sta_mean + sta_sd, alpha=0.22, color=c, lw=0
        )
        ax.plot(t_ms, sta_mean, color=c, lw=2.0, label=f"Subthreshold STA (n={n_psp})")
        if ctrl_mean is not None:
            ax.fill_between(
                t_ms,
                ctrl_mean - ctrl_sd,
                ctrl_mean + ctrl_sd,
                alpha=0.13,
                color=_GREY,
                lw=0,
            )
            ax.plot(
                t_ms,
                ctrl_mean,
                color=_GREY,
                lw=1.6,
                ls="--",
                label=f"Ctrl (n={n_ctrl})",
            )
        ax.axvline(0, color="black", lw=0.8, ls=":")
        ax.axvline(
            onset, color=_INH, lw=1.0, ls="--", label=f"{onset:.0f} ms gate"
        )

        # Title carries the combined |log10 p| score; subtitle carries the
        # evoked-AP fraction so reviewers can see at a glance how much of
        # the evidence comes from each pool.
        ap_frac = (n_ap_evoked / max(1, n_psp + n_ap_evoked)) * 100
        ax.set_title(
            f"{label}  |log10 p|={abs(signed):.2f}\n"
            f"evoked AP {n_ap_evoked}/{n_psp+n_ap_evoked}"
            f" ({ap_frac:.0f}%)",
            color=c,
            fontsize=10,
        )
        ax.set_xlabel("Time relative to pre-AP (ms)")
        ax.set_ylabel("dF/F (baseline-corrected)")
        ax.legend(fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"STA T{pre} -> T{post}  P1 vs P2", y=1.02)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 7. Per-neuron tier bar
# ============================================================================
def plot_neuron_tier_bar(
    neuron_tier_df: pd.DataFrame, output_path: Optional[str] = None
):
    """Bar chart of tier counts: confident / putative / ambiguous / no_valid_outgoing_connections."""
    counts = neuron_tier_df["consensus_type"].value_counts()
    order = [
        "confident_exc",
        "confident_inh",
        "putative_exc",
        "putative_inh",
        "ambiguous",
        "no_valid_outgoing_connections",
    ]
    counts = counts.reindex(order, fill_value=0)
    # Order matches `order` above:
    #   confident_exc, confident_inh, putative_exc, putative_inh, ambiguous, no_valid_outgoing_connections
    colors = [_EXC, _INH, _EXC_LIGHT, _INH_LIGHT, _CONFLICT, "#bdc3c7"]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(len(counts)), counts.values, color=colors, edgecolor="white")
    for i, v in enumerate(counts.values):
        ax.text(i, v + 0.2, str(int(v)), ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(counts.index, rotation=20, fontsize=10)
    ax.set_ylabel("Number of neurons")
    ax.set_title("Per-neuron consensus classification (v17)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 8. Pharmacology comparison (batch-only)
# ============================================================================
def plot_pharmacology_comparison(
    all_fov_results: list,
    fov_condition_map: dict,
    conn_type: str = 'inh',
    drug_keyword: str = 'gabazine',
    output_path: Optional[str] = None,
    condition_colors: Optional[dict] = None,
) -> Optional[pd.DataFrame]:
    """Bar + scatter comparison of No-Drug vs drug conditions for EXC or INH metrics.

    Parameters
    ----------
    all_fov_results : list
        List of per-FOV result dicts (each with keys 'fov', 'scs1', 'merged').
    fov_condition_map : dict
        Mapping of fov -> condition string (e.g. built from df_all_conn_md).
    conn_type : {'inh', 'exc'}
        Which connection type to evaluate.
    drug_keyword : str
        Case-insensitive substring used to identify drug conditions
        (e.g. 'gabazine', 'apv', 'cnqx').
    output_path : str, optional
        If provided, save the figure here.

    Returns
    -------
    pd.DataFrame or None
        The per-FOV metrics DataFrame, or None if skipped.
    """
    import pandas as _pd

    ct = conn_type.lower()
    if ct not in ('inh', 'exc'):
        raise ValueError(f"conn_type must be 'inh' or 'exc', got {conn_type!r}")

    VAL_TIERS = {'both', 'scs_only', 'sta_only'}

    # ── Identify drug conditions on this plate ─────────────────────────────
    all_conds = {str(c or '').strip() for c in fov_condition_map.values()}
    drug_conds = sorted(c for c in all_conds if drug_keyword.lower() in c.lower())
    if not drug_conds:
        print(f"Skipping {ct.upper()} comparison — no '{drug_keyword}' conditions found.")
        return None

    # Normalise control label
    CONDITIONS = ['No Drug'] + drug_conds
    if condition_colors is not None:
        COLORS = {'No Drug': _GREY}
        COLORS.update({c: condition_colors.get(c, _QUIVER_PURPLE) for c in drug_conds})
    else:
        drug_colors = _quiver_colors(len(drug_conds))
        COLORS = {'No Drug': _GREY}
        COLORS.update({c: drug_colors[i] for i, c in enumerate(drug_conds)})

    # ── Metric definitions ─────────────────────────────────────────────────
    if ct == 'inh':
        psp_key = 'ipsps_all'
        type_str = 'INH'
        metrics = [
            ('psp_count',      f'IPSP count (total per FOV)'),
            ('pct_validated',  f'INH validated (%)'),
            ('mean_score',     f'INH confidence score'),
        ]
    else:
        psp_key = 'epsps_all'
        type_str = 'EXC'
        metrics = [
            ('psp_count',      f'EPSP count (total per FOV)'),
            ('pct_validated',  f'EXC validated (%)'),
            ('mean_score',     f'EXC confidence score'),
        ]

    score_cols_p1 = ('scs_score_p1', 'sta_score_p1')

    # ── Build per-FOV rows ─────────────────────────────────────────────────
    rows = []
    for R in all_fov_results:
        raw_cond = str(fov_condition_map.get(R.get('fov', ''), '') or '').strip()
        if raw_cond in _DRUG_CONTROL_LABELS or raw_cond == '':
            cond = 'No Drug'
        else:
            cond = raw_cond
        if cond not in CONDITIONS:
            continue

        scs = R.get('scs1')
        merged = R.get('merged')

        # PSP count from scs dict
        psp_count = 0
        if scs and psp_key in scs:
            psp_count = sum(len(v) for v in scs[psp_key].values())

        # Validation % and mean score from merged df
        pct_val = 0.0
        mean_score = 0.0
        if merged is not None and not merged.empty:
            subset = merged[merged['type'].str.upper() == type_str]
            n_total = len(subset)
            n_val = subset['consensus_tier'].isin(VAL_TIERS).sum()
            pct_val = 100.0 * n_val / n_total if n_total else 0.0
            scores = _pd.concat(
                [subset[c].dropna() for c in score_cols_p1 if c in subset.columns]
            )
            mean_score = float(scores.mean()) if len(scores) else 0.0

        rows.append({
            'fov':           R.get('fov', ''),
            'condition':     cond,
            'psp_count':     psp_count,
            'pct_validated': pct_val,
            'mean_score':    mean_score,
        })

    df_cmp = _pd.DataFrame(rows)
    if df_cmp.empty:
        print(f"No data rows collected for {ct.upper()} comparison.")
        return df_cmp

    valid_conds = [c for c in CONDITIONS if not df_cmp.loc[df_cmp['condition'] == c].empty]
    if len(valid_conds) < 2:
        print(f"Not enough conditions with data — found: {valid_conds}")
        return df_cmp

    # ── Plot ───────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for ax, (col, ylabel) in zip(axes, metrics):
        for i, cond in enumerate(valid_conds):
            vals = df_cmp.loc[df_cmp['condition'] == cond, col].dropna()
            n = len(vals)
            mean = float(vals.mean()) if n else 0.0
            sem = float(vals.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
            ax.bar(
                i, mean, yerr=sem,
                color=COLORS[cond], width=0.55, capsize=6,
                error_kw=dict(elinewidth=1.5),
            )
            ax.scatter([i] * n, vals, color='k', s=20, zorder=5, alpha=0.6)
            ax.text(i, 0, f'n={n}', ha='center', va='bottom', fontsize=8)
        ax.set_xticks(range(len(valid_conds)))
        ax.set_xticklabels(valid_conds, rotation=15, ha='right')
        ax.set_ylabel(ylabel)
        ax.spines[['top', 'right']].set_visible(False)

    title = (
        'No Drug vs ' + ' / '.join(drug_conds)
        + f' — {type_str} metrics'
    )
    fname_stem = (
        'nodrug_vs_'
        + '_'.join(drug_conds).replace('+', '-').replace(' ', '')
        + f'_{ct}.png'
    )
    fig.suptitle(title, fontsize=12)
    plt.tight_layout()
    _out = output_path or fname_stem
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.show()
    plt.close()
    return df_cmp


# ============================================================================
# 9. Condition summary (batch-only, optional)
# ============================================================================
def plot_condition_summary(
    merged_all_fovs: pd.DataFrame,
    condition_col: str = "drug1",
    output_path: Optional[str] = None,
):
    """Per-condition tier composition across FOVs (batch only)."""
    if condition_col not in merged_all_fovs.columns:
        print(f"Column '{condition_col}' not in dataframe — skipping.")
        return
    df = merged_all_fovs.copy()
    df[condition_col] = df[condition_col].fillna("NoDrug").astype(str).str.strip()

    pivot = df.groupby([condition_col, "consensus_tier"]).size().unstack(fill_value=0)
    order_t = ["both", "scs_only", "sta_only", "conflict", "unvalidated"]
    pivot = pivot.reindex(
        columns=[c for c in order_t if c in pivot.columns], fill_value=0
    )

    fig, ax = plt.subplots(figsize=(max(7, 1.4 * len(pivot)), 4.5))
    pivot.plot(
        kind="bar",
        stacked=True,
        ax=ax,
        color=[_BOTH, _SCS_ONLY, _STA_ONLY, _CONFLICT, "#bdc3c7"][: pivot.shape[1]],
        edgecolor="white",
    )
    ax.set_title("Connection consensus tier by condition")
    ax.set_xlabel(condition_col)
    ax.set_ylabel("# connections (validated or seen)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


# ============================================================================
# 9. Spaghetti connectivity overlay (vendored from Hongkang's pipeline_v11.1)
# ============================================================================
# Layout/style constants for source-marker sizing on the overlay.
SPATIAL_BASELINE = 3
SPATIAL_MAX = 18
SPATIAL_MAX_AP = 21


def _resolve_centroids(stim_meta: dict, all_traces) -> Dict[int, tuple]:
    """
    Build {trace_id: (col, row)} from stim_meta's source_centroid_row/col arrays.
    Falls back to legacy blob_row/blob_col fields written by older splitter
    versions. Returns empty dict if no centroid data is available.
    """
    rows = np.asarray(stim_meta.get("source_centroid_row", []), dtype=float)
    cols = np.asarray(stim_meta.get("source_centroid_col", []), dtype=float)
    if rows.size == 0 or cols.size == 0:
        rows = np.asarray(stim_meta.get("blob_row", []), dtype=float)
        cols = np.asarray(stim_meta.get("blob_col", []), dtype=float)
    if rows.size == 0 or cols.size == 0:
        return {}
    centroids = {}
    for tid in all_traces:
        idx = int(tid) - 1  # 1-indexed source IDs -> 0-indexed array
        if idx < 0 or idx >= rows.size:
            continue
        r, c = rows[idx], cols[idx]
        if not (np.isnan(r) or np.isnan(c)):
            centroids[int(tid)] = (float(c), float(r))
    return centroids


def _find_base_image(
    savefast_name: str, fov_dir: Optional[str], preference: str = "quasr"
) -> Optional[str]:
    """
    Look for a Quasr / DLX base image alongside the FOV's savefast.

    preference : 'quasr' or 'dlx'.
        Quasr: looks for *_Red_contrasted.png, then *_Red.png.
        DLX  : looks for *_Yellow.png, *_yellow.png, *_DLX.png, *_dlx.png.
    """
    if not fov_dir or not os.path.isdir(fov_dir):
        return None
    if savefast_name and savefast_name.endswith(".savefast"):
        stem = savefast_name[: -len(".savefast")]
    else:
        stem = "*"
    if preference == "quasr":
        candidates = [
            os.path.join(fov_dir, f"{stem}_Red_contrasted.png"),
            os.path.join(fov_dir, f"{stem}_Red.png"),
            os.path.join(fov_dir, "*_Red.png"),
            os.path.join(fov_dir, "*_Red_contrasted.png"),
        ]
    else:  # dlx
        candidates = [
            os.path.join(fov_dir, "*_RCaMP_*.png"),
            os.path.join(fov_dir, "*_GFP_*.png"),
            os.path.join(fov_dir, f"{stem}_Yellow.png"),
            os.path.join(fov_dir, f"{stem}_yellow.png"),
            os.path.join(fov_dir, f"{stem}_DLX.png"),
            os.path.join(fov_dir, f"{stem}_dlx.png"),
            os.path.join(fov_dir, "*_Yellow.png"),
            os.path.join(fov_dir, "*_yellow.png"),
            os.path.join(fov_dir, "*_DLX.png"),
            os.path.join(fov_dir, "*_dlx.png"),
        ]
    for pattern in candidates:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None


def _plot_spatial_map(
    ax,
    centroids,
    inh_scores_raw,
    exc_scores_raw,
    score_thresh=1.3,
    img_shape=None,
    neuron_type=None,
    aps_all=None,
    title="Spatial Connectivity Map",
    open_circles=False,
    show_labels=False,
    skip_no_connection=False,
):
    """Circles ~ sqrt(n_AP), color = neuron type. Arrows pre -> post with
    thickness/alpha encoding score above threshold.
    """
    ax.set_facecolor("#0D1130")
    if img_shape is not None:
        ax.set_xlim(0, img_shape[1])
        ax.set_ylim(img_shape[0], 0)

    for tid, (cx, cy) in centroids.items():
        nt = (neuron_type or {}).get(tid, "no_valid_outgoing_connections")
        if skip_no_connection and nt == "no_valid_outgoing_connections":
            continue

        n_ap = len(aps_all[tid]) if (aps_all and tid in aps_all) else 0
        r = 3.0 # radius of circle around neurons

        if nt == "inh":
            fc, ec = ("none", _INH) if open_circles else (_INH, _INH_LIGHT)
        elif nt == "exc":
            fc, ec = ("none", _EXC) if open_circles else (_EXC, _EXC_LIGHT)
        else:
            fc, ec = "#555555", "#888888"

        circle = plt.Circle((cx, cy), r, facecolor=fc, edgecolor=ec, lw=1.5, zorder=3)
        ax.add_patch(circle)

        if show_labels:
            fs = max(6, min(11, int(r * 0.7)))
            ax.text(
                cx,
                cy,
                f"T{tid}",
                color="white",
                fontsize=fs,
                ha="center",
                va="center",
                zorder=4,
                fontweight="bold",
            )
            if n_ap > 0:
                ax.text(
                    cx,
                    cy + r + 2,
                    str(n_ap),
                    color="#aaaaaa",
                    fontsize=max(5, fs - 2),
                    ha="center",
                    va="bottom",
                    zorder=4,
                )

    all_scores = list(inh_scores_raw.values()) + list(exc_scores_raw.values())
    above = [s for s in all_scores if s >= score_thresh]
    if not above:
        ax.set_title(title, color="white", fontsize=13, pad=8)
        return
    score_max = max(above)

    def draw_arrows(scores_raw, color):
        for (pre, post), score in scores_raw.items():
            if score < score_thresh:
                continue
            if pre not in centroids or post not in centroids:
                continue
            x1, y1 = centroids[pre]
            x2, y2 = centroids[post]
            t = float(
                np.clip(
                    (score - score_thresh) / max(score_max - score_thresh, 1e-6), 0, 1
                )
            )
            ax.annotate(
                "",
                xy=(x2, y2),
                xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle="->",
                    color=color,
                    lw=1.5 + 4.5 * t,
                    alpha=0.2 + 0.45 * t,
                ),
                zorder=2,
            )

    draw_arrows(inh_scores_raw, _INH)
    draw_arrows(exc_scores_raw, _EXC)

    ax.legend(
        handles=[
            Line2D([0], [0], color=_INH, lw=2, label="Inhibitory"),
            Line2D([0], [0], color=_EXC, lw=2, label="Excitatory"),
        ],
        loc="lower right",
        fontsize=9,
        facecolor="#333333",
        edgecolor="#aaaaaa",
        labelcolor="white",
    )
    ax.set_title(title, color="white", fontsize=13, pad=8)


def plot_spaghetti_overlay(
    merged_df: pd.DataFrame,
    neuron_tier_df: pd.DataFrame,
    stim_meta: dict,
    aps_all: Optional[Dict[int, np.ndarray]] = None,
    score_thresh: float = 1.3,
    base_image_path: Optional[str] = None,
    fov_dir: Optional[str] = None,
    channel: str = "quasr",
    img_shape: tuple = (160, 800),
    title: Optional[str] = None,
    output_path: Optional[str] = None,
    validated_only: bool = True,
    layout: str = "three_panel",
    image_alpha: float = 0.8,
):
    """
    Spatial connectivity overlay — arrows between source centroids on a
    Quasr or DLX base image. Adapted from generate_figures.plot_spaghetti_overlay
    + Hongkang's plot_spatial_map (vendored above).

    Inputs
    ------
    merged_df       : the per-FOV merged_connections table (output of
                      consensus.merge_connections).
    neuron_tier_df  : per-neuron tier table (output of consensus.classify_neurons).
                      Used for neuron color (exc/inh/no_valid_outgoing_connections/ambiguous).
    stim_meta       : dict from data_utils.load_stim_meta — must carry
                      source_centroid_row/col arrays (written by the v16
                      splitter). Re-run the splitter on plates that lack them.
    aps_all         : optional {trace_id: np.array of AP indices}. If provided,
                      circle radius scales as sqrt(n_AP). Pass scs_res['aps_all']
                      or sta_res['aps_all'] depending on which is more relevant.
    base_image_path : explicit path to a PNG base image. If None, the function
                      auto-detects via fov_dir.
    fov_dir         : path to the FOV folder where the savefast lives. Used to
                      auto-detect the base image. Pass `None` to draw on a
                      black background only.
    channel         : 'quasr' (default; *_Red_contrasted.png) or 'dlx'
                      (*_Yellow.png / *_DLX.png).
    validated_only  : if True (default), draw only connections whose
                      consensus_tier is 'both', 'scs_only', or 'sta_only' —
                      i.e. at least one method's validation step passed.
                      Set to False to draw all discovery hits, including
                      'unvalidated' and 'conflict' tiers.
    layout          : 'three_panel' (default) or 'overlay'. 'three_panel'
                      stacks three vertically: connections-only on top,
                      grayscale Quasr image alone in the middle, and the
                      overlay on the bottom — easiest to interpret a busy
                      FOV. 'overlay' draws everything in one panel as
                      before. Auto-downgrades to 'overlay' when no base
                      image is available.
    image_alpha     : opacity of the base image where it appears (default
                      0.8). Drop to ~0.4 if arrows feel obscured by the
                      image; raise toward 1.0 to dim arrows relative to
                      the underlying biology.
    """
    # Optional gate: keep only validated tiers (skip unvalidated / conflict).
    if validated_only:
        VALIDATED_TIERS = {"both", "scs_only", "sta_only"}
        merged_df = merged_df[merged_df["consensus_tier"].isin(VALIDATED_TIERS)]
        if merged_df.empty:
            print(
                "No validated connections to draw "
                "(consensus_tier in {both, scs_only, sta_only}). "
                "Pass validated_only=False to see discovery-only hits."
            )
            return
    # ── Resolve centroids ────────────────────────────────────────────────────
    all_traces = sorted(neuron_tier_df["trace"].astype(int).tolist())
    centroids = _resolve_centroids(stim_meta, all_traces)
    if not centroids:
        print(
            "No source centroids in stim_meta. Re-run SCS_MovieSplit_v17.m "
            "on this plate to populate source_centroid_row/col, or pass "
            "stim_meta with those fields populated."
        )
        return

    # ── Build inh / exc score dicts from merged_df ───────────────────────────
    # We pick whichever score is highest per (pre, post): merged_df has
    # sta_score_p1 and scs_score_p1 — combine via max so a connection seen by
    # only one method still draws an arrow.
    inh_scores_raw, exc_scores_raw = {}, {}
    for _, row in merged_df.iterrows():
        pre, post = int(row["pre"]), int(row["post"])
        s_scs = row.get("scs_score_p1", 0.0)
        s_sta = row.get("sta_score_p1", 0.0)
        s_scs = float(s_scs) if pd.notna(s_scs) else 0.0
        s_sta = float(s_sta) if pd.notna(s_sta) else 0.0
        score = max(s_scs, s_sta)
        if score < score_thresh:
            continue
        if str(row["type"]).upper() == "INH":
            inh_scores_raw[(pre, post)] = max(
                inh_scores_raw.get((pre, post), 0.0), score
            )
        else:
            exc_scores_raw[(pre, post)] = max(
                exc_scores_raw.get((pre, post), 0.0), score
            )

    # ── Neuron type map (for circle colors) ──────────────────────────────────
    neuron_type = {}
    for _, row in neuron_tier_df.iterrows():
        tid = int(row["trace"])
        ct = str(row.get("consensus_type", "no_valid_outgoing_connections"))
        if "exc" in ct:
            neuron_type[tid] = "exc"
        elif "inh" in ct:
            neuron_type[tid] = "inh"
        else:
            neuron_type[tid] = "no_valid_outgoing_connections"

    # ── Resolve base image ───────────────────────────────────────────────────
    base_img = None
    if base_image_path is None and fov_dir is not None:
        sf_name = stim_meta.get("savefast", "")
        base_image_path = _find_base_image(sf_name, fov_dir, preference=channel)
    if base_image_path and os.path.exists(base_image_path):
        try:
            base_img = plt.imread(base_image_path)
        except Exception as e:
            print(f"Could not read base image {base_image_path}: {e}")
            base_img = None

    # Convert to grayscale for cleaner display behind colored arrows.
    # Uses ITU-R BT.601 luminance for any RGB(A) image.
    base_img_gray = None
    if base_img is not None:
        if base_img.ndim == 2:
            base_img_gray = base_img
        else:
            rgb = base_img[..., :3]
            base_img_gray = (
                0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            )

    if title is None:
        fov = stim_meta.get("fov", "FOV")
        title = (
            f"{fov}  spatial connectivity ({channel.upper()})"
            f"  score>={score_thresh}"
        )
        if validated_only:
            title += "  (validated only)"

    # Auto-downgrade three_panel to overlay when there's no base image to show.
    effective_layout = layout
    if effective_layout == "three_panel" and base_img_gray is None:
        effective_layout = "overlay"

    # ── Render ───────────────────────────────────────────────────────────────
    extent = [0, img_shape[1], img_shape[0], 0]

    def _draw_image(ax_):
        ax_.imshow(
            base_img_gray, cmap="gray", extent=extent, aspect="auto", alpha=image_alpha
        )

    def _draw_sources_only(ax_, panel_title):
        # Neuron circles with no connection arrows — spatial source map.
        _plot_spatial_map(
            ax_,
            centroids,
            inh_scores_raw={},
            exc_scores_raw={},
            score_thresh=score_thresh,
            img_shape=img_shape,
            neuron_type=neuron_type,
            aps_all=aps_all,
            title=panel_title,
        )

    def _draw_arrows(ax_, with_image, panel_title):
        # When `with_image` is True we already drew the image first; the
        # spatial map only needs to add circles and arrows on top.
        if not with_image:
            ax_.set_facecolor("#0D1130")
        _plot_spatial_map(
            ax_,
            centroids,
            inh_scores_raw=inh_scores_raw,
            exc_scores_raw=exc_scores_raw,
            score_thresh=score_thresh,
            img_shape=img_shape,
            neuron_type=neuron_type,
            aps_all=aps_all,
            title=panel_title,
        )

    if effective_layout == "three_panel":
        # Three rows stacked vertically — preserves full image width per panel.
        per_panel_h = 14 * img_shape[0] / img_shape[1]
        fig, axes = plt.subplots(3, 1, figsize=(14, 3 * per_panel_h + 1.0))
        # Top: sources only (neuron circles, no arrows)
        _draw_sources_only(axes[0], panel_title=f"{title}  —  sources")
        # Middle: grayscale image, no arrows
        _draw_image(axes[1])
        axes[1].set_xlim(0, img_shape[1])
        axes[1].set_ylim(img_shape[0], 0)
        axes[1].set_title(
            f"{title}  —  {channel.upper()} (grayscale)",
            color="white",
            fontsize=13,
            pad=8,
        )
        axes[1].set_facecolor("#0D1130")
        # Bottom: image + arrows
        _draw_image(axes[2])
        _draw_arrows(axes[2], with_image=True, panel_title=f"{title}  —  overlay")
        for ax_ in axes:
            ax_.set_aspect("equal")
    else:
        # Single-panel overlay (or connections-only when no image is available).
        fig, ax = plt.subplots(figsize=(14, 14 * img_shape[0] / img_shape[1]))
        if base_img_gray is not None:
            img_shape = (base_img_gray.shape[0], base_img_gray.shape[1])
            extent = [0, img_shape[1], img_shape[0], 0]
            _draw_image(ax)
        _draw_arrows(ax, with_image=base_img_gray is not None, panel_title=title)
        ax.set_aspect("equal")

    fig.patch.set_facecolor("none")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="none")
        #print(f"Saved: {output_path}")
    if plt.isinteractive():
        plt.show()


# ============================================================================
# 10. Batch-level validation-rate per FOV (EXC / INH)
# ============================================================================
_VALIDATED_TIERS = ("both", "scs_only", "sta_only")


def _draw_summary_boxplot(ax, groups, ylabel, title, ylim=None):
    """
    Box plot + jittered dots for a list of (label, values, color) groups.
    Used by the per-FOV batch plots to show collapsed summaries.
    """
    labels, colors = [], []
    for i, (label, vals, color) in enumerate(groups):
        vals = np.asarray([v for v in vals if not np.isnan(v)], dtype=float)
        labels.append(label)
        colors.append(color)
        if len(vals) == 0:
            continue
        bp = ax.boxplot(
            vals, positions=[i], widths=0.45, patch_artist=True,
            medianprops=dict(color="white", linewidth=2),
            boxprops=dict(facecolor=color, alpha=0.75, linewidth=0),
            whiskerprops=dict(color="#444", linewidth=1),
            capprops=dict(color="#444", linewidth=1),
            flierprops=dict(marker="", markersize=0),
            zorder=2,
        )
        jitter = np.random.uniform(-0.12, 0.12, len(vals))
        ax.scatter(
            np.full(len(vals), i) + jitter, vals,
            color="white", edgecolor="#333333", s=22, zorder=3, linewidth=0.8,
        )
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(labels)
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)


def plot_validation_rate_by_fov(
    df_all_conn: pd.DataFrame,
    output_path: Optional[str] = None,
    title: str = "Per-FOV validation rate",
    drug_col: str = "drug1",
    drug_map: Optional[dict] = None,
):
    """
    Two figures:
      1. Per-FOV grouped bar chart: % validated EXC and INH connections.
      2. Summary bar (mean ± SD across FOVs) for EXC and INH.

    Validated = consensus_tier in {both, scs_only, sta_only}.

    Parameters
    ----------
    drug_col : column in df_all_conn holding drug/condition label (default 'drug1').
    drug_map : optional explicit {fov: drug_label} dict — takes priority over drug_col.
               Pass drug_map={} to suppress the subtitle entirely.
    """
    if df_all_conn.empty:
        print("df_all_conn is empty — nothing to plot.")
        return

    is_validated = df_all_conn["consensus_tier"].isin(_VALIDATED_TIERS)
    df = df_all_conn.assign(_validated=is_validated)

    fovs = sorted(df["fov"].unique())
    _dmap  = _fov_drug_map(df, drug_col, drug_map)
    _sub   = _drug_subtitle(_dmap, fovs)
    _title = title + _sub
    rows = []
    for fov in fovs:
        sub = df[df["fov"] == fov]
        for ctype in ("EXC", "INH"):
            cs = sub[sub["type"].str.upper() == ctype]
            n_disc = len(cs)
            n_val = int(cs["_validated"].sum())
            pct = (100.0 * n_val / n_disc) if n_disc > 0 else float("nan")
            rows.append(dict(fov=fov, type=ctype, n_disc=n_disc, n_val=n_val, pct=pct))
    pf = pd.DataFrame(rows)

    # ── Plot 1: per-FOV ───────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(fovs)), 4.5))
    x = np.arange(len(fovs))
    width = 0.4
    exc = pf[pf["type"] == "EXC"].set_index("fov").reindex(fovs)
    inh = pf[pf["type"] == "INH"].set_index("fov").reindex(fovs)
    ax.bar(x - width / 2, exc["pct"], width, color=_EXC, label="EXC", edgecolor="white")
    ax.bar(x + width / 2, inh["pct"], width, color=_INH, label="INH", edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(fovs, rotation=60, ha="right", fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% validated")
    ax.set_title(_title)
    ax.legend(fontsize=9, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        ##print(f"Saved: {output_path}")
    plt.close()

    # ── Plot 2: summary box plot across FOVs ─────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(3, 4))
    _draw_summary_boxplot(
        ax2,
        [("EXC", pf[pf["type"] == "EXC"]["pct"].values, _EXC),
         ("INH", pf[pf["type"] == "INH"]["pct"].values, _INH)],
        ylabel="% validated",
        title=f"{_title}\n(n={len(fovs)} FOVs)",
        ylim=(0, 110),
    )
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit(".", 1)[0]
        plt.savefig(f"{base}_summary.png", dpi=150, bbox_inches="tight")
        print(f"Saved: {base}_summary.png")
    plt.close()


def plot_validated_conn_count_by_fov(
    df_all_conn: pd.DataFrame,
    output_path: Optional[str] = None,
    title: str = "Validated connections per FOV",
    drug_col: str = "drug1",
    drug_map: Optional[dict] = None,
):
    """
    Per-FOV stacked bar: number of validated EXC and INH connections.

    Parameters
    ----------
    drug_col : column in df_all_conn holding drug/condition label (default 'drug1').
    drug_map : optional explicit {fov: drug_label} dict — takes priority over drug_col.
    """
    if df_all_conn.empty:
        print("df_all_conn is empty — nothing to plot.")
        return

    val = df_all_conn[df_all_conn["consensus_tier"].isin(_VALIDATED_TIERS)].copy()
    val["type"] = val["type"].str.upper()

    fovs = sorted(df_all_conn["fov"].unique())
    _dmap  = _fov_drug_map(df_all_conn, drug_col, drug_map)
    _sub   = _drug_subtitle(_dmap, fovs)
    _title = title + _sub
    counts = (val.groupby(["fov", "type"]).size().unstack(fill_value=0).reindex(fovs, fill_value=0))
    for col in ("EXC", "INH"):
        if col not in counts.columns:
            counts[col] = 0

    fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(fovs)), 4))
    x = np.arange(len(fovs))
    width = 0.5
    ax.bar(x, counts["EXC"], width, color=_EXC, label="EXC")
    ax.bar(x, counts["INH"], width, bottom=counts["EXC"], color=_INH, label="INH")

    ax.set_xticks(x)
    ax.set_xticklabels(fovs, rotation=60, ha="right", fontsize=9)
    ax.set_ylabel("Validated connections (n)")
    ax.set_title(_title)
    ax.legend(fontsize=9, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        ##print(f"Saved: {output_path}")
    plt.close()

    # ── Summary box plot across FOVs ──────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(3, 4))
    _draw_summary_boxplot(
        ax2,
        [("EXC", counts["EXC"].values.astype(float), _EXC),
         ("INH", counts["INH"].values.astype(float), _INH)],
        ylabel="Validated connections (n)",
        title=f"{_title}\n(n={len(fovs)} FOVs)",
    )
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit(".", 1)[0]
        plt.savefig(f"{base}_summary.png", dpi=150, bbox_inches="tight")
        print(f"Saved: {base}_summary.png")
    plt.close()


# ============================================================================
# 11. Batch-level: % of neurons with >= 1 validated outgoing connection
# ============================================================================
def plot_connected_neurons_pct(
    df_all_conn: pd.DataFrame,
    df_all_neurons: pd.DataFrame,
    output_path: Optional[str] = None,
    title: str = "Neurons with >= 1 validated connection",
    drug_col: str = "drug1",
    drug_map: Optional[dict] = None,
):
    """
    Per-FOV bar: % of neurons that have at least one validated outgoing
    connection (any type). The denominator is `df_all_neurons` (one row per
    detected neuron in the FOV); the numerator is the unique pre-neuron count
    among validated rows of df_all_conn for that FOV.

    "Validated" here uses the same consensus_tier rule as
    plot_validation_rate_by_fov — i.e. {both, scs_only, sta_only}.

    Parameters
    ----------
    drug_col : column in df_all_conn or df_all_neurons holding drug/condition
               label (default 'drug1'). df_all_conn is checked first.
    drug_map : optional explicit {fov: drug_label} dict — takes priority.
    """
    if df_all_neurons.empty:
        print("df_all_neurons is empty — nothing to plot.")
        return

    fovs = sorted(df_all_neurons["fov"].unique())
    # Prefer drug info from df_all_conn (richer); fall back to df_all_neurons.
    _src   = df_all_conn if not df_all_conn.empty else df_all_neurons
    _dmap  = _fov_drug_map(_src, drug_col, drug_map)
    _sub   = _drug_subtitle(_dmap, fovs)
    _title = title + _sub
    is_validated = (
        df_all_conn["consensus_tier"].isin(_VALIDATED_TIERS)
        if not df_all_conn.empty
        else pd.Series(dtype=bool)
    )
    val = df_all_conn[is_validated] if not df_all_conn.empty else df_all_conn

    rows = []
    for fov in fovs:
        n_total = int((df_all_neurons["fov"] == fov).sum())
        if val.empty:
            n_connected = 0
        else:
            connected_pre = set(val.loc[val["fov"] == fov, "pre"].astype(int).unique())
            n_connected = len(connected_pre)
        pct = (100.0 * n_connected / n_total) if n_total > 0 else float("nan")
        rows.append(dict(fov=fov, n_total=n_total, n_connected=n_connected, pct=pct))
    pf = pd.DataFrame(rows)

    # ── Plot 1: per-FOV ───────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(fovs)), 4.0))
    x = np.arange(len(fovs))
    ax.bar(x, pf["pct"], color=_BOTH, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(pf["fov"], rotation=60, ha="right", fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% neurons with >= 1 validated connection")
    ax.set_title(_title)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        ##print(f"Saved: {output_path}")
    plt.close()

    # ── Plot 2: summary box plot across FOVs ─────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(2.5, 4))
    _draw_summary_boxplot(
        ax2,
        [("connected", pf["pct"].values, _BOTH)],
        ylabel="% neurons with >= 1 validated connection",
        title=f"{_title}\n(n={len(fovs)} FOVs)",
        ylim=(0, 110),
    )
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit(".", 1)[0]
        plt.savefig(f"{base}_summary.png", dpi=150, bbox_inches="tight")
        print(f"Saved: {base}_summary.png")
    plt.close()


# ============================================================================
# 12. Batch-level: AP / EPSP / IPSP counts per FOV
# ============================================================================
def build_event_counts_df(batch_results: list) -> pd.DataFrame:
    """
    Summarise AP, EPSP, and IPSP counts per FOV from a list of per-FOV
    result dicts (each element is the R dict from run_one_fov or equivalent).

    Expected R keys used:
        'fov'          — FOV identifier string
        'scs1'         — SCS result dict (epsps_all, ipsps_all, ap_counts)
        'sta1'         — STA result dict (ap_counts) — used when scs1 is None
        'neuron_tier'  — per-neuron tier DataFrame

    Returns a DataFrame with columns:
        fov, n_neurons, n_aps, n_epsps, n_ipsps
    """
    rows = []
    for R in batch_results:
        fov = R.get("fov", "unknown")
        scs = R.get("scs1")
        sta = R.get("sta1")

        # APs: SCS spontaneous trace is the primary source; STA stim trace fallback.
        src = scs if scs is not None else sta
        n_aps = int(sum(len(v) for v in src.get("aps_all", {}).values())) if src else 0

        n_epsps = (
            int(sum(len(v) for v in scs.get("epsps_all", {}).values())) if scs else 0
        )
        n_ipsps = (
            int(sum(len(v) for v in scs.get("ipsps_all", {}).values())) if scs else 0
        )

        tier_df = R.get("neuron_tier")
        n_neurons = (
            int(len(tier_df)) if (tier_df is not None and not tier_df.empty) else 0
        )

        rows.append(
            dict(
                fov=fov,
                n_neurons=n_neurons,
                n_aps=n_aps,
                n_epsps=n_epsps,
                n_ipsps=n_ipsps,
            )
        )
    return pd.DataFrame(rows)


def plot_event_counts_by_fov(
    df_event_counts: pd.DataFrame,
    output_path: Optional[str] = None,
    log_scale: bool = False,
    title: str = "Detected events per FOV",
    drug_col: str = "drug1",
    drug_map: Optional[dict] = None,
):  # noqa: E501
    """
    Grouped bar chart: total APs, EPSPs, and IPSPs per FOV.

    Parameters
    ----------
    df_event_counts : DataFrame with columns [fov, n_aps, n_epsps, n_ipsps]
                      and optionally n_neurons. Build with build_event_counts_df.
    log_scale       : log y-axis — useful when AP counts dwarf PSP event counts.
    drug_col        : column in df_event_counts holding drug/condition label
                      (default 'drug1').
    drug_map        : optional explicit {fov: drug_label} dict — takes priority.
    """
    if df_event_counts.empty:
        print("df_event_counts is empty — nothing to plot.")
        return

    fovs = list(df_event_counts["fov"])
    _dmap  = _fov_drug_map(df_event_counts, drug_col, drug_map)
    _sub   = _drug_subtitle(_dmap, fovs)
    _title = title + _sub
    x = np.arange(len(fovs))
    width = 0.25
    n_aps = df_event_counts["n_aps"].values.astype(float)
    n_epsps = df_event_counts["n_epsps"].values.astype(float)
    n_ipsps = df_event_counts["n_ipsps"].values.astype(float)
    n_neurons = (
        df_event_counts["n_neurons"].values
        if "n_neurons" in df_event_counts.columns
        else np.zeros(len(fovs), dtype=int)
    )

    fig, ax = plt.subplots(figsize=(max(8, 0.7 * len(fovs)), 5))
    ax.bar(x - width, n_aps, width, label="APs", color="#555555", edgecolor="white")
    ax.bar(x, n_epsps, width, label="EPSPs", color=_EXC, edgecolor="white")
    ax.bar(x + width, n_ipsps, width, label="IPSPs", color=_INH, edgecolor="white")

    if log_scale:
        ax.set_yscale("log")

    # Annotate neuron count above the AP bar.
    y_top = np.nanmax(n_aps) if np.any(n_aps > 0) else 1.0
    for i, (n, nn) in enumerate(zip(n_aps, n_neurons)):
        if nn > 0:
            ypos = n * 1.08 if log_scale else n + y_top * 0.02
            ax.text(
                x[i] - width,
                ypos,
                f"{int(nn)} cells",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#555555",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(fovs, rotation=60, ha="right", fontsize=9)
    ax.set_ylabel("Total events (summed across all neurons)")
    ax.set_title(_title)
    ax.legend(fontsize=9, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()

    # ── Summary box plot across FOVs ──────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(4, 4))
    _draw_summary_boxplot(
        ax2,
        [("APs",   n_aps,   "#555555"),
         ("EPSPs", n_epsps, _EXC),
         ("IPSPs", n_ipsps, _INH)],
        ylabel="Total events per FOV",
        title=f"{_title}\n(n={len(fovs)} FOVs)",
    )
    if log_scale:
        ax2.set_yscale("log")
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit(".", 1)[0]
        plt.savefig(f"{base}_summary.png", dpi=150, bbox_inches="tight")
        print(f"Saved: {base}_summary.png")
    plt.close()


# ============================================================================
# 13. Plate-level well/FOV heatmaps
# ============================================================================


def _parse_well_coords(well_series: pd.Series):
    """Parse 'A1'-style well IDs into (row_int, col_int) Series pair."""
    row = well_series.str[0].str.upper().apply(lambda c: ord(c) - ord("A"))
    col = well_series.str[1:].astype(int) - 1
    return row, col


def plot_well_heatmap(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    output_path: Optional[str] = None,
    cmap: str = "Blues",
    vmin: float = 0,
    vmax: float = 100,
    cbar_label: Optional[str] = None,
    fmt: str = ".0f",
    fov_level: bool = False,
    fov_subrows: int = 2,
    n_plate_rows: int = 8,
    n_plate_cols: int = 12,
    drug_map: Optional[dict] = None,
    drug_col: str = "drug1",
) -> None:
    """
    96-well plate heatmap for any per-FOV or per-well metric.

    Parameters
    ----------
    df          : DataFrame with columns 'well', metric_col, and (if
                  fov_level=True) 'fov'. Well format: 'A1', 'B3', etc.
                  Build with build_validated_pct_df, build_exc_balance_df,
                  or build_active_neuron_df.
    metric_col  : Column name to colour-encode.
    fov_level   : If True, draw fov_subrows sub-rows per well (one per FOV).
                  If False, average metric_col across FOVs per well first.
    fov_subrows : Sub-rows per well when fov_level=True (default 2).
    drug_map    : optional {well_id: drug_label} dict. When provided, each
                  well tile gets a small drug-condition label near the top.
                  Control labels (DMSO, No Drug, etc.) are shown as 'ctrl'.
    drug_col    : column in df holding drug/condition label (default 'drug1').
                  Used to auto-build drug_map when drug_map is not supplied.
                  Pass drug_col=None to suppress the label entirely.
    """
    from matplotlib.cm import ScalarMappable

    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cm = plt.get_cmap(cmap)
    _EMPTY = (0.93, 0.93, 0.93, 1)

    df = df[df["well"].notna() & (df["well"] != "unknown")].copy()
    df["_row"], df["_col"] = _parse_well_coords(df["well"])

    # Auto-build drug_map from df column when not supplied explicitly.
    if drug_map is None and drug_col and drug_col in df.columns:
        drug_map = (
            df.groupby("well")[drug_col]
            .first()
            .fillna("No Drug")
            .astype(str)
            .str.strip()
            .to_dict()
        )

    if not fov_level:
        # ── Well-averaged view ──────────────────────────────────────────────
        well_avg = df.groupby("well")[metric_col].mean().reset_index()
        well_avg["_row"], well_avg["_col"] = _parse_well_coords(well_avg["well"])

        fig, ax = plt.subplots(figsize=(n_plate_cols * 0.8, n_plate_rows * 0.9))

        # Background: all wells empty
        for r in range(n_plate_rows):
            for c in range(n_plate_cols):
                ax.add_patch(
                    Rectangle(
                        (c, r),
                        1,
                        1,
                        linewidth=1.5,
                        edgecolor="#333333",
                        facecolor=_EMPTY,
                    )
                )

        # Fill wells with data
        for _, row in well_avg.iterrows():
            v = row[metric_col]
            if np.isnan(v):
                continue
            ax.add_patch(
                Rectangle(
                    (int(row["_col"]), int(row["_row"])),
                    1,
                    1,
                    linewidth=1.5,
                    edgecolor="#333333",
                    facecolor=cm(norm(v)),
                )
            )
            ax.text(
                int(row["_col"]) + 0.5,
                int(row["_row"]) + 0.5,
                format(v, fmt),
                ha="center",
                va="center",
                fontsize=8,
            )

    else:
        # ── FOV-level subdivided view ───────────────────────────────────────
        df["_sub"] = df.groupby("well").cumcount()
        fig, ax = plt.subplots(figsize=(n_plate_cols * 0.8, n_plate_rows * 0.9))

        # Background: all sub-rows empty
        for r in range(n_plate_rows):
            for c in range(n_plate_cols):
                for s in range(fov_subrows):
                    ax.add_patch(
                        Rectangle(
                            (c, r + s / fov_subrows),
                            1,
                            1 / fov_subrows,
                            linewidth=0.5,
                            edgecolor="#aaaaaa",
                            facecolor=_EMPTY,
                        )
                    )

        # Fill sub-rows with data
        for _, row in df.iterrows():
            sr = int(row["_sub"])
            if sr >= fov_subrows:
                continue
            c, r, v = int(row["_col"]), int(row["_row"]), row[metric_col]
            ax.add_patch(
                Rectangle(
                    (c, r + sr / fov_subrows),
                    1,
                    1 / fov_subrows,
                    linewidth=0.5,
                    edgecolor="#aaaaaa",
                    facecolor=cm(norm(v)) if not np.isnan(v) else _EMPTY,
                )
            )
            fov_label = str(row["fov"]).split("_")[-1] if "fov" in row.index else ""
            text = f"{fov_label}  ({format(v, fmt)})" if not np.isnan(v) else fov_label
            ax.text(
                c + 0.5,
                r + (sr + 0.5) / fov_subrows,
                text,
                ha="center",
                va="center",
                fontsize=6,
            )

        # Well outlines on top
        for r in range(n_plate_rows):
            for c in range(n_plate_cols):
                ax.add_patch(
                    Rectangle(
                        (c, r),
                        1,
                        1,
                        linewidth=1.5,
                        edgecolor="#333333",
                        facecolor="none",
                    )
                )

    # ── Drug-condition label overlay (both modes) ─────────────────────────────
    if drug_map:
        def _abbrev_drug(d: str) -> str:
            return 'ctrl' if d in _DRUG_CONTROL_LABELS else d

        for well_id, drug in drug_map.items():
            label = _abbrev_drug(str(drug).strip())
            try:
                r = ord(str(well_id)[0].upper()) - ord('A')
                c = int(str(well_id)[1:]) - 1
            except (IndexError, ValueError):
                continue
            if 0 <= r < n_plate_rows and 0 <= c < n_plate_cols:
                ax.text(
                    c + 0.5, r + 0.09, label,
                    ha='center', va='top',
                    fontsize=5.5, color='#333333',
                    style='italic', clip_on=True,
                )

    ax.set_xlim(0, n_plate_cols)
    ax.set_ylim(n_plate_rows, 0)
    ax.set_xticks([i + 0.5 for i in range(n_plate_cols)])
    ax.set_xticklabels(range(1, n_plate_cols + 1))
    ax.set_yticks([i + 0.5 for i in range(n_plate_rows)])
    ax.set_yticklabels([chr(ord("A") + i) for i in range(n_plate_rows)])
    ax.tick_params(length=0)
    plt.colorbar(
        ScalarMappable(norm=norm, cmap=cm), ax=ax, label=cbar_label or metric_col
    )
    ax.set_title(title)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        #print(f"Saved: {output_path}")
    plt.close()


def build_validated_pct_df(
    df_conn_md: pd.DataFrame,
    well_col: str = "wellId",
    drug_col: str = "drug1",
) -> pd.DataFrame:
    """
    Per-FOV % of connections that are validated.

    Returns DataFrame: fov, well, pct_validated, n_val, n_total.
    If drug_col is present in df_conn_md, it is passed through as well.
    Pass to plot_well_heatmap with metric_col='pct_validated'.
    """
    has_drug = drug_col and drug_col in df_conn_md.columns
    rows = []
    for fov, sub in df_conn_md.groupby("fov"):
        well = sub[well_col].iloc[0] if well_col in sub.columns else "unknown"
        n_total = len(sub)
        n_val = int(sub["consensus_tier"].isin(_VALIDATED_TIERS).sum())
        pct = 100.0 * n_val / n_total if n_total > 0 else np.nan
        row = dict(fov=fov, well=well, pct_validated=pct, n_val=n_val, n_total=n_total)
        if has_drug:
            row[drug_col] = sub[drug_col].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows)


def build_exc_balance_df(
    df_conn_md: pd.DataFrame,
    well_col: str = "wellId",
    drug_col: str = "drug1",
) -> pd.DataFrame:
    """
    Per-FOV E/I balance index: (n_exc − n_inh) / (n_exc + n_inh).

    -1 = all inhibitory, 0 = balanced, +1 = all excitatory, NaN = no validated connections.
    Returns DataFrame: fov, well, exc_balance, n_exc, n_inh.
    If drug_col is present in df_conn_md, it is passed through as well.
    Pass to plot_well_heatmap with metric_col='exc_balance'.
    """
    has_drug = drug_col and drug_col in df_conn_md.columns
    rows = []
    for fov, sub in df_conn_md.groupby("fov"):
        well = sub[well_col].iloc[0] if well_col in sub.columns else "unknown"
        val = sub[sub["consensus_tier"].isin(_VALIDATED_TIERS)]
        n_exc = int((val["type"].str.upper() == "EXC").sum())
        n_inh = int((val["type"].str.upper() == "INH").sum())
        n_tot = n_exc + n_inh
        pct = (n_exc - n_inh) / n_tot if n_tot > 0 else np.nan
        row = dict(fov=fov, well=well, exc_balance=pct, n_exc=n_exc, n_inh=n_inh)
        if has_drug:
            row[drug_col] = sub[drug_col].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows)


def build_connect_neuron_df(
    all_fov_results: list,
    fov_to_well: dict,
    drug_col: str = "drug1",
    fov_to_drug: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Per-FOV % of neurons that are connected (consensus_type != 'no_valid_outgoing_connections').

    Parameters
    ----------
    all_fov_results : list of per-FOV result dicts, each with keys 'fov'
                      and 'neuron_tier' (DataFrame from classify_neurons).
    fov_to_well     : {fov_id: well_id} — build from df_all_conn_md via
                      df_all_conn_md.groupby('fov')['wellId'].first().to_dict()
    drug_col        : column name to use in the output DataFrame (default 'drug1').
    fov_to_drug     : {fov_id: drug_label} — build from df_all_conn_md via
                      df_all_conn_md.groupby('fov')['drug1'].first().to_dict()
                      Drug1 lives in df_all_conn_md (added by attach_metadata),
                      not in R['meta'], so pass this explicitly.

    Returns DataFrame: fov, well, pct_connected, n_connected, n_total[, drug1].
    Pass to plot_well_heatmap with metric_col='pct_connected'.
    """
    rows = []
    for R in all_fov_results:
        fov = R.get("fov", "unknown")
        well = fov_to_well.get(fov, "unknown")

        # Prefer aps_all (available in both SCS and STA); fall back to neuron tier
        src = R.get("scs1") or R.get("sta1")
        tier_df = R.get("neuron_tier")
        if src and "aps_all" in src:
            aps_all = src["aps_all"]
            n_total = len(aps_all)
            n_connected = int(sum(1 for aps in aps_all.values() if len(aps) > 0))
        elif tier_df is not None and not tier_df.empty:
            n_total = len(tier_df)
            n_connected = int(
                (tier_df["consensus_type"] != "no_valid_outgoing_connections").sum()
            )
        else:
            n_total = n_connected = 0

        pct = 100.0 * n_connected / n_total if n_total > 0 else np.nan
        row = dict(
            fov=fov,
            well=well,
            pct_connected=pct,
            n_connected=n_connected,
            n_total=n_total,
        )
        if drug_col and fov_to_drug is not None:
            cond = str(fov_to_drug.get(fov, '') or '').strip()
            row[drug_col] = cond if cond else 'No Drug'
        rows.append(row)
    return pd.DataFrame(rows)


def build_snr_df(
    all_fov_results: list,
    fov_to_well: dict,
    snr_gate: float = 10.0,
    drug_col: str = "drug1",
    fov_to_drug: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Per-FOV % of active neurons whose mean AP SNR >= snr_gate.

    Uses SCS spontaneous traces preferentially (fall back to STA).
    Silent neurons (0 APs) are excluded from the denominator.

    Parameters
    ----------
    all_fov_results : list of per-FOV result dicts from run_one_fov.
    fov_to_well     : {fov_id: well_id} mapping.
    snr_gate        : mean SNR threshold (default 10.0 — higher than the
                      3.5 AP detection gate since all APs already passed that).
    drug_col        : column name to use in the output DataFrame (default 'drug1').
    fov_to_drug     : {fov_id: drug_label} — build from df_all_conn_md via
                      df_all_conn_md.groupby('fov')['drug1'].first().to_dict()

    Returns DataFrame: fov, well, pct_above_snr, n_above, n_total, median_snr[, drug1].
    Pass to plot_well_heatmap with metric_col='pct_above_snr'.
    """
    from .data_utils import compute_neuron_snr

    rows = []
    for R in all_fov_results:
        fov = R.get("fov", "unknown")
        well = fov_to_well.get(fov, "unknown")
        src = R.get("scs1") or R.get("sta1")
        if src is None:
            row = dict(
                fov=fov,
                well=well,
                pct_above_snr=np.nan,
                n_above=0,
                n_total=0,
                median_snr=np.nan,
            )
            if drug_col and fov_to_drug is not None:
                cond = str(fov_to_drug.get(fov, '') or '').strip()
                row[drug_col] = cond if cond else 'No Drug'
            rows.append(row)
            continue
        mean_snr, above_gate = compute_neuron_snr(
            src["traces_all"], src["aps_all"], snr_gate=snr_gate
        )
        n_total = len(mean_snr)
        n_above = int(sum(above_gate.values()))
        pct = 100.0 * n_above / n_total if n_total > 0 else np.nan
        med_snr = float(np.median(list(mean_snr.values()))) if mean_snr else np.nan
        row = dict(
            fov=fov,
            well=well,
            pct_above_snr=pct,
            n_above=n_above,
            n_total=n_total,
            median_snr=med_snr,
        )
        if drug_col and fov_to_drug is not None:
            cond = str(fov_to_drug.get(fov, '') or '').strip()
            row[drug_col] = cond if cond else 'No Drug'
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================================
# 13. Batch-level: full stacked voltage traces with stim boxes
# ============================================================================
def plot_full_stacked_traces_batch(
    quartets: list,
    all_fov_results: list,
    output_dir: str,
    fs: int = 500,
    sep: float = 1.0,
    regress: bool = False,
    max_workers: int = 4,
) -> None:
    """
    For every FOV in `quartets`, concatenate the four trace CSVs
    (spont_p1, spont_p2, stim_p1, stim_p2), plot all neurons as a
    vertically stacked normalised trace, and overlay cyan vertical lines
    at the exact frame where each neuron was stimulated.  Traces are
    sorted top-to-bottom by FOV row position (source_centroid_row);
    stim-targeted neurons are drawn in Quiver purple, others in Quiver navy.

    Saves one PNG per FOV to <output_dir>/<fov>/full_stacked_traces.png.
    Figures are closed after saving to avoid flooding the notebook.

    Parameters
    ----------
    quartets        : list of dicts produced by the batch discovery loop.
                      Each dict must have keys: fov, meta, spont_p1,
                      spont_p2, stim_p1, stim_p2.
    all_fov_results : list of per-FOV result dicts from run_one_fov.
    output_dir      : root output directory; a sub-folder per FOV is
                      created automatically.
    fs              : sampling rate in Hz (default 500).
    sep             : vertical separation between traces in normalised units
                      (default 1.0).
    regress         : if True, apply global signal regression to each CSV
                      part before plotting (matches what the pipeline
                      analyses). Default False plots raw traces.
    max_workers     : number of parallel threads for FOV processing
                      (default 4).
    """
    import concurrent.futures
    from .data_utils import load_stim_meta, regress_global_signal
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection

    fov_result_map = {R["fov"]: R for R in all_fov_results}

    def _process_one_fov(q):
        fov = q["fov"]
        R = fov_result_map.get(fov)
        if R is None:
            print(f"  [{fov}] no results found, skipping.")
            return

        meta = load_stim_meta(q["meta"])

        # ── load & concatenate trace CSVs ─────────────────────────────
        part_keys  = ["spont_p1", "spont_p2", "stim_p1", "stim_p2"]
        loaded_dfs = {}
        for key in part_keys:
            path = q.get(key)
            if path and os.path.exists(path):
                df = pd.read_csv(path)
                loaded_dfs[key] = regress_global_signal(df) if regress else df
        dfs = [loaded_dfs[k] for k in part_keys if k in loaded_dfs]
        if not dfs:
            print(f"  [{fov}] no CSV files found, skipping.")
            return

        # ── align all CSVs to a canonical column order before
        #    concatenating; filter to T{int} columns only so stray
        #    non-neuron columns (e.g. Time, Frame) don't crash parsing ─
        ref_cols = [c for c in dfs[0].columns
                    if c.startswith('T') and c[1:].isdigit()]
        for k, df in enumerate(dfs):
            if list(df.columns) != list(dfs[0].columns):
                print(f"  [{fov}] WARNING: CSV {k} column order differs "
                      f"from CSV 0 — reindexing to match.")
        full = np.concatenate(
            [df.reindex(columns=ref_cols).values for df in dfs],
            axis=0,
        )
        trace_ids = [int(c[1:]) for c in ref_cols]

        n_neurons = full.shape[1]
        n_samples = full.shape[0]
        t = np.arange(n_samples) / fs

        # ── frame offsets derived from actual loaded row counts so that
        #    missing CSV parts don't shift stim markers incorrectly ────
        actual_spont_rows   = sum(len(loaded_dfs[k]) for k in ("spont_p1", "spont_p2")
                                  if k in loaded_dfs)
        actual_stim_p1_rows = len(loaded_dfs["stim_p1"]) if "stim_p1" in loaded_dfs else 0
        p1_frames  = np.asarray(meta.get("stim_frames_part1", []), dtype=float)
        p2_frames  = np.asarray(meta.get("stim_frames_part2", []), dtype=float)

        # ── build per-neuron absolute frame list from barcode sidecar ─
        sidecar = R.get("mat_sidecar")
        neuron_frames_map = {tid: [] for tid in trace_ids}

        if sidecar is not None:
            ordering = np.asarray(sidecar["ordering_of_masks"], dtype=int).flatten()
            barcode  = np.asarray(sidecar["barcode_matrix"], dtype=bool)

            if barcode.ndim < 2 or barcode.shape[1] == 0:
                barcode = None

            if barcode is not None:
                n_mat    = barcode.shape[0]
                n_events = min(len(ordering), len(p1_frames))
                for ev in range(n_events):
                    col = int(ordering[ev]) - 1
                    if col < 0 or col >= barcode.shape[1]:
                        continue
                    abs_p1 = float(p1_frames[ev]) - 1 + actual_spont_rows
                    abs_p2 = (float(p2_frames[ev]) - 1 + actual_spont_rows + actual_stim_p1_rows
                                if ev < len(p2_frames) else None)
                    for j in range(n_mat):
                        if barcode[j, col]:
                            tid = j + 1
                            if tid in neuron_frames_map:
                                neuron_frames_map[tid].append(abs_p1)
                                if abs_p2 is not None:
                                    neuron_frames_map[tid].append(abs_p2)
            else:
                print(f"  [{fov}] barcode_matrix empty — falling back to JSON sfps")
                sfps = meta.get("stim_frames_per_source", {})
                for tid in trace_ids:
                    parts = sfps.get(f"T{tid}", sfps.get(str(tid), {}))
                    sf1 = np.asarray(parts.get("part1") or [], dtype=float)
                    sf2 = np.asarray(parts.get("part2") or [], dtype=float)
                    neuron_frames_map[tid] = (
                        (sf1 - 1 + actual_spont_rows).tolist() +
                        (sf2 - 1 + actual_spont_rows + actual_stim_p1_rows).tolist()
                    )
        else:
            # fallback: stim_frames_per_source from JSON
            sfps = meta.get("stim_frames_per_source", {})
            for tid in trace_ids:
                parts = sfps.get(f"T{tid}", sfps.get(str(tid), {}))
                _p1 = parts.get("part1"); sf1 = np.asarray(_p1 if _p1 is not None else [], dtype=float)
                _p2 = parts.get("part2"); sf2 = np.asarray(_p2 if _p2 is not None else [], dtype=float)
                neuron_frames_map[tid] = (
                    (sf1 - 1 + actual_spont_rows).tolist() +
                    (sf2 - 1 + actual_spont_rows + actual_stim_p1_rows).tolist()
                )
        # ── spatial sort: order traces top-to-bottom by FOV row ──────
        c_rows = np.asarray(meta.get("source_centroid_row", []), dtype=float)
        c_cols = np.asarray(meta.get("source_centroid_col", []), dtype=float)
        # Build {tid: (row, col)} — index is 1-based (tid = j+1)
        centroid_map: dict = {}
        for j, tid in enumerate(trace_ids):
            r = float(c_rows[j]) if j < len(c_rows) else np.nan
            c = float(c_cols[j]) if j < len(c_cols) else np.nan
            centroid_map[tid] = (r, c)

        def _sort_key(tid):
            r, c = centroid_map.get(tid, (np.nan, np.nan))
            # NaN centroids sink to the bottom of the stack
            return (0, r) if not np.isnan(r) else (1, tid)

        sorted_trace_ids = sorted(trace_ids, key=_sort_key)
        # Map tid → column index in `full` array (original CSV order)
        tid_to_col = {tid: i for i, tid in enumerate(trace_ids)}

        # ── stim-mask membership for trace colouring ─────────────────
        # Prefer barcode (authoritative, consistent across FOVs) over
        # stim_mask_sources, which can be unreliable (40 on one FOV, 90
        # on another). Fall back to stim_mask_sources when no sidecar.
        _tid_set = set(trace_ids)
        if sidecar is not None:
            _bc = np.asarray(sidecar.get("barcode_matrix", []), dtype=bool)
            if _bc.ndim == 2 and _bc.size > 0:
                stim_mask_set = {j + 1 for j in np.where(_bc.any(axis=1))[0]
                                 if (j + 1) in _tid_set}
            else:
                stim_mask_set = {int(x) for x in meta.get("stim_mask_sources", [])
                                 if int(x) in _tid_set}
        else:
            stim_mask_set = {int(x) for x in meta.get("stim_mask_sources", [])
                             if int(x) in _tid_set}
        _STIM_COLOR   = _QUIVER_PURPLE
        _NOSTIM_COLOR = "#0D1130"

        # ── vectorised normalisation ──────────────────────────────────
        col_order  = [tid_to_col[tid] for tid in sorted_trace_ids]
        data       = full[:, col_order].T.astype(float)   # (n_neurons, n_samples)
        means      = np.nanmean(data, axis=1, keepdims=True)
        rngs       = (np.nanmax(data, axis=1, keepdims=True)
                      - np.nanmin(data, axis=1, keepdims=True))
        data_norm  = (data - means) / (rngs + 1e-9)
        y_centers  = np.arange(n_neurons - 1, -1, -1, dtype=float) * sep

        # ── build trace + stim segments ───────────────────────────────
        trace_segs   = []
        trace_colors = []
        stim_segments = []

        for plot_i, tid in enumerate(sorted_trace_ids):
            y     = data_norm[plot_i] + y_centers[plot_i]
            color = _STIM_COLOR if tid in stim_mask_set else _NOSTIM_COLOR

            # split at NaN gaps into contiguous polyline segments
            valid = ~np.isnan(y)
            if valid.any():
                diff   = np.diff(valid.astype(np.int8))
                starts = np.where(np.concatenate([[valid[0]],  diff ==  1]))[0]
                ends   = np.where(np.concatenate([diff == -1, [valid[-1]]]))[0] + 1
                for s, e in zip(starts, ends):
                    if e - s > 1:
                        trace_segs.append(np.column_stack([t[s:e], y[s:e]]))
                        trace_colors.append(color)

            y_bot = y_centers[plot_i] - sep * 0.45
            y_top = y_centers[plot_i] + sep * 0.45
            for sf in neuron_frames_map.get(tid, []):
                stim_segments.append([(sf / fs, y_bot), (sf / fs, y_top)])

        # ── figure (OO API — thread-safe, no plt global state) ────────
        fig = Figure(figsize=(20, max(4, n_neurons * 0.35)))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        if trace_segs:
            ax.add_collection(LineCollection(
                trace_segs, colors=trace_colors, linewidths=0.4, alpha=0.8, zorder=2,
            ))
        if stim_segments:
            ax.add_collection(LineCollection(
                stim_segments, colors="cyan", linewidths=0.8, alpha=0.85, zorder=1,
            ))

        # ── axes formatting ───────────────────────────────────────────
        ax.set_yticks([y_centers[i] for i in range(n_neurons)])
        ax.set_yticklabels([f"T{tid}" for tid in sorted_trace_ids], fontsize=5)
        ax.set_xlim(0, t[-1])
        ax.set_ylim(-sep, n_neurons * sep)
        ax.set_xlabel("Time (s)")
        n_stim = len(stim_mask_set & set(trace_ids))
        ax.set_title(
            f"{fov} — full trace ({n_neurons} neurons, sorted top→bottom by FOV row)  |  "
            f"purple = stim-targeted ({n_stim})  |  cyan = stim delivery"
        )
        ax.legend(
            handles=[
                Patch(color=_STIM_COLOR,   alpha=0.8, label=f"stim-targeted ({n_stim})"),
                Patch(color=_NOSTIM_COLOR, alpha=0.8, label="not targeted"),
                Patch(color="cyan",        alpha=0.6, label="stim delivery"),
            ],
            fontsize=8,
        )
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()

        # ── save ──────────────────────────────────────────────────────
        fname    = "full_stacked_traces_regressed.png" if regress else "full_stacked_traces.png"
        out_path = os.path.join(output_dir, fov, fname)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"  [{fov}] saved {out_path}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(_process_one_fov, quartets))


# ============================================================================
# 14. Batch-level: DLX overlay and cell identity verification
# ============================================================================
# Not all folders have DLX (yellow), currently using GFP image which is wrong. Fix.


def _otsu_1d(values):
    """Otsu threshold on a 1D float array. Falls back to median if flat."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return float(np.median(values))
    hist, edges = np.histogram(values, bins=min(256, len(values)))
    centers = (edges[:-1] + edges[1:]) / 2
    p = hist / hist.sum()
    best_thresh, best_var = centers[0], -1.0
    for i in range(1, len(centers)):
        w0, w1 = p[:i].sum(), p[i:].sum()
        if w0 == 0 or w1 == 0:
            continue
        mu0 = (p[:i] * centers[:i]).sum() / w0
        mu1 = (p[i:] * centers[i:]).sum() / w1
        var = w0 * w1 * (mu0 - mu1) ** 2
        if var > best_var:
            best_var, best_thresh = var, centers[i]
    return float(best_thresh)


def plot_dlx_identity_overlay(R, fov_dir, output_path, img_shape=(160, 800)):
    """DLX (yellow) image background + circles colored by consensus cell identity. No arrows."""
    meta = R["meta"]
    nt_df = R["neuron_tier"]
    fov = R["fov"]

    all_traces = sorted(nt_df["trace"].astype(int).tolist())
    centroids = _resolve_centroids(meta, all_traces)
    if not centroids:
        print(f"  [{fov}] no centroids — skipping")
        return

    dlx_path = os.path.join(fov_dir, f"SupplementalImages_RCaMP_{fov}_enhanced.png")
    if not os.path.exists(dlx_path):
        print(f"  [{fov}] SupplementalImages_RCaMP not found — skipping")
        return
    gray = None
    img = plt.imread(dlx_path)
    if img.ndim >= 3:
        rgb = img[..., :3]
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    else:
        gray = img.astype(float)

    img_shape = (gray.shape[0], gray.shape[1])  # (rows, cols) = (height, width)

    neuron_type = {}
    for _, row in nt_df.iterrows():
        tid = int(row["trace"])
        ct = str(row.get("consensus_type", ""))
        if "exc" in ct:
            neuron_type[tid] = "exc"
        elif "inh" in ct:
            neuron_type[tid] = "inh"
        else:
            neuron_type[tid] = "no_valid_outgoing_connections"

    src = R.get("scs1") or R.get("sta1")
    aps_all = {}

    fig, ax = plt.subplots(figsize=(14, 14 * img_shape[0] / img_shape[1]))
    if gray is not None:
        ax.imshow(
            gray,
            cmap="gray",
            extent=[0, img_shape[1], img_shape[0], 0],
            aspect="auto",
            alpha=0.8,
        )
    _plot_spatial_map(
        ax,
        centroids,
        inh_scores_raw={},
        exc_scores_raw={},  # no arrows
        img_shape=img_shape,
        neuron_type=neuron_type,
        aps_all=aps_all,
        title=f"{fov}  —  DLX (GFP) cell identity",
        open_circles=True,
        show_labels=False,
        skip_no_connection=True,
    )
    ax.set_aspect("equal")
    fig.patch.set_facecolor("none")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="none")
    plt.close()


def build_dlx_accuracy_df(all_fov_results, input_dir, window=5, window_neg=None,
    thresh_pct=30, thresh_pct_neg=None):
    """
    Per-FOV DLX accuracy: Otsu threshold on window-mean brightness → DLX+/−.
    DLX+ = predicted INH. Compares against pipeline EXC/INH classification.
    Returns (df_per_fov, df_summary).
    """
    half = window // 2
    half_neg = (window_neg // 2) if window_neg is not None else half
    thresh_pct_neg = thresh_pct_neg if thresh_pct_neg is not None else thresh_pct
    EXC_NT = ("confident_exc", "putative_exc")
    INH_NT = ("confident_inh", "putative_inh")

    fov_rows = []
    for R in all_fov_results:
        fov = R["fov"]
        meta = R["meta"]
        nt_df = R["neuron_tier"]
        fov_dir = os.path.join(input_dir.replace("v17_traces", ""), fov)

        dlx_path = os.path.join(fov_dir, f"SupplementalImages_RCaMP_{fov}.png")
        if not os.path.exists(dlx_path):
            print(f"  [{fov}] SupplementalImages_RCaMP not found — skipping")
            continue

        img = plt.imread(dlx_path)
        if img.ndim >= 3:
            rgb = img[..., :3]
            gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        else:
            gray = img.astype(float)
        h, w = gray.shape[:2]

        all_traces = sorted(nt_df["trace"].astype(int).tolist())
        centroids = _resolve_centroids(meta, all_traces)
        if not centroids:
            print(f"  [{fov}] no centroids — skipping")
            continue

        nt_map = {
            int(r["trace"]): str(r["consensus_type"]) for _, r in nt_df.iterrows()
        }

        # (tid, row_idx, col_idx) — note centroids are (cx=col, cy=row)
        clist = [
            (tid, int(round(cy)), int(round(cx))) for tid, (cx, cy) in centroids.items()
        ]

        neuron_info = []
        for tid, ri, ci in clist:
            r0, r1 = ri - half, ri + half + 1
            c0, c1 = ci - half, ci + half + 1
            if r0 < 0 or r1 > h or c0 < 0 or c1 > w:
                neuron_info.append((tid, np.nan, np.nan, True, nt_map.get(tid, "")))
                continue
            overlap = any(
                abs(ri - r2) <= half and abs(ci - c2) <= half
                for tid2, r2, c2 in clist
                if tid2 != tid
            )
            brightness = float(gray[r0:r1, c0:c1].mean())
            if half_neg != half:
                rn0, rn1 = ri - half_neg, ri + half_neg + 1
                cn0, cn1 = ci - half_neg, ci + half_neg + 1
                if rn0 < 0 or rn1 > h or cn0 < 0 or cn1 > w:
                    brightness_neg = np.nan
                else:
                    brightness_neg = float(gray[rn0:rn1, cn0:cn1].mean())
            else:
                brightness_neg = brightness
            neuron_info.append((tid, brightness, brightness_neg, overlap, nt_map.get(tid, "")))

        valid_b = np.array([b for _, b, _bn, ov, _ in neuron_info if not ov and not np.isnan(b)])
        
        if len(valid_b) < 2:
            print(f"  [{fov}] too few valid neurons for Otsu")
            continue
        thresh = float(np.percentile(valid_b, 30)) # reduce from 50 for weak DLX signal
        thresh_neg = float(np.percentile(valid_b, thresh_pct_neg)) # different thresh for DLX-

        tp = tn = fp = fn = n_overlap = n_boundary = 0
        for tid, brightness, brightness_neg, overlap, ct in neuron_info:
            if np.isnan(brightness):
                n_boundary += 1
                continue
            if overlap:
                n_overlap += 1
                continue
            if ct not in EXC_NT + INH_NT:
                continue
            dlx_pos     = brightness     >= thresh      # INH prediction
            dlx_pos_neg = brightness_neg >= thresh_neg  # used for EXC prediction
            true_inh = ct in INH_NT
            if true_inh and dlx_pos:         tp += 1
            elif not true_inh and not dlx_pos_neg: tn += 1
            elif true_inh and not dlx_pos:   fn += 1
            else:                            fp += 1

        n_total = tp + tn + fp + fn
        fov_rows.append(
            {
                "fov": fov,
                "threshold": round(thresh, 4),
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "n_total": n_total,
                "n_overlap": n_overlap,
                "n_boundary": n_boundary,
                "pct_inh_correct": round(tp / (tp + fn) * 100, 1) if (tp + fn) > 0 else np.nan,
                "pct_exc_correct": round(tn / (tn + fp) * 100, 1) if (tn + fp) > 0 else np.nan,
            }
        )

    df_fov = pd.DataFrame(fov_rows)

    summary_rows = []
    for col, label in (
        ("pct_inh_correct", "INH correctly classified as DLX+ (%)"),
        ("pct_exc_correct", "EXC correctly classified as DLX− (%)"),
        ("n_overlap",       "Neurons excluded — overlap"),
        ("n_total",         "Neurons in accuracy analysis"),
    ):
        s = df_fov[col].dropna()
        n = len(s)
        summary_rows.append(
            {
                "Metric": label,
                "Mean": round(s.mean(), 3) if n else np.nan,
                "SEM": round(s.std(ddof=1) / np.sqrt(n), 3) if n > 1 else np.nan,
                "n (FOVs)": n,
            }
        )
    df_summary = pd.DataFrame(summary_rows)
    return df_fov, df_summary

def classify_dlx_positive(
    stim_meta: dict,
    all_traces,
    fov_dir: Optional[str] = None,
    fov: Optional[str] = None,
    dlx_image_path: Optional[str] = None,
    window: int = 5,
    thresh_pct: float = 30.0,
) -> Dict[int, bool]:
    """
    Classify each neuron as DLX+ (inhibitory) or DLX- by sampling the
    SupplementalImages_RCaMP image at each neuron's centroid.

    Threshold is the `thresh_pct` percentile of in-bounds neuron brightnesses
    (default 30 — same as build_dlx_accuracy_df).

    Parameters
    ----------
    stim_meta      : dict from load_stim_meta, must carry source_centroid_row/col.
    all_traces     : list of 1-indexed trace IDs.
    fov_dir        : directory containing SupplementalImages_RCaMP_{fov}.png.
    fov            : FOV name string used to construct the default image path.
    dlx_image_path : explicit path that overrides fov_dir + fov convention.
    window         : pixel half-window for brightness sampling.
    thresh_pct     : percentile of all valid brightnesses used as the cutoff.

    Returns {trace_id: bool} — True = DLX+ (inhibitory).
    """
    if dlx_image_path is None:
        if fov_dir is None or fov is None:
            print("classify_dlx_positive: provide fov_dir + fov, or dlx_image_path.")
            return {int(t): False for t in all_traces}
        dlx_image_path = os.path.join(fov_dir, f"SupplementalImages_RCaMP_{fov}.png")
    if not os.path.exists(dlx_image_path):
        print(f"classify_dlx_positive: image not found — {dlx_image_path}")
        return {int(t): False for t in all_traces}

    img = plt.imread(dlx_image_path).astype(float)
    if img.ndim >= 3:
        img = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
    h, w = img.shape
    half = window // 2

    centroids = _resolve_centroids(stim_meta, list(all_traces))
    brightnesses: Dict[int, float] = {}
    for t in all_traces:
        tid = int(t)
        if tid not in centroids:
            continue
        cx, cy = centroids[tid]
        ri, ci = int(round(cy)), int(round(cx))
        r0, r1 = ri - half, ri + half + 1
        c0, c1 = ci - half, ci + half + 1
        if r0 < 0 or r1 > h or c0 < 0 or c1 > w:
            continue
        brightnesses[tid] = float(img[r0:r1, c0:c1].mean())

    if not brightnesses:
        print("classify_dlx_positive: no centroids fell within image bounds.")
        return {int(t): False for t in all_traces}

    thresh = float(np.percentile(list(brightnesses.values()), thresh_pct))
    print(f"  DLX  {os.path.basename(dlx_image_path)}  "
          f"shape={img.shape}  {thresh_pct}th-pct thr={thresh:.4f}  "
          f"n_neurons={len(brightnesses)}")

    return {int(t): bool(brightnesses.get(int(t), -1.0) >= thresh) for t in all_traces}


def plot_stim_dlx_summary(
    in_stim_mask: Dict[int, bool],
    dlx_positive: Dict[int, bool],
    title: str = "Stimulated neurons: DLX+ vs DLX-",
    output_path: Optional[str] = None,
) -> dict:
    """
    Print and plot how many stimulated neurons are DLX+ (inhibitory) vs DLX-.

    Parameters
    ----------
    in_stim_mask : {trace_id: bool} — True = neuron was in the DMD stim mask.
    dlx_positive : {trace_id: bool} — from classify_dlx_positive.

    Returns {'stim_total': int, 'dlx_pos': int, 'dlx_neg': int}.
    """
    stim_ids = [t for t, v in in_stim_mask.items() if v]
    n_dlx_pos = sum(1 for t in stim_ids if dlx_positive.get(t, False))
    n_dlx_neg = len(stim_ids) - n_dlx_pos

    print(f"\n{title}")
    print(f"  Stimulated neurons total : {len(stim_ids)}")
    print(f"  DLX+ (inhibitory)        : {n_dlx_pos}")
    print(f"  DLX- (not inhibitory)    : {n_dlx_neg}")

    fig, ax = plt.subplots(figsize=(4, 4))
    bars = ax.bar(
        ["DLX+\n(inhibitory)", "DLX-\n(not inhibitory)"],
        [n_dlx_pos, n_dlx_neg],
        color=[_INH, _EXC],
        edgecolor="white",
        width=0.5,
    )
    for bar, v in zip(bars, [n_dlx_pos, n_dlx_neg]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.1,
            str(v),
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=12,
        )
    ax.set_ylabel("Number of stimulated neurons")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {output_path}")
    if plt.isinteractive():
        plt.show()
    else:
        plt.close()

    return {"stim_total": len(stim_ids), "dlx_pos": n_dlx_pos, "dlx_neg": n_dlx_neg}


def plot_stim_neurons_on_gfp(R, fov_dir, output_path=None, radius=6, bg_path=None):
    """
    Overlay every stimulated neuron on a background FOV image as an open circle,
    coloured by image-based DLX identity (not connection classification).

    Red    = DLX+ (inhibitory)
    Purple = DLX- (excitatory)
    Legend is placed below and outside the axes.

    bg_path : explicit path to background image; defaults to SupplementalImages_GFP_{fov}.png.
              Pass SupplementalImages_RCaMP_{fov}.png (or _enhanced) for the QUASR image.
    """
    fov          = R["fov"]
    meta         = R["meta"]
    in_stim_mask = R["sta1"]["in_stim_mask"] if R.get("sta1") else {}
    dlx_positive = R.get("dlx_positive", {})

    stim_ids = sorted(t for t, v in in_stim_mask.items() if v)
    if not stim_ids:
        print(f"[{fov}] no stim-mask neurons — skipping")
        return None

    centroids = _resolve_centroids(meta, stim_ids)

    # Default to GFP supplemental image; caller can override with QUASR or any FOV image
    img_path = bg_path if bg_path is not None else os.path.join(fov_dir, f"SupplementalImages_GFP_{fov}.png")
    if not os.path.exists(img_path):
        print(f"[{fov}] background image not found — {img_path}")
        return None

    img = plt.imread(img_path)
    if img.ndim >= 3:
        rgb  = img[..., :3]
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    else:
        gray = img.astype(float)

    # Centroid coordinates are in camera pixel space (160 × 800).
    # Scale to actual image dimensions in case the PNG was saved at a different resolution.
    img_h, img_w = gray.shape[:2]
    scale_x = img_w / 800
    scale_y = img_h / 160

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.imshow(gray, cmap="gray", aspect="auto")

    seen: dict = {}
    for tid in stim_ids:
        if tid not in centroids:
            continue
        cx, cy   = centroids[tid][0] * scale_x, centroids[tid][1] * scale_y
        is_inh   = dlx_positive.get(tid, None)
        if is_inh is True:
            color, label = _INH, "DLX+ (inhibitory)"
        elif is_inh is False:
            color, label = _EXC, "DLX− (excitatory)"
        else:
            color, label = "gray", "Unclassified"
        ax.add_patch(Circle((cx, cy), radius=radius * scale_x, fill=False,
                            edgecolor=color, linewidth=1.5))
        off = radius * scale_x * 1.4             # leader-line length — just outside the circle edge
        ax.annotate(
            str(tid),
            xy=(cx, cy),                         # line anchors at circle centre
            xytext=(cx + off, cy - off),         # label sits upper-right of circle
            color=color, fontsize=5, fontweight="bold",
            ha="left", va="bottom",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.7),
            clip_on=True,
        )
        seen[label] = color

    bg_label = os.path.basename(img_path).replace(".png", "")  # e.g. SupplementalImages_GFP_FOV_0001
    ax.set_title(f"{fov} — stimulated neurons  (n={len(stim_ids)})  [{bg_label}]")
    ax.axis("off")

    legend_order = ["DLX+ (inhibitory)", "DLX− (excitatory)", "Unclassified"]
    handles = [
        Patch(facecolor="none", edgecolor=seen[lbl], linewidth=1.5, label=lbl)
        for lbl in legend_order if lbl in seen
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.04), ncol=len(handles),
              frameon=True, fontsize=10)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[{fov}] saved → {output_path}")
    if plt.isinteractive():
        plt.show()
    else:
        plt.close()
    return fig


def plot_stim_vs_spont_connection_fraction(R, output_path=None):
    """
    Stacked bar: exc vs inh validated connections for SCS (spontaneous) and
    STA (stim-driven).  Shows whether DLX stimulation shifts detection toward
    inhibitory connections.
    """
    fov    = R["fov"]
    merged = R.get("merged", pd.DataFrame())
    if merged.empty:
        print(f"[{fov}] no merged connections — skipping")
        return None

    def _counts(col):
        sub = merged[merged[col] == True]
        return int((sub["type"] == "exc").sum()), int((sub["type"] == "inh").sum())

    scs_exc, scs_inh = _counts("scs_validated")
    sta_exc, sta_inh = _counts("sta_validated")

    labels   = ["SCS\n(spont)", "STA\n(stim)"]
    exc_vals = [scs_exc, sta_exc]
    inh_vals = [scs_inh, sta_inh]
    totals   = [e + i for e, i in zip(exc_vals, inh_vals)]

    fig, ax = plt.subplots(figsize=(4, 4))
    x = np.arange(2)
    w = 0.5
    ax.bar(x, exc_vals, width=w, color=_EXC, label="Excitatory")
    ax.bar(x, inh_vals, width=w, bottom=exc_vals, color=_INH, label="Inhibitory")

    for i, (total, inh) in enumerate(zip(totals, inh_vals)):
        pct = 100 * inh / total if total > 0 else 0
        ax.text(x[i], total + 0.3, f"{pct:.0f}% inh\n(n={total})",
                ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Validated connections")
    ax.set_title(f"{fov} — connection type: SCS vs. STA")
    ax.legend(loc="upper right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, (max(totals) if totals else 1) * 1.35)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[{fov}] saved → {output_path}")
    if plt.isinteractive():
        plt.show()
    else:
        plt.close()
    return fig


def plot_dlx_enrichment_in_inh_connections(R, output_path=None):
    """
    Compare DLX+ fraction in (a) the full stim mask vs (b) the unique
    pre-neurons of validated STA inh connections.  Enrichment in (b) links
    the DLX targeting protocol to inhibitory connection detection.
    """
    fov          = R["fov"]
    merged       = R.get("merged", pd.DataFrame())
    in_stim_mask = R["sta1"]["in_stim_mask"] if R.get("sta1") else {}
    dlx_positive = R.get("dlx_positive", {})

    stim_ids = [t for t, v in in_stim_mask.items() if v]
    if not stim_ids:
        print(f"[{fov}] no stim neurons — skipping")
        return None

    def _dlx_counts(ids):
        pos = sum(1 for t in ids if dlx_positive.get(t) is True)
        neg = sum(1 for t in ids if dlx_positive.get(t) is False)
        unk = len(list(ids)) - pos - neg
        return pos, neg, unk

    s_pos, s_neg, s_unk = _dlx_counts(stim_ids)

    if not merged.empty:
        inh_pres = set(
            merged[(merged["sta_validated"] == True) & (merged["type"] == "inh")]
            ["pre"].astype(int)
        )
    else:
        inh_pres = set()

    i_pos, i_neg, i_unk = _dlx_counts(inh_pres)

    fig, ax = plt.subplots(figsize=(4, 4))
    x = np.arange(2)
    w = 0.5
    pos_vals = [s_pos, i_pos]
    neg_vals = [s_neg, i_neg]
    unk_vals = [s_unk, i_unk]
    ax.bar(x, pos_vals, width=w, color=_INH,  label="DLX+")
    ax.bar(x, neg_vals, width=w, bottom=pos_vals, color=_EXC, label="DLX−")
    ax.bar(x, unk_vals, width=w,
           bottom=[p + n for p, n in zip(pos_vals, neg_vals)],
           color="lightgray", label="Unclassified")

    totals_n = [len(stim_ids), len(inh_pres)]
    for i, (pos, neg, n) in enumerate(zip(pos_vals, neg_vals, totals_n)):
        known = pos + neg
        pct   = 100 * pos / known if known > 0 else 0
        ax.text(x[i], n + 0.3, f"{pct:.0f}% DLX+\n(n={n})",
                ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(["Stim mask", "STA inh\npre-neurons"], fontsize=11)
    ax.set_ylabel("Neuron count")
    ax.set_title(f"{fov} — DLX+ enrichment in STA inh pre-neurons")
    ax.legend(loc="upper right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, (max(totals_n) if totals_n else 1) * 1.35)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[{fov}] saved → {output_path}")
    if plt.isinteractive():
        plt.show()
    else:
        plt.close()
    return fig


def plot_inh_yield_by_dlx(R, output_path=None):
    """
    For each stim neuron: count validated STA inh outgoing connections.
    Strip-plot (jitter + median bar) split by DLX identity.  Shows whether
    DLX+ neurons drive more inhibitory connections than DLX- neurons.
    """
    fov          = R["fov"]
    merged       = R.get("merged", pd.DataFrame())
    in_stim_mask = R["sta1"]["in_stim_mask"] if R.get("sta1") else {}
    dlx_positive = R.get("dlx_positive", {})

    stim_ids = [t for t, v in in_stim_mask.items() if v]
    if not stim_ids:
        print(f"[{fov}] no stim neurons — skipping")
        return None

    if not merged.empty:
        inh_rows   = merged[(merged["sta_validated"] == True) & (merged["type"] == "inh")]
        inh_counts = inh_rows.groupby("pre").size().to_dict()  # pre_id → n inh connections
    else:
        inh_counts = {}

    rows = [
        {"group": "DLX+" if dlx_positive.get(t) is True else "DLX−",
         "inh_conns": inh_counts.get(t, 0)}
        for t in stim_ids
        if dlx_positive.get(t) is not None        # skip unclassified
    ]
    if not rows:
        print(f"[{fov}] no DLX-classified stim neurons — skipping")
        return None

    df    = pd.DataFrame(rows)
    order  = ["DLX+", "DLX−"]
    colors = {"DLX+": _INH, "DLX−": _EXC}
    rng    = np.random.default_rng(42)              # fixed seed for reproducible jitter

    fig, ax = plt.subplots(figsize=(4, 4))
    for i, grp in enumerate(order):
        vals = df[df["group"] == grp]["inh_conns"].values
        if len(vals) == 0:
            continue
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals,
                   color=colors[grp], alpha=0.7, s=40, zorder=3)
        med = np.median(vals)
        ax.plot([i - 0.25, i + 0.25], [med, med],    # median bar
                color=colors[grp], linewidth=2.5, zorder=4)
        n_nonzero = int((vals > 0).sum())
        ax.text(i, vals.max() + 0.15,
                f"n={len(vals)}\n{n_nonzero} with ≥1",  # total n and n with any inh conns
                ha="center", va="bottom", fontsize=8)

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, fontsize=12)
    ax.set_ylabel("STA inh connections (as pre-neuron)")
    ax.set_title(f"{fov} — inhibitory yield: DLX+ vs DLX−")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(-0.6, len(order) - 0.4)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[{fov}] saved → {output_path}")
    if plt.isinteractive():
        plt.show()
    else:
        plt.close()
    return fig


def plot_gfp_identity_overlay(R, fov_dir, output_path):
    meta = R["meta"]
    nt_df = R["neuron_tier"]
    fov = R["fov"]

    all_traces = sorted(nt_df["trace"].astype(int).tolist())
    centroids = _resolve_centroids(meta, all_traces)
    if not centroids:
        print(f"  [{fov}] no centroids — skipping")
        return

    gfp_path = os.path.join(fov_dir, f"SupplementalImages_GFP_{fov}.png")
    if not os.path.exists(gfp_path):
        print(f"  [{fov}] SupplementalImages_GFP not found — skipping")
        return

    img = plt.imread(gfp_path)
    if img.ndim >= 3:
        rgb = img[..., :3]
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    else:
        gray = img.astype(float)

    img_shape = (gray.shape[0], gray.shape[1])  # (rows, cols) = (height, width)

    neuron_type = {}
    for _, row in nt_df.iterrows():
        tid = int(row["trace"])
        ct = str(row.get("consensus_type", ""))
        if "exc" in ct:
            neuron_type[tid] = "exc"
        elif "inh" in ct:
            neuron_type[tid] = "inh"
        else:
            neuron_type[tid] = "no_valid_outgoing_connections"

    src = R.get("scs1") or R.get("sta1")
    aps_all = {}

    fig, ax = plt.subplots(figsize=(14, 14 * img_shape[0] / img_shape[1]))
    ax.imshow(
        gray,
        cmap="gray",
        extent=[0, img_shape[1], img_shape[0], 0],
        aspect="auto",
        alpha=0.8,
    )
    _plot_spatial_map(
        ax,
        centroids,
        inh_scores_raw={},
        exc_scores_raw={},
        img_shape=img_shape,
        neuron_type=neuron_type,
        aps_all=aps_all,
        title=f"{fov}  —  GFP cell identity",
        open_circles=True,
        show_labels=False,
        skip_no_connection=True,
    )
    ax.set_aspect("equal")
    fig.patch.set_facecolor("none")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="none")
    plt.close()


def _draw_empty_subrow(ax, x0, y0, w, h, label, facecolor):
    """Fallback: grey sub-row with text label when no image is available."""
    ax.add_patch(
        Rectangle(
            (x0, y0),
            w,
            h,
            linewidth=0.5,
            edgecolor="#aaaaaa",
            facecolor=facecolor,
            zorder=2,
        )
    )
    ax.text(
        x0 + 0.5,
        y0 + h / 2,
        label,
        ha="center",
        va="center",
        fontsize=5,
        color="#666666",
    )


def plot_well_quasr(
    all_fov_results,
    base_dir,
    *,
    fov_to_well=None,
    n_plate_rows=8,
    n_plate_cols=12,
    fov_subrows=None,
    preference="quasr",
    output_path=None,
):
    """
    Plate-layout view with quasr/DLX thumbnail images in each well cell.
    Multiple FOVs per well are stacked vertically as sub-rows.

    Parameters
    ----------
    all_fov_results : list of dicts from run_one_fov()
    base_dir        : root directory containing per-FOV subdirectories
    n_plate_rows    : int, plate rows (default 8 for 96-well)
    n_plate_cols    : int, plate cols (default 12 for 96-well)
    fov_subrows     : int or None - if None, inferred from max FOVs per well
    preference      : 'quasr' or 'dlx'
    output_path     : str or None
    """
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes as _inset_axes

    _EMPTY = "#e8e8e8"

    well_fovs = defaultdict(list)

    for R in all_fov_results:
        fov = R["fov"]
        meta = R["meta"]
        savefast = meta.get("savefast", "")
        fov_dir = os.path.join(base_dir, fov)
        img_path = _find_base_image(savefast, fov_dir, preference=preference)

        well = fov_to_well.get(fov) if fov_to_well else None
        if not well:
            print(f"  [warn] no well mapping for fov: {fov}")
            continue
        m = re.match(r"^([A-Ha-h])(\d{1,2})$", str(well).strip())
        if not m:
            print(f"  [warn] cannot parse well id: {well}")
            continue
        row_idx = ord(m.group(1).upper()) - ord("A")
        col_idx = int(m.group(2)) - 1
        fov_label = fov.split("_")[-1] if "_" in fov else fov
        well_fovs[(row_idx, col_idx)].append((fov_label, img_path))

    if fov_subrows is None:
        fov_subrows = max((len(v) for v in well_fovs.values()), default=1)

    cell_w, cell_h = 1.8, 1.8
    fig, ax = plt.subplots(figsize=(n_plate_cols * cell_w, n_plate_rows * cell_h))
    ax.set_xlim(0, n_plate_cols)
    ax.set_ylim(n_plate_rows, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    subrow_h = 1.0 / fov_subrows

    for r in range(n_plate_rows):
        for c in range(n_plate_cols):
            for s in range(fov_subrows):
                ax.add_patch(
                    Rectangle(
                        (c, r + s * subrow_h),
                        1,
                        subrow_h,
                        linewidth=0.5,
                        edgecolor="#aaaaaa",
                        facecolor=_EMPTY,
                        zorder=1,
                    )
                )

    for (row_idx, col_idx), fov_list in well_fovs.items():
        if row_idx >= n_plate_rows or col_idx >= n_plate_cols:
            continue
        for s, (label, img_path) in enumerate(fov_list):
            if s >= fov_subrows:
                break
            x0 = col_idx
            y0 = row_idx + s * subrow_h
            w = 1.0
            h = subrow_h

            if img_path and os.path.isfile(img_path):
                try:
                    img = plt.imread(img_path)
                    axins = ax.inset_axes(
                        [x0, y0, w, h], transform=ax.transData, zorder=2
                    )
                    axins.imshow(
                        img, aspect="auto", interpolation="bilinear", cmap="gray"
                    )
                    axins.axis("off")
                    axins.text(
                        0.5,
                        0.02,
                        label,
                        transform=axins.transAxes,
                        ha="center",
                        va="bottom",
                        fontsize=5,
                        color="white",
                        bbox=dict(facecolor="black", alpha=0.4, pad=1, linewidth=0),
                    )
                except Exception as e:
                    print(f"  [warn] could not load image {img_path}: {e}")
                    _draw_empty_subrow(ax, x0, y0, w, h, label, _EMPTY)
            else:
                _draw_empty_subrow(ax, x0, y0, w, h, label, _EMPTY)

    for r in range(n_plate_rows):
        for c in range(n_plate_cols):
            ax.add_patch(
                Rectangle(
                    (c, r),
                    1,
                    1,
                    linewidth=1.5,
                    edgecolor="#333333",
                    facecolor="none",
                    zorder=3,
                )
            )

    for r in range(n_plate_rows):
        ax.text(
            -0.15,
            r + 0.5,
            chr(ord("A") + r),
            ha="right",
            va="center",
            fontsize=8,
            fontweight="bold",
        )
    for c in range(n_plate_cols):
        ax.text(
            c + 0.5,
            -0.15,
            str(c + 1),
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    title_pref = "Quasr (Red)" if preference == "quasr" else "DLX (Yellow)"
    ax.set_title(f"Plate layout - {title_pref} thumbnails", fontsize=11, pad=10)

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved {output_path}")
    plt.close()


# ============================================================================
# Condition heatmap — per-FOV feature matrix + Cohen's d vs control
# ============================================================================

_CONTROL_LABELS = {'No Drug', 'NoDrug', 'no drug', 'no_drug', 'DMSO', 'dmso', 'control', 'Control', ''}

_PSP_KEYS = ('amplitude', 'auc', 'peak_time_ms', 'onset_delay_ms',
             'rise_time_ms', 'half_width_ms', 'snr', 'decay_time_ms', 'duration_ms')


# Explicit feature order: EXC/INH paired within each biological theme so that
# features expected to change together appear adjacent in heatmaps.
_FEATURE_ORDER = [
    # PSP properties (EXC)
    'psp_amplitude_exc',
    'psp_auc_exc',
    'psp_peak_time_ms_exc',
    'psp_rate_exc_per_neuron',
    'psp_rate_morph_exc_per_neuron',
    'psp_onset_delay_ms_exc',
    'psp_rise_time_ms_exc',
    'psp_decay_time_ms_exc',
    'psp_duration_ms_exc',
    'psp_half_width_ms_exc',
    'psp_snr_exc',
    # PSP properties (INH)
    'psp_amplitude_inh',
    'psp_auc_inh',
    'psp_peak_time_ms_inh',
    'psp_rate_inh_per_neuron',
    'psp_rate_morph_inh_per_neuron',
    'psp_onset_delay_ms_inh',
    'psp_rise_time_ms_inh',
    'psp_decay_time_ms_inh',
    'psp_duration_ms_inh',
    'psp_half_width_ms_inh',
    'psp_snr_inh',
    # Connection properties
    'conn_n_total',
    'conn_density_index',
    'conn_exc_inh_ratio',
    'conn_n_exc',
    'conn_n_exc_per_active_exc',
    'conn_n_inh',
    'conn_n_inh_per_active_inh',
    'conn_n_total_per_neuron',
    'conn_n_total_per_active',
    'conn_mean_per_source',
    'conn_mean_inputs_per_post',
    'conn_pct_hub_sources',
    'conn_n_reciprocal',
    'conn_pct_reciprocal',
    'conn_pct_post_both_input',
    'conn_pct_post_exc_input',
    'conn_pct_post_inh_input',
    'conn_pct_post_no_input',
    'conn_n_e2e',
    'conn_n_e2i',
    'conn_n_i2e',
    'conn_n_i2i',
    # Source properties
    'neuron_n_total',
    'neuron_pct_exc',
    'neuron_pct_inh',
    'nonfiring_neurons_pct',
    'neuron_pct_active',
    'ap_mean_rate_exc',
    'ap_mean_count_exc',
    'ap_mean_rate_inh',
    'ap_mean_count_inh',
    'ap_mean_isi_cv',
    # Discovery properties
    'conn_pct_validated',
    'conn_mean_score_exc',
    'conn_mean_score_inh',
    'dlx_pct_exc_correct',
    'dlx_pct_inh_correct',
    'dlx_threshold',
]

_CAT_PREFIXES = ['psp_', 'ap_', 'neuron_', 'conn_', 'dlx_']

_FEATURE_EXCLUDE = {
    'neuron_pct_confident_exc',
    'neuron_pct_confident_inh',
    'conn_pct_both_methods',
}


def _ordered_features(cols):
    """Order features by biological theme (explicit list); unknowns appended alphabetically."""
    col_set  = set(cols) - _FEATURE_EXCLUDE
    ordered  = [c for c in _FEATURE_ORDER if c in col_set]
    known    = set(_FEATURE_ORDER)
    leftover = sorted(c for c in col_set if c not in known)
    return ordered + leftover


def _sig_stars(p):
    """Return significance stars for a p-value."""
    if p < 0.001: return '***'
    if p < 0.01:  return '**'
    if p < 0.05:  return '*'
    return 'ns'


# Called in the plate comparison notebook.
def _cohens_d(a, b):
    """Cohen's d: (mean_a - mean_b) / pooled SD. NaN if n < 2 in either group."""
    a = np.asarray(a, dtype=float); a = a[~np.isnan(a)]
    b = np.asarray(b, dtype=float); b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled = np.sqrt(((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
                     / (len(a) + len(b) - 2))
    return np.nan if pooled == 0 else float((np.mean(a) - np.mean(b)) / pooled)


# Called in the plate comparison notebook.
def filter_fovs(df_features, max_fov=None, max_fov_per_plate=None, exclude=None, max_per_well=None):
    """
    Return a filtered copy of df_features.

    Parameters
    ----------
    max_fov : int, optional
        Drop FOVs whose numeric ID exceeds this value globally.
    max_fov_per_plate : int, optional
        Drop FOVs whose numeric ID exceeds this value within each plate.
    exclude : list, optional
        Explicit fov values to drop (e.g. ['fov_021', 'fov_022']).
    max_per_well : int, optional
        Keep only the first N FOVs per (plate, well) group, sorted by fov.
        Useful when later acquisitions in a well are systematically worse.
    """
    df = df_features.copy()

    if exclude is not None:
        df = df[~df['fov'].isin(exclude)]

    if max_fov is not None:
        fov_col = df['fov']
        if pd.api.types.is_numeric_dtype(fov_col):
            df = df[fov_col <= max_fov]
        else:
            nums = fov_col.astype(str).str.extract(r'(\d+)', expand=False).astype(float)
            df = df[nums <= max_fov]

    if max_fov_per_plate is not None:
        if 'plate' not in df.columns:
            print('filter_fovs: max_fov_per_plate requires a plate column — ignored.')
        else:
            fov_col = df['fov']
            if pd.api.types.is_numeric_dtype(fov_col):
                nums = fov_col
            else:
                nums = fov_col.astype(str).str.extract(r'(\d+)', expand=False).astype(float)
            df = df[nums <= max_fov_per_plate]

    if max_per_well is not None:
        group_cols = [c for c in ('plate', 'well') if c in df.columns]
        if not group_cols:
            print('filter_fovs: max_per_well requires plate/well columns — ignored.')
        else:
            df = (df.sort_values('fov')
                    .groupby(group_cols, group_keys=False)
                    .head(max_per_well))

    n_dropped = len(df_features) - len(df)
    if n_dropped:
        print(f'filter_fovs: dropped {n_dropped} / {len(df_features)} FOVs '
              f'({len(df)} remaining).')
    return df


# Called in the plate comparison notebook.
def pool_conditions(df_features, mapping):
    """
    Rename condition labels so that the same drug across different plates is
    treated as one condition in all downstream plots and tables.

    Parameters
    ----------
    mapping : dict
        Keys are the canonical label to use; values are lists of condition
        strings that should map to it.
        e.g. {'Forskolin': ['Forskolin', 'Forskolin 10uM', 'fsk']}

    Example
    -------
    df_plot = pool_conditions(df_features, {
        'Forskolin': ['Forskolin', 'Forskolin 10uM'],
        'Ketamine':  ['Ketamine', 'KET'],
    })
    """
    df = df_features.copy()
    for canonical, aliases in mapping.items():
        mask = df['condition'].isin(aliases)
        if mask.any():
            df.loc[mask, 'condition'] = canonical
            print(f'pool_conditions: merged {mask.sum()} FOVs → "{canonical}"')
        else:
            print(f'pool_conditions: no FOVs matched aliases for "{canonical}" — check spelling')
    return df


# Called in the plate comparison notebook.
def build_condition_feature_df(all_fov_results, df_dlx_fov=None, hub_threshold=3,
                               pixel_um=4.81):
    """
    Build per-FOV feature matrix for the condition heatmap.

    Extracts per-FOV means for:
      - PSP properties (EXC and INH separately)
      - AP count and rate (EXC and INH neurons separately)
      - Neuron composition (% INH, % EXC, % confident)
      - Connection counts, mean score, % validated, INH:EXC ratio
      - DLX cell-identity accuracy (if df_dlx_fov supplied)

    Condition is read from R['meta'].get('drug1', 'No Drug').
    Returns a DataFrame with one row per FOV.
    """
    rows = []
    for R in all_fov_results:
        fov  = R['fov']
        meta = R.get('meta', {})
        cond = str(meta.get('drug1', '') or '').strip()
        if not cond or cond in _CONTROL_LABELS:
            cond = 'No Drug'

        row = {'fov': fov, 'condition': cond}

        # Pool APs and recording time from both spontaneous halves once —
        # reused by connection normalisation and AP rate/count blocks below.
        aps_pooled: dict = {}
        rec_s_pooled = 0.0
        for _src_key in ('scs1', 'scs2'):
            _src = R.get(_src_key)
            if _src is not None:
                for _t, _aps in _src.get('aps_all', {}).items():
                    if _t in aps_pooled:
                        aps_pooled[_t] = np.concatenate([aps_pooled[_t], np.asarray(_aps)])
                    else:
                        aps_pooled[_t] = np.asarray(_aps)
                rec_s_pooled += sum(e - s for s, e in _src.get('segs', [])) / FS
        rec_s_pooled = rec_s_pooled if rec_s_pooled > 0 else np.nan
        nt_df_early  = R.get('neuron_tier')

        # ── PSP properties ─────────────────────────────────────────────────
        # Shape/timing metrics from ALL detected PSPs (scs1+scs2), not filtered
        # to validated connections — these describe the PSPs themselves.
        _all_wf = compute_all_psp_waveforms(R)
        for typ in ('EXC', 'INH'):
            src = _all_wf.get(typ.lower(), {}).get('props', {})
            for k in _PSP_KEYS:
                row[f'psp_{k}_{typ.lower()}'] = src.get(k, np.nan)

        _snr_vals = [row.get('psp_snr_exc', np.nan), row.get('psp_snr_inh', np.nan)]
        _snr_vals = [v for v in _snr_vals if not np.isnan(v)]
        row['psp_snr_total'] = float(np.mean(_snr_vals)) if _snr_vals else np.nan

        # PSP event rate from spontaneous period only (scs1+scs2)
        for typ, psp_key in (('exc', 'epsps_all'), ('inh', 'ipsps_all')):
            total_events = 0
            total_time   = 0.0
            n_neurons    = 0
            for src_key in ('scs1', 'scs2'):
                src = R.get(src_key)
                if src is not None:
                    total_events += sum(len(v) for v in src.get(psp_key, {}).values())
                    total_time   += sum(e - s for s, e in src.get('segs', [])) / FS
                    if n_neurons == 0:
                        n_neurons = len(src.get('all_traces', []))
            row[f'psp_rate_{typ}'] = total_events / total_time if total_time > 0 else np.nan
            row[f'psp_rate_{typ}_per_neuron'] = (
                total_events / total_time / n_neurons
                if (total_time > 0 and n_neurons > 0) else np.nan
            )

        _r_exc = row.get('psp_rate_exc', np.nan)
        _r_inh = row.get('psp_rate_inh', np.nan)
        row['psp_rate_total'] = (
            np.nansum([_r_exc, _r_inh])
            if not (np.isnan(_r_exc) and np.isnan(_r_inh)) else np.nan
        )

        # PSP morphological event rates (includes extra-FOV sources)
        # Pooled across spontaneous halves (scs1, scs2) and stim period (sta1)
        for typ, morph_key in (('exc', 'epsps_morphological'), ('inh', 'ipsps_morphological')):
            total_events = 0
            total_time   = 0.0
            n_neurons    = 0
            for src_key in ('scs1', 'scs2', 'sta1'):
                src = R.get(src_key)
                if src is not None and morph_key in src:
                    total_events += sum(len(v) for v in src.get(morph_key, {}).values())
                    total_time   += sum(e - s for s, e in src.get('segs', [])) / FS
                    if n_neurons == 0:
                        n_neurons = len(src.get('all_traces', []))
            row[f'psp_rate_morph_{typ}'] = (
                total_events / total_time if total_time > 0 else np.nan
            )
            row[f'psp_rate_morph_{typ}_per_neuron'] = (
                total_events / total_time / n_neurons
                if (total_time > 0 and n_neurons > 0) else np.nan
            )

        _rm_exc = row.get('psp_rate_morph_exc', np.nan)
        _rm_inh = row.get('psp_rate_morph_inh', np.nan)
        row['psp_rate_morph_total'] = (
            np.nansum([_rm_exc, _rm_inh])
            if not (np.isnan(_rm_exc) and np.isnan(_rm_inh)) else np.nan
        )

        # ── AP properties ─────────────────────────────────────────────────
        nt_df = nt_df_early
        if aps_pooled and nt_df is not None:
            rec_s  = rec_s_pooled
            nt_map = {}
            for _, nr in nt_df.iterrows():
                ct = str(nr.get('consensus_type', ''))
                if 'exc' in ct:   nt_map[int(nr['trace'])] = 'exc'
                elif 'inh' in ct: nt_map[int(nr['trace'])] = 'inh'
            for typ in ('exc', 'inh'):
                tids   = [t for t, nt in nt_map.items() if nt == typ]
                counts = [len(aps_pooled.get(t, [])) for t in tids] if tids else []
                row[f'ap_mean_count_{typ}'] = float(np.mean(counts)) if counts else np.nan
                firing = [c for c in counts if c > 0]
                row[f'ap_mean_rate_{typ}']  = float(np.mean(firing) / rec_s) if (firing and not np.isnan(rec_s)) else np.nan
            # Silent neuron fraction
            _n_all = len(nt_df)
            _n_act = sum(1 for t in nt_df['trace'].astype(int) if len(aps_pooled.get(t, [])) > 0)
            row['nonfiring_neurons_pct'] = 100 * (_n_all - _n_act) / _n_all if _n_all > 0 else np.nan
            row['neuron_pct_active']     = 100 * _n_act / _n_all if _n_all > 0 else np.nan
            # Neurons with PSPs detected (as postsynaptic), split by whether they also spike
            _has_psp = set()
            for _src_key in ('scs1', 'scs2'):
                _src = R.get(_src_key)
                if _src is not None:
                    for _psp_key in ('epsps_all', 'ipsps_all'):
                        for _tid, _evts in _src.get(_psp_key, {}).items():
                            if len(_evts) > 0:
                                _has_psp.add(_tid)
            _n_psp_spike    = sum(1 for t in _has_psp if len(aps_pooled.get(t, [])) > 0)
            _n_psp_no_spike = len(_has_psp) - _n_psp_spike
            row['neuron_pct_psp_and_spike'] = 100 * _n_psp_spike    / _n_all if _n_all > 0 else np.nan
            row['neuron_pct_psp_no_spike']  = 100 * _n_psp_no_spike / _n_all if _n_all > 0 else np.nan
            # ISI CV — uses the same pooled APs
            _cvs = []
            for _ap_list in aps_pooled.values():
                if len(_ap_list) >= 3:
                    _isis = np.diff(np.sort(_ap_list))
                    _mu = float(np.mean(_isis))
                    if _mu > 0:
                        _cv = float(np.std(_isis, ddof=1) / _mu)
                        if np.isfinite(_cv):
                            _cvs.append(_cv)
            row['ap_mean_isi_cv'] = float(np.mean(_cvs)) if _cvs else np.nan
        else:
            for typ in ('exc', 'inh'):
                row[f'ap_mean_count_{typ}'] = np.nan
                row[f'ap_mean_rate_{typ}']  = np.nan
            row['nonfiring_neurons_pct']    = np.nan
            row['neuron_pct_active']        = np.nan
            row['ap_mean_isi_cv']           = np.nan
            row['neuron_pct_psp_and_spike'] = np.nan
            row['neuron_pct_psp_no_spike']  = np.nan
            for _typ in ('exc', 'inh'):
                row[f'psp_rate_morph_{_typ}']            = np.nan
                row[f'psp_rate_morph_{_typ}_per_neuron'] = np.nan
            row['psp_rate_morph_total'] = np.nan

        # ── Neuron composition ────────────────────────────────────────────
        if nt_df is not None:
            n   = len(nt_df)
            cts = nt_df['consensus_type'].astype(str)
            row['neuron_n_total']          = n
            row['neuron_pct_inh']          = 100 * cts.str.contains('inh').sum() / n if n else np.nan
            row['neuron_pct_exc']          = 100 * cts.str.contains('exc').sum() / n if n else np.nan
            row['neuron_pct_confident_inh'] = 100 * cts.str.fullmatch('confident_inh').sum() / n if n else np.nan
            row['neuron_pct_confident_exc'] = 100 * cts.str.fullmatch('confident_exc').sum() / n if n else np.nan
        else:
            for k in ('neuron_n_total', 'neuron_pct_inh', 'neuron_pct_exc',
                      'neuron_pct_confident_inh', 'neuron_pct_confident_exc'):
                row[k] = np.nan

        # ── Spatial distances (microns) ───────────────────────────────────
        c_rows = np.asarray(meta.get('source_centroid_row', []), dtype=float)
        c_cols = np.asarray(meta.get('source_centroid_col', []), dtype=float)
        if len(c_rows) > 0 and nt_df is not None:
            def _coords(ids):
                pts = []
                for tid in ids:
                    idx = tid - 1
                    if idx < len(c_rows) and np.isfinite(c_rows[idx]) and np.isfinite(c_cols[idx]):
                        pts.append((c_rows[idx], c_cols[idx]))
                return np.array(pts) if pts else np.empty((0, 2))

            def _mean_dist_um(a, b, same=False):
                if len(a) == 0 or len(b) == 0:
                    return np.nan
                if same:
                    if len(a) < 2:
                        return np.nan
                    dists = [np.hypot(a[i, 0] - a[j, 0], a[i, 1] - a[j, 1])
                             for i in range(len(a)) for j in range(i + 1, len(a))]
                else:
                    dists = [np.hypot(r[0] - c[0], r[1] - c[1]) for r in a for c in b]
                return float(np.mean(dists) * pixel_um) if dists else np.nan

            cts  = nt_df['consensus_type'].astype(str)
            tids = nt_df['trace'].astype(int)
            exc_pts = _coords([t for t, ct in zip(tids, cts) if 'exc' in ct])
            inh_pts = _coords([t for t, ct in zip(tids, cts) if 'inh' in ct])
            row['dist_mean_ee_um'] = _mean_dist_um(exc_pts, exc_pts, same=True)
            row['dist_mean_ii_um'] = _mean_dist_um(inh_pts, inh_pts, same=True)
            row['dist_mean_ei_um'] = _mean_dist_um(exc_pts, inh_pts)
        else:
            for k in ('dist_mean_ee_um', 'dist_mean_ii_um', 'dist_mean_ei_um'):
                row[k] = np.nan

        # ── Connection properties ─────────────────────────────────────────
        merged = R.get('merged')
        if merged is not None and not merged.empty:
            val = merged[merged['consensus_tier'].isin({'both', 'scs_only', 'sta_only'})]
            for typ, label in (('INH', 'inh'), ('EXC', 'exc')):
                sub    = val[val['type'].str.upper() == typ]
                scores = pd.concat([sub[c].dropna() for c in ('scs_score_p1', 'sta_score_p1') if c in sub.columns])
                row[f'conn_n_{label}']          = len(sub)
                row[f'conn_mean_score_{label}'] = float(scores.mean()) if len(scores) else np.nan
            row['conn_n_total']        = len(val)
            row['conn_pct_validated']  = 100 * len(val) / len(merged) if len(merged) else np.nan
            n_exc = row.get('conn_n_exc', 0) or 0
            n_inh = row.get('conn_n_inh', 0) or 0
            row['conn_exc_inh_ratio']  = (n_exc + 0.5) / (n_inh + 0.5) if (n_exc + n_inh) > 0 else np.nan
            # Divergence: mean validated outputs per source neuron (how broadly each neuron broadcasts)
            _source_counts = val.groupby('pre').size() if len(val) else pd.Series([], dtype=int)
            row['conn_mean_per_source']   = float(_source_counts.mean()) if len(_source_counts) else np.nan
            row['conn_pct_hub_sources']   = 100 * (_source_counts > hub_threshold).sum() / len(_source_counts) if len(_source_counts) else np.nan
            post_exc = set(val.loc[val['type'].str.upper() == 'EXC', 'post'].unique())
            post_inh = set(val.loc[val['type'].str.upper() == 'INH', 'post'].unique())
            row['conn_n_post_exc_input']  = len(post_exc)
            row['conn_n_post_inh_input']  = len(post_inh)
            row['conn_n_post_both_input'] = len(post_exc & post_inh)
            if nt_df is not None:
                all_neurons = set(nt_df['trace'].astype(int))
                row['conn_n_post_no_input'] = len(all_neurons - (post_exc | post_inh))
            else:
                row['conn_n_post_no_input'] = np.nan
            # Normalize post-synaptic counts by total neuron count
            n_tot_neurons = float(row.get('neuron_n_total') or np.nan)
            if np.isfinite(n_tot_neurons) and n_tot_neurons > 0:
                row['conn_n_total_per_neuron']  = row['conn_n_total'] / n_tot_neurons
                row['conn_pct_post_exc_input']  = 100 * row['conn_n_post_exc_input']  / n_tot_neurons
                row['conn_pct_post_inh_input']  = 100 * row['conn_n_post_inh_input']  / n_tot_neurons
                row['conn_pct_post_both_input'] = 100 * row['conn_n_post_both_input'] / n_tot_neurons
                _no = row['conn_n_post_no_input']
                row['conn_pct_post_no_input']   = 100 * _no / n_tot_neurons if pd.notna(_no) else np.nan
            else:
                for k in ('conn_n_total_per_neuron', 'conn_pct_post_exc_input',
                          'conn_pct_post_inh_input', 'conn_pct_post_both_input',
                          'conn_pct_post_no_input'):
                    row[k] = np.nan
            # Normalize connection counts by active neuron count
            if aps_pooled and nt_df_early is not None:
                _cts  = nt_df_early['consensus_type'].astype(str)
                _tids = nt_df_early['trace'].astype(int)
                n_act_exc = sum(len(aps_pooled.get(t, [])) > 0 for t, ct in zip(_tids, _cts) if 'exc' in ct)
                n_act_inh = sum(len(aps_pooled.get(t, [])) > 0 for t, ct in zip(_tids, _cts) if 'inh' in ct)
                n_act = n_act_exc + n_act_inh
                row['conn_n_total_per_active']   = row['conn_n_total'] / n_act     if n_act     > 0 else np.nan
                row['conn_n_exc_per_active_exc'] = row['conn_n_exc']   / n_act_exc if n_act_exc > 0 else np.nan
                row['conn_n_inh_per_active_inh'] = row['conn_n_inh']   / n_act_inh if n_act_inh > 0 else np.nan
            else:
                for k in ('conn_n_total_per_active', 'conn_n_exc_per_active_exc',
                          'conn_n_inh_per_active_inh'):
                    row[k] = np.nan
            # Dual-method validation rate
            row['conn_pct_both_methods'] = 100 * (val['consensus_tier'] == 'both').sum() / len(val) if len(val) else np.nan
            # Convergence: mean validated inputs per receiving neuron (how many sources drive each target)
            row['conn_mean_inputs_per_post'] = float(val.groupby('post').size().mean()) if len(val) else np.nan
            # Reciprocal connections
            _directed = set(zip(val['pre'].astype(int), val['post'].astype(int)))
            _recip = sum(1 for (a, b) in _directed if (b, a) in _directed)
            row['conn_n_reciprocal']   = _recip // 2
            row['conn_pct_reciprocal'] = 100 * _recip / len(_directed) if _directed else np.nan
            # Network density: validated connections / max possible directed connections
            _n = float(row.get('neuron_n_total') or np.nan)
            row['conn_density_index'] = row['conn_n_total'] / (_n * (_n - 1)) if (np.isfinite(_n) and _n > 1) else np.nan
            # E→E, E→I, I→E, I→I breakdown
            if nt_df is not None:
                _post_type = {}
                for _, _nr in nt_df.iterrows():
                    _ct = str(_nr.get('consensus_type', ''))
                    if 'exc' in _ct:   _post_type[int(_nr['trace'])] = 'exc'
                    elif 'inh' in _ct: _post_type[int(_nr['trace'])] = 'inh'
                for _pre_t, _post_t, _key in [
                    ('EXC', 'exc', 'conn_n_e2e'), ('EXC', 'inh', 'conn_n_e2i'),
                    ('INH', 'exc', 'conn_n_i2e'), ('INH', 'inh', 'conn_n_i2i'),
                ]:
                    _sub = val[val['type'].str.upper() == _pre_t]
                    row[_key] = int((_sub['post'].map(_post_type) == _post_t).sum())
                _n_conn_total = row.get('conn_n_total', 0) or 0
                for _k in ('conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i'):
                    _pct_k = _k.replace('conn_n_', 'conn_pct_')
                    row[_pct_k] = 100 * row[_k] / _n_conn_total if _n_conn_total > 0 else np.nan
            else:
                for k in ('conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i',
                          'conn_pct_e2e', 'conn_pct_e2i', 'conn_pct_i2e', 'conn_pct_i2i'):
                    row[k] = np.nan
        else:
            for k in ('conn_n_inh', 'conn_n_exc', 'conn_n_total',
                      'conn_mean_score_inh', 'conn_mean_score_exc',
                      'conn_pct_validated', 'conn_exc_inh_ratio',
                      'conn_mean_per_source', 'conn_n_post_exc_input',
                      'conn_n_post_inh_input', 'conn_n_post_both_input',
                      'conn_n_post_no_input', 'conn_n_total_per_neuron',
                      'conn_pct_post_exc_input', 'conn_pct_post_inh_input',
                      'conn_pct_post_both_input', 'conn_pct_post_no_input',
                      'conn_n_total_per_active', 'conn_n_exc_per_active_exc',
                      'conn_n_inh_per_active_inh', 'conn_pct_both_methods',
                      'conn_mean_inputs_per_post', 'conn_n_reciprocal',
                      'conn_pct_reciprocal', 'conn_density_index',
                      'conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i',
                      'conn_pct_e2e', 'conn_pct_e2i', 'conn_pct_i2e', 'conn_pct_i2i',
                      'psp_rate_exc_per_neuron', 'psp_rate_inh_per_neuron',
                      'psp_rate_total'):
                row[k] = np.nan

        rows.append(row)

    df = pd.DataFrame(rows)

    # ── DLX cell identity ─────────────────────────────────────────────────
    if df_dlx_fov is not None:
        keep = [c for c in ('fov', 'pct_inh_correct', 'pct_exc_correct', 'threshold') if c in df_dlx_fov.columns]
        df = df.merge(
            df_dlx_fov[keep].rename(columns={
                'pct_inh_correct': 'dlx_pct_inh_correct',
                'pct_exc_correct': 'dlx_pct_exc_correct',
                'threshold':       'dlx_threshold',
            }),
            on='fov', how='left',
        )

    return df


# ============================================================================
# AP feature DataFrame  (Heatmap 3 — AP properties by network role)
# ============================================================================
_AP_SHAPE_KEYS = ('amplitude', 'rise_time_ms', 'half_width_ms', 'width_80_ms',
                  'max_dv_dt', 'min_dv_dt', 'ahp_depth', 'ahp_time_ms', 'snr')
_AP_RATE_KEYS  = ('ap_rate', 'ap_isi_cv')
_AP_ALL_KEYS   = _AP_RATE_KEYS + _AP_SHAPE_KEYS

_AP_CATEGORIES = ('all', 'exc', 'inh',
                  'pre_exc', 'pre_inh', 'post_exc', 'post_inh', 'hub')


def build_ap_feature_df(all_fov_results, hub_threshold: int = 3,
                        min_group: int = 1) -> pd.DataFrame:
    """
    Build per-FOV AP feature matrix broken down by network role.

    Neuron categories
    -----------------
    all       — every neuron with ≥1 detected AP
    exc / inh — by consensus_type
    pre_exc   — pre-neuron in ≥1 validated EXC connection
    pre_inh   — pre-neuron in ≥1 validated INH connection
    post_exc  — post-neuron in ≥1 validated EXC connection
    post_inh  — post-neuron in ≥1 validated INH connection
    hub       — neurons with ≥ hub_threshold validated outputs

    AP features per category (mean across neurons in category)
    ----------------------------------------------------------
    ap_rate, ap_isi_cv,
    amplitude, rise_time_ms, half_width_ms, width_80_ms,
    max_dv_dt, min_dv_dt, ahp_depth, ahp_time_ms, snr

    Groups with fewer than min_group neurons are reported as NaN.
    Column names: <category>_<feature>  e.g. pre_exc_ap_rate
    """
    from .data_utils import mean_ap_shape

    rows = []
    for R in all_fov_results:
        fov    = R['fov']
        scs    = R.get('scs1')
        nt_df  = R.get('neuron_tier')
        merged = R.get('merged')

        row = {'fov': fov}

        if scs is None or nt_df is None:
            for cat in _AP_CATEGORIES:
                for feat in _AP_ALL_KEYS:
                    row[f'{cat}_{feat}'] = np.nan
            rows.append(row)
            continue

        aps_all  = scs.get('aps_all', {})
        raws_all = scs.get('raws_all', {})
        segs     = scs.get('segs', [])
        rec_s    = sum(e - s for s, e in segs) / FS if segs else np.nan

        # Neuron type map from consensus_type
        cts  = nt_df['consensus_type'].astype(str)
        tids = nt_df['trace'].astype(int)
        type_map = {}
        for t, ct in zip(tids, cts):
            if 'exc' in ct:   type_map[t] = 'exc'
            elif 'inh' in ct: type_map[t] = 'inh'

        # Network role sets from validated connections
        val = pd.DataFrame()
        if merged is not None and not merged.empty:
            val = merged[merged['consensus_tier'].isin({'both', 'scs_only', 'sta_only'})]

        pre_exc  = set(val.loc[val['type'].str.upper() == 'EXC', 'pre'].astype(int)) if len(val) else set()
        pre_inh  = set(val.loc[val['type'].str.upper() == 'INH', 'pre'].astype(int)) if len(val) else set()
        post_exc = set(val.loc[val['type'].str.upper() == 'EXC', 'post'].astype(int)) if len(val) else set()
        post_inh = set(val.loc[val['type'].str.upper() == 'INH', 'post'].astype(int)) if len(val) else set()
        hub_counts = val.groupby('pre').size() if len(val) else pd.Series(dtype=int)
        hub_set  = set(hub_counts[hub_counts >= hub_threshold].index.astype(int))

        category_sets = {
            'all':      set(t for t in tids if len(aps_all.get(t, [])) > 0),
            'exc':      set(t for t in tids if type_map.get(t) == 'exc' and len(aps_all.get(t, [])) > 0),
            'inh':      set(t for t in tids if type_map.get(t) == 'inh' and len(aps_all.get(t, [])) > 0),
            'pre_exc':  pre_exc  & set(t for t in tids if len(aps_all.get(t, [])) > 0),
            'pre_inh':  pre_inh  & set(t for t in tids if len(aps_all.get(t, [])) > 0),
            'post_exc': post_exc & set(t for t in tids if len(aps_all.get(t, [])) > 0),
            'post_inh': post_inh & set(t for t in tids if len(aps_all.get(t, [])) > 0),
            'hub':      hub_set  & set(t for t in tids if len(aps_all.get(t, [])) > 0),
        }

        # Per-neuron AP features (memoised — each neuron computed once)
        neuron_cache: dict = {}
        def _neuron_feats(t):
            if t in neuron_cache:
                return neuron_cache[t]
            aps = aps_all.get(t, np.array([], dtype=int))
            raw = raws_all.get(t)
            feats: dict = {}
            # Rate and ISI CV
            feats['ap_rate']   = len(aps) / rec_s if (len(aps) > 0 and np.isfinite(rec_s)) else np.nan
            if len(aps) >= 3:
                isis = np.diff(np.sort(aps))
                mu   = float(np.mean(isis))
                feats['ap_isi_cv'] = float(np.std(isis, ddof=1) / mu) if mu > 0 else np.nan
            else:
                feats['ap_isi_cv'] = np.nan
            # Shape features from raw trace
            if raw is not None and len(aps) > 0:
                shape = mean_ap_shape(raw, aps)
            else:
                shape = {k: np.nan for k in _AP_SHAPE_KEYS}
            feats.update(shape)
            neuron_cache[t] = feats
            return feats

        for cat, neuron_set in category_sets.items():
            if len(neuron_set) < min_group:
                for feat in _AP_ALL_KEYS:
                    row[f'{cat}_{feat}'] = np.nan
                continue
            records = [_neuron_feats(t) for t in neuron_set]
            df_cat  = pd.DataFrame(records)
            for feat in _AP_ALL_KEYS:
                row[f'{cat}_{feat}'] = float(df_cat[feat].mean()) if feat in df_cat else np.nan

        rows.append(row)

    return pd.DataFrame(rows)


def plot_ap_heatmap(df_ap, control_labels=None, output_path=None,
                    condition_order=None):
    """
    Heatmap 3 — AP properties by network role.

    Rows: category × feature (grouped by category).
    Columns: drug conditions (Cohen's d vs control).
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS

    feat_cols = [c for c in df_ap.columns if c != 'fov' and
                 any(c.startswith(cat + '_') for cat in _AP_CATEGORIES)]

    conditions = df_ap['condition'].unique().tolist() if 'condition' in df_ap.columns else []
    if condition_order is not None:
        drug_conditions = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conditions += [c for c in conditions if c not in ctrl_set and c not in drug_conditions]
    else:
        drug_conditions = [c for c in conditions if c not in ctrl_set]

    if not drug_conditions:
        print('plot_ap_heatmap: no drug conditions found.')
        return None

    ctrl_df = df_ap[df_ap['condition'].isin(ctrl_set)]
    data = {
        cond: {feat: _cohens_d(
                   df_ap.loc[df_ap['condition'] == cond, feat].values,
                   ctrl_df[feat].values)
               for feat in feat_cols}
        for cond in drug_conditions
    }
    hm_df = pd.DataFrame(data, index=feat_cols)

    # Role-specific categories first; broad/general ones at the bottom
    _PLOT_CAT_ORDER = ('pre_exc', 'pre_inh', 'post_exc', 'post_inh', 'hub',
                       'all', 'exc', 'inh')
    _PLOT_CAT_LABELS = {
        'pre_exc':  'Pre-syn\n(EXC)',
        'pre_inh':  'Pre-syn\n(INH)',
        'post_exc': 'Post-syn\n(EXC)',
        'post_inh': 'Post-syn\n(INH)',
        'hub':      'Hub\nneurons',
        'all':      'All\nactive',
        'exc':      'EXC\nneurons',
        'inh':      'INH\nneurons',
    }
    ordered = []
    for cat in _PLOT_CAT_ORDER:
        for feat in _AP_ALL_KEYS:
            col = f'{cat}_{feat}'
            if col in hm_df.index:
                ordered.append(col)
    hm_df = hm_df.loc[[c for c in ordered if c in hm_df.index]]

    n_rows, n_cols = hm_df.shape
    fig, ax = plt.subplots(figsize=(max(4, n_cols * 1.5), max(6, n_rows * 0.15)))

    cmap = plt.cm.bwr.copy()
    cmap.set_bad(color='#c0c0c0')
    masked = np.ma.masked_invalid(hm_df.values.astype(float))
    vmax = max(1.0, float(np.nanpercentile(np.abs(masked.compressed()), 95))) if masked.count() else 2.0
    im   = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(hm_df.columns, rotation=0, ha='center', fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(hm_df.index, fontsize=7)

    def _ap_group(col):
        return next((c for c in _AP_CATEGORIES if col.startswith(c + '_')), 'other')

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Cohen's d vs control\n(gray = insufficient group size)", fontsize=8)
    ax.set_title("AP properties by network role", fontsize=11, pad=10)

    plt.tight_layout()
    _add_group_brackets(ax, list(hm_df.index), _ap_group, _PLOT_CAT_LABELS)
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()
    return hm_df


def _add_group_brackets(ax, feat_list, group_fn, label_map,
                        fontsize=7, color='#444444'):
    """
    Draw white dividers between row groups and add rotated group labels
    just to the left of the y-axis tick labels.
    Must be called after plt.tight_layout() for accurate positioning.
    """
    from matplotlib.transforms import blended_transform_factory, offset_copy

    fig = ax.get_figure()

    # Build contiguous groups and draw dividers
    groups, prev_key, start = [], None, 0
    for i, feat in enumerate(feat_list):
        key = group_fn(feat)
        if key != prev_key:
            if prev_key is not None:
                groups.append((start, i, prev_key))
                ax.axhline(i - 0.5, color='white', lw=1.5, zorder=3)
            prev_key, start = key, i
    if prev_key is not None:
        groups.append((start, len(feat_list), prev_key))

    if not groups:
        return

    # Render to get accurate tick-label bounding boxes
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    tick_labels = [t for t in ax.get_yticklabels() if t.get_text().strip()]
    ax_left_disp = ax.transAxes.transform((0, 0))[0]
    if tick_labels:
        leftmost_disp = min(t.get_window_extent(renderer).x0 for t in tick_labels)
        offset_pts = (leftmost_disp - ax_left_disp) * 72.0 / fig.dpi - 4.0
    else:
        offset_pts = -60.0

    base_trans = blended_transform_factory(ax.transAxes, ax.transData)
    line_xfm   = offset_copy(base_trans, fig=fig, x=offset_pts,            y=0, units='points')
    text_xfm   = offset_copy(base_trans, fig=fig, x=offset_pts - fontsize, y=0, units='points')

    for grp_start, grp_end, key in groups:
        mid   = (grp_start + grp_end - 1) / 2.0
        label = label_map.get(key, key)
        ax.plot([0, 0], [grp_start - 0.45, grp_end - 0.55],
                transform=line_xfm, color=color, lw=1.2,
                clip_on=False, solid_capstyle='butt')
        ax.text(0, mid, label,
                transform=text_xfm, ha='center', va='center',
                fontsize=fontsize, color=color,
                rotation=90, rotation_mode='anchor', clip_on=False)


# Called in the plate comparison notebook.
def plot_condition_heatmap(
    df_features,
    control_labels=None,
    output_path=None,
    vmax=None,
    condition_order=None,
):
    ctrl_set  = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    _cond_excl = {'fov', 'condition',
                  'psp_rate_exc', 'psp_rate_inh',
                  'psp_rate_exc_per_neuron', 'psp_rate_inh_per_neuron'}
    feat_cols = [c for c in df_features.select_dtypes(include='number').columns if c not in _cond_excl]
    conditions     = df_features['condition'].unique().tolist()
    if condition_order is not None:
        drug_conditions = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conditions += [c for c in conditions if c not in ctrl_set and c not in drug_conditions]
    else:
        drug_conditions = [c for c in conditions if c not in ctrl_set]

    _zero_fill = {
        'conn_n_exc', 'conn_n_inh', 'conn_n_total',
        'conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i',
        'psp_rate_exc', 'psp_rate_inh',
        'ap_mean_rate_exc', 'ap_mean_rate_inh',
        'ap_mean_count_exc', 'ap_mean_count_inh',
        'conn_n_exc_per_active_exc', 'conn_n_inh_per_active_inh',
    }
    df_features = df_features.copy()
    for col in _zero_fill:
        if col in df_features.columns:
            df_features[col] = df_features[col].fillna(0)

    if drug_conditions:
        ctrl_df = df_features[df_features['condition'].isin(ctrl_set)]
        data = {
            cond: {
                feat: _cohens_d(
                    df_features.loc[df_features['condition'] == cond, feat].values,
                    ctrl_df[feat].values,
                )
                for feat in feat_cols
            }
            for cond in drug_conditions
        }
        hm_df      = pd.DataFrame(data, index=feat_cols).loc[_ordered_features(feat_cols)]
        cbar_label = "Cohen's d (vs control)"
        title      = "Condition heatmap — Cohen's d vs control"
    else:
        # Collapse: z-score per feature, then mean across FOVs per condition
        std = df_features[feat_cols].std(ddof=1)
        z   = (df_features[feat_cols] - df_features[feat_cols].mean()) / std.replace(0, np.nan)
        z['condition'] = df_features['condition'].values
        collapsed = z.groupby('condition')[feat_cols].mean()
        hm_df      = collapsed.T.loc[_ordered_features(feat_cols)]
        cbar_label = 'mean z-score (across FOVs)'
        title      = 'Network Feature heatmap — mean z-score per condition'

    n_rows, n_cols = hm_df.shape
    fig, ax = plt.subplots(figsize=(max(4, n_cols * 1.5), max(6, n_rows * 0.15)))

    cmap = plt.cm.bwr.copy()
    cmap.set_bad(color='#c0c0c0')
    masked = np.ma.masked_invalid(hm_df.values.astype(float))
    if vmax is None:
        vmax = max(1.0, float(np.nanpercentile(np.abs(masked.compressed()), 95))) if masked.count() else 2.0
    im     = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')
    ax.set_xticks(range(n_cols))
    _max_label_len = 14
    _xlabels = [c[:_max_label_len] if len(c) > _max_label_len else c for c in hm_df.columns]
    ax.set_xticklabels(_xlabels, rotation=0, ha='center', fontsize=9)
    ax.set_yticks(range(n_rows))

    _type_color = {
        'exc':     QUIVER_NEURON_COLORS['Excitatory'],
        'inh':     QUIVER_NEURON_COLORS['Inhibitory'],
        'neutral': 'black',
    }

    def _type_group(f):
        if f.startswith('psp_'):
            if f.endswith('_exc'): return 'exc'
            if f.endswith('_inh'): return 'inh'
        return 'neutral'

    ax.set_yticklabels(hm_df.index, fontsize=8)
    for tick, feat in zip(ax.get_yticklabels(), hm_df.index):
        tick.set_color(_type_color[_type_group(feat)])

    for row_i in range(n_rows):
        for col_j in range(n_cols):
            if masked.mask[row_i, col_j]:
                ax.text(col_j, row_i, 'none found', ha='center', va='center',
                        fontsize=4, color='#555555')

    def _cond_group(f):
        if f.startswith('psp_') and f.endswith('_exc'): return 'psp_exc'
        if f.startswith('psp_') and f.endswith('_inh'): return 'psp_inh'
        if (f in ('conn_pct_validated', 'conn_mean_score_exc', 'conn_mean_score_inh')
                or f.startswith('dlx_')): return 'discovery'
        if f.startswith('conn_'):    return 'connectivity'
        if f.startswith('neuron_') or f.startswith('nonfiring_'): return 'neurons'
        if f.startswith('ap_'):      return 'ap'
        return 'other'

    _COND_LABELS = {
        'psp_exc':      'PSP\n(EXC)',
        'psp_inh':      'PSP\n(INH)',
        'connectivity': 'Connectivity',
        'neurons':      'Neurons',
        'ap':           'AP activity',
        'discovery':    'Discovery',
        'other':        'Other',
    }
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label(f"{cbar_label}\n(gray = missing data)", fontsize=9)
    ax.set_title(title, fontsize=11, pad=10)

    plt.tight_layout()
    _add_group_brackets(ax, list(hm_df.index), _cond_group, _COND_LABELS)
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()
    return hm_df


_CONNECTED_AP_CATS = ('pre_exc', 'pre_inh', 'post_exc', 'post_inh', 'hub')


def plot_connected_pair_heatmap(df_features, df_ap,
                                control_labels=None,
                                output_path=None,
                                vmax=None,
                                condition_order=None):
    """
    Cohen's d heatmap for PSP waveform features + AP properties of connected neurons only
    (pre-synaptic, post-synaptic, and hub).

    Rows: psp_* features (EXC then INH) followed by pre/post/hub AP features.
    Columns: drug conditions vs control.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS

    _pair_excl = {'psp_rate_morph_exc', 'psp_rate_morph_inh', 'psp_rate_morph_total',
                  'psp_rate_morph_exc_per_neuron', 'psp_rate_morph_inh_per_neuron'}
    psp_cols = [c for c in _FEATURE_ORDER if c.startswith('psp_')
                and c in df_features.columns and c not in _pair_excl]
    ap_cols  = [f'{cat}_{key}' for cat in _CONNECTED_AP_CATS for key in _AP_ALL_KEYS
                if f'{cat}_{key}' in df_ap.columns]

    merge_keys = [c for c in ('fov', 'condition', 'plate') if c in df_features.columns and c in df_ap.columns]
    merged = df_features[merge_keys + psp_cols].merge(
        df_ap[[c for c in merge_keys if c in df_ap.columns] + ap_cols],
        on=[c for c in merge_keys if c in df_ap.columns],
        how='outer',
    )
    if 'condition' not in merged.columns and 'condition' in df_features.columns:
        merged['condition'] = df_features['condition'].values

    all_feat_cols = psp_cols + ap_cols
    conditions = merged['condition'].unique().tolist()
    if condition_order is not None:
        drug_conds  = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conds += [c for c in conditions if c not in ctrl_set and c not in drug_conds]
    else:
        drug_conds = [c for c in conditions if c not in ctrl_set]

    if not drug_conds:
        print('plot_connected_pair_heatmap: no drug conditions found.')
        return None

    ctrl_df = merged[merged['condition'].isin(ctrl_set)]
    data = {
        cond: {
            feat: _cohens_d(
                merged.loc[merged['condition'] == cond, feat].values,
                ctrl_df[feat].values,
            )
            for feat in all_feat_cols
        }
        for cond in drug_conds
    }
    hm_df = pd.DataFrame(data, index=all_feat_cols)

    ordered_rows = [c for c in psp_cols if c in hm_df.index]
    for cat in _CONNECTED_AP_CATS:
        for key in _AP_ALL_KEYS:
            col = f'{cat}_{key}'
            if col in hm_df.index:
                ordered_rows.append(col)
    hm_df = hm_df.loc[[c for c in ordered_rows if c in hm_df.index]]

    n_rows, n_cols = hm_df.shape
    fig, ax = plt.subplots(figsize=(max(4, n_cols * 1.5), max(6, n_rows * 0.15)))

    cmap = plt.cm.bwr.copy()
    cmap.set_bad(color='#c0c0c0')
    masked = np.ma.masked_invalid(hm_df.values.astype(float))
    if vmax is None:
        vmax = max(1.0, float(np.nanpercentile(np.abs(masked.compressed()), 95))) if masked.count() else 2.0
    im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(hm_df.columns, rotation=0, ha='center', fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(hm_df.index, fontsize=8)

    _type_color = {
        'exc':     QUIVER_NEURON_COLORS['Excitatory'],
        'inh':     QUIVER_NEURON_COLORS['Inhibitory'],
        'neutral': 'black',
    }

    def _row_type(f):
        if f.startswith('psp_'):
            if f.endswith('_exc'): return 'exc'
            if f.endswith('_inh'): return 'inh'
        if any(f.startswith(c + '_') for c in ('pre_exc', 'post_exc')): return 'exc'
        if any(f.startswith(c + '_') for c in ('pre_inh', 'post_inh')): return 'inh'
        return 'neutral'

    for tick, feat in zip(ax.get_yticklabels(), hm_df.index):
        tick.set_color(_type_color[_row_type(feat)])

    def _pair_group(f):
        if f.startswith('psp_') and f.endswith('_exc'): return 'psp_exc'
        if f.startswith('psp_') and f.endswith('_inh'): return 'psp_inh'
        for cat in _CONNECTED_AP_CATS:
            if f.startswith(cat + '_'): return cat
        return 'other'

    _PAIR_LABELS = {
        'psp_exc':  'PSP\n(EXC)',
        'psp_inh':  'PSP\n(INH)',
        'pre_exc':  'Pre-syn\nEXC',
        'pre_inh':  'Pre-syn\nINH',
        'post_exc': 'Post-syn\nEXC',
        'post_inh': 'Post-syn\nINH',
        'hub':      'Hub',
        'other':    'Other',
    }
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Cohen's d (vs control)\n(gray = missing data)", fontsize=9)
    ax.set_title("PSP waveform & connected-neuron AP properties", fontsize=11, pad=10)

    plt.tight_layout()
    _add_group_brackets(ax, list(hm_df.index), _pair_group, _PAIR_LABELS)
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()
    return hm_df


# Called in the plate comparison notebook.
def plot_plate_heatmap(df_features, output_path=None):

    feat_cols = [c for c in df_features.select_dtypes(include='number').columns
                 if c not in ('fov',)]

    std = df_features[feat_cols].std(ddof=1).replace(0, np.nan)
    z = (df_features[feat_cols] - df_features[feat_cols].mean()) / std
    z['plate'] = df_features['plate'].values

    collapsed = z.groupby('plate')[feat_cols].mean()
    hm_df = collapsed.T.loc[_ordered_features(feat_cols)]

    n_rows, n_cols = hm_df.shape
    fig, ax = plt.subplots(figsize=(max(4, n_cols * 1.5), max(6, n_rows * 0.25)))

    masked = np.ma.masked_invalid(hm_df.values.astype(float))
    vmax = np.nanpercentile(np.abs(masked.compressed()), 95) if masked.count() else 2
    im = ax.imshow(masked, cmap='RdBu_r', vmin=-vmax, vmax=vmax, aspect='auto')

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(hm_df.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(hm_df.index, fontsize=8)

    def _plate_group(f):
        if f.startswith('psp_'):
            if 'inh' in f: return 'psp_inh'
            return 'psp_exc'
        if (f in ('conn_pct_validated', 'conn_mean_score_exc', 'conn_mean_score_inh')
                or f.startswith('dlx_')): return 'discovery'
        if f.startswith('conn_'):    return 'connectivity'
        if f.startswith('neuron_') or f.startswith('nonfiring_'): return 'neurons'
        if f.startswith('ap_'):      return 'ap'
        return 'other'

    _PLATE_LABELS = {
        'psp_exc':      'PSP\n(EXC)',
        'psp_inh':      'PSP\n(INH)',
        'connectivity': 'Connectivity',
        'neurons':      'Neurons',
        'ap':           'AP activity',
        'discovery':    'Discovery',
        'other':        'Other',
    }

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label('mean z-score', fontsize=9)
    ax.set_title('Plate comparison — mean z-score per feature', fontsize=11, pad=10)

    plt.tight_layout()
    _add_group_brackets(ax, list(hm_df.index), _plate_group, _PLATE_LABELS)
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()
    return hm_df


# Called in the plate comparison notebook.
def plot_well_feature_heatmap(df_features, output_path=None,  cmap='YlOrRd'):
    """One heatmap per plate: features x wells, log1p-transformed and row-normalised."""

    def _well_sort_key(w):
        if not isinstance(w, str) or len(w) < 2:
            return (99, 999)
        return (ord(w[0].upper()) - ord('A'), int(w[1:]))

    feat_cols = _ordered_features([
        c for c in df_features.select_dtypes(include='number').columns
        if c not in ('fov',)
    ])

    for plate in df_features['plate'].unique():
        pdf = df_features[df_features['plate'] == plate]
        well_df = pdf.groupby('well')[feat_cols].mean()
        wells = sorted(well_df.index, key=_well_sort_key)
        well_df = well_df.loc[wells]

        # log1p transform (clip negatives to 0 first)
        vals = np.log1p(np.clip(well_df.values.T, 0, None))  # features x wells

        # min-max normalise each feature row so colour spans full range per feature
        row_min = np.nanmin(vals, axis=1, keepdims=True)
        row_max = np.nanmax(vals, axis=1, keepdims=True)
        span = np.where(row_max - row_min == 0, np.nan, row_max - row_min)
        normed = (vals - row_min) / span

        n_feats, n_wells = normed.shape
        fig, ax = plt.subplots(figsize=(max(6, n_wells * 0.65), max(6, n_feats * 0.25)))

        masked = np.ma.masked_invalid(normed)
        im = ax.imshow(masked, aspect='auto', cmap=cmap, vmin=0, vmax=1)

        ax.set_xticks(range(n_wells))
        ax.set_xticklabels(wells, rotation=45, ha='right', fontsize=8)
        ax.set_yticks(range(n_feats))
        ax.set_yticklabels(feat_cols, fontsize=7)

        prev_cat = None
        for i, feat in enumerate(feat_cols):
            cat = next((p for p in _CAT_PREFIXES if feat.startswith(p)), 'other')
            if cat != prev_cat and i > 0:
                ax.axhline(i - 0.5, color='white', lw=1.5)
            prev_cat = cat

        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
        cbar.set_label('log1p (min–max per feature)', fontsize=9)
        ax.set_title(f'{plate} — feature consistency across wells', fontsize=11, pad=10)

        plt.tight_layout()
        if output_path:
            base = output_path.rsplit('.', 1)[0]
            plt.savefig(f'{base}_{plate}.png', dpi=150, bbox_inches='tight')
            print(f'Saved: {base}_{plate}.png')
        plt.close()


# Called in the plate comparison notebook.
def plot_plate_condition_heatmap(df_features, output_path=None, vmax=None):
    """One Cohen's d heatmap per plate: features x drug conditions vs No Drug."""
    feat_cols = _ordered_features([
        c for c in df_features.select_dtypes(include='number').columns
        if c not in ('fov',)
    ])

    def _type_group(f):
        if f.endswith('_exc'): return 'exc'
        if f.endswith('_inh'): return 'inh'
        return 'neutral'

    for plate in df_features['plate'].unique():
        pdf = df_features[df_features['plate'] == plate]
        ctrl = pdf[pdf['condition'] == 'No Drug']
        drugs = [c for c in pdf['condition'].unique() if c != 'No Drug']

        if not drugs:
            print(f'[{plate}] no drug conditions — skipping')
            continue

        data = {
            drug: {
                feat: _cohens_d(
                    pdf.loc[pdf['condition'] == drug, feat].values,
                    ctrl[feat].values,
                )
                for feat in feat_cols
            }
            for drug in drugs
        }
        hm_df = pd.DataFrame(data, index=feat_cols)

        n_rows, n_cols = hm_df.shape
        fig, ax = plt.subplots(figsize=(max(4, n_cols * 1.5), max(6, n_rows * 0.25)))

        masked = np.ma.masked_invalid(hm_df.values.astype(float))
        _vmax = vmax if vmax is not None else (
            max(1.0, float(np.nanpercentile(np.abs(masked.compressed()), 95))) if masked.count() else 2.0
        )
        im = ax.imshow(masked, cmap='RdBu_r', vmin=-_vmax, vmax=_vmax, aspect='auto')

        ax.set_xticks(range(n_cols))
        ax.set_xticklabels(hm_df.columns, rotation=45, ha='right', fontsize=9)
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(hm_df.index, fontsize=8)

        prev_type = prev_cat = None
        for i, feat in enumerate(hm_df.index):
            typ = _type_group(feat)
            cat = next((p for p in _CAT_PREFIXES if feat.startswith(p)), 'other')
            if i > 0:
                if typ != prev_type:
                    ax.axhline(i - 0.5, color='white', lw=2.5)
                elif cat != prev_cat:
                    ax.axhline(i - 0.5, color='white', lw=1.0)
            prev_type, prev_cat = typ, cat

        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
        cbar.set_label("Cohen's d (vs No Drug)", fontsize=9)
        ax.set_title(f"{plate} — drug conditions vs No Drug", fontsize=11, pad=10)

        plt.tight_layout()
        if output_path:
            base = output_path.rsplit('.', 1)[0]
            plt.savefig(f'{base}_{plate}.png', dpi=150, bbox_inches='tight')
            print(f'Saved: {base}_{plate}.png')
        plt.close()


# Called in the plate comparison notebook.
def build_variance_table(df_features, output_path=None):
    """
    Per-plate mean, SD, and CoV (%) for every numeric feature.
    Returns a styled DataFrame; optionally saves to CSV.
    """
    feat_cols = _ordered_features([
        c for c in df_features.select_dtypes(include='number').columns
        if c not in ('fov',)
    ])
    plates = df_features['plate'].unique().tolist()

    col_tuples = [(p, stat) for p in plates for stat in ('mean', 'SD', 'CoV %')]
    columns = pd.MultiIndex.from_tuples(col_tuples)
    table = pd.DataFrame(index=feat_cols, columns=columns, dtype=float)

    for plate in plates:
        sub = df_features[df_features['plate'] == plate][feat_cols]
        m   = sub.mean()
        sd  = sub.std(ddof=1)
        cov = (sd / m * 100).where(m != 0, other=np.nan)
        table[(plate, 'mean')]  = m
        table[(plate, 'SD')]    = sd
        table[(plate, 'CoV %')] = cov

    if output_path:
        table.to_csv(output_path)
        print(f'Saved: {output_path}')

    cov_cols = [c for c in table.columns if c[1] == 'CoV %']

    def _cov_color(val):
        if pd.isna(val) or val <= 0:
            return ''
        if val > 50:
            return 'color: #c0392b; font-weight: bold'
        if val > 25:
            return 'color: #e67e22'
        return 'color: #27ae60'

    styled = (table.round(3)
              .style
              .set_caption('Within-plate variability — mean, SD, CoV per feature')
              .set_table_styles([{'selector': 'th, td', 'props': [('font-size', '9px')]}])
              .map(_cov_color, subset=cov_cols))
    return styled


# ============================================================================
# Network topology visualizations
# ============================================================================

_FEATURE_GROUPS = [
    ('Activity', [
        ('EXC firing rate',  'ap_mean_rate_exc'),
        ('INH firing rate',  'ap_mean_rate_inh'),
        ('Nonfiring neurons %', 'nonfiring_neurons_pct'),
    ]),
    ('Connectivity', [
        ('Total connections', 'conn_n_total'),
        ('E/I ratio',         'conn_exc_inh_ratio'),
        ('Network density',   'conn_density_index'),
    ]),
    ('Synaptic properties', [
        ('EXC amplitude',    'psp_amplitude_exc'),
        ('INH amplitude',    'psp_amplitude_inh'),
        ('EXC AUC',          'psp_auc_exc'),
        ('INH AUC',          'psp_auc_inh'),
        ('EXC PSP rate',     'psp_rate_exc'),
        ('INH PSP rate',     'psp_rate_inh'),
    ]),
    ('Topology', [
        ('Divergence',       'conn_mean_per_source'),
        ('Convergence',      'conn_mean_inputs_per_post'),
        ('Reciprocal %',     'conn_pct_reciprocal'),
        ('Mixed-input %',    'conn_pct_post_both_input'),
    ]),
    ('PSP kinetics', [
        ('EXC rise time',    'psp_rise_time_ms_exc'),
        ('EXC decay time',   'psp_decay_time_ms_exc'),
        ('EXC half-width',   'psp_half_width_ms_exc'),
        ('INH rise time',    'psp_rise_time_ms_inh'),
        ('INH decay time',   'psp_decay_time_ms_inh'),
        ('INH half-width',   'psp_half_width_ms_inh'),
    ]),
]

_RADAR_FEATURES = [
    ('density',       'conn_density_index'),
    ('reciprocal %',  'conn_pct_reciprocal'),
    ('divergence',    'conn_mean_per_source'),
    ('convergence',   'conn_mean_inputs_per_post'),
    ('silent %',      'nonfiring_neurons_pct'),
    ('ISI CV (firing irregularity)', 'ap_mean_isi_cv'),
    ('dual-method %', 'conn_pct_both_methods'),
]


# Called in the plate comparison notebook.
def plot_network_fingerprint(df_features, control_labels=None, output_path=None,
                             condition_colors=None):
    """
    Radar chart: one polygon per condition over min-max normalised topology features.
    Features are averaged per condition before normalisation.

    condition_colors : dict, optional
        Mapping of condition name -> hex color. Pass the same dict used in
        boxplots to keep colors consistent across figures. If None, colors are
        assigned from the Quiver ramp over sorted drug conditions.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS

    available = [(lbl, col) for lbl, col in _RADAR_FEATURES if col in df_features.columns]
    if len(available) < 3:
        print('plot_network_fingerprint: fewer than 3 radar features present — skipping.')
        return
    labels, cols = zip(*available)
    cols = list(cols)

    cond_means = df_features.groupby('condition')[cols].mean()
    vmin = cond_means.min()
    vmax = cond_means.max()
    norm = (cond_means - vmin) / (vmax - vmin).replace(0, np.nan)
    norm = norm.fillna(0.5)

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    ctrl_conds = [c for c in cond_means.index if c in ctrl_set]
    drug_conds = ([c for c in condition_colors if c in cond_means.index and c not in ctrl_set]
                  if condition_colors is not None
                  else [c for c in cond_means.index if c not in ctrl_set])

    if condition_colors is None:
        _palette = _quiver_colors(max(len(drug_conds), 1))
        condition_colors = {c: _palette[i] for i, c in enumerate(drug_conds)}

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    ax.set_position([0.3, 0.3, 0.35, 0.35])
    ax.tick_params(pad=12)

    _drug_ls = ['-', '--', '-.', ':']

    for cond in ctrl_conds + drug_conds:
        if cond not in norm.index:
            continue
        vals = norm.loc[cond, cols].tolist() + [norm.loc[cond, cols[0]]]
        is_ctrl = cond in ctrl_set
        idx   = drug_conds.index(cond) if not is_ctrl else 0
        color = _GREY if is_ctrl else condition_colors.get(cond, _QUIVER_PURPLE)
        ls    = '--' if is_ctrl else _drug_ls[idx % len(_drug_ls)]
        ax.plot(angles, vals, color=color, lw=1.5 if is_ctrl else 2.0,
                ls=ls, label=cond)
        ax.fill(angles, vals, color=color, alpha=0.06)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['0', '', '0.5', '', '1'], fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_title('Network fingerprint\n(min–max normalised per feature)', pad=16, fontsize=10)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, 0.02),
               ncol=min(len(labels), 4), fontsize=8, frameon=False)

    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_circuit_composition(df_features, control_labels=None, output_path=None,
                             condition_order=None):
    """
    Side-by-side stacked bars per condition: E→E / E→I / I→E / I→I connection counts
    (absolute left, proportional right).
    """
    cols    = ['conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i']
    clabels = ['E→E', 'E→I', 'I→E', 'I→I']
    colors  = [_EXC, _EXC_LIGHT, _INH_LIGHT, _INH]

    missing = [c for c in cols if c not in df_features.columns]
    if missing:
        print(f'plot_circuit_composition: missing columns {missing} — skipping.')
        return

    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    cond_means = df_features.groupby('condition')[cols].mean()
    ctrl_conds = [c for c in cond_means.index if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in cond_means.index and c not in ctrl_set]
        drug_conds += [c for c in cond_means.index if c not in ctrl_set and c not in drug_conds]
    else:
        drug_conds = [c for c in cond_means.index if c not in ctrl_set]
    cond_means = cond_means.loc[ctrl_conds + drug_conds]

    n_conds = len(cond_means)
    fig, axes = plt.subplots(1, 2, figsize=(max(7, n_conds * 1.3 + 2), 4.5))

    for ax, proportional in zip(axes, (False, True)):
        data = cond_means[cols].fillna(0)
        if proportional:
            totals = data.sum(axis=1).replace(0, np.nan)
            data = (data.T / totals).T * 100
        bottom = np.zeros(n_conds)
        for col, lbl, color in zip(cols, clabels, colors):
            vals = data[col].values
            ax.bar(range(n_conds), vals, bottom=bottom, color=color, label=lbl, width=0.6)
            bottom += vals
        ax.set_xticks(range(n_conds))
        ax.set_xticklabels(cond_means.index, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel('% of typed connections' if proportional else 'Mean connection count')
        ax.set_title('Proportional' if proportional else 'Absolute')
        ax.legend(fontsize=9)
        ax.spines[['top', 'right']].set_visible(False)

    fig.suptitle('Circuit E/I composition per condition', fontsize=11)
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_fanin_fanout(df_features, control_labels=None, output_path=None,
                     condition_colors=None, condition_order=None):
    """
    Scatter of divergence vs convergence per FOV, coloured by condition.

    Divergence (x-axis): mean number of validated outgoing connections per
    source neuron — how broadly a typical neuron broadcasts its output.

    Convergence (y-axis): mean number of validated inputs per receiving neuron
    — how many sources a typical neuron integrates from.

    Points above the diagonal → network is more convergent than divergent.
    Points below → more divergent than convergent.
    Cross marker = condition centroid.
    """
    x_col, y_col = 'conn_mean_per_source', 'conn_mean_inputs_per_post'
    if x_col not in df_features.columns or y_col not in df_features.columns:
        print(f'plot_fanin_fanout: missing {x_col} or {y_col} — skipping.')
        return

    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    conditions = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in conditions if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conds += [c for c in conditions if c not in ctrl_set and c not in drug_conds]
    elif condition_colors is not None:
        drug_conds = [c for c in condition_colors if c in conditions and c not in ctrl_set]
    else:
        drug_conds = [c for c in conditions if c not in ctrl_set]
    if condition_colors is not None:
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: condition_colors.get(c, _QUIVER_PURPLE) for c in drug_conds})
    else:
        _palette = _quiver_colors(max(len(drug_conds), 1))
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: _palette[i] for i, c in enumerate(drug_conds)})
    cond_order = ctrl_conds + drug_conds

    # compute shared axis limits across all conditions
    sub_all = df_features.dropna(subset=[x_col, y_col])
    x_min, x_max = sub_all[x_col].min(), sub_all[x_col].max()
    y_min, y_max = sub_all[y_col].min(), sub_all[y_col].max()
    pad_x = (x_max - x_min) * 0.1 or 0.5
    pad_y = (y_max - y_min) * 0.1 or 0.5
    diag_lo = min(x_min, y_min) - max(pad_x, pad_y)
    diag_hi = max(x_max, y_max) + max(pad_x, pad_y)

    n_conds = len(cond_order)
    fig, axes = plt.subplots(1, n_conds, figsize=(3.5 * n_conds, 4),
                             sharex=True, sharey=True)
    if n_conds == 1:
        axes = [axes]

    for ax, cond in zip(axes, cond_order):
        sub = df_features[df_features['condition'] == cond].dropna(subset=[x_col, y_col])
        color = cond_color[cond]
        ax.scatter(sub[x_col], sub[y_col], s=40, color=color,
                   alpha=0.6, edgecolors='white', linewidths=0.5)
        if not sub.empty:
            ax.scatter(sub[x_col].mean(), sub[y_col].mean(),
                       marker='+', s=200, color=color, linewidths=2.5, zorder=5)
        ax.plot([diag_lo, diag_hi], [diag_lo, diag_hi],
                color='#cccccc', lw=1, ls='--', zorder=0)
        ax.set_xlim(x_min - pad_x, x_max + pad_x)
        ax.set_ylim(y_min - pad_y, y_max + pad_y)
        ax.set_title(cond, fontsize=9, color=color)
        ax.set_xlabel('Divergence', fontsize=8)
        ax.spines[['top', 'right']].set_visible(False)

    axes[0].set_ylabel('Convergence', fontsize=8)
    fig.suptitle('Convergence vs divergence per FOV', fontsize=10)
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_pharmacology_dissociation(df_features, control_labels=None, output_path=None,
                                   condition_colors=None, condition_order=None):
    """
    Normalized bar chart (% of control mean) for four key metrics:
    EXC AP rate, INH AP rate, EXC PSP rate, INH PSP rate.
    Bars are colored green (EXC) / orange (INH); conditions distinguished by hatch.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    conditions = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in conditions if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conds += [c for c in conditions if c not in ctrl_set and c not in drug_conds]
    elif condition_colors is not None:
        drug_conds = [c for c in condition_colors if c in conditions and c not in ctrl_set]
    else:
        drug_conds = [c for c in conditions if c not in ctrl_set]
    if not drug_conds:
        print('plot_pharmacology_dissociation: no drug conditions found — skipping.')
        return

    metrics = [
        ('ap_mean_rate_exc',  'EXC AP rate'),
        ('ap_mean_rate_inh',  'INH AP rate'),
        ('psp_rate_exc',      'EXC PSP rate'),
        ('psp_rate_inh',      'INH PSP rate'),
    ]
    metrics = [(col, lbl) for col, lbl in metrics if col in df_features.columns]
    if not metrics:
        print('plot_pharmacology_dissociation: required columns missing — skipping.')
        return

    def _iqr_filter(s, k=3.0):
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return s[(s >= q1 - k * iqr) & (s <= q3 + k * iqr)]

    from scipy.stats import mannwhitneyu

    if condition_colors is not None:
        cond_color = {cond: condition_colors.get(cond, _QUIVER_PURPLE) for cond in drug_conds}
    else:
        palette    = _quiver_colors(len(drug_conds))
        cond_color = {cond: palette[j] for j, cond in enumerate(drug_conds)}

    ctrl_df    = df_features[df_features['condition'].isin(ctrl_set)]
    ctrl_means = {col: ctrl_df[col].fillna(0).mean() for col, _ in metrics}

    n_metrics = len(metrics)
    n_drugs   = len(drug_conds)
    bar_w     = 0.22
    group_width = n_drugs * bar_w + 0.15
    x_centers   = np.arange(n_metrics) * (group_width + 0.2)

    fig, ax = plt.subplots(figsize=(n_drugs * n_metrics * 0.5 + 2.5, 4))

    for j, cond in enumerate(drug_conds):
        drug_df = df_features[df_features['condition'] == cond]
        offsets = np.linspace(-(n_drugs - 1) / 2, (n_drugs - 1) / 2, n_drugs) * bar_w

        for i, (col, lbl) in enumerate(metrics):
            vals     = drug_df[col].fillna(0)
            baseline = ctrl_means[col]
            pct_vals = (100 * vals / baseline) if baseline > 0 else pd.Series(np.zeros(len(vals)))
            pct_vals = _iqr_filter(pd.Series(pct_vals))
            n    = len(pct_vals)
            mean = pct_vals.mean() if n else 0
            sem  = pct_vals.std(ddof=1) / np.sqrt(n) if n > 1 else 0
            x    = x_centers[i] + offsets[j]
            ax.bar(x, mean, yerr=sem, width=bar_w, color=cond_color[cond],
                   capsize=4, error_kw=dict(elinewidth=1.2),
                   label=cond if i == 0 else '')
            ax.scatter([x] * n, pct_vals, color='k', s=12, zorder=5, alpha=0.5)

            raw_ctrl = ctrl_df[col].fillna(0)
            raw_drug = drug_df[col].fillna(0)
            if len(raw_ctrl) >= 2 and len(raw_drug) >= 2:
                _, p = mannwhitneyu(raw_ctrl, raw_drug, alternative='two-sided')
                stars = _sig_stars(p)
                if stars != 'ns':
                    ax.annotate(stars, xy=(x, mean + sem),
                                xytext=(0, 4), textcoords='offset points',
                                ha='center', va='bottom', fontsize=8, clip_on=False)

    ax.axhline(100, color='gray', lw=1, ls='--', zorder=0)
    ax.set_xticks(x_centers)
    ax.set_xticklabels([lbl for _, lbl in metrics], fontsize=9)
    ax.set_ylabel('% of control mean', fontsize=9)
    ax.set_title('Pre-synaptic firing vs post-synaptic transmission\n(normalized to control)', fontsize=10)
    ax.legend(frameon=False, fontsize=8, bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.spines[['top', 'right']].set_visible(False)

    plt.tight_layout()
    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_synaptic_coupling(df_features, control_labels=None, output_path=None,
                           condition_colors=None, condition_order=None):
    """
    Synaptic coupling efficiency: PSP rate / AP rate per type, per condition.
    Shown as % of control. Two panels (EXC, INH), one bar per drug condition,
    colored green/orange with hatch to distinguish conditions.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    conditions = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in conditions if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conds += [c for c in conditions if c not in ctrl_set and c not in drug_conds]
    elif condition_colors is not None:
        drug_conds = [c for c in condition_colors if c in conditions and c not in ctrl_set]
    else:
        drug_conds = [c for c in conditions if c not in ctrl_set]
    if not drug_conds:
        print('plot_synaptic_coupling: no drug conditions found — skipping.')
        return

    required = {'ap_mean_rate_exc', 'ap_mean_rate_inh', 'psp_rate_exc', 'psp_rate_inh'}
    if not required.issubset(df_features.columns):
        print(f'plot_synaptic_coupling: missing columns {required - set(df_features.columns)} — skipping.')
        return

    def _iqr_filter(s, k=3.0):
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return s[(s >= q1 - k * iqr) & (s <= q3 + k * iqr)]

    df = df_features.copy()
    df['coupling_exc'] = df['psp_rate_exc'] / df['ap_mean_rate_exc'].replace(0, np.nan)
    df['coupling_inh'] = df['psp_rate_inh'] / df['ap_mean_rate_inh'].replace(0, np.nan)

    ctrl_df    = df[df['condition'].isin(ctrl_set)]
    ctrl_exc   = ctrl_df['coupling_exc'].mean()
    ctrl_inh   = ctrl_df['coupling_inh'].mean()
    if condition_colors is not None:
        cond_color = {cond: condition_colors.get(cond, _QUIVER_PURPLE) for cond in drug_conds}
    else:
        palette    = _quiver_colors(len(drug_conds))
        cond_color = {cond: palette[j] for j, cond in enumerate(drug_conds)}

    panels = [
        ('coupling_exc', 'EXC coupling\n(EPSP rate / EXC AP rate)', ctrl_exc),
        ('coupling_inh', 'INH coupling\n(IPSP rate / INH AP rate)', ctrl_inh),
    ]

    from scipy.stats import mannwhitneyu

    n_drugs   = len(drug_conds)
    fig, axes = plt.subplots(1, 2, figsize=(n_drugs * 1.8 + 3, 4), sharey=True)

    ctrl_df_raw = df[df['condition'].isin(ctrl_set)]

    for ax, (col, lbl, baseline) in zip(axes, panels):
        for j, cond in enumerate(drug_conds):
            drug_df  = df[df['condition'] == cond]
            vals     = drug_df[col].dropna()
            pct_vals = (100 * vals / baseline) if (baseline and baseline > 0) else pd.Series(np.zeros(len(vals)))
            pct_vals = _iqr_filter(pd.Series(pct_vals))
            n    = len(pct_vals)
            mean = pct_vals.mean() if n else 0
            sem  = pct_vals.std(ddof=1) / np.sqrt(n) if n > 1 else 0
            ax.bar(j, mean, yerr=sem, width=0.5, color=cond_color[cond],
                   capsize=4, error_kw=dict(elinewidth=1.2), label=cond)
            ax.scatter([j] * n, pct_vals, color='k', s=12, zorder=5, alpha=0.5)

            raw_ctrl = ctrl_df_raw[col].dropna()
            raw_drug = drug_df[col].dropna()
            if len(raw_ctrl) >= 2 and len(raw_drug) >= 2:
                _, p = mannwhitneyu(raw_ctrl, raw_drug, alternative='two-sided')
                stars = _sig_stars(p)
                if stars != 'ns':
                    ax.annotate(stars, xy=(j, mean + sem),
                                xytext=(0, 4), textcoords='offset points',
                                ha='center', va='bottom', fontsize=8, clip_on=False)

        ax.axhline(100, color='gray', lw=1, ls='--', zorder=0)
        ax.set_xticks(range(n_drugs))
        ax.set_xticklabels(drug_conds, rotation=30, ha='right', fontsize=8)
        ax.set_title(lbl, fontsize=9)
        ax.spines[['top', 'right']].set_visible(False)

    axes[0].set_ylabel('% of control mean', fontsize=9)
    fig.suptitle('Synaptic coupling efficiency per condition', fontsize=10)
    plt.tight_layout()
    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.close()


# Called in the plate comparison notebook.
def plot_feature_boxplots(df_features, control_labels=None, output_path=None, show_ns=False, fold_change=False,
                          condition_colors=None, condition_order=None):
    """
    One figure per feature group: box plot + scatter overlay per condition.
    Groups and features are defined by _FEATURE_GROUPS.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    conditions = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in conditions if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in conditions and c not in ctrl_set]
        drug_conds += [c for c in conditions if c not in ctrl_set and c not in drug_conds]
    elif condition_colors is not None:
        drug_conds = [c for c in condition_colors if c in conditions and c not in ctrl_set]
    else:
        drug_conds = [c for c in conditions if c not in ctrl_set]
    cond_order = ctrl_conds + drug_conds
    if condition_colors is not None:
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: condition_colors.get(c, _QUIVER_PURPLE) for c in drug_conds})
    else:
        _palette = _quiver_colors(max(len(drug_conds), 1))
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: _palette[i] for i, c in enumerate(drug_conds)})

    for group_name, features in _FEATURE_GROUPS:
        avail = [(lbl, col) for lbl, col in features if col in df_features.columns]
        missing = [col for _, col in features if col not in df_features.columns]
        if missing:
            print(f'[{group_name}] skipping missing columns: {missing}')
        if not avail:
            continue

        n_feat = len(avail)
        fig, axes = plt.subplots(1, n_feat, figsize=(n_feat * 2.8, 4.5))
        if n_feat == 1:
            axes = [axes]

        _zero_fill = {
            'conn_n_exc', 'conn_n_inh', 'conn_n_total',
            'conn_n_e2e', 'conn_n_e2i', 'conn_n_i2e', 'conn_n_i2i',
            'psp_rate_exc', 'psp_rate_inh',
            'ap_mean_rate_exc', 'ap_mean_rate_inh',
            'conn_n_exc_per_active_exc', 'conn_n_inh_per_active_inh',
        }

        for ax, (feat_label, feat_col) in zip(axes, avail):
            plot_data, plot_pos, plot_colors = [], [], []

            ctrl_mean = None
            if fold_change and ctrl_conds:
                ctrl_raw = df_features.loc[df_features['condition'].isin(ctrl_conds), feat_col]
                ctrl_vals = (ctrl_raw.fillna(0) if feat_col in _zero_fill else ctrl_raw.dropna()).values
                ctrl_mean = float(np.mean(ctrl_vals)) if len(ctrl_vals) else None

            for i, cond in enumerate(cond_order):
                raw = df_features.loc[df_features['condition'] == cond, feat_col]
                vals = (raw.fillna(0) if feat_col in _zero_fill else raw.dropna()).values
                if len(vals) < 2:
                    continue
                if fold_change and ctrl_mean and abs(ctrl_mean) > 1e-10:
                    vals = vals / ctrl_mean
                plot_data.append(vals)
                plot_pos.append(i)
                plot_colors.append(cond_color[cond])

            if plot_data:
                bp = ax.boxplot(
                    plot_data, positions=plot_pos, patch_artist=True,
                    widths=0.5, showfliers=False,
                    medianprops=dict(color='black', lw=2),
                    boxprops=dict(linewidth=0.8),
                    whiskerprops=dict(linewidth=0.8),
                    capprops=dict(linewidth=0.8),
                )
                for patch, color in zip(bp['boxes'], plot_colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.5)

                for vals, pos, color in zip(plot_data, plot_pos, plot_colors):
                    jitter = np.random.normal(0, 0.08, size=len(vals))
                    ax.scatter(pos + jitter, vals, s=14, color=color,
                               alpha=0.7, zorder=3, edgecolors='none')

                _pct_cols = {'nonfiring_neurons_pct', 'conn_pct_reciprocal', 'conn_pct_post_both_input'}
                if fold_change:
                    ax.axhline(1.0, color='gray', lw=0.8, ls='--', zorder=0)
                    all_vals = np.concatenate(plot_data)
                    q1, q3 = np.percentile(all_vals, [25, 75])
                    iqr = q3 - q1
                    y_bot = min(0, q1 - 1.5 * iqr) if iqr > 0 else min(0, all_vals.min() * 0.9)
                    y_top = max(q3 + 4.5 * iqr, all_vals.max() * 1.1) if iqr > 0 else (all_vals.max() * 1.1)
                    ax.set_ylim(y_bot, y_top)
                elif feat_col in _pct_cols:
                    ax.set_ylim(0, 100)
                else:
                    all_vals = np.concatenate(plot_data)
                    q1, q3 = np.percentile(all_vals, [25, 75])
                    iqr = q3 - q1
                    if iqr > 0:
                        y_bot = min(0, q1 - 1.5 * iqr)
                        y_top = max(q3 + 4.5 * iqr, all_vals.max() * 1.1)
                    else:
                        span = max(abs(all_vals.max()), abs(all_vals.min()), 1e-9)
                        y_bot = min(0, all_vals.min() - 0.1 * span)
                        y_top = all_vals.max() + 0.1 * span
                    ax.set_ylim(y_bot, y_top)

                # ── Drug vs control: Mann-Whitney U, bracket annotations ───
                if ctrl_conds and drug_conds:
                    from scipy.stats import mannwhitneyu
                    pos_to_vals = dict(zip(plot_pos, plot_data))
                    ctrl_pos = [cond_order.index(c) for c in ctrl_conds
                                if cond_order.index(c) in pos_to_vals]
                    if ctrl_pos:
                        ctrl_stat = np.concatenate([pos_to_vals[p] for p in ctrl_pos])
                        y_lo, y_hi = ax.get_ylim()
                        step = (y_hi - y_lo) * 0.13
                        sig_pairs = []
                        for dc in drug_conds:
                            dp = cond_order.index(dc)
                            if dp not in pos_to_vals:
                                continue
                            dv = pos_to_vals[dp]
                            if len(ctrl_stat) < 2 or len(dv) < 2:
                                continue
                            _, p = mannwhitneyu(ctrl_stat, dv, alternative='two-sided')
                            stars = _sig_stars(p)
                            if show_ns or stars != 'ns':
                                sig_pairs.append((dp, stars))
                        if sig_pairs:
                            ax.set_ylim(y_lo, y_hi + step * (len(sig_pairs) + 0.5))
                            cx = ctrl_pos[0]
                            for rank, (dp, stars) in enumerate(sig_pairs):
                                by = y_hi + step * (rank + 0.4)
                                th = step * 0.15
                                ax.plot([cx, cx, dp, dp],
                                        [by - th, by, by, by - th],
                                        color='#555', lw=0.8, clip_on=False)
                                ax.text((cx + dp) / 2, by + step * 0.05, stars,
                                        ha='center', va='bottom', fontsize=9,
                                        clip_on=False)

            ax.set_xticks(range(len(cond_order)))
            ax.set_xticklabels(cond_order, rotation=45, ha='right', fontsize=8)
            ax.set_xlim(-0.5, len(cond_order) - 0.5)
            ax.set_title(feat_label, fontsize=9, pad=4)
            if fold_change:
                ax.set_ylabel('Fold change over No Drug', fontsize=8)
            ax.spines[['top', 'right']].set_visible(False)

        # Sync y-axes for _exc / _inh pairs within this group
        for j, (_, col_j) in enumerate(avail):
            if col_j.endswith('_exc'):
                pair = col_j[:-4] + '_inh'
                for k, (_, col_k) in enumerate(avail):
                    if col_k == pair:
                        ymin = min(axes[j].get_ylim()[0], axes[k].get_ylim()[0])
                        ymax = max(axes[j].get_ylim()[1], axes[k].get_ylim()[1])
                        axes[j].set_ylim(ymin, ymax)
                        axes[k].set_ylim(ymin, ymax)

        fig.suptitle(group_name, fontsize=11, y=1.01)
        plt.tight_layout()

        if output_path:
            base = output_path.rsplit('.', 1)[0]
            safe = group_name.lower().replace(' ', '_')
            plt.savefig(f'{base}_{safe}.png', dpi=150, bbox_inches='tight')
            print(f'Saved: {base}_{safe}.png')
        plt.close()


# Called in the plate comparison notebook.
def plot_ei_balance_debug(df_features, control_labels=None, condition_order=None,
                          condition_colors=None, output_path=None):
    """
    Diagnostic strip plot for troubleshooting E/I balance.

    Three panels per condition:
      Left   — conn_n_exc  (validated EXC connections per FOV)
      Middle — conn_n_inh  (validated INH connections per FOV)
      Right  — conn_exc_inh_ratio  (computed ratio)

    Each dot is one FOV; median shown as a horizontal line.
    FOVs with ratio=NaN (no validated connections at all) are marked
    separately so you can see how many are being excluded.
    """
    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    all_conds = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in all_conds if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in all_conds and c not in ctrl_set]
        drug_conds += [c for c in all_conds if c not in ctrl_set and c not in drug_conds]
    else:
        drug_conds = [c for c in all_conds if c not in ctrl_set]
    cond_order = ctrl_conds + drug_conds

    if condition_colors is not None:
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: condition_colors.get(c, _QUIVER_PURPLE) for c in drug_conds})
    else:
        palette = _quiver_colors(max(len(drug_conds), 1))
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: palette[i] for i, c in enumerate(drug_conds)})

    panels = [
        ('conn_n_exc',        'EXC connections\n(validated, per FOV)'),
        ('conn_n_inh',        'INH connections\n(validated, per FOV)'),
        ('conn_exc_inh_ratio', 'E/I ratio\n(exc+0.5)/(inh+0.5)'),
    ]
    panels = [(col, lbl) for col, lbl in panels if col in df_features.columns]

    n_conds = len(cond_order)
    fig, axes = plt.subplots(1, len(panels), figsize=(len(panels) * max(4, n_conds * 0.9), 4.5))
    if len(panels) == 1:
        axes = [axes]

    rng = np.random.default_rng(0)

    for ax, (col, ylabel) in zip(axes, panels):
        for i, cond in enumerate(cond_order):
            rows = df_features[df_features['condition'] == cond]
            vals = rows[col].values.astype(float)
            valid = vals[~np.isnan(vals)]
            nan_count = np.isnan(vals).sum()

            color = cond_color.get(cond, _GREY)
            jitter = rng.uniform(-0.18, 0.18, size=len(valid))
            ax.scatter(i + jitter, valid, s=22, color=color, alpha=0.7,
                       zorder=3, edgecolors='none')

            if len(valid):
                med = np.median(valid)
                ax.plot([i - 0.28, i + 0.28], [med, med],
                        color=color, lw=2.0, zorder=4)

            if nan_count:
                ax.text(i, ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else -0.5,
                        f'{nan_count} NaN', ha='center', va='top',
                        fontsize=7, color='#999999', style='italic')

        ax.set_xticks(range(n_conds))
        ax.set_xticklabels(cond_order, rotation=30, ha='right', fontsize=8)
        ax.set_xlim(-0.5, n_conds - 0.5)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.spines[['top', 'right']].set_visible(False)

        # Annotate median per condition above each strip
        for i, cond in enumerate(cond_order):
            vals = df_features.loc[df_features['condition'] == cond, col].dropna().values
            if len(vals):
                ax.text(i, ax.get_ylim()[1], f'med={np.median(vals):.1f}',
                        ha='center', va='bottom', fontsize=6.5, color='#555')

    fig.suptitle('E/I balance diagnostics — per-FOV connection counts', fontsize=10)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'Saved: {output_path}')
    plt.show()
    plt.close()


# Called in the plate comparison notebook.
def plot_pharmacology_summary(df_features, all_fov_results=None,
                               control_labels=None, output_path=None,
                               condition_colors=None, condition_order=None):
    """
    Partner-facing summary figure:
      A) Total validated connections per FOV
      B) EXC synaptic properties — amplitude + PSP rate (% of No Drug)
      C) INH synaptic properties — amplitude + PSP rate (% of No Drug)
      D) Mean EPSP waveform per condition (when all_fov_results is provided)
      E) Mean IPSP waveform per condition (when all_fov_results is provided)
    All drug conditions are treated uniformly.
    """
    from scipy.stats import mannwhitneyu
    from matplotlib.gridspec import GridSpec

    ctrl_set   = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    all_conds  = df_features['condition'].unique().tolist()
    ctrl_conds = [c for c in all_conds if c in ctrl_set]
    if condition_order is not None:
        drug_conds = [c for c in condition_order if c in all_conds and c not in ctrl_set]
        drug_conds += [c for c in all_conds if c not in ctrl_set and c not in drug_conds]
    elif condition_colors is not None:
        drug_conds = [c for c in condition_colors if c in all_conds and c not in ctrl_set]
    else:
        drug_conds = [c for c in all_conds if c not in ctrl_set]

    if condition_colors is not None:
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: condition_colors.get(c, _QUIVER_PURPLE) for c in drug_conds})
    else:
        _palette   = _quiver_colors(max(len(drug_conds), 1))
        cond_color = {c: _GREY for c in ctrl_conds}
        cond_color.update({c: _palette[i] for i, c in enumerate(drug_conds)})

    cond_order = ctrl_conds + drug_conds
    ctrl_df    = df_features[df_features['condition'].isin(ctrl_set)]

    def _iqr_filter(s, k=3.0):
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return s[(s >= q1 - k * iqr) & (s <= q3 + k * iqr)]

    add_waves = all_fov_results is not None
    n_drugs   = len(drug_conds)
    fig_w     = max(13, 4 + n_drugs * 1.5)

    if add_waves:
        fig = plt.figure(figsize=(fig_w, 8.5))
        gs_top = GridSpec(1, 3, figure=fig, left=0.07, right=0.97, top=0.93, bottom=0.54, wspace=0.38)
        gs_bot = GridSpec(1, 2, figure=fig, left=0.07, right=0.97, top=0.44, bottom=0.08, wspace=0.35)
        axes    = [fig.add_subplot(gs_top[0, i]) for i in range(3)]
        ax_epsp = fig.add_subplot(gs_bot[0, 0])
        ax_ipsp = fig.add_subplot(gs_bot[0, 1])
    else:
        fig, axes = plt.subplots(1, 3, figsize=(fig_w, 4.5))

    # ── Panel A: E/I ratio ────────────────────────────────────────────────
    ax = axes[0]
    _a_col = 'conn_exc_inh_ratio'
    if _a_col in df_features.columns:
        pdata, ppos, pcols = [], [], []
        for i, c in enumerate(cond_order):
            vals = df_features.loc[df_features['condition'] == c, _a_col].dropna().values
            if len(vals) < 1:
                continue
            pdata.append(vals)
            ppos.append(i)
            pcols.append(cond_color.get(c, _GREY))

        bp = ax.boxplot(pdata, positions=ppos, patch_artist=True,
                        widths=0.5, showfliers=False,
                        medianprops=dict(color='black', lw=2),
                        boxprops=dict(linewidth=0.8),
                        whiskerprops=dict(linewidth=0.8),
                        capprops=dict(linewidth=0.8))
        for patch, color in zip(bp['boxes'], pcols):
            patch.set_facecolor(color)
            patch.set_alpha(0.5)
        for vals, pos, color in zip(pdata, ppos, pcols):
            jitter = np.random.normal(0, 0.08, size=len(vals))
            ax.scatter(pos + jitter, vals, s=14, color=color, alpha=0.7, zorder=3, edgecolors='none')

        all_A = np.concatenate(pdata)
        q1, q3 = np.percentile(all_A, [25, 75])
        iqr_A = q3 - q1
        ax.set_ylim(bottom=0, top=max(q3 + 4.5 * iqr_A, all_A.max() * 1.1, 1.0))
        ax.axhline(1.0, color='gray', lw=0.8, ls='--', zorder=0)

        ctrl_vals_A = ctrl_df[_a_col].dropna().values
        y_lo, y_hi  = ax.get_ylim()
        step        = (y_hi - y_lo) * 0.12
        sig_pairs   = []
        for c in drug_conds:
            dv = df_features.loc[df_features['condition'] == c, _a_col].dropna().values
            if len(ctrl_vals_A) >= 2 and len(dv) >= 2:
                _, p  = mannwhitneyu(ctrl_vals_A, dv, alternative='two-sided')
                stars = _sig_stars(p)
                if stars != 'ns':
                    sig_pairs.append((cond_order.index(ctrl_conds[0]), cond_order.index(c), stars))
        if sig_pairs:
            ax.set_ylim(y_lo, y_hi + step * (len(sig_pairs) + 0.5))
            for rank, (cx, dx, stars) in enumerate(sig_pairs):
                by = y_hi + step * (rank + 0.4)
                th = step * 0.15
                ax.plot([cx, cx, dx, dx], [by - th, by, by, by - th],
                        color='#555', lw=0.8, clip_on=False)
                ax.text((cx + dx) / 2, by + step * 0.05, stars,
                        ha='center', va='bottom', fontsize=9, clip_on=False)

    ax.set_xticks(range(len(cond_order)))
    ax.set_xticklabels(cond_order, rotation=30, ha='right', fontsize=8)
    ax.set_xlim(-0.5, len(cond_order) - 0.5)
    ax.set_ylabel('E/I ratio  (EXC+0.5)/(INH+0.5)', fontsize=8)
    ax.set_title('A   Synaptic E/I balance', fontsize=9, loc='left', fontweight='bold')
    ax.spines[['top', 'right']].set_visible(False)

    # ── Panels B & C: normalized synaptic properties ───────────────────────
    panel_specs = [
        (axes[1], 'psp_amplitude_exc', 'psp_rate_exc', 'EPSP amplitude', 'EPSP rate (Hz)', 'B   Excitatory synaptic strength'),
        (axes[2], 'psp_amplitude_inh', 'psp_rate_inh', 'IPSP amplitude', 'IPSP rate (Hz)', 'C   Inhibitory synaptic strength'),
    ]

    bar_w = 0.22

    for _panel_idx, (ax, amp_col, rate_col, amp_lbl, rate_lbl, title) in enumerate(panel_specs):
        metrics = [(col, lbl) for col, lbl in
                   [(amp_col, amp_lbl), (rate_col, rate_lbl)]
                   if col in df_features.columns]
        if not metrics:
            ax.set_visible(False)
            continue

        ctrl_means  = {col: ctrl_df[col].dropna().mean() for col, _ in metrics}
        n_metrics   = len(metrics)
        group_width = n_drugs * bar_w + 0.15
        x_centers   = np.arange(n_metrics) * (group_width + 0.2)
        offsets     = np.linspace(-(n_drugs - 1) / 2, (n_drugs - 1) / 2, n_drugs) * bar_w

        for j, cond in enumerate(drug_conds):
            drug_df   = df_features[df_features['condition'] == cond]
            bar_color = cond_color.get(cond, _GREY)

            for i, (col, lbl) in enumerate(metrics):
                vals     = drug_df[col].dropna()
                baseline = ctrl_means[col]
                pct_vals = (100 * vals / baseline) if abs(baseline) > 1e-10 else pd.Series(np.zeros(len(vals)))
                pct_vals = _iqr_filter(pd.Series(pct_vals))
                n    = len(pct_vals)
                mean = pct_vals.mean() if n else 0
                sem  = pct_vals.std(ddof=1) / np.sqrt(n) if n > 1 else 0
                x    = x_centers[i] + offsets[j]

                ax.bar(x, mean, yerr=sem, width=bar_w, color=bar_color,
                       capsize=4, error_kw=dict(elinewidth=1.2),
                       label=cond if i == 0 else '')
                ax.scatter([x] * n, pct_vals, color='k', s=12, zorder=5, alpha=0.5)

                raw_ctrl = ctrl_df[col].dropna()
                raw_drug = drug_df[col].dropna()
                if len(raw_ctrl) >= 2 and len(raw_drug) >= 2:
                    _, p  = mannwhitneyu(raw_ctrl, raw_drug, alternative='two-sided')
                    stars = _sig_stars(p)
                    if stars != 'ns':
                        ax.annotate(stars, xy=(x, 0.97),
                                    xycoords=('data', 'axes fraction'),
                                    ha='center', va='top', fontsize=8, clip_on=False)

        ax.axhline(100, color='gray', lw=1, ls='--', zorder=0)
        ax.set_xticks(x_centers)
        ax.set_xticklabels([lbl for _, lbl in metrics], fontsize=8)
        ax.set_ylabel('% of No Drug control (mean ± SEM)', fontsize=8)
        ax.set_title(title, fontsize=9, loc='left', fontweight='bold')
        if _panel_idx == len(panel_specs) - 1:
            ax.legend(frameon=False, fontsize=7, bbox_to_anchor=(1.01, 1), loc='upper left')
        ax.spines[['top', 'right']].set_visible(False)

    # ── Panels D & E: mean PSP waveforms per condition ────────────────────
    if add_waves:
        fov_cond_lookup = df_features.groupby(['fov', 'plate'])['condition'].first().to_dict() \
                          if 'plate' in df_features.columns else \
                          df_features.groupby('fov')['condition'].first().to_dict()

        cond_waves = {c: {'exc': [], 'inh': []} for c in cond_order}
        for R in all_fov_results:
            key  = (R['fov'], R.get('_plate', ''))
            cond = fov_cond_lookup.get(key) or fov_cond_lookup.get(R['fov'], 'No Drug')
            if cond not in cond_waves:
                continue
            w = compute_mean_psp_waveforms(R)
            for conn_type in ('exc', 'inh'):
                if w.get(conn_type, {}).get('mean') is not None:
                    cond_waves[cond][conn_type].append(w[conn_type]['mean'])

        t_ms = (np.arange(WIN_LEN) - PRE_AP_BLANK) / FS * 1000

        for wave_ax, conn_type, panel_label in [
            (ax_epsp, 'exc', 'D   Mean EPSP waveform (validated EXC connections)'),
            (ax_ipsp, 'inh', 'E   Mean IPSP waveform (validated INH connections)'),
        ]:
            for cond in cond_order:
                waves = cond_waves[cond][conn_type]
                if not waves:
                    continue
                arr        = np.array(waves)
                grand_mean = arr.mean(axis=0)
                grand_sem  = arr.std(axis=0) / np.sqrt(len(waves)) if len(waves) > 1 else np.zeros_like(grand_mean)
                color      = cond_color.get(cond, _GREY)
                wave_ax.fill_between(t_ms, grand_mean - grand_sem, grand_mean + grand_sem,
                                     alpha=0.15, color=color, lw=0)
                wave_ax.plot(t_ms, grand_mean, color=color, lw=1.8, label=cond)

            wave_ax.axvline(0, color='#666666', lw=0.8, ls='--')
            wave_ax.axhline(0, color='#cccccc', lw=0.6)
            wave_ax.set_xlabel('Time relative to pre-synaptic AP (ms)', fontsize=8)
            wave_ax.set_ylabel('Mean ΔF/F ± SEM across FOVs', fontsize=8)
            wave_ax.set_title(panel_label, fontsize=9, loc='left', fontweight='bold')
            wave_ax.legend(frameon=False, fontsize=7)
            wave_ax.tick_params(labelsize=7)
            wave_ax.spines[['top', 'right']].set_visible(False)

    fig.suptitle('SCS pharmacology — drug effects on connectivity and synaptic strength', fontsize=11,
                 y=0.97 if add_waves else 1.02)
    if not add_waves:
        plt.tight_layout()
    if output_path:
        base = output_path.rsplit('.', 1)[0]
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


# ============================================================================
# Power analysis
# ============================================================================

def plot_power_analysis(
    df_features,
    df_ap=None,
    control_labels=None,
    effect_sizes=None,
    alpha=0.05,
    power=0.80,
    output_path=None,
):
    """
    Required N per group (wells, one FOV each) to detect a % change from
    control mean at the given alpha and power.

    Variability is estimated from the pooled within-(plate, condition) SD
    of control FOVs only, separating within-condition noise from any drug
    effect present on mixed plates.

    Parameters
    ----------
    df_features    : DataFrame from build_condition_feature_df; must have
                     'plate' and 'condition' columns.
    df_ap          : optional DataFrame from build_ap_feature_df. When provided,
                     connected-pair AP features (pre/post/hub categories) are
                     appended to the analysis.
    control_labels : set of condition strings treated as control.
                     Defaults to _CONTROL_LABELS.
    effect_sizes   : list of fractions, e.g. [0.10, 0.20, 0.30, 0.50].
                     Defaults to [0.10, 0.20, 0.30, 0.40, 0.50].
    alpha          : type I error rate (default 0.05, two-tailed).
    power          : target power (default 0.80).
    output_path    : base path for output; saves <base>_heatmap.png and
                     <base>_lines.png. No files saved if None.

    Returns
    -------
    DataFrame of required N (float, pre-ceiling) indexed by feature,
    columns = effect size labels.  None if no control FOVs found.
    """
    from scipy import stats as _stats

    ctrl_set = set(control_labels) if control_labels is not None else _CONTROL_LABELS
    if effect_sizes is None:
        effect_sizes = [0.10, 0.20, 0.30, 0.40, 0.50]

    _meta = {'fov', 'condition', 'plate', 'well'}
    working_df = df_features.copy()

    if df_ap is not None:
        ap_feat_cols = [c for c in df_ap.columns
                        if any(c.startswith(cat + '_') for cat in _CONNECTED_AP_CATS)]
        merge_keys = [k for k in ('fov', 'plate') if k in df_features.columns and k in df_ap.columns]
        working_df = working_df.merge(df_ap[merge_keys + ap_feat_cols], on=merge_keys, how='left')

    feat_cols = [c for c in working_df.select_dtypes(include='number').columns
                 if c not in _meta]
    feat_cols = _ordered_features(feat_cols)

    ctrl_df = working_df[working_df['condition'].isin(ctrl_set)]
    if ctrl_df.empty:
        print('plot_power_analysis: no control FOVs found.')
        return None
    print(f"Control wells used for variance estimate: {len(ctrl_df)} "
          f"({ctrl_df.groupby('plate').size().to_dict()})")

    z_a = _stats.norm.ppf(1 - alpha / 2)
    z_b = _stats.norm.ppf(power)
    es_labels = [f'{int(e * 100)}%' for e in effect_sizes]

    results = {}
    for feat in feat_cols:
        vals = ctrl_df[feat].dropna().values
        if len(vals) < 3:
            continue
        ctrl_mean = float(np.mean(vals))
        ctrl_sd   = float(np.std(vals, ddof=1))
        if ctrl_sd == 0 or abs(ctrl_mean) < 1e-10:
            continue
        row = {}
        for es, lbl in zip(effect_sizes, es_labels):
            d = (es * abs(ctrl_mean)) / ctrl_sd
            row[lbl] = float(np.ceil(2 * ((z_a + z_b) / d) ** 2)) if d > 0 else np.inf
        results[feat] = row

    if not results:
        print('plot_power_analysis: no features with sufficient data.')
        return None

    result_df = pd.DataFrame(results).T
    result_df = result_df.loc[
        result_df.replace(np.inf, 200).mean(axis=1).sort_values().index
    ]
    base = output_path.rsplit('.', 1)[0] if output_path else None

    # ── Heatmap ───────────────────────────────────────────────────────────────
    # Piecewise-linear norm: half the color range covers 0–10, a quarter 10–20,
    # a quarter 20–100.  Gradient is preserved but transitions at 10 and 20 are
    # visually dramatic.
    from matplotlib.colors import Normalize as _Normalize
    class _PiecewiseNorm(_Normalize):
        def __call__(self, value, clip=None):
            v   = np.asarray(value, dtype=float)
            out = np.interp(v, [0, 10, 20, 50], [0.0, 0.50, 0.75, 1.0])
            return np.ma.masked_array(out, mask=np.isnan(v))

    _norm = _PiecewiseNorm()

    display = result_df.clip(upper=50).fillna(50)
    fig, ax = plt.subplots(figsize=(max(4, len(effect_sizes) * 0.9),
                                    max(6, len(results) * 0.15)))
    im = ax.imshow(display.values, cmap='RdYlGn_r', norm=_norm, aspect='auto')
    ax.set_xticks(range(len(es_labels)))
    ax.set_xticklabels(es_labels, fontsize=9)
    ax.set_yticks(range(len(result_df.index)))
    ax.set_yticklabels(result_df.index, fontsize=7)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04,
                        ticks=[0, 10, 20, 30, 50])
    cbar.set_label('Required N per group', fontsize=8)

    if 0.5 in effect_sizes:
        _ci = effect_sizes.index(0.5)
        ax.add_patch(plt.Rectangle(
            (_ci - 0.5, -0.5), 1, len(result_df),
            fill=False, edgecolor='black', linewidth=2, clip_on=False))

    ax.set_title(f'Power analysis  (α={alpha}, power={power})', fontsize=10)
    plt.tight_layout()
    if base:
        plt.savefig(f'{base}_heatmap.png', dpi=150, bbox_inches='tight')
        print(f'Saved: {base}_heatmap.png')
    plt.close()

    # ── Lines plot — top 30 features by fewest wells required ────────────────
    key_feats = result_df.index[:30].tolist()

    if key_feats:
        _line_colors = plt.cm.nipy_spectral(np.linspace(0.05, 0.95, len(key_feats)))
        fig, ax = plt.subplots(figsize=(5, 8))
        for feat, color in zip(key_feats, _line_colors):
            vals = result_df.loc[feat].values.astype(float)
            ax.plot(effect_sizes, np.clip(vals, 0, 100), marker='o', lw=1.5,
                    label=feat, color=color)
        ax.axhline(10, color='#aaaaaa', ls='--', lw=0.8)
        ax.axhline(20, color='#aaaaaa', ls=':',  lw=0.8)
        ax.set_xlabel('Effect size (fraction of control mean)', fontsize=9)
        ax.set_ylabel('Required N per group', fontsize=9)
        ax.set_ylim(0, 60)
        ax.legend(fontsize=6, loc='upper right')
        ax.set_title(f'Power analysis — key features  (α={alpha}, power={power})', fontsize=10)
        ax.spines[['top', 'right']].set_visible(False)
        plt.tight_layout()
        if base:
            plt.savefig(f'{base}_lines.png', dpi=150, bbox_inches='tight')
            print(f'Saved: {base}_lines.png')
        plt.close()

    return result_df


# ============================================================================
# Mean AP waveform by cell type
# ============================================================================
def plot_mean_ap_waveform_by_type(
    all_fov_results: list,
    window_ms: tuple = (-20, 80),
    baseline_ms: tuple = (-15, -5),
    fs: int = FS,
    output_path: Optional[str] = None,
    title: str = "Mean AP waveform by cell type",
) -> None:
    """
    Grand-mean AP waveform across all neurons, with separate traces for EXC
    and INH neurons. Shaded band is ±1 SEM across neurons.

    For each neuron all detected AP windows are extracted from the raw
    spontaneous trace (scs1), baseline-corrected using a pre-AP median
    window, and averaged to a single per-neuron waveform. Those per-neuron
    waveforms are then averaged across cell types.

    Parameters
    ----------
    all_fov_results : list of run_one_fov result dicts
    window_ms       : (pre_ms, post_ms) window around AP peak
    baseline_ms     : (start_ms, end_ms) pre-AP window used for baseline;
                      both values should be negative (before the peak)
    fs              : sampling rate in Hz
    output_path     : if given, saves PNG there
    title           : figure title
    """
    pre_samp  = int(abs(window_ms[0])   * fs / 1000)
    post_samp = int(window_ms[1]        * fs / 1000)
    bl_s      = int(abs(baseline_ms[0]) * fs / 1000)
    bl_e      = int(abs(baseline_ms[1]) * fs / 1000)
    n_samp    = pre_samp + post_samp
    t_ms      = np.linspace(window_ms[0], window_ms[1], n_samp)

    waveforms: dict = {'exc': [], 'inh': [], 'all': []}

    for R in all_fov_results:
        scs = R.get('scs1')
        nt  = R.get('neuron_tier')
        if scs is None or nt is None or nt.empty:
            continue

        raws_all = scs.get('raws_all', {})
        aps_all  = scs.get('aps_all',  {})
        type_map = dict(zip(nt['trace'].astype(int), nt['consensus_type']))

        for tid, aps in aps_all.items():
            raw = raws_all.get(tid)
            if raw is None or len(aps) == 0:
                continue

            ctype = type_map.get(int(tid), 'no_valid_outgoing_connections')

            windows = []
            for ap in aps:
                ap    = int(ap)
                start = ap - pre_samp
                end   = ap + post_samp
                if start < 0 or end > len(raw):
                    continue
                win      = raw[start:end].copy()
                baseline = np.median(raw[ap - bl_s: ap - bl_e])
                win     -= baseline
                windows.append(win)

            if not windows:
                continue

            mean_waveform = np.mean(windows, axis=0)

            if ctype in ('confident_exc', 'putative_exc'):
                waveforms['exc'].append(mean_waveform)
            elif ctype in ('confident_inh', 'putative_inh'):
                waveforms['inh'].append(mean_waveform)
            if ctype != 'no_valid_outgoing_connections':
                waveforms['all'].append(mean_waveform)

    fig, ax = plt.subplots(figsize=(7, 4))

    _colors = {'all': _GREY, 'exc': _EXC, 'inh': _INH}
    _labels = {
        'all': f"All neurons (n={len(waveforms['all'])})",
        'exc': f"EXC (n={len(waveforms['exc'])})",
        'inh': f"INH (n={len(waveforms['inh'])})",
    }

    for key in ('all', 'exc', 'inh'):
        data = waveforms[key]
        if not data:
            continue
        arr   = np.array(data)
        mean  = arr.mean(axis=0)
        sem   = arr.std(axis=0, ddof=1) / np.sqrt(len(arr))
        color = _colors[key]
        ax.plot(t_ms, mean, color=color, lw=1.8, label=_labels[key])
        ax.fill_between(t_ms, mean - sem, mean + sem, color=color, alpha=0.2)

    ax.axvline(0, color='black', lw=0.8, ls='--', alpha=0.5)
    ax.set_xlabel("Time relative to AP peak (ms)")
    ax.set_ylabel("dF/F (baseline-corrected)")
    ax.set_title(title)
    ax.legend(fontsize=9, frameon=False)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")
    plt.close()
