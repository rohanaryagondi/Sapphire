# Q-Models — vendored into Sapphire

This directory is the **full Q-Models codebase, vendored** into the Sapphire repo on **2026-06-21**.
It is now the **canonical, modifiable home** — the standalone GitHub repo
(`github.com/rohanaryagondi/Q-Models`) is **abandoned** and will not be used again. Edit here.

## Provenance
- Source: `github.com/rohanaryagondi/Q-Models` (shallow clone, `main`), copied wholesale minus `.git/`.
- Vendored by the overnight Q-Models-integration run (see
  `../specs/2026-06-21-qmodels-integration-overnight-plan.md`).

## What this is
The model launchpad for Quiver CNS drug discovery — evaluation scripts, AWS launch userdata, baselines,
benchmarks, the Explorer inference server/UI, and results. The Sapphire orchestrator calls these tools
through the integration layer in [`../sapphire-orchestrator/qmodels/`](../sapphire-orchestrator/qmodels/)
(registry + client + launcher + adapters) — see that folder's README.

## Kept vs. excluded
- **Kept:** all code (`aws/`, `baselines/`, `benchmarks/`, `mammal_quiver/`, `scripts/`, `ui/`),
  docs, and the small **curated** test sets under `data/wdr91`, `data/pgk2`, `data/ben_tsc2`
  (force-committed; hard to regenerate), plus the committed `results/` eval artifacts (~11 MB).
- **Excluded** (via this dir's own `.gitignore`, carried over from upstream — regenerable or sensitive):
  model weights (`models/`, ~17 GB), PyTDC/BindingDB/solubility caches, `aws/*.pem` /
  `aws/.launch_vars` / `aws/userdata.sh`, and `results/*_run.log` (may contain userdata traces).
- **Secret scan at vendor time:** clean. The only regex hits were a credentials *placeholder* in
  `docs/AWS_INFRASTRUCTURE.md` ("aws_secret_access_key = ...") and protein-sequence fragments in
  `results/big_panel.json` / `results/_uniprot_cache.json` (e.g. `AKIARPKKRAETIRFSQHAV` — all valid
  amino acids). No real AWS keys or private keys were committed.

## AWS note
Upstream scripts assume the shared Quiver production account. Sapphire's launcher
(`../sapphire-orchestrator/qmodels/launcher.py`) re-implements invocation with hard safety rails
(profile `Rohan-Sapphire`, create-only + ledgered teardown, budget cap, `sapphire-qmodels-*`
namespacing) — **prefer the launcher over the raw `aws/*_userdata.sh` scripts for any new run.**
