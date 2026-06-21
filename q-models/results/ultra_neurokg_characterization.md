# ULTRA on NeuroKG — TRUE same-substrate head-to-head vs PROTON (2026-06-14)

Rohan supplied the **NeuroKG** dataverse export, so ULTRA finally runs on **the exact graph PROTON was
trained on** — the apples-to-apples test the Hetionet run (`results/ultra_kg_characterization.md`) could
only approximate. **NeuroKG = PrimeKG + Quiver neuro augmentation:** 147,020 nodes, 16 node types
(incl. `brain_structure`, `brain_region`, `cell_subtype_PD` Parkinson's markers), binding relation
`drug_protein` (28,774 edges), 8,160 drugs. **Run:** g5.2xlarge, **GPU** (rspmm CUDA kernel compiled —
no CPU fallback), zero-shot `ultra_4g`. Dropped the 4.1M anatomy-expression edges (not binding-relevant)
→ 3.21M forward edges. All 10 Quiver targets resolved. ~$0.6.

## Verdict: **On PROTON's own graph, ULTRA (zero-shot) fixes BOTH of PROTON's documented failure modes — no hub bias, and real inductive novel-target capability. This confirms the Track-6 co-winner call on the fair substrate. PROTON + ULTRA co-deploy; ULTRA is the default for hub-sensitive, novel-target, and ion-channel queries.**

### B. Hub bias — DECISIVE, biologically-validated win (this is the fair, same-protocol comparison)
PROTON's #1 failure: the same promiscuous drug (Bepridil) ranks #1 for 9 unrelated targets. ULTRA on the
same graph: **mean pairwise top-10 Jaccard = 0.065; most-promiscuous drug in only 4/10 targets.** And the
per-target top drugs are **correct pharmacology**, not hubs:
| Target | ULTRA's top drugs | correct? |
|---|---|---|
| MTOR | Dactolisib, XL765, SF1126 | ✅ PI3K/mTOR inhibitors |
| EGFR | Varlitinib, Tesevatinib, Abivertinib, PD-168393 | ✅ EGFR inhibitors |
| BRAF | PLX-4720, RAF-265, XL281 | ✅ RAF inhibitors |
| DRD2 | Sarizotan, Pardoprunox, Sumanirole | ✅ dopaminergics |
| HTR2A | Nelotanserin, Setiptiline | ✅ serotonergics |
| SCN10A/9A/5A (Nav) | Pentoxyverine, Amylocaine, Hexylcaine, Butamben | ✅ local anesthetics / Na-blockers |
The only cross-target overlap is **among the three Nav paralogs** — which is *correct biology* (Na-channel
blockers are genuinely cross-reactive), not a hub artifact. This is the exact opposite of PROTON's pathology.

### C. Inductive novel-target — capability PROTON entirely lacks (`binder_not_in_kg` = 0)
Hold **all** of a target's `drug_protein` edges out, then rank the held binder zero-shot. Median inductive
rank **0.34%** (of 147,020 nodes):
| Target | held-out drug | rank | rank % |
|---|---|---|---|
| Cav1.2 | Enflurane | 173 | 0.12% |
| Nav1.7 | Phenytoin | 421 | 0.29% |
| Nav1.5 | Phenytoin | 497 | 0.34% |
| Nav1.8 | Phenytoin | 512 | 0.35% |
| MTOR | Sirolimus (rapamycin) | 3,638 | 2.47% |
With every binding edge removed, ULTRA still places Phenytoin (a Na-channel anticonvulsant) in the top
~0.3% for the Nav channels and Sirolimus (the canonical mTOR binder) in the top 2.5% for MTOR — real
inductive transfer on novel targets, which PROTON cannot do at all.

### A. Known-binder retrieval — strong, but NOT a clean same-protocol number vs PROTON's 4.3% (caveat)
ULTRA ranks the correct **target** for a known drug at **median absolute rank 16–61 of 147,020 nodes**
(overall median ≈ rank 40 = **0.026%**): Cav1.2 16, DRD2 19, HTR2A 20, EGFR/Nav1.7 33–34, Nav1.5 41,
GRIN1 53, BRAF 59, MTOR 60, Nav1.8 61.
**Do not read 0.026% as "165× better than PROTON's 4.3%."** This section ranks *target-given-drug over all
node types*, whereas PROTON's 4.3% is *known-drug-given-target among drugs* — different direction and a
much larger denominator, so the percentages are not comparable. What A *does* show: ULTRA's zero-shot link
scoring is strong and well-behaved on NeuroKG. A strict same-protocol known-binder-ranking % (target→drug,
drug-restricted candidates) is a cheap follow-up if a single head-to-head number is wanted; the verdict
above rests on B and C, which **are** protocol-fair.

## Comparison to the Hetionet run
Same qualitative story on both graphs (no hub bias; strong inductive), now confirmed on PROTON's *actual*
training graph. NB: the prior Hetionet writeup's A percentages were mis-scaled by 100× and have been
corrected there; the B/C conclusions were and remain correct.

## Recommendation / scorecard
**Track 6 = PROTON + ULTRA (co-winners), confirmed on the same substrate.** Use **ULTRA** (zero-shot, MIT,
168k params) as the default for **novel/weakly-connected targets** (inductive — PROTON can't), **hub-robust
shortlists** (no Bepridil effect; biologically-specific top drugs), and **ion-channel / kinase / GPCR**
targets where its top-drug lists are pharmacologically correct. Keep **PROTON** for any Quiver-private edges
not in this export + as a cross-check. Both stay **hypothesis-shortlist tools, not binder predictors**.
NeuroKG is now in our S3 (`neurokg_src/`) for future same-substrate work.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/ultra_neurokg/ultra_neurokg_result.json`;
eval `aws/ultra_neurokg_eval.py`; instance `i-0f23240569fd7a434` self-terminated; no strays.
