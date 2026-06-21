# Boltz-API Tier-2 (ADME / library-screen / de-novo design) on Quiver CNS, 2026-06-17

Ran the three remaining Boltz Compute capabilities via the hosted **boltz-api** (no GPU, no CUDA — the
CUDA-13 unlock). All built on existing Quiver assets. **Total ~$1.9** (T4 $0.11 + T5 ~$1.10 + T6 $0.60),
matching the free `estimate-cost` ($1.985). Driver `experiments/boltz_tier2_run.py`; re-parse (idempotent,
no re-bill) `experiments/boltz_tier2_parse.py`; raw `results/boltz_tier2_result.json`.

Per-unit pricing (the Tier-2 surprise): **ADME $0.01/mol, screen & design $0.025/mol — flat, size-
independent**, i.e. ~8× cheaper per ligand than a full structure-and-binding co-fold of the 1956-aa Nav1.8
(~$0.20/fold in Tier-1). This reprices the whole binder-triage workflow (see T5).

## T5 — library-screen = the operational win (new structure-based virtual-screening track)

Screened **44 molecules** against Nav1.8 (`small-molecule:library-screen`): the 11-cpd panel + 20 strong
SCN10A ChEMBL actives (pChEMBL ≥ 7) + 20 measured inactives (pChEMBL < 5). 7 of 51 submitted were
**filtered pre-fold** by Boltz's default molecule filters (the giant linaclotide-like peptide, metformin,
carbamazepine, a few inactives) — 0 fold failures, 0 invalid.

| readout | AUROC (n=44) | panel-only (n=9) | ChEMBL only (n=35) |
|---|---|---|---|
| **`optimization_score`** | **0.808** | **0.889** | **0.859** |
| `binding_confidence` | 0.678 | — | — |
| `iptm` | 0.520 | — | — |

- **`optimization_score` is the screen's right readout** (0.81), well above `binding_confidence` (0.68,
  which matches Tier-1 Q1's per-fold 0.71) and `iptm` (0.52). The panel-only 0.889 ≈ Q1's best per-fold
  readout (`ligand_iptm` 0.893) — **but at $0.025/molecule vs ~$0.20/fold.**
- **Headline for the stack:** for Nav1.8 binder triage at scale, use **`library-screen` + `optimization_score`**,
  NOT per-fold `structure-and-binding`. Same discrimination, **~8× cheaper**, and one call returns binding +
  structure + a free ADME column per molecule.
- The harder test — **potent (pChEMBL≥7) vs measured-weak (<5) within the related suzetrigine
  sulfonamide-carboxamide series — still hits 0.86.** That's real enrichment inside a chemotype, not just
  binder-vs-random-decoy.
- Still **below the per-target ligand fine-tune (0.987 in Q1)** — consistent with Tier-1: structure
  **complements**, doesn't replace, the in-domain QSAR. Top-8 by `optimization_score` is 7 ChEMBL actives +
  1 inactive (inact-15, a CF3-pyridone carboxamide — a near-miss false positive).

## T6 — de-novo design = generative track revived

Generated **24 novel Nav1.8 candidates** in **Enamine REAL** (synthesizable space) with the `recommended`
SMARTS catalog filter, then scored each for validity + scaffold-novelty vs known Nav1.8 binders (panel +
top-200 ChEMBL actives).

- **24/24 valid; 22/24 novel Murcko scaffolds; median max-Tanimoto to any known binder = 0.19** — genuinely
  novel, not regurgitating the training actives.
- Top `optimization_score` 0.25–0.35 — **the same band as the screened real actives (0.31–0.42)** in T5, so
  the generator proposes structurally plausible, structure-scored candidates.
- **Contrast with public MAMMAL**, which is a span-infiller (grammar-valid *analogs* only, 1/8 exact
  recovery, no usable de-novo). **Boltz design does real synthesizable de-novo generation** — this is a
  capability MAMMAL's public artifact does not have.
- Caveat: `optimization_score` is model self-consistency, not affinity; the T5 panel AUROC (~0.81–0.89)
  bounds confidence. These are **synthesis hypotheses**, not validated hits — feed the top few through the
  per-target fine-tune + a docking pose before ordering.

## T4 — ADME = cheap de-risking sanity layer (and it's free inside every screen)

11 Nav-panel CNS drugs through `predictions:adme` (Tier-1 solubility / permeability / lipophilicity),
$0.01/mol. Directionally correct:

- CNS-penetrant Nav blockers score **high permeability** (mexiletine 1.73, lidocaine 1.62, caffeine 1.36,
  lacosamide 1.28); hydrophilic non-CNS decoys score **low / negative** (metformin perm −0.54 / logD −1.06;
  atenolol −0.29 / −1.15) — exactly right.
- A-803467 correctly flagged **`high-risk` solubility** (notoriously insoluble tool compound).
- **Every `library-screen` result row already carries an `adme` object** (solubility/permeability/
  lipophilicity) for free — so the screen delivers binding + ADME in a single call. Complements MapLight
  (our BBBP/hERG/DILI gate), doesn't replace it.

## Net / scorecard impact

- **New track — structure-based virtual screening (Boltz library-screen):** Nav1.8 enrichment AUROC **0.81**
  (`optimization_score`) at **$0.025/mol**; the cost-efficient way to do binder triage at scale (use this,
  not per-fold). Free ADME column bundled.
- **Generative / de-novo design track revived (Boltz design):** 100% valid, 92% novel-scaffold, synthesizable
  Enamine REAL candidates scored in the real-active band — a capability public MAMMAL lacks.
- **ADME track:** cheap, directionally sound Tier-1 properties; redundant with the free screen column.
- **Consistent with Tier-1:** structure is a **complement** to the per-target ligand fine-tune (0.987), best
  used for scale/cost (screen) and novel chemotypes (design + the suzetrigine rescue from Q1).
- **boltz-api stays the operational unlock** for the whole Boltz suite with no GPU/CUDA toolchain.

**Receipts:** `experiments/boltz_tier2_run.py` (idempotency keys `tier2-t{4,5,6}-*`),
`experiments/boltz_tier2_parse.py`, `results/boltz_tier2_result.json`; per-molecule CIFs/metrics under
`results/boltz_tier2_runs/` (gitignored). Jobs idempotent server-side (no re-bill on re-parse/re-download).
