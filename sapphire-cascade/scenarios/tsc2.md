# Scenario: TSC2 / mTOR network — the #7 → #1 demo (with an abstain twist)

**Query:** *"Prioritize novel therapeutic targets to normalize TSC2-loss mTORC1 hyperactivation /
neuronal hyperexcitability for a tuberous-sclerosis CNS program (chronic paediatric + adult dosing)."*

**Headline result:** the moat's **#7 (RHEB)** becomes the **#1 novel actionable target**; the highest
raw-scored target (**DEPDC5**) is **abstained** (intractable modality); the everolimus **incumbent
(MTOR)** is set aside; and a Quiver Optopatch metabolic hit (**PPARD**) is **vetoed** on
carcinogenicity. Every gate/boost is backed by **real, cited EMET evidence**.

> Internal-moat scores are **synthetic/MOCK** (`internal_moat/tsc2.candidates.json`).
> External evidence is real — L3 corroboration chat `df322bc6`, L2 Drug Safety chat `793bf0e7`.

---

## L1 — Internal moat (synthetic): the ranked hypothesis

The moat ranks by functional EP-excitability effect. Big druggable kinases and Quiver's own Optopatch
metabolic hits score high; the small GTPase and scaffold nodes score low.

| # | Gene | s_internal | why the moat ranks it here |
|---|---|---|---|
| 1 | MTOR | 0.89 | master kinase — large excitability effect |
| 2 | AKT1 | 0.85 | strong kinase effect |
| 3 | PIK3CA | 0.82 | strong kinase effect |
| 4 | RPS6KB1 | 0.78 | S6K1 downstream effect |
| 5 | PKM | 0.74 | **Quiver Optopatch metabolic hit** (PKM2) |
| 6 | PPARD | 0.70 | **Quiver Optopatch metabolic hit** (PPAR-δ) |
| **7** | **RHEB** | **0.62** | **small GTPase downstream of TSC2 — subtle/indirect functional signature → under-detected** |
| 8 | PRKAA1 | 0.55 | AMPK — modulatory, weak signature |
| 9 | DEPDC5 | 0.50 | GATOR1 scaffold — weak direct effect |
| 10 | EEF2K | 0.45 | feedforward node — weak effect |

*Anchor TSC2 is excluded. MTOR stays in the list but is the **everolimus incumbent**, not a discovery.*

## L2 — Context/safety GATE (EMET Drug Safety workflow, cited)

| Gene | EMET class | Gate | Cited liability |
|---|---|---|---|
| **PPARD** | **CRITICAL** | **NO-GO** | GW501516 multi-species **carcinogenicity** → program termination, FDA/EMA holds — "do not progress systemically" |
| MTOR | WARNING | flag ×0.85 | Immunosuppression, vaccine blunting, growth impairment (everolimus 50,182 FAERS; PMID 31335226) |
| PIK3CA | WARNING | flag ×0.85 | Hyperglycaemia Grade 3–4 ~64% (alpelisib; PMID 34632383) |
| AKT1 | WARNING | flag ×0.85 | Metabolic triad; IPATential150 toxicity |
| RHEB, RPS6KB1, PRKAA1, DEPDC5, EEF2K, PKM | MONITOR | flag ×0.92 | No approved inhibitor — safety inferred |

## L3 — Predictivity BOOST (EMET corroboration, cited)

`corroboration = 0.45·genetics + 0.30·ppi_to_TSC2/MTOR + 0.25·screen`:

| Gene | genetics | PPI | screen | corrob. | note |
|---|---|---|---|---|---|
| DEPDC5 | **0.92** (FFEVF, OT 0.81) | 0.76 | 0.85 | 0.853 | best Mendelian epilepsy genetics |
| MTOR | 0.82 (FCD IIb) | 0.99 | 0.95 | 0.904 | incumbent |
| PIK3CA | 0.85 (PROS/MCAP) | 0.96 | 0.85 | 0.884 | |
| AKT1 | 0.76 (Proteus) | 0.99 | 0.80 | 0.839 | |
| **RHEB** | **0.55** (2nd FCD somatic cause) | **0.999** | 0.85 | **0.760** | *"underweighted in GWAS-centric databases"* |
| RPS6KB1 | 0.10 | 0.999 | 0.70 | 0.520 | |
| PRKAA1 | 0.10 | 0.978 | 0.70 | 0.513 | |
| EEF2K | 0.05 | 0.961 | 0.30 | 0.386 | |
| PKM | 0.05 | 0.30 | 0.40 | 0.213 | |

## Raw re-rank — `s_final = (s_internal + (1−s_internal)·corroboration) · gate_penalty`

| Raw | Gene | s_final | was | disposition |
|---|---|---|---|---|
| 1 | DEPDC5 | 0.853 | #9 | **ABSTAIN** (see below) |
| 2 | MTOR | 0.841 | #1 | **INCUMBENT** (everolimus) |
| **3** | **RHEB** | **0.836** | **#7** | **→ #1 novel actionable** |
| 4 | PIK3CA | 0.832 | #3 | flag (hyperglycaemia) |
| 5 | AKT1 | 0.829 | #2 | flag (hyperglycaemia) |
| 6 | RPS6KB1 | 0.823 | #4 | |
| 7 | PKM | 0.732 | #5 | |
| 8 | PRKAA1 | 0.719 | #8 | |
| 9 | EEF2K | 0.609 | #10 | |
| — | PPARD | removed | #6 | **CRITICAL no-go veto** |

## Uncertainty / abstention (exit gate) — where the judgment happens

This scenario's distinctive lesson: **the exit gate overrides the raw score.**

- **DEPDC5 (raw #1): ABSTAIN.** It has the strongest Mendelian epilepsy genetics in the panel — but it
  is a GATOR1 *brake* (a tumour-suppressor complex). Therapy means *restoring/enhancing* its function,
  for which **no validated small-molecule handle exists**. A confident "go" here would be a trap.
  **Proposed experiment:** a GATOR1-reactivation tool-compound / genetic screen before any program commitment.
- **MTOR (raw #2): INCUMBENT.** Everolimus is already approved for TSC — not a discovery. Set aside as
  standard-of-care; the question is what comes *next*.
- **RHEB (raw #3 → #1 actionable): HIGH confidence, with a caveat + experiment.** A selective RHEB
  inhibitor sits directly downstream of TSC2 and *"would phenocopy rapalogs for TSC efficacy"* — while
  being **node-specific**, plausibly avoiding pan-mTOR immunosuppression. A druggable handle exists
  (farnesyltransferase inhibitors). *Caveat:* no clinical-stage RHEB inhibitor, so safety is inferred
  (MONITOR). **Proposed experiment:** confirm RHEB-directed modulation normalizes the excitability
  phenotype in Quiver's oEP assay (the signature the moat under-resolved) and establish a node-specific
  safety margin vs. pan-mTOR inhibition.

**Net recommendation:** **RHEB — the moat's #7 — is the #1 novel actionable target.**

## Why this is "not Emit 2.0"

The candidate list came from the **internal moat**, not EMET. EMET only **vetoed** (PPARD
carcinogenicity), **flagged** (MTOR/PIK3CA/AKT1), and **boosted** (RHEB's somatic-FCD genetics that
GWAS databases under-weight). The decisive judgments — *abstain on the genetically-best-but-undruggable
node, set aside the incumbent, promote the under-detected node-specific target* — are made by the
cascade's gate and uncertainty layers, not by a generic tool-calling agent.
