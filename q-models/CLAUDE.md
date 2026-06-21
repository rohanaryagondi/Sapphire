# CLAUDE.md — `models` branch (Quiver MAMMAL repo)

**You are the Models Claude.** This branch is dedicated to the broader
"what's the best model for each Quiver capability" work — extending the
9-track scorecard, testing the Q3 punchlist models, and shipping verified
results into the MAMMAL Explorer UI.

Two sibling branches handle the narrower lanes — **do not duplicate their
effort:**

- **`emet` branch** — EMET (BenchSci) evaluation, agentic-research-platform comparisons, Sprint Friday slide deck. If you find yourself thinking about literature-search agents, switch branches.
- **`boltz` branch** — stale. **Boltz-2 is now INTEGRATED into THIS (`models`) branch (2026-06-14, per Rohan):** `aws/boltz_runner.py`, `baselines/boltz.py`, the `results/aws_eval/boltz_*` results, and the Explorer wiring (`predict_boltz2` in `aws/explorer_inference_server.py`; Tracks DTI/structure/selectivity) all live here. `origin/boltz` stalled "blocked on Ben" (now resolved) and is BEHIND — do NOT merge it back (it would regress shared files). Co-folding work — incl. the TSC2→PKM2/PPARD deconvolution now that Ben's data landed (`aws/tsc2_deconv_panel.json`) — runs here.

The full repo is intact here. **Your code, results, and writeups go in:**
`mammal_quiver/`, `experiments/`, `baselines/`, `aws/` (non-Boltz), `results/`
(non-`boltz_*`), `docs/`, `ui/`.

---

## What this lane actually is

James asked us to **build out the table of tracks and find more models for
each Quiver capability** — so we have the best model for each specific task.
The canonical answer is in [`docs/models_tracks_scorecard.md`](docs/models_tracks_scorecard.md):
9 tracks, current best per track, and the Q3 punchlist of what to test next.

**Your job:** make that scorecard a more complete answer over time. Every
new model evaluation updates the scorecard. Every Q3 priority lands in
Explorer.

---

## Current scorecard (read [`docs/models_tracks_scorecard.md`](docs/models_tracks_scorecard.md) for full detail)

| # | Track | Current best | Receipts |
|---|---|---|---|
| 1 | Protein family clustering | MAMMAL 458M = ESM-2 650M (0.750); SaProt for GPCRs (1.000) | `results/aws_eval/*.json` |
| 2 | DTI / binder triage | Boltz-2 (Nav1.8 0.714, mTOR 1.000) | `results/aws_eval/boltz_nav_eval.md` |
| 3 | Structure-based binding | Boltz-2 (same as Track 2) | same |
| 4 | BBBP de-risking | **MolFormer-XL (0.889 vs MAMMAL 0.833)** | `results/aws_eval/molformer/` |
| 5 | Toxicity / DILI / hERG | ADMET-AI (DILI 0.83) + hERG rule | `results/compare_admet_ai.md` |
| 6 | KG / hypothesis generation | **PROTON link prediction (median 4.3% binder rank)** | `results/aws_eval/README.md` §4.1 |
| 7 | Cross-modal Sapphire bridge | **NOTHING PUBLIC WORKS** — build, don't buy | `results/phase6_crossmodal_alignment.md` |
| 8 | Generative chemistry | Morgan FP + Enamine REAL NN (skip) | — |
| 9 | Off-target / selectivity | Boltz-2 (folded into Track 2) | — |

Already tested (don't re-test): MAMMAL 458M, ESM-2 650M, ConPLex, Boltz-2,
PROTON, MolFormer-XL, PINNACLE, SaProt-650M_AF2, ADMET-AI, Morgan FP.

---

## Q3 top-3 priorities (from `docs/models_tracks_scorecard.md` §2)

### 1. **Quiver Nav1.8 fine-tune** *(the biggest open question)*
The off-the-shelf eval is done — Nav1.8 is a chance/below-chance target for
every public model except Boltz-2 (and Boltz at 0.714 is still marginal).
Datafit bimodality work (`results/datafit_summary.md`) showed data volume
is necessary but not sufficient; Nav having zero training pairs in BindingDB_Kd
means a Quiver-data fine-tune is the only remaining lever.

**Plan:**
- Source Quiver SPR / binding data on Nav1.8 (need to ask Mahdi/David).
- Fine-tune `base_458m` on Quiver binders + matched decoys.
- Eval on **scaffold-held-out split** (Murcko scaffold).
- Success criterion: AUROC ≥ 0.80 or EF5 ≥ 5× on the held-out chunk.
- Cost: ~$2 AWS on g4dn.xlarge (pilot already worked there — see
  `results/aws_finetune_pilot.md`).
- Don't expect to beat IBM on public tasks; the win is *Quiver targets where
  IBM has no head* (Nav1.8, UBE3A, mTOR-Quiver-specific, DFP/CRISPR-N).

### 2. **Ship MolFormer-XL + ADMET-AI + hERG rule + PROTON evidence panel to the Explorer**
Pure integration, no research. Highest "users see better answers tomorrow" ROI.

The Explorer is the FastAPI + single-page UI in `ui/`. Currently it surfaces
all 9 public MAMMAL heads with per-prediction reliability verdicts. Add:
- **MolFormer-XL** as the new BBB head (replaces MAMMAL BBBP as the default;
  keep MAMMAL as the "trust the no's" specificity backstop).
- **ADMET-AI DILI** for the toxicity gate (replaces ClinTox which is worse
  than chance).
- **hERG rule** (basic-N + logP + 2 aryl rings) as the cardiac filter.
- **PROTON link-prediction evidence panel** — when a user asks about a
  target/hit, surface the top-5 KG-connected drugs from PROTON's NeuroKG
  decoder, with "hypothesis shortlist (not binder predictor)" framing.

Brief: `docs/ui_handoff.md`. Spec: `docs/ui_spec.md`. Setup: `ui/SETUP_NEW_MACHINE.md`.

### 3. **Q3 model search punchlist (run in parallel where cheap)**
From `docs/models_tracks_scorecard.md` §1 punchlists:
- **ESM-C 600M** (Track 1) — direct upgrade test vs ESM-2-650M. Target ≥0.80 NN-recall. ~$0.30.
- **ProstT5** (Track 1) — cheaper SaProt alternative for GPCRs. ~$0.40.
- **Uni-Mol2** (Track 4) — only if MolFormer-XL has edge cases in Explorer integration.
- **DrugBAN / PerceiverCPI** (Track 2) — quick BindingDB-baseline check; expect Nav-blind. $0.30 each.
- **Tahoe-x1** (Track 7) — only external model that could plausibly bridge V1-T traces → compounds (Apache 2.0). $3 AWS test.
- **Chai-1** (Track 3) — non-commercial license; only as a Boltz-2 cross-check, verify with Quiver legal first.

**Don't test these (Nature Methods 2025 receipts):** scFoundation, scGPT, Geneformer, CellPLM.
**Don't test these (license traps):** ESM-3 (non-commercial), TxGemma (research-only).

---

## Where things live

- `mammal_quiver/` — package: `dti.py`, `embed.py`, `sequences.py`, `datafit.py`, `wdr91.py`.
- `experiments/` — runnable scripts; import the package via a `sys.path.insert(0, REPO)` shim.
- `baselines/` — comparison infra (`conplex.py`, `boltz.py`, `mammal_heads.py`, `common.py`).
- `aws/` — AWS launch scripts: `proton_strength_eval.py`, `molformer_eval.py`, `saprot_eval.py`, `pinnacle_eval.py`, plus matching userdata. **Boltz scripts (`boltz_runner.py`, etc.) are now integrated + owned HERE** (2026-06-14) — the `boltz`-branch lane is absorbed into this branch.
- `results/` — `.md` writeups (authoritative) + timestamped `.json` raw runs. `results/aws_eval/boltz_*` is the `boltz` branch's lane.
- `models/` — local checkpoints (base_458m, dti_bindingdb_pkd[_peer], moleculenet_bbbp, etc.). Gitignored; fetch with `bash scripts/download_models.sh`.
- `ui/` — the MAMMAL Explorer.

## Setup + run

- Env: conda `mammal`, Python 3.11 (`/opt/anaconda3/envs/mammal/bin/python`).
- Deps: `biomed-multi-alignment`, `PyTDC`; web layer in `ui/requirements.txt`. M3 Pro / MPS, ~0.4-0.8 s/pair.
- Run an experiment from repo root: `/opt/anaconda3/envs/mammal/bin/python experiments/phaseX.py`.
- **GOTCHA — `USE_TF=0`**: transformers auto-imports TensorFlow which deadlocks on macOS. The `mammal_quiver` package sets it at import; scripts set it too. Ad-hoc REPL must `export USE_TF=0 USE_FLAX=0` first.
- DTI head truncates target to 1250 aa, drug SMILES to 256 tokens. PEER checkpoint needs its own norms (6.286 / 1.542).

---

## AWS guardrails (apply on this branch too)

- **Hard budget cap: $15 per session.** Per-model evaluations are typically $0.20-$1.
- **Only touch the user's 50GB EBS** (`vol-066389517f2740f19`) **and instances you launch.** Never `aws s3 ls` other buckets. Shared Quiver account.
- **Ask before deleting** any S3 bucket, instance, or volume.
- **Label `Rohan-<Model>-*`** for cost tracking.
- **Polling cadence: 60s** on running instances + cost watch.

---

## What NOT to touch (other branches' work)

- **EMET** — `emet` branch. The verdict (demo, don't buy) is settled there.
- **The Sprint Friday slide deck** — `emet` branch (it's an EMET deck).

(Boltz-2 is no longer a separate lane — it's integrated here; see the branches note at top. Launch Boltz
from this branch when needed, on AWS GPU, under the same budget/teardown guardrails as every other model.)

---

## Strategic framing (don't lose this)

- *"State-of-the-art on shit is still shit."* Empirical grounding required. Test on real Quiver problems, not paper benchmarks.
- *"Our value is insights that point to targets others can't see; commodity tools enrich those insights."* MAMMAL and all the alternatives are tools. The moat is V1-T + functional trace data.
- **Fine-tuning insight:** off-the-shelf eval is done. Fine-tuning only beats the best available off-the-shelf on tasks IBM has no head for — i.e. Quiver-specific targets. The real fine-tune is on Quiver data, scaffold-split eval.
- Don't: feed traces into MAMMAL (no trace modality — V1-T's job, forever).
- **Verify before claiming.** This project has flipped its own conclusions 3× by fixing the I/O, not the model.

## The user

Rohan Aryagondi — Yale sophomore, Quiver research (rohan.gondi@quiverbioscience.com).
Plainspoken, technical. Push back when a request seems wrong; flag uncertainty; verify before claiming. Collaborators: Matt (MAMMAL lead), Mahdi (V1-T), David (lab), Caitlin (KG), James (asks for the deck/tracks expansion), Ben (DFP work — owned by `boltz` branch).

## Reporting

- Weekly check-ins (Matt): 6/11 Phase 2 use cases.
- Notion project page `36ee87e515f181289939ee64294ab5e8`. Append findings; for substantial artifacts create a Notes-DB row linked to the project page.

## Next actions when you start

1. Read [`docs/models_tracks_scorecard.md`](docs/models_tracks_scorecard.md) end-to-end — that's the canonical state.
2. Read `NEXT_STEPS.md` (this branch — the Models-focused version).
3. Pick a Q3 priority. If unsure, default order: Nav fine-tune > Explorer integration > Q3 model punchlist.
