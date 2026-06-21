# Boltz validation panel — known-drug-target calibration test (2026-06-12)

**Run:** AWS g6e.xlarge in us-east-1b, 13 min wall time, $0.57 spend.
All 9 complexes rc=0. **Total Boltz-lane spend: $5.59 / $15 cap.**

**Reason for the run:** sanity-check Boltz on three canonical drug-target
pairs (gold-standard pharmacology) to map where Boltz cleanly calibrates
vs where its architectural limits kick in.

## TL;DR

| Pair | Construct | Boltz result | Calibration |
|---|---|---|---|
| **Rapamycin / mTOR-FRB** | mTOR residues 2015-2114 (100 aa) | Rapamycin = 0.79 vs decoys 0.23-0.33. **Clean +0.47 margin.** | ✓ Excellent |
| Flupirtine / KCNQ2 | KCNQ2 TMD residues 91-323 (233 aa) — **monomer** | Flupirtine = 0.42 vs decoys 0.35-0.36. Narrow +0.05 margin. | ✓ Marginal |
| **Ketamine / NMDAR-GRIN1** | GRIN1 TMD residues 558-810 (253 aa) — **monomer of one subunit** | Ketamine = 0.11, **ranked LAST** below both decoys (0.40, 0.46) | ✗ **CATASTROPHIC** |

## Per-target details

### mTOR-FRB + Rapamycin — clean validation ✓

| Rank | prob_binder | Compound |
|---:|---:|---|
| 1 | 0.7926 | Rapamycin (POSITIVE) |
| 2 | 0.3274 | BMS 191011 |
| 3 | 0.2300 | BIIB021 |

Best calibration in this panel. **Rapamycin scores 0.79 — strong clean signal**,
margin +0.47 over the top decoy. I had flagged the FKBP12 concern earlier
(rapamycin's real binding mode is through FKBP12-mediated ternary complex),
but **Boltz can in fact model rapamycin's direct FRB interaction** without
FKBP12 nearby. The FRB pocket has enough binding-mode information for Boltz
to recognize rapamycin directly. Reproduces the original Bouchet result
(1.000) in spirit.

### KCNQ2-TMD + Flupirtine — marginal calibration

| Rank | prob_binder | Compound |
|---:|---:|---|
| 1 | 0.4167 | Flupirtine (POSITIVE) |
| 2 | 0.3632 | BIIB021 |
| 3 | 0.3548 | BMS 191011 |

Flupirtine wins #1 but only by **+0.054** over top decoy — narrow, same
"marginal but real" regime we saw on Nav1.8 (AUROC 0.714) earlier in this
campaign. The cause is structural: **KCNQ2 is a homotetramer**, the activation
gate where flupirtine binds is formed at the inter-subunit interface (S5
helices of adjacent monomers). A single subunit captures part of the binding
site but not the full geometry. Same architectural lesson as PKM2 monomer →
dimer: if a tetramer test were rerun with `n_chains=4` the calibration would
likely sharpen substantially.

### NMDAR-GRIN1 + Ketamine — CATASTROPHIC failure

| Rank | prob_binder | Compound |
|---:|---:|---|
| 1 | 0.4574 | BIIB021 (decoy) |
| 2 | 0.4019 | BMS 191011 (decoy) |
| 3 | **0.1060** | **Ketamine (POSITIVE)** |

Ketamine — the well-characterized NMDA-receptor channel blocker — ranks
LAST at 0.11. Both decoys outscore it by 4×. **Margin: −0.35.**

This is a clean architectural failure case, exactly the pattern we now
recognize:
- Ketamine binds the **open-channel pore** of the NMDA receptor.
- The NMDA receptor is a **heterotetramer of GRIN1 + GRIN2B** subunits.
- The pore lives at the 4-subunit assembly interface (M2 region of all 4 chains).
- I supplied a single GRIN1 subunit (1 chain). **The pore literally doesn't exist** in that input — same failure mode as PKM2 monomer for Dasa-58, and BAZ2B isolated BRD for GSK2801.
- Without a binding site to recognize, Boltz scored ketamine on opportunistic surface fits, where its rigid bicyclic ketone scaffold loses to drug-like decoys with more flexible aryl + heterocycle features.

A heterotetramer rerun (2 GRIN1 + 2 GRIN2B, n_chains=4 with heteromer schema)
would likely fix the calibration — same as the PKM2 dimer fix worked.

## Synthesis — Boltz architectural-limit rules confirmed

This validation panel + the prior PKM2 / BAZ2B results give us a clean
testable rule for which Boltz panels to run vs not:

| Binding site lives in... | Boltz calibration probability |
|---|---|
| Single domain, intrasubunit (mTOR FRB, mTOR kinase, LDHA, PPARA-LBD, RXRA-LBD) | High ✓ |
| Multi-subunit interface, but tetramer/dimer construct supplied | High ✓ (PKM2 dimer = +0.054 ; Dasa-58 cleanly recognized) |
| Multi-subunit interface, but only monomer supplied | **Failed** (PKM2 monomer, NMDA GRIN1 monomer, KCNQ2 partial) |
| Small isolated bromodomain (~115 aa) | **Failed** (BAZ2B BRD) |
| Covalent binding modes | **Failed** (PPARD + GSK 3787) |

For future Quiver Boltz runs the playbook is now:
1. Identify where the drug binds in the target's real biology.
2. If it's at a multi-subunit interface, supply the right assembly (`n_chains=2/4` for homo, or heteromer schema for hetero).
3. If it's covalent or in a small isolated domain, expect failure — don't burn Boltz budget on it.

## Cost

- Run: $0.57 (g6e.xlarge, 13 min wall)
- Cumulative Boltz-lane spend: **$5.59 / $15 cap**
- Remaining: $9.41

## Files

- `aws/boltz_validation_panel.json` (boltz) — 9-complex input panel
- `aws/boltz_validation_userdata.sh` (boltz) — AWS userdata
- `results/aws_eval/boltz_validation/results.json` — raw outputs
- `results/aws_eval/boltz_validation_report.md` (boltz branch) — this report
- `docs/boltz_validation_report_2026-06-12.md` (RohanOnly) — same content
