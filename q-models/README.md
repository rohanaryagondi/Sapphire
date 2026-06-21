# MAMMAL exploration (Quiver Bioscience)

Evaluating IBM's MAMMAL biomedical foundation model
([Shoshan et al., *npj Drug Discovery*, May 2026](https://doi.org/10.1038/s44386-026-00047-4))
for Quiver's drug-discovery and CNS work. Spun up out of the 5/28/2026 sprint
meeting: is the model useful enough to be a workflow component, vs occasional
enrichment, vs the latent-space layer of Sapphire? The bar is empirical results
on Quiver-relevant problems, not paper benchmarks.

- Model card: `ibm/biomed.omics.bl.sm.ma-ted-458m` (HuggingFace), 458M params
- Upstream code: https://github.com/BiomedSciAI/biomed-multi-alignment

## Current state (Phases 0–6 done + an in-house fine-tune pilot)

**Read [`docs/COMPLETE_UNDERSTANDING.md`](docs/COMPLETE_UNDERSTANDING.md) for the full synthesis.**
Verdict: MAMMAL is **commodity enrichment, not core infrastructure** for Quiver.

- **DTI / single-target binding** — SOTA-but-weak. PEER checkpoint reaches Spearman 0.43 on 10 known
  pairs but single-target binder-vs-decoy triage ≈ chance; the named suzetrigine(=Jernabix)→Nav1.8 test
  **fails**. Soft cross-target re-ranking only.
- **De-risking heads** — BBBP AUROC 0.968 but a false-positive bias (soft *positive* signal, not a
  rule-out gate); **ClinTox unusable** (memorization, 0% external-toxic sensitivity).
- **Similarity expansion** — Morgan fingerprints beat MAMMAL embeddings (0.96 vs 0.72). Use fingerprints.
- **Cross-modal alignment = NO** (Phase 6) — protein & SMILES embeddings near-orthogonal; the "MAMMAL =
  Sapphire's shared latent space" pitch is **falsified off-the-shelf**. Protein/gene-family embeddings
  *are* useful (beat size-matched ESM-2 650M, 0.92 vs 0.84) — just not as a binding-retrieval space.
- **Generation** — public weights span-infill only; no de-novo molecule design.
- **Per-target fine-tuning works** — PGK2 head separates its hits from the PGK1 homolog at AUROC 0.97
  (in-distribution chemotype triage). And we **piloted the fine-tune pipeline ourselves on AWS** (~$0.80,
  BBBP val acc 0.88): it works. **But** fine-tuning only beats the best-available MAMMAL on **Quiver-
  specific targets** (where off-the-shelf ≈ 0.5), not on public tasks IBM already has a head for.

Full detail: [`docs/COMPLETE_UNDERSTANDING.md`](docs/COMPLETE_UNDERSTANDING.md),
[`results/aws_finetune_pilot.md`](results/aws_finetune_pilot.md), and the `results/` + `docs/` indexes.

## Layout

```
mammal_quiver/        importable package — inference wrappers
  __init__.py           sets USE_TF=0 / USE_FLAX=0 (see gotcha below)
  dti.py                load DTI checkpoint, predict_pkd(target_seq, drug_smiles)
  embed.py              base-model compound/protein embeddings (masked mean-pool)
  sequences.py          UniProt fetch + pinned reference SMILES/targets
experiments/          runnable phased evaluation scripts (phase0 / phase1* / phase1b* / phase2a*)
docs/                 planning docs (meeting context, plan, success criteria, open questions) + index
results/              experiment outputs (*.md writeups + timestamped *.json) + index
data/                 bindingdb_kd.tab (TDC BindingDB_Kd export)
models/               ~9 GB local checkpoints — NOT in git (see .gitignore), fetch separately
```

## Setup

Dedicated env (we use conda `mammal`, Python 3.11 at `/opt/anaconda3/envs/mammal/`):

```bash
pip install -r requirements.txt   # biomed-multi-alignment + PyTDC (rdkit comes via PyTDC)
pip install -e .                  # optional: install the mammal_quiver package
```

**Critical macOS gotcha — `USE_TF=0`.** `transformers` auto-imports the installed
TensorFlow, which deadlocks at import on macOS (`[mutex.cc:452] RAW: Lock blocking`).
MAMMAL inference is pure PyTorch, so TF is never needed. Importing the `mammal_quiver`
package sets `USE_TF=0` and `USE_FLAX=0` for you; the experiment scripts also set it
explicitly. **An ad-hoc Python REPL must `export USE_TF=0 USE_FLAX=0` before importing
transformers/mammal.**

**Model weights.** The DTI / BBBP / ClinTox checkpoints live as local copies under
`models/` (`base_458m`, `dti_bindingdb_pkd`, `dti_bindingdb_pkd_peer`, `moleculenet_bbbp`,
`moleculenet_clintox_tox`). The wrappers prefer the local copy and fall back to the HF hub
id. Weights are not committed (the HF downloader's resume is broken on this network; they
were fetched via curl). Hardware: M3 Pro, MPS; load ~10 s, inference ~0.4–0.8 s/pair.

## Reproduce the phases

Run from the repo root with the env's Python:

```bash
PY=/opt/anaconda3/envs/mammal/bin/python

# Phase 0 — instantiation smoke test (model loads, encodes, predicts)
$PY experiments/phase0_smoke_test.py

# Phase 1 — DTI calibration
$PY experiments/phase1_calibration.py          # named test + negative controls (cold-split)
$PY experiments/phase1_correlation.py          # 10 known pairs, cold-split checkpoint
$PY experiments/phase1_peer_comparison.py      # same pairs, PEER checkpoint (the fix)
$PY experiments/phase1_indistribution_check.py # BindingDB_Kd in-distribution control
$PY experiments/phase1_nrmse_verify.py         # reproduce paper NRMSE

# Phase 1b — de-risking property heads (proper held-out scaffold split)
$PY experiments/phase1b_molnet_eval.py bbbp    # BBBP AUROC
$PY experiments/phase1b_molnet_eval.py tox     # ClinTox-tox AUROC
$PY experiments/phase1b_bbbp_check.py          # quick hand-set (flawed; see writeup)

# Phase 2a — hit-expansion similarity check
$PY experiments/phase2a_similarity_check.py
```

`phase1b_molnet_eval.py` reads `/tmp/BBBP.csv` and `/tmp/clintox.csv` (MoleculeNet CSVs).

## Where to read next

- Strategy / what was decided: [`docs/`](docs/) ([index](docs/README.md))
- Findings: [`results/`](results/) ([index](results/README.md))
- Project status / decisions (source of truth):
  [Notion project page](https://www.notion.so/36ee87e515f181289939ee64294ab5e8)
