# Quiver MAMMAL Explorer — handoff (for the next session)

Read this first if you're picking up the `ui/` web app. It's the state + how-to-run + the
non-obvious correctness rules + a prioritized backlog. The build spec is `docs/ui_spec.md`; the
user-facing run docs are `ui/README.md`; this doc is the "continue improving it" brief.

## What it is

An internal web UI (`ui/`) that exposes **every public IBM MAMMAL head** and shows **Quiver's
empirical reliability verdict next to every prediction** (✅ Reliable / ⚠️ Caution / ❌ Don't use /
➖ Low value / ✅-❌ split). The verdict overlay — citing our own `results/` writeups — is the entire
reason this exists instead of just using David Margulies' face-value UI. FastAPI backend + a single
vanilla-JS page, served same-origin. Built and verified end-to-end (all 9 capability tabs + a
History tab; 16 passing tests; every output type seen rendering in the browser).

## Run it

```bash
conda activate mammal      # /opt/anaconda3/envs/mammal (has biomed-multi-alignment + rdkit + fastapi)
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1
cd <repo root>
/opt/anaconda3/envs/mammal/bin/uvicorn ui.backend.app:app --reload
# open http://localhost:8000/   (Swagger at /docs)
```

All 7 checkpoints already live in `models/` (verify with `python ui/scripts/predownload_models.py`;
`--warm` preloads them). First call to a tab loads its ~1.8 GB checkpoint (seconds on MPS). Tests:
`pytest ui/tests -m "not slow"` (fast) or `pytest ui/tests` (loads models). There is a registered
`.claude/launch.json` so the Claude preview tooling can `preview_start` the server by name `mammal-ui`.

## Tabs & their verified readouts (THE CRUX — every prior eval broke on readout I/O)

| Tab | Checkpoint (local) | Readout | Verdict |
|---|---|---|---|
| DTI | `dti_bindingdb_pkd_peer` | `mammal_quiver.dti.predict_pkd` with **PEER norms 6.286/1.542** (module default is cold-split — pass explicitly) | ⚠️ Caution |
| PPI | `base_458m` | base model + `<BINDING_AFFINITY_CLASS>` (model card readout); normalized P(`<1>`) | ✅ Reliable\* |
| BBBP / ClinTox-tox / ClinTox-fda | `moleculenet_*` | `molnet_infer.create_sample_dict`/`get_predictions` → normalized P(`<1>`) | ⚠️ / ❌ / ➖ |
| Solubility | `protein_solubility` | `ProteinSolubilityTask` data_preprocessing → generate → process_model_output | ✅ Reliable |
| TCR | `tcr_epitope_bind` | exact tcr_epitope prompt (special entity tokens) → normalized P(`<1>`) | ✅ Reliable |
| Generation | `base_458m` | span-infill (`experiments/phase6_generation.py` logic): mask span, generate, splice | ❌ Don't use for design |
| Embeddings | `base_458m` | `mammal_quiver.embed.embed` → 768-d; cosine vs a small UniProt family panel | ✅/❌ split |

**Rules, do not break:**
- Classifiers use the **generative** readout (prompt + `<SENTINEL_ID_0>`, `model.generate`, read
  P(`<1>`) at class position 1) — NEVER the vestigial scalar head. Reference: `mammal_quiver/wdr91.py:binder_prob`.
- The backend **normalizes** every classifier to `P(<1>)/(P(<1>)+P(<0>))` (`mammal_runner._norm_p1`)
  so numbers are comparable across tabs. `prediction.score_kind` (`pkd`|`normalized_p1`|`none`) tells
  the frontend how to render.
- Standardize SMILES (`backend/_smiles.py:neutral_parent`) before DTI/BBBP/ClinTox.
- Set `USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1` before any mammal import (done at module top).
- PPI validated against the model card's calmodulin–calcineurin sanity pair → P≈0.946. If you touch
  the PPI prompt, re-check that number.

## Architecture

```
ui/backend/
  app.py            routes + same-origin frontend serving + SMILES standardization + UniProt fetch + history logging
  mammal_runner.py  Provider registry + lazy model cache + the correct readouts + run_generate/run_embed
  reliability.py    the §2 verdicts (pure data) + STRATEGIC_BANNER          ← keep wording honest
  models.py         pydantic v2 schemas (Prediction.score_kind, ProviderResult, PredictResponse)
  history.py        append-only JSONL prediction log (gitignored _history.jsonl)
  _smiles.py        neutral_parent() standardizer
ui/frontend/index.html   single-page tabbed UI (no build step); data-driven from a TABS config + a History tab
ui/tests/                pytest (fast: routing/wording/schemas/history; slow: real model loads)
ui/scripts/predownload_models.py   verify-present (+ --warm)
```

**Provider/registry (the future-proofing seam):** each task in `mammal_runner.TASKS` holds a **list**
of `Provider`s. Today that's the IBM public head. `run_task` loops all providers; the API returns
`providers[]`; the frontend renders one card per provider. So a **Quiver fine-tuned per-target head
drops in with one class + one append** — see the backlog.

## History feature (added this session)

Server-side, append-only (`backend/_history.jsonl`, gitignored; path overridable via
`MAMMAL_UI_HISTORY`). Every successful prediction logs `{id, ts, task, inputs (original), summary,
badge, provider}`. Endpoints: `GET /history?limit=&task=`, `DELETE /history`. The **History tab**
lists past predictions newest-first with badge/result/inputs/time; **Load into tab** repopulates the
original inputs in the right tab to re-run. Tests isolate the file via the env var (see `conftest.py`).

## Batch triage (added 2026-06-02 — the highest-leverage item, now done)

`POST /predict/{task}/batch` with `{"rows": [ {<single-prediction payload>}, … ]}`. Returns
`{task, reliability, requested, processed, dropped, rows[]}`; each row is
`{index, rank, inputs, standardized_smiles, prediction, providers, error}`.

**Two-phase, on purpose:**
1. **Preprocess every row OUTSIDE the inference lock** (`app._preprocess_row`): standardize SMILES,
   resolve DTI targets via UniProt with a **per-accession cache** (so 1 compound × 50 targets is 50
   fetches, but 50 compounds × 1 target is 1 fetch). A bad SMILES / unresolvable target → that row
   becomes an **error row**, never a 500.
2. **Score under ONE inference-lock hold** (`mammal_runner.run_task_batch`): loops the prepared rows,
   wraps each `provider.predict` in try/except so one model failure isolates to its row.

**Rules, do not break:**
- **Per-row validation** uses the same pydantic model as the single route (`app._REQUEST_MODEL`).
  Tasks absent from that map (generation, embeddings) are **not batchable → 404**.
- **Ranking** is best-score-first by `_rank_value` (pkd and normalized_p1 are both higher=better);
  errored rows sort last with `rank=null`.
- **No silent truncation:** over `MAX_BATCH_ROWS` (`MAMMAL_UI_MAX_BATCH`, default 256), extra rows are
  dropped and `dropped` is reported (frontend surfaces it). This is the project's "log what you drop" ethos.
- **History:** one compact summary row per batch (`provider="batch · N rows"`, `inputs={"_batch": …}`),
  not N rows. It is intentionally **not** re-runnable from History (no single input to reload).
- Frontend builds rows + a parallel `labels[]` array; it maps results back by `row.index` (ranking
  reorders rows, so never assume position). DTI batch = cross-product of compounds × targets.

## Deviations from the literal spec (all intentional, documented)

1. Frontend served at `/` (same-origin) instead of opened as `file://` → zero CORS.
2. Generation/Embeddings live at `/predict/generation|embeddings` (uniform with the others) with
   `/generate` + `/embed` aliases for spec-compliance.
3. TCR is normalized like the other classifiers (its upstream `task_infer` returns a raw score; we
   replicate its exact prompt and normalize) rather than shown raw.

## Backlog — highest-leverage improvements next

**Shipped this session (2026-06-02):** batch triage (#2), DTI cross-target ranking folded into it
(#5), clickable evidence links (#3), and DTI truncation warning (part of #6). See "Batch triage"
below. Tests: `ui/tests/test_batch.py` (13 fast + 1 slow).

1. **Quiver fine-tuned per-target heads** — the real value (`results/aws_finetune_pilot.md`). Pattern:
   subclass `Provider` (load `models/quiver_<target>/`, same `predict()` contract, set
   `provider_kind="quiver_finetuned"`), then `TASKS["dti"].providers.append(...)`. Give it its own
   reliability record (add an optional per-provider override in `mammal_runner`/`reliability`). The
   UI already renders N providers side by side — IBM vs Quiver for the same input. **Batch already
   runs every provider per row**, so an IBM-vs-Quiver column drops into the table for free.
2. ~~**Batch / CSV mode**~~ ✅ **DONE.** `POST /predict/{task}/batch` (`{"rows":[…]}`) → ranked rows,
   per-row error isolation, UniProt cache, cap+dropped reporting (no silent truncation). Frontend:
   Single/Batch toggle on bbbp/clintox_tox/clintox_fda/solubility/dti; paste-or-upload list, sortable
   table, CSV export. `mammal_runner.run_task_batch` holds the inference lock once.
3. ~~**Clickable `evidence:` paths**~~ ✅ **DONE.** `GET /doc/{path}` serves `results/`+`docs/`
   read-only (traversal-safe); `evidenceLinks()` renders the citations as links.
4. **History upgrades** — one-click "re-run" (Load + auto-Predict), filter by task/badge, text search,
   CSV/JSON export, star/annotate rows, dedupe identical inputs. (Batch runs now log one compact
   summary row each — `provider="batch · N rows"`; not yet re-runnable from History.)
5. ~~**DTI cross-target ranking mode**~~ ✅ **DONE** as the DTI batch shape (1 compound × N targets,
   framed per the verdict as the one reasonable DTI use).
6. **Result niceties** — confidence/percent bar for normalized_p1, copy-to-clipboard, show the exact
   prompt/tokens for transparency. (DTI >1250-aa truncation warning ✅ done, single + batch.)
7. **Sharing/deployment** — only if it leaves localhost: Option B clean venv (`ui/README.md`), Docker,
   basic auth. Not needed for solo internal use.

## Gotchas / ground truth

- `mammal_quiver.dti` module-level `NORM_Y_MEAN/STD` are the **cold-split** constants; DTI must pass
  the **PEER** norms (`mammal_runner.DTI_PEER_NORM_*`).
- DTI output key is `model.out.dti_bindingdb_kd` (inside `predict_pkd`); DTI uses `forward_encoder_only`
  (scalar regression), the only non-generative readout.
- One global `_INFER_LOCK` serializes generates (MPS, single user). Run uvicorn `--workers 1`.
- The base model is shared across PPI/Generation/Embeddings via `mammal_runner.get_base_model()` —
  loaded once, not three times.
- `Date.now()`/`new Date()` work fine in the browser and `datetime` in the backend — the "unavailable"
  restriction only applies to the Workflow-tool JS sandbox, not this app.
- All checkpoints are local and gitignored (`models/`); none are committed. `aws/` has the fine-tune pipeline.

## Provenance

Verdicts copied verbatim from `docs/ui_spec.md §2` (which distills Phases 0–6 / `docs/COMPLETE_UNDERSTANDING.md`).
Receipts: `results/phase1_calibration.md`, `phase2b_quiver_targets.md`, `phase4_bbbp_literature.md`,
`phase4_finetuned_report_card.md`, `phase5_summary.md`, `phase6_generation.md`,
`phase6_crossmodal_alignment.md`, `benchmark_verification.md`, `aws_finetune_pilot.md`.
