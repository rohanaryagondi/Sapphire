# Pipeline v16 — Merged SCS + STA Neuronal Connectivity

Combines two complementary detection branches into one notebook so a single
plate can be analyzed with both methods and the results joined into a unified,
tiered map of putative connections and neuron identities.

---

## What's new vs. v14

| Area | v14 | v16 |
|---|---|---|
| Recording use | Two separate notebooks, one plate each | One notebook; SCS reads spontaneous halves, STA reads stim halves of the **same** movie |
| MATLAB splitter | Two scripts (one for spont, one for stim) | One script (`SCS_MovieSplit_v16.m`) writes all four CSVs + a stim-metadata JSON in one pass |
| EPSP detection bug | EPSPs assigned outside the `for tidx` loop — only the last neuron's EPSPs survived | Fixed: assignment lives inside the loop, every neuron gets its events |
| Pairing window | SCS used `IPSP_WINDOW=100`, `EPSP_WINDOW=50`; STA used a 0–150 ms response zone | All three aligned to **150 ms** (`PSP_WINDOW = 75` samples in SCS) |
| Neuron classification | Each method used its own rule (count vs. score-sum) | Both rules computed; consensus tier `confident_*` / `putative_*` / `ambiguous` / `silent` |
| Stim metadata | None | `in_stim_mask` flag per pre-neuron; optional stim-locked AP subset for STA diagnostic |

---

## Folder layout

```
v16/
  SCS_MovieSplit_v16.m            <- MATLAB: savefast + blobtraces.mat -> 4 CSVs + JSON
  pipeline_v16_merged.ipynb       <- single notebook, single-FOV/batch toggle
  README_v16.md                   <- this file
  utils/
    __init__.py
    data_utils.py                 <- shared: detect_segments, preprocess, detect_aps,
                                            find_duplicate_neurons, _noise_std,
                                            stim metadata loader
    scs_utils.py                  <- discrete-event branch: PSP detection, score table,
                                            pairing, conflict resolution
    sta_utils.py                  <- waveform branch: STA windows, t-test, asymmetric gates
    consensus.py                  <- merger: per-pair union + tiered neuron classification
    visualization.py              <- one example each (heatmap, top SCS, top STA, AP, PSP,
                                            P1/P2 STA, neuron-tier bar, condition summary)
```

---

## Step 1 — MATLAB splitter

Edit `PLATE_DIR` at the top of `SCS_MovieSplit_v16.m` and run. For each FOV
folder under the plate it produces, into a single `<plate>/v16_traces/`
folder:

```
FOV_XXXX_<base>_spont_part1.csv     <- samples 1..3475      (first half of 13.9 s spont)
FOV_XXXX_<base>_spont_part2.csv     <- samples 3476..6950   (second half)
FOV_XXXX_<base>_stim_part1.csv      <- first half of stim block (samples 6951..mid)
FOV_XXXX_<base>_stim_part2.csv      <- second half (mid..end)
FOV_XXXX_<base>_stim_meta.json      <- stim_mask sources, per-source stim frames remapped
                                       into part1/part2 local sample numbers
```

If the recording is shorter than the configured spontaneous block
(`SPONT_END_SAMPLE = 6950`), the FOV is skipped with a clear log line.
If the stim block contains NaN-gap segments, the script splits at the
segment boundary closest to the midpoint so each half holds an equal
integer number of segments — change inside the script if you want a
different rule. If it's a single contiguous block, it splits at the
sample-count midpoint.

Stim-mask membership rule (note in the script too): a source is flagged
`in_stim_mask` if `stimPixelMask(blobInfo.row, blobInfo.col) > 0` —
i.e. the mask is sampled at the source's anchor pixel only. If you'd
rather use a "majority of the blob's pixels in the mask" rule, edit the
`IS_IN_STIM_MASK` block.

The `*.qsm.blobtraces.h5` sibling file holds the same data as the `.mat`
and is friendlier to load directly from Python — if you ever want to skip
the MATLAB step, the splitter logic translates straightforwardly to an
`h5py` call. For now the MATLAB script is the canonical entry point.

---

## Step 2 — Notebook

Open `pipeline_v16_merged.ipynb`. At the top:

```python
INPUT_DIR    = r'<plate path>\v16_traces'
SELECTED_FOV = 'FOV_0001'        # used only when MODE = 'single'
MODE         = 'single'          # or 'batch'

SCS_SCORE_THRESH = 1.0           # SCS default (kept distinct from STA per spec)
STA_SCORE_THRESH = 1.3           # STA default
SCS_MIN_AP       = 1
STA_MIN_AP       = 2

STA_USE_STIM_LOCKED = False      # diagnostic: STA only over stim-locked APs
```

Run top-to-bottom. The single-FOV and batch paths share the same
`run_one_fov(quartet)` function, so they always agree.

---

## Per-method gates (kept identical to v14, except where v16 explicitly aligns them)

### SCS (event-pairing, spontaneous period)

| Gate | Value | Notes |
|------|-------|-------|
| AP detection | half-width <= 10 samples (20 ms), local SNR >= 3.5x, rise <= 20 ms, >= 30% of trace max SNR | shared with STA |
| Pairing window | 150 ms (`PSP_WINDOW = 75`) | EPSP and IPSP unified to STA's response zone |
| Onset minimum | 5 ms | unchanged |
| Min above-threshold duration | 10 ms | unchanged |
| Score | binomial-style table | unchanged |
| Default score threshold | 1.0 | per spec |

### STA (waveform average, stim period)

| Gate | Discovery (P1) | Validation (P2) |
|------|:---:|:---:|
| Baseline drift | \|pre-AP mean\| <= 3x noise | same |
| Median SNR | >= 4.0x noise | >= 2.5x noise (relaxed, unconditional) |
| Welch t-test | p < 0.05 | same |
| Onset timing | peak >= 20 ms post-AP | >= 10 ms |
| Accepted-window count | >= 2 | >= 3 |

---

## Consensus rules

**Per connection** (one row per `(fov, pre, post, type)` across both methods):

| Tier | Meaning |
|------|---------|
| `both` | Validated by SCS *and* STA in the same direction |
| `scs_only` | Only the SCS branch validated |
| `sta_only` | Only the STA branch validated |
| `conflict` | Both methods see the pair, in opposite directions, and neither validated cleanly |
| `unvalidated` | Pair seen but no method's validation passed |

**Per neuron** (combines SCS count rule and STA score-sum rule):

| Tier | Meaning |
|------|---------|
| `confident_exc` / `confident_inh` | Both methods classify the neuron the same way |
| `putative_exc` / `putative_inh` | One method classifies, the other is silent |
| `ambiguous` | Methods disagree on direction, or SCS calls `na` (count tie) |
| `silent` | Neither method assigns a connection type |

Each neuron-row also carries `in_stim_mask` (from the stim_meta.json) so
you can inspect whether driven neurons (which produce the cleanest STA
triggers) end up with cleaner consensus calls than non-driven ones.

---

## Outputs

Per FOV (under `<plate>/v16_outputs/FOV_XXXX/`):

```
scs_connectivity_EPSP_<stem>.csv     <- per-method, per-part raw scores (audit trail)
scs_connectivity_IPSP_<stem>.csv
sta_connectivity_EPSP_<stem>.csv
sta_connectivity_IPSP_<stem>.csv
merged_connections_<FOV>.csv         <- unified per-connection table with consensus_tier
merged_neurons_<FOV>.csv             <- per-neuron tier table
consensus_heatmap.png                <- (single-FOV mode) one example each
scs_top_exc.png / scs_top_inh.png
sta_top_exc.png / sta_top_inh.png
ap_waveform.png / psp_waveforms.png
sta_p1p2_T<pre>_T<post>.png
neuron_tier_bar.png
```

Across the plate (under `<plate>/v16_outputs/`):

```
merged_connections_all_fovs.csv                 <- batch only
merged_neurons_all_fovs.csv                     <- batch only
merged_connections_all_fovs_with_metadata.csv   <- after Excel join
condition_summary.png
```

The pre-existing v14 outputs are not touched.

---

## Stim-locked STA diagnostic (optional)

Set `STA_USE_STIM_LOCKED = True` at the top of the notebook to restrict
STA triggers to APs that fall within +/- 5 samples of any stim frame for
that source — only for sources that are in the stim mask. Sources outside
the mask continue to use all their APs. This is a strict diagnostic: a
connection that survives this run is essentially as confident as the
data allows, but the AP count drops sharply, so most genuine connections
will fail the `MIN_WIN` gate. Useful for spot-checking flagship pairs.

---

## Known gotchas

* `SPONT_END_SAMPLE = 6950` (13.9 s) is hardcoded right now because the
  protocol is still being tuned. When that finalises, update the constant
  in both `SCS_MovieSplit_v16.m` and the matching docs.
* AP-train duplicates (different fluorescence amplitudes but identical
  spike-time identity from upstream segmentation) are still not caught;
  `find_duplicate_neurons` matches identical raw traces only.
* The metadata Excel join in `consensus.attach_metadata` assumes one row
  per `fov` per plate — if you have multi-row entries the merge will
  duplicate downstream connections. Inspect the result before publishing.

---

*v16 built May 2026 — Quiver Bioscience.*
