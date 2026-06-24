"""
consensus.py — pipeline v17 merger.

Joins the per-connection tables from the SCS (event-pairing, spontaneous
period) and STA (waveform-average, stim period) branches into a single
unified table, and produces a tiered per-neuron classification combining
both methods' votes.

Per-connection consensus tier:

    both       — flagged in both methods, same direction (highest confidence)
    scs_only   — flagged in SCS only
    sta_only   — flagged in STA only
    conflict   — flagged in both but with opposite directions

Per-neuron classification tier:

    confident_exc / confident_inh — both methods classify the same way
                                    (and at least one method has a non-no_valid_outgoing_connections
                                     classification at threshold)
    putative_exc  / putative_inh  — one method classifies, the other is no_valid_outgoing_connections
    ambiguous                     — methods classify differently
    no_valid_outgoing_connections                        — neither method assigns a connection type

Optional metadata join (drug / condition) is left to the caller — the
helper `attach_metadata` does it for an FOV-level frame.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


# ============================================================================
# Per-connection union
# ============================================================================
def merge_connections(scs_df: pd.DataFrame, sta_df: pd.DataFrame,
                      fov_label: str = "") -> pd.DataFrame:
    """
    Outer-join SCS and STA per-connection tables on (pre, post, type).

    Inputs (both produced by the per-method `validate_*_in_part2` helpers):
        scs_df : columns [pre, post, type, scs_score_p1, scs_score_p2,
                          scs_validated, scs_n_ap_p2]
        sta_df : columns [pre, post, type, sta_score_p1, sta_score_p2,
                          sta_validated, sta_win_p1, sta_win_p2]

    Returns a frame with one row per (pre, post, type) seen in EITHER
    method, with NaN-filled scores for the method that didn't fire,
    plus a `consensus_tier` column.
    """
    if scs_df.empty and sta_df.empty:
        return _empty_merged(fov_label)

    scs = scs_df.copy() if not scs_df.empty else _scs_skeleton()
    sta = sta_df.copy() if not sta_df.empty else _sta_skeleton()

    # Outer join in two passes so we capture rows present in only one method.
    merged = pd.merge(
        scs, sta,
        on=["pre", "post", "type"], how="outer",
        suffixes=("", "_dup"),
    )

    # Detect direction conflicts: same (pre, post) but different `type`
    # in each method. Build a small lookup keyed by (pre,post) -> set of types.
    seen = {}
    for df in (scs_df, sta_df):
        if df.empty: continue
        for _, r in df.iterrows():
            seen.setdefault((int(r["pre"]), int(r["post"])), set()).add(r["type"])

    # Base columns / fillers
    for c in ("scs_score_p1", "scs_score_p2", "scs_n_ap_p2",
              "sta_score_p1", "sta_score_p2", "sta_win_p1", "sta_win_p2"):
        if c not in merged.columns:
            merged[c] = np.nan

    if "scs_validated" not in merged.columns:
        merged["scs_validated"] = False
    if "sta_validated" not in merged.columns:
        merged["sta_validated"] = False
    merged["scs_validated"] = merged["scs_validated"].fillna(False).astype(bool)
    merged["sta_validated"] = merged["sta_validated"].fillna(False).astype(bool)

    # Consensus tier
    tiers = []
    for _, r in merged.iterrows():
        in_scs = bool(r["scs_validated"])
        in_sta = bool(r["sta_validated"])
        types_seen = seen.get((int(r["pre"]), int(r["post"])), set())
        if in_scs and in_sta:
            tiers.append("both")
        elif in_scs:
            tiers.append("scs_only")
        elif in_sta:
            tiers.append("sta_only")
        else:
            # Both methods saw the pair but neither validated.
            # If the pair shows up in opposite directions across methods,
            # flag the conflict; otherwise mark unvalidated.
            tiers.append("conflict" if len(types_seen) > 1 else "unvalidated")

    merged["consensus_tier"] = tiers
    merged.insert(0, "fov", fov_label)
    return merged.reset_index(drop=True)


def _scs_skeleton() -> pd.DataFrame:
    return pd.DataFrame(columns=["pre", "post", "type",
                                 "scs_score_p1", "scs_score_p2",
                                 "scs_validated", "scs_n_ap_p2"])


def _sta_skeleton() -> pd.DataFrame:
    return pd.DataFrame(columns=["pre", "post", "type",
                                 "sta_score_p1", "sta_score_p2",
                                 "sta_validated", "sta_win_p1", "sta_win_p2"])


def _empty_merged(fov_label: str) -> pd.DataFrame:
    cols = ["fov", "pre", "post", "type",
            "scs_score_p1", "scs_score_p2", "scs_validated", "scs_n_ap_p2",
            "sta_score_p1", "sta_score_p2", "sta_validated",
            "sta_win_p1", "sta_win_p2", "consensus_tier"]
    df = pd.DataFrame(columns=cols)
    if fov_label:
        df["fov"] = []
    return df


# ============================================================================
# Per-neuron tiered classification
# ============================================================================
def neuron_types_from_merged(merged: pd.DataFrame,
                              validated_col: str,
                              pre_col: str = 'pre',
                              type_col: str = 'type') -> Dict[int, str]:
    """
    Derive a {trace_id: 'exc'|'inh'|'no_valid_outgoing_connections'|'na'} dict from the merged
    connection table using one method's validation flag.

    This is the preferred input to classify_neurons because it uses the same
    discovered connection set for both methods and each method's own validated
    flag — avoiding the asymmetry between SCS discovery scores (pre-validation)
    and STA validated scores that caused artificially few 'confident' labels.

    Parameters
    ----------
    merged        : output of merge_connections (rows = discovered connections)
    validated_col : 'scs_validated' or 'sta_validated'
    """
    if merged.empty or validated_col not in merged.columns:
        return {}
    val = merged[merged[validated_col] == True]
    types: Dict[int, str] = {}
    for t in merged[pre_col].dropna().unique():
        t = int(t)
        sub = val[val[pre_col] == t]
        ne = int((sub[type_col].str.upper() == 'EXC').sum())
        ni = int((sub[type_col].str.upper() == 'INH').sum())
        if ne == 0 and ni == 0:
            types[t] = 'no_valid_outgoing_connections'
        elif ne == ni:
            types[t] = 'na'
        elif ne > ni:
            types[t] = 'exc'
        else:
            types[t] = 'inh'
    return types


def classify_neurons(scs_neuron_type: Dict[int, str],
                     sta_neuron_type: Dict[int, str],
                     all_traces: Iterable[int],
                     in_stim_mask: Optional[Dict[int, bool]] = None
                     ) -> pd.DataFrame:
    """
    Combine the SCS count-rule classification with the STA score-sum
    classification into a four-level tier:

        confident_<exc|inh>  : both methods agree (and not no_valid_outgoing_connections)
        putative_<exc|inh>   : one method calls a type, the other is no_valid_outgoing_connections
        ambiguous            : methods call opposite types
        no_valid_outgoing_connections               : both methods no_valid_outgoing_connections

    `scs_neuron_type` values: 'exc' | 'inh' | 'no_valid_outgoing_connections' | 'na'
    `sta_neuron_type` values: 'exc' | 'inh' | 'no_valid_outgoing_connections'
    'na' from SCS (count-tied) is treated as 'ambiguous' if STA disagrees.
    """
    rows = []
    for t in sorted(set(all_traces)):
        s = scs_neuron_type.get(t, "no_valid_outgoing_connections")
        a = sta_neuron_type.get(t, "no_valid_outgoing_connections")

        s_is_silent = s in ("no_valid_outgoing_connections",)
        a_is_silent = a == "no_valid_outgoing_connections"

        if s_is_silent and a_is_silent:
            tier = "no_valid_outgoing_connections"
        elif s_is_silent:
            tier = f"putative_{a}"
        elif a_is_silent:
            tier = f"putative_{s}" if s in ("exc", "inh") else "ambiguous"
        elif s == a and s in ("exc", "inh"):
            tier = f"confident_{s}"
        else:
            tier = "ambiguous"

        rows.append(dict(
            trace=t,
            scs_type=s, sta_type=a,
            consensus_type=tier,
            in_stim_mask=bool(in_stim_mask.get(t, False)) if in_stim_mask else False,
        ))
    return pd.DataFrame(rows)


# ============================================================================
# Metadata attachment (Excel join)
# ============================================================================
def attach_metadata(df: pd.DataFrame,
                    metadata_path: str,
                    plate_number: int,
                    fov_col: str = "fov",
                    keep_cols=("parametersTested", "testingCondition", "drug1"),
                    ) -> pd.DataFrame:
    """
    Left-join an FOV-keyed table with the plate's expMetadata.xlsx rows.
    Returns the same df with extra columns from `keep_cols` (filtered to
    those that actually exist in the Excel sheet).
    """
    if not metadata_path:
        return df
    meta = pd.read_excel(metadata_path, header=0, skiprows=[1])
    meta = meta[meta["plateNumber"] == plate_number].copy()
    meta["fov"] = meta["fov"].apply(
        lambda x: f"FOV_{int(x):04d}" if str(x).strip().isdigit() else str(x).strip())
    keep = [c for c in keep_cols if c in meta.columns]
    return df.merge(meta[["fov", *keep]],
                    left_on=fov_col, right_on="fov", how="left")
