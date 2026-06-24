"""
scs_utils.py — pipeline v17, discrete-event PSP-pairing branch.

Detects discrete EPSP / IPSP events in each post-synaptic trace, then pairs
each event back to a pre-synaptic AP that fired within `psp_window` samples.
Scores per-pair pairing rate against a precomputed binomial-style table."""


from __future__ import annotations

import os
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from .data_utils import (
    FS, _local_stats, _noise_std, detect_aps, detect_segments,
    find_duplicate_neurons, preprocess, regress_global_signal,
)
from .sta_utils import PRE_AP_BLANK, WIN_LEN


# ============================================================================
# Constants — pipeline v17
# ============================================================================
AHP_BLANK         = 50      # samples (100 ms) — post-neuron own-AP AHP exclusion
PSP_WINDOW        = 75      # samples (150 ms) — pairing window after pre-AP
EPSP_WINDOW       = PSP_WINDOW
IPSP_WINDOW       = 150    # doubled window allowing for slow IPSPs
EPSP_DUR_MIN      = 20.0    # ms — EPSP minimum half-max duration
IPSP_DUR_MIN      = 20.0    # ms — IPSP minimum half-max duration
ONSET_MIN_MS      = 10.0     # ms — minimum pre-AP -> PSP window onset
MIN_ABOVE_THR_MS  = 20.0    # ms smoothed signal must remain above threshold

PEAK_WIN_MS       = 20      # smoothing window for peak detection (ms)
PEAK_DIST_MS      = 50      # minimum distance between detected peaks (ms)
PEAK_THR_MULT     = 3.0     # threshold multiplier (× noise)
EPSP_AMP_THR_MULT = 1.5     # EPSP amplitude floor (× global noise) — shared by
                             # detect_epsps AND detect_epsps_morphological; change here
PRE_CONTEXT_MS    = 100     # pre-AP context for detrending (ms)
POST_CONTEXT_MS   = 100     # post-window context for detrending (ms)
AP_UNDERSHOOT_RATIO = 3.0   # reject IPSP candidate if preceding positive peak > this × trough depth

SCORE_THRESH      = 0.7     # default score threshold (lookup-table units)


# ============================================================================
# Detrending helpers
# ============================================================================
def _rolling_avg_fast(arr, win_samples):
    half   = max(1, win_samples // 2)
    cs     = np.concatenate([[0], np.cumsum(arr)])
    starts = np.maximum(0, np.arange(len(arr)) - half)
    ends   = np.minimum(len(arr), np.arange(len(arr)) + half + 1)
    return (cs[ends] - cs[starts]) / (ends - starts)


# Old rolling-avg implementation (replaced by savgol below — kept for reference):
# def _detrend_and_smooth(arr, fs=FS, peak_win_ms=PEAK_WIN_MS):
#     dwin      = len(arr)
#     pwin      = max(1, int(peak_win_ms / 1000 * fs))
#     trend     = _rolling_avg_fast(arr, dwin)
#     detrended = arr - trend
#     smoothed  = _rolling_avg_fast(detrended, pwin)
#     return smoothed, detrended, trend

# TESTING SAVGOL DETREND
from scipy.signal import savgol_filter

def _detrend_and_smooth(arr, fs=FS, peak_win_ms=PEAK_WIN_MS):
    dwin      = len(arr)
    pwin      = max(1, int(peak_win_ms / 1000 * fs))
    trend     = _rolling_avg_fast(arr, dwin)
    detrended = arr - trend
    # savgol requires window_length to be odd and > polyorder
    win_sg    = pwin if pwin % 2 == 1 else pwin + 1
    smoothed  = savgol_filter(detrended, window_length=win_sg, polyorder=2)
    return smoothed, detrended, trend




def _psp_context_window(ap, seg_s, seg_e, psp_window, fs,
                        onset_min_ms=ONSET_MIN_MS):
    onset_samp   = max(1, int(onset_min_ms / 1000 * fs))
    win_start    = ap + onset_samp
    win_end      = min(ap + psp_window, seg_e)
    pre_context  = max(seg_s, ap - int(PRE_CONTEXT_MS  / 1000 * fs))
    post_context = min(seg_e, win_end + int(POST_CONTEXT_MS / 1000 * fs))
    n_pre        = ap + 1 - pre_context
    n_pre_onset  = win_start - pre_context
    n_post       = win_end - win_start
    return win_start, win_end, pre_context, post_context, n_pre, n_pre_onset, n_post


# ============================================================================
# IPSP detection
# ============================================================================
# NOTE: detect_ipsps / detect_epsps and their morphological counterparts share
# all module-level constants above.  epsp_ap_frac (default 0.7) is a duplicated
# function-level default — if you tune it in one, update the other manually.
def detect_ipsps(trace, ap_indices, segs, own_ap_indices=None,
                 ahp_blank: int   = AHP_BLANK,
                 ipsp_window: int = IPSP_WINDOW,
                 ipsp_dur_min: float = IPSP_DUR_MIN,
                 onset_min_ms: float = ONSET_MIN_MS,
                 min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                 ap_peak_ratio: float = AP_UNDERSHOOT_RATIO,
                 fs: int = FS) -> np.ndarray:
    """Detect valid IPSP troughs in `trace` triggered by `ap_indices`."""
    if len(ap_indices) == 0:
        return np.array([], dtype=int)

    DUR_MIN_SAMP = int(ipsp_dur_min / 1000 * fs)
    dist_s       = max(1, int(PEAK_DIST_MS / 1000 * fs))

    if own_ap_indices is None:
        own_ap_indices = ap_indices
    own_aps_arr = np.asarray(sorted(own_ap_indices), dtype=int)

    def zero_crossing_extent(idx):
        s = idx
        while s > 0 and trace[s] < 0: s -= 1
        e = idx
        while e < len(trace) - 1 and trace[e] < 0: e += 1
        return s, e

    def merge_troughs(trough_list):
        if not trough_list: return []
        with_extents = [(idx, val, *zero_crossing_extent(idx))
                        for idx, val in trough_list]
        with_extents.sort(key=lambda x: x[2])
        merged = []
        cur_idx, cur_val, cur_s, cur_e = with_extents[0]
        for idx, val, s, e in with_extents[1:]:
            if s <= cur_e:
                cur_e = max(cur_e, e)
                if val < cur_val: cur_idx, cur_val = idx, val
            else:
                merged.append(cur_idx)
                cur_idx, cur_val, cur_s, cur_e = idx, val, s, e
        merged.append(cur_idx)
        return merged

    all_candidates = []
    for seg_s, seg_e in segs:
        seg_aps = ap_indices[(ap_indices >= seg_s) & (ap_indices <= seg_e)]
        for ap in seg_aps:
            ws, we, pre_ctx, post_ctx, _n_pre, n_pre_onset, n_post = \
                _psp_context_window(ap, seg_s, seg_e, ipsp_window, fs,
                                    onset_min_ms=onset_min_ms)
            if ws >= we or n_post <= 0:
                continue
            full_window = trace[pre_ctx:post_ctx]
            if np.all(np.isnan(full_window)):
                continue

            smoothed_full, _, _ = _detrend_and_smooth(full_window, fs=fs)
            smoothed = smoothed_full[n_pre_onset:n_pre_onset + n_post]

            noise_s    = max(np.median(np.abs(smoothed - np.median(smoothed))) / 0.6745, 1e-6)
            thr_s      = PEAK_THR_MULT * noise_s
            troughs, _ = find_peaks(-smoothed, height=thr_s, distance=dist_s)

            for tr in troughs:
                abs_idx = ws + tr

                # AHP exclusion
                if len(own_aps_arr) > 0:
                    preceding = own_aps_arr[own_aps_arr < abs_idx]
                    if len(preceding) > 0 and (abs_idx - preceding[-1]) <= ahp_blank:
                        continue

                # Duration floor on raw trace
                trough_val = trace[abs_idx]
                base_start = max(0, ap - int(PRE_CONTEXT_MS / 1000 * fs))
                base_end   = ap
                local_base = np.nanmedian(trace[base_start:base_end])

                # AP-undershoot exclusion: if a large positive peak immediately
                # precedes the trough (within ahp_blank), it is likely the
                # Ca²⁺ transient of a missed post-neuron AP, not a real IPSP.
                if ap_peak_ratio > 0:
                    pre_seg = trace[max(seg_s, abs_idx - ahp_blank):abs_idx]
                    if len(pre_seg) > 0:
                        pre_peak   = float(np.nanmax(pre_seg)) - local_base
                        trough_amp = local_base - float(trough_val)
                        if trough_amp > 0 and pre_peak > ap_peak_ratio * trough_amp:
                            continue

                half_level = local_base + 0.5 * (trough_val - local_base)
                left, right = abs_idx, abs_idx
                while left  > seg_s and trace[left]  < half_level: left  -= 1
                while right < seg_e and trace[right] < half_level: right += 1
                if (right - left) < DUR_MIN_SAMP:
                    continue

                # Threshold-crossing duration on smoothed signal
                arr_local = -smoothed
                left, right = tr, tr
                while left  > 0                 and arr_local[left]  > thr_s: left  -= 1
                while right < len(arr_local)-1  and arr_local[right] > thr_s: right += 1
                if left == 0 and arr_local[0] > thr_s:
                    continue
                if (right - left) < max(1, int(min_above_thr_ms / 1000 * fs)):
                    continue
                if right >= len(arr_local) - 1:
                    continue

                all_candidates.append((abs_idx, trough_val))

    seen = {}
    for idx, val in all_candidates:
        if idx not in seen or val < seen[idx]:
            seen[idx] = val
    unique_candidates = sorted(seen.items(), key=lambda x: x[0])
    events = merge_troughs(unique_candidates)
    return np.array(sorted(set(events)), dtype=int)


# ============================================================================
# EPSP detection
# ============================================================================
def detect_epsps(trace, ap_indices, segs, own_ap_indices=None, raw=None,
                 ahp_blank: int   = AHP_BLANK,
                 epsp_window: int = EPSP_WINDOW,
                 epsp_dur_min: float = EPSP_DUR_MIN,
                 onset_min_ms: float = ONSET_MIN_MS,
                 min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                 fs: int = FS,
                 epsp_ap_frac: float = 0.7) -> np.ndarray:
    """Detect valid EPSP peaks in `trace` triggered by `ap_indices`."""
    if len(ap_indices) == 0:
        return np.array([], dtype=int)

    raw_ref      = raw if raw is not None else trace
    noise        = _noise_std(trace, segs)
    epsp_thr     = EPSP_AMP_THR_MULT * noise
    DUR_MIN_SAMP = int(epsp_dur_min / 1000 * fs)
    dist_s       = max(1, int(PEAK_DIST_MS / 1000 * fs))

    ap_amps = []
    if own_ap_indices is not None and len(own_ap_indices) > 0:
        for ap_idx in own_ap_indices:
            _, local_base, _, _, _ = _local_stats(raw_ref, int(ap_idx), fs=fs)
            ap_amps.append(raw_ref[int(ap_idx)] - local_base)
    epsp_amp_max = (np.median(ap_amps) * epsp_ap_frac) if ap_amps else np.inf

    own_aps_arr = np.asarray(sorted(own_ap_indices if own_ap_indices is not None
                                    else ap_indices), dtype=int)

    events = []
    for seg_s, seg_e in segs:
        seg_aps = ap_indices[(ap_indices >= seg_s) & (ap_indices <= seg_e)]
        for ap in seg_aps:
            ws, we, pre_ctx, post_ctx, _n_pre, n_pre_onset, n_post = \
                _psp_context_window(ap, seg_s, seg_e, epsp_window, fs,
                                    onset_min_ms=onset_min_ms)
            if ws >= we or n_post <= 0:
                continue
            full_window = trace[pre_ctx:post_ctx]
            if np.all(np.isnan(full_window)):
                continue

            smoothed_full, _, _ = _detrend_and_smooth(full_window, fs=fs)
            smoothed = smoothed_full[n_pre_onset:n_pre_onset + n_post]

            noise_s  = max(np.median(np.abs(smoothed - np.median(smoothed))) / 0.6745, 1e-6)
            thr_s    = PEAK_THR_MULT * noise_s
            peaks, _ = find_peaks(smoothed, height=thr_s, distance=dist_s)

            for pk in peaks:
                abs_idx = ws + pk
                amp     = trace[abs_idx]

                # AHP exclusion
                if len(own_aps_arr) > 0:
                    preceding = own_aps_arr[own_aps_arr < abs_idx]
                    if len(preceding) > 0 and (abs_idx - preceding[-1]) <= ahp_blank:
                        continue

                # Amplitude floor / ceiling
                if amp < epsp_thr or amp > epsp_amp_max:
                    continue

                # Duration floor on raw trace
                base_start = max(0, ap - int(PRE_CONTEXT_MS / 1000 * fs))
                base_end   = ap
                local_base = np.nanmedian(raw_ref[base_start:base_end])
                half_level = local_base + 0.5 * (raw_ref[abs_idx] - local_base)
                left, right = abs_idx, abs_idx
                while left  > seg_s and raw_ref[left]  > half_level: left  -= 1
                while right < seg_e and raw_ref[right] > half_level: right += 1
                if (right - left) < DUR_MIN_SAMP:
                    continue

                # Threshold-crossing duration on smoothed signal
                left, right = pk, pk
                while left  > 0              and smoothed[left]  > thr_s: left  -= 1
                while right < len(smoothed)-1 and smoothed[right] > thr_s: right += 1
                if left == 0 and smoothed[0] > thr_s:
                    continue
                if (right - left) < max(1, int(min_above_thr_ms / 1000 * fs)):
                    continue
                if right >= len(smoothed) - 1:
                    continue

                events.append(abs_idx)

    return np.array(sorted(set(events)), dtype=int)


# ============================================================================
# Morphological PSP detectors  (no presynaptic AP trigger required)
#
# Complementary to detect_epsps / detect_ipsps — find PSP-shaped deflections
# anywhere in the trace, including those driven by extra-FOV neurons whose APs
# are not visible. Own-AP windows and AHPs are blanked before scanning.
# ============================================================================

# NOTE: morphological detectors share all module-level constants with their
# AP-triggered counterparts.  epsp_ap_frac (default 0.7) is a duplicated
# function-level default — tune in both places if you change it.
def detect_epsps_morphological(trace, segs, own_ap_indices=None, raw=None,
                                ahp_blank: int         = AHP_BLANK,
                                epsp_dur_min: float    = EPSP_DUR_MIN,
                                min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                                fs: int                = FS,
                                epsp_ap_frac: float    = 0.7) -> np.ndarray:
    """
    Morphological EPSP detector — no presynaptic AP required.

    Scans the full trace for positive PSP-shaped deflections using the same
    amplitude, duration, and shape gates as detect_epsps, but without
    constraining to windows after a specific presynaptic AP.  Blanks a window
    around each of the post-neuron's own APs (AP + AHP) before scanning.

    Use alongside detect_epsps to capture synaptic input from extra-FOV
    sources as well as within-FOV sources.
    """
    raw_ref      = raw if raw is not None else trace
    noise        = _noise_std(trace, segs)
    epsp_thr     = EPSP_AMP_THR_MULT * noise
    DUR_MIN_SAMP = int(epsp_dur_min / 1000 * fs)
    dist_s       = max(1, int(PEAK_DIST_MS / 1000 * fs))
    pre_ctx_samp = int(PRE_CONTEXT_MS / 1000 * fs)

    own_aps_arr = np.asarray(sorted(own_ap_indices if own_ap_indices is not None
                                    else []), dtype=int)

    # AP amplitude ceiling — same logic as detect_epsps
    ap_amps = []
    for ap_idx in own_aps_arr:
        _, local_base, _, _, _ = _local_stats(raw_ref, int(ap_idx), fs=fs)
        ap_amps.append(raw_ref[int(ap_idx)] - local_base)
    epsp_amp_max = float(np.median(ap_amps) * epsp_ap_frac) if ap_amps else np.inf

    # Build a boolean valid mask: False inside own-AP / AHP windows
    valid_mask = np.ones(len(trace), dtype=bool)
    for ap in own_aps_arr:
        valid_mask[max(0, ap - pre_ctx_samp): min(len(trace), ap + ahp_blank)] = False

    events = []
    for seg_s, seg_e in segs:
        seg      = trace[seg_s:seg_e + 1].copy()
        seg_valid = valid_mask[seg_s:seg_e + 1]

        if seg_valid.sum() < DUR_MIN_SAMP:
            continue

        # Fill invalid samples with local median so detrending isn't disrupted
        seg_filled = seg.copy()
        seg_filled[~seg_valid] = np.nanmedian(seg[seg_valid])

        smoothed, _, _ = _detrend_and_smooth(seg_filled, fs=fs)

        valid_smoothed = smoothed[seg_valid]
        noise_s = max(np.median(np.abs(valid_smoothed - np.median(valid_smoothed))) / 0.6745, 1e-6)
        thr_s   = PEAK_THR_MULT * noise_s

        peaks, _ = find_peaks(smoothed, height=thr_s, distance=dist_s)

        for pk in peaks:
            abs_idx = seg_s + pk

            if not valid_mask[abs_idx]:
                continue

            amp = trace[abs_idx]
            if amp < epsp_thr or amp > epsp_amp_max:
                continue

            # Duration floor on raw trace
            local_base = np.nanmedian(raw_ref[max(0, abs_idx - pre_ctx_samp):abs_idx])
            half_level = local_base + 0.5 * (raw_ref[abs_idx] - local_base)
            left, right = abs_idx, abs_idx
            while left  > seg_s and raw_ref[left]  > half_level: left  -= 1
            while right < seg_e and raw_ref[right] > half_level: right += 1
            if (right - left) < DUR_MIN_SAMP:
                continue

            # Threshold-crossing duration on smoothed signal
            l_s, r_s = pk, pk
            while l_s > 0              and smoothed[l_s] > thr_s: l_s -= 1
            while r_s < len(smoothed)-1 and smoothed[r_s] > thr_s: r_s += 1
            if l_s == 0 and smoothed[0] > thr_s:
                continue
            if (r_s - l_s) < max(1, int(min_above_thr_ms / 1000 * fs)):
                continue
            if r_s >= len(smoothed) - 1:
                continue

            events.append(abs_idx)

    return np.array(sorted(set(events)), dtype=int)


def detect_ipsps_morphological(trace, segs, own_ap_indices=None,
                                ahp_blank: int          = AHP_BLANK,
                                ipsp_dur_min: float     = IPSP_DUR_MIN,
                                min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                                fs: int                 = FS) -> np.ndarray:
    """
    Morphological IPSP detector — no presynaptic AP required.

    Scans the full trace for negative PSP-shaped deflections (troughs) using
    the same duration and shape gates as detect_ipsps, without constraining to
    windows after a specific presynaptic AP.  Blanks own-AP / AHP windows
    before scanning.
    """
    DUR_MIN_SAMP = int(ipsp_dur_min / 1000 * fs)
    dist_s       = max(1, int(PEAK_DIST_MS / 1000 * fs))
    pre_ctx_samp = int(PRE_CONTEXT_MS / 1000 * fs)

    own_aps_arr = np.asarray(sorted(own_ap_indices if own_ap_indices is not None
                                    else []), dtype=int)

    valid_mask = np.ones(len(trace), dtype=bool)
    for ap in own_aps_arr:
        valid_mask[max(0, ap - pre_ctx_samp): min(len(trace), ap + ahp_blank)] = False

    events = []
    for seg_s, seg_e in segs:
        seg       = trace[seg_s:seg_e + 1].copy()
        seg_valid = valid_mask[seg_s:seg_e + 1]

        if seg_valid.sum() < DUR_MIN_SAMP:
            continue

        seg_filled = seg.copy()
        seg_filled[~seg_valid] = np.nanmedian(seg[seg_valid])

        smoothed, _, _ = _detrend_and_smooth(seg_filled, fs=fs)

        valid_smoothed = smoothed[seg_valid]
        noise_s = max(np.median(np.abs(valid_smoothed - np.median(valid_smoothed))) / 0.6745, 1e-6)
        thr_s   = PEAK_THR_MULT * noise_s

        troughs, _ = find_peaks(-smoothed, height=thr_s, distance=dist_s)

        for tr in troughs:
            abs_idx = seg_s + tr

            if not valid_mask[abs_idx]:
                continue

            # Duration floor (zero-crossing extent)
            trough_val = trace[abs_idx]
            local_base = np.nanmedian(trace[max(0, abs_idx - pre_ctx_samp):abs_idx])
            half_level = local_base + 0.5 * (trough_val - local_base)
            left, right = abs_idx, abs_idx
            while left  > seg_s and trace[left]  < half_level: left  -= 1
            while right < seg_e and trace[right] < half_level: right += 1
            if (right - left) < DUR_MIN_SAMP:
                continue

            # Threshold-crossing duration on smoothed signal
            arr_local = -smoothed
            l_s, r_s = tr, tr
            while l_s > 0              and arr_local[l_s] > thr_s: l_s -= 1
            while r_s < len(arr_local)-1 and arr_local[r_s] > thr_s: r_s += 1
            if l_s == 0 and arr_local[0] > thr_s:
                continue
            if (r_s - l_s) < max(1, int(min_above_thr_ms / 1000 * fs)):
                continue
            if r_s >= len(arr_local) - 1:
                continue

            events.append(abs_idx)

    return np.array(sorted(set(events)), dtype=int)


def detect_all_morphological_psps(traces_all: dict, aps_all: dict, segs: list,
                                   raws_all: Optional[dict] = None,
                                   ahp_blank: int          = AHP_BLANK,
                                   epsp_dur_min: float     = EPSP_DUR_MIN,
                                   ipsp_dur_min: float     = IPSP_DUR_MIN,
                                   min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                                   fs: int                 = FS) -> Tuple[dict, dict]:
    """
    Run morphological PSP detection on an arbitrary traces/APs dict.

    Shared by run_scs_pipeline (spontaneous) and run_one_fov (stim period via
    sta1).  Returns (epsps_morphological, ipsps_morphological), each a
    {trace_id: np.ndarray} of event sample indices.
    """
    epsps_morph: dict = {}
    ipsps_morph: dict = {}
    for t, trace in traces_all.items():
        raw     = raws_all.get(t) if raws_all else None
        own_aps = aps_all.get(t, np.array([], dtype=int))
        epsps_morph[t] = detect_epsps_morphological(
            trace, segs, own_ap_indices=own_aps, raw=raw,
            ahp_blank=ahp_blank, epsp_dur_min=epsp_dur_min,
            min_above_thr_ms=min_above_thr_ms, fs=fs)
        ipsps_morph[t] = detect_ipsps_morphological(
            trace, segs, own_ap_indices=own_aps,
            ahp_blank=ahp_blank, ipsp_dur_min=ipsp_dur_min,
            min_above_thr_ms=min_above_thr_ms, fs=fs)
    return epsps_morph, ipsps_morph


# ============================================================================
# Score table  (chance_p=0.05, sqrt(rate)-weighted binomial)
# ============================================================================
_SCORE_TABLE = np.array([
    [1.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.7, 2.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.5, 1.7, 3.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.4, 1.3, 2.9, 5.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.3, 1.0, 2.3, 4.0, 6.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.2, 0.9, 1.9, 3.3, 5.2, 7.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.2, 0.7, 1.6, 2.8, 4.4, 6.5, 9.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.2, 0.6, 1.4, 2.4, 3.8, 5.5, 7.7,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.5, 1.2, 2.1, 3.3, 4.8, 6.7, 8.9,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.5, 1.1, 1.9, 3.0, 4.3, 5.9, 7.9, 9.5,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.4, 0.9, 1.7, 2.7, 3.9, 5.3, 7.0, 9.0, 9.5,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.4, 0.9, 1.5, 2.4, 3.5, 4.8, 6.4, 8.2, 9.1, 9.6,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.3, 0.8, 1.4, 2.2, 3.2, 4.4, 5.8, 7.4, 8.8, 9.2, 9.6,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.3, 0.7, 1.3, 2.0, 2.9, 4.0, 5.3, 6.8, 8.5, 8.9, 9.3, 9.6,10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.3, 0.6, 1.2, 1.9, 2.7, 3.7, 4.9, 6.3, 7.9, 8.6, 8.9, 9.3, 9.7,10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.3, 0.6, 1.1, 1.7, 2.5, 3.5, 4.6, 5.8, 7.3, 8.3, 8.7, 9.0, 9.4, 9.7,10.0, 0.0, 0.0, 0.0, 0.0],
    [0.1, 0.2, 0.5, 1.0, 1.6, 2.3, 3.2, 4.3, 5.4, 6.8, 8.0, 8.4, 8.7, 9.1, 9.4, 9.7,10.0, 0.0, 0.0, 0.0],
    [0.1, 0.2, 0.5, 0.9, 1.5, 2.2, 3.0, 4.0, 5.1, 6.4, 7.8, 8.2, 8.5, 8.8, 9.1, 9.4, 9.7,10.0, 0.0, 0.0],
    [0.0, 0.2, 0.5, 0.9, 1.4, 2.0, 2.8, 3.7, 4.8, 6.0, 7.3, 7.9, 8.3, 8.6, 8.9, 9.2, 9.5, 9.7,10.0, 0.0],
    [0.0, 0.2, 0.4, 0.8, 1.3, 1.9, 2.6, 3.5, 4.5, 5.6, 6.9, 7.7, 8.1, 8.4, 8.7, 8.9, 9.2, 9.5, 9.7,10.0],
])


def compute_score(n_obs: int, n_ap: int) -> float:
    """Look up score from the binomial landscape table."""
    if n_obs == 0 or n_ap == 0:
        return 0.0
    n_obs = min(int(n_obs), int(n_ap))
    if n_ap <= 20:
        return float(_SCORE_TABLE[n_ap - 1, n_obs - 1])
    n_obs_scaled = max(1, round(n_obs / n_ap * 20))
    n_obs_scaled = min(n_obs_scaled, 20)
    return float(_SCORE_TABLE[19, n_obs_scaled - 1])


# ============================================================================
# Pairing & scoring
# ============================================================================
def get_all_pairs(aps_all, events_all, trace_nums, segs,
                  psp_window: int = PSP_WINDOW):
    """Return (pre, post, ap_idx, event_idx) tuples — one PSP per AP max."""
    pairs = []
    for seg_s, seg_e in segs:
        for pre in trace_nums:
            seg_aps = aps_all[pre]
            seg_aps = seg_aps[(seg_aps >= seg_s) & (seg_aps <= seg_e)]
            for post in trace_nums:
                if pre == post: continue
                evts = events_all.get(post, np.array([], dtype=int))
                evts = evts[(evts >= seg_s) & (evts <= seg_e)]
                for ap in seg_aps:
                    matches = evts[(evts >= ap + 1) & (evts <= ap + psp_window)]
                    if len(matches) > 0:
                        pairs.append((pre, post, int(ap), int(matches[0])))
    return pairs


def build_scores(aps_all, events_all, trace_nums, pairs, segs):
    scores = {}
    for pre in trace_nums:
        n_ap = len(aps_all[pre])
        for post in trace_nums:
            if pre == post: continue
            n_obs = sum(1 for p in pairs if p[0] == pre and p[1] == post)
            scores[(pre, post)] = compute_score(n_obs, n_ap)
    return scores


def resolve_conflicts(pairs, scores, max_claimants: int = 1):
    """Resolve PSP events claimed by multiple pre-neurons (keep top by score)."""
    claims = defaultdict(list)
    for p in pairs:
        claims[(p[1], p[3])].append(p)
    out = []
    for _, claimants in claims.items():
        if len(claimants) <= max_claimants:
            out.extend(claimants)
        else:
            top = sorted(claimants, key=lambda p: scores.get((p[0], p[1]), 0),
                         reverse=True)[:max_claimants]
            out.extend(top)
    return out


def classify_neuron_type(inh_scores, exc_scores, trace_nums,
                           thresh: float = SCORE_THRESH):
    types = {}
    for t in trace_nums:
        si = sum(s for (p, _), s in inh_scores.items() if p == t and s >= thresh)
        se = sum(s for (p, _), s in exc_scores.items() if p == t and s >= thresh)
        if si == 0 and se == 0:
            types[t] = "silent"
        elif si == se:
            types[t] = "na"
        elif se > si:
            types[t] = "exc"
        else:
            types[t] = "inh"
    return types


# ============================================================================
# Pipeline runner — SCS spontaneous-period analysis
# ============================================================================
def run_scs_pipeline(csv_path: str, label: str = "",
                     score_thresh: float = SCORE_THRESH,
                     output_dir: Optional[str] = None,
                     fs: int = FS,
                     ahp_blank: int = AHP_BLANK,
                     psp_window: int = PSP_WINDOW,
                     epsp_dur_min: float = EPSP_DUR_MIN,
                     ipsp_dur_min: float = IPSP_DUR_MIN,
                     onset_min_ms: float = ONSET_MIN_MS,
                     min_above_thr_ms: float = MIN_ABOVE_THR_MS,
                     ap_peak_ratio: float = AP_UNDERSHOOT_RATIO,
                     exclude_neurons: Optional[Sequence[int]] = None,
                     regress_global: bool = True) -> dict:
    """
    Run SCS event-pairing on a single spontaneous-period CSV.

    Fixes the v14 bug where the EPSP detection assignment was outside the
    AP-iteration loop (only the last neuron's EPSPs survived).
    """
    print("\n" + "=" * 60)
    print(f"SCS pipeline v17  |  {label or csv_path}")
    print("=" * 60)

    df       = pd.read_csv(csv_path)
    n_traces = df.shape[1]
    if regress_global:
        df = regress_global_signal(df)
        print(f"  Global signal regressed out ({n_traces} traces).")
    segs     = detect_segments(df.iloc[:, 0].values)
    print(f"Loaded {n_traces} traces, {len(segs)} segments.")

    dups = find_duplicate_neurons(df)
    excl = set(exclude_neurons or []) | dups
    if dups: print(f"Duplicates excluded: {sorted(dups)}")
    all_traces = [t for t in range(1, n_traces + 1) if t not in excl]

    # Pass 1 — preprocess and detect APs
    print("[AP detection]")
    traces_all, raws_all, aps_all = {}, {}, {}
    for t in all_traces:
        raw = df[df.columns[t-1]].values.astype(float)
        tr  = preprocess(raw, segs, fs=fs)
        traces_all[t] = tr
        raws_all[t]   = raw
        aps_all[t]    = detect_aps(tr, segs, raw=raw, fs=fs)
    print(f"  Active neurons: {sum(1 for t in all_traces if len(aps_all[t])>0)}/{len(all_traces)}")

    # Pass 2 — detect PSPs (BUG FIX: assignment inside the loop, every neuron)
    print("[PSP detection]")
    ipsps_all, epsps_all = {}, {}
    all_aps_combined = (np.sort(np.concatenate(list(aps_all.values())))
                        if any(len(v) for v in aps_all.values())
                        else np.array([], dtype=int))
    for t in all_traces:
        other = np.setdiff1d(all_aps_combined, aps_all[t])
        if len(other) == 0:
            ipsps_all[t] = np.array([], dtype=int)
            epsps_all[t] = np.array([], dtype=int)
            continue
        ipsps_all[t] = detect_ipsps(traces_all[t], other, segs,
                                    own_ap_indices=aps_all[t],
                                    ahp_blank=ahp_blank,
                                    ipsp_window=psp_window,
                                    ipsp_dur_min=ipsp_dur_min,
                                    onset_min_ms=onset_min_ms,
                                    min_above_thr_ms=min_above_thr_ms,
                                    ap_peak_ratio=ap_peak_ratio,
                                    fs=fs)
        epsps_all[t] = detect_epsps(traces_all[t], other, segs,
                                    own_ap_indices=aps_all[t],
                                    raw=raws_all[t],
                                    ahp_blank=ahp_blank,
                                    epsp_window=psp_window,
                                    epsp_dur_min=epsp_dur_min,
                                    onset_min_ms=onset_min_ms,
                                    min_above_thr_ms=min_above_thr_ms,
                                    fs=fs)
    print(f"  IPSP events: {sum(len(v) for v in ipsps_all.values())}  "
          f"EPSP events: {sum(len(v) for v in epsps_all.values())}")

    # Pass 2b — morphological PSP detection (no presynaptic AP required)
    print("[Morphological PSP detection]")
    epsps_morphological, ipsps_morphological = detect_all_morphological_psps(
        traces_all, aps_all, segs, raws_all=raws_all,
        ahp_blank=ahp_blank, epsp_dur_min=epsp_dur_min,
        ipsp_dur_min=ipsp_dur_min, min_above_thr_ms=min_above_thr_ms, fs=fs)
    print(f"  Morphological IPSP events: {sum(len(v) for v in ipsps_morphological.values())}  "
          f"EPSP events: {sum(len(v) for v in epsps_morphological.values())}")

    # Scoring (with conflict resolution)
    print("[Scoring]")
    inh_pairs_pre  = get_all_pairs(aps_all, ipsps_all, all_traces, segs, IPSP_WINDOW)
    inh_scores_pre = build_scores(aps_all, ipsps_all, all_traces, inh_pairs_pre, segs)
    inh_pairs      = resolve_conflicts(inh_pairs_pre, inh_scores_pre)
    inh_scores     = build_scores(aps_all, ipsps_all, all_traces, inh_pairs, segs)

    exc_pairs_pre  = get_all_pairs(aps_all, epsps_all, all_traces, segs, EPSP_WINDOW)
    exc_scores_pre = build_scores(aps_all, epsps_all, all_traces, exc_pairs_pre, segs)
    exc_pairs      = resolve_conflicts(exc_pairs_pre, exc_scores_pre)
    exc_scores     = build_scores(aps_all, epsps_all, all_traces, exc_pairs, segs)

    ni = sum(1 for s in inh_scores.values() if s >= score_thresh)
    ne = sum(1 for s in exc_scores.values() if s >= score_thresh)
    print(f"  Connections >={score_thresh}: inh={ni}  exc={ne}")

    neuron_type = classify_neuron_type(inh_scores, exc_scores, all_traces, score_thresh)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(csv_path))[0]
        for ctype, scores in [("IPSP", inh_scores), ("EPSP", exc_scores)]:
            rows = [{"pre": k[0], "post": k[1], "score": v}
                    for k, v in sorted(scores.items(), key=lambda x: -x[1])]
            pd.DataFrame(rows).to_csv(
                os.path.join(output_dir, f"scs_connectivity_{ctype}_{stem}.csv"),
                index=False)

    return dict(
        label=label, segs=segs, all_traces=all_traces,
        traces_all=traces_all, raws_all=raws_all, aps_all=aps_all,
        ipsps_all=ipsps_all, epsps_all=epsps_all,
        epsps_morphological=epsps_morphological,
        ipsps_morphological=ipsps_morphological,
        inh_scores=inh_scores, exc_scores=exc_scores,
        neuron_type=neuron_type, score_thresh=score_thresh,
        psp_window=psp_window,
    )


# ============================================================================
# Validation pass — re-pair P1 connections in P2 traces
# ============================================================================
def validate_scs_in_part2(res1: dict, res2: dict,
                          score_thresh: float = SCORE_THRESH,
                          val_score_thresh: float = SCORE_THRESH,
                          min_ap: int = 1) -> pd.DataFrame:
    """
    For each P1 connection at score >= threshold, re-count pre-AP -> PSP
    coincidences in Part 2 and emit a `validated` flag.
    """
    aps2  = res2["aps_all"]
    ips2  = res2["ipsps_all"]
    eps2  = res2["epsps_all"]
    psp_w = res1["psp_window"]

    rows = []
    for ctype, p1_scores, p2_psps in [
        ("INH", res1["inh_scores"], ips2),
        ("EXC", res1["exc_scores"], eps2),
    ]:
        for (pre, post), s1 in p1_scores.items():
            if s1 < score_thresh:
                continue
            aps_p2 = aps2.get(pre, [])
            n_ap   = len(aps_p2)
            if n_ap < min_ap:
                rows.append(dict(pre=pre, post=post, type=ctype,
                                 scs_score_p1=round(s1, 2),
                                 scs_score_p2=0.0,
                                 scs_validated=False,
                                 scs_n_ap_p2=n_ap))
                continue
            n_obs = sum(1 for ap in aps_p2
                        if any(1 <= ev - ap <= psp_w
                               for ev in p2_psps.get(post, [])))
            sp2 = compute_score(n_obs, n_ap)
            rows.append(dict(pre=pre, post=post, type=ctype,
                             scs_score_p1=round(s1, 2),
                             scs_score_p2=round(sp2, 2),
                             scs_validated=bool(sp2 >= val_score_thresh),
                             scs_n_ap_p2=n_ap))
    return pd.DataFrame(rows)

# ============================================================================
# Plot PSP properties
# ============================================================================
def _psp_decay_spline(post_signal, fs):
    """
    Decay time from 90% to 10% of PSP peak using cubic spline interpolation.
    post_signal : 1-D array starting at the peak, polarity-corrected (peak is positive).
    Returns time in ms, or np.nan if estimation fails.
    """
    from scipy.interpolate import CubicSpline
    if len(post_signal) < 4 or post_signal[0] <= 0:
        return np.nan
    peak_val = float(post_signal[0])
    t_samp   = np.arange(len(post_signal), dtype=float)
    try:
        roots_90 = CubicSpline(t_samp, post_signal - 0.9 * peak_val).roots()
        roots_90 = roots_90[(roots_90 > 0) & (roots_90 <= t_samp[-1])]
        if len(roots_90) == 0:
            return np.nan
        t90 = float(roots_90[0])

        roots_10 = CubicSpline(t_samp, post_signal - 0.1 * peak_val).roots()
        roots_10 = roots_10[(roots_10 > t90) & (roots_10 <= t_samp[-1])]
        if len(roots_10) == 0:
            return np.nan
        t10 = float(roots_10[0])

        return float((t10 - t90) / fs * 1000)
    except Exception:
        return np.nan


def _psp_props_one(trace, ap, psp_window, fs, noise=None, thr=None, baseline_window=None, polarity=1):
    pre_samp = int(PRE_CONTEXT_MS / 1000 * fs)
    base_start = max(0, ap - pre_samp)
    if base_start >= ap:
        return None
    baseline = np.nanmedian(trace[base_start:ap])
    noise    = np.nanstd(trace[base_start:ap])
    thr      = 2.5 * max(noise, 1e-6)

    win_start = ap + 1
    win_end   = min(len(trace), ap + psp_window + 1)
    if win_start >= win_end:
        return None
    snippet = trace[win_start:win_end] - baseline
    if np.all(np.isnan(snippet)):
        return None

    peak_idx  = int(np.nanargmax(polarity * snippet))
    amplitude = float(snippet[peak_idx])
    peak_time_ms   = float((peak_idx + 1) / fs * 1000)
    crossings      = np.where(np.abs(snippet) > thr)[0]
    onset_delay_ms = float((crossings[0] + 1) / fs * 1000) if len(crossings) else np.nan
    auc = (float(np.trapz(np.abs(snippet[crossings[0]:crossings[-1] + 1])) / fs)
           if len(crossings) >= 2 else np.nan)

    rise_time_ms = (peak_time_ms - onset_delay_ms) if not np.isnan(onset_delay_ms) else np.nan

    above_half = np.where(np.abs(snippet) > np.abs(amplitude) / 2)[0]
    half_width_ms = float((above_half[-1] - above_half[0] + 1) / fs * 1000) if len(above_half) >= 2 else np.nan

    snr = float(np.abs(amplitude) / max(noise, 1e-6))

    decay_time_ms = _psp_decay_spline(polarity * snippet[peak_idx:], fs)

    duration_ms = float(len(crossings) / fs * 1000) if len(crossings) else np.nan

    return dict(amplitude=amplitude, auc=auc,
                peak_time_ms=peak_time_ms, onset_delay_ms=onset_delay_ms,
                rise_time_ms=rise_time_ms, half_width_ms=half_width_ms,
                snr=snr, decay_time_ms=decay_time_ms, duration_ms=duration_ms)


def _psp_props_from_window(window, polarity, fs):
    """Compute PSP properties from a pre-extracted window where AP is at PRE_AP_BLANK."""
    pre     = window[:PRE_AP_BLANK]
    snippet = window[PRE_AP_BLANK:] - float(np.nanmedian(pre))
    noise   = float(np.nanstd(pre))
    if np.all(np.isnan(snippet)):
        return None
    thr           = 2.5 * max(noise, 1e-6)
    peak_idx      = int(np.nanargmax(polarity * snippet))
    amplitude     = float(snippet[peak_idx])
    peak_time_ms  = float((peak_idx + 1) / fs * 1000)
    crossings     = np.where(np.abs(snippet) > thr)[0]
    onset_delay_ms = float((crossings[0] + 1) / fs * 1000) if len(crossings) else np.nan
    auc = (float(np.trapz(np.abs(snippet[crossings[0]:crossings[-1] + 1])) / fs)
           if len(crossings) >= 2 else np.nan)
    rise_time_ms  = (peak_time_ms - onset_delay_ms) if not np.isnan(onset_delay_ms) else np.nan
    above_half    = np.where(np.abs(snippet) > np.abs(amplitude) / 2)[0]
    half_width_ms = float((above_half[-1] - above_half[0] + 1) / fs * 1000) if len(above_half) >= 2 else np.nan
    snr           = float(np.abs(amplitude) / max(noise, 1e-6))
    decay_time_ms = _psp_decay_spline(polarity * snippet[peak_idx:], fs)
    duration_ms   = float(len(crossings) / fs * 1000) if len(crossings) else np.nan
    return dict(amplitude=amplitude, auc=auc, peak_time_ms=peak_time_ms,
                onset_delay_ms=onset_delay_ms, rise_time_ms=rise_time_ms,
                half_width_ms=half_width_ms, snr=snr, decay_time_ms=decay_time_ms,
                duration_ms=duration_ms)


def compute_psp_props_fov(R, val_tiers=('both', 'scs_only', 'sta_only')):
    """Per-FOV PSP properties for validated EXC and INH connections.

    Shape features (amplitude, AUC, timing, widths) are extracted from the
    mean PSP waveform — averaging across events before measuring reduces
    noise-driven jitter in threshold-crossing features. SNR is kept as
    mean-of-individuals since it is a per-event signal-to-noise metric.

    Pools events from scs1 and scs2 so drug conditions with reduced
    spontaneous activity are not excluded.
    """
    merged = R.get('merged')
    if merged is None or merged.empty:
        return None
    val = merged[merged['consensus_tier'].isin(val_tiers)]
    if val.empty:
        return None

    _empty = dict(amplitude=np.nan, auc=np.nan, peak_time_ms=np.nan, onset_delay_ms=np.nan,
                  rise_time_ms=np.nan, half_width_ms=np.nan, snr=np.nan,
                  decay_time_ms=np.nan, duration_ms=np.nan)

    _POST = WIN_LEN - PRE_AP_BLANK   # post-AP samples in aligned window
    windows  = {'EXC': [], 'INH': []}
    snr_vals = {'EXC': [], 'INH': []}

    for src_key in ('scs1', 'scs2'):
        scs = R.get(src_key)
        if scs is None:
            continue

        traces    = scs['traces_all']
        aps_all   = scs['aps_all']
        ipsps_all = scs['ipsps_all']
        epsps_all = scs['epsps_all']
        segs      = scs['segs']

        for _, row in val.iterrows():
            pre = int(row['pre'])
            post = int(row['post'])
            typ  = str(row['type']).upper()
            if typ not in windows or pre not in traces or post not in traces:
                continue
            trace    = traces[post]
            pre_aps  = aps_all.get(pre, np.array([], dtype=int))
            events   = (ipsps_all if typ == 'INH' else epsps_all).get(post, np.array([], dtype=int))
            win      = IPSP_WINDOW if typ == 'INH' else EPSP_WINDOW
            polarity = -1 if typ == 'INH' else 1
            for seg_s, seg_e in segs:
                seg_aps  = pre_aps[(pre_aps >= seg_s) & (pre_aps <= seg_e)]
                seg_evts = events[(events >= seg_s)   & (events <= seg_e)]
                for ap in seg_aps:
                    if not any((seg_evts > ap) & (seg_evts <= ap + win)):
                        continue
                    p = _psp_props_one(trace, int(ap), win, FS, polarity=polarity)
                    if p is not None:
                        snr_vals[typ].append(p['snr'])
                    n1, n2 = int(ap) - PRE_AP_BLANK, int(ap) + _POST
                    if n1 >= 0 and n2 <= len(trace):
                        windows[typ].append(trace[n1:n2].astype(float))

    result = {}
    for typ in ('EXC', 'INH'):
        polarity = -1 if typ == 'INH' else 1
        if not windows[typ]:
            result[typ] = _empty.copy()
            continue
        mean_wave = np.mean(windows[typ], axis=0)
        shape = _psp_props_from_window(mean_wave, polarity, FS)
        if shape is None:
            result[typ] = _empty.copy()
            continue
        shape['snr'] = float(np.mean(snr_vals[typ])) if snr_vals[typ] else np.nan
        result[typ] = shape
    return result
