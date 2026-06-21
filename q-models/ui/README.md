# Quiver MAMMAL Explorer

An internal web UI that exposes every **public** IBM MAMMAL capability **and shows Quiver's
empirical reliability verdict next to every prediction**. David Margulies' MAMMAL UI presents
each capability at face value; we've run the experiments (Phases 0–6), so this tool lets the
model predict *and* tells you whether to trust it — citing our own `results/` writeups. That
overlay is the whole reason this exists.

> **Strategic context (shown as a banner in-app):** MAMMAL is commodity enrichment, not a binding
> oracle. The capabilities Quiver will actually win on are per-target binder heads fine-tuned on
> Quiver data — not yet in this UI. See `results/aws_finetune_pilot.md`.

## Tabs (all public heads + base capabilities)

| Tab | Head | Readout | Quiver verdict |
|---|---|---|---|
| Drug–Target Binding (DTI) | `dti_bindingdb_pkd_peer` | scalar pKd (PEER norms) | ⚠️ Caution — coarse cross-target ranking only |
| Protein–Protein Interaction | base + `<BINDING_AFFINITY_CLASS>` | generative P(`<1>`) | ✅ Reliable\* (light internal check) |
| BBB Penetrance | `moleculenet_bbbp` | generative P(`<1>`) | ⚠️ Caution — soft positive only |
| Clinical Toxicity | `moleculenet_clintox_tox` | generative P(`<1>`) | ❌ Don't use — memorization |
| FDA Approval | `moleculenet_clintox_fda` | generative P(`<1>`) | ➖ Low value — trivial task |
| Protein Solubility | `protein_solubility` | generative P(`<1>`) | ✅ Reliable — ~at baseline |
| TCR–Epitope Binding | `tcr_epitope_bind` | generative P(`<1>`) | ✅ Reliable — low Quiver relevance |
| Generation | base (span-infill) | `model.generate` | ❌ Don't use for design — demo only |
| Embeddings | base (mean-pool) | 768-d + nearest family | ✅/❌ split — family clustering YES, cross-modal NO |

The reliability verdicts are the table in `docs/ui_spec.md §2`, kept verbatim in
`backend/reliability.py` and returned on **every** `/predict` response.

A **History** tab logs every prediction server-side (`backend/_history.jsonl`, gitignored) so
past searches survive restarts and a fresh session can see them. Each row shows the verdict badge,
task, inputs, result, and time; **Load into tab** re-populates the original inputs to re-run.

### Batch triage (the real Quiver use)

Quiver's actual workflow is ranking *many* compounds (DEL/DFP screens), not one at a time — so
the SMILES tabs (BBBP, ClinTox-tox, FDA), Solubility, and DTI now have a **Batch triage** mode
(toggle at the top of the tab):

- **SMILES / sequence tabs** — paste one entry per line (or upload a `.csv`/`.txt`; first column is
  the entity, an optional second column is a display name) → a ranked, sortable table.
- **DTI cross-target** — one compound × a panel of UniProt targets (the *one* DTI use the verdict
  calls reasonable: rank a compound across targets, not absolute single-target triage). Many-vs-many
  also works (cross-product).

Each row is standardized + scored independently; a bad row becomes an error row instead of killing
the batch; rows over the cap (`MAMMAL_UI_MAX_BATCH`, default 256) are dropped and the count is shown
(never silently truncated). Sort by rank/score/name, and **Download CSV**. The reliability verdict
shows once above the table — it travels with the whole batch. API: `POST /predict/{task}/batch`
with `{"rows": [ {<payload>}, … ]}`.

### Clickable evidence + truncation honesty

- The `evidence:` citations under every verdict are now **links** — the backend serves the actual
  `results/`/`docs/` writeup read-only at `GET /doc/{path}` (path-traversal-safe; only those two dirs).
- DTI predictions on a target **longer than 1250 aa** now carry a visible truncation warning
  (`prediction.extra.target_truncated`) — the mechanical reason the named suzetrigine→Nav1.8 test
  fails (Nav1.8 is ~1956 aa; the binding region is past the window).

## Setup (Option A — reuse the existing conda env)

```bash
conda activate mammal        # /opt/anaconda3/envs/mammal — already has biomed-multi-alignment + rdkit
pip install fastapi uvicorn pydantic python-dotenv httpx pytest
```

Always set these (the code also sets them at import as a backstop):

```bash
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1
```

All seven checkpoints already exist locally under `models/` (each ~1.8 GB). Verify / warm:

```bash
python ui/scripts/predownload_models.py          # confirm presence
python ui/scripts/predownload_models.py --warm    # load every model into memory once
```

## Run

From the repo root:

```bash
/opt/anaconda3/envs/mammal/bin/uvicorn ui.backend.app:app --reload
```

Then open **http://localhost:8000/** (Swagger at `/docs`). The frontend is served same-origin from
`/`, so there is no CORS setup — do **not** open `frontend/index.html` as a `file://` page.

Models lazy-load per task on first request (seconds on MPS/CPU; the first call to a tab loads its
checkpoint). Run with `--workers 1` (default): MPS models aren't fork-safe and each worker would
re-load every checkpoint. Requests are serialized by a single inference lock — fine for an internal
single-user tool.

## API

- `GET /health` — status + task list + device
- `GET /reliability` — strategic banner + all verdicts
- `GET /reliability/{task}` — one verdict
- `GET /examples/{task}` — Load-example prefill
- `POST /predict/{dti,ppi,bbbp,clintox_tox,clintox_fda,solubility,tcr}` — predict + reliability
- `POST /predict/{task}/batch` — `{"rows":[…]}` → ranked rows + per-row errors + dropped count
- `POST /predict/generation`, `POST /predict/embeddings` (aliases `/generate`, `/embed`)
- `GET /doc/{path}` — read-only `results/`/`docs/` writeup (the evidence links)
- `GET /history?limit=&task=` — past predictions (newest first); `DELETE /history` — clear

Every `/predict/*` response is `{ task, prediction, reliability, providers[] }`. `prediction.score_kind`
tells the client how to read `value`: `pkd` (regression), `normalized_p1` (calibrated P(`<1>`)/(P(`<1>`)+P(`<0>`)),
shown as a %), or `none` (generation text / embedding vector).

## Readout correctness (this is how every prior eval broke — don't change without care)

- **Classifier heads use the GENERATIVE readout**, never the vestigial scalar head: prompt + `<SENTINEL_ID_0>`,
  `model.generate`, read P(`<1>`) at class position 1. Mirrors `mammal_quiver/wdr91.py:binder_prob`. The
  backend normalizes to `P(<1>)/(P(<1>)+P(<0>))` for comparable numbers across tabs.
- **DTI** uses the **PEER** checkpoint with norms **mean 6.286 / std 1.542** (passed explicitly — the
  `mammal_quiver.dti` module defaults are the cold-split constants). Protein truncated to 1250 aa, SMILES to 256 tokens.
- **SMILES are standardized** (neutralize charges, strip salts to neutral parent) before DTI/BBBP/ClinTox.
- **PPI** runs on the base model via `<BINDING_AFFINITY_CLASS>` (no dedicated checkpoint). Validated against
  the base model card's calmodulin–calcineurin sanity pair (P≈0.95).

## Architecture & the Quiver-head seam

```
ui/backend/
  app.py            FastAPI routes + same-origin frontend serving
  mammal_runner.py  Provider registry + lazy load/cache + the correct readouts
  reliability.py    the §2 verdicts (pure data) + strategic banner
  models.py         pydantic v2 request/response schemas
  _smiles.py        neutral_parent() SMILES standardizer
ui/frontend/index.html   single-page tabbed UI (no build step)
ui/tests/                pytest smoke tests (fast + slow)
ui/scripts/              predownload_models.py
```

Each task in `mammal_runner.TASKS` holds a **list of providers**. Today that's the IBM public head.
A Quiver fine-tuned per-target head (the real value — see `results/aws_finetune_pilot.md`) drops in
beside it with no rebuild:

```python
class DtiQuiverNav18Provider(Provider): ...        # loads models/quiver_nav18/, same predict() contract
TASKS["dti"].providers.append(DtiQuiverNav18Provider())
```

`run_task` already loops over N providers, the API already returns `providers[]`, and the frontend
already renders one card per provider — so the IBM and Quiver predictions show side by side.

## Tests

```bash
pytest ui/tests -m "not slow"     # fast: routing, reliability wording, schemas (no model load)
pytest ui/tests                   # everything, incl. real predictions (loads checkpoints)
```

## Out of scope (now)

- **No Quiver fine-tuned heads yet** — public IBM heads only; the seam above is ready for them.
- **No production hardening** — internal localhost tool (no auth/Docker/nginx).
- **Batch is per-task, single-provider-ranked** — when a Quiver head lands, batch already runs every
  provider per row; ranking is by `providers[0]`.
