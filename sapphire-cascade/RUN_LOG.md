# Sapphire Cascade — Run Log

Two end-to-end cascade runs, executed live on **2026-06-16**. Each agent drove **EMET (BenchSci)**
through the shared Playwright session per [`emet_protocol.md`](emet_protocol.md): a new tab, mode set
to **Thorough** (or a Drug Safety **workflow**, which fixes its own depth), a query in **public
identifiers only**, then read + cite + close the tab — base tab 0 always left open.

Internal-moat (L1) scores are **synthetic/MOCK**. All L2/L3 evidence is **real and cited**, with the
EMET chat URLs recorded as anchors. The full per-target evidence + arithmetic lives in
`internal_moat/*.candidates.json` and `scenarios/*.md`.

---

## EMET sessions used (evidence anchors)

| Run | Layer | EMET mode / workflow | Chat |
|---|---|---|---|
| Nav1.8 pain | L3 corroboration | Thorough (GWAS, STRING, PubMed, Open Targets, Europe PMC; 43 sources) | `d070bf32` |
| Nav1.8 pain | L2 context/safety | **Drug Safety** workflow (FAERS, DailyMed, trials, literature; 13-step) | `eacfaebc` |
| TSC2 | L3 corroboration | Thorough (6-step; STRING, Open Targets, PubMed, Europe PMC; 30 sources) | `df322bc6` |
| TSC2 | L2 context/safety | **Drug Safety** workflow (8-step; FAERS 50k+ everolimus reports) | `793bf0e7` |

> Base URL: `https://app.summit-prod.benchsci.com/chat/<chat-id>`. No proprietary EP/CRISPR data was
> ever entered into EMET — only gene symbols and disease terms.

---

## RUN 1 — Nav1.8 / SCN10A neuropathic-pain network

**Query:** *Prioritize novel analgesic targets in the Nav1.8 (SCN10A) network for a systemic
neuropathic-pain program.* Full walkthrough: [`scenarios/nav1_8_pain.md`](scenarios/nav1_8_pain.md).

```
EXECUTION PLAN — nav1_8_pain
INITIAL (L1 internal moat, MOCK):
  #1 TRPV1   0.86   [MODEX,ENS,PCA]
  #2 CACNA2D1 0.83  [MODEX,PCA]
  #3 TRPA1   0.80   [MODEX,ENS,PCA]
  #4 P2RX3   0.78   [MODEX,ENS]
  #5 NGF     0.74   [LINCS,ENS]
  #6 KCNQ2   0.70   [MODEX,ENS]
  #7 SCN11A  0.62   [MODEX,PLATINUM]  <- target to watch (persistent current under-resolved)
  #8 NTRK1   0.55   [LINCS,PCA]
  #9 PRDM12  0.46   [LINCS]

GATE (L2 — EMET Drug Safety, chat eacfaebc):
  CACNA2D1 : NO-GO   CRITICAL — black-box respiratory depression; 4,569 fatal FAERS [PMID 28972983]
  NGF      : NO-GO   CRITICAL — RPOA/joint destruction; NDA rejected 2021 [PMID 37652258; NCT02697773]
  TRPV1    : flag    WARNING  — class-wide hyperthermia; all systemic Ph2 failed [PMID 31926897]
  NTRK1    : flag    WARNING  — CIPA phenotype (anhidrosis, bone fragility) [PMID 37869783]
  KCNQ2    : flag    WARNING  — retigabine withdrawn 2017 (retinal/skin) [PMID 25642319]
  P2RX3    : flag    MONITOR  — dysgeusia 58-69%; FDA CRL 2023 [PMID 35248186]
  SCN11A   : pass    SAFE     — most favorable profile; LoF tolerable [PMID 26243570]

BOOST (L3 — EMET corroboration, chat d070bf32):
  SCN11A : genetics 0.89 (FEPS3 Mendelian) + PPI 0.63 to SCN10A + screen 0.50 -> corrob 0.713
  (full table in scenarios/nav1_8_pain.md)

FINAL (re-ranked, survivors):
  #1 SCN11A 0.891   (was #7)  <- PROMOTED: SAFE + strong Mendelian genetics; moat under-resolved its
                                  persistent current (EMET independently flags its "ultra-slow kinetics")
  #2 TRPA1  0.873   (was #3)
  #3 P2RX3  0.793   (was #4)
  #4 TRPV1  0.780   (was #1)  <- demoted by hyperthermia flag
  #5 NTRK1  0.773   (was #8)
  #6 PRDM12 0.758   (was #9)  -> ABSTAIN (developmental TF, not a druggable effector)
  #7 KCNQ2  0.657   (was #6)
  removed: CACNA2D1, NGF (CRITICAL vetoes)

UNCERTAINTY / ABSTENTION:
  SCN11A (#1): HIGH, caveated. SAFE is provisional (no clinical-stage Nav1.9 inhibitor); needs >100x
    Nav1.5 cardiac selectivity. PROPOSE: resolve Nav1.9 persistent-current contribution in Quiver's oEP
    assay (the signal the moat under-detected) + establish cardiac selectivity early.
  PRDM12 (#6): ABSTAIN. Strong genetics, undruggable developmental regulator. PROPOSE: pursue as a
    nociceptor cell-reprogramming factor, not a small-molecule target.
```

**Result:** the moat's #7 (**SCN11A / Nav1.9**) → **#1**, on real cited human genetics + the cleanest
safety profile in the panel; the moat's #1 (TRPV1) → #4; two CRITICAL targets vetoed. James' #7→#1,
produced structurally.

---

## RUN 2 — TSC2 / mTOR network

**Query:** *Prioritize novel targets to normalize TSC2-loss mTORC1 hyperactivation for a tuberous-
sclerosis CNS program.* Full walkthrough: [`scenarios/tsc2.md`](scenarios/tsc2.md).

```
EXECUTION PLAN — tsc2
INITIAL (L1 internal moat, MOCK):
  #1 MTOR   0.89   #2 AKT1 0.85   #3 PIK3CA 0.82   #4 RPS6KB1 0.78   #5 PKM 0.74
  #6 PPARD  0.70   #7 RHEB 0.62 <- target to watch   #8 PRKAA1 0.55   #9 DEPDC5 0.50   #10 EEF2K 0.45
  (PKM2 and PPARD are Quiver Optopatch metabolic hits; TSC2 anchor excluded)

GATE (L2 — EMET Drug Safety, chat 793bf0e7):
  PPARD  : NO-GO   CRITICAL — GW501516 multi-species CARCINOGENICITY; FDA/EMA holds ("do not progress")
  MTOR   : flag    WARNING  — immunosuppression/growth impairment; everolimus 50,182 FAERS [PMID 31335226]
  PIK3CA : flag    WARNING  — hyperglycaemia Grade 3-4 ~64% [PMID 34632383]
  AKT1   : flag    WARNING  — metabolic toxicity triad
  RHEB/RPS6KB1/PRKAA1/DEPDC5/EEF2K/PKM : flag_mild  MONITOR — no approved inhibitor (safety inferred)

BOOST (L3 — EMET corroboration, chat df322bc6):
  RHEB   : 2nd-most-common FCD somatic cause + STRING 0.999 to TSC2 + screen 0.85 -> corrob 0.760
           (genetics "systematically underweighted in GWAS-centric databases" — exactly what the moat misses)
  DEPDC5 : highest Mendelian epilepsy genetics in set (OT 0.81 / genetic 0.92) -> corrob 0.853

FINAL (raw re-rank, survivors):
  raw#1 DEPDC5 0.853   raw#2 MTOR 0.841   raw#3 RHEB 0.836 (was #7)   raw#4 PIK3CA 0.832
  raw#5 AKT1 0.829     raw#6 RPS6KB1 0.823   raw#7 PKM 0.732   raw#8 PRKAA1 0.719   raw#9 EEF2K 0.609
  removed: PPARD (CRITICAL veto)

UNCERTAINTY / ABSTENTION (overrides raw score):
  DEPDC5 (raw#1): ABSTAIN — best genetics but a GATOR1 brake; no validated handle to restore function.
    PROPOSE: GATOR1-reactivation tool-compound/genetic screen.
  MTOR (raw#2): INCUMBENT — everolimus already approved for TSC; not a discovery.
  RHEB (raw#3 -> #1 ACTIONABLE): node-specific; "would phenocopy rapalogs for TSC efficacy" potentially
    without pan-mTOR immunosuppression; druggable (farnesyltransferase inhibitors). PROPOSE: confirm RHEB
    modulation normalizes excitability in Quiver's oEP assay + establish node-specific safety margin.

NET RECOMMENDATION: RHEB — the moat's #7 — is the #1 NOVEL ACTIONABLE target.
```

**Result:** the moat's #7 (**RHEB**) → **#1 actionable**, after the exit gate abstains on the
genetically-best-but-undruggable DEPDC5 and sets aside the everolimus incumbent; a Quiver Optopatch hit
(PPARD) is vetoed on carcinogenicity. Same #7→#1 shape, with the uncertainty layer doing decisive work.

---

## What both runs demonstrate

1. **Internal-first.** The hypothesis (candidate list) is the moat's; EMET never authored it.
2. **Gate ≠ boost.** Context only vetoes/demotes (CRITICAL → no-go); predictivity only adds
   corroboration. Separate channels, separate math.
3. **#7 → #1 is structural,** not luck: a target the functional assay under-resolves, rescued by
   independent human genetics + a clean safety read.
4. **Abstention is discovery.** Both runs abstain on a genetically-strong but undruggable node and
   *propose the experiment* — and the pain run's proposed experiment points straight back at the moat's
   own blind spot, closing the active-learning loop.
