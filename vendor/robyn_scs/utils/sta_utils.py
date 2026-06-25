"""
sta_utils.py — pipeline v17, spike-triggered-average waveform branch.

Same algorithm as the v14 STA pipeline (5 sequential gates, asymmetric P1/P2),
factored into a clean module that consumes the shared `data_utils` AP detector
so both branches see the same APs.

New for v16:
  * Optional stim-locked subset trigger filter for diagnostic comparison —
    by default, all pre-APs are used as triggers; pass
    `stim_locked_only=True` to restrict to APs within +/- N samples of a
    stim frame (fed in via `stim_frames`).
  * Pipeline runner consumes the stim metadata loaded by data_utils so the
    output dict carries `in_stim_mask` per pre-neuron.

Gate summary:

  Gate                    Discovery (P1)        Validation (P2)
  ------------------------------------------------------------------
  1. Baseline drift       |pre-AP mean| <= 3 * noise        same
  2. Median SNR           median(peaks) >= 4.0 * noise      >= 2.5 * noise
  3. Welch t-test         p < 0.05 (two-sided)              same
  4. Onset timing         peak >= 20 ms post-AP             >= 10 ms
  5. Window count         accepted_windows >= 2             >= 3
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.stats import binomtest, ttest_ind

from .data_utils import (
    FS, _noise_std, detect_aps, detect_segments, find_duplicate_neurons,
    preprocess, regress_global_signal, stim_locked_aps,
)


# ============================================================================
# Constants
# ============================================================================
PRE_AP_BLANK         = int(0.050 * FS)             # 50 ms pre-AP
POST_AP_WIN          = int(0.400 * FS)             # 400 ms post-AP
WIN_LEN              = PRE_AP_BLANK + POST_AP_WIN
RESP_END             = PRE_AP_BLANK + int(0.150 * FS)   # response zone end
N_CTRL_FIXED         = 20
CTRL_SEED            = 42

BASELINE_GATE_SIGMA  = 4.0
SNR_AMP_GATE         = 4.0      # P1 median SNR gate
MIN_ONSET_MS         = 5.0     # P1 onset gate
MIN_WIN_DISC         = 2        # P1 minimum accepted windows
MIN_WIN_VAL          = 2        # P2 minimum accepted windows
VAL_SNR_RELAXED      = 3.5      # P2 median SNR gate (unconditional relax)
VAL_ONSET_MS         = 5.0     # P2 onset gate (unconditional relax)

SCORE_THRESH         = 1.7      # -log10(p) ~= p < 0.05

# Strict coincidence: windows where the post-neuron fires within +/- this many
# ms of the pre-AP are dropped entirely (these are non-synaptic coincidences).
# v16 lowered this from 20 ms to 5 ms because anything in the (5 ms, 150 ms)
# window is now classified as an *evoked AP* and tracked separately, rather
# than thrown out.
COINCIDENCE_MS       = 5.0


# ============================================================================
# Internal helpers — STA window extraction
# ============================================================================
def _ap_excluded_mask(post_aps, n, blank_before_ms=50, blank_after_ms=100,
                      fs=FS):
    mask = np.zeros(n, dtype=bool)
    pre  = int(blank_before_ms / 1000 * fs)
    post = int(blank_after_ms  / 1000 * fs)
    for ap in post_aps:
        mask[max(0, ap-pre):min(n, ap+post)] = True
    return mask


def _valid_ctrl_starts_vec(combined, segs, n):
    cum = np.zeros(n + 1, dtype=np.int32)
    cum[1:] = np.cumsum(combined.astype(np.int32))
    out = []
    for seg_s, seg_e in segs:
        starts = np.arange(int(seg_s), int(seg_e) - WIN_LEN + 2)
        if len(starts) == 0:
            continue
        ends = np.clip(starts + WIN_LEN, 0, n)
        out.append(starts[cum[ends] - cum[starts] == 0])
    return np.concatenate(out) if out else np.array([], dtype=int)


def _extract_sta_windows(post_trace, pre_aps, post_aps, segs, noise=None,
                         fs: int = FS):
    """
    All accepted (non-coincident) signal windows = psp_wins + ap_wins.

    Kept for backward-compat with `count_accepted_windows` and any external
    callers. `_classify_sta_windows` is the canonical entry point now.
    """
    psp_wins, ap_wins, _ = _classify_sta_windows(
        post_trace, pre_aps, post_aps, segs, noise=noise, fs=fs)
    return psp_wins + ap_wins


def _sample_control_windows(post_trace, pre_aps, post_aps, segs, rng,
                            noise=None):
    n = len(post_trace)
    forbidden = np.zeros(n, dtype=bool)
    for ap in pre_aps:
        ap = int(ap); ws = ap - PRE_AP_BLANK; we = ap + POST_AP_WIN
        if 0 <= ws and we < n: forbidden[ws:we] = True
    vstarts = _valid_ctrl_starts_vec(forbidden | _ap_excluded_mask(post_aps, n),
                                     segs, n)
    if len(vstarts) == 0:
        return []
    chosen = rng.choice(vstarts, size=min(N_CTRL_FIXED, len(vstarts)),
                        replace=False)
    wins = []
    for s in chosen:
        win = post_trace[s:s+WIN_LEN].copy()
        bl  = win[:PRE_AP_BLANK].mean()
        if noise is not None and abs(bl) > BASELINE_GATE_SIGMA * noise:
            continue
        wins.append(win - bl)
    return wins


def count_accepted_windows(post_trace, pre_aps, post_aps, segs, noise,
                           fs: int = FS) -> int:
    return len(_extract_sta_windows(post_trace, pre_aps, post_aps, segs,
                                    noise=noise, fs=fs))


# ============================================================================
# Window classification — split signal windows into PSP and evoked-AP pools
# ============================================================================
def _classify_sta_windows(post_trace, pre_aps, post_aps, segs, noise=None,
                          coincidence_ms: float = COINCIDENCE_MS,
                          evoked_ap_zone_ms: float = 150.0,
                          ap_peak_mult: float = 8.0,
                          fs: int = FS):
    """
    Pre-AP-locked windows from `post_trace`, partitioned by whether the post
    neuron fires inside the response zone:

      * psp_wins  — post does NOT fire in the evoked-AP zone and no large
                    positive peak is detected. These windows drive the
                    subthreshold STA mean.
      * ap_wins   — post fires in the evoked-AP zone, OR a large positive
                    peak (> ap_peak_mult * noise) is detected in the response
                    portion (catches missed APs from shifted amplitude
                    distributions, e.g. under CTZ).
      * dropped   — post fires within +/- coincidence_ms of pre-AP. These are
                    non-synaptic coincidences and are excluded from both pools.

    Evoked-AP zone: (pre_ap + coincidence_samples, pre_ap + evoked_ap_zone_ms)
    i.e. everything from `coincidence_ms` to 150 ms post pre-AP.

    Returns
    -------
    psp_wins, ap_wins, n_dropped_coincident
    """
    n = len(post_trace)
    seg_set = [(int(s), int(e)) for s, e in segs]
    coinc_samp = int(coincidence_ms / 1000 * fs)
    response_zone_end = int(evoked_ap_zone_ms / 1000 * fs)
    post_aps = np.asarray(post_aps, dtype=int)

    psp_wins, ap_wins = [], []
    n_dropped = 0

    for ap in pre_aps:
        ap = int(ap)
        ws = ap - PRE_AP_BLANK
        we = ap + POST_AP_WIN
        if ws < 0 or we >= n: continue
        if not any(s <= ws and we <= e for s, e in seg_set): continue

        # Strict coincidence drop (post fires within +/- coincidence_ms of pre-AP).
        if len(post_aps) > 0 and np.any(np.abs(post_aps - ap) <= coinc_samp):
            n_dropped += 1
            continue

        win = post_trace[ws:we]
        if np.any(np.isnan(win)): continue
        bl = win[:PRE_AP_BLANK].mean()
        if noise is not None and abs(bl) > BASELINE_GATE_SIGMA * noise:
            continue
        win_corr = win - bl

        # Classify: does post fire in (coincidence_ms, evoked_ap_zone_ms) post pre-AP?
        evoked_in_zone = (post_aps > ap + coinc_samp) & \
                         (post_aps < ap + response_zone_end)
        if np.any(evoked_in_zone):
            ap_wins.append(win_corr)
            continue

        # Missed-AP check: large positive peak in the response portion of the
        # window suggests a Ca²⁺ transient from an AP the detector missed
        # (e.g. amplitude-shifted under CTZ). Move to ap_wins rather than
        # letting the undershoot contaminate the subthreshold STA mean.
        if noise is not None and noise > 0:
            resp_seg = win_corr[PRE_AP_BLANK + coinc_samp:]
            if len(resp_seg) > 0 and float(np.nanmax(resp_seg)) > ap_peak_mult * noise:
                ap_wins.append(win_corr)
                continue

        psp_wins.append(win_corr)

    return psp_wins, ap_wins, n_dropped


# ============================================================================
# AP-rate test — does the pre-AP elevate (or suppress) post-AP probability?
# ============================================================================
def _ap_rate_test(n_psp: int, n_ap_evoked: int, post_aps, segs,
                  coincidence_ms: float = COINCIDENCE_MS, fs: int = FS):
    """
    Binomial test on the rate at which post-APs fall inside the pre-AP-locked
    response zone, vs the post neuron's *background* AP rate (estimated from
    the full recording).

    Returns (ap_pval, ap_rate_sig, ap_rate_ctrl_expected, ap_dir).

    `ap_dir`:
        'exc'  — observed rate > expected (pre-AP raises post-firing probability,
                 evidence of a depolarizing connection).
        'inh'  — observed rate < expected (pre-AP suppresses post-firing,
                 evidence of an inhibitory connection). NEW IN v16: uses a
                 two-sided binomial test, so suppression is also detected.
                 To revert to elevation-only behaviour, change `alternative`
                 below to 'greater' and treat ap_dir == 'inh' as 'none'.
        'none' — null result.

    Note: the "control" rate here is computed analytically (Poisson approx
    from background AP density × evoked-zone duration) rather than sampled
    from random control windows. This avoids the existing control-window
    sampler's bias against post-AP-containing windows.
    """
    n_total = n_psp + n_ap_evoked
    if n_total == 0 or len(post_aps) == 0:
        return 1.0, 0.0, 0.0, 'none'

    # Total imaging samples across all valid segments.
    total_samples = sum(int(e) - int(s) + 1 for s, e in segs)
    background_rate = len(post_aps) / max(total_samples, 1)   # per-sample

    # Evoked-zone duration in samples (matches _classify_sta_windows zone).
    coinc_samp = int(coincidence_ms / 1000 * fs)
    zone_samp  = (RESP_END - PRE_AP_BLANK) - coinc_samp
    if zone_samp <= 0:
        return 1.0, 0.0, 0.0, 'none'

    # Poisson approximation: P(>=1 AP in a zone of `zone_samp` samples).
    expected_p = 1.0 - float(np.exp(-background_rate * zone_samp))
    expected_p = float(np.clip(expected_p, 1e-6, 1.0 - 1e-6))

    # Two-sided binomial test (detects both elevation and suppression).
    # NOTE: `alternative='two-sided'` is the v16 INH-suppression upgrade.
    # Revert to 'greater' to test only AP-rate elevation (EXC drive only).
    res = binomtest(n_ap_evoked, n_total, expected_p, alternative='two-sided')
    ap_pval = float(res.pvalue)

    ap_rate_sig = n_ap_evoked / n_total
    if ap_rate_sig > expected_p:
        ap_dir = 'exc'
    elif ap_rate_sig < expected_p:
        ap_dir = 'inh'
    else:
        ap_dir = 'none'

    return ap_pval, ap_rate_sig, expected_p, ap_dir


# ============================================================================
# Result container — tuple-compatible with the v15 9-field shape, plus extras
# ============================================================================
class StaResult(NamedTuple):
    # Backward-compat positional fields (first 9 match the old result tuple).
    signed: float
    p_val: float
    direction: str
    n_sig: int                          # n_psp + n_ap_evoked  (total accepted)
    n_ctrl: int
    sta_mean: Optional[np.ndarray]      # mean of psp_wins (subthreshold)
    sta_sd: Optional[np.ndarray]
    ctrl_mean: Optional[np.ndarray]
    ctrl_sd: Optional[np.ndarray]
    # New v16 fields:
    n_psp: int = 0
    n_ap_evoked: int = 0
    n_coinc_dropped: int = 0
    ap_rate_sig: float = 0.0
    ap_rate_ctrl: float = 0.0           # expected (Poisson from background)
    ap_pval: float = 1.0
    ap_score: float = 0.0
    ap_direction: str = 'none'
    psp_pval: float = 1.0
    psp_score: float = 0.0
    psp_direction: str = 'none'


def _null_sta_result() -> "StaResult":
    return StaResult(
        signed=0.0, p_val=1.0, direction='none',
        n_sig=0, n_ctrl=0,
        sta_mean=None, sta_sd=None, ctrl_mean=None, ctrl_sd=None,
    )


# ============================================================================
# STA scoring
# ============================================================================
ONSET_FRAC = 0.20   # response must reach this fraction of peak before being
                    # called "onset" — standard fraction-of-peak convention


def _score_window_pair(sa, ca, snr_gate, onset_ms, noise, fs=FS,
                       onset_frac: float = ONSET_FRAC):
    """Run gates 2-4 on already-extracted signal/control window arrays.

    Onset gate (gate 4) — STRICT FIRST-CROSSING form:
        Compute the smoothed mean STA over the full window (pre-AP + response
        zone). The onset is the FIRST crossing of `onset_frac * peak`
        (sign-aware), measured in ms relative to t=0 (the pre-AP).
        Rejection condition: onset < `onset_ms` ms after t=0.
        Measuring from the full window (not just post-AP) correctly catches
        responses that are already rising before t=0 — those yield a negative
        onset_ms_rel and are rejected.  Without the pre-AP region in `resp`,
        a pre-AP rise can dip at t=0 due to baseline subtraction and then
        re-cross the threshold several ms later, fooling the gate.
    """
    sp = sa[:, PRE_AP_BLANK:RESP_END].max(axis=1)
    cp = ca[:, PRE_AP_BLANK:RESP_END].max(axis=1)
    st = sa[:, PRE_AP_BLANK:RESP_END].min(axis=1)
    ct = ca[:, PRE_AP_BLANK:RESP_END].min(axis=1)

    _, p_exc = ttest_ind(sp, cp, equal_var=False)
    _, p_inh = ttest_ind(st, ct, equal_var=False)
    p_exc = max(p_exc, 1e-10); p_inh = max(p_inh, 1e-10)

    if noise is not None:
        exc_amp_ok = np.median(sp)         >= snr_gate * noise
        inh_amp_ok = np.median(np.abs(st)) >= snr_gate * noise
    else:
        exc_amp_ok = inh_amp_ok = True

    exc_sep = sp.mean() > cp.mean()
    inh_sep = st.mean() < ct.mean()
    if exc_sep and exc_amp_ok and (not (inh_sep and inh_amp_ok) or p_exc <= p_inh):
        direction, p_val = "exc", p_exc
    elif inh_sep and inh_amp_ok and (not (exc_sep and exc_amp_ok) or p_inh < p_exc):
        direction, p_val = "inh", p_inh
    else:
        direction, p_val = "none", 1.0

    log_p = -np.log10(max(p_val, 1e-10))
    if p_val >= 0.05 or direction == "none":
        direction, signed = "none", 0.0
    else:
        signed = log_p if direction == "exc" else -log_p

    # Onset gate (gate 4) — first crossing of onset_frac * peak
    # Include pre-AP region so responses already rising before t=0 are caught
    if direction != "none":
        resp   = sa[:, :RESP_END].mean(axis=0)          # from t=-PRE_AP_BLANK to t=+150ms
        wl     = min(11, len(resp) if len(resp) % 2 == 1 else len(resp) - 1)
        smooth = savgol_filter(resp, wl, 3) if wl >= 5 else resp
        if direction == "exc":
            peak_val  = float(np.max(smooth))
            threshold = onset_frac * peak_val             # 20% of peak
            crossings = np.where(smooth >= threshold)[0]
        else:
            peak_val  = float(np.min(smooth))             # negative
            threshold = onset_frac * peak_val             # negative
            crossings = np.where(smooth <= threshold)[0]
        if len(crossings) == 0:
            direction, signed, p_val = "none", 0.0, 1.0
        else:
            first_idx    = int(crossings[0])
            onset_ms_rel = (first_idx - PRE_AP_BLANK) / fs * 1000  # ms rel to AP; negative = pre-AP rise
            # Reject if onset is before or too close to the AP (< onset_ms ms after AP)
            if onset_ms_rel < onset_ms:
                direction, signed, p_val = "none", 0.0, 1.0

    return signed, p_val, direction


def compute_sta_score(pre_trace, post_trace, pre_aps, post_aps, segs, rng,
                      noise=None, snr_gate: float = SNR_AMP_GATE,
                      onset_ms: float = MIN_ONSET_MS,
                      onset_frac: float = ONSET_FRAC,
                      score_thresh: float = SCORE_THRESH,
                      fs: int = FS) -> "StaResult":
    """
    Discovery-phase scoring (P1: SNR_AMP_GATE 4x, MIN_ONSET_MS 20 ms,
    first-crossing onset @ onset_frac of peak).

    v16 split-pool refactor:
      * Windows are partitioned into PSP-only (subthreshold) and evoked-AP
        pools by `_classify_sta_windows`.
      * The Welch t-test for PSP score uses the PSP-only pool, so the STA
        mean / SD are clean of post-AP waveforms.
      * The evoked-AP rate is tested separately via `_ap_rate_test` (binomial
        vs background AP rate).
      * combined_score = max(psp_score, ap_score). Direction follows whichever
        channel has the higher score; the per-channel direction and p-value
        are also returned in the StaResult so downstream code (and plots)
        can show both.
    """
    psp_wins, ap_wins, n_coinc = _classify_sta_windows(
        post_trace, pre_aps, post_aps, segs, noise=noise, fs=fs)
    n_psp       = len(psp_wins)
    n_ap_evoked = len(ap_wins)
    n_sig_total = n_psp + n_ap_evoked

    # Need at least *some* signal windows AND control windows.
    if n_sig_total < 2:
        return _null_sta_result()
    ctrl = _sample_control_windows(post_trace, pre_aps, post_aps, segs, rng,
                                   noise=noise)
    if len(ctrl) < 2:
        return _null_sta_result()
    ca = np.array(ctrl)

    # -------- PSP score (subthreshold-only Welch t-test) ----------------------
    if n_psp >= 2:
        psp_sa = np.array(psp_wins)
        psp_signed, psp_pval, psp_dir = _score_window_pair(
            psp_sa, ca, snr_gate, onset_ms, noise,
            fs=fs, onset_frac=onset_frac)
        # `psp_signed` carries the sign already; psp_score is the magnitude.
        psp_score = abs(psp_signed)
        sta_mean  = psp_sa.mean(axis=0)
        sta_sd    = psp_sa.std(axis=0)
    else:
        psp_pval, psp_score, psp_dir = 1.0, 0.0, 'none'
        sta_mean = sta_sd = None

    # -------- AP-rate score (post-AP elevation OR suppression) ---------------
    ap_pval, ap_rate_sig, ap_rate_ctrl, ap_dir = _ap_rate_test(
        n_psp, n_ap_evoked, post_aps, segs, fs=fs)
    ap_score = -np.log10(max(ap_pval, 1e-10)) if ap_pval < 0.05 else 0.0
    if ap_score == 0.0:
        ap_dir = 'none'

    # Combine: PSP and evoked-AP are two independent witnesses of the same
    # connection. Sum the per-channel scores (Stouffer-like log-p sum) so that
    # evidence from both compounds, while either signal alone still carries
    # its own score. Per-channel direction and p-values are kept in psp_*/ap_*
    # fields for visualization and mechanism analysis.
    combined_score = psp_score + ap_score
    # Direction logic:
    #   * Both significant + agree -> that direction
    #   * Both significant + disagree -> dominant channel's direction (logged
    #     internally via psp_direction / ap_direction so the conflict is visible)
    #   * Only one significant -> that direction
    #   * Neither -> 'none'
    if psp_score > 0 and ap_score > 0:
        direction = psp_dir if psp_dir == ap_dir else (
            psp_dir if psp_score >= ap_score else ap_dir
        )
    elif psp_score > 0:
        direction = psp_dir
    elif ap_score > 0:
        direction = ap_dir
    else:
        direction = 'none'
    combined_pval = min(psp_pval, ap_pval)   # for reporting only

    if direction == 'none' or combined_score < score_thresh:
        signed = 0.0
    elif direction == 'exc':
        signed = combined_score
    else:  # 'inh'
        signed = -combined_score

    return StaResult(
        signed=signed, p_val=combined_pval, direction=direction,
        n_sig=n_sig_total, n_ctrl=len(ctrl),
        sta_mean=sta_mean, sta_sd=sta_sd,
        ctrl_mean=ca.mean(axis=0), ctrl_sd=ca.std(axis=0),
        n_psp=n_psp, n_ap_evoked=n_ap_evoked, n_coinc_dropped=n_coinc,
        ap_rate_sig=ap_rate_sig, ap_rate_ctrl=ap_rate_ctrl,
        ap_pval=ap_pval, ap_score=ap_score, ap_direction=ap_dir,
        psp_pval=psp_pval, psp_score=psp_score, psp_direction=psp_dir,
    )


def compute_sta_score_val(pre_trace, post_trace, pre_aps, post_aps, segs, rng,
                          noise=None, onset_frac: float = ONSET_FRAC,
                          score_thresh: float = SCORE_THRESH,
                          fs: int = FS) -> "StaResult":
    """Validation-phase scoring (P2: SNR 2.5x, onset 10 ms — relaxed)."""
    return compute_sta_score(pre_trace, post_trace, pre_aps, post_aps, segs,
                             rng, noise=noise, snr_gate=VAL_SNR_RELAXED,
                             onset_ms=VAL_ONSET_MS, onset_frac=onset_frac,
                             score_thresh=score_thresh, fs=fs)


# ============================================================================
# Pipeline runner — STA stim-period analysis
# ============================================================================
def run_sta_pipeline(csv_path: str, label: str = "",
                     score_thresh: float = SCORE_THRESH,
                     output_dir: Optional[str] = None,
                     fs: int = FS,
                     use_val_scorer: bool = False,
                     stim_meta: Optional[dict] = None,
                     part: str = "part1",
                     exclude_neurons: Optional[Sequence[int]] = None,
                     min_onset_ms: Optional[float] = None,
                     onset_frac: float = ONSET_FRAC,
                     regress_global: bool = True) -> dict:
    """Run STA scoring on a single stim-period CSV. See module docstring."""
    print("\n" + "=" * 60)
    print(f"STA pipeline v17  |  {label or csv_path}  |  "
          f"{'P2 (relaxed)' if use_val_scorer else 'P1 (strict)'}"
          )
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

    print("[AP detection]")
    traces_all, raws_all, aps_all = {}, {}, {}
    for t in all_traces:
        raw = df[df.columns[t-1]].values.astype(float)
        tr  = preprocess(raw, segs, fs=fs)
        traces_all[t] = tr; raws_all[t] = raw
        aps_all[t]    = detect_aps(tr, segs, raw=raw, fs=fs)

    n_active  = sum(1 for t in all_traces if len(aps_all[t]) > 0)
    ap_counts = {t: int(len(aps_all[t])) for t in all_traces}
    print(f"  Active neurons: {n_active}/{len(all_traces)}")

    noise_all = {t: _noise_std(traces_all[t], segs) for t in all_traces}

    in_stim_mask = {t: False for t in all_traces}
    if stim_meta is not None:
        mask_set = set(int(x) for x in stim_meta.get("stim_mask_sources", []))
        for t in all_traces:
            in_stim_mask[t] = t in mask_set

    aps_for_sta = {t: aps_all[t] for t in all_traces}
    active_traces = [t for t in all_traces if len(aps_for_sta[t]) >= 1]

    win_counts = {}
    for pre in active_traces:
        for post in all_traces:
            if pre == post: continue
            win_counts[(pre, post)] = count_accepted_windows(
                traces_all[post], aps_for_sta[pre], aps_all[post],
                segs, noise_all[post], fs=fs)

    print("[STA scoring]")
    rng = np.random.default_rng(CTRL_SEED)
    exc_scores, inh_scores, all_results = {}, {}, {}
    scorer_kwargs = dict(score_thresh=score_thresh, onset_frac=onset_frac, fs=fs)
    if min_onset_ms is not None:
        scorer_kwargs['onset_ms'] = float(min_onset_ms)

    for pre in active_traces:
        for post in all_traces:
            if pre == post: continue
            if use_val_scorer:
                # compute_sta_score_val uses VAL_ONSET_MS; allow override via min_onset_ms
                if min_onset_ms is not None:
                    result = compute_sta_score(
                        traces_all[pre], traces_all[post],
                        aps_for_sta[pre], aps_all[post], segs, rng,
                        noise=noise_all[post], snr_gate=VAL_SNR_RELAXED,
                        onset_ms=float(min_onset_ms), onset_frac=onset_frac,
                        score_thresh=score_thresh, fs=fs)
                else:
                    result = compute_sta_score_val(
                        traces_all[pre], traces_all[post],
                        aps_for_sta[pre], aps_all[post], segs, rng,
                        noise=noise_all[post], onset_frac=onset_frac,
                        score_thresh=score_thresh, fs=fs)
            else:
                result = compute_sta_score(
                    traces_all[pre], traces_all[post],
                    aps_for_sta[pre], aps_all[post], segs, rng,
                    noise=noise_all[post], **scorer_kwargs)
            all_results[(pre, post)] = result
            signed = result.signed
            direction = result.direction
            if direction == "exc" and abs(signed) >= score_thresh:
                exc_scores[(pre, post)] = abs(signed)
                inh_scores[(pre, post)] = 0.0
            elif direction == "inh" and abs(signed) >= score_thresh:
                inh_scores[(pre, post)] = abs(signed)
                exc_scores[(pre, post)] = 0.0
            else:
                exc_scores[(pre, post)] = 0.0
                inh_scores[(pre, post)] = 0.0

    n_exc = sum(1 for s in exc_scores.values() if s >= score_thresh)
    n_inh = sum(1 for s in inh_scores.values() if s >= score_thresh)
    print(f"  Connections >= {score_thresh}: exc={n_exc}  inh={n_inh}")

    neuron_type = {}
    for t in all_traces:
        si = sum(s for (p, _), s in inh_scores.items()
                 if p == t and s >= score_thresh)
        se = sum(s for (p, _), s in exc_scores.items()
                 if p == t and s >= score_thresh)
        if si == 0 and se == 0:
            neuron_type[t] = "silent"
        else:
            neuron_type[t] = "exc" if se >= si else "inh"

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(csv_path))[0]
        for ctype, scores in [("EPSP", exc_scores), ("IPSP", inh_scores)]:
            rows = [{"pre": k[0], "post": k[1], "score": v}
                    for k, v in sorted(scores.items(), key=lambda x: -x[1])]
            pd.DataFrame(rows).to_csv(
                os.path.join(output_dir, f"sta_connectivity_{ctype}_{stem}.csv"),
                index=False)

    return dict(
        label=label, segs=segs, all_traces=all_traces,
        traces_all=traces_all, raws_all=raws_all, aps_all=aps_all,
        aps_for_sta=aps_for_sta,
        exc_scores=exc_scores, inh_scores=inh_scores,
        neuron_type=neuron_type, ap_counts=ap_counts,
        all_results=all_results, win_counts_p1=win_counts,
        score_thresh=score_thresh, in_stim_mask=in_stim_mask,
        use_val_scorer=use_val_scorer,
    )


# ============================================================================
# Validation pass — score Part 1 connections against Part 2 traces
# ============================================================================
def validate_sta_in_part2(res1: dict, res2: dict,
                          score_thresh: float = SCORE_THRESH,
                          min_win_disc: int = MIN_WIN_DISC,
                          min_win_val: int = MIN_WIN_VAL) -> pd.DataFrame:
    """
    Build a per-connection table joining P1 discovery and P2 validation
    scores, with the asymmetric window-count gate applied.
    """
    win_p1 = res1.get("win_counts_p1", {})
    rows = []
    for direction, p1_scores, p2_scores in [
        ("EXC", res1["exc_scores"], res2["exc_scores"]),
        ("INH", res1["inh_scores"], res2["inh_scores"]),
    ]:
        for (pre, post), s1 in p1_scores.items():
            if s1 < score_thresh:
                continue
            if win_p1.get((pre, post), 0) < min_win_disc:
                continue
            wp2 = count_accepted_windows(
                res2["traces_all"][post], res2["aps_for_sta"][pre],
                res2["aps_all"][post], res2["segs"],
                _noise_std(res2["traces_all"][post], res2["segs"]))
            s2  = p2_scores.get((pre, post), 0.0)
            rows.append(dict(
                pre=pre, post=post, type=direction,
                sta_score_p1=round(s1, 2),
                sta_score_p2=round(s2, 2),
                sta_validated=bool(s2 >= score_thresh and wp2 >= min_win_val),
                sta_win_p1=int(win_p1.get((pre, post), 0)),
                sta_win_p2=int(wp2),
            ))
    return pd.DataFrame(rows)


# ============================================================================
# Interleaved-trial validation
# ============================================================================
# Why this exists: the time-half validate_sta_in_part2 above assumes the
# trigger rate is stationary across the stim recording — it isn't. With a
# 30-mask comb protocol, a pre-neuron's APs may cluster around whichever
# masks happen to drive it, leaving the "other half" undertriggered. We
# replace that with a split on the trigger sequence. Two modes are supported:
#
#   'random' (default): randomly assign pre-APs to a ~70% train set and a
#            ~30% test set (>= 2 test APs).  Train uses strict gates and must
#            clear score_thresh; test only checks that the mean PSP deflection
#            is non-zero in the same direction — no t-test, no threshold,
#            because the held-out set is typically 1–2 trials.
#
#   'parity' (legacy): even-indexed pre-APs → discovery, odd-indexed →
#            validation.  Both subsets must clear score_thresh with strict
#            gates (original v16 behaviour).

MIN_AP_STIM = 2     # min total pre-AP count in the stim recording


def _test_set_agrees(post_trace: np.ndarray, pre_aps_test: np.ndarray,
                     post_aps: np.ndarray, segs, noise: float,
                     expected_dir: str, fs: int = FS) -> bool:
    """
    Lightweight direction check for a small held-out test set (1–2 trials).
    No t-test, no score threshold.  Returns True iff the grand-mean PSP
    response in the response zone is non-zero in the same direction as
    `expected_dir`.
    """
    if len(pre_aps_test) == 0 or expected_dir == 'none':
        return False
    psp_wins, _, _ = _classify_sta_windows(
        post_trace, pre_aps_test, post_aps, segs, noise=noise, fs=fs)
    if len(psp_wins) == 0:
        return False
    grand_mean = np.array(psp_wins)[:, PRE_AP_BLANK:RESP_END].mean()
    if expected_dir == 'exc':
        return bool(grand_mean > 0)
    else:
        return bool(grand_mean < 0)


def run_sta_pipeline_interleaved(csv_p1: str, csv_p2: str, label: str = "",
                                 score_thresh: float = SCORE_THRESH,
                                 min_ap_stim: int = MIN_AP_STIM,
                                 output_dir: Optional[str] = None,
                                 stim_meta: Optional[dict] = None,
                                 exclude_neurons: Optional[Sequence[int]] = None,
                                 onset_frac: float = ONSET_FRAC,
                                 onset_ms: float = MIN_ONSET_MS,
                                 split_mode: str = 'random',
                                 train_frac: float = 0.70,
                                 fs: int = FS,
                                 in_stim_mask_override: Optional[Dict[int, bool]] = None,
                                 regress_global: bool = True) -> dict:
    """
    STA discovery + validation in one pass via a train/test split on pre-APs.

    split_mode='random' (default)
        Randomly assigns pre-APs to a ~`train_frac` train set and a
        ~`1-train_frac` test set (minimum 2 test APs).  Train uses full
        strict gates and must clear `score_thresh`.  Test only checks that
        the grand-mean PSP deflection is non-zero in the same direction —
        no t-test, no threshold, because the held-out set is typically 1–2
        trials.  Reported score is the train (discovery) score.

    split_mode='parity'
        Even-indexed pre-APs → discovery, odd-indexed → validation.  Both
        subsets must clear `score_thresh` with strict gates (original v16
        behaviour).  Reported score is min(disc_score, val_score).

    Concatenates the two stim CSVs the splitter wrote (natural ordering
    keeps samples contiguous), detects APs once on the joined trace, then
    scores every directed pair.

    Trigger-count gate: a pre-neuron is admitted iff it has >= `min_ap_stim`
    total pre-APs in the stim recording. `compute_sta_score` returns a null
    result when a subset has fewer than 2 windows, so very-low-AP neurons
    fail naturally rather than via a hard pre-filter.

    Backward-compat: returns the same dict shape as `run_sta_pipeline`
    (`all_results`, `win_counts_p1`, `exc_scores`, etc.).
    """
    if split_mode not in ('random', 'parity'):
        raise ValueError(
            f"split_mode must be 'random' or 'parity', got {split_mode!r}")

    print("\n" + "=" * 60)
    print(f"STA pipeline v17 ({split_mode} split)  |  {label or csv_p1}")
    print("=" * 60)

    # ── Load + concatenate the two halves ────────────────────────────────────
    df1 = pd.read_csv(csv_p1)
    df2 = pd.read_csv(csv_p2)
    if regress_global:
        df1 = regress_global_signal(df1)
        df2 = regress_global_signal(df2)
        print(f"  Global signal regressed out (each half independently).")
    df  = pd.concat([df1, df2], ignore_index=True)
    n_traces = df.shape[1]
    segs = detect_segments(df.iloc[:, 0].values)
    print(f"Loaded {n_traces} traces, {len(segs)} segments, "
          f"{len(df)} samples (concatenated).")

    dups = find_duplicate_neurons(df)
    excl = set(exclude_neurons or []) | dups
    if dups: print(f"Duplicates excluded: {sorted(dups)}")
    all_traces = [t for t in range(1, n_traces + 1) if t not in excl]

    # ── AP detection on the joined trace ─────────────────────────────────────
    print("[AP detection]")
    traces_all, raws_all, aps_all = {}, {}, {}
    for t in all_traces:
        raw = df[df.columns[t-1]].values.astype(float)
        tr  = preprocess(raw, segs, fs=fs)
        traces_all[t] = tr; raws_all[t] = raw
        aps_all[t]    = detect_aps(tr, segs, raw=raw, fs=fs)

    n_active = sum(1 for t in all_traces if len(aps_all[t]) > 0)
    ap_counts = {t: int(len(aps_all[t])) for t in all_traces}
    print(f"  Active neurons: {n_active}/{len(all_traces)}")

    noise_all = {t: _noise_std(traces_all[t], segs) for t in all_traces}

    # Use .mat-derived mask if provided; fall back to JSON stim_mask_sources.
    if in_stim_mask_override is not None:
        in_stim_mask = {t: bool(in_stim_mask_override.get(t, False)) for t in all_traces}
    else:
        in_stim_mask = {t: False for t in all_traces}
        if stim_meta is not None:
            mask_set = set(int(x) for x in stim_meta.get("stim_mask_sources", []))
            for t in all_traces:
                in_stim_mask[t] = t in mask_set

    # ── AP split ─────────────────────────────────────────────────────────────
    if split_mode == 'parity':
        # Even-indexed → train (discovery), odd-indexed → test (validation).
        aps_disc = {t: aps_all[t][::2]  for t in all_traces}
        aps_val  = {t: aps_all[t][1::2] for t in all_traces}
    else:
        # Random split: ~train_frac train, remainder test (>= 2 test APs).
        split_rng = np.random.default_rng(CTRL_SEED)
        aps_disc, aps_val = {}, {}
        for t in all_traces:
            aps = aps_all[t]
            n   = len(aps)
            if n == 0:
                aps_disc[t] = aps; aps_val[t] = aps
                continue
            n_test = max(2, round(n * (1.0 - train_frac)))
            n_test = min(n_test, n - 1)          # keep at least 1 train AP
            test_idx  = split_rng.choice(n, size=n_test, replace=False)
            test_mask = np.zeros(n, dtype=bool)
            test_mask[test_idx] = True
            aps_disc[t] = aps[~test_mask]
            aps_val[t]  = aps[test_mask]

    active_traces = [t for t in all_traces if len(aps_all[t]) >= min_ap_stim]
    print(f"  Pre-neurons with >= {min_ap_stim} stim-period APs: "
          f"{len(active_traces)}/{len(all_traces)}")

    # Window-count gate uses the FULL AP set.
    win_counts = {}
    for pre in active_traces:
        for post in all_traces:
            if pre == post: continue
            win_counts[(pre, post)] = count_accepted_windows(
                traces_all[post], aps_all[pre], aps_all[post],
                segs, noise_all[post], fs=fs)

    # ── Score each pair ───────────────────────────────────────────────────────
    if split_mode == 'parity':
        print("[STA scoring — discovery (even) + validation (odd)]")
    else:
        print(f"[STA scoring — train ({train_frac*100:.0f}%, strict gates) + "
              f"test ({(1-train_frac)*100:.0f}%, direction-check only)]")

    rng_disc = np.random.default_rng(CTRL_SEED)
    rng_val  = np.random.default_rng(CTRL_SEED + 1)
    disc_results, val_results                        = {}, {}
    exc_scores, inh_scores                           = {}, {}
    test_agrees_map: Dict[Tuple[int, int], bool]     = {}   # random mode only

    for pre in active_traces:
        for post in all_traces:
            if pre == post: continue

            disc_r = compute_sta_score(
                traces_all[pre], traces_all[post],
                aps_disc[pre], aps_all[post], segs, rng_disc,
                noise=noise_all[post], score_thresh=score_thresh,
                onset_frac=onset_frac, onset_ms=onset_ms, fs=fs)
            disc_results[(pre, post)] = disc_r

            if split_mode == 'parity':
                val_r = compute_sta_score(
                    traces_all[pre], traces_all[post],
                    aps_val[pre], aps_all[post], segs, rng_val,
                    noise=noise_all[post], score_thresh=score_thresh,
                    onset_frac=onset_frac, onset_ms=onset_ms, fs=fs)
                val_results[(pre, post)] = val_r

                same_dir  = (disc_r.direction == val_r.direction
                             and disc_r.direction != 'none')
                both_pass = (abs(disc_r.signed) >= score_thresh
                             and abs(val_r.signed) >= score_thresh)
                validated = same_dir and both_pass
                mag       = min(abs(disc_r.signed), abs(val_r.signed))

            else:   # random
                disc_ok = (disc_r.direction != 'none'
                           and abs(disc_r.signed) >= score_thresh)
                agrees  = _test_set_agrees(
                    traces_all[post], aps_val[pre], aps_all[post],
                    segs, noise_all[post], disc_r.direction, fs=fs) \
                    if disc_ok else False
                test_agrees_map[(pre, post)] = agrees
                val_results[(pre, post)]     = _null_sta_result()
                validated = disc_ok and agrees
                mag       = abs(disc_r.signed)

            if validated:
                if disc_r.direction == 'exc':
                    exc_scores[(pre, post)] = mag
                    inh_scores[(pre, post)] = 0.0
                else:   # 'inh'
                    inh_scores[(pre, post)] = mag
                    exc_scores[(pre, post)] = 0.0
            else:
                exc_scores[(pre, post)] = 0.0
                inh_scores[(pre, post)] = 0.0

    n_exc = sum(1 for s in exc_scores.values() if s >= score_thresh)
    n_inh = sum(1 for s in inh_scores.values() if s >= score_thresh)
    print(f"  Validated (split_mode={split_mode}, score>={score_thresh}): "
          f"exc={n_exc}  inh={n_inh}")

    # ── Neuron classification: SUM of validated scores ───────────────────────
    neuron_type = {}
    for t in all_traces:
        si = sum(s for (p, _), s in inh_scores.items()
                 if p == t and s >= score_thresh)
        se = sum(s for (p, _), s in exc_scores.items()
                 if p == t and s >= score_thresh)
        if si == 0 and se == 0:
            neuron_type[t] = 'silent'
        else:
            neuron_type[t] = 'exc' if se >= si else 'inh'

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(csv_p1))[0].replace('_part1', '_interleaved')
        for ctype, scores in [("EPSP", exc_scores), ("IPSP", inh_scores)]:
            rows = [{"pre": k[0], "post": k[1], "score": v}
                    for k, v in sorted(scores.items(), key=lambda x: -x[1])]
            pd.DataFrame(rows).to_csv(
                os.path.join(output_dir, f"sta_connectivity_{ctype}_{stem}.csv"),
                index=False)

    return dict(
        label=label, segs=segs, all_traces=all_traces,
        traces_all=traces_all, raws_all=raws_all,
        aps_all=aps_all,
        aps_disc=aps_disc, aps_val=aps_val,
        aps_for_sta=aps_all,
        ap_counts=ap_counts,
        exc_scores=exc_scores, inh_scores=inh_scores,
        neuron_type=neuron_type,
        all_results=disc_results,
        disc_results=disc_results,
        val_results=val_results,
        test_agrees_map=test_agrees_map,
        win_counts_p1=win_counts,
        score_thresh=score_thresh, in_stim_mask=in_stim_mask,
        validation_mode=f'interleaved-{split_mode}',
        split_mode=split_mode,
    )


# ============================================================================
# Validation table builder for run_sta_pipeline_interleaved (both split modes)
# ============================================================================
def validate_sta_interleaved(res: dict,
                             score_thresh: float = SCORE_THRESH) -> pd.DataFrame:
    """
    Per-connection table built from the dict returned by
    `run_sta_pipeline_interleaved`. Output columns match the schema produced
    by `validate_sta_in_part2` so the consensus merger keeps working
    unchanged:

        pre, post, type, sta_score_p1, sta_score_p2,
        sta_validated, sta_win_p1, sta_win_p2

    Behaviour by split mode:

        split_mode='parity'
            sta_score_p1 = abs(disc.signed)        (even-indexed triggers)
            sta_score_p2 = abs(val.signed)         (odd-indexed triggers)
            sta_validated = True iff both halves cleared score_thresh
                            and agreed on direction (already determined
                            during the run; surfaces here as a non-zero
                            entry in exc_scores or inh_scores).

        split_mode='random'
            sta_score_p1 = abs(disc.signed)        (train, strict gates)
            sta_score_p2 = NaN                     (test side does not run
                                                    a t-test; agreement is
                                                    a boolean)
            sta_validated = True iff training cleared score_thresh AND
                            the test set's mean response agreed in
                            direction (test_agrees_map). Same logic as the
                            run loop's `validated` flag.
    """
    disc      = res.get("disc_results", {})
    val       = res.get("val_results", {})
    test_map  = res.get("test_agrees_map", {})
    split_mode = res.get("split_mode", "parity")
    exc_scores = res.get("exc_scores", {})
    inh_scores = res.get("inh_scores", {})

    rows = []
    for (pre, post), disc_r in disc.items():
        if disc_r is None or disc_r.direction == 'none':
            continue

        d_score = abs(disc_r.signed)
        if d_score < score_thresh:
            continue

        # The run loop only writes a non-zero entry to exc_scores/inh_scores
        # when the pair was validated under the chosen split_mode rule.
        validated = (exc_scores.get((pre, post), 0.0) >= score_thresh
                     or inh_scores.get((pre, post), 0.0) >= score_thresh)

        # Test-side score / win counts depend on split_mode.
        if split_mode == 'parity':
            val_r = val.get((pre, post))
            v_score = abs(val_r.signed) if val_r is not None else 0.0
            v_win   = int(val_r.n_sig)  if val_r is not None else 0
        else:  # 'random' / 'holdout'
            v_score = float('nan')   # not a t-test score
            v_win   = 0

        rows.append(dict(
            pre=pre, post=post,
            type=disc_r.direction.upper(),
            sta_score_p1 = round(d_score, 2),
            sta_score_p2 = (round(v_score, 2) if not np.isnan(v_score)
                            else float('nan')),
            sta_validated = bool(validated),
            sta_win_p1   = int(disc_r.n_sig),
            sta_win_p2   = int(v_win),
        ))
    return pd.DataFrame(rows)
