# robyn_scs endpoint wiring (`tools/robyn_scs/`)

Clean, callable **endpoints** around the vendored `robyn_scs` SCS/STA neuronal-connectivity pipeline.
This package finds the *correct ways to call* the vendored analysis code — it does **not** reimplement it
and does **not** modify `vendor/`.

- **Vendored source:** `vendor/robyn_scs/` (`q-state-biosciences/Analysis@robyn_scs` `a1d5dc5`; Robyn granted
  full permission — see `vendor/robyn_scs/VENDORED.md`). The working analysis code is in
  `vendor/robyn_scs/utils/`; `SCS_Pipeline_v17.ipynb` is the reference for call order.
- **What it is:** SCS = Discrete Event Pairing over the *spontaneous* period; STA = Spike-Triggered Average
  over the *stim* period; a consensus merger unifies both into a tiered per-connection + per-neuron map.

## Runtime posture
- **Engine stays stdlib-only.** Heavy deps (`numpy`, `scipy`, `pandas`, `matplotlib`) are imported **lazily**
  inside `endpoints.py` (`_utils()` / `_viz()`) — importing the module touches no third-party package, and the
  Sapphire engine imports nothing here. `seaborn` is **not** required.
- **Wiring only (this task).** Not yet a Sapphire harness agent / `live_engine` seam — that's a follow-up once
  the call paths are proven. The full pipeline is **not run here** (it needs MATLAB-split imaging CSVs); the
  wiring is verified by import + `inspect.signature` alignment (+ one cheap synthetic `detect_events` call).
- The vendored `utils` package uses relative imports, so it is imported as the package `utils` with
  `vendor/robyn_scs` on `sys.path`; `_utils()` asserts it loaded the **vendored** package (fail-loud on clash).

## Input data layout
The MATLAB splitter `SCS_MovieSplit_v17.m` is a **manual upstream step** (imaging → CSVs; not wrapped here).
It writes, per plate, into `<plate>/v17_traces/`:
```
FOV_XXXX_<base>_spont_part1.csv   FOV_XXXX_<base>_spont_part2.csv
FOV_XXXX_<base>_stim_part1.csv    FOV_XXXX_<base>_stim_part2.csv
FOV_XXXX_<base>_stim_meta.json
```

## Endpoint catalogue
| Endpoint | Vendored call path | Inputs → output |
|---|---|---|
| `detect_events(raw, …)` | `data_utils.detect_segments` → `preprocess` → `detect_aps` | 1-D trace → `{segments, trace, aps}` |
| `run_scs(spont_p1_csv, spont_p2_csv, …)` | `scs_utils.run_scs_pipeline` ×2 → `validate_scs_in_part2` | two spont CSVs → `{res_p1, res_p2, scs_df}` |
| `run_sta(stim_p1_csv, stim_p2_csv, …)` | `sta_utils.run_sta_pipeline_interleaved` → `validate_sta_interleaved` | two stim CSVs (+stim_meta) → `{res, sta_df}` |
| `load_stim_metadata(meta_path)` | `data_utils.load_stim_meta` | `*_stim_meta.json` → dict |
| `stim_mask_from_sidecar(mat_path, meta)` | `data_utils.load_ensemble_mask_sidecar` → `stim_mask_from_mat` | `EnsembleDmdMasks.mat` + meta → `{trace_id: bool}` |
| `merge_and_classify(scs_df, sta_df, …)` | `consensus.merge_connections` → `neuron_types_from_merged` ×2 → `classify_neurons` | two per-connection tables → `{merged_connections, neuron_tiers}` |
| `visualize(kind, …)` | `visualization.plot_consensus_heatmap` / `plot_neuron_tier_bar` | artifacts (+output_path) → figure/file |
| `discover_fov_quartets(input_dir)` | (pure stdlib; mirrors the notebook) | a `v17_traces` dir → list of FOV quartet dicts |
| `run_fov(quartet, …)` | the full single-FOV chain (mirrors `run_one_fov`) | one quartet → per-FOV result dict |
| `run_batch(input_dir, output_dir, …)` | `discover_fov_quartets` → loop `run_fov` → `pd.concat` | a plate dir → plate-level frames (+CSVs) |

The optional `.mat` ensemble-mask path is exposed via `stim_mask_from_sidecar` and the `in_stim_mask_override`
parameter of `run_sta` / `run_fov`; if absent, the STA pipeline falls back to the JSON `stim_mask_sources`.
The notebook's morphological-PSP STA diagnostic is not run by default (it's a diagnostic add-on).

## Usage
```python
import sys; sys.path.insert(0, "tools/robyn_scs")   # or import tools.robyn_scs.endpoints
import endpoints as rs
quartets = rs.discover_fov_quartets(r"<plate>/v17_traces")
result   = rs.run_fov(quartets[0])           # {fov, merged_connections, neuron_tiers, ...}
plate    = rs.run_batch(r"<plate>/v17_traces", output_dir=r"<plate>/v17_outputs")
```

## Deps
`numpy`, `scipy`, `pandas`, `matplotlib` (see `requirements.txt`) — at **call time** only, in this tool's
subprocess. `pip install -r tools/robyn_scs/requirements.txt`. The engine path does not import them.
