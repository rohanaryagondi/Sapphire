# Boltz overnight briefing — structural layer for the antipodal-rescue CNS program

*Generated 2026-06-17 09:52Z · est. spend ~$18.85 / $50 cap · 51 jobs complete*

## TL;DR — what Boltz is actually useful for on this program

The deck's rescue pairs are mostly *plausible–unconfirmed* (slide 27). Boltz adds a **structural data layer**: (1) a **small-molecule druggability map** of every query/partner target — reliable and cheap; (2) **de-novo starting hits** for the ligandable ones; (3) a weak/exploratory **interface-plausibility** read on rescue pairs (iptm only). Calibrated against Tier-1–3: trust the small-molecule side; treat protein–protein scores as directional only, and **never** read Boltz binding scores as affinity or selectivity (Tier-3: it ranked the Nav1.8-selective drug LAST of 9 paralogs).

## WS1 — Druggability / ligandability map (de-novo `small-molecule:design`, 24 mol, Enamine REAL)

`bindconf_max` = best de-novo binder's binding_confidence on that target's structured domain — a *relative* pocket-ligandability signal (calibrate vs WS2), not an affinity.

| target | role | domain len | bindconf_max | median | verdict | rescue partner (drug target) |
|---|---|---|---|---|---|---|
| **SCN2A** | query | 2005 | 0.710 | 0.235 | ligandable (designs engage strongly) | KCNIP1 / m6A-NMD (restore intact allele) |
| **TSC1** | query | 1164 | 0.688 | 0.335 | ligandable (designs engage strongly) | mTOR pathway / TSC complex |
| **SRCAP** | query | 500 | 0.671 | 0.298 | ligandable (designs engage strongly) | EP400/BRD8/DMAP1 (paralogous H2A.Z machinery) |
| **EP400** | partner | 550 | 0.671 | 0.306 | ligandable (designs engage strongly) | — |
| **EP300** | partner | 390 | 0.660 | 0.283 | ligandable (designs engage strongly) | — |
| **TSC2_GAP** | deep | 230 | 0.645 | 0.335 | ligandable (moderate) | — |
| **KCNQ2** | query | 872 | 0.637 | 0.266 | ligandable (moderate) | STXBP1 (E/I rebalance) |
| **CHD8** | query | 520 | 0.603 | 0.303 | ligandable (moderate) | USP7 / SLC12A2 |
| **STXBP1** | query | 594 | 0.593 | 0.275 | ligandable (moderate) | USP7 (stabilize residual Munc18-1) / STMN2 |
| **HNRNPK** | query | 463 | 0.582 | 0.333 | ligandable (moderate) | USP7 (proteostasis) |
| **SMARCA4** | query | 1647 | 0.581 | 0.337 | ligandable (moderate) | RBBP7 (shared chromatin subunit) |
| **USP7** | partner | 1102 | 0.572 | 0.335 | ligandable (moderate) | — |
| **KDM1A** | partner | 852 | 0.566 | 0.334 | ligandable (moderate) | — |
| **DOT1L** | partner | 1537 | 0.557 | 0.252 | ligandable (moderate) | — |
| **RPS17** | query | 135 | 0.555 | 0.343 | ligandable (moderate) | USP7 (proteostasis) |
| **WDR26** | query | 661 | 0.538 | 0.269 | shallow/partial | CTLH/GID complex (RMND5A/MAEA) |
| **CREBBP** | partner | 580 | 0.531 | 0.27 | shallow/partial | — |
| **TSC2** | query | 1807 | 0.501 | 0.313 | shallow/partial | mTOR pathway (Rheb-GAP) |
| **SYNGAP1** | query | 1343 | 0.482 | 0.281 | shallow/partial | — |
| **RBBP7** | partner | 425 | 0.477 | 0.199 | shallow/partial | — |
| **PTEN** | query | 403 | 0.469 | 0.205 | shallow/partial | — |
| **WDR5** | partner | 334 | 0.403 | 0.206 | poor (likely not SM-tractable) | — |
| **KMT2A** | query | 269 | 0.312 | 0.153 | poor (likely not SM-tractable) | CREBBP/EP300/PAF1 (H3K27ac+elongation) |

## WS2 — Calibration: known-inhibitor recovery (`structure-and-binding`)

Anchors the WS1 scale: a *real potent non-covalent inhibitor* should score high; a decoy (metformin) low. **DOT1L+pinometostat 0.96 and WDR5+OICR-9429 0.98 (vs decoy 0.21/0.49) — clean recovery**, confirming Boltz scores these soluble-enzyme pockets well. (Covalent LSD1+TCP reads low on binding_confidence but high ligand_iptm — covalency isn't modeled; HAT inhibitors A-485 separate weakly, likely an imperfect domain crop.) **So de-novo WS1 `bindconf_max` of 0.5–0.7 = a real but moderately-engaged pocket, NOT a drug-quality fit (those hit ~0.95+).**

| target | ligand | tag | binding_confidence | ligand_iptm |
|---|---|---|---|---|
| CREBBP | metformin | decoy | 0.134 | 0.844 |
| CREBBP | A-485 | inh | 0.274 | 0.969 |
| DOT1L | metformin | decoy | 0.215 | 0.256 |
| DOT1L | pinometostat | inh | 0.958 | 0.946 |
| EP300 | metformin | decoy | 0.128 | 0.867 |
| EP300 | A-485 | inh | 0.23 | 0.984 |
| KDM1A | metformin | decoy | 0.135 | 0.758 |
| KDM1A | tranylcypromine | inh | 0.392 | 0.808 |
| WDR5 | metformin | decoy | 0.493 | 0.971 |
| WDR5 | OICR-9429 | inh | 0.976 | 0.981 |

## Rescue-pair interface plausibility (`protein:library-screen`, iptm — EXPLORATORY)

Anchored to this run's controls: **positive STXBP1↔Syntaxin1A iptm 0.79**; negative baseline (PTEN/RPS17 ↔ STMN2) ≈ 0.42–0.55. Tier-3 showed this readout is weak (binding_confidence degenerate; iptm AUROC ~0.56), so treat as directional confirmation, not proof. Pairs at/above the positive band are the credible structural support for the deck's *plausible-unconfirmed* pairs.

| pair | role | iptm | support |
|---|---|---|---|
| STXBP1↔Syntaxin1A | pos | 0.789 | supported (≥ pos-ctrl band) |
| RPS17↔USP7-TRAF | test | 0.774 | supported (≥ pos-ctrl band) |
| WDR26↔MAEA | test | 0.698 | weak/ambiguous |
| PTEN↔USP7-TRAF | test | 0.679 | weak/ambiguous |
| HNRNPK↔USP7-TRAF | test | 0.652 | weak/ambiguous |
| STXBP1↔STMN2 | test | 0.578 | not supported (≈ neg baseline) |
| WDR26↔GID8 | test | 0.558 | not supported (≈ neg baseline) |
| PTEN↔STMN2(neg) | neg | 0.55 | not supported (≈ neg baseline) |
| STXBP1↔USP7-TRAF | test | 0.481 | not supported (≈ neg baseline) |
| TSC2gap↔RHEB | test | 0.43 | not supported (≈ neg baseline) |
| RPS17↔STMN2(neg) | neg | 0.419 | not supported (≈ neg baseline) |
| WDR26↔RMND5A | test | 0.329 | not supported (≈ neg baseline) |
| TSC2gap↔TBC1D7 | test | 0.291 | not supported (≈ neg baseline) |
| KCNQ2↔STXBP1(neg-size) | test | 0.29 | not supported (≈ neg baseline) |
| PTEN↔TBC1D7(neg) | neg | 0.176 | not supported (≈ neg baseline) |
| HNRNPK↔STMN2(neg) | neg | 0.149 | not supported (≈ neg baseline) |

## WS4 — Deep dive: TSC2 + WDR26

*Deepening (WS5, N=48 designs): TSC2-GAP bindconf_max 0.555, WDR26 0.443 — more sampling did not surface higher-confidence binders, so the ligandability calls below are stable, not undersampled.*

**TSC2** (tuberous sclerosis; Rheb-GAP). Whole-protein design bindconf_max 0.501; TSC2 acts via the mTOR axis; the catalytic GAP domain is the structural handle. Rescue logic is pathway-level (mTOR), so the high-value Boltz use is **ligandability of the GAP domain** + the TSC2-GAP↔RHEB interface (WS3).

**WDR26** (Skraban-Deardorff; WD40 β-propeller, CTLH/GID E3 scaffold). Design bindconf_max 0.538 → shallow/partial. WD40 propellers present a central pocket / PPI face; WS3 probes WDR26↔RMND5A/MAEA (CTLH partners) — the structural test of its complex membership.

## Recommended Boltz next moves (computed from this run)

- **Most ligandable targets (pursue with SM design/screening):** SCN2A, TSC1, SRCAP, EP400, EP300, TSC2_GAP. These have a pocket Boltz engages — good candidates to scale de-novo design + a focused virtual screen.
- **Rescue pairs with structural support (iptm ≥ 0.70, above neg baseline):** RPS17↔USP7-TRAF (0.774). These move from *plausible-unconfirmed* toward *structurally plausible* — prioritize for the proteostasis (USP7) and complex-membership rationales; confirm with deeper co-folding / experiment.
- **De-prioritize for small molecules:** KMT2A (shallow/poor de-novo engagement *and* no known chemical matter — pursue via the partner-inhibition route or non-SM modality).
- **⚠️ De-novo false-negatives:** WDR5 scored low on de-novo design BUT have a WS2-confirmed known inhibitor (e.g. WDR5+OICR-9429 = 0.98) — **de-novo ligandability under-calls known-druggable pockets; always cross-check against known chemical matter before writing a target off.**
- **TSC2:** the focused **Rheb-GAP domain is more ligandable than the whole protein** — design/screen against the GAP domain, not full-length. **WDR26:** WD40 pocket is moderately ligandable; its strongest structural complex signal is **↔MAEA** (CTLH/GID).

## How to read this (capability trust, from Tier-1–3)

- **Small-molecule design/screen/ADME + structure-and-binding** — reliable, cheap ($0.025/mol). Use `optimization_score`/`bindconf` as *relative* ligandability.
- **protein:library-screen / protein:design** — exploratory only (iptm-weak; binding_confidence dead).
- **Not an affinity or selectivity oracle** — Tier-3 ranked Nav1.8-selective suzetrigine LAST of 9.
- Large multidomain proteins folded whole (≤2500) or cropped to the catalytic domain — lower-confidence than a single clean domain; flagged per row by `domain len`.

## Top de-novo candidate hits (Enamine REAL, for the priority/ligandable targets)

Synthesizable starting points from `small-molecule:design`; `bind` = binding_confidence (relative, calibrate vs WS2), `opt` = optimization_score. Confirm top picks with a focused screen + docking.

**TSC2_GAP** (bindconf_max 0.645):
- `FC(F)c1c(Cl)ccnc1C=CCNC(=S)NN=C(Cc1ccccc1)c1ccccn1`  (bind 0.645, opt 0.3086170256137848)
- `O=C(O)C1Nc2c(NCc3cccc4ccsc34)ccc([N+](=O)[O-])c2C2C=CCC12`  (bind 0.644, opt 0.4248645007610321)
- `CC1CCc2c(sc3nc(SC(=O)c4cc(CNC(=O)OCC5c6ccccc6-c6ccccc65)ccc4F)n(Cc4ccco4)c(=O)c23)C1`  (bind 0.531, opt 0.419979453086853)
**WDR26** (bindconf_max 0.538):
- `C#Cc1c(C(C)(C)N)nnn1Cc1cccc(C(=O)NCc2ccco2)c1`  (bind 0.538, opt 0.11954256892204285)
- `O=C(O)C(Br)Sc1nccc2ccccc12`  (bind 0.468, opt 0.09445638954639435)
- `CC(N)c1nc2cc(C(=O)c3ccc(N=C=O)cc3F)ccc2[nH]1`  (bind 0.442, opt 0.15216514468193054)
**SCN2A** (bindconf_max 0.710):
- `Cc1ccc(C2(C(=O)C(C)c3ccc(Cl)cc3Cl)CCN(Cc3ccccc3)CC2)cc1`  (bind 0.71, opt 0.286283016204834)
- `COc1cccc(Cn2ccc3ccc(NC(=O)C4(c5ccccc5Cl)CCC4)cc32)c1`  (bind 0.567, opt 0.3268810212612152)
- `CC(C)(C)c1ccc(CN2CCN(C(c3ccccc3)c3ccc(C(=O)c4cc(B(O)O)ccc4F)cc3)CC2)cc1`  (bind 0.509, opt 0.4852340817451477)
**TSC1** (bindconf_max 0.688):
- `Cn1c(-c2ccc(C(=O)CCl)o2)nc2ccnc(Cl)c21`  (bind 0.688, opt 0.1120247021317482)
- `COC(=O)c1cc2c(C#N)ccc(Cl)c2[nH]1`  (bind 0.632, opt 0.12646202743053436)
- `Cc1cc(C(F)F)nc2sc(-c3nnn(C(Cl)(Cl)c4nc5ccccc5[nH]4)n3)c(N)c12`  (bind 0.62, opt 0.23995114862918854)
**SRCAP** (bindconf_max 0.671):
- `C#Cc1cncc(NC(=O)CC(=O)c2ccc(Br)cc2C(=O)CBr)c1`  (bind 0.671, opt 0.31155773997306824)
- `S=C(NCc1cccc(Br)c1)Nc1nc(=S)c2[nH]cnc2[nH]1`  (bind 0.557, opt 0.15564751625061035)
- `CC(C)(C)OC(=O)NCCC(=O)Cn1nnc(-c2ncccc2C=O)n1`  (bind 0.508, opt 0.14179649949073792)

## Receipts
`experiments/boltz_overnight.py` (runner), `experiments/boltz_overnight_brief.py` (this), `results/boltz_overnight_state.json` (all metrics), per-job CIFs under `results/boltz_overnight_runs/` (gitignored). Capability calibration: `results/boltz_tier{1,2,3}_characterization.md`.

