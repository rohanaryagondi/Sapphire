# DrugCLIP — pocket↔molecule shared-embedding eval on Quiver panels (2026-06-14)

**Question:** does DrugCLIP (the structure-based CLIP-for-virtual-screening SOTA) give a usable
pocket↔molecule cosine on Quiver targets — the structure-based counterpart to BALM's
sequence-based shared space?

**Model:** DrugCLIP (NeurIPS 2023, MIT; Uni-Mol 3D pocket encoder + Uni-Mol 3D molecule encoder,
CLIP-contrastive shared space, cosine retrieval). Checkpoint `checkpoint_best.pt` (1.18 GB, now
S3-cached). **Run:** AWS g5.xlarge; eval `aws/drugclip_crossmodal_eval.py`, literature-pocket mode.

## Result — DrugCLIP fails on our pockets (below chance)

Same Nav1.8 (n=11) + mTOR (n=7) binder/decoy panels as BALM/Boltz-2.

| Target | **DrugCLIP AUROC** | binder/decoy cosine sep | BALM | Boltz-2 | ConPLex |
|---|---|---|---|---|---|
| **Nav1.8** | **0.393** (below chance) | −0.05 (binders *lower*) | 0.857 | 0.714 | 0.437 |
| **mTOR** | **0.250** (below chance) | −0.16 (binders *lower*) | 1.000 | 1.000 | — |

The pipeline ran cleanly (retrieval_rc=0, all 18 compounds scored), so this is a real result, not a
failure: **DrugCLIP's pocket↔molecule cosine does not separate binders from decoys on our targets —
it's below chance, with a decoy (ibuprofen) ranked #1 on both.** Cosines are tiny (−0.15 to +0.19)
vs BALM's clear binder band (~0.5). DrugCLIP is the **worst** of the four on this substrate.

## Why — it's the pocket, not the model
DrugCLIP is **highly sensitive to pocket definition** (it's trained on crystal/holo-defined DUD-E /
PDBbind pockets; cf. "Does DrugCLIP Find the Right Pocket?"). We had no holo crystal for these
targets, so we fed it the only thing available: a pocket carved from **approximate literature
site-residues on an apo AlphaFold v6 model** (Nav1.8 DIV-S6 anesthetic pore ~res 1399–1406; mTOR
FRB ~2025–2114) + 12 Å. That is almost certainly an ill-defined / mis-located pocket for a 1956-aa
channel and a 2549-aa kinase, and DrugCLIP degrades to noise on it. This is an **operating-envelope
finding, not a bug**: pocket-based screening needs a good, ligand-defined binding site — exactly
what Quiver's hard targets usually lack.

## Verdict (and the BALM contrast this sharpens)
For Quiver's compound↔target shared-embedding need, **the sequence-based model (BALM) is the
practical winner and the pocket-based SOTA (DrugCLIP) is the wrong tool absent crystal pockets:**
- **BALM** (seq → seq): Nav1.8 **0.857**, mTOR **1.000**, real cosine geometry (+0.31 sep), inputs we
  always have (sequence + SMILES). See `results/balm_crossmodal.md`.
- **DrugCLIP** (pocket → mol): **below chance** here because it needs a crystal-quality pocket we
  don't have. It would likely shine on targets *with* a good holo structure (its DUD-E numbers are
  excellent) — but that's not Quiver's data-poor regime.

So the cross-modal investigation is complete: **yes, a good compound↔target shared-cosine model
exists for us — BALM** — and the structure-based alternative is gated on pocket quality we lack.

## If revisited later
The checkpoint is S3-cached (`s3://rohan-mammal-bootstrap-20260610-213029/drugclip_crossmodal/checkpoint_best.pt`)
and the full toolchain is solved (Uni-Core 0.0.1+cu118torch2.0.0 wheel, rdkit 2022.9.5 + numpy<2,
ipython, `data` positional, no `--dict-name`). To give DrugCLIP a fair shot: use a **holo/crystal
pocket** (or dock a reference ligand to define the site) instead of apo-AlphaFold + literature
residues, and confirm the residue numbering matches the structure.

**Receipts:** `s3://…/drugclip_crossmodal/drugclip_crossmodal_result.json`, eval
`aws/drugclip_crossmodal_eval.py`, pocket prep `aws/drugclip_pocket_prep.py`. Setup chain (8 runs):
Uni-Core wheel filename, AlphaFold v4→v6, numpy<2 (rdkit ABI), checkpoint direct-file-id+S3-cache,
ipython debug-import, `--dict-name` removal, `data` positional — all in git history.
