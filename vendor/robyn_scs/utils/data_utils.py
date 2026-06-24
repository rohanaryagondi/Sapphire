"""
data_utils.py — pipeline v17 shared utilities.
Notes on what changed vs. v16:
  * `detect_aps` keeps the half-width / SNR / rise-time / 30%-of-max-SNR
    chain from the SCS notebook (the STA version was a one-liner copy with
    no fallback). APD50_MAX is harmonised to 10 samples (20 ms).
  * `preprocess` is identical to both v14 versions but defined once.
  * New helpers `load_stim_meta`, `select_in_mask_sources`, `nearest_stim_frame`
    consume the JSON metadata produced by SCS_MovieSplit_v17.m.
"""

from __future__ import annotations

import json
import os
import warnings
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter

warnings.filterwarnings("ignore")

# ============================================================================
# Constants  (defaults — every function accepts overrides)
# ============================================================================
FS            = 500    # Hz, FireflyOne sample rate
APD50_MAX     = 5     # samples (20 ms) — AP half-width gate
SNR_GATE      = 3.5    # minimum local SNR for AP detection
AP_RISE_MAX   = 20.0   # ms — maximum AP rise time
AP_SNR_FRAC   = 0.30   # AP must be >= this * trace max SNR
PBR_THRESH    = 0.6    # peak-vs-baseline ratio threshold for AP


# ============================================================================
# 1. Segment detection from NaN gaps
# ============================================================================
def detect_segments(time_or_col0) -> List[Tuple[int, int]]:
    """Infer segment boundaries (inclusive) from NaN gaps in a 1-D array."""
    arr   = np.asarray(time_or_col0, dtype=float)
    valid = np.where(~np.isnan(arr))[0]
    if len(valid) == 0:
        return [(0, len(arr) - 1)]
    segs, start = [], int(valid[0])
    for i in range(1, len(valid)):
        if valid[i] - valid[i-1] > 1:
            segs.append((start, int(valid[i-1])))
            start = int(valid[i])
    segs.append((start, int(valid[-1])))
    return segs


# ============================================================================
# 2. Preprocessing  (1 Hz highpass + Savitzky-Golay smoothing, per-segment)
# ============================================================================
def preprocess(raw, segs, fs: int = FS) -> np.ndarray:
    """Return a denoised float trace, NaN-padded outside detected segments."""
    raw   = np.asarray(raw, dtype=float)
    out   = np.full(len(raw), np.nan)
    b, a  = butter(2, 1.0 / (fs / 2), btype="high")
    for s, e in segs:
        seg = raw[s:e+1].astype(float)
        if np.any(np.isnan(seg)):
            valid = np.where(~np.isnan(seg))[0]
            if len(valid) == 0:
                continue
            seg = np.interp(np.arange(len(seg)), valid, seg[valid])
        out[s:e+1] = filtfilt(b, a, seg)
    valid_idx = np.where(~np.isnan(out))[0]
    if len(valid_idx) > 5:
        interp = np.interp(np.arange(len(out)), valid_idx, out[valid_idx])
        smooth = savgol_filter(interp, window_length=5, polyorder=3)
        out[valid_idx] = smooth[valid_idx]
    return out


# ============================================================================
# 3. Global signal regression  (population common-mode removal)
# ============================================================================
def regress_global_signal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove the population-wide common-mode signal from every trace.

    Computes the cross-neuron mean at each timepoint (global signal), then
    for each trace fits:  trace = a * global + b + residual
    and returns the residuals.  Removes shared hemodynamic fluctuations,
    network-wide co-activation, and residual optical crosstalk not handled
    by the MATLAB splitter.

    Parameters
    ----------
    df : DataFrame, shape (n_samples, n_sources), columns T1..TN.

    Returns
    -------
    DataFrame — same shape and columns, values replaced by residuals.
    """
    mat        = df.values.astype(float)                    # (n_samples, n_sources)
    global_sig = np.nanmean(mat, axis=1)                    # (n_samples,)
    X          = np.column_stack([global_sig, np.ones(len(global_sig))])
    corrected  = mat.copy()
    for col in range(mat.shape[1]):
        y     = mat[:, col]
        valid = np.isfinite(y) & np.isfinite(global_sig)
        if valid.sum() < 2:
            continue
        coeffs, *_ = np.linalg.lstsq(X[valid], y[valid], rcond=None)
        corrected[:, col] = y - X @ coeffs
    return pd.DataFrame(corrected, columns=df.columns)


# ============================================================================
# 4. Noise / local statistics
# ============================================================================
def _noise_std(trace, segs) -> float:
    """Robust global noise estimate (MAD/0.6745) across all valid samples."""
    vals = []
    for s, e in segs:
        seg = trace[s:e+1]
        seg = seg[~np.isnan(seg)]
        if len(seg) > 10:
            vals.extend(seg.tolist())
    if not vals:
        return 1.0
    v = np.array(vals)
    return max(np.median(np.abs(v - np.median(v))) / 0.6745, 1e-6)


def _local_stats(raw, peak_idx: int, fs: int = FS):
    """
    Local baseline / noise / SNR / rise time around a candidate AP.

    Returns
    -------
    local_base, local_noise, local_snr, rise_samp, rise_ms
    """
    base_seg = raw[max(0, peak_idx-80):max(0, peak_idx-40)]
    base_seg = base_seg[~np.isnan(base_seg)]
    if len(base_seg) < 20:
        post_start = min(len(raw)-1, peak_idx + 200)
        post_end   = min(len(raw),   peak_idx + 500)
        base_seg   = raw[post_start:post_end]
        base_seg   = base_seg[~np.isnan(base_seg)]

    local_base  = float(np.nanmedian(base_seg)) if len(base_seg) > 0 else 0.0
    local_noise = (np.median(np.abs(base_seg - local_base)) / 0.6745
                   if len(base_seg) > 2 else 1e-6)
    local_noise = max(float(local_noise), 1e-6)

    amp_local = float(raw[peak_idx]) - local_base
    local_snr = amp_local / local_noise

    level_20 = local_base + 0.2 * amp_local
    foot     = peak_idx
    limit    = max(0, peak_idx - 10)
    while foot > limit and raw[foot] > level_20:
        foot -= 1
    rise_samp = peak_idx - foot
    rise_ms   = rise_samp / fs * 1000.0
    return local_base, local_noise, local_snr, rise_samp, rise_ms


# ============================================================================
# Per-neuron SNR (post-hoc, from stored traces and AP indices)
# ============================================================================
def compute_neuron_snr(traces_all: dict, aps_all: dict,
                       snr_gate: float = 10.0,
                       fs: int = FS) -> tuple:
    """
    Compute per-neuron mean AP SNR from stored traces and AP indices.

    All returned APs already passed SNR_GATE=3.5 during detect_aps, so
    snr_gate here should be set higher (default 10.0) to meaningfully
    distinguish recording quality across FOVs.

    Returns
    -------
    mean_snr  : {neuron_id: float}  — mean SNR across all detected APs
    above_gate: {neuron_id: bool}   — True if mean SNR >= snr_gate
    """
    mean_snr: dict = {}
    above_gate: dict = {}
    for tid, aps in aps_all.items():
        raw = traces_all.get(tid)
        if raw is None or len(aps) == 0:
            continue
        snrs = []
        for ap in aps:
            try:
                _, _, s, _, _ = _local_stats(raw, int(ap), fs=fs)
                snrs.append(s)
            except Exception:
                pass
        if snrs:
            m = float(np.mean(snrs))
            mean_snr[tid]   = m
            above_gate[tid] = m >= snr_gate
    return mean_snr, above_gate


# ============================================================================
# 4. AP detection
# ============================================================================
def detect_aps(trace, segs, raw=None,
               apd50_max: int = APD50_MAX,
               snr_gate: float = SNR_GATE,
               ap_rise_max: float = AP_RISE_MAX,
               ap_snr_frac: float = AP_SNR_FRAC,
               pbr_thresh: float = PBR_THRESH,
               fs: int = FS) -> np.ndarray:
    """
    Voltage-imaging AP detector. Five sequential filters:

      F1. Global MAD threshold     :  peak > median + 3 * noise
      F2. APD50 width              :  half-width <= apd50_max samples
      F3. Peak-vs-baseline ratio   :  pre-window max / amp <= pbr_thresh
      F4. Local SNR & rise time    :  SNR >= snr_gate, rise <= ap_rise_max ms
      F5. Relative SNR             :  >= ap_snr_frac of trace max SNR
    """
    if raw is None:
        raw = trace
    raw = np.asarray(raw, dtype=float)

    noise = _noise_std(trace, segs)
    av    = np.concatenate([trace[s:e+1] for s, e in segs])
    av    = av[~np.isnan(av)]
    if len(av) == 0:
        return np.array([], dtype=int)
    thr = float(np.median(av)) + 3.0 * noise

    # F1
    cands = []
    for s, e in segs:
        seg = trace[s:e+1]
        pk, _ = find_peaks(seg, height=thr, distance=10)
        cands.extend([(int(p + s), float(seg[p])) for p in pk])
    if not cands:
        return np.array([], dtype=int)

    # F2 — half-width
    p2 = []
    for idx, amp in cands:
        h = amp / 2.0
        l, r = idx, idx
        while l > 0 and trace[l] > h:
            l -= 1
        while r < len(trace) - 1 and trace[r] > h:
            r += 1
        if (r - l) <= apd50_max:
            p2.append((idx, amp))
    if not p2:
        return np.array([], dtype=int)

    # F3 — peak-vs-baseline ratio
    p3 = []
    for idx, amp in p2:
        pw = trace[max(0, idx-15):max(0, idx-4)]
        pw = pw[~np.isnan(pw)]
        ratio = float(np.max(pw) / amp) if len(pw) > 0 else 0.0
        if ratio <= pbr_thresh:
            p3.append((idx, amp))
    if not p3:
        return np.array([], dtype=int)

    # F4 — local SNR + rise time on RAW trace
    p4 = []
    for idx, _ in p3:
        _, _, local_snr, _, rise_ms = _local_stats(raw, idx, fs=fs)
        if local_snr >= snr_gate and rise_ms <= ap_rise_max:
            p4.append((idx, local_snr))
    if not p4:
        return np.array([], dtype=int)

    # F5 — relative SNR
    mx = max(s for _, s in p4)
    return np.array(sorted(idx for idx, s in p4 if s >= ap_snr_frac * mx),
                    dtype=int)


# ============================================================================
# 5. Duplicate trace detection
# ============================================================================
def find_duplicate_neurons(df_or_path) -> set:
    """
    Identify columns whose values are identical to an earlier column. Returns
    the set of duplicate (1-based) column indices. Accepts either a CSV path
    or a pre-loaded DataFrame.
    """
    if isinstance(df_or_path, str):
        df = (pd.read_csv(df_or_path) if df_or_path.endswith(".csv")
              else pd.read_excel(df_or_path))
    else:
        df = df_or_path
    n = df.shape[1]
    keep, checked = set(range(1, n+1)), set()
    for t1 in range(1, n+1):
        if t1 in checked:
            continue
        r1 = df[df.columns[t1-1]].values.astype(float)
        for t2 in range(t1+1, n+1):
            if t2 in checked:
                continue
            r2 = df[df.columns[t2-1]].values.astype(float)
            if np.allclose(r1, r2, equal_nan=True, atol=1e-10):
                keep.discard(t2)
                checked.add(t2)
    return set(range(1, n+1)) - keep


# ============================================================================
# 6. Stim metadata loader (consumes SCS_MovieSplit_v17.m JSON output)
# ============================================================================

# 6b. New dmd file digestion after 5/7/26
def load_ensemble_mask_sidecar(mat_path: str) -> dict:
      import scipy.io
      try:
          mat = scipy.io.loadmat(mat_path, squeeze_me=True, struct_as_record=False)
      except NotImplementedError:
          raise IOError(f"File may be MATLAB v7.3 — install mat73 and use mat73.loadmat")
      sc = mat['ensembleMaskSidecar']
      return dict(
          n_masks                = int(sc.nMasks),
          ordering_of_masks      = np.asarray(sc.orderingOfMasks, dtype=int).flatten(),
          mask_step_index        = int(sc.maskStepIndex),
          barcode_matrix         = np.asarray(sc.ensembleNeuronBarcodeMatrix, dtype=bool),
          fov_seed               = float(sc.fovSeed),
          mask_dilation_radius_px= int(sc.maskDilationRadiusPx),
          mask_stack             = np.asarray(mat['dmdMaskStack'], dtype=bool),
          mask_pixel_idx         = mat['dmdMaskPixelIdx'],
      )

def stim_mask_from_mat(sidecar: dict, meta: dict) -> dict:
      """
      Returns {trace_id: bool} — True if neuron centroid is among the N closest to any
      DMD mask pixel, where N = number of rows in barcode_matrix (i.e. the known stim count).

      Uses a distance transform so the result is robust to small coordinate offsets between
      the DMD pixel space and the stim_meta centroid space.
      """
      from scipy.ndimage import distance_transform_edt
      mask_stack = sidecar.get('mask_stack')
      if mask_stack is None:
          return {}
      c_rows = np.asarray(meta.get('source_centroid_row', []), dtype=float)
      c_cols = np.asarray(meta.get('source_centroid_col', []), dtype=float)
      if len(c_rows) == 0:
          return {}
      mask_any = mask_stack.any(axis=2)   # (H, W) — any pixel lit in any pattern
      H, W = mask_any.shape
      dist = distance_transform_edt(~mask_any)   # distance of each pixel to nearest lit pixel

      # distance from each neuron centroid to the nearest mask pixel
      neuron_dist = {}
      for i in range(len(c_rows)):
          if np.isnan(c_rows[i]) or np.isnan(c_cols[i]):
              continue
          r, c = int(round(c_rows[i])), int(round(c_cols[i]))
          if 0 <= r < H and 0 <= c < W:
              neuron_dist[i + 1] = float(dist[r, c])

      # take the N closest neurons where N = barcode_matrix row count (known stim count)
      n_stim = int(sidecar['barcode_matrix'].shape[0])
      sorted_ids = sorted(neuron_dist, key=neuron_dist.get)
      stim_set = set(sorted_ids[:n_stim])
      return {i + 1: (i + 1 in stim_set) for i in range(len(c_rows))}


def load_stim_meta(meta_path: str) -> dict:
    """
    Load and lightly normalise a stim_meta.json file written by the v17 splitter.

    The v17 splitter (multi-protocol-step aware, with CorrectSourceTrace) produces a JSON that flags
    which protocol steps the FOV had. Fields used downstream:

        spont_present, stim_present : bool — which CSVs to expect
        spont_step_name, stim_step_name : str (when present)
        spont_n_samples, spont_split_local : int — for the spont CSV halves
        stim_n_samples,  stim_split_local  : int — for the stim CSV halves
        stim_mask_sources : np.ndarray of int (1-indexed source IDs)
        stim_frames_part1, stim_frames_part2 : np.ndarray, part-local 1-indexed

    Legacy fields (per-source stim frames, blob_row/col, source_blob_id) are
    kept around but only filled when present in the JSON, so older outputs
    written by an earlier splitter still load cleanly.
    """
    if not os.path.exists(meta_path):
        return _empty_stim_meta()

    with open(meta_path, "r") as fh:
        m = json.load(fh)

    def _arr(x, dtype=None):
        if x is None: return np.array([], dtype=dtype or int)
        a = np.atleast_1d(np.asarray(x))
        return a.astype(dtype) if dtype else a

    out = dict(m)
    out["spont_present"]     = bool(m.get("spont_present", False))
    out["stim_present"]      = bool(m.get("stim_present", False))
    out["stim_mask_sources"] = _arr(m.get("stim_mask_sources", []), int)
    out["stim_frames_part1"] = _arr(m.get("stim_frames_part1", []), int)
    out["stim_frames_part2"] = _arr(m.get("stim_frames_part2", []), int)

    out["source_centroid_row"] = _arr(m.get("source_centroid_row", []), float)
    out["source_centroid_col"] = _arr(m.get("source_centroid_col", []), float)

    out["source_blob_id"] = _arr(m.get("source_blob_id", []))
    out["blob_row"]       = _arr(m.get("blob_row", []))
    out["blob_col"]       = _arr(m.get("blob_col", []))
    per_src = m.get("stim_frames_per_source", {}) or {}
    norm = {}
    for k, v in per_src.items():
        src_key = k[1:]
        norm[src_key] = {
            "part1": _arr(v.get("part1", []), int),
            "part2": _arr(v.get("part2", []), int),
        }
    out["stim_frames_per_source"] = norm
    return out


def _empty_stim_meta() -> dict:
    return {
        "fov": "",
        "fs": FS,
        "n_sources": 0,
        "spont_present": False,
        "stim_present": False,
        "spont_n_samples": 0,
        "spont_split_local": 0,
        "stim_n_samples": 0,
        "stim_split_local": 0,
        "stim_mask_sources": np.array([], dtype=int),
        "stim_frames_part1": np.array([], dtype=int),
        "stim_frames_part2": np.array([], dtype=int),
        "source_centroid_row": np.array([], dtype=float),
        "source_centroid_col": np.array([], dtype=float),
        "source_blob_id": np.array([]),
        "blob_row": np.array([]),
        "blob_col": np.array([]),
        "stim_frames_per_source": {},
    }


def select_in_mask_sources(meta: dict) -> set:
    """Set of (1-indexed) source IDs flagged as inside the stim mask."""
    return set(int(x) for x in meta.get("stim_mask_sources", []))


def stim_locked_aps(ap_indices: np.ndarray,
                    stim_frames: np.ndarray,
                    window_samples: int = 5) -> np.ndarray:
    """Subset of `ap_indices` within +/- window_samples of any frame in `stim_frames`."""
    if len(ap_indices) == 0 or len(stim_frames) == 0:
        return np.array([], dtype=int)
    ap = np.asarray(ap_indices, dtype=int)
    sf = np.sort(np.asarray(stim_frames, dtype=int))
    pos = np.searchsorted(sf, ap)
    pos = np.clip(pos, 1, len(sf) - 1)
    left  = sf[pos - 1]
    right = sf[np.minimum(pos, len(sf) - 1)]
    nearest = np.where(np.abs(ap - left) <= np.abs(ap - right), left, right)
    keep = np.abs(ap - nearest) <= window_samples
    return ap[keep]


def ap_count_table(aps_all):
    return pd.DataFrame(
        [{"trace": t, "n_ap": int(len(v))} for t, v in sorted(aps_all.items())]
    )


# ============================================================================
# AP shape features  (mirrors Quiver's GetNextSpikeShape)
# ============================================================================
def compute_ap_shape(raw, ap_idx: int, fs: int = FS,
                     pre_window_ms: float = 15.0,
                     post_window_ms: float = 100.0) -> Optional[dict]:
    """
    Extract spike shape features from the raw voltage trace at one AP.

    Mirrors Quiver's GetNextSpikeShape feature set:
      amplitude    — peak − threshold  (threshold = preMaxConcavity)
      rise_time_ms — threshold → peak
      half_width_ms — width at 50% of spike height  (AP50)
      width_80_ms   — width at 80%  (AP80 — Quiver's shape.width)
      max_dv_dt    — peak rate of rise  (V/s equivalent)
      min_dv_dt    — peak rate of repolarization (negative)
      ahp_depth    — AHP minimum − threshold
      ahp_time_ms  — peak → AHP minimum
      snr          — amplitude / local noise (from _local_stats)

    Width fractions follow Quiver's interpWidth convention:
      level = max(thresh_v, ahp_v) * frac  +  peak_v * (1 − frac)

    Returns None if the window is too short, contains NaNs, or the AP
    cannot be bracketed.
    """
    pre_samp  = int(pre_window_ms  / 1000 * fs)
    post_samp = int(post_window_ms / 1000 * fs)
    n1 = max(0, ap_idx - pre_samp)
    n2 = min(len(raw) - 1, ap_idx + post_samp)

    if n2 - n1 < 5:
        return None
    seg = raw[n1:n2 + 1].astype(float)
    if np.any(np.isnan(seg)):
        return None

    ap_rel = ap_idx - n1

    # Refine peak to nearest sample
    search = slice(max(0, ap_rel - 3), min(len(seg), ap_rel + 4))
    peak_rel = int(np.argmax(seg[search])) + search.start
    peak_v   = float(seg[peak_rel])

    if peak_rel == 0:
        return None

    # Derivatives (per-sample units, scaled to per-second below)
    dv  = np.gradient(seg)
    d2v = np.gradient(dv)

    # Threshold: max of second derivative on the rising phase (preMaxConcavity)
    thresh_rel = int(np.argmax(d2v[:peak_rel]))
    thresh_v   = float(seg[thresh_rel])

    amplitude = peak_v - thresh_v
    if amplitude <= 0:
        return None

    rise_time_ms = (peak_rel - thresh_rel) / fs * 1000.0

    # dV/dt scaled to per-second
    scale = float(fs)
    max_dv_dt = (float(np.max(dv[thresh_rel:peak_rel + 1])) * scale
                 if peak_rel > thresh_rel else np.nan)
    fall_end  = min(len(seg), peak_rel + int(0.05 * fs))
    min_dv_dt = (float(np.min(dv[peak_rel:fall_end])) * scale
                 if fall_end > peak_rel + 1 else np.nan)

    # AHP: minimum voltage after peak in the post-window
    post_v = seg[peak_rel:]
    if len(post_v) < 2:
        ahp_v = ahp_depth = ahp_time_ms = np.nan
    else:
        ahp_idx = int(np.argmin(post_v))
        ahp_v   = float(post_v[ahp_idx])
        ahp_depth   = ahp_v - thresh_v
        ahp_time_ms = ahp_idx / fs * 1000.0

    # Width at fractional height (Quiver interpWidth convention)
    def _interp_width_ms(frac: float) -> float:
        bottom = max(thresh_v, ahp_v if np.isfinite(ahp_v) else thresh_v)
        level  = bottom * frac + peak_v * (1.0 - frac)

        # Rising phase: last sample ≤ level before peak
        rising = seg[:peak_rel + 1]
        below  = np.where(rising <= level)[0]
        if len(below) == 0 or below[-1] + 1 > peak_rel:
            return np.nan
        iF1 = below[-1]
        yF1, yF2 = rising[iF1], rising[iF1 + 1]
        if yF2 <= yF1:
            return np.nan
        iF = iF1 + (level - yF1) / (yF2 - yF1)

        # Falling phase: first sample ≤ level after peak
        falling = seg[peak_rel:]
        below_f = np.where(falling <= level)[0]
        if len(below_f) == 0 or below_f[0] == 0:
            return np.nan
        iB2 = below_f[0]
        yB1, yB2 = falling[iB2 - 1], falling[iB2]
        if yB1 <= yB2:
            return np.nan
        iB = iB2 - 1 + (level - yB1) / (yB2 - yB1)

        return (peak_rel + iB - iF) / fs * 1000.0

    half_width_ms = _interp_width_ms(0.5)
    width_80_ms   = _interp_width_ms(0.8)

    _, _, snr, _, _ = _local_stats(raw, ap_idx, fs=fs)

    return dict(
        amplitude     = amplitude,
        rise_time_ms  = rise_time_ms,
        half_width_ms = half_width_ms,
        width_80_ms   = width_80_ms,
        max_dv_dt     = max_dv_dt,
        min_dv_dt     = min_dv_dt,
        ahp_depth     = ahp_depth,
        ahp_time_ms   = ahp_time_ms,
        snr           = snr,
    )


def mean_ap_shape(raw, ap_indices, fs: int = FS) -> dict:
    """
    Spike shape features extracted from the mean AP waveform across all events.
    Averaging before feature extraction reduces noise-driven jitter in
    threshold-crossing measurements (rise time, widths, AHP timing).
    SNR is kept as mean-of-individuals since it is a per-event metric.
    """
    _keys = ('amplitude', 'rise_time_ms', 'half_width_ms', 'width_80_ms',
             'max_dv_dt', 'min_dv_dt', 'ahp_depth', 'ahp_time_ms', 'snr')

    pre_samp  = int(15.0  / 1000 * fs)
    post_samp = int(100.0 / 1000 * fs)

    windows  = []
    snr_vals = []
    for ap in ap_indices:
        n1, n2 = int(ap) - pre_samp, int(ap) + post_samp
        if n1 < 0 or n2 >= len(raw):
            continue
        windows.append(raw[n1:n2 + 1].astype(float))
        s = compute_ap_shape(raw, int(ap), fs=fs)
        if s is not None:
            snr_vals.append(s['snr'])

    if not windows:
        return {k: np.nan for k in _keys}

    mean_wave = np.mean(windows, axis=0)
    shape = compute_ap_shape(mean_wave, pre_samp, fs=fs)
    if shape is None:
        return {k: np.nan for k in _keys}

    shape['snr'] = float(np.mean(snr_vals)) if snr_vals else np.nan
    return shape
