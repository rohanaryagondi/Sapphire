# ATOMICA for CNS (Nav1.8 binder-vs-decoy) — tested; NOT a useful track for small-molecule triage, 2026-06-16

**Question (candidate new "structural-interaction" track):** does ATOMICA's interface embedding
(mims-harvard, geometric model of intermolecular interactions, MIT) separate Nav1.8 binders from
decoys, beyond a plain docking score? **Answer: no — not for single-target small-molecule triage.**
Total spend ~$0.62 (banked Boltz attempts + one successful docking run); all instances terminated.

## Result (option c — docking, no Boltz)
Docked all 11 panel compounds (7 binders / 4 decoys, 0 skipped) into the real human Nav1.8 cryo-EM
structure **7WFR** (A-803467 / "95T" bound, 1956 aa) with **smina** (`--autobox_ligand` on the bound
blocker = the central-pore drug site), merged each top pose into a complex, embedded the interface
with ATOMICA (`graph_embedding`), and scored binder-vs-decoy.

| readout | AUROC |
|---|---|
| smina docking score (baseline) | **0.786** |
| ATOMICA embedding, LOO cosine-centroid | 0.679 |
| ATOMICA embedding, LOO cosine-kNN | **0.0 (degenerate)** |

**ATOMICA loses to a plain docking score, and its probe is near-degenerate.**

## Why — the embedding is dominated by the (shared) protein, not the ligand
Every ATOMICA cosine score sits at **0.993–0.9995** — i.e. all 11 complexes embed to almost the same
vector. Because all complexes share the **same Nav1.8 receptor**, the whole-complex `graph_embedding`
is dominated by the (identical) protein interface; the small ligand barely moves it. So binder-vs-decoy
separation collapses (0.68 is 4th-decimal noise; the kNN's 0.0 is the same degeneracy). By contrast the
docking score reflects the ligand directly and ranks cleanly (binders carbamazepine −9.2 / suzetrigine
−8.9 / ranolazine −8.6 / A-803467 −8.3; decoys metformin −4.7 / caffeine −5.5 / atenolol −6.8).

## Verdict
- **Do NOT add ATOMICA as a CNS binder-triage track.** For "does drug X bind CNS target Y," a docking
  score (or our per-target fine-tunes / Boltz-2) beats it; ATOMICA's whole-complex embedding adds
  nothing on a single receptor.
- This is consistent with what ATOMICA *is*: an **interface-representation** model built to compare
  DIFFERENT interfaces / PPIs / cross-modal interactions — not to discriminate ligands at one pocket.
  If ever revisited for Quiver, use it for **protein–protein / protein–peptide interface comparison**
  (a capability our small-molecule models lack), or pocket-level `block_embedding` rather than the
  whole-complex vector — not single-target small-molecule triage.

## Caveats (don't over-read the negative)
- n = 11 (wide CI); predicted docked poses, not experimental complexes.
- **Single-site confound:** all ligands docked into the central pore; suzetrigine actually binds VSD-II,
  so its pose is off-site. But this doesn't change the verdict — the failure is the embedding's
  insensitivity to the ligand (all cosines ~0.99), not the pose choice.
- Whole-complex `graph_embedding` used; a pocket-restricted (`block`) embedding might do better — untested.

## Toolchain note (the Boltz detour)
The first design co-folded with Boltz-2; it banked because the current AWS DLAMI ships CUDA-13/torch-cu130
and `cuequivariance-ops-cu13-torch` isn't on PyPI → Boltz can't fold (see [[boltz-broken-cuda13-ami]]).
Option (c) — smina docking + ATOMICA — sidestepped that entirely and ran clean in ~7 min.

**Receipts:** `aws/atomica_dock_nav18_eval.py` + `aws/atomica_dock_nav18_userdata.sh`;
`s3://rohan-mammal-bootstrap-20260610-213029/atomica_dock_nav18/` (result.json, run.log, DONE rc=0);
instance i-0e0f08d181e0577ee (terminated). Prior banked Boltz attempt: same S3 bucket `atomica_nav18/`.
