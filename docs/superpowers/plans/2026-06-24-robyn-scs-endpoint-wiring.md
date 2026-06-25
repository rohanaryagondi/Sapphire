# Task brief — robyn_scs endpoint wiring

*Owner: **hayes**. Tier: **Standard**. Created 2026-06-24 by Head Claude.*

## Context
`robyn_scs` (Robyn's SCS/STA neuronal-connectivity pipeline) is now **vendored** into Sapphire at
`vendor/robyn_scs/` (verbatim snapshot of `q-state-biosciences/Analysis@robyn_scs` `a1d5dc5`; Robyn gave full
permission — see `vendor/robyn_scs/VENDORED.md`). The analysis code in `vendor/robyn_scs/utils/` **already
works** ("the stuff in the middle works"). Your job is to **wire up the endpoints** — find the correct ways to
CALL this code — so the rest of the Quiver stack (Sapphire/LOKA orchestrator) can invoke it.

## Goal / Definition of Done
A new **`tools/robyn_scs/`** package that exposes the pipeline's operations as clean, correctly-wired callable
endpoints **around the vendored code, without modifying the vendored code and without running the full pipeline**
(it needs MATLAB-split imaging CSVs we don't have here — so verify by IMPORT + signature, not by execution).

Deliver:
1. **`tools/robyn_scs/endpoints.py`** — one well-documented function per operation below. Each:
   - imports the real implementation from `vendor.robyn_scs.utils.*` (set up the import path cleanly; the vendored
     `utils` uses intra-package imports, so import it as a package — do NOT copy/retype its logic),
   - has the **correct signature** mapping to the underlying function(s) (params + return), passing arguments
     through correctly,
   - has a docstring stating inputs (file paths / dicts / arrays), outputs, and which vendored function(s) it calls
     (`file:line` of the target). **Thin wrappers only — no reimplementation, no edits to `vendor/`.**
2. The **endpoints** (from the verified callable map):
   - `detect_events(csv_path, …)` → preprocess + AP-detect (`data_utils.detect_segments` / `preprocess` /
     `detect_aps`).
   - `run_scs(spont_p1_csv, spont_p2_csv, …)` → `scs_utils.run_scs_pipeline` ×2 + `validate_scs_in_part2`.
   - `run_sta(stim_p1_csv, stim_p2_csv, stim_meta, …)` → `sta_utils.run_sta_pipeline_interleaved` +
     `validate_sta_interleaved`.
   - `merge_and_classify(scs_df, sta_df, …)` → `consensus.merge_connections` + `classify_neurons`.
   - `visualize(result, output_path, …)` → the relevant `visualization.plot_*` (pick the headline ones:
     `plot_consensus_heatmap`, `plot_neuron_tier_bar`).
   - `run_fov(quartet, …)` → the full single-FOV chain (steps above in order), mirroring the notebook's
     `run_one_fov` (see `vendor/robyn_scs/SCS_Pipeline_v17.ipynb`).
   - `run_batch(input_dir, output_dir, …)` → discover FOV quartets → loop `run_fov` → concat plate-level CSVs.
   - (The MATLAB splitter is a manual upstream step — document it, don't wrap it.)
3. **`tools/robyn_scs/README.md`** — the endpoint catalogue: each endpoint, its inputs/outputs, the vendored
   call path, the expected input data layout (`<plate>/v17_traces/FOV_*_{spont,stim}_part{1,2}.csv` +
   `*_stim_meta.json`), and the deps it needs at call time.
4. A **smoke/wiring test** `sapphire-orchestrator/tests/test_robyn_scs_endpoints.py` (or under `tools/`) that
   verifies, **without running the pipeline**: the module imports; each endpoint exists and is callable; and each
   endpoint's parameters line up with the vendored target's signature (use `inspect.signature`). Optionally call
   an endpoint with tiny synthetic in-memory arrays for the ones that don't require MATLAB CSVs (e.g.,
   `detect_events` on a short numpy trace) IF it runs cheaply offline — but do NOT require real imaging data.

## Constraints (hard)
- **Do NOT modify anything under `vendor/robyn_scs/`** — it's the canonical original. Wiring lives only in
  `tools/robyn_scs/`.
- **Do NOT run the full pipeline / do not require MATLAB or real imaging data.** Verification is import + signature
  alignment (+ optional cheap synthetic call). "Don't try to run it."
- **Engine stays stdlib-only.** `robyn_scs` pulls heavy deps (numpy/scipy/pandas/matplotlib/seaborn). Keep them
  OUT of the Sapphire engine import path — `tools/robyn_scs/` imports them, the engine does not. Record the deps in
  `tools/robyn_scs/README.md` (and a `requirements.txt` there if useful). Do NOT add them to the engine.
- This task is **wiring only** — NOT a Sapphire harness agent / live_engine seam yet (that's a follow-up once the
  call paths are proven). Don't touch `live_engine.py`, `harness/`, or contracts.

## Gates before PR (dev/GATES.md)
1. Full suite green (`bash dev/run-tests.sh`) including your new wiring test.
2. Independent review (Head Claude). 3. Provenance + no secrets/binaries. 4. Stdlib-runtime (engine clean) +
verbatim-vendor (you didn't touch `vendor/`). 5. Functional verification = the wiring test passes + Head Claude
confirms the endpoints actually resolve to the right vendored functions with matching signatures.

## Notes
- The vendored `utils` package is imported as a package — figure out the cleanest import (e.g., add
  `vendor/robyn_scs` to `sys.path` inside `tools/robyn_scs/endpoints.py`, or import via
  `vendor.robyn_scs.utils...`). Pick one, document it, keep it contained to `tools/robyn_scs/`.
- Reference, don't re-derive: the call order + signatures are in `vendor/robyn_scs/SCS_Pipeline_v17.ipynb` and
  `vendor/robyn_scs/README_v16.md`. The 8-endpoint map is in `vendor/robyn_scs/VENDORED.md`.
- If a call path is genuinely unclear (e.g., the MATLAB `.mat` ensemble-mask branch), wire the clear ones and
  raise the unclear one in `dev/HELP.md` rather than guessing.
