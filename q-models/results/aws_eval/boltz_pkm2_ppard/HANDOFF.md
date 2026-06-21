# HANDOFF — Boltz-2 PKM2/PPARD: the fair structural retest (for the AWS Claude)

**From the Bouchet Boltz Claude, 2026-06-11.** Bouchet GPU is jammed (Ada ~3.5-day queue; the H200 is
held by Rohan's own TransformerModel job), so the *fair structural retest* below is **built and staged
but not yet run**. Everything you need is in this folder. You're on AWS with real GPU — please run it.

---

## The mission (unchanged)

Ben (Quiver) ran a 30K Optopatch screen for compounds that rescue a **TSC2 phenotype**; two hits,
**QS0069567** and **QS0113172**, came up. Ben's DFP library functionally matched them to **Dasa-58**
(PKM2 activator) and **GSK 3787** (PPARD antagonist). Question: does that functional match translate to
**physical binding**? **Binding targets are PKM2 (UniProt P14618) and PPARD (Q03181). TSC2 is the
phenotype — do NOT build a TSC2 complex.**

## What's already done (read these)

- **Off-the-shelf run (monomer / full-length): COMPLETE → INCONCLUSIVE.** All 15 of Ben's complexes ran
  clean (rc=0). The **positive controls didn't clear the decoys**, so Boltz couldn't adjudicate the
  putatives. Baseline numbers (you'll compare against these):
  - PKM2 / **Dasa-58 (positive) = 0.511** — only +0.013 over the top decoy (BMS 191011 0.498). Tied.
  - PPARD / **GSK 3787 (positive) = 0.209** — *below* the decoy mean (0.245); decoy BMS 191011 = 0.512.
  - Putatives all decoy-like (0.20–0.23).
  - Raw: `results.json`; writeup: `../ben_tsc2_pkm2_ppard.md`; biology of why it failed:
    `../../../RohanOnly/boltz/boltz_pkm2_ppard_biology.md`.
- **Diagnosis (the reason the retest exists):** for PKM2 the DASA-58–class activator pocket sits at a
  **subunit interface that does not exist in a monomer fold** — Boltz literally never built the binding
  site. For PPARD, GSK 3787 is a **covalent** antagonist (Boltz models only reversible binding) and the
  LBD is a big greasy pocket. Decoys are real drugs (binders of *other* targets) and score "sticky."

## YOUR JOB: run `fair_retest_panel.json`

It changes **only the protein representation** (Ben's compounds + SMILES are byte-for-byte identical):

| target | original (failed) | fair retest (this panel) |
|---|---|---|
| **PKM2** | monomer (531 aa) — activator pocket absent | **homodimer** (`n_chains: 2`, 1062 aa) → the dimer-interface activator pocket is present |
| **PPARD** | full-length (441 aa) | **LBD only** (residues 211–441, 231 aa) → cleaner ligand-binding pocket |

15 complexes: PPARD-LBD ×8 (1 positive GSK 3787 + 2 putatives + 5 negatives) then PKM2-dimer ×7
(1 positive Dasa-58 + 1 putative QS0113172 + 5 negatives). Sequences are embedded in the JSON.

### How to run

1. **Install Boltz 2.2.1.** Use **`--no_kernels`** — this is the safe path and it's already baked into
   `scripts/boltz_runner_multimer.py`. The cuequivariance kernels are the landmine: the handoff's
   `cuequivariance-ops-cu13-torch` is a **non-existent package** (real name `cuequivariance-ops-torch-cu12`,
   cu12-only), and even when correctly installed the kernels crashed at runtime on Bouchet. On the AWS DL
   AMI (driver 580 / CUDA 13) the default `torch ...+cu130` *will* initialize CUDA (Bouchet's driver 570
   could not — that's why we pinned cu128 there; you likely don't need the pin). Either way, **keep
   `--no_kernels` unless you verify the kernels actually run.** Full corrected recipe + post-mortem:
   `../boltz_nav_eval.md` §11.
2. **Env vars:** `BOLTZ_CACHE` (weights ~7.5 GB auto-download on first run), `HF_HOME`, `BOLTZ_OUT`.
3. **Run:** `BOLTZ_OUT=/path python scripts/boltz_runner_multimer.py fair_retest_panel.json`
   — it loops the complexes, reads `n_chains` per complex (folds that many identical protein chains +
   the ligand, affinity binder = ligand), and atomically writes `results.json` to `BOLTZ_OUT`.
   `scripts/run_boltz.sbatch` shows the Bouchet SLURM invocation (env vars + flags) — adapt to AWS.
4. **GPU sizing:** PPARD-LBD (231 aa) is tiny/fast. **PKM2 dimer (1062 aa)** needs a bigger card — it OOMed
   the 32 GB Bouchet Ada in testing; use **A100 40/80 GB** (the Nav 1956 aa runs fit a 141 GB H200 fine).

### The calibration gate (LOAD-BEARING — do this first)

Check the **positive controls** before reading anything else: `PKM2dim_QS0321744` (Dasa-58) and
`PPARDlbd_QS0321760` (GSK 3787). The test is the **positive-vs-negative margin per target**, not the
absolute value: *does the positive now clear the 5 decoys?*
- If the **PKM2 dimer rescues Dasa-58** (clears the decoys, vs the tied 0.511 baseline) → the pocket fix
  worked; now read the putative QS0113172 vs the decoys. **Optional escalation:** if the dimer only
  half-helps, run the **homotetramer** — copy `fair_retest_panel.json`, set `n_chains: 4` on the PKM2
  entries (2124 aa, needs A100 80 GB). The tetramer is the full native assembly.
- If the positives **still** don't separate, the inconclusive verdict stands even with fair structure —
  itself a strong, reportable result.

**⚠ Critical caveat (surfaced by an independent literature review of our biology claims, 2026-06-11):**
Boltz-2's own *Limitations* section states the affinity module **does not explicitly handle multimeric
binding partners**. So the homodimer/tetramer fixes the *structure* (the A–A′ interface activator pocket
now physically exists — DASA-58 was co-crystallized there, Anastasiou 2012 PMID 22922757), **but the
affinity head may still not score a ligand bound at a subunit interface.** A flat PKM2-multimer result is
therefore **confounded** — affinity-module limitation vs. true non-binding — *not* clean evidence the
compound doesn't bind. If the multimer doesn't rescue Dasa-58, the honest read is "Boltz-2 can't be
trusted on this interface-pocket target," and the genuinely fair test becomes a **pocket-restricted
docking / absolute-binding-FEP run on a PKM2-activator co-crystal template** (e.g. PDB 3GR4/3ME3/4G1N
class) rather than Boltz affinity. Please state this caveat explicitly in your writeup.

**[POST-RUN UPDATE — the AWS retest has since run; see §7 of `../ben_tsc2_pkm2_ppard.md`.]** The multimer
limitation proved **non-fatal here**: the PKM2 dimer **rescued** Dasa-58 to #1 (+0.054 over the top
decoy), and on that calibrated panel QS0113172 fell below 4/5 decoys → **QS0113172↔PKM2 REFUTED** (low
margin). PPARD-LBD stayed **inconclusive** (covalent GSK 3787 ranked below the decoys), exactly as
predicted. So the dimer fix worked; the residual concern is the *narrow* margin, not a hard multimer failure.

### Don't put a thumb on the scale
- **GSK 3787 is covalent** → Boltz may keep it low regardless of structure. The LBD fix helps the pocket,
  not the covalent mechanism. A low PPARD positive is expected, not a bug — flag it, don't hide it.
- Run Ben's SMILES exactly as given (a professional chemist provided them). Do **not** substitute
  "canonical" structures. The only thing we changed is the protein assembly/domain, never the ligands.
- Either outcome (confirmed / refuted / inconclusive) is useful. No thumb on the scale.

## Where to put your results
- Append a **"Fair structural retest"** section to `../ben_tsc2_pkm2_ppard.md` (positive-vs-negative and
  putative-vs-negative margins for the dimer/LBD run; compare to the monomer baseline; 1-paragraph
  verdict).
- Raw JSON → this folder (e.g. `fair_retest_results.json`).
- Leave a 1-line note that `docs/models_tracks_scorecard.md` (on the **`models` branch**) Tracks 2 + 9
  may shift — Rohan merges across branches; don't edit the other branch directly.
- Push to the **`boltz`** branch.

## Files in this kit
- `fair_retest_panel.json` — **the 15 complexes to run** (PPARD-LBD ×8 + PKM2-dimer ×7; `n_chains` set).
- `ben_pkm2_ppard_panel.json` — the original monomer/full-length panel (reference).
- `results.json` — the original (inconclusive) run results — your comparison baseline.
- `scripts/boltz_runner_multimer.py` — **use this**; supports the `n_chains` field for homo-oligomers.
- `scripts/boltz_runner_nokernels.py` — the original single-chain runner (what produced `results.json`).
- `scripts/run_boltz.sbatch` — Bouchet SLURM wrapper (env-var invocation reference; AWS won't use SLURM).
- `scripts/seq_P14618.txt`, `seq_Q03181.txt`, `seq_Q03181_LBD.txt` — sequences (also embedded in panels).
