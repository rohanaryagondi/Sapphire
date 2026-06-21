# Open Questions

Questions raised in the 5/28 sprint meeting that this exploration should answer. Each question maps to a phase of the plan.

## Status summary (updated 2026-05-28) — see [`FINDINGS.md`](FINDINGS.md) for the synthesis

| Q | Question (short) | Status | Answer |
|---|---|---|---|
| Q1 | DTI on a known pair (Jernabix→Nav1.8)? | **answered** | ❌ fails — true binder doesn't beat random small molecules |
| Q2 | DTI generalize to ion-channel/CNS pairs? | **answered** | ⚠️ coarse ranking only (PEER Spearman 0.43); no single-target triage |
| Q3 | False-positive rate / negative controls? | **answered** | high — decoys score ≈ binders for a single target |
| Q4 | Do specialists beat MAMMAL on DTI? | **answered** | MAMMAL's own DTI is ~9% better than the mean — weak regardless |
| Q5 | MAMMAL vs Proton (CNS)? | open | not run (Proton not yet evaluated) |
| Q6 | Hit-list expansion useful? | **answered** | use Morgan fingerprints for expansion; MAMMAL's value is the de-risk step |
| Q7 | TSC genes → known TSC drugs surface? | **answered** | ❌ rapamycin/everolimus don't rank above decoys vs mTOR off-the-shelf |
| Q8 | CRISPR-N druggable candidates? | partial | protein embeddings cluster genes by family (NN 0.92); not applied to real panel |
| Q9 | MAMMAL as Sapphire latent layer? | partial | protein embeddings sensible; benchmark vs ESM before committing |
| Q10 | Generation head for ASO design? | deferred | no public antibody/ASO checkpoint to test |
| Q11 | How fast target/screen → molecules? | **answered** | de-risk funnel ~0.16 s/cpd; 150 candidates < 1 min |
| Q12 | Hallucination / false confidence? | **answered** | DTI confidently wrong (flat ~mean); ClinTox confidently over-predicts toxicity |
| Q13 | What does Margalise's interface do? | open | not yet coordinated |
| Q14 | **Should we fine-tune on Quiver data?** | **YES (for Quiver targets only)** | Pipeline piloted on AWS (~$0.80): trains cleanly (BBBP val acc 0.88; PGK2 rc0). Key: fine-tuning can't beat IBM on a *public* task (same base+data=same ceiling); it only wins on **Quiver-specific targets** where off-the-shelf MAMMAL ≈ AUROC 0.5. → need Quiver data. `results/aws_finetune_pilot.md` |

## Calibration questions (Phase 1)

### Q1. Does MAMMAL actually work on a known drug-target pair from our domain?
**Test**: Jernabix → Nav1.8 binding prediction. Feed SMILES + protein sequence. Compare predicted affinity to known experimental value.
**Owner**: Phase 1 work
**Status**: open

### Q2. Does MAMMAL's drug-target binding generalize to other ion-channel or CNS-relevant pairs?
**Test**: 5–10 more known drug-target pairs from Quiver's prior work
**Owner**: Phase 1 work
**Status**: open

### Q3. What is the false positive rate?
**Test**: Negative controls — feed unrelated drug-protein pairs, confirm low predicted affinity. Characterize the gap between true binders and random pairs.
**Owner**: Phase 1 work
**Status**: open

## Comparative questions (Phase 3)

### Q4. Do specialized drug-target binding models beat MAMMAL on our data?
**Test**: Run a specialized DTI model (DeepPurpose, MolTrans, or similar) on the Phase 1 calibration set. Compare.
**Owner**: Phase 1/Phase 3 work
**Status**: open
**Source**: Senior voice in meeting — "if your task is drug target binding prediction, it's possible a specialized model is gonna perform better"

### Q5. How does MAMMAL compare to Proton (CNS-specific, Zitnik lab)?
**Test**: Run both on the TSC top-20 use case. Compare ranked candidates.
**Owner**: Phase 3 work
**Status**: open

## Usefulness questions (Phase 2)

### Q6. Can MAMMAL meaningfully expand a hit list from a real screen?
**Test**: Take Quiver's top 50, expand via SMILES similarity to 200–500, filter by BBB + ClinTox, end with usable shortlist.
**Owner**: Phase 2a work
**Status**: open

### Q7. Does MAMMAL surface known TSC drugs when given TSC gene targets?
**Test**: TSC top-20 nominated genes → MAMMAL ranks candidates. Check whether rapamycin / everolimus / MTOR-pathway drugs appear in top 100.
**Owner**: Phase 2b work
**Status**: open

### Q8. Can MAMMAL nominate druggable candidates for CRISPR-N disease-target genes?
**Test**: For disease-target genes in the CRISPR-N 1400, ask MAMMAL for small-molecule inhibitor candidates.
**Owner**: Phase 2c work
**Status**: open

## Strategic questions (Phase 4 + beyond)

### Q9. Is MAMMAL the right shared latent space for Sapphire, or just enrichment?
**Test**: Phase 4 — prototype MAMMAL embeddings as Caitlin's KG node properties; build hybrid query; demo it.
**Owner**: Phase 4 work
**Status**: open

### Q10. Can we leverage MAMMAL's generation head for ASO design?
**Test**: Out of scope for current exploration; flagged for future work. The Ab Infilling head generates antibody CDR sequences — conceptually similar to ASO sequence design.
**Owner**: future work
**Status**: deferred

### Q11. How fast can MAMMAL get us from a target / screen result to ranked candidate molecules?
**Test**: Time-to-result on Phase 2a end-to-end. The senior voice's "how fast can we go" question.
**Owner**: Phase 2 work
**Status**: open

### Q12. What's the hallucination / false confidence rate?
**Test**: Track confidence calibration across all phases. Are wrong predictions also low-confidence, or does MAMMAL confidently make things up?
**Owner**: cross-cutting
**Status**: open
**Source**: Meeting discussion of biomedical foundation model hallucination problem

## Operational questions

### Q13. What does Margalise's existing MAMMAL interface do?
**Test**: Coordinate with Matt + Margalise before building anything new. Document what exists.
**Owner**: Phase 0 work
**Status**: open

### Q14. Should we fine-tune MAMMAL on Quiver data?
**Test**: Answered via IBM's published per-target heads (`wdr91_asms`, `pgk2_del_cdd`) as an existence proof. They are **functional generative binder classifiers** (prompt with `<WDR91_ASMS>` task token, read P(active); validated on BBBP=0.996). `wdr91_asms` ranks WDR91 actives over decoys: **top-5% enrichment 5.25×, AUROC 0.63** — modest but real. See `../results/phase3_wdr91_finetune.md`.
**Owner**: open (decision pending)
**Status**: **YES — but only for targets IBM has no head for (i.e. Quiver targets).** Two-part answer:
(a) *Existence proof* (Phase 3): IBM's `wdr91_asms`/`pgk2_del_cdd` generative classifiers give real
target→binder triage (PGK2 vs PGK1 homolog AUROC 0.97); use the generative `binder_prob` readout, not the
vestigial scalar head.
(b) *Pipeline pilot* (AWS, 2026-06-01, `results/aws_finetune_pilot.md`): we fine-tuned `base_458m`
ourselves on a g4dn T4 for **~$0.80** — BBBP **val acc 0.88**, PGK2 rc0 in 19 min. The pipeline works.
(Held-out eval invalid — run on a bare instance, must re-run on a GPU with `process_model_output`.)
**The decisive insight:** fine-tuning on *public* data can never beat IBM's own published head (same base
+ same data = same ceiling — our BBBP 0.88 ≈ confirmation, not a win). The win exists ONLY for **Quiver-
specific targets** (Nav1.8, UBE3A/DUP15Q, mTOR/TSC, DFP compounds, CRISPR-N genes) where the best
available MAMMAL is the base model at ≈ AUROC 0.5 and a Quiver-trained head is the only one in existence.
**Next step:** fine-tune on a Quiver target with the most labelled hit data (binary hit/non-hit, SMILES +
label), evaluate by enrichment factor on a held-out **scaffold** split. Triage/enrichment tool, not a
precision oracle (sharp in-distribution, weak on novel scaffolds, no graded potency).
