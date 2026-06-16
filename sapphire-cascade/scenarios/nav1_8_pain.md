# Scenario: Nav1.8 / SCN10A neuropathic-pain network — the #7 → #1 demo

**Query:** *"Prioritize novel analgesic targets in the peripheral sensory-neuron / Nav1.8 (SCN10A)
network for a systemic neuropathic-pain program."*

**Headline result:** the moat's **#7 (SCN11A / Nav1.9)** is promoted to **#1**; the moat's **#1
(TRPV1)** falls to #4; two CRITICAL-safety targets (**CACNA2D1, NGF**) are **vetoed**. Every gate
and boost is backed by **real, cited EMET evidence**.

> Internal-moat scores are **synthetic/MOCK** (`internal_moat/nav1_8_pain.candidates.json`).
> All external evidence is real, pulled live from EMET — L3 corroboration chat `d070bf32`,
> L2 Drug Safety chat `eacfaebc`.

---

## L1 — Internal moat (synthetic): the ranked hypothesis

The moat ranks candidates by functional EP/CRISPR signal strength. Sharp-current ion channels score
high; the receptor/ligand/TF candidates and **the slow, non-inactivating Nav1.9 current** score low.

| # | Gene | s_internal | why the moat ranks it here |
|---|---|---|---|
| 1 | TRPV1 | 0.86 | large capsaicin/heat current |
| 2 | CACNA2D1 | 0.83 | strong Ca-current modulation |
| 3 | TRPA1 | 0.80 | strong irritant-evoked current |
| 4 | P2RX3 | 0.78 | strong ATP-gated current |
| 5 | NGF | 0.74 | CRISPR-KO collapses nociceptor program |
| 6 | KCNQ2 | 0.70 | M-current signature |
| **7** | **SCN11A (Nav1.9)** | **0.62** | **ultra-slow persistent current — hard to resolve in the optical-EP assay → under-detected** |
| 8 | NTRK1 (TrkA) | 0.55 | RTK — only indirect excitability signal |
| 9 | PRDM12 | 0.46 | developmental TF — no effector signature |

*Anchors SCN10A/Nav1.8 and SCN9A/Nav1.7 are excluded as already-prosecuted — the value is the
non-obvious promotion.*

## L2 — Context/safety GATE (EMET Drug Safety workflow, cited)

Subtractive only. EMET classified each target SAFE/MONITOR/WARNING/CRITICAL from FAERS + labels +
trials + literature:

| Gene | EMET class | Gate | Cited liability |
|---|---|---|---|
| CACNA2D1 | **CRITICAL** | **NO-GO** | Black-box respiratory depression; 4,569 fatal FAERS; abuse (PMID 28972983) |
| NGF | **CRITICAL** | **NO-GO** | RPOA / joint destruction; NDA rejected 2021 (PMID 37652258; NCT02697773) |
| TRPV1 | WARNING | flag ×0.85 | Class-wide hyperthermia; all systemic Ph2 failed (PMID 31926897) |
| NTRK1 | WARNING | flag ×0.85 | CIPA phenotype: anhidrosis, bone fragility (PMID 37869783) |
| KCNQ2 | WARNING | flag ×0.85 | Retigabine withdrawn 2017 — retinal/skin (PMID 25642319) |
| P2RX3 | MONITOR | flag ×0.92 | Dysgeusia 58–69%; FDA CRL 2023 (PMID 35248186) |
| TRPA1 | — | flag ×0.92 | Broad airway/vascular expression — selectivity |
| **SCN11A** | **SAFE** | **pass ×1.0** | Most favorable in panel; LoF tolerable, no clinical tox (PMID 26243570) |
| PRDM12 | — | pass | no drug; not a druggable effector |

## L3 — Predictivity BOOST (EMET corroboration, cited)

Additive only. `corroboration = 0.45·genetics + 0.30·ppi_to_SCN10A + 0.25·screen` (EMET values):

| Gene | genetics | PPI→SCN10A | screen | corroboration |
|---|---|---|---|---|
| NTRK1 | 0.94 (CIPA, OT) | 0.54 | 0.85 | 0.798 |
| NGF | 0.79 (HSAN-V) | 0.63 | 0.85 | 0.756 |
| TRPA1 | 0.65 (FEPS1) | 0.76 | 0.90 | 0.746 |
| **SCN11A** | **0.89 (FEPS3)** | **0.63** | 0.50 | **0.713** |
| PRDM12 | 0.88 (CIP) | 0.10 | 0.50 | 0.551 |
| CACNA2D1 | 0.05 | 0.71 | 0.80 | 0.436 |
| TRPV1 | 0.05 | 0.81 | 0.60 | 0.414 |
| P2RX3 | 0.05 | 0.66 | 0.60 | 0.370 |
| KCNQ2 | 0.05 | 0.40 | 0.40 | 0.243 |

## Final re-rank — `s_final = (s_internal + (1−s_internal)·corroboration) · gate_penalty`

| Final | Gene | s_final | was | what moved it |
|---|---|---|---|---|
| **1** | **SCN11A** | **0.891** | **#7** | SAFE (no penalty) + strong Mendelian genetics; nothing above survives unpenalized |
| 2 | TRPA1 | 0.873 | #3 | strong corroboration, mild selectivity flag |
| 3 | P2RX3 | 0.793 | #4 | high internal, MONITOR flag |
| 4 | TRPV1 | 0.780 | #1 | demoted by hyperthermia flag + weak genetics |
| 5 | NTRK1 | 0.773 | #8 | strongest genetics, capped by WARNING (CIPA) flag |
| 6 | PRDM12 | 0.758 | #9 | genetics boost — but ABSTAIN (not druggable) |
| 7 | KCNQ2 | 0.657 | #6 | weak genetics + WARNING flag |
| — | CACNA2D1, NGF | removed | #2, #5 | **CRITICAL no-go vetoes** |

## Uncertainty / abstention (exit gate)

- **SCN11A (#1): HIGH confidence, with a flagged caveat + proposed experiment.** Genetics +
  safety + PPI agree. *But* SAFE is provisional (no clinical-stage Nav1.9 inhibitor exists) and
  selective blockade needs >100× sparing of cardiac Nav1.5. **Proposed experiment:** resolve Nav1.9's
  persistent-current contribution in Quiver's oEP assay (the very signal the moat under-detected) and
  establish Nav1.5 selectivity early — closing the active-learning loop on the moat's own blind spot.
- **PRDM12 (#6): ABSTAIN.** Strong genetics, but a developmental regulator, not a druggable adult-pain
  effector. **Proposed:** pursue as a nociceptor cell-reprogramming factor, not a small-molecule target.

## Why this is "not Emit 2.0"

The hypothesis came from the **internal moat**, not from EMET. EMET (the external "world") only
**gated** (vetoed CACNA2D1/NGF, demoted TRPV1) and **boosted** (genetics promoted SCN11A) — it never
authored the candidate list. The winning insight — *a target the functional assay under-resolved,
rescued by human genetics and a clean safety profile* — is exactly James' #7→#1, produced structurally.
