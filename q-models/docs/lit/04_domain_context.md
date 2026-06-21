# Domain context — what MAMMAL's numbers mean for real drug discovery

**Lane: DOMAIN CONTEXT.** Purpose: ground every MAMMAL metric in what it actually buys in a
hit-finding / de-risking campaign, so the synthesis can judge "useful or not" on the right yardstick.
Bar = realistic field ceilings on hard, prospective, out-of-distribution problems — **not** the
paper's leaderboard badges. Team mantra: *"state-of-the-art on shit is still shit."*

Written 2026-06-01. Sources inline; full list at the bottom. Cross-refs: `../FINDINGS.md`,
`../../results/phase3_wdr91_finetune.md`, `../../results/phase1_calibration.md`,
`../../results/phase4_finetuned_report_card.md`.

---

## 0. Bottom line up top (calibration verdict per MAMMAL claim)

| MAMMAL claim (our measured / paper) | Realistic field ceiling | Calibrated verdict |
|---|---|---|
| **WDR91 binder triage**: AUROC 0.63, **top-5% enrichment 5.25×** (OOD) | EF mean ~6 at top 2%; **10–50× = "very good"**; 6× over HTS was "noteworthy" prospectively | **Mediocre-to-OK.** Real signal, ordinary magnitude. A 5× enrichment is a *normal* triage result, not a differentiator. |
| **PGK2/DEL**: AUROC 0.97–0.98 in-distribution; **Spearman vs DEL read-count ≈ 0** | DEL+ML done right: AUROC 0.97 *and* ~**30% prospective hit rate**, IC50 **< 10 nM** found, graded enrichment→potency link | **The 0.97 is memorization.** The field's 0.97 came *with* potency ranking + prospective hits; MAMMAL's comes *without* either. Looks identical, buys far less. |
| **DTI pKd**: NRMSE ~0.88 (paper 0.906), PEER Spearman 0.43 | Best hard-split BindingDB Pearson ≈ **0.51**; proper de-leaked splits drop 0.74→0.67; R²≈0.18 | **At/just below the realistic ceiling.** "~9% better than the mean" is **normal** for cold-split DTA — the whole field is bad here. |
| **BBBP**: AUROC 0.957 (paper) / 0.968 (ours) | Specialist BBB models routinely **0.92–0.98**; plain RF often wins; benchmark is leaky/curation-flawed | **In-pack, not a moat.** 0.957 is a *commodity* number a Random Forest matches. Held-out TNR 0.70 is the real story. |
| **ClinTox-tox**: AUROC ~1.0 (paper 0.986) | Realistic clinical-tox (DILI) external-test ceiling ≈ **0.79–0.80**; hERG specialists ~0.83–0.95 | **AUROC 1.0 is impossible→memorization.** No clinical-tox model generalizes to 1.0; 0.80 is the honest bar. Confirms our "0% external sensitivity" finding. |

**One sentence:** MAMMAL's numbers are *honest reproductions of benchmarks that are themselves
either easy/saturated (BBBP, ClinTox) or hard-for-everyone (DTI), and its one genuinely useful
capability (per-target triage) lands at an ordinary, not exceptional, enrichment.*

---

## 1. DEL and ASMS screening — what hit/non-hit means, and what enrichment buys

### What the labels are
- **DEL (DNA-encoded library):** pool 10^6–10^9 small molecules, each tagged with a unique DNA
  barcode. Incubate against immobilized target, wash, elute, **NGS-sequence the surviving barcodes**.
  A "hit" = a molecule whose barcode is **enriched** (over-represented) in the eluate vs the input or
  a no-target control. The readout is a *count* (enrichment ratio), inherently noisy and stochastic
  at low counts (modeled as Poisson-ish; randomness must be modeled for reliable enrichment calls —
  [Kuai 2018](https://journals.sagepub.com/doi/10.1177/2472555218757718)).
- **ASMS (affinity-selection MS):** incubate library + target in solution, size-exclude to keep only
  target-bound molecules, dissociate, and **identify survivors by exact mass on an HRMS**. A "hit" =
  a molecule detected as target-bound. Biases toward higher-affinity (Kd typically **< low-double-digit
  µM**), slow-off-rate, ionizable compounds
  ([Edelris](https://www.edelris.com/blog/affinity-selection-mass-spectrometry-as-ms-a-smarter-path-to-high-quality-hits-for-drug-discovery),
  [Sygnature](https://www.sygnaturediscovery.com/bioscience/affinity-selection-mass-spectrometry/)).

Both produce **binary-ish hit/non-hit calls plus a noisy magnitude** (DEL count / MS intensity), and
**both are affinity-blind in the fine-grained sense** — they tell you "bound enough to survive,"
not Kd. This is exactly why MAMMAL's heads, trained on DEL/ASMS labels, are binary classifiers with
**no graded potency signal** — the training labels barely carry one.

### Typical hit rates (so the "inactive prior" is contextualized)
- **DEL primary hit rates: ~0.08–0.24%** of the library
  ([search synthesis, FXa/ATX studies](https://www.nature.com/articles/s44386-025-00007-4)).
- **ASMS hit rates: ~0.5–1.5%** per screen, throughput ~10^5 cmpds/day, deliberately low to keep
  hit quality high
  ([WuXi](https://wuxibiology.com/resource/application-of-affinity-selection-mass-spectrometry-molecular-glues-drug-discovery/)).
- So the **base rate of a true binder is well under 1%.** A classifier with a strong "inactive prior"
  (which is what MAMMAL's WDR91/PGK2 heads are — they predict `<0>` for almost everything) is
  *correctly calibrated to the prior* — the question is only whether its top-ranked slice is enriched.

### What enrichment factor (EF) and AUROC ~0.8 actually buy
- **EF_x% = (hit rate in top x% selected) / (random hit rate).** It is the *only* metric that maps
  to the real decision (how many compounds must I make/assay to find N hits).
- **Field calibration of EF:** across methods, **mean EF ≈ 6 at the top 2%** (range 0–26);
  state-of-the-art structure-based AI hits **EF_1% ≈ 12–17**; **10–50× is "very good."** A **6× over
  the HTS hit rate was called "noteworthy" in prospective studies**
  ([Pharmacelera](https://pharmacelera.com/blog/science/measuring-virtual-screening-accuracy/),
  [Cambridge MedChem](https://www.cambridgemedchemconsulting.com/resources/hit_identification/virtual_screening_selection.html),
  [Nat Commun 2024](https://www.nature.com/articles/s41467-024-52061-7)).
  → **MAMMAL's WDR91 5.25× at top-5% is a real, ordinary triage result — squarely "useful but
  unremarkable," not a moat.**
- **AUROC is the wrong headline metric for screening.** It weights the whole ranked list equally,
  but you only ever assay the top sliver — so AUROC is **insensitive to early recognition**
  ([Truchon & Bayly, the "early recognition" paper](https://www.researchgate.net/publication/6517236);
  [practicalcheminformatics](http://practicalcheminformatics.blogspot.com/2023/08/we-need-better-benchmarks-for-machine.html)).
  A model can have AUROC 0.63 (MAMMAL/WDR91) yet still be useful *because* its top-5% is enriched, or
  AUROC 0.97 (MAMMAL/PGK2-in-dist) and be near-useless prospectively. **Always quote EF / BEDROC, not
  AUROC, for a screening tool.**
- **What "good" looks like, end to end:** the canonical DEL+ML benchmark (X-Chem/Google,
  [J Med Chem 2020](https://pubs.acs.org/doi/10.1021/acs.jmedchem.0c00452)) trained on DEL counts and
  *prospectively* hit **~30% confirmed at 30 µM across 3 targets (sEH, ERα, c-KIT), with IC50 < 10 nM
  compounds for every target** — and its AUROC-0.97 model **also** ranked potency. A more recent
  [npj Drug Discovery 2025 DEL+ML study](https://www.nature.com/articles/s44386-025-00007-4) confirmed
  **~10% of predicted binders and ~94% of predicted non-binders** in biophysical assays (i.e. ML is a
  strong *de-risking* filter — great negative predictive value, modest positive).
  → **The bar MAMMAL is implicitly compared to is "AUROC 0.97 *plus* prospective nM hits *plus*
  potency ranking." MAMMAL's PGK2 head reproduces only the first and explicitly fails the other two
  (Spearman vs count ≈ 0).** State-of-the-art shape, not state-of-the-art payload.

---

## 2. BBB-penetrance and clinical-tox — is BBBP 0.957 good, and what do specialists hit?

### BBB penetrance
- **Specialist BBB models routinely score AUROC 0.92–0.98**: Random Forests at **0.931–0.943**;
  recent reports up to **0.98**; reviews note DL edges out only modestly
  ([Nabi 2025 review](https://onlinelibrary.wiley.com/doi/full/10.1002/minf.202400325),
  [PMC11938273](https://pmc.ncbi.nlm.nih.gov/articles/PMC11938273/)).
- **The MoleculeNet BBBP benchmark is known-saturated, leaky, and mis-curated.** A plain **RF on
  RDKit2D descriptors is often the best model under scaffold split**; rankings are compressed; AUROC
  is "over-optimistic" and **PPV/NPV matter more for screening**; the BBBP set itself has documented
  curation errors ([systematic survey](https://arxiv.org/html/2604.16586v1),
  [practicalcheminformatics](http://practicalcheminformatics.blogspot.com/2023/08/we-need-better-benchmarks-for-machine.html),
  [DataSAIL leakage addendum](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12905371/)).
- **Verdict: MAMMAL's BBBP 0.957 is a commodity number** — exactly what a 30-line Random Forest gets,
  on a benchmark whose ceiling is inflated. Our own held-out **TNR 0.70 / false-positive bias** finding
  (passes cetirizine/atenolol/domperidone) is the *real* deployment story, and it's consistent with
  "AUROC ≠ deployable PPV." **Good benchmark score, mediocre as a rule-out gate.**

### Clinical toxicity (the ClinTox 1.0 reality check)
- **There is no clinical-tox model that generalizes near 1.0.** The honest external-test ceilings:
  - **DILI (drug-induced liver injury):** DILIPredictor on a held-out external set **AUROC ≈ 0.79**;
    a strong DNN **≈ 0.80**; severity/concern variants **0.58–0.63**
    ([bioRxiv 2024 / PMC11185581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11185581/),
    [PMC7702310](https://pmc.ncbi.nlm.nih.gov/articles/PMC7702310/)). DILIst (~1279 drugs) is the
    standard set; ~0.80 is the realistic wall because clinical tox is multi-mechanism and label-noisy.
  - **hERG (cardiotox surrogate):** specialist GNN/ML **AUROC ≈ 0.835–0.95** depending on split
    ([AttenhERG, J Cheminform 2024](https://jcheminf.biomedcentral.com/articles/10.1186/s13321-024-00940-y)).
- **Verdict: MAMMAL ClinTox AUROC ~1.0 is *prima facie* memorization**, not skill — no honest
  clinical-tox model exceeds ~0.80 out-of-distribution. This independently corroborates Phase 4's
  "0% sensitivity to external clinically-toxic drugs." **Do not treat 1.0 as good; treat it as a red
  flag.** A genuinely useful tox gate would look like AUROC ~0.80 *with* external generalization.

---

## 3. Drug-target binding affinity — is "9% better than the mean" normal?

- **On hard, leakage-controlled splits, DTA is a genuinely hard problem and everyone is bad at it.**
  Best models on **BindingDB hard splits reach Pearson ≈ 0.51** (AdaMBind); fixing data leakage drops
  the best benchmark from **Pearson 0.74 → 0.67**; performance "severely degrades" on compounds
  dissimilar to training ([similarity-aware eval](https://arxiv.org/html/2504.09481v1),
  [meta-learning DTA, Nat Commun 2026](https://www.nature.com/articles/s41467-026-70554-5),
  [generalization benchmark, ChemRxiv 2025](https://chemrxiv.org/doi/full/10.26434/chemrxiv-2025-gmrdb)).
- **MAMMAL's reproduced NRMSE ~0.88 corresponds to R² ≈ 0.18 (≈9% better than predicting the mean).**
  In this field, on cold/PEER splits, **that is normal, not bad** — it's "least-bad at a hard task."
  Our PEER Spearman **0.43** sits right in the realistic band (0.4–0.5), and the in-distribution control
  (Spearman ~0.61) confirms the pipeline isn't broken — the *task* is hard.
- **What this means for use:** DTA scores are usable for **coarse cross-target re-ranking** (which of
  these diverse pairs is more likely to bind) and **useless for single-target triage** ("does drug X
  hit target Y") — exactly what Phase 2 found (Nav1.8/mTOR separation ≈ 0). The ceiling itself forbids
  a binding oracle here; this is a property of the field, not a MAMMAL defect.

---

## 4. What "potency ranking" (graded KD) requires that binary classification does not

This is the crux of why MAMMAL's per-target heads are *triage* tools, not *lead-ranking* tools.

| Requirement | Binary hit/non-hit | Graded KD / potency ranking |
|---|---|---|
| **Label** | one bit (bound / not) — what DEL & ASMS natively give | a *continuous, calibrated* affinity (Kd/IC50/Ki) across ≥3–4 log units |
| **Training data** | abundant (every DEL/ASMS screen) | scarce, expensive (dose-response curves; ASMS/DEL counts are **not** clean surrogates — count↔potency correlation is weak/noisy) |
| **What it must learn** | a *decision boundary* around the active chemotype | a *monotone, smooth structure→affinity surface* (SAR) — small structural edits → small, ordered ΔKd |
| **Metric** | AUROC, EF, BEDROC | Spearman/Pearson on held-out potencies; Kendall-τ on rank |
| **Failure mode** | saturates at 0/1 (fine for triage) | saturation *kills* it — can't order compounds it all calls "active" |
| **MAMMAL result** | works (WDR91 EF 5.25×; PGK2 in-dist AUROC 0.97) | **fails by construction** — PGK2 scores saturate at ~0.99998 for all hits → **Spearman vs DEL count ≈ 0 / −0.06**; WDR91 **Spearman vs pKd −0.15** |

**Why binary is genuinely easier:** a classifier only needs the active region to be *separable* in
representation space. Potency ranking needs the representation to be *locally ordered by affinity*
everywhere — a much stronger geometric demand that requires (a) potency-labeled training data MAMMAL
never saw and (b) a regression head MAMMAL's per-target checkpoints leave untrained/vestigial. The
two heads literally cannot rank: they emit a saturated near-1.0 for everything they recognize. **So
"can MAMMAL prioritize my lead series by potency?" is a hard NO, independent of how good the binary
triage looks.** Lead optimization — the step where ranking matters most and is most valuable — is
exactly where these heads stop helping.

---

## 5. Sources

DEL / ASMS screening:
- [DEL+ML hit discovery eval, npj Drug Discovery 2025](https://www.nature.com/articles/s44386-025-00007-4) — ~10% predicted-binders / ~94% predicted-non-binders confirmed; DEL hit rates 0.08–0.24%.
- [Machine learning on DEL, J Med Chem 2020 (X-Chem/Google)](https://pubs.acs.org/doi/10.1021/acs.jmedchem.0c00452) — prospective ~30% hit rate @30µM, IC50<10nM, AUROC 0.97. ([arXiv](https://arxiv.org/abs/2002.02530))
- [Kuai 2018, modeling randomness in DEL selection](https://journals.sagepub.com/doi/10.1177/2472555218757718).
- ASMS hit rates / quality: [WuXi](https://wuxibiology.com/resource/application-of-affinity-selection-mass-spectrometry-molecular-glues-drug-discovery/), [Edelris](https://www.edelris.com/blog/affinity-selection-mass-spectrometry-as-ms-a-smarter-path-to-high-quality-hits-for-drug-discovery), [Sygnature](https://www.sygnaturediscovery.com/bioscience/affinity-selection-mass-spectrometry/).

Enrichment / VS metrics:
- [Pharmacelera, measuring VS accuracy (EF mean ~6 @top2%)](https://pharmacelera.com/blog/science/measuring-virtual-screening-accuracy/).
- [Cambridge MedChem, VS selection (6× over HTS "noteworthy")](https://www.cambridgemedchemconsulting.com/resources/hit_identification/virtual_screening_selection.html).
- [Truchon & Bayly, "early recognition" — AUROC insensitivity](https://www.researchgate.net/publication/6517236_Evaluating_Virtual_Screening_Methods_Good_and_Bad_Metrics_for_the_Early_Recognition_Problem).
- [AI VS platform, Nat Commun 2024 (EF_1% 12–17)](https://www.nature.com/articles/s41467-024-52061-7).

BBB / clinical tox:
- [Nabi 2025, BBB ML review (RF 0.93–0.94)](https://onlinelibrary.wiley.com/doi/full/10.1002/minf.202400325); [standardized-DB BBB study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11938273/).
- [MoleculeNet leakage/saturation, systematic survey 2026](https://arxiv.org/html/2604.16586v1); [practicalcheminformatics on benchmarks](http://practicalcheminformatics.blogspot.com/2023/08/we-need-better-benchmarks-for-machine.html); [DataSAIL leakage addendum](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12905371/).
- DILI: [DILIPredictor / DNN, AUROC ~0.79–0.80, PMC11185581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11185581/), [PMC7702310](https://pmc.ncbi.nlm.nih.gov/articles/PMC7702310/).
- hERG: [AttenhERG 0.835, J Cheminform 2024](https://jcheminf.biomedcentral.com/articles/10.1186/s13321-024-00940-y).

DTA hard-split ceilings:
- [Similarity-aware DTA eval (0.74→0.67 with proper splits)](https://arxiv.org/html/2504.09481v1).
- [Meta-learning DTA, Nat Commun 2026 (BindingDB ~0.51)](https://www.nature.com/articles/s41467-026-70554-5).
- [Generalization benchmark, ChemRxiv 2025](https://chemrxiv.org/doi/full/10.26434/chemrxiv-2025-gmrdb); [TDC DTI task](https://tdcommons.ai/multi_pred_tasks/dti/).
