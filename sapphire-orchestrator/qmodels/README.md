# Sapphire ↔ Q-Models integration

The layer that lets the orchestrator **call any Q-Models tool**. The model code itself is vendored at
[`../../q-models/`](../../q-models/); this folder is the bridge to it.

| File | Role |
|---|---|
| `registry.json` | Every tool — 9 curated tracks + 15 underlying models — with `tier`, `status`, inputs, output `score_kind`, and how to invoke. The single source of truth. |
| `client.py` | `QModelsClient` — routes a call by tier: **local-cpu → sync** (POST the Explorer backend), **gpu-launch/endpoint/batch → async** (the launcher). Every result carries `provenance`. |
| `adapters.py` | Normalize each tool's ad-hoc output (by `score_kind`) into the dossier `validate.runs` row. |
| `launcher.py` | The unified AWS batch launcher (auto-launch a tagged `sapphire-qmodels` instance → run → retrieve → auto-teardown), with the safety/budget rails. GPU/async path. |
| `serve_local.sh` | Stand up the vendored Explorer (the local-cpu endpoint) in an **isolated venv** (never the shared `mammal` conda env), stub-by-default. |
| `catalog.json` | Legacy mock catalog (kept for the Console's catalog display). |

## Two-speed model
- **CPU tools** (`dti`, `bbbp`, `toxicity`) → synchronous, instant, $0. `client.call("dti", {...})` →
  `provenance: live-local` when the Explorer serves real joblibs, else `stub`.
- **GPU tools** (Boltz structure/selectivity, ESM, etc.) → asynchronous. `client.call(...)` returns a
  `job_id` (`provenance: gpu-async`); `client.poll(job_id)` for the result.
- **deprecated/todo** tools are addressable but return an honest `unavailable`.

## Provenance (the truth surface)
`live-local` (real CPU model) · `stub` (endpoint up, placeholder prediction) · `gpu-async` (launched job) ·
`unavailable` / `gpu-disabled` (not called). The dossier + Console show this per fact — nothing
fabricated is ever shown as real.

## Make the CPU tools live (joblibs)
The local-cpu tools serve real predictions only when `q-models/models/cns_pertarget` + `derisking_local`
joblibs exist. Regenerate them in an **isolated env** (do NOT use the shared `mammal` conda env):
the upstream `q-models/scripts/setup_new_device.sh` does this but uses conda — prefer running the
`q-models/experiments/cns_pertarget_finetune.py` etc. under `.qm-venv`, or copy joblibs from a known-good
Explorer instance. Until then, CPU tools return clearly-labeled `stub`.
