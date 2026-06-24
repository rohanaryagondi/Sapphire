"""
endpoints.py — Sapphire wiring for the vendored robyn_scs SCS/STA connectivity pipeline.

Thin, correctly-wired CALLABLE endpoints AROUND the vendored analysis code in
`vendor/robyn_scs/utils/`. The logic is NOT reimplemented here and `vendor/` is NOT
modified — each endpoint imports the real implementation and forwards arguments; the
docstrings name the exact vendored function(s) called (`module.func` + line).

POSTURE:
- The Sapphire ENGINE stays stdlib-only. The heavy scientific deps robyn_scs needs
  (numpy, scipy, pandas, matplotlib) are imported LAZILY inside the endpoints (this
  tool's subprocess) — importing THIS module touches no third-party package.
- `vendor/robyn_scs/utils` uses intra-package relative imports, so it must be imported
  as the package `utils` with `vendor/robyn_scs` on sys.path. `_utils()` / `_viz()` set
  that up once and assert they loaded the VENDORED package (fail-loud on any name clash).
- WIRING ONLY (per the brief): no live_engine/harness/contract wiring, and the full
  pipeline is not run here (it needs MATLAB-split imaging CSVs). Verify by import +
  signature alignment; see `sapphire-orchestrator/tests/test_robyn_scs_endpoints.py`.

DATA LAYOUT: real inputs are MATLAB-split imaging CSVs laid out as
  <plate>/v17_traces/FOV_XXXX_<base>_{spont,stim}_part{1,2}.csv  +  *_stim_meta.json
The MATLAB splitter (`SCS_MovieSplit_v17.m`) is a manual upstream step — documented, not wrapped.

Vendored source: `vendor/robyn_scs/` (q-state-biosciences/Analysis@robyn_scs `a1d5dc5`; see VENDORED.md).
Robyn granted full permission to use the code as-is.
"""
from __future__ import annotations

import functools
import glob
import os
import re
import sys

__all__ = [
    "detect_events", "run_scs", "run_sta", "load_stim_metadata", "stim_mask_from_sidecar",
    "merge_and_classify", "visualize", "discover_fov_quartets", "run_fov", "run_batch",
]

# repo_root/tools/robyn_scs/endpoints.py  ->  repo_root/vendor/robyn_scs
_VENDOR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "vendor", "robyn_scs")
)


def _ensure_path():
    if _VENDOR not in sys.path:
        sys.path.insert(0, _VENDOR)


@functools.lru_cache(maxsize=1)
def _utils():
    """Lazily import the vendored core `utils` subpackages — numpy/scipy/pandas live HERE, not the
    engine. Returns (data_utils, scs_utils, sta_utils, consensus). Fails loudly if a non-vendored
    `utils` package shadows the vendored one (defensive: `utils` is a generic name)."""
    _ensure_path()
    import utils  # the vendored package at vendor/robyn_scs/utils
    expected = os.path.normpath(os.path.join(_VENDOR, "utils"))
    got = os.path.normpath(os.path.dirname(utils.__file__))
    if got != expected:
        raise RuntimeError(f"wrong 'utils' package imported: {utils.__file__} (expected under {expected})")
    import utils.data_utils as data_utils
    import utils.scs_utils as scs_utils
    import utils.sta_utils as sta_utils
    import utils.consensus as consensus
    return data_utils, scs_utils, sta_utils, consensus


@functools.lru_cache(maxsize=1)
def _viz():
    """Lazily import the vendored visualization module — matplotlib lives HERE, not the engine."""
    _ensure_path()
    import utils.visualization as visualization
    return visualization


# ── Primitives ────────────────────────────────────────────────────────
def detect_events(raw, *, fs=500, apd50_max=5, snr_gate=3.5, ap_rise_max=20.0,
                  ap_snr_frac=0.3, pbr_thresh=0.6):
    """Preprocess a single raw fluorescence trace and detect action potentials.

    Wires, in order, `vendor/robyn_scs/utils/data_utils.py`:
      `detect_segments` (:39) -> `preprocess` (:57) -> `detect_aps` (:205).
    Input: `raw` = a 1-D array-like fluorescence trace (NaN-gapped segments allowed).
    Returns: {"segments": List[(start,end)], "trace": np.ndarray (denoised), "aps": np.ndarray (AP indices)}.
    Cheap + offline (no CSV / MATLAB) — the synthetic smoke-test path.
    """
    du, _, _, _ = _utils()
    segs = du.detect_segments(raw)
    trace = du.preprocess(raw, segs, fs=fs)
    aps = du.detect_aps(trace, segs, raw=raw, apd50_max=apd50_max, snr_gate=snr_gate,
                        ap_rise_max=ap_rise_max, ap_snr_frac=ap_snr_frac, pbr_thresh=pbr_thresh, fs=fs)
    return {"segments": segs, "trace": trace, "aps": aps}


# ── Per-method branches ───────────────────────────────────────────────
def run_scs(spont_p1_csv, spont_p2_csv, *, label="", score_thresh=0.7, output_dir=None,
            exclude_neurons=None, regress_global=True, min_ap=1, val_score_thresh=None):
    """SCS (spontaneous, discrete-event-pairing) branch for one FOV.

    Wires `vendor/robyn_scs/utils/scs_utils.py`: `run_scs_pipeline` (:635) on the P1 and P2 CSVs,
    then `validate_scs_in_part2` (:767). Mirrors run_one_fov's SCS branch (SCS_Pipeline_v17.ipynb).
    Inputs: paths to the two spontaneous-half CSVs. Returns {"res_p1", "res_p2", "scs_df": DataFrame}.
    """
    _, scs, _, _ = _utils()
    res1 = scs.run_scs_pipeline(spont_p1_csv, label=f"{label} P1".strip(), score_thresh=score_thresh,
                                output_dir=output_dir, exclude_neurons=exclude_neurons, regress_global=regress_global)
    res2 = scs.run_scs_pipeline(spont_p2_csv, label=f"{label} P2".strip(), score_thresh=score_thresh,
                                output_dir=output_dir, exclude_neurons=exclude_neurons, regress_global=regress_global)
    scs_df = scs.validate_scs_in_part2(
        res1, res2, score_thresh=score_thresh,
        val_score_thresh=score_thresh if val_score_thresh is None else val_score_thresh, min_ap=min_ap)
    return {"res_p1": res1, "res_p2": res2, "scs_df": scs_df}


def run_sta(stim_p1_csv, stim_p2_csv, *, stim_meta=None, label="", score_thresh=1.7,
            min_ap_stim=2, output_dir=None, exclude_neurons=None, in_stim_mask_override=None,
            onset_ms=5.0, regress_global=True):
    """STA (stim, spike-triggered-average) branch for one FOV.

    Wires `vendor/robyn_scs/utils/sta_utils.py`: `run_sta_pipeline_interleaved` (:733) then
    `validate_sta_interleaved` (:973). `stim_meta` may be a loaded dict OR a path to a
    *_stim_meta.json (loaded via `data_utils.load_stim_meta`). `in_stim_mask_override`: optional
    {trace_id: bool} (e.g. from `stim_mask_from_sidecar`); None -> the pipeline falls back to the
    JSON stim_mask_sources. Returns {"res": dict|None, "sta_df": DataFrame}.
    """
    du, _, sta, _ = _utils()
    if isinstance(stim_meta, str):
        stim_meta = du.load_stim_meta(stim_meta)
    res = sta.run_sta_pipeline_interleaved(
        stim_p1_csv, stim_p2_csv, label=label, score_thresh=score_thresh, min_ap_stim=min_ap_stim,
        output_dir=output_dir, stim_meta=stim_meta, exclude_neurons=exclude_neurons,
        in_stim_mask_override=in_stim_mask_override, onset_ms=onset_ms, regress_global=regress_global)
    import pandas as pd  # lazy (tool subprocess)
    sta_df = sta.validate_sta_interleaved(res, score_thresh=score_thresh) if res is not None else pd.DataFrame()
    return {"res": res, "sta_df": sta_df}


# ── Stim-metadata helpers ─────────────────────────────────────────────
def load_stim_metadata(meta_path):
    """Load a *_stim_meta.json sidecar. Thin wrapper for `data_utils.load_stim_meta`. Returns dict."""
    du, _, _, _ = _utils()
    return du.load_stim_meta(meta_path)


def stim_mask_from_sidecar(mat_path, meta):
    """Build the per-neuron in-stim mask from a MATLAB `EnsembleDmdMasks.mat` sidecar.

    Wires `data_utils.load_ensemble_mask_sidecar`(mat_path) -> `data_utils.stim_mask_from_mat`(sidecar, meta).
    `meta` is a loaded stim_meta dict (see `load_stim_metadata`). Returns {trace_id: bool} — the optional
    `in_stim_mask_override` for `run_sta` / `run_fov`. If you don't have the .mat sidecar, omit it and the
    STA pipeline falls back to the JSON stim_mask_sources.
    """
    du, _, _, _ = _utils()
    sidecar = du.load_ensemble_mask_sidecar(mat_path)
    return du.stim_mask_from_mat(sidecar, meta)


# ── Consensus ─────────────────────────────────────────────────────────
def merge_and_classify(scs_df, sta_df, *, scs_res=None, sta_res=None, all_traces=None,
                       fov_label="", in_stim_mask=None):
    """Merge the SCS + STA per-connection tables and classify each neuron into a consensus tier.

    Wires `vendor/robyn_scs/utils/consensus.py`: `merge_connections` (:40) ->
    `neuron_types_from_merged` (x2, for 'scs_validated' and 'sta_validated') -> `classify_neurons`
    (:176). Mirrors run_one_fov's consensus block. `all_traces`: the union of neuron ids; if None it is
    derived from `scs_res`/`sta_res` ['all_traces'] (the per-pipeline result dicts).
    Returns {"merged_connections": DataFrame, "neuron_tiers": DataFrame}.
    """
    _, _, _, cons = _utils()
    merged = cons.merge_connections(scs_df, sta_df, fov_label=fov_label)
    if all_traces is None:
        a = list(scs_res.get("all_traces", [])) if scs_res else []
        b = list(sta_res.get("all_traces", [])) if sta_res else []
        all_traces = sorted(set(a + b))
    scs_nt = cons.neuron_types_from_merged(merged, "scs_validated")
    sta_nt = cons.neuron_types_from_merged(merged, "sta_validated")
    neuron_tiers = cons.classify_neurons(scs_nt, sta_nt, all_traces, in_stim_mask=in_stim_mask)
    return {"merged_connections": merged, "neuron_tiers": neuron_tiers}


# ── Visualization ─────────────────────────────────────────────────────
_VIS_KINDS = ("consensus_heatmap", "neuron_tier_bar")


def visualize(kind, *, output_path=None, **artifacts):
    """Render one of the headline plots (`vendor/robyn_scs/utils/visualization.py`).

    kind='consensus_heatmap' -> `plot_consensus_heatmap` (:246) (kwargs: merged_df, all_traces, [title]).
    kind='neuron_tier_bar'   -> `plot_neuron_tier_bar` (:1388) (kwarg: neuron_tier_df).
    `output_path` is forwarded (None -> the vendored function's default behavior).
    """
    viz = _viz()
    if kind == "consensus_heatmap":
        return viz.plot_consensus_heatmap(
            artifacts["merged_df"], artifacts["all_traces"], output_path=output_path,
            title=artifacts.get("title", "Consensus connectivity (v17)"))
    if kind == "neuron_tier_bar":
        return viz.plot_neuron_tier_bar(artifacts["neuron_tier_df"], output_path=output_path)
    raise ValueError(f"unknown kind {kind!r}; expected one of {_VIS_KINDS}")


# ── FOV + batch orchestration ─────────────────────────────────────────
def discover_fov_quartets(input_dir):
    """Discover FOV input quartets in a `<plate>/v17_traces` dir (PURE STDLIB — no heavy deps).

    Mirrors `discover_fov_quartets` in SCS_Pipeline_v17.ipynb: for each `*_stim_meta.json`, resolve the
    sibling `_spont_part{1,2}.csv` / `_stim_part{1,2}.csv` and extract `FOV_XXXX`. Returns a list of dicts:
      {fov, meta, spont_p1, spont_p2, stim_p1, stim_p2, has_spont, has_stim}.
    """
    out = []
    for meta_path in sorted(glob.glob(os.path.join(input_dir, "*_stim_meta.json"))):
        base = meta_path[: -len("_stim_meta.json")]
        sp1, sp2 = base + "_spont_part1.csv", base + "_spont_part2.csv"
        st1, st2 = base + "_stim_part1.csv", base + "_stim_part2.csv"
        m = re.search(r"(FOV_\d{4})", os.path.basename(base))
        fov = m.group(1) if m else os.path.basename(base)
        has_spont = os.path.exists(sp1) and os.path.exists(sp2)
        has_stim = os.path.exists(st1) and os.path.exists(st2)
        if not (has_spont or has_stim):
            continue
        out.append(dict(
            fov=fov, meta=meta_path,
            spont_p1=sp1 if has_spont else None, spont_p2=sp2 if has_spont else None,
            stim_p1=st1 if has_stim else None, stim_p2=st2 if has_stim else None,
            has_spont=has_spont, has_stim=has_stim))
    return out


def _canonical_excludes(quartet):
    """Union of duplicate-trace IDs across all four of an FOV's CSVs (mirrors run_one_fov's helper).

    Composes `data_utils.find_duplicate_neurons` over each present CSV. Excluding the SAME canonical
    duplicates from BOTH branches keeps the SCS and STA `all_traces` sets aligned — the notebook's CP-2
    guard (a trace that is a duplicate in one half but unique in another would otherwise be dropped by one
    method and kept by the other). Returns a sorted id list.
    """
    import pandas as pd  # lazy
    du, _, _, _ = _utils()
    dups = set()
    for key in ("spont_p1", "spont_p2", "stim_p1", "stim_p2"):
        p = quartet.get(key)
        if p and os.path.exists(p):
            dups |= du.find_duplicate_neurons(pd.read_csv(p))
    return sorted(dups)


def run_fov(quartet, *, scs_score_thresh=0.7, sta_score_thresh=1.7, scs_min_ap=1, sta_min_ap=2,
            output_dir=None, exclude_neurons=None, scs_val_score_thresh=None,
            in_stim_mask_override=None, regress_global=True):
    """Full single-FOV chain, mirroring `run_one_fov` (SCS_Pipeline_v17.ipynb).

    `quartet`: a dict from `discover_fov_quartets`. Order: `load_stim_metadata` -> canonical-duplicate
    exclusion -> [SCS: `run_scs`] -> [STA: `run_sta`] -> `merge_and_classify`. Each branch is skipped
    (empty table) when its CSVs are absent, exactly as run_one_fov does. Returns
      {fov, merged_connections, neuron_tiers, scs_df, sta_df, scs_res, sta_res, excludes, meta}.

    `exclude_neurons`: duplicate-trace IDs excluded from BOTH branches so their `all_traces` stay aligned
    (the notebook's CP-2 guard); None -> auto-computed via `_canonical_excludes(quartet)`.
    `scs_val_score_thresh`: the SCS *validation* threshold; None -> pinned to the vendored
    `scs_utils.SCORE_THRESH` constant, decoupled from the discovery `scs_score_thresh` (as run_one_fov pins
    validation to SCS_SCORE_THRESH regardless of the discovery threshold). The optional `.mat` ensemble-mask
    + morphological-PSP diagnostics from run_one_fov are not run by default; pass
    `in_stim_mask_override=stim_mask_from_sidecar(...)` to supply the .mat-derived mask.
    """
    import pandas as pd  # lazy
    du, scs_mod, _, _ = _utils()
    fov = quartet.get("fov", "")
    meta = du.load_stim_meta(quartet["meta"]) if quartet.get("meta") else None

    # canonical duplicate-trace exclusions shared by BOTH branches (keeps all_traces aligned)
    excludes = _canonical_excludes(quartet) if exclude_neurons is None else exclude_neurons
    val_thresh = scs_mod.SCORE_THRESH if scs_val_score_thresh is None else scs_val_score_thresh

    scs_res = {"res_p1": None, "res_p2": None, "scs_df": pd.DataFrame()}
    if quartet.get("has_spont"):
        scs_res = run_scs(quartet["spont_p1"], quartet["spont_p2"], label=f"{fov} spont",
                          score_thresh=scs_score_thresh, output_dir=output_dir, min_ap=scs_min_ap,
                          exclude_neurons=excludes, val_score_thresh=val_thresh, regress_global=regress_global)
    scs_df = scs_res["scs_df"]

    sta_out = {"res": None, "sta_df": pd.DataFrame()}
    if quartet.get("has_stim"):
        sta_out = run_sta(quartet["stim_p1"], quartet["stim_p2"], stim_meta=meta, label=f"{fov} stim",
                          score_thresh=sta_score_thresh, min_ap_stim=sta_min_ap, output_dir=output_dir,
                          exclude_neurons=excludes, in_stim_mask_override=in_stim_mask_override,
                          regress_global=regress_global)
    sta_df, sta_res = sta_out["sta_df"], sta_out["res"]

    in_stim_mask = in_stim_mask_override
    if in_stim_mask is None and sta_res is not None:
        in_stim_mask = sta_res.get("in_stim_mask")
    mc = merge_and_classify(scs_df, sta_df, scs_res=scs_res.get("res_p1"), sta_res=sta_res,
                            fov_label=fov, in_stim_mask=in_stim_mask)
    return {"fov": fov, "merged_connections": mc["merged_connections"], "neuron_tiers": mc["neuron_tiers"],
            "scs_df": scs_df, "sta_df": sta_df, "scs_res": scs_res, "sta_res": sta_res,
            "excludes": excludes, "meta": meta}


def run_batch(input_dir, output_dir=None, *, scs_score_thresh=0.7, sta_score_thresh=1.7,
              scs_min_ap=1, sta_min_ap=2, regress_global=True):
    """Discover all FOV quartets under `input_dir`, `run_fov` each, concat plate-level tables.

    Mirrors the notebook's batch path: `discover_fov_quartets` -> loop `run_one_fov` -> `pd.concat` the
    per-FOV merged-connection + neuron-tier tables into plate-level frames (written to `output_dir` if
    given, as `merged_connections_all_fovs.csv` / `merged_neurons_all_fovs.csv`). Per-FOV failures are
    captured (not raised), as in the notebook, so one bad FOV doesn't sink the plate. Returns
      {quartets, results, failed, merged_all, neurons_all}.
    """
    import pandas as pd  # lazy
    quartets = discover_fov_quartets(input_dir)
    results, all_merged, all_neurons, failed = [], [], [], []
    for q in quartets:
        try:
            r = run_fov(q, scs_score_thresh=scs_score_thresh, sta_score_thresh=sta_score_thresh,
                        scs_min_ap=scs_min_ap, sta_min_ap=sta_min_ap, output_dir=output_dir,
                        regress_global=regress_global)
            results.append(r)
            if r["merged_connections"] is not None and len(r["merged_connections"]):
                all_merged.append(r["merged_connections"])
            if r["neuron_tiers"] is not None and len(r["neuron_tiers"]):
                all_neurons.append(r["neuron_tiers"])
        except Exception as exc:  # mirror run_one_fov's per-FOV try/except — capture, don't raise
            failed.append({"fov": q.get("fov", ""), "error": str(exc)})
    merged_all = pd.concat(all_merged, ignore_index=True) if all_merged else pd.DataFrame()
    neurons_all = pd.concat(all_neurons, ignore_index=True) if all_neurons else pd.DataFrame()
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        if not merged_all.empty:
            merged_all.to_csv(os.path.join(output_dir, "merged_connections_all_fovs.csv"), index=False)
        if not neurons_all.empty:
            neurons_all.to_csv(os.path.join(output_dir, "merged_neurons_all_fovs.csv"), index=False)
    return {"quartets": quartets, "results": results, "failed": failed,
            "merged_all": merged_all, "neurons_all": neurons_all}
