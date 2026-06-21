# Quiver MAMMAL Explorer — set up & run on a new machine

The from-zero runbook to bring up the **Quiver MAMMAL Explorer** web UI (`ui/`) on a fresh
machine — including for a brand-new Claude Code session. Follow it top to bottom; every command
is copy-pasteable from the repo root.

> **If you are a Claude session picking this up:** run this runbook to get the app live, then read
> `CLAUDE.md` (orientation + gotchas), `HANDOFF.md` (the full evaluation story), and
> `docs/ui_handoff.md` (the UI's "continue improving it" brief — the **verified readouts are the
> crux**; every prior eval broke on readout I/O). This file is the *runbook*; those are the *why*.

---

## What you're setting up

A single-page web app (FastAPI backend + vanilla-JS frontend, no build step) that exposes **every
public IBM MAMMAL head** and shows **Quiver's empirical reliability verdict next to every
prediction** — citing our own `results/` writeups. The verdict overlay is the whole reason it
exists (David Margulies' MAMMAL UI shows each head at face value; this one tells you whether to
trust it). It also has **batch triage** (rank many compounds — Quiver's real workflow), **clickable
evidence** links, a **DTI truncation warning**, and a persistent **History** tab.

## Prerequisites

- **Python 3.11** (conda strongly recommended — that's how the env was built).
- **~20 GB free disk** (~17 GB model weights + the conda env).
- **Network access** to `huggingface.co` (one-time model download) and `rest.uniprot.org`
  (DTI fetches a target sequence by accession at request time).
- macOS (Apple-silicon → MPS), Linux (CUDA or CPU), or any CPU box. **No GPU is required** — CPU is
  just slower (~seconds/prediction). The code auto-picks `mps` → `cuda` → `cpu`.

---

## 1. Get the repo (everything is on `main`)

Fresh machine:

```bash
git clone https://github.com/rohanaryagondi/Q-Models.git
cd Q-Mammal
```

Already have a clone (e.g. the other laptop)? Just update `main`:

```bash
cd Q-Mammal
git checkout main && git pull origin main
```

> The **whole project** — the UI, the experiments, the docs, and the AWS fine-tune pipeline — is on
> `main`. (The `ui-mammal-explorer` branch still exists on the remote as a backup/revert point; you
> don't need to check it out.) `models/` is **not** in git (see step 3).

## 2. Environment + dependencies

```bash
conda create -n mammal python=3.11 -y
conda activate mammal
pip install -r requirements.txt        # MAMMAL + torch + rdkit (via PyTDC) — large, takes a while
pip install -r ui/requirements.txt     # the web layer: fastapi / uvicorn / pydantic / httpx / pytest
```

**CRITICAL env vars — set these in your shell before anything else:**

```bash
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1
```

`USE_TF=0`/`USE_FLAX=0` stop `transformers` from auto-importing TensorFlow, which **deadlocks on
macOS** (`[mutex.cc:452] RAW: Lock blocking`). The code sets these at import as a backstop, but set
them in your shell too. `HF_HUB_DISABLE_XET=1` avoids a flaky downloader path.

## 3. Models (~17 GB in `./models/`, gitignored) — CHECK what you already have FIRST

Weights are never in git. **This machine may already have some or all of them** (from earlier work),
so check before downloading anything:

```bash
python ui/scripts/predownload_models.py     # ✓/✗ per checkpoint (the 7 the UI needs)
```

- **All ✓** → skip to step 4, you're done here.
- **Some ✗** → fetch *only what's missing*. `scripts/download_models.sh` lists each HF repo's files and
  `curl`s them with resume, **skipping any file you already have**, so it's safe to run against a
  partial `models/`:

```bash
# the 7 the UI needs:
bash scripts/download_models.sh base_458m dti_bindingdb_pkd_peer moleculenet_bbbp \
     moleculenet_clintox_tox moleculenet_clintox_fda protein_solubility tcr_epitope_bind

# …or ALL 10 — adds wdr91_asms + pgk2_del_cdd (the per-target binder heads the offline fine-tune
# experiments use). Get these too if you're continuing the full project, not just running the UI:
bash scripts/download_models.sh
```

Re-run `python ui/scripts/predownload_models.py` until every UI checkpoint is ✓. (It checks the 7 UI
heads; `wdr91_asms`/`pgk2_del_cdd` are only needed by `experiments/`.) `models/` is gitignored —
weights are always fetched here, never cloned.

## 4. Run

```bash
export USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1   # if not already set this shell
uvicorn ui.backend.app:app --reload --workers 1
```

Open **http://localhost:8000/** (Swagger at `/docs`). Each tab lazy-loads its ~1.8 GB checkpoint on
first use (seconds on MPS/CPU). **Use `--workers 1`**: MPS models aren't fork-safe and each worker
would reload every checkpoint; one inference lock serializes requests (fine for a single user).

Optional: preload everything once to remove first-request latency:

```bash
python ui/scripts/predownload_models.py --warm
```

## 5. Verify it works

```bash
pytest ui/tests -m "not slow"     # fast: routing, reliability wording, batch envelope, /doc security
pytest ui/tests                   # everything, incl. real predictions (loads checkpoints; slower)
```

In the browser:
- **BBB Penetrance** tab → **Load example** → **Predict** → caffeine comes back penetrant (~100%).
- Same tab, flip to **Batch triage** → **Load example** → **Rank** → a ranked table of 5 compounds,
  with **Download CSV**.
- **Drug–Target Binding** tab → **Batch triage** → **Load example** → **Rank** → suzetrigine ranked
  across Nav1.8 / Nav1.1, both flagged **"target … aa — truncated to 1250"**.
- Click any **`evidence:`** link under a verdict → the actual `results/`/`docs/` writeup opens.

---

## What's in it (capabilities × Quiver's verdict)

| Tab | Head | Quiver verdict |
|---|---|---|
| Drug–Target Binding (DTI) | `dti_bindingdb_pkd_peer` | ⚠️ Caution — coarse cross-target ranking only |
| Protein–Protein Interaction | base + `<BINDING_AFFINITY_CLASS>` | ✅ Reliable\* (light internal check) |
| BBB Penetrance | `moleculenet_bbbp` | ⚠️ Caution — soft positive only |
| Clinical Toxicity | `moleculenet_clintox_tox` | ❌ Don't use — memorization |
| FDA Approval | `moleculenet_clintox_fda` | ➖ Low value — trivial task |
| Protein Solubility | `protein_solubility` | ✅ Reliable — ~at baseline |
| TCR–Epitope Binding | `tcr_epitope_bind` | ✅ Reliable — low Quiver relevance |
| Generation | base (span-infill) | ❌ Don't use for design — demo only |
| Embeddings | base (mean-pool) | ✅/❌ split — family clustering YES, cross-modal NO |

Verdicts are verbatim from `docs/ui_spec.md §2` (which distills Phases 0–6). The reliability overlay
ships on **every** `/predict` response — keeping it honest is the product.

## API (Swagger at `/docs`)

- `GET /health` · `GET /reliability[/{task}]` · `GET /examples/{task}`
- `POST /predict/{dti,ppi,bbbp,clintox_tox,clintox_fda,solubility,tcr}` — one prediction + verdict
- `POST /predict/{task}/batch` — `{"rows":[…]}` → ranked rows + per-row errors + dropped count
- `POST /predict/generation`, `POST /predict/embeddings` (aliases `/generate`, `/embed`)
- `GET /doc/{path}` — read-only `results/`/`docs/` writeup (the evidence links; path-traversal-safe)
- `GET /history?limit=&task=` · `DELETE /history`

## Configuration knobs (env vars)

- `USE_TF=0 USE_FLAX=0 HF_HUB_DISABLE_XET=1` — **required** (see step 2).
- `MAMMAL_UI_HISTORY` — prediction-history JSONL path (default `ui/backend/_history.jsonl`, gitignored).
- `MAMMAL_UI_MAX_BATCH` — max rows scored per batch before extras are dropped + reported (default `256`).

## Troubleshooting (these cost real time — see `HANDOFF.md §6`)

- **Import hangs at `RAW: Lock blocking`** → you didn't set `USE_TF=0 USE_FLAX=0`.
- **Download stalls / resume fails** → use `scripts/download_models.sh` (curl `-C -` + retry), not
  `huggingface-cli download`; keep `HF_HUB_DISABLE_XET=1`.
- **DTI numbers look wrong** → it must use the **PEER** checkpoint with norms 6.286 / 1.542. The UI
  does this for you (`mammal_runner.DTI_PEER_NORM_*`); don't swap in the cold-split head.
- **A BBBP/ClinTox score is a hard 0 or 1** → expected. These MoleculeNet heads emit saturated
  labels, not calibrated probabilities — the verdict overlay says so. Don't threshold-tune them.
- **DTI on a big target** → if the protein is > 1250 aa the head only sees the first 1250; the UI
  warns you (this is exactly why suzetrigine→Nav1.8 fails). Treat the score with extra caution.
- **Missing checkpoint** → `python ui/scripts/predownload_models.py` names which; re-download it.
- **Slow / odd concurrency** → run `--workers 1`; a single lock serializes generates (single user).

## Where the rest of the knowledge lives

- `CLAUDE.md` — terse orientation for an AI agent (state, gotchas, conventions, the people).
- `HANDOFF.md` — the single entry point for the whole evaluation (Phases 0–6 + the AWS fine-tune
  pilot), the one-paragraph verdict, the repo map, and the consolidated gotchas.
- `docs/COMPLETE_UNDERSTANDING.md` — master synthesis (read first for the full picture).
- `docs/ui_handoff.md` — the UI's verified readouts (the crux), the Provider/registry seam for
  dropping in **Quiver fine-tuned heads** (the real future value), the batch-triage internals, and
  the prioritized backlog.
- `docs/ui_spec.md` — the build spec + §2 reliability verdicts (verbatim source of the overlay).
- `ui/README.md` — the user-facing UI doc (tabs, API, architecture, the Quiver-head seam).
