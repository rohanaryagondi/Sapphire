# MAMMAL out-of-the-box — meeting prep
*Rohan Aryagondi · Quiver Bioscience · 2026-05-29*

---

## What MAMMAL is

IBM's MAMMAL (`biomed.omics.bl.sm.ma-ted-458m`) is a 458M-parameter encoder-decoder
(T5-style) pretrained on proteins, small molecules, antibodies, and gene expression — all
in a single shared latent space. It ships with roughly 10 fine-tuned task heads covering
drug-target binding affinity, BBB penetrance, clinical toxicity, TCR-epitope binding,
protein solubility, and per-target binder classification.

The core architectural idea: by training across modalities together, MAMMAL learns
representations where a molecule's embedding and a protein's embedding "live" in the same
space and can be compared directly. This is what separates it from stacking separate
molecule models (e.g. Morgan fingerprints) with separate protein models (e.g. ESM-2) —
those two embedding spaces have no shared geometry, so you can't directly ask "is this
molecule close to this protein's binder cluster?"

We ran every publicly available fine-tuned head against real data across 5 phases of
testing. The picture is more nuanced than the paper benchmarks suggest — some capabilities
are genuinely deployable, others are broken, and one path (per-target fine-tuning) is the
most interesting for Quiver.

---

## Capability map with explanations

### BBB penetrance (BBBP head) — usable, with caveats

**What it does:** Given a SMILES string, predicts whether a compound crosses the
blood-brain barrier. Trained on the MoleculeNet BBBP dataset (~2000 compounds from
literature).

**Why it works:** The BBB dataset is large, structurally diverse, and well-curated —
CNS drugs follow recognizable physicochemical rules (Lipinski-adjacent: moderate logP,
low MW, few H-bond donors). MAMMAL's encoder learns these rules from SMILES tokens
during fine-tuning. The model hits AUROC 0.968 on the held-out scaffold test fold.

**What we found on real data:** 11/11 known CNS-active drugs (carbamazepine, valproate,
clonazepam, sertraline, etc.) correctly called penetrant. Large, clearly excluded molecules
(vancomycin MW 1449, sirolimus MW 914) correctly called non-penetrant. But: small
peripherally-restricted drugs with low passive permeability (cetirizine, atenolol,
domperidone) are wrongly called "penetrant" — the model doesn't know about active efflux
transporters like P-gp, which keep these drugs out despite favorable physicochemistry.

**Bottom line for Quiver:** Strong positive signal — if MAMMAL calls a compound
CNS-penetrant, it probably is. The reverse is not reliable (30% false-positive on
peripheral drugs). Use as an enrichment step, not a hard filter. Standardize SMILES
to neutral parent form (strip salts, neutralize charges) before scoring — the model is
sensitive to protonation state.

---

### Clinical toxicity (ClinTox head) — do not use

**What it does:** Predicts clinical toxicity from SMILES. Trained on ~1500 FDA drug
submissions split into clinically-toxic and non-toxic.

**Why it fails:** The training set is tiny (~112 unique toxic compounds) and the toxic
drugs are structurally concentrated — most are specific withdrawn drugs from specific
chemical series. The model achieves AUROC 1.0 by memorizing the exact structures it
trained on, not by learning any general toxicity mechanism. When you give it a drug that
wasn't in the training set, it has nothing to generalize from.

**What we found:** On 15 clinically withdrawn drugs (cerivastatin/rhabdomyolysis,
troglitazone/hepatotoxicity, terfenadine/QTc, thalidomide/teratogenicity, etc.) —
**zero were flagged as toxic.** The model called all of them safe. Earlier reports that
it "over-predicts toxicity" were an artifact of feeding protonated SMILES from PubChem;
with properly standardized inputs it swings the other direction entirely.

**The underlying problem:** Toxicity is mechanism-specific. hERG blockers cause QTc
prolongation; reactive metabolites from certain moieties cause hepatotoxicity; thalidomide's
toxicity is tied to its enantiomeric binding to cereblon. A single head trained on a
mixed toxicity dataset learns a smeared average that generalizes to nothing outside its
training distribution.

**Bottom line for Quiver:** Discard. Replace with mechanism-specific tools (see tox section).

---

### Drug-target binding affinity (DTI head) — coarse re-ranking only

**What it does:** Given a drug SMILES + protein sequence, predicts binding affinity as
pKd. Trained on ~500K drug-protein pairs from BindingDB.

**Why it works coarsely:** BindingDB is broad — millions of pairs across thousands of
targets and drug classes. The model learns correlations between chemical features and
general binding propensity. Across a *diverse set of targets and compounds*, it produces
a ranking that's better than random (Spearman 0.43 on our 10-pair test with the PEER
checkpoint).

**Why it fails for single-target triage:** To discriminate binders from non-binders for
a *specific* target, the model needs to learn the precise shape and electrostatic
complementarity of that target's binding site. BindingDB training gives it approximate
chemical-biological correlations, not target-specific pharmacophore knowledge. When we
test Nav1.8 binders (suzetrigine, other VGSCs) against drug-like decoys, scores are
indistinguishable — the model has no idea what makes a compound selective for Nav1.8
versus any other sodium channel.

An additional technical issue: the DTI head truncates protein sequences to 1250 amino
acids. Several of our targets (Nav1.8 is 1956 aa) get truncated, losing the C-terminal
domain that contains binding-relevant regions.

**Bottom line for Quiver:** Use the PEER checkpoint (not the cold-split checkpoint —
wrong normalization constants, Spearman −0.03) to coarsely re-rank hits across diverse
targets at the end of a funnel. Do not use for any binary "does this bind target X"
question.

---

### Per-target binder heads (wdr91_asms, pgk2_del_cdd) — the interesting one

**What they are:** IBM trained MAMMAL specifically on affinity-selection mass spectrometry
(ASMS) data for WDR91 and PGK2. These are generative classifiers: you prompt the model
with a per-target task token (`<WDR91_ASMS>`) alongside a SMILES string, run `model.generate`,
and read the probability of the `<1>` (active) token at the first output position.

**Why this works where off-the-shelf DTI fails:** The fine-tuned head has seen the
specific chemical series that bind WDR91. During training, the model's encoder learns
to associate certain SMILES substructures — the pharmacophoric features of WDR91 binders
— with the active output token. The base model's general chemical representations are
steered toward a target-specific manifold.

**What we found on real data:**
- On 239 Ahmad 2023 SPR compounds (38 confirmed SPR binders, 201 confirmed SPR
  non-binders with KD = 0): **AUROC 0.816**, top-5% enrichment **4.57×**
- Earlier tests with synthetic drug-like decoys gave AUROC 0.63 — the real-data number
  is higher because confirmed SPR zeros are cleaner negatives than random compounds
  (which occasionally weakly bind by chance)
- **No potency ranking:** among the 35 binders with numeric KD (4–270 µM), Spearman
  correlation with score is ≈ 0. The head is a binary classifier, not a ranker.
- **Chemotype-specific:** the head recognizes the scaffold families present in its
  training ASMS data. It is not a generative hit-finder — it will not reliably score
  a completely novel scaffold from a different chemical series.

**An important gotcha:** IBM's scalar prediction head (the DTI-style readout) is
completely untrained in these models — it sits at random weights. Reading the scalar
output gives AUROC 0.43 and looks like a broken model. The correct readout is the
generative probability, which took significant debugging to discover.

---

### Protein embeddings — good, and important for Quiver

**What they do:** The base MAMMAL encoder produces a 768-dimensional embedding for any
protein sequence (masked mean-pool of the encoder's last hidden state). These embeddings
encode evolutionary, structural, and functional relationships between proteins.

**Why they work:** MAMMAL was pretrained on millions of protein sequences. Like language
model pretraining, this teaches the encoder to represent protein "meaning" — sequence
motifs, domain structures, functional residues. Proteins from the same structural family
share similar embeddings because they share evolutionary ancestry and structural fold.

**Head-to-head vs ESM-2 (8M parameter variant):**

| Model | NN same-family recall | Intra/inter gap |
|---|---|---|
| MAMMAL (458M) | **0.920** | **0.463** |
| ESM-2 (8M) | 0.880 | 0.093 |

MAMMAL beats ESM-2's smallest variant on both metrics. ESM-2 8M squishes all proteins
into a narrow cosine range (0.84–0.99 everywhere) with almost no family discrimination.
MAMMAL has sharper boundaries. *Important caveat:* ESM-2 at 650M or 3B parameters was
trained specifically on protein sequences at far larger scale and would almost certainly
win. The comparison is against the 8M variant — don't overread it.

**On a 40-gene CRISPR-N-style panel:**
- GPCRs: 100% correct family clustering
- Kinases: 100% correct
- Sodium channels (Nav1.7, Nav1.8, SCN1A, SCN5A): 100% correct
- Ion channels (all): 88% correct
- E3 ligases: 25% — but this "family" is structurally heterogeneous (MDM2, YAP1, SF3B1,
  RARA are unrelated proteins grouped by function, not fold)
- Nuclear receptors: 33% by label, but most "failures" route to RARA, which is
  *actually* a nuclear receptor — it was mislabeled in our test

**What this means for Quiver:** Protein embeddings are ready to use for CRISPR-N gene
clustering, specifically for structurally coherent families. Group by embedding
neighborhood, not by functional annotation alone.

---

## Why simple methods still beat MAMMAL in places

**Similarity expansion (Morgan fingerprints vs MAMMAL embeddings):**
Morgan fingerprints encode exact circular substructure presence/absence around each
atom — they directly capture the chemical features medicinal chemists care about for
similarity. MAMMAL compound embeddings encode a learned representation that conflates
many signals (binding, ADMET, general chemistry). On same-scaffold retrieval, Morgan wins
(0.96 vs 0.72 same-class NN recall) because the task is purely about chemical structure.

**Tox filtering (structural rules vs ClinTox):**
A simple rule encoding "lipophilic compound with a basic nitrogen in an aromatic scaffold"
catches the main QTc-causing drugs because the hERG channel has a known pharmacophore
(hydrophobic inner cavity, basic N makes the cation form that blocks the channel). This
rule is *mechanistic* — it's derived from understanding how hERG blockade works.
ClinTox has no such mechanistic grounding — it just pattern-matches against training examples.

---

## What Quiver can achieve by integrating MAMMAL with its own data

This is the most important section.

### Per-target binder classification — the proprietary play

IBM's WDR91/PGK2 heads are proof that the recipe works. The training pipeline is in
`mammal/examples/`. The inputs it needs:

- SMILES strings for each compound
- Binary labels: hit (1) / non-hit (0)
- Minimum ~500 labelled examples; more is better

**Where Quiver's data comes in:**
- DEL (DNA-encoded library) read counts → threshold on enrichment ratio → binary labels
- ASMS data → threshold on signal → binary labels
- Any binary screen with chemistry

**What a Quiver-trained head gives you:**
1. A binder classifier tuned to your exact target, not a generic DTI score
2. Enrichment factors in the 4–5× range at top 5% (based on IBM's WDR91 precedent)
3. A filter that runs at 0.4s/compound on a laptop — fast enough to score DEL-sized
   libraries interactively
4. A proprietary model that encodes your compound-target interaction data in MAMMAL's
   cross-modal latent space

**What it doesn't give you (realistic expectations):**
- It won't rank binders by potency — it's a binary classifier
- It won't generalize to totally novel scaffolds far from its training chemistry
- It won't replace wet lab confirmation
- It works best on targets where the training data has diverse chemotypes — one
  tight chemical series produces a head that's just a substructure alarm

**The comparison that matters:** Off-the-shelf MAMMAL DTI gives AUROC ≈ 0.5 on
binder-vs-nonbinder for a specific target (Nav1.8, mTOR). A fine-tuned per-target head
gives AUROC 0.816 on real SPR data. That gap — from random to genuinely useful — is
what fine-tuning adds.

---

### CRISPR-N gene prioritization

The 1400-gene CRISPR-N panel produces a ranked list of genes. MAMMAL protein
embeddings can add a layer of context: cluster the top-ranked genes by protein
family, surface which drug target families are over-represented, and flag genes
in well-precedented druggable families (kinases, GPCRs, ion channels) vs.
undruggable families (transcription factors with no ligand site, scaffolding proteins).

**The integration:** Run MAMMAL `embed(model, tok, sequence, kind="protein")` on the
UniProt sequences for each of the 1400 genes → 768-d embeddings → UMAP or hierarchical
clustering → overlay with druggability annotations. This produces a visual / queryable
map of the CRISPR-N panel by protein family.

**Why this adds value:** Current prioritization is essentially ranked by functional
evidence (hit strength, reproducibility). Family clustering asks a different question:
"Are multiple genes in this hit list from the same druggable family?" If five hits are
all kinases, that's a stronger signal than five unrelated hits, because one clinical
kinase inhibitor might address several of them, and the SAR knowledge is transferable.

---

### The longer-term play: joint molecule-protein query

Once you have (a) per-target fine-tuned heads and (b) protein embeddings, both living in
MAMMAL's shared latent space, you can ask queries that neither Morgan fingerprints nor
ESM-2 can answer:

*"Which molecules from this library are most similar to the binder cluster of target X,
as measured in the joint molecular-protein embedding space?"*

This is a cross-modal nearest-neighbor search. It doesn't need the fine-tuned head to
score each compound explicitly — instead you embed the library once, embed the target
once, and retrieve by distance. At library scale, this is orders of magnitude faster
than running the generative classifier on every compound.

IBM hasn't released tooling for this, and it would require validating that the shared
space actually aligns (not guaranteed). But it's the architectural capability that
makes MAMMAL distinct from any combination of single-modal tools.

---

## Recommended tox stack (replaces ClinTox)

Toxicity is mechanistically diverse — no single filter catches all failure modes.
The correct approach is layered and mechanism-specific.

| Risk type | Recommended tool | Status |
|---|---|---|
| QTc / cardiac arrhythmia | hERG rule: logP > 1.5, basic N, MW > 200 | ✅ Validated — 100% sens/spec on 10-compound QTc panel |
| DILI / hepatotoxicity | pkCSM DILI API (`biosig.uq.edu.au/pkcsm`) | Not yet validated on our set; use as additional flag |
| Reactive groups / pan-assay interference | RDKit BRENK + PAINS filters | 42% sens / 67% spec on mixed panel — useful for flagging, not ruling out |
| CNS exposure | MAMMAL BBBP | ✅ Validated — retain as soft positive signal |
| MAMMAL ClinTox | — | ❌ Discard — 0% sensitivity to external clinical toxics |

**The hERG rule works because it's mechanistic:** the hERG potassium channel has
a hydrophobic inner cavity that traps lipophilic basic molecules in their cationic form.
The rule (logP > 1.5, basic nitrogen, aromatic scaffold) directly encodes this
pharmacophore. Structural rule > trained model for a well-understood mechanism.

---

## Summary: what to say in the meeting

**"Off the shelf, MAMMAL does two things reliably: it tells you whether a compound
is likely CNS-penetrant, and it clusters proteins by structural family. Both are
useful enrichment steps in a triage funnel, not gates."**

**"Its drug-target binding prediction is SOTA on the benchmark — and that benchmark
is still only 9% better than predicting the mean affinity. On our targets, it can't
tell binders from non-binders."**

**"The clinical toxicity head is benchmarked at AUROC 1.0 and is practically useless.
It memorized 112 training toxics and generalizes to nothing. A 3-line physicochemical
rule catches the QTc drugs it misses."**

**"The interesting path is fine-tuning. IBM's per-target heads show AUROC 0.816 on
real biophysical data. The recipe is published. If we have DEL or ASMS data on a
high-priority target, we can build a Quiver-specific binder classifier that does
single-target triage off-the-shelf MAMMAL can't. That's the one thing in this stack
that Morgan fingerprints and ESM-2 cannot replicate."**
