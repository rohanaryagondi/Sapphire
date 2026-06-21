# 5/28 Sprint Meeting Context

This project was spun up out of the **Weekly Sprint Check-in on 5/28/2026** ([Notion link](https://www.notion.so/58bfd6ca57bc4fdd84f43c83a9c01599)). David M. shared the IBM MAMMAL paper that week. The team discussed it and decided to play around with the model. This doc captures what was actually decided.

## Decisions made

- **Instantiate MAMMAL and play with it** — added to the MVP roadmap discussion at 5pm same day
- **Matt is the lead** for the exploration. Coordinate with David (lab context) and Margalise (already has a MAMMAL interface built — sent excited late-night message about it)
- **Also try Proton** (Zitnik lab, CNS-specific) as a second model to evaluate in parallel
- **Next week's scoping meeting** between James, Caitlin, and Mahdi to discuss MAMMAL + Angelini gene application

## Use cases proposed in the meeting

In rough priority order from the meeting discussion:

1. **Prediction enrichment / re-ranking** of Quiver's existing compound predictions — the most direct near-term value
2. **Gene-target → small-molecule traversal** — "I have a nominated drug target from our Atlas program, give me a list of small-molecule candidates"
3. **Hit-list expansion via SMILES similarity** — "Take 10 hits, expand by SMILES to find 100 untested compounds with similar structure, de-risk by BBB + toxicity, pick top 5"
4. **CRISPR-N 1400 genes systematic interrogation** — Mahdi's idea: we have 1400 genes but no functional fingerprints for all of them; cluster by gene functional state, for disease-target genes nominate small-molecule inhibitors or ASOs
5. **Disease-rescue ranking** for TSC — top 20 TSC genes → MAMMAL nominates rescue candidates → de-risk → narrow to top 5
6. **Antibody/ASO generation** — repurpose MAMMAL's antibody CDR generation head for ASO design (longer-term)

## Concerns raised in the meeting

These all need to be addressed by the exploration work:

- **Not CNS-trained**: MAMMAL wasn't trained specifically on neuron/CNS data. Probably benefits from fine-tuning on our data — but fine-tuning is real work.
- **"State-of-the-art is shit being state-of-the-art within shit"** (senior voice, paraphrased): paper benchmark wins don't mean the model is actually useful. Empirical grounding on our data is required.
- **Specialized models may beat the multimodal generalist** on specific tasks (e.g., drug-target binding). Has to be tested head-to-head, not assumed.
- **Hallucination is still a real problem** with biomedical foundation models (IBM YouTube reference in the meeting). Need to characterize false positive rate.
- **Not plug-and-play** — the paper's benchmark numbers required fine-tuning the model. Off-the-shelf will likely underperform what the paper claims.
- **Trace modality not in MAMMAL** — can't feed Quiver's electrophysiology traces. Trace stays V1-T's job.

## Strategic positioning (also from the meeting)

The room's framing of MAMMAL's role in Quiver:

> *"The team's platform value is in generating insights that point to targets others can't see; commodity tools like MAMMAL then enrich those insights."*

> *"The value will come because our insights of our platform point us to something that people can't... haven't been able to see before, and that insight then we can leverage this total set of knowledge to enrich it even further."*

MAMMAL is a tool. Initial posture is **downstream commodity enrichment**, not core infrastructure. The moat is the functional trace data and V1-T's embeddings on it.

That posture could shift if Phase 4 (Sapphire integration prototype) works well — but only with evidence.

## Two questions the work should answer (senior voice)

1. *"How much better does our measurement improve the enrichment of the insight?"*
2. *"With that insight, how do we quickly get to molecules? How fast can we go?"*

These are the success measures that matter to the room — not paper benchmark scores.

## Specific test case called out by name

**Jernabix → Nav1.8** — known drug-target pair. Feed SMILES + protein sequence into MAMMAL, check whether the predicted binding affinity matches what we know experimentally. This was explicitly proposed in the meeting as a calibration test.

## Resources

- **Margalise already has some interface built** — sent late-night message about it. Check what exists before building.
- **David has done related lab work** — Matt should consult.
- **MAMMAL weights**: HuggingFace `ibm/biomed.omics.bl.sm.ma-ted-458m`. Matt estimated "hours" to instantiate.

## Reporting cadence

Matt to report back at next two weekly check-ins:
- **6/4** (Week 1): Phase 1 calibration results
- **6/11** (Week 2): Phase 2 use case results
