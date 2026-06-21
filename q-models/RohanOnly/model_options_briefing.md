# Models we can try beyond MAMMAL — briefing

_Rohan's working notes. Date: 2026-06-05. Context: David M. / James asked whether there are models
better than MAMMAL for our work. This is the landscape + what's runnable + what I've actually tested._

## Bottom line

- MAMMAL is **commodity enrichment, not core infrastructure** (already established, Phases 0–6). It's a
  fine de-risking/representation layer but **not a binding oracle**, and the "shared protein↔ligand
  latent space" pitch is empirically dead off-the-shelf.
- The sharpest gap is **single-target binder triage / DTI** — where MAMMAL is ≈ chance and Quiver's need
  is highest. Two open, runnable challengers target exactly that: **ConPLex** (contrastive DTI, runs on
  the Mac, free) and **Boltz-2** (AF3-class structure + near-FEP affinity, needs a GPU).
- **New this week:** I stood up Boltz-2 on AWS and confirmed its affinity head **runs on a cheap g4dn
  T4 (15 GB)** for ~400-aa targets — propranolol→ADRB2 scored prob_binder **0.997** in ~7 min for **~$0.30**.
  So the GPU-cost worry is resolved for small/medium targets; big channels (Nav1.8, 1956 aa) still need a
  domain construct.
- The win condition to keep in mind: a challenger "beats" MAMMAL only if it gives **real triage signal on
  a Quiver target where MAMMAL has none** (e.g. Nav1.8, mTOR). Beating MAMMAL on a public benchmark
  doesn't count — "SOTA on shit is still shit."

---

## The bar: what MAMMAL does / doesn't do (the baseline to beat)

| Task | MAMMAL off-the-shelf | Usable? |
|---|---|---|
| Single-target binder vs decoy (DTI) | ≈ chance (Nav1.8 +0.00, mTOR +0.10 separation); cross-target Spearman 0.43 | **No** — only coarse cross-target re-ranking |
| Protein / gene-family embeddings | NN recall 0.92, beats size-matched ESM-2 650M (0.84) | **Yes** — clustering, KG, CRISPR-N family grouping |
| BBB penetrance | AUROC 0.97 but over-calls "crosses" (70% TNR), hard 0/1 | Soft **positive** signal only |
| Clinical toxicity (ClinTox) | memorized; 0% sensitivity to external toxics | **No** — don't gate on it |
| Structure | none | n/a |
| Cross-modal retrieval (Sapphire pitch) | protein/SMILES near-orthogonal (cos 0.08) | **Falsified** |
| Per-target fine-tune (PGK2 head) | AUROC 0.97 selectivity vs PGK1 — but only on Quiver-specific targets IBM has no head for | works, Quiver-data-only |

---

## Candidates by task (open + realistically runnable first)

### A. Drug–target binding / single-target triage — THE priority
| Model | What it is | Open / size | Runs on | Verdict |
|---|---|---|---|---|
| **ConPLex** (Singh et al., PNAS 2023) | Contrastive co-embedding of protein (ProtBert) + drug (Morgan); outputs a binding probability. Purpose-built for the decoy-resistant single-target axis MAMMAL fails. | MIT; ~12 MB head + ProtBert ~1.6 GB | **Mac CPU/MPS, free** | **Try first.** Scaffolded already (see below). |
| **Boltz-2** (Wohlwend et al. / Recursion, 2025) | AF3-class co-folding + a binding-affinity head approaching FEP accuracy. Per-pair oracle, not a fast screen. | MIT, open weights (~7–10 GB) | **g4dn T4 works** for ≤~450 aa (confirmed); big targets need a domain construct | **Try second** (GPU). ~$0.30/handful of pairs. |
| DrugBAN / DeepPurpose baselines | classic DTI GNN/encoders | open | Mac | reference baselines if we want a spread |

### B. Protein representation / embeddings (MAMMAL currently wins here)
| Model | Note | Runs on |
|---|---|---|
| **ESM-C / ESM Cambrian** (EvolutionaryScale) | ESM-2 successor, "dramatic improvements," open + commercial-OK. Re-run our 25-protein / CRISPR-N clustering test against it before trusting MAMMAL as the embedding layer. | Mac/MPS (300M/600M) |
| ESM-3 | frontier, generative; **gated / non-commercial** open variant | HPC |
| SaProt (structure-aware), Ankh (small, efficient) | strong representation alternatives | Mac/GPU |

### C. ADMET / de-risking (replace the broken ClinTox)
| Model | Note | Runs on |
|---|---|---|
| **ADMET-AI** (Swanson 2024, Chemprop-RDKit) | #1 TDC ADMET leaderboard; 41 calibrated endpoints (BBB, hERG, DILI, CYP, clearance, solubility). Drop-in replacement for MAMMAL's unusable ClinTox. | **pip, CPU-friendly** |
| Chemprop v2 (D-MPNN) | classic, trusted; small property datasets where simple GNNs beat big FMs | Mac/GPU |
| MolFormer-XL (IBM), Uni-Mol2 (3D) | SMILES / 3D-aware property models | GPU |

### D. Structure (MAMMAL has none)
- **Boltz-2 / Boltz-1, Chai-1** — open, runnable. **AlphaFold3** — gold standard but gated (no commercial
  weights; affinity ranking mixed). NeuralPLexer3 — multi-ligand co-folding.

### E. Multimodal protein↔ligand "shared space" (MAMMAL's falsified claim)
- **Nothing production-ready** claims a working shared retrieval space in 2026. **MolX** and **LigUnity**
  are 2026 preprints to watch; not released/peer-reviewed yet. If we need structure-grounded affinity,
  use Boltz-2 + ESM-C separately rather than waiting for a unifying FM.

---

## What I've actually tested (empirical, not paper claims)

- **MAMMAL** — fully (Phases 0–6 + an in-house fine-tune pilot). The baseline above.
- **Boltz-2** — **AWS pre-flight done (2026-06-04).** g4dn.xlarge (T4 15 GB), weights cached to the 50 GB
  volume. propranolol→ADRB2 (413 aa) → `affinity_probability_binary` **0.997**, ~7 min, no OOM, ~**$0.30**.
  Confirms T4 is enough for ~400-aa targets. Run was stopped early (only the pre-flight of a 5-complex set
  completed). Recipe + scripts in `aws/` (`boltz_runner.py`, `boltz_setup_run.sh`, `boltz_complexes.json`).
- **ConPLex** — **scaffolded, not yet run.** Separate conda env `conplex` (its deps conflict with `mammal`),
  checkpoint downloaded, a standalone predict driver written (bypasses its broken CLI). The ProtBert
  download was interrupted; one `boltz`-style smoke test away from first numbers.
- **Eval harness (local, not yet committed):** `baselines/` (`conplex.py`, `boltz.py`, `mammal_heads.py`,
  `common.py` with rank-only cross-model stats + bootstrap CIs) and `experiments/compare{1,2,3,4}.py` +
  `compare_all.py`. These swap any challenger into MAMMAL's exact test sets (10-pair correlation, named
  suzetrigine→Nav1.8 test, Nav1.8/mTOR triage, WDR91/PGK2) and emit one apples-to-apples scorecard.

---

## Recommended order to try (effort / cost)

1. **ConPLex on our targets** — local, free, ~1 hr. Finish the smoke test, then run `compare1–4`. This is
   the cheapest shot at the headline question (does anything beat MAMMAL on Nav1.8/mTOR triage?).
2. **Boltz-2 on a Nav1.8 / mTOR domain construct** — GPU, ~$0.30–1 on g4dn. We've proven the pipeline; the
   only new work is choosing the binding-domain construct for the big channels. Highest-value because it's
   structure-grounded affinity on the exact targets MAMMAL fails.
3. **ESM-C clustering re-test** — local, ~1 hr. Confirms whether MAMMAL should remain the embedding layer.
4. **ADMET-AI** — local, ~1 hr. Replaces the unusable ClinTox with calibrated tox/ADMET endpoints.

Items 1, 3, 4 run on the Mac for free. Item 2 is the only one that needs the (now-proven) ~$0.30 AWS path.

---

## Strategic framing (don't lose this)

- The moat stays **V1-T + functional trace data**, not any off-the-shelf model. These tools *enrich*
  insights; they are not the insight. Do **not** feed functional traces into any of them.
- A challenger earns a slot only if it does something MAMMAL can't **on our problems** — single-target
  triage where MAMMAL is chance is the clean test.
- Fine-tuning only beats IBM where IBM has no head — i.e. Quiver-specific targets, on Quiver data,
  evaluated by enrichment on a held-out scaffold split. It's chemotype triage, not a precision oracle.

## Pointers
- Full MAMMAL synthesis: `docs/COMPLETE_UNDERSTANDING.md`; competitive scan: `docs/lit/02_competitive_landscape.md`,
  `docs/analysis/q2_specialists_vs_cohesive.md`.
- Boltz AWS recipe: `aws/boltz_setup_run.sh` + `aws/boltz_runner.py` (g4dn.xlarge, DLAMI PyTorch 2.7,
  volume `vol-066389517f2740f19` at `/mnt/rohan`, `BOLTZ_CACHE` on the volume, self-terminate).
- ConPLex wrapper: `baselines/conplex.py` (+ `baselines/_conplex_predict.py`); eval harness:
  `experiments/compare_all.py`.
