# Set up the Quiver **Q-Models** repo on a NEW device — from zero

**Start here if you are a Claude (or human) bringing this project up on a fresh machine.**
This is the canonical runbook for **Q-Models** (`github.com/rohanaryagondi/Q-Models`) — the
consolidated "best model per Quiver capability" work + the Boltz-2 evaluation lane, the live
Explorer with per-target fine-tunes, and the AWS continuation. **Everything is on `main`.**

> This repo merges what used to be scattered across the `models` and `boltz` branches of the old
> Q-Mammal repo into one clean `main`. `docs/models_tracks_scorecard.md` is the headline deliverable;
> the Boltz-2 work lives under `results/aws_eval/boltz*` + `docs/boltz_handoff/` + `RohanOnly/boltz/`.

---

## 0. TL;DR (the fast path)

```bash
# clone to a NORMAL local path — do NOT clone into a OneDrive/Dropbox/iCloud synced folder (see §5)
git clone https://github.com/rohanaryagondi/Q-Models.git ~/q-models
cd ~/q-models          # everything is on the default branch `main`
bash scripts/setup_new_device.sh          # env + deps + REGENERATE live models + smoke test
# then start the live Explorer:
EXPLORER_LOCAL_MODELS=1 USE_TF=0 USE_FLAX=0 \
  python -m uvicorn ui.explorer.backend.app:app --host 127.0.0.1 --port 8000
# -> http://localhost:8000   (DTI / BBBP / Tox serve LIVE; no GPU, no 17 GB weights)
```

That's the whole live app. Everything below is the detail + the AWS continuation.

---

## 1. What you're standing up

- **The Capability Explorer** (`ui/explorer/`, FastAPI + vanilla-JS, no build step): one card per
  Quiver capability ("track"), each showing the **best model + Quiver's empirical reliability
  verdict**, a **Launch Hub** (queue many inputs across tracks, CSV drag-drop, run all), a
  **Results** page, and per-track queue/results panels.
- **Live local fine-tunes**: the DTI, BBBP, and Tox tracks return **real predictions in-process**
  (CPU Morgan-FP + GradientBoosting models) when `EXPLORER_LOCAL_MODELS=1`. Other tracks are
  best-model-documented + AWS-served (GPU) or informational.
- The canonical "what's the best model per track" answer: **`docs/models_tracks_scorecard.md`**.

## 2. Prerequisites

- **Python 3.11** (conda recommended — that's how the env was built).
- **Network**: `huggingface.co` (only for the optional MAMMAL weights), ChEMBL
  (`ebi.ac.uk/chembl`), PubChem (`pubchem.ncbi.nlm.nih.gov`), `rest.uniprot.org`, and PyTDC
  datasets — the fine-tune regeneration pulls these.
- **No GPU needed** for the live Explorer / fine-tunes (CPU only). GPU/AWS is only for the
  heavier tracks (Boltz-2 structure, ESM-2 clustering) and new model evals.
- **~2 GB disk** for env + regenerated models. (The 17 GB MAMMAL weights are **optional** —
  only for MAMMAL-head experiments.)

## 3. The one non-obvious step: regenerate the live models

`models/` is **gitignored**, so the per-target fine-tunes do **not** come with the clone — they
are **regenerated locally** from public data (this is also how we keep them current). The setup
script runs all three trainers:

| Script | Produces | Source | Time |
|---|---|---|---|
| `experiments/cns_pertarget_finetune.py` | `models/cns_pertarget/*.joblib` (~16 CNS targets, 0.95–0.997) | ChEMBL + GtoPdb | ~15–30 min |
| `experiments/pubchem_qhts_finetune.py` | `models/cns_pertarget/{KCNQ2,CACNA1H}.joblib` (0.79–0.81) | PubChem qHTS | ~5 min |
| `experiments/derisking_local_train.py` | `models/derisking_local/*.joblib` (BBBP 0.90 / hERG 0.88 / DILI 0.93) | TDC | ~3 min |

ChEMBL is intermittently flaky; the pullers **cache to `data/cns_dti_cache` + retry**, so if a
target is missing just **re-run the script** (or `scripts/setup_new_device.sh`) — cached pulls
are instant and only the gaps refetch. The Explorer loads whatever joblibs exist (no restart
needed for new ones). See `results/cns_pertarget_finetune_characterization.md` +
`results/derisking_local_characterization.md` for what "good" looks like.

## 4. Run + verify

```bash
EXPLORER_LOCAL_MODELS=1 USE_TF=0 USE_FLAX=0 \
  python -m uvicorn ui.explorer.backend.app:app --host 127.0.0.1 --port 8000
```
- `curl -s localhost:8000/api/meta | python -c 'import sys,json;print(json.load(sys.stdin)["live_tracks"])'`
  → should print `['dti', 'bbbp', 'toxicity']`.
- DTI sanity (in-domain): POST `/api/predict/dti` `{"smiles":"<haloperidol>","uniprot_acc":"P14416"}`
  → `stubbed:false`, P≈1.0. Suzetrigine→Nav1.8 (Q9Y5Y9) correctly scores low/low-confidence (novel
  scaffold, out-of-domain) — that's the honest applicability-domain gate, not a bug.
- `pytest ui/explorer/tests -q` → 19 pass (live models are gated off in tests).

## 5. git + sync-folder gotcha (READ if cloning near a cloud-sync folder)

On the original machine the repo lived under **OneDrive**, and OneDrive's file-on-demand driver
stalled every `git push`/`gc` with `mmap failed: Operation timed out`. **On a new device, just
clone to a plain local path** (e.g. `~/q-mammal`) and you avoid this entirely.

If you must keep the working tree inside a synced folder, keep `.git` OUT of it:
```bash
# move .git to local disk, symlink it back (what we did on the original machine):
mv <repo>/.git ~/.local-gitstore/<name>.git
ln -s ~/.local-gitstore/<name>.git <repo>/.git
git config http.postBuffer 524288000 && git config http.version HTTP/1.1
```
Commits always live safely on GitHub (`origin/main`).

## 6. AWS continuation (for new model evals + GPU tracks)

You will be given AWS credentials separately. **Configure them locally only — never commit keys.**
```bash
aws configure        # paste the provided access key / secret; region us-east-1
```
The launch pattern + guardrails are in **`CLAUDE.md`** (read its "AWS guardrails" section) and the
`aws/*_eval.py` + `aws/*_userdata.sh` scripts are working templates. Operational config (NOT
secrets):

- **Region** `us-east-1`. **AMI** `ami-012ba162b9cd2729c` (Deep Learning OSS Nvidia DLAMI),
  **subnet** `subnet-93dd2ccb` (us-east-1b), **SG** `sg-1b4dee62`, typical instance `g5.xlarge`.
- **S3 staging bucket** `s3://rohan-mammal-bootstrap-20260610-213029/` (per-job prefix). Only touch
  this bucket + instances you launch — it's a **shared Quiver account**; never inspect others'
  buckets/instances.
- **Every instance**: `--instance-initiated-shutdown-behavior terminate` + a watchdog, 100 GB gp3
  root, tags `Owner=RohanAryaGondi` / `Project=mammal-explorer`. Creds go via `aws configure get`
  sed'd into `/tmp/*_ud.sh` then `shred -u` — **never bake keys into committed userdata**.
- **Budget**: hard cap (was \$55) — per-model evals are \$0.20–\$1.50. Poll running instances every
  ~60 s; **always tear down** (verify zero live `Owner=RohanAryaGondi` instances when done).
- The campaign's launch/teardown recipe + every gotcha is in the AWS-related memory notes and the
  committed `aws/` scripts — reuse them, don't reinvent.

## 7. Orientation — read in this order

1. **`CLAUDE.md`** — branch mission, what NOT to duplicate (emet/boltz lanes), AWS guardrails, the user.
2. **`docs/models_tracks_scorecard.md`** — the canonical best-model-per-track answer (the deliverable for James).
3. **`docs/overnight_summary_2026-06-15.md`** — the latest campaign synthesis (what was tested, the fine-tunes, build-vs-buy).
4. **`docs/cns_finetune_readiness.md`** — which targets are fine-tunable today vs need Quiver data.
5. `results/*_characterization.md` — the per-model receipts (read the ones relevant to your task).
6. **`NEXT_STEPS.md`** — the Models-focused backlog. Default priority order is in `CLAUDE.md` §"Next actions".

## 8. The one thing only Rohan/Quiver can unblock

Everything is validated on **public** scaffold-splits, **not** on Quiver's own measured binders.
The single highest-value next step is a **Quiver held-out panel** (SMILES + measured activity on a
live target) to compute true Quiver-substrate AUROCs — and Quiver screening data for the data-poor
channels (Nav1.1/Dravet, Nav1.6) that have no public data. That's the moat; it's the ask.
