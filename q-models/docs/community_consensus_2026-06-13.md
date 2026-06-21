# Community / literature consensus vs our empirical findings (2026-06-13)

Cross-check: what the published 2025 benchmarks say is "best per track" vs what we found on
Quiver's own substrate. **Headline: the literature largely validates our empirical winners** —
and surfaces a few untested candidates worth noting.

| Track | Our empirical pick | Literature consensus | Verdict |
|---|---|---|---|
| 1 Family / embeddings | **ESM-2-650M ≈ ESM-C 600M** | "**ESM-C 600M with mean embeddings = optimal balance**"; medium models (650M/600M) within a few % of 15B/6B — scale barely helps | ✅ **matches exactly** (our 650M=3B=15B finding) |
| 2/3 DTI / co-folding | **Boltz-2** | Boltz-2 is the clear SOTA — "first to approach **FEP accuracy**," beat every CASP16 entry, **discriminates binders from decoys** (MF-PCBA enrichment), beats AF3/Chai-1 on affinity | ✅ **matches** (and validates our binder-vs-decoy use case) |
| 4/5 ADMET (BBBP/tox) | **ChemBERTa-2 ≈ MolFormer-XL**; AD-gate needed | ChemBERTa-2 0.71–0.93, MolFormer 0.65–0.88, Uni-Mol 0.67–0.96 — competitive but "**do not dominate**"; fingerprints/descriptors often match; TDC leaderboard is the standard | ✅ **matches** (strong-but-not-dominant; our Morgan-FP-beats-embeddings + AD-collapse findings) |
| 6 KG / hypothesis | **PROTON** (NeuroKG, neuro-specific) | General repurposing SOTA = **TxGNN** (Nature Med, clinician-centered, 17K diseases zero-shot) + **BioPathNet** (2025, NBFNet path-based, "outperforms or matches") | ⚠️ PROTON is the neuro-specialist; **TxGNN / BioPathNet are the general-repurposing SOTA we haven't tested** |
| 7 Cross-modal (V1-T) | nothing public works | perturbation FMs (scGPT/Geneformer) underperform a mean baseline (Nature Methods 2025); Tahoe-x1 the exception | ✅ matches — build on V1-T |

## Where the literature adds something (untested candidates worth flagging)
1. **xTrimoPGLM** (Track 1) — large protein LM that appears in the 2025 embedding benchmarks alongside ESM/Ankh/ProstT5; we didn't test it. Given our saturation finding (medium models already ~0.95), low expected upside, but it's the one Track-1 model the literature rates that we skipped.
2. **TxGNN** (Track 6) — the Nature-Medicine clinician-centered drug-repurposing foundation model (zero-shot across 17,080 diseases). PROTON is neuro-KG-specific; TxGNN is the general-disease repurposing SOTA. We deprioritized it (DGL install drama) — but the literature rates it highly for the broader repurposing use case.
3. **BioPathNet** (Track 6, 2025) — NBFNet path-based reasoning on biomedical KGs; "outperforms or matches existing methods." Newer than PROTON; **path-based (explainable) vs PROTON's embedding decoder** — could give better/interpretable hypotheses. Untested.
4. **Descriptor-augmented / EffiChem** (Track 4/5) — 2025 work shows +3–5% AUC over MolFormer-XL via descriptor augmentation / parameter-efficient adaptation. Cheap potential edge on our ADMET layer.

## Takeaway
The empirical campaign agrees with the published consensus on every track where we have a winner
(strong external validation of "test on our substrate" — we independently reproduced the
field's medium-model + Boltz-2 + transformers-don't-dominate conclusions). The only place the
literature points somewhere we haven't gone is **Track 6 KG**: PROTON is the right neuro-specialist,
but **TxGNN / BioPathNet are the general-repurposing SOTA** — worth a look if Quiver wants
disease-level repurposing beyond the neuro-KG. (We're characterizing PROTON's operating envelope
on AWS now.)

## Sources
- Protein LMs: [Sci Reports — medium PLMs transfer well](https://www.nature.com/articles/s41598-025-05674-x), [PLM crystallization benchmark](https://www.nature.com/articles/s41598-025-86519-5), [function-prediction PLM review (Frontiers)](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2025.1506508/full)
- Co-folding/affinity: [Boltz-2 (bioRxiv)](https://www.biorxiv.org/content/10.1101/2025.06.14.659707v1), [external Boltz-2 benchmarks (Rowan)](https://rowansci.com/blog/boltz2-benchmarks), [AF3 vs Boltz vs Chai (Boolean Biotech)](https://blog.booleanbiotech.com/alphafold3-boltz-chai1)
- ADMET: [feature-representation ADMET benchmark (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12281724/), [EffiChem (ChemRxiv)](https://chemrxiv.org/doi/full/10.26434/chemrxiv-2025-2lljt), [frozen SMILES embeddings vs fingerprints (ChemRxiv)](https://chemrxiv.org/doi/full/10.26434/chemrxiv.15004188/v1)
- KG repurposing: [TxGNN (Nature Medicine)](https://www.nature.com/articles/s41591-024-03233-x), [BioPathNet (Nature BME 2025)](https://www.nature.com/articles/s41551-025-01598-z), [KG-for-repurposing review (Brief Bioinform)](https://academic.oup.com/bib/article/25/6/bbae461/7774899)
