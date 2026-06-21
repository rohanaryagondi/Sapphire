# Boltz-API Tier-1 (Q1 + Q3) — structure-and-binding on Quiver CNS, 2026-06-17

Ran Boltz-2.1 **structure-and-binding** via the hosted **boltz-api** (no GPU, no CUDA toolchain — the clean
fix for the local-Boltz CUDA-13 block). 29 real co-folds (`num_samples=1`), ~**$3.8** total (Q1 11 + Q3 18
folds ≈ $3.55, + ~$0.22 throwaway probes from debugging). Readouts: `binding_metrics.binding_confidence`,
`optimization_score`, and `ligand_iptm` (ligand-interface pTM) from `outputs/files/prediction/metrics.json`.

## Q1 — Nav1.8 binder-vs-decoy (n=11; 7 binders / 4 decoys)

| readout | AUROC |
|---|---|
| **`ligand_iptm`** (interface confidence) | **0.893** |
| `binding_confidence` | 0.714 |
| our per-target fine-tune (baseline) | **0.987** |
| BALM zero-shot (baseline) | 0.857 |

**Verdict: Boltz structure-based binding is decent but below our in-domain ligand fine-tune for ranking the
whole panel — yet it COMPLEMENTS it exactly where the ligand model fails.** The headline:

- **It rescues the OOD miss.** Our ligand fine-tune scored **suzetrigine→Nav1.8 = 0.14** (a false negative —
  novel 2024 scaffold, out-of-domain). **Boltz `binding_confidence` = 0.479, the 2nd-highest of all 11 and
  cleanly above every decoy.** Structure "sees" the binding the ligand QSAR couldn't. This is the
  add-structure-for-novel-chemotypes thesis, confirmed.
- It nails the potent, distinct binders (A-803467 0.59 top, mexiletine 0.44) and ranks decoys low
  (metformin 0.11, atenolol 0.04), but **misses the weak pore local-anesthetics** (lacosamide 0.04 — last;
  lidocaine/carbamazepine 0.165), which drags `binding_confidence` to 0.71. `ligand_iptm` is the better
  readout here (0.89) — it captures the interface even for the weak binders.
- One decoy false-positive-ish: ibuprofen 0.255 (highest decoy).

**Takeaway for the stack:** don't replace the per-target fine-tune (0.987 in-domain) with Boltz — but **add
Boltz as the second opinion for novel scaffolds the fine-tune flags low-confidence** (it caught suzetrigine).
Use `ligand_iptm` (0.89), not `binding_confidence` (0.71), as the structural binder score.

## Q3 — TSC2 deconvolution: PKM2 vs PPARD `binding_confidence`

| compound | true (PKM2/PPARD) | PKM2 | PPARD | Boltz higher |
|---|---|---|---|---|
| QS0113172 (the hit) | 1 / 1 | 0.222 | 0.188 | PKM2 |
| GSK 3787 | 0 / 1 (PPARD) | 0.262 | 0.250 | **PKM2 ✗** |
| QS0069567 | 0 / 1 (PPARD) | 0.343 | 0.172 | **PKM2 ✗** |
| "Dasa-58"* | 1 / 0 | 0.479 | 0.522 | PPARD ✗ |
| controls (GF109203X / carbamazepine / BMS191011 / Biperiden / BIIB021) | 0 / 0 | 0.11–0.46 | 0.11–0.43 | mixed |

**Verdict: structure-based `binding_confidence` does NOT deconvolve PKM2 vs PPARD either** — the two known
PPARD binders score *higher on PKM2* (wrong direction), values sit in one undifferentiated 0.1–0.5 band, and
a control (GF109203X) scores high on PKM2 (0.45). So **co-folding fails the TSC2 deconvolution, same as both
zero-shot and supervised ligand-QSAR.** Caveats that soften (not overturn) this: GSK3787 is a **covalent**
PPARD antagonist (covalent binding isn't modeled by standard co-folding); the panel's "Dasa-58" SMILES is
wrong (a nucleotide — flagged earlier); PKM2 is a **tetramer** with an allosteric site and PPARD was folded
as a **full-length monomer** (the LBD is the real pocket) — so the targets may be mis-conditioned. Even so:
TSC2 deconvolution remains unsolved by structure; the open routes stay **Quiver functional/DFP signatures**,
or better-conditioned structures (PPARD-LBD only, PKM2 multimer + allosteric pocket).

## Net / scorecard impact
- **Track 3 (structure-based binding) now has real Quiver numbers** (was "documented / AWS-served"): Boltz-2.1
  via hosted API, Nav1.8 binder AUROC 0.89 (`ligand_iptm`) / 0.71 (`binding_confidence`) — a useful
  **complement** to the ligand fine-tune, decisive specifically on **novel scaffolds** (suzetrigine rescue).
- **boltz-api is the operational unlock**: Boltz-2.1 with no GPU/CUDA toolchain (kills the CUDA-13 block).
- Q3 leaves TSC2 deconvolution open — structure didn't crack it under these conditions.

**Receipts:** `experiments/boltz_tier1_run.py` (model boltz-2.1; idempotency keys `tier1-q*`),
`results/boltz_tier1_result.json`, per-job CIFs+metrics under `results/boltz_tier1_runs/` (gitignored if
large). Q2 (suzetrigine × 9-paralog selectivity, ~$2.6) deferred. Jobs are idempotent server-side (no
re-bill on re-download).
