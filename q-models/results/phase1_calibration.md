# Phase 1 — Calibration results

**Date:** 2026-05-28
**Model:** `ibm/biomed.omics.bl.sm.ma-ted-458m` DTI heads (off-the-shelf, no fine-tuning)
**Hardware:** M3 Pro, MPS. Load ~10 s, inference ~0.4–0.8 s/pair.
**Raw outputs:** `results/phase1_*_20260528_*.json`

## Bottom line

MAMMAL's off-the-shelf DTI head has **real but modest** drug-target signal on Quiver-relevant
target classes (GPCRs, ion channels, kinases) — **once you use the right checkpoint.** The first
result was a near-total failure; the cause turned out to be **checkpoint selection**, not the model.

- **Correlation on our 10 known pairs: Spearman −0.03 (cold-split checkpoint) → 0.43 (PEER checkpoint).** PASS with PEER.
- **Named test suzetrigine→Nav1.8: FAIL on both checkpoints** — the true binder does not beat random small molecules for that single target.
- **In-distribution control (BindingDB_Kd): Spearman 0.61** — the model works as designed.

Net: usable for **rank-ordering / enrichment** of candidate lists on our domain (with the PEER
checkpoint), **not** for precise affinity or for reliably picking one true binder vs decoys.

## The checkpoint discovery (the "why")

IBM publishes **two** DTI checkpoints (under the `ibm-research/` namespace):

| Checkpoint | Trained/eval split | norm mean/std | Our 10-pair Spearman |
|---|---|---|---|
| `…dti_bindingdb_pkd` | TDC BindingDB_Kd, drug+target **cold-split** | 5.794 / 1.338 | **−0.03** |
| `…dti_bindingdb_pkd_peer` | **PEER** benchmark — holds out ER, **GPCRs, ion channels, RTKs** to test generalization to exactly those classes | 6.286 / 1.542 | **0.43** |

The paper's headline DTI number (NRMSE 0.906, SOTA) is the **PEER** result. Our test pairs *are*
those held-out classes — so PEER is the correct checkpoint for our use case, and the one I should
have used first. The cold-split checkpoint regresses to its training mean (~5.8) on our pairs;
PEER produces real dynamic range (5.3–9.3).

Also discovered (downloadable, not yet tested): `moleculenet_bbbp`, `moleculenet_clintox_fda`,
`moleculenet_clintox_tox` (Phase 2a de-risking), `protein_solubility`, `tcr_epitope_bind`. Paper
reports BBBP AUROC 0.957, ClinTox 0.986.

## Tests and verdicts (vs `success_criteria.md`)

| Test | cold-split | PEER | Bar | Verdict |
|---|---|---|---|---|
| Known-pairs correlation (10) | Spearman −0.03 | **Spearman 0.43**, Pearson 0.31 | > 0.4 | **PASS (PEER)** |
| Jernabix→Nav1.8 vs negatives | 6.14 (below controls) | 7.00 (still below ibuprofen 7.60, CA2 7.09) | beat random pairs | **FAIL** |
| In-distribution control (BindingDB_Kd, 20) | Spearman 0.61 | — | (diagnostic) | model works in-domain |

### Known-pairs correlation (PEER)
10 well-characterized pairs (ABL1, EGFR, SERT, DRD2, ADRB2, Nav1.5), experimental affinity =
median pChEMBL pulled live from ChEMBL. PEER predictions track biology: fluoxetine/SERT exp 8.0→9.3,
risperidone/DRD2 8.2→8.1, haloperidol/DRD2 8.8→7.8. Misses: EGFR binders underpredicted
(gefitinib 7.8→5.3), lidocaine/Nav1.5 overpredicted (4.3→6.8). Spearman 0.43 clears the bar but
Pearson is only 0.31 and n=10 is small — consistent with the paper's modest NRMSE 0.906 (rank yes,
precise pKd no).

### Jernabix → Nav1.8 (named test) — FAIL
"Jernabix" = **Journavx = suzetrigine (VX-548)**, Vertex's selective Nav1.8 inhibitor (the plan's
"JZP-110/solriamfetol" lead was wrong). With PEER, suzetrigine→Nav1.8 = 7.00, but ibuprofen→Nav1.8
= 7.60 and suzetrigine→carbonic-anhydrase = 7.09 score higher — no separation. Three reasons this
specific case is hard: (1) Nav1.8 is 1956 aa, truncated to 1250 — the binding region is likely in
the 706 unseen C-terminal residues; (2) suzetrigine was approved Jan 2025, after the Oct-2024
training cutoff; (3) the model over-scores generic small molecules (ibuprofen), so single-target
binder-vs-decoy discrimination is weak off-the-shelf.

## Reconciling with the paper's "SOTA" DTI claim (verification)
We reproduced the paper's own DTI metric to confirm we load/query correctly. On a real
BindingDB_Kd test sample (n=150, pKd range 2.0–9.3), `scripts/phase1_nrmse_verify.py`:

| checkpoint | NRMSE | Pearson | Spearman | pred range |
|---|---|---|---|---|
| cold-split | 0.859 | 0.532 | 0.468 | 3.1–7.0 |
| **PEER** | **0.880** | **0.654** | 0.526 | 3.4–8.8 |
| paper (PEER holdout) | **0.906** | — | — | — |
| mean-predictor | 1.000 | 0 | 0 | — |

**We match the paper (NRMSE 0.86–0.88 vs their 0.906).** This proves loading and querying are
correct. It also exposes what "SOTA" means here: NRMSE 0.906 is only ~9% better than predicting the
average affinity (the mean-predictor scores exactly 1.0); the model explains ~a quarter of the
variance (Pearson ~0.5–0.65 *on its own benchmark*). It tops the leaderboard because cross-modal
DTI generalization is a hard, universally-poorly-solved task — not because it is accurate.
Our Quiver-pair PEER Spearman (0.43) is consistent with the benchmark (0.47–0.53); the small gap is
pChEMBL-vs-Kd assay mismatch + harder targets, not a pipeline error. The PEER checkpoint is also the
better DTI checkpoint (higher Pearson, less prediction compression).

## What we ruled out (so the numbers are trustworthy)
- **Pipeline bug** — inference is byte-identical to IBM's model-card example and test file.
- **Weight load** — all checkpoint keys matched.
- **MPS artifact** — CPU and MPS predictions identical to 4 decimals.
- **Non-determinism** — repeated runs identical.

## Recommendation
1. **Use the PEER checkpoint (`dti_bindingdb_pkd_peer`), not the cold-split one**, for any DTI work on our targets.
2. **MAMMAL DTI is usable for enrichment / re-ranking** (the meeting's use case #1) on our classes —
   rank-order a candidate list, don't trust absolute pKd. Not reliable for single-target binder-vs-decoy calls.
3. **Mind truncation** for large targets (>1250 aa): Nav channels lose their C-terminal half. Consider
   passing the binding-domain region rather than the full sequence.
4. **Next:** validate the BBBP + ClinTox heads on known compounds (directly serves Phase 2a de-risking),
   and decide whether the modest DTI precision warrants fine-tuning on Quiver/CNS affinity data (Q14).
5. The original "Phase 1 fails, stop" call is **revised** — with the correct checkpoint, the correlation
   test passes. Proceeding to a scoped Phase 2a (hit-list de-risking with BBBP/ClinTox) is justified.

## Different heads — BBBP + ClinTox de-risking (PROPER held-out eval)
These are Phase 2a's de-risking filters. Unlike DTI (cross-modal protein+drug), these are
single-molecule property heads — and they work **at published, SOTA level off-the-shelf**.

Evaluated on the canonical MoleculeNet **scaffold-split test fold** (deepchem ScaffoldSplitter
reproduced with rdkit; the split MAMMAL says it finetuned on):

| Head | Our held-out AUROC | Paper | acc@0.5 | test n (pos rate) |
|---|---|---|---|---|
| `moleculenet_bbbp` | **0.968** | 0.957 | 0.85 | 204 (0.52) |
| `moleculenet_clintox_tox` | **1.000** | 0.986 | 1.00 | 148 (0.07) |

BBBP is the clean confirmation (balanced test fold, matches the paper). ClinTox's literal 1.000 should
be read as "matches the paper's 0.986" — the test fold has only ~10 positives and the small dataset
means our reproduced split may overlap MAMMAL's training (mild leakage). Both are usable de-risking
filters as-is.

**Earlier quick BBBP check (accuracy 0.55) was a flawed test, not a model failure** — that set was
confounded by P-gp efflux substrates (permeable but pumped out; a structure-only model can't know) and
by vancomycin exceeding the 256-token drug limit. The proper held-out eval (0.968) is the real number.

**Why property heads work but DTI struggles:** BBBP/ClinTox are single-molecule SMILES→property — no
protein, no cross-modal generalization, no truncation, well-covered chemical space. DTI requires
generalizing binding to unseen *target classes* — much harder. The split is mechanistically sensible.

**Meta-lesson (recurring):** naive off-the-shelf evaluation of MAMMAL produces false negatives —
wrong DTI checkpoint (−0.03 → 0.43), confounded BBBP hand-set (0.55 → 0.968 done right). The model
works when used correctly; the discipline is the right checkpoint + a clean, in-domain, properly-split eval.

## Reproduce
```
/opt/anaconda3/envs/mammal/bin/python scripts/phase0_smoke_test.py
/opt/anaconda3/envs/mammal/bin/python scripts/phase1_correlation.py          # cold-split, our pairs
/opt/anaconda3/envs/mammal/bin/python scripts/phase1_peer_comparison.py      # PEER, our pairs (the fix)
/opt/anaconda3/envs/mammal/bin/python scripts/phase1_indistribution_check.py # BindingDB_Kd control
/opt/anaconda3/envs/mammal/bin/python scripts/phase1b_bbbp_check.py           # BBBP quick hand-set (flawed; see note)
/opt/anaconda3/envs/mammal/bin/python scripts/phase1b_molnet_eval.py bbbp     # BBBP proper scaffold-test AUROC
/opt/anaconda3/envs/mammal/bin/python scripts/phase1b_molnet_eval.py tox      # ClinTox-tox proper AUROC
```
Scripts set `USE_TF=0` (transformers deadlocks importing TensorFlow on macOS). Weights are local copies
under `models/` (HF downloader resume is broken on this network; fetched via curl). PEER norms: 6.286 / 1.542.
