# Boltz on the antipodal-rescue druggable partner targets — validate-then-deploy + selectivity

*Generated 2026-06-17 19:52Z · est. spend ~$25.75 · 18 jobs complete*

## TL;DR

The deck's rescue strategy needs **inhibitors of the druggable partner** (LSD1, USP7, DOT1L, WDR5, HDAC, BRD4). This run (1) **validates** whether Boltz can be trusted to find/rank inhibitors on each partner — using real ChEMBL actives + potencies — and (2) **deploys** it on the trusted targets to produce CNS-filtered candidate molecules (de-novo + repurposing). It also tests whether Boltz's ion-channel selectivity failure (Tier-3) extends to soluble enzymes.

**Bottom line:** Boltz **triages binders well on all 6 partner enzymes (AUROC 0.79–0.99)** — the opposite of its ion-channel failure — and **ranks potency** on several (WDR5 0.92, LSD1 0.72). **Selectivity also works here** (3/4 selective tool compounds put the true isoform/target top — unlike Nav paralogs), because these enzymes have *distinct* pockets. Net: Boltz is a usable hit-finder + triage layer for the inhibit-the-partner rescue strategy, strongest on WDR5/BRD4.

## P1 — Per-target trust scorecard (can we believe Boltz here?)

Enrichment AUROC = active-vs-decoy triage (ChEMBL actives vs measured inactives). Potency Spearman = correlation of Boltz `optimization_score` with measured pIC50 *within actives* — **the never-before-tested lead-optimization question.**

| partner | class | enrich AUROC (opt) | AUROC (bind) | potency Spearman | n act/dec | verdict |
|---|---|---|---|---|---|---|
| **WDR5** | WD40 PPI | 0.9935 | 0.9542 | 0.924 | 17/18 | TRUSTED — triage + potency-ranking |
| **KDM1A** | FAD amine oxidase (LSD1) | 0.8549 | 0.537 | 0.7193 | 18/18 | TRUSTED — triage + potency-ranking |
| **BRD4** | bromodomain (BD1) | 0.9739 | 0.9477 | 0.4877 | 17/18 | TRUSTED — triage + potency-ranking |
| **DOT1L** | methyltransferase | 0.7941 | 0.7092 | 0.5539 | 17/18 | TRUSTED — triage + potency-ranking |
| **HDAC1** | Zn hydrolase | 0.8858 | 0.716 | 0.4551 | 18/18 | TRUSTED — triage + potency-ranking |
| **USP7** | DUB | 0.9549 | 0.5451 | 0.3176 | 16/18 | triage-only (enriches binders; potency-ranking weak) |

**Headline:** potency-ranking works on **WDR5, KDM1A, BRD4, DOT1L, HDAC1** (triage + rank by potency); triage-only on **USP7**. Where Spearman is low, Boltz separates binders from non-binders but cannot rank analog potency — use it as a screen, not a lead-opt scorer.

## P4 — Selectivity on soluble enzymes (does the ion-channel failure generalize?)


**LSD1 (vs MAO-A/B — CNS-critical off-targets)** — `optimization_score` per compound across targets (want the true target highest):

| compound | KDM1A | MAOA | MAOB | Boltz top | true |
|---|---|---|---|---|---|
| ORY-1001 | 0.237 | 0.000 | 0.080 | KDM1A ✓ | KDM1A |
| tranylcypromine | 0.069 | 0.218 | 0.100 | MAOA ✗ | KDM1A |

**HDAC isoform** — `optimization_score` per compound across targets (want the true target highest):

| compound | HDAC1 | HDAC6 | HDAC8 | Boltz top | true |
|---|---|---|---|---|---|
| Entinostat | 0.346 | 0.078 | 0.204 | HDAC1 ✓ | HDAC1 |
| Tubastatin-A | 0.247 | 0.533 | 0.224 | HDAC6 ✓ | HDAC6 |

## P2 — Deployed hits on the trusted targets (CNS-filtered)

Deployed on: **WDR5, KDM1A, BRD4**. Two hit sources, each row carries free Boltz ADME (solubility/permeability/logD); cross-check with MapLight BBBP/hERG before committing.


### WDR5 — *COMPASS scaffold; SETD2/KMT2A H3K4 methylation rebalancing*
**De-novo (Enamine REAL) top candidates:**
- `COC(=O)c1ccc2cc(Cl)cc(C3=CC(C(=O)O)CC3NC(=O)OCC3c4ccccc4-c4ccccc43)c2n1` (opt 0.43, bind 0.495)
- `CN(C)CCOc1cc(C(=O)c2cc(B(O)O)c(Cl)cc2Cl)ccn1` (opt 0.361, bind 0.414)
- `Cc1ncc(-c2ccc(Cl)cc2)c(NC(=O)CN(C(=O)OCC2c3ccccc3-c3ccccc32)C2CCN(C(=O)OC(C)(C)C)CC2)n1` (opt 0.319, bind 0.254)
- `FC(F)(F)c1ccc(-c2noc(CCc3c[nH]c4cc(Cl)ccc34)n2)c(I)n1` (opt 0.273, bind 0.195)
- `CC(Sc1ccc(-c2n[nH]c(-c3cc4c5c(ccc4[nH]3)OC(F)(F)O5)n2)cc1)C(=O)O` (opt 0.27, bind 0.342)
**CNS-drug repurposing — top predicted binders:**
- DARIFENACIN (opt 0.349; perm 0.8846455812454224, logD 2.6505625247955322)
- ZIPRASIDONE (opt 0.315; perm 0.7971293330192566, logD 4.084108352661133)
- TERTATOLOL (opt 0.291; perm 1.2820549011230469, logD 0.9470179080963135)
- MISOPROSTOL (opt 0.241; perm 1.3716659545898438, logD 2.923532009124756)
- GLICLAZIDE (opt 0.232; perm 0.6980740427970886, logD -1.3749287128448486)
- FLECAINIDE (opt 0.231; perm 0.7932689189910889, logD 1.664899230003357)
- TOLAZAMIDE (opt 0.212; perm 0.7329143285751343, logD -1.3728691339492798)
- MOXIFLOXACIN (opt 0.212; perm 0.678199291229248, logD -0.3091105818748474)

### KDM1A — *LSD1 inhibition raises H3K4me → compensates KMT2D loss (Kabuki) — flagship pair*
**De-novo (Enamine REAL) top candidates:**
- `CC(C)(C)OC(=O)NC1CCCc2c(C(=O)Nc3nc(-c4c[nH]c5ncccc45)cs3)n[nH]c21` (opt 0.377, bind 0.5)
- `Nc1ncn(Cc2cccc(C(=O)OCc3c(F)cccc3I)c2)n1` (opt 0.372, bind 0.306)
- `CC1(C)C(C=C(Cl)C(F)(F)F)C1C(=O)OCC(F)(F)C(F)(F)CO` (opt 0.349, bind 0.243)
- `COC(=O)c1c(C)nc(C)c(-c2nc(-c3cc(F)c(S(=O)(=O)Cl)c(F)c3)n[nH]2)c1-c1ccccc1[N+](=O)[O-]` (opt 0.297, bind 0.096)
- `CCn1ncc2ccc(-c3nc(-c4c(N)ncc5c4CCN(C(=O)OC(C)(C)C)C5)n[nH]3)cc21` (opt 0.294, bind 0.202)
**CNS-drug repurposing — top predicted binders:**
- TADALAFIL (opt 0.356; perm 0.9639381170272827, logD 2.498932361602783)
- ZIPRASIDONE (opt 0.344; perm 0.7971293330192566, logD 4.084108352661133)
- DARIFENACIN (opt 0.319; perm 0.8846455216407776, logD 2.6505630016326904)
- BIPERIDEN (opt 0.309; perm 1.6100521087646484, logD 1.4425580501556396)
- LINEZOLID (opt 0.303; perm 1.2478440999984741, logD 0.9695603847503662)
- RIVAROXABAN (opt 0.301; perm 0.8602766990661621, logD 2.6175801753997803)
- NORFLOXACIN (opt 0.301; perm 0.6157406568527222, logD -0.966018557548523)
- PERPHENAZINE (opt 0.3; perm 0.4933941066265106, logD 2.1056647300720215)

### BRD4 — *BET reader; transcriptional-elongation node for chromatin disease genes*
**De-novo (Enamine REAL) top candidates:**
- `COC(=O)c1cc(Cl)nc(Cn2nnnc2-c2c(NC(=O)CCl)oc(-c3ccco3)c2-c2ccco2)c1` (opt 0.368, bind 0.46)
- `COC(=O)c1cc2cccc(C3NCCc4c3ccc(Br)c4OC)c2[nH]1` (opt 0.332, bind 0.49)
- `COc1ccccc1NS(=O)(=O)c1ccc2oc(C(CCSC)NC3=NS(=O)(=O)c4ccccc43)nc2c1` (opt 0.297, bind 0.165)
- `CCCCN(CCCC)c1ccc(C#Cc2cc(Cl)cc3cccnc23)cc1` (opt 0.29, bind 0.373)
- `Cc1ccc(F)c(-n2nc(C(=O)Sc3nc(C)c(C)n3CC(C)C)c3c2CCC3)c1` (opt 0.288, bind 0.211)
**CNS-drug repurposing — top predicted binders:**
- ESTRONE (opt 0.336; perm 1.7449536323547363, logD 4.047327518463135)
- VORICONAZOLE (opt 0.319; perm 1.5293684005737305, logD 2.3194773197174072)
- TADALAFIL (opt 0.313; perm 0.9639382362365723, logD 2.4989330768585205)
- NEVIRAPINE (opt 0.296; perm 1.4556396007537842, logD 2.0595338344573975)
- COLCHICINE (opt 0.282; perm 1.4007668495178223, logD 2.9792096614837646)
- PRUCALOPRIDE (opt 0.282; perm 0.7956563234329224, logD 0.015471603721380234)
- APOMORPHINE (opt 0.278; perm 0.966596245765686, logD 1.507590651512146)
- ATOMOXETINE (opt 0.276; perm 1.2231290340423584, logD 1.7392061948776245)

## How to read / caveats

- `optimization_score` = Boltz binding-strength proxy (the hosted-API affinity readout). Enrichment AUROC and potency Spearman calibrate it **per target** — trust varies by pocket class.
- Tier-1–3: Boltz is **not** an absolute affinity or selectivity oracle (ranked Nav1.8-selective suzetrigine LAST of 9 paralogs). P4 tests whether soluble enzymes behave better.
- Repurposing/de-novo hits are **structure-scored hypotheses**, not validated binders — confirm top picks experimentally; CNS-filter via MapLight + the ADME columns here.
- Domains cropped to the catalytic site where the protein is large; pocket anchored with 2 known potent reference ligands (excluded from scored set to avoid potency-correlation leakage).

## Receipts
`experiments/boltz_partner.py` (runner), `experiments/boltz_partner_brief.py` (this), `results/boltz_partner_state.json` (metrics), `data/partner_chembl_cache.json` (ChEMBL sets), per-job CIFs under `results/boltz_partner_runs/` (gitignored). Capability calibration: `results/boltz_tier{1,2,3}_characterization.md`, prior overnight: `RohanOnly/boltz_overnight_briefing_2026-06-18.md`.
