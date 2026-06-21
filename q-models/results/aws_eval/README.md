# AWS evaluation results — PROTON + Boltz-2

Two models that needed AWS GPU access were run on 2026-06-07/08 across multiple
launch attempts (the launch infrastructure took 7 iterations to get right — see
"AWS infrastructure post-mortem" at the bottom; the **scientific results** are
fully retrievable and reproducible).

- Hardware: AWS g5.xlarge (A10G 24 GB, NVIDIA driver 580, CUDA 13.0)
- Boltz version: 2.2.1
- Models: PROTON via `mims-harvard/PROTON` repo (HEAD as of 2026-06-07)
- Raw artefacts: [`proton_results.json`](proton_results.json),
  [`boltz_v7_results.json`](boltz_v7_results.json),
  [`boltz_per_complex_affinity_dump.txt`](boltz_per_complex_affinity_dump.txt)

---

## 1. PROTON — full success

**Setup.** Embed the 40-gene CRISPR-N panel (same as
[`compare_esm2_650m.md`](../compare_esm2_650m.md)) using PROTON's pretrained
NeuroKG embeddings (147,020 × 512 tensor). Look up each panel gene by HGNC
symbol in `nodes.csv` (column `node_name`, filtered to `node_type == "gene/protein"`),
extract its embedding row, compute NN-recall + family-separation gap +
kNN k=3 accuracy. Same protocol as the prior MAMMAL / ESM-2-650M head-to-head.

**Gene resolution: 39/40** — only `IKBKA` missed (likely synonym mismatch: true
IKKα is the HGNC-canonical symbol `CHUK`; `IKBKA` is a deprecated alias).
Panel-by-family resolution: kinase 11, gpcr 8, ion_channel 8, nuclear_receptor 6,
e3_ligase 4, lipid_kinase 1, phosphatase 1.

**Numbers** (reproducible — confirmed across 3 independent v4/v5/v7 runs;
v7 numbers include a deterministic kNN tie-break vs v4/v5's hash-dependent one):

| Model | License | NN-recall | family gap | kNN-3 acc |
|---|---|---:|---:|---:|
| MAMMAL 458M | IBM (research) | **0.750** | 0.374 | — |
| ESM-2 650M (raw cosine) | MIT (open) | 0.725 | 0.039 | — |
| ESM-2 650M (centered) | MIT (open) | **0.750** | 0.417 | — |
| **PROTON (raw)** | MIT + Harvard Dataverse | **0.487** | 0.106 | 0.462 |
| **PROTON (centered)** | MIT + Harvard Dataverse | **0.487** | 0.315 | 0.538 |

**Per-family PROTON NN-recall (centered):**

| family | recall | n |
|---|---:|---:|
| e3_ligase | 0.75 | 4 |
| ion_channel | 0.625 | 8 |
| kinase | 0.545 | 11 |
| nuclear_receptor | 0.50 | 6 |
| gpcr | 0.25 | 8 |
| lipid_kinase | 0.0 | 1 (singleton — by construction can never match a same-family NN) |
| phosphatase | 0.0 | 1 (singleton — same) |

**Verdict.** **PROTON loses to MAMMAL and ESM-2-650M on family clustering.** NN-recall
of 0.487 is ~35 % below sequence-only models (0.750). PROTON's embeddings reflect
the KG link-prediction objective (gene ↔ disease, gene ↔ drug, gene ↔ cell type), not
protein-family structure — which is what NN-recall on this panel measures. The
per-family breakdown is informative: GPCRs cluster particularly poorly under PROTON
(0.25 recall), kinases moderately, e3_ligases best — likely reflecting how
heavily-studied each family is in the KG's drug-target literature rather than any
property of the proteins themselves.

**Strategic implication.** PROTON does NOT replace MAMMAL or ESM-2 as the embedding
layer for Sapphire's protein representation problem. Its strengths are elsewhere
(drug repurposing, hypothesis generation on KG-resident relations) and were not
tested here — that would be a different eval, not directly comparable to the
NN-recall numbers in this writeup.

---

## 2. Boltz-2 — partial (2/5 complexes succeeded)

> **UPDATE 2026-06-08 — the Nav1.8 (+ mTOR + selectivity) tests below are now DONE.**
> Re-run on the Yale **Bouchet** cluster (not AWS). Split result: **mTOR AUROC = 1.000**
> (decisive — 3 rapalogs all above 4 decoys, p=0.029; MAMMAL failed mTOR at 0.56) but
> **Nav1.8 AUROC = 0.714** — first off-the-shelf model above chance on Nav1.8 (vs MAMMAL 0.43 /
> ConPLex 0.39) yet **marginal** (n=28, p=0.16, 95% CI [0.40,1.0]). Selectivity (Test C) is weak:
> Nav1.8 ranked #1 for suzetrigine but by a tiny margin, low off-target Δ. Boltz-2 is strong on
> well-precedented targets (mTOR) and better-than-prior on Nav, but not yet a confident Nav triage
> oracle. **Off-target control (UBE3A/TUBB): target-aware but soft** — every Nav binder scores higher
> on Nav1.8 than on the unrelated proteins (decoys flat; clear step up from MAMMAL's compressed pKd),
> but margins are modest and A-803467 leaks (~0.46 on off-targets). **Test E reproduces 0.71–0.75**
> across Nav1.7/1.5/1.8. Positive control (CA2/CDK2) staged but not yet run (queue-blocked). Full
> analysis + corrected install recipe: **[`boltz_nav_eval.md`](boltz_nav_eval.md)**.
> (The "kernel-ops fix" suggested below is itself wrong — see correction #1 in that writeup.)

**Setup.** 5 protein-ligand complexes from `aws/boltz_complexes.json`:

| name | target | drug | label |
|---|---|---|---|
| ADRB2_propranolol | ADRB2 (β2-adrenergic receptor) | propranolol | known binder |
| DRD2_haloperidol | DRD2 (D2 dopamine receptor) | haloperidol | known binder |
| DRD2_risperidone | DRD2 | risperidone | known binder |
| DRD2_metformin | DRD2 | metformin | decoy |
| ADRB2_caffeine | ADRB2 | caffeine | decoy |

Each scored via Boltz-2's affinity head (`affinity_probability_binary` ∈ [0,1] +
`affinity_pred_value` = predicted log₁₀(IC₅₀ µM)). Reduced sampling
(`--sampling_steps 100 --diffusion_samples 1`) to stay under the $2 budget cap.

**Results — 2 of 5 succeeded:**

| name | rc | prob_binder | log_ic50 (predicted log10 IC50 µM) | elapsed | source |
|---|---:|---:|---:|---:|---|
| ADRB2 / propranolol (known binder) | 0 | **0.997** | −2.95 | 4.9 s | v4 |
| DRD2 / haloperidol (known binder) | 0 | **0.988** | −2.98 | 4.9 s | v4 |
| DRD2 / risperidone (known binder) | 1 | — | — | 56 s | v4 (`cuequivariance_torch` missing) |
| DRD2 / metformin (decoy) | 1 | — | — | 42 s | v4 (same) |
| ADRB2 / caffeine (decoy) | 1 | — | — | 41 s | v4 (same) |

**For the 2 successful complexes**, the multi-sample affinity output (3 diffusion
samples per pair, preserved on the volume for DRD2/haloperidol):

```json
{
  "affinity_probability_binary":   0.988,  // main
  "affinity_probability_binary_1": 1.000,
  "affinity_probability_binary_2": 0.976,
  "affinity_pred_value":   -2.98,          // main log10(IC50 µM)
  "affinity_pred_value_1": -3.30,
  "affinity_pred_value_2": -2.67
}
```

Both real predictions. Propranolol IS a known ADRB2 β-blocker (K_d ~10 nM range);
haloperidol IS a known DRD2 D2 antagonist (K_i ~1 nM range). Predicted prob_binder
≈ 0.99 for both is qualitatively correct — Boltz-2 affinity is working on the pairs
it could run.

**Why 3/5 failed.** Boltz 2.2.1's `triangular_mult` layer unconditionally calls
`kernel_triangular_mult`, which imports `cuequivariance_torch.primitives.triangle.triangle_multiplicative_update`,
which itself imports from **`cuequivariance_ops_torch`** — a *separate* CUDA-kernel
package (`cuequivariance-ops-cu13-torch` on pip for CUDA 13). v4 had neither package
installed; v7 had `cuequivariance-torch` 0.10.0 installed but not the `*-ops-*`
sibling. The 2 successful v4 complexes happened to skip this code path (smaller
template-attention pair size); the 3 failed ones triggered it. On the next AWS run,
the one-line fix is `pip install cuequivariance-ops-cu13-torch` alongside
`cuequivariance-torch`.

**What this means for the Quiver comparison.** With only 2 binders and 0 decoys
that completed, we **cannot compute binder-vs-decoy AUROC**. What we DO have:
**Boltz-2 returns prob_binder ≈ 0.99 for known potent binders on β2-adrenergic
and D2 dopamine receptors** (the targets are 413–443 aa, well within Boltz's
trained range, and both drugs are well-represented in the literature Boltz was
trained on). That's a working-on-easy-pairs signal, not the Nav/mTOR triage test
we actually want. Boltz-2 on Nav1.8 / mTOR remains the open question.

**Strategic implication.** Boltz-2 has a non-trivial AWS install footprint
(weights ~10 GB; needs CUDA-13 kernel ops package; A10G or better). On easy
β-blocker / D2-antagonist pairs it produces sensible probabilities. The actual
Quiver-relevant test (Nav-family binder-vs-decoy AUROC) is **not** done — it would
require (a) the kernel-ops fix in the install + (b) Nav1.8/mTOR sequences + Nav
blockers + matched decoys in the complexes JSON + a re-run on AWS.

---

## 3. AWS infrastructure post-mortem (~$1.07, 7 launches)

For posterity, since this took longer than the science. Each launch hit a different
silent-failure mode (every fix exposed the next layer):

| Run | Time | Cost | Failure mode | Fix |
|---|---:|---:|---|---|
| v1 | 8 m | $0.13 | `python3 -m venv` failed (`ensurepip` not on DL AMI) | switched to `pip install --user` |
| v2 | 8 m | $0.13 | `sudo -u ubuntu` without `-H` kept `HOME=/root`; pip installed to `/root/.local/bin`, ubuntu user couldn't see boltz binary | `sudo -H -u ubuntu bash -lc` |
| v3 | 2.5 m | $0.04 | `lsblk \| grep '^nvme1n1'` matched the g5.xlarge's local 250 GB instance store, not the 50 GB EBS volume | detect EBS by SIZE (`lsblk -bdn -o NAME,SIZE`) |
| v4 | 25 m | $0.42 | **PROTON: full success.** Boltz: 2/5 complexes succeeded; 3 failed with `ModuleNotFoundError: cuequivariance_torch` | (this is the run that produced the actual data above) |
| v5 | 13.5 m | $0.23 | PROTON re-confirmed. Boltz install completed but `pip show boltz \| head -3` triggered SIGPIPE + `set -eo pipefail` → script exited before any Boltz complex ran | replaced `\| head` with `\| sed -n '1,5p'` (sed reads its whole input) |
| v7 | 8.5 m | $0.14 | All 6 structural bug classes from subagent review fixed (no SIGPIPE, no mount issue, no race conditions, no `if ! \| tee` rc-loss). Boltz hit a NEW failure: `cuequivariance-torch` 0.10.0 installs but Boltz needs `cuequivariance-ops-torch` (separate package with the actual CUDA kernels). | One-line `pip install cuequivariance-ops-cu13-torch` for a v8 if run again |
| readers × 6 | — | $0.01 | (volume retrieval) | |

**Meta-finding** (3-subagent code review of the userdata after v5 surfaced this):
every silent failure in v1-v5 was the same bug class — `cmd 2>&1 | tee log | tail -N`
under `set -eo pipefail`. `tail` closes its stdin after N lines → SIGPIPE → cmd
exits with rc 141 → pipefail propagates → set -e kills script BEFORE the
`if [ status != 0 ]` branch could run. The v7 userdata refactor eliminated this
entire class: `cmd > log 2>&1; rc=$?` (no pipe), `tail` only AFTER, `if !` outer
wrapper uses process substitution (`> >(tee log) 2>&1; rc=$?`) so the `tee` rc
doesn't mask the inner script's rc.

The lesson: **never pipe into `head` or `tail` under `set -eo pipefail`**. Doesn't
matter how careful you are with the explicit `${PIPESTATUS[0]}` branch — that
branch is dead code, `set -e` already left the building.

---

## Files in this directory

- [`boltz_nav_eval.md`](boltz_nav_eval.md) — **the Nav1.8 binder-vs-decoy result (AUROC 0.714)** + selectivity/mTOR/full-panel confirmation, run on Bouchet 2026-06-08, with the corrected Boltz-2 install recipe
- [`boltz_nav1.8_results.json`](boltz_nav1.8_results.json) — raw Test B output (11 Nav1.8 complexes, prob_binder + log_ic50 per complex, infra metadata)
- [`boltz_mtor_results.json`](boltz_mtor_results.json) — raw Test D output (mTOR × 3 rapalogs + 4 decoys; AUROC 1.000)
- [`boltz_suzetrigine_selectivity_results.json`](boltz_suzetrigine_selectivity_results.json) — raw Test C output (suzetrigine × 9 Nav paralogs)
- [`boltz_navfull_partial_results.json`](boltz_navfull_partial_results.json) — Test E partial (36/99; Nav1.7/1.5/1.8 panels complete → per-paralog AUROC 0.71–0.75)
- [`boltz_offtarget_vixotrigine_results.json`](boltz_offtarget_vixotrigine_results.json) — off-target control (Nav drugs × UBE3A + TUBB) + vixotrigine × Nav (2/9)
- [`proton_results.json`](proton_results.json) — full PROTON eval output (39/40 panel, raw + centered metrics, per-gene NN detail, per-family recall)
- [`boltz_v7_results.json`](boltz_v7_results.json) — v7's single-complex attempt (infrastructure metadata + the 1 failed complex's diagnostic record)
- [`boltz_per_complex_affinity_dump.txt`](boltz_per_complex_affinity_dump.txt) — raw `affinity_*.json` content from the v4 success (DRD2/haloperidol multi-sample affinity)
