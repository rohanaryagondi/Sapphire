# Report — robyn_scs endpoint wiring

**Built-By:** hayes · **Branch:** `hayes/robyn-scs-endpoints` · **Task:** `robyn-scs-endpoint-wiring` ·
**Tier:** Standard · **Date:** 2026-06-24 · **Vendored source:** `vendor/robyn_scs/` (q-state-biosciences/Analysis@robyn_scs `a1d5dc5`; Robyn gave full permission).

## What this delivers
A new **`tools/robyn_scs/`** package exposing the vendored SCS/STA neuronal-connectivity pipeline as clean,
correctly-wired **callable endpoints** — *around* `vendor/robyn_scs/utils/`, **without modifying `vendor/`** and
**without running the full pipeline** (it needs MATLAB-split imaging CSVs we don't have here, so the wiring is
verified by import + `inspect.signature` alignment, plus one cheap synthetic call).

`endpoints.py` — 10 endpoints, each a thin wrapper that imports the real vendored function(s) and forwards
arguments; docstrings name the exact vendored call path:

| Endpoint | Vendored call path |
|---|---|
| `detect_events(raw, …)` | `data_utils.detect_segments` → `preprocess` → `detect_aps` |
| `run_scs(spont_p1_csv, spont_p2_csv, …)` | `scs_utils.run_scs_pipeline` ×2 → `validate_scs_in_part2` |
| `run_sta(stim_p1_csv, stim_p2_csv, …)` | `sta_utils.run_sta_pipeline_interleaved` → `validate_sta_interleaved` |
| `load_stim_metadata(meta_path)` | `data_utils.load_stim_meta` |
| `stim_mask_from_sidecar(mat_path, meta)` | `data_utils.load_ensemble_mask_sidecar` → `stim_mask_from_mat` |
| `merge_and_classify(scs_df, sta_df, …)` | `consensus.merge_connections` → `neuron_types_from_merged` ×2 → `classify_neurons` |
| `visualize(kind, …)` | `visualization.plot_consensus_heatmap` / `plot_neuron_tier_bar` |
| `discover_fov_quartets(input_dir)` | pure stdlib; mirrors the notebook |
| `run_fov(quartet, …)` | the full single-FOV chain (mirrors `run_one_fov`) |
| `run_batch(input_dir, output_dir, …)` | `discover_fov_quartets` → loop `run_fov` → `pd.concat` |

## Files
| File | Change |
|---|---|
| `tools/robyn_scs/endpoints.py` | **new** — the 10 endpoints; lazy heavy imports; package-path setup + fail-loud `utils`-clash guard. |
| `tools/robyn_scs/{__init__.py, README.md, requirements.txt}` | **new** — package marker; endpoint catalogue + data layout + deps; `numpy/scipy/pandas/matplotlib` (call-time, tool subprocess). |
| `sapphire-orchestrator/tests/test_robyn_scs_endpoints.py` | **new** — 15 wiring tests. |

## The things that matter here
- **Correct wiring, verified against the REAL signatures.** I probed every target's `inspect.signature` from the
  vendored code; every kwarg each endpoint forwards is an actual parameter of its target (no TypeError-on-call).
  Call order + branch logic mirror `run_one_fov` / `discover_fov_quartets` in `SCS_Pipeline_v17.ipynb` (the
  canonical duplicate-trace exclusion shared by both branches — the CP-2 guard, via `_canonical_excludes`; the
  `all_traces` union; the skip-when-CSVs-absent branches; the `in_stim_mask` fallback; the per-FOV try/except).
- **Thin wrappers, `vendor/` untouched.** No vendored logic reimplemented; `git status vendor/` is clean.
- **Engine stays stdlib-only.** `endpoints.py` imports only stdlib at module load; `numpy/scipy/pandas/matplotlib`
  are imported **lazily** inside `_utils()`/`_viz()` (this tool's subprocess). Proven by a test that blocks all heavy
  deps via `sys.meta_path` and still imports the module. The engine (`live_engine.py`) imports nothing here.
- **`utils` name-clash guard.** The vendored package is generically named `utils`; `_utils()` asserts it loaded the
  package from under `vendor/robyn_scs/` and raises loudly otherwise.
- **`seaborn`/`sklearn` are NOT needed** — the vendored code references seaborn only in a `quiver_style.py`
  docstring; nothing imports it. `requirements.txt` lists only the four deps actually used.
- **The `.mat` ensemble-mask branch is wired, not guessed** — `stim_mask_from_sidecar` wraps the (clearly-defined)
  `load_ensemble_mask_sidecar` + `stim_mask_from_mat`; it feeds the optional `in_stim_mask_override` of
  `run_sta`/`run_fov`, which otherwise falls back to the JSON `stim_mask_sources` (exactly as the notebook does).

## Gate evidence (run locally on `hayes/robyn-scs-endpoints`)
- **Gate 1 — full suite GREEN: 478 tests** (`bash dev/run-tests.sh`; +15 robyn_scs in the `tests` suite).
- **Gate 2 — independent review: APPROVE-WITH-MINORS.** The reviewer cross-checked every endpoint's forwarded
  args against the real vendored signatures (0 bad kwargs), confirmed all docstring `file:line` citations exact and
  `vendor/` untouched. Findings addressed: **MAJOR** — added `_canonical_excludes` (the cross-method duplicate
  exclusion / CP-2 guard) and threaded `exclude_neurons` into both branches of `run_fov` (now matches
  `run_one_fov`); **MINOR** — pinned the SCS validation threshold to the vendored `SCORE_THRESH` constant
  (decoupled from discovery) + exposed `scs_val_score_thresh`; **MINOR** — strengthened the test to catch a bogus
  forwarded kwarg (`test_run_scs/sta_forwards_clean_kwargs`). The visualize-signature + apd50 notes needed no change.
- **Gate 3 — provenance/secrets/binaries:** clean — only new `.py`/`.md`/`.txt`, no binaries, no secrets (scanned).
- **Gate 4 — stdlib-only runtime + verbatim vendor:** module import is stdlib-only (deps-blocked subprocess test
  passes); engine has zero refs to the tool; `vendor/` untouched (`git status` clean).
- **Gate 5 — functional verification: WORKS-AS-CLAIMED** (independent verifier). All 7 claims verified by
  execution, incl. adversarial AST + `inspect.Signature.bind` on all 19 vendored call sites (zero bad kwargs; the
  result-dict key contract checked too), the deps-blocked import, the fail-loud `utils`-clash guard, the synthetic
  `detect_events` chain (recovered all 3 events), discovery, and `vendor/` untouched.

## Notes / scope
- **Wiring only** (per the brief) — NOT a Sapphire harness agent / `live_engine` seam yet; that's a follow-up once
  the call paths are proven. The MATLAB splitter (`SCS_MovieSplit_v17.m`) is a manual upstream step, documented not
  wrapped. The full pipeline is not run here (no MATLAB / real imaging CSVs) — verified by import + signature
  alignment + the synthetic `detect_events` call, exactly as the brief specifies.
- The notebook's morphological-PSP STA diagnostic is a diagnostic add-on, not run by default in `run_fov`.
