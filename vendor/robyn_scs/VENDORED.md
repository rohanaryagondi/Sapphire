# Vendored: robyn_scs (SCS / STA neuronal-connectivity pipeline)

**Upstream:** `q-state-biosciences/Analysis` — branch `robyn_scs`, commit `a1d5dc5` ("DLX detection fixes").
**Vendored:** 2026-06-24. **Permission:** Robyn granted full permission to pull the code into Sapphire and use it as-is.

## What this is
The SCS (Single-Cell Spikes) v16/v17 pipeline — a merged dual-method neuronal-connectivity analysis for
FireflyOne voltage-imaging data:
- **SCS** (spontaneous period): Discrete Event Pairing — detects EPSPs/IPSPs and pairs them to presynaptic APs.
- **STA** (stim period): Spike-Triggered Average — waveform averaging from stimulus-driven responses.
- **Consensus merger**: unifies both into a tiered per-connection + per-neuron classification.

The callable code lives in `utils/` (`data_utils`, `scs_utils`, `sta_utils`, `consensus`, `visualization`,
`quiver_style`). The notebooks (`SCS_Pipeline_v17.ipynb`, …) are the reference for call order. `SCS_MovieSplit_v17.m`
is the MATLAB splitter (a manual upstream step: imaging → CSVs + `stim_meta.json`; not called from Python).

## Rules (this is a verbatim snapshot — treat as read-only)
- **Do NOT modify anything under `vendor/robyn_scs/`.** It is the canonical original (CONVENTIONS §4), like
  `vendor/design-form-agent/` and the vendored Q-Models. Endpoint-wiring/integration code lives ELSEWHERE
  (`tools/robyn_scs/`) and calls *into* this package.
- **Use as-is.** "The stuff in the middle works" — the task is to find the correct ways to CALL this code, not
  to change it or run the full pipeline (which needs MATLAB-split imaging CSVs we don't have here).

## Deliberate exclusion
- `quiver-viz.skill` (a binary ZIP, ~8.7 KB) was **excluded** — Gate 3 blocks committed binaries, and it is a
  matplotlib-styling *generator*, not pipeline code. Its product, `utils/quiver_style.py`, IS vendored, so the
  Quiver plotting style still applies via `import utils.quiver_style`. To refresh the skill, pull it from upstream.

## How to refresh
Re-clone `q-state-biosciences/Analysis@robyn_scs` and `rsync` `robyn_scs/` here (excluding `quiver-viz.skill`,
`.git`, `__pycache__`, `.ipynb_checkpoints`), then update the commit hash above.

## Callable surface (entry points the wiring targets)
See `tools/robyn_scs/` (the endpoint-wiring) and the brief
`docs/superpowers/plans/2026-06-24-robyn-scs-endpoint-wiring.md`. The 8 natural operations:
1. MATLAB splitter (`SCS_MovieSplit_v17.m`) — manual, upstream of Python.
2. preprocess + AP-detect — `data_utils.preprocess`, `data_utils.detect_segments`, `data_utils.detect_aps`.
3. SCS spontaneous — `scs_utils.run_scs_pipeline` (×2 P1/P2) → `scs_utils.validate_scs_in_part2`.
4. STA stim — `sta_utils.run_sta_pipeline_interleaved` → `sta_utils.validate_sta_interleaved`.
5. merge + classify — `consensus.merge_connections`, `consensus.classify_neurons`.
6. visualization — `visualization.plot_*` (output_path=…).
7. batch over FOVs — discover quartets → loop steps 3–6 → concat plate-level CSVs.
8. styling — `import utils.quiver_style`.
