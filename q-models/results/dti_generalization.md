# DTI Nav-generalization cross-check — GatorAffinity (overnight Phase 3, 2026-06-14)

**Question:** does a structure-based affinity model that claims unseen-protein generalization crack
the **Nav blind spot** that sinks BindingDB-trained DTI (and beat BALM/Boltz-2)?

**Model:** GatorAffinity (AIDD-LiLab, bioRxiv 2025; ATOMICA SE(3) backbone; MIT code, CC-BY-NC-SA
checkpoint = non-commercial research). Chosen over IPBind (no public inference repo).

## Outcome: attempted thoroughly, NOT landable on our pipeline — STOPPED at the cap

GatorAffinity got **further than DrugCLIP** but ultimately didn't score our panels. The full chain,
across 3 AWS runs (checkpoints S3-cached so retries were cheap/fast):

| Stage | Result |
|---|---|
| Uni-Core-free venv (torch 2.1.1+cu118, torch_scatter/cluster, e3nn 0.5.1, openbabel) | ✅ installed |
| GatorAffinity + ATOMICA backbone + fine-tuned checkpoint | ✅ loaded (cached to S3) |
| AlphaFold pocket build (Nav1.8 258 atoms, mTOR 383 atoms) | ✅ built |
| RDKit/MMFF ligand conformers | ✅ built (run 2 fixed an `EmbedMolecule` kwarg bug) |
| `process_pdbs.py` featurization | ✅ runs (run 3 fixed `--input_csv`/`--output_pkl` args) … |
| … but **"Processed 0 protein-ligand pairs"** | ❌ `process_pdbs` can't find a `LIG` residue in our ligand PDBs |
| `inference.py` | ❌ also needs `tensorboard` (uninstalled) — moot given 0 pairs |

**Root cause = input-pose format, not the model.** GatorAffinity's `process_pdbs` expects a properly
prepared protein–ligand **complex** (a ligand `HETATM`/residue named `LIG` positioned in the pocket,
i.e. a real docked/crystal pose). We fed it an **approximate, docking-free pose** (an RDKit conformer
translated to the literature-site centroid). That isn't a valid complex for its featurizer → 0 pairs.
The subagent flagged this risk upfront: *a fair GatorAffinity test needs real docked poses.*

**Head-to-head (GatorAffinity could not produce a number):**
| Target | GatorAffinity | BALM | Boltz-2 | ConPLex |
|---|---|---|---|---|
| Nav1.8 | — (not landable) | 0.857 | 0.714 | 0.437 |
| mTOR | — (not landable) | 1.000 | 1.000 | — |

## Verdict + the campaign-level lesson
**BALM (family-level triage) + Boltz-2 (selectivity / co-folding) remain the Track-2 answers.**
GatorAffinity is not ruled out — it's *untested on a fair input*: it needs real docked complexes,
which on Quiver's data-poor, **no-holo-crystal** targets we don't have (and producing them means
docking, i.e. the very co-folding Boltz-2 already does).

**Recurring lesson across the structure-based models we tried:** both **DrugCLIP** (pocket-based CLIP)
and **GatorAffinity** (structure-based affinity) are **gated on pocket/pose quality we lack** for the
hard targets — DrugCLIP scored below chance on an apo-AlphaFold pocket, GatorAffinity can't featurize
an approximate pose. The **sequence-based** route (BALM) *runs* on our inputs but is family-level-only
(fails selectivity + GPCRs). So for Quiver's data-poor targets: **sequence models for cheap triage,
Boltz-2 co-folding when structure-grounded affinity is needed** — the off-the-shelf structure-based
affinity/CLIP models don't add a usable lever without crystal-quality inputs.

## If revisited
Checkpoints are S3-cached (`s3://…/dti_generalization/gator_ckpt.ckpt`, `atomica.tar`) and the
toolchain is solved. A fair retry needs: (1) real docked poses (e.g. dock each ligand into the pocket
with Smina/Vina, or use a Boltz-2 complex) written as proper `LIG`-residue complex PDBs, and (2)
`pip install tensorboard`. Then `process_pdbs` → `inference.py` should score. Out of scope for the
overnight budget; logged for a future structure-prep pass.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/dti_generalization/` (result + cached ckpts),
eval `aws/dti_generalization.py`. 3 runs, all instances terminated.
