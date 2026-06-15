# Sapphire Pipeline Master Checklist

**Total Prompts: 299** | **Completed: 299** | **Remaining: 0**

---

## EXAMPLES FROM PITCH DECK (9/9 complete)

- [x] **001** — Are there known disease-causing variants in Gene X that could guide a splice-modulating or allele-selective ASO strategy?
- [x] **002** — What is the predicted minimal knockdown threshold needed for phenotypic rescue/efficacy based on human neuronal phenotypes?
- [x] **003** — What ASO target sites on this transcript show the highest predicted efficacy? lowest toxicity?
- [x] **004** — Does the gene require selective targeting to avoid unwanted biological consequences?
- [x] **005** — Based on known oligo distribution maps, will an ASO targeting this gene achieve sufficient exposure in the relevant brain regions or neuron classes?
- [x] **006** — What other disease-causing genes produce similar electrophysiological or transcriptomic rescue signatures? Can they be addressed by the same oligos?
- [x] **007** — What is the patent landscape for ASO target sites on this gene (target coordinates, sequence claims, modification claims)?
- [x] **008** — Does this transcript display features that increase probability of success? (e.g., long half-life, accessible RNase H sites, favorable exon/intron architecture)
- [x] **009** — Evaluate the risk of pro-inflammatory cytokine release (IL-6, TNF-alpha) for this specific chemical modification pattern.

## ORIGINAL EXAMPLES FROM JAMES/GRAHAM (15/15 complete)

- [x] **010** — Which gene perturbations are most similar to TSC2 based on their EP profiles/signatures?
- [x] **011** — Do the TSC1 and TSC2 gene perturbations have close proximity?
- [x] **012** — Which gene perturbations are anti-podal to TSC1/TSC2 based on their EP profiles/signatures?
- [x] **030** — Please list all of the genes that are "hits"
- [x] **031** — Which gene perturbations are most severe in their disruption of neuronal function?
- [x] **032** — Which voltage-gated sodium channels cluster together?
- [x] **033** — List the gene perturbations within the mTOR pathway and confirm enrichment or identify mTOR pathway genes whose signature is not aligned with those of the other mTOR members.
- [x] **034** — How internally consistent are electrophysiological signatures among gene perturbations in the mTOR pathway, and which outliers deviate most strongly from the cluster?
- [x] **035** — Within the mTOR signaling pathway, which gene perturbations produce electrophysiological profiles that are least similar to other members of the pathway?
- [x] **036** — Are genes associated with the EMC Complex present in the Quiver gene perturbation data set?
- [x] **037** — If so, do the EMC Complex genes cluster together? If yes, how many and which ones?
- [x] **038** — Rank KEGG pathways by the internal similarity of their gene perturbation profiles.
- [x] **039** — Are EP profiles from the PI3K-Akt pathway distinguishable from those of the Wnt signaling pathway?
- [x] **040** — Can we reconstruct the KEGG mTOR pathway structure from EP similarity alone?
- [x] **041** — Do epilepsy-associated gene perturbations cluster more closely together than a randomly selected set of 50 gene perturbations?

## TARGET DISCOVERY & PRIORITIZATION (10/10 complete)

- [x] **042** — Rank the top 25 genetically supported targets for disease modification in early Alzheimer's disease based on Quiver functional phenotype reversal, human genetics strength, and biomarker measurability.
- [x] **043** — For TSC2 loss-of-function, identify all gene perturbations in Quiver that are functionally antipodal. Rank them by druggability and BBB feasibility.
- [x] **013** — Identify CRISPR hits that normalize excitatory/inhibitory imbalance in human cortical neurons and overlap with schizophrenia GWAS loci.
- [x] **014** — For SCN2A gain-of-function epilepsy, propose target suppression strategies ranked by predicted functional rescue and safety margin.
- [x] **015** — Map all genes functionally converging on the same Quiver embedding cluster as GRIN2B and identify which are more druggable.
- [x] **016** — Identify gene targets in neuroinflammation that show strong functional rescue in human neurons but minimal microglial toxicity signals.
- [x] **017** — Among 18k gene perturbations, which 50 genes most strongly improve neuronal firing stability without reducing network connectivity?
- [x] **018** — Identify pathway "common nodes" across ASD, schizophrenia, and epilepsy functional clusters.
- [x] **019** — For Parkinson's disease, identify targets with protective genetic variants and strong Quiver phenotype modulation.
- [x] **020** — Rank top 10 CNS targets where Quiver functional signal contradicts transcriptomic predictions.

## ASO DESIGN PROMPTS (10/10 complete)

- [x] **021** — Design 5 optimized ASO sequences targeting TSC2 with predicted >70% knockdown efficiency and minimal off-target risk.
- [x] **022** — Generate allele-specific ASOs for a pathogenic gain-of-function mutation in SCN8A.
- [x] **023** — For MECP2 duplication syndrome, design partial suppression ASOs that achieve 30–50% knockdown without complete silencing.
- [x] **024** — Identify antisense targets predicted to normalize hyperexcitability in Dup15q neurons.
- [x] **025** — Rank ASO chemistry modifications (2'MOE, LNA, PMO) by predicted CNS tolerability for gene X.
- [x] **026** — For gene Y, generate ASO sequences optimized for intrathecal delivery with low innate immune activation risk.
- [x] **027** — Predict toxicity risk for the top 10 ASO candidates targeting gene Z using known ASO safety datasets.
- [x] **028** — Propose combination ASO strategies for polygenic epilepsy clusters.
- [x] **029** — Identify antisense approaches that replicate the functional phenotype of a known protective LoF human variant.
- [x] **044** — For rare monogenic neurodegeneration gene A, design ASOs and estimate IND timeline feasibility.

## SMALL MOLECULE DISCOVERY (10/10 complete)

- [x] **045** — Identify FDA-approved molecules that are functionally antipodal to gene X LoF phenotype.
- [x] **046** — Rank small molecules in Quiver with strongest rescue effect in TSC2 neurons and BBB penetrance evidence.
- [x] **047** — Propose novel scaffolds structurally similar to compound cluster Y but predicted to improve selectivity.
- [x] **048** — Identify molecules that normalize E/I imbalance without suppressing intrinsic excitability.
- [x] **049** — For Nav1.7/Nav1.8 dual inhibition, propose a small molecule profile predicted to avoid cardiovascular liability.
- [x] **050** — Generate 3 novel chemical structures predicted to reverse disease phenotype cluster Z.
- [x] **051** — Identify repurposing candidates with prior Phase 2 CNS safety data and strong Quiver phenotype match.
- [x] **052** — Compare small molecule vs ASO strategy for gene X in terms of predicted PoS and rNPV.
- [x] **053** — Identify compounds in the atlas with disease-modifying phenotype but low historical clinical investment.
- [x] **054** — Rank 20 CNS compounds by predicted Phase 2 probability of success using Quiver + external data.

## COMBINATION THERAPY (5/5 complete)

- [x] **055** — Identify drug combinations that produce additive rescue in ASD-like functional cluster.
- [x] **056** — Propose combination strategies targeting excitatory neuron intrinsic excitability + inhibitory synaptic transmission.
- [x] **057** — Identify combination pairs that maximize phenotype rescue while minimizing toxicity signals.
- [x] **058** — For treatment-resistant depression, propose dual-mechanism combinations supported by Quiver embedding similarity.
- [x] **059** — Identify synergistic pairs for SCN2A epilepsy predicted to outperform monotherapy.

## TRANSLATIONAL & BIOMARKER QUESTIONS (5/5 complete)

- [x] **060** — For gene X, identify fluid biomarkers that align with the Quiver functional phenotype.
- [x] **061** — Which CRISPR perturbations correlate best with known EEG phenotypes in epilepsy?
- [x] **062** — Map Quiver excitability signatures to clinical symptom domains in schizophrenia.
- [x] **063** — Identify functional signatures predictive of cognitive improvement vs mood improvement.
- [x] **064** — For neurodegeneration gene Y, predict whether functional rescue implies disease modification or symptomatic effect.

## PORTFOLIO & CAPITAL ALLOCATION (5/5 complete)

- [x] **065** — Rank top 10 CNS programs by probability-adjusted NPV using Quiver + external competitive landscape.
- [x] **066** — Identify targets with high functional signal but low competitive saturation.
- [x] **067** — For gene X, estimate peak sales potential and regulatory risk profile.
- [x] **068** — Identify programs likely to fail in Phase 2 based on weak functional-human alignment.
- [x] **069** — Recommend which 3 programs should receive $50M allocation for maximum PoS improvement.

## STRATEGIC DUE DILIGENCE (5/5 complete)

- [x] **070** — For target X, how many companies are currently active and what stage are they in?
- [x] **071** — Identify adjacent pathway members that are more druggable than the current target.
- [x] **072** — Evaluate whether targeting gene X is likely to face safety liabilities based on historical toxicology.
- [x] **073** — Compare ASO vs small molecule approach for gene Y in terms of regulatory path and commercial scalability.
- [x] **074** — If we were building a first-in-class CNS franchise, which Quiver-derived target cluster provides the highest long-term strategic value?

## MECHANISM DISAMBIGUATION (10/10 complete)

- [x] **075** — For gene X, does the Quiver phenotype more closely resemble synaptic dysfunction or intrinsic excitability shift? Quantify effect sizes.
- [x] **076** — If we suppress gene Y by 50%, what compensatory pathways are predicted to activate?
- [x] **077** — Identify targets whose CRISPR phenotype is reversed by known anti-inflammatory drugs.
- [x] **078** — Which gene perturbations cluster with known rapid-onset antidepressants?
- [x] **079** — For target Z, is the functional phenotype likely upstream or downstream of mTOR signaling?
- [x] **080** — Identify genes whose perturbation worsens phenotype in rodent-supported neurons but improves in human-only systems.
- [x] **081** — Does the Quiver signature of gene X suggest disease modification or symptomatic modulation?
- [x] **082** — Identify targets that normalize spike waveform morphology but not firing rate — what does this imply mechanistically?
- [x] **083** — Rank perturbations that stabilize network synchrony without suppressing firing frequency.
- [x] **084** — Which CRISPR hits produce phenotype reversal only under synaptic assay, not intrinsic excitability assay?

## GENETICS + FUNCTION INTEGRATION (10/10 complete)

- [x] **085** — Identify genes with strong GWAS support but weak Quiver phenotype.
- [x] **086** — Identify genes with strong Quiver phenotype but no GWAS support — are these novel opportunities?
- [x] **087** — For protective LoF variant carriers in gene X, simulate expected electrophysiology profile.
- [x] **088** — Identify gene clusters converging on common functional embedding despite different genetic pathways.
- [x] **089** — Map ClinVar pathogenic variants onto Quiver perturbation space.
- [x] **090** — Identify genes where partial knockdown gives superior functional outcome compared to full knockdown.
- [x] **091** — Rank LoF vs GoF perturbations for gene Y by predicted clinical feasibility.
- [x] **092** — Identify polygenic convergence points in ASD functional clusters.
- [x] **093** — Which targets show strong effect in excitatory neurons but minimal effect in inhibitory neurons?
- [x] **094** — Identify genes whose perturbation mimics effect of top 3 antidepressant compounds.

## BBB, PK/PD, AND DRUGGABILITY (10/10 complete)

- [x] **095** — For top 20 Quiver targets in schizophrenia cluster, rank by BBB penetrance feasibility.
- [x] **096** — Identify targets predicted to require >80% CNS exposure to show effect.
- [x] **097** — Which targets are likely extracellular and antibody-accessible?
- [x] **098** — For gene X, simulate required brain exposure for functional rescue.
- [x] **099** — Rank top 30 hits by small-molecule ligandability.
- [x] **100** — Identify targets with structural homology enabling virtual screening acceleration.
- [x] **101** — For molecule cluster Y, predict metabolic liabilities.
- [x] **102** — Identify ion channels with strong functional signal but cardiovascular risk.
- [x] **103** — Compare oral small molecule vs intrathecal ASO for gene Z — which gives higher therapeutic index?
- [x] **104** — Identify targets with narrow therapeutic window based on Quiver amplitude-response curves.

## TOXICITY & SAFETY PREDICTION (10/10 complete)

- [x] **105** — Predict seizure risk liability for top 15 excitability-modulating compounds.
- [x] **106** — Identify gene suppressions predicted to cause hypoexcitability-related cognitive impairment.
- [x] **107** — Rank ASO sequences by predicted innate immune activation.
- [x] **108** — Identify compounds whose Quiver profile resembles known neurotoxic agents.
- [x] **109** — For target X, estimate likelihood of psychiatric adverse events.
- [x] **110** — Predict long-term synaptic destabilization risk.
- [x] **111** — Identify genes essential for neuronal survival in baseline state.
- [x] **112** — Which compounds reduce firing rate below physiological range?
- [x] **113** — Rank gene perturbations by risk of developmental toxicity.
- [x] **114** — Identify targets whose suppression induces compensatory upregulation of oncogenic pathways.

## COMBINATION & NETWORK STRATEGY (10/10 complete)

- [x] **115** — Identify synergistic gene-gene suppression pairs.
- [x] **116** — Predict dual-target small molecule profiles for ASD cluster.
- [x] **117** — Identify combinations that normalize E/I ratio without affecting total spike output.
- [x] **118** — Rank combinations by predicted reduction in Phase 2 failure.
- [x] **119** — Identify gene suppression + small molecule combination strategies.
- [x] **120** — For SCN2A epilepsy, simulate combination of partial knockdown + sodium channel modulation.
- [x] **121** — Identify pathway node where single intervention produces maximal downstream correction.
- [x] **122** — Predict multi-target strategy outperforming mTOR inhibition alone in TSC.
- [x] **123** — Identify hub genes whose perturbation collapses multiple disease clusters.
- [x] **124** — Rank top 5 two-target combinations for depression based on functional rescue + safety.

## RARE DISEASE & PRECISION (10/10 complete)

- [x] **125** — For monogenic epilepsy gene X, design ASO achieving 40% knockdown.
- [x] **126** — Identify genotype-specific rescue strategies.
- [x] **127** — Predict response heterogeneity across iPSC donor lines.
- [x] **128** — Identify targets for pediatric intervention with minimal developmental risk.
- [x] **129** — Map newborn screening targets to functional clusters.
- [x] **130** — Predict severity gradient from electrophysiology amplitude.
- [x] **131** — For ultra-rare gene Y, is there sufficient effect size to justify IND?
- [x] **132** — Identify targets suitable for orphan designation.
- [x] **133** — Rank rare disease targets by time-to-IND feasibility.
- [x] **134** — Identify CRISPR perturbations rescuing severe LoF phenotypes.

## COMMERCIAL & COMPETITIVE INTELLIGENCE (10/10 complete)

- [x] **135** — For target X, list all companies in Phase 1–3.
- [x] **136** — Identify white-space opportunities in schizophrenia MoA landscape.
- [x] **137** — For gene Y, is market saturation high?
- [x] **138** — Estimate peak sales for top 5 ASO programs.
- [x] **139** — Rank targets by exclusivity durability.
- [x] **140** — Identify MoAs crowded by generics.
- [x] **141** — Predict pricing potential for rare genetic CNS target.
- [x] **142** — Identify targets with low competition but high genetic support.
- [x] **143** — Compare mTOR vs adjacent pathway target commercialization potential.
- [x] **144** — For portfolio of 10 programs, optimize for $10B revenue in 10 years.

## PORTFOLIO OPTIMIZATION (10/10 complete)

- [x] **145** — If budget is $100M, allocate across 5 programs for max rNPV.
- [x] **146** — Kill one of these three programs based on data.
- [x] **147** — Rank current CNS portfolio by translational robustness.
- [x] **148** — Identify 3 programs to fast-track to IND.
- [x] **149** — Identify 3 programs to terminate preclinical.
- [x] **150** — Predict Phase 2 PoS uplift from adding Quiver validation.
- [x] **151** — For $50M investment, which cluster maximizes PoS delta?
- [x] **152** — Compare small molecule platform vs ASO platform ROI.
- [x] **153** — Optimize portfolio for 30% PoS improvement.
- [x] **154** — Simulate outcome if top 2 programs fail — what is backup plan?

## AI SELF-REFLECTION & UNCERTAINTY (10/10 complete)

- [x] **155** — Where is Quiver data insufficient to support this hypothesis?
- [x] **156** — Identify assumptions driving ranking.
- [x] **157** — Provide uncertainty intervals around predictions.
- [x] **158** — Which predictions rely most heavily on external data?
- [x] **159** — Where does transcriptomics contradict electrophysiology?
- [x] **160** — Identify predictions most sensitive to model drift.
- [x] **161** — Which targets have weak replication across plates?
- [x] **162** — What additional experiment would most increase confidence?
- [x] **163** — If we had 2x power in screen, which targets likely emerge?
- [x] **164** — Provide confidence score for ASO sequence prediction.

## EXTREME STRATEGIC PROMPTS (10/10 complete)

- [x] **165** — If you were CSO at Lilly, which 3 targets would you license?
- [x] **166** — If you were CSO at Roche, which disease-modifying target is most compelling?
- [x] **167** — For Pfizer scale, which target yields $5B+ potential?
- [x] **168** — For BioMarin rare focus, which gene is best monogenic candidate?
- [x] **169** — For Alnylam RNAi model, which targets are most suppressible?
- [x] **170** — For Regeneron antibody-first strategy, which extracellular CNS targets stand out?
- [x] **171** — If we aim to dominate CNS in 15 years, which cluster is franchise anchor?
- [x] **172** — Identify a first-in-class opportunity with minimal competition.
- [x] **173** — Identify a best-in-class improvement opportunity.
- [x] **174** — What is the single highest-value program in the entire Quiver atlas?

## MONOGENIC & RARE NEUROGENETIC DISORDERS (25/25 complete)

- [x] **175** — Find a clinically de-risked drug for SCN2A gain-of-function epilepsy using Quiver EP rescue ranking.
- [x] **176** — Identify ASO strategies for MECP2 duplication syndrome and rank by predicted functional rescue and toxicity profile.
- [x] **177** — Find small molecules that reverse SYNGAP1 haploinsufficiency phenotypes using multi-modal rescue scoring.
- [x] **178** — Identify clinically de-risked drugs for Fragile X Syndrome based on EP + transcriptomic rescue alignment.
- [x] **179** — For CDKL5 deficiency disorder, rank FDA-approved CNS drugs by EP rescue score.
- [x] **180** — Identify combination therapies for STXBP1 encephalopathy that maximize E/I balance restoration.
- [x] **181** — For KIF1A-associated neurological disorder, identify suppressor targets from Quiver's CRISPR atlas and rank druggability.
- [x] **182** — Identify allele-specific ASOs for SCN8A gain-of-function variants.
- [x] **183** — For Rett syndrome, find mTOR-adjacent mechanisms that provide safer alternatives to rapalogs.
- [x] **184** — Rank anti-seizure drugs by predicted long-term network stability in TSC2 KO neurons.
- [x] **185** — For Dravet syndrome (SCN1A LOF), identify drugs antipodal to inhibitory neuron dysfunction.
- [x] **186** — Identify synaptic stabilizers for Phelan-McDermid syndrome using Quiver E/I metrics.
- [x] **187** — For Angelman syndrome, identify rescue strategies targeting UBE3A pathway nodes.
- [x] **188** — Identify BBB-penetrant small molecules correcting CACNA1A-associated phenotypes.
- [x] **189** — Rank antisense vs small molecule strategies for GRIN2B-related neurodevelopmental disorder.
- [x] **190** — For PTEN hamartoma tumor syndrome with CNS involvement, identify EP rescue candidates with pediatric safety.
- [x] **191** — Identify drugs rescuing SHANK3 KO phenotypes using morphology + EP integration.
- [x] **192** — For DEPDC5 epilepsy, rank mTOR pathway modulators by rescue strength.
- [x] **193** — Identify repurposing candidates for SLC6A1 disorder using drug-gene antipodal embeddings.
- [x] **194** — Rank partial knockdown ASOs for gain-of-function ion channelopathies.
- [x] **195** — Identify drugs that normalize dendritic arborization in TSC1 models.
- [x] **196** — For FOXG1 syndrome, find multi-modal rescue candidates across EP and transcriptomics.
- [x] **197** — Identify small molecules correcting CNTNAP2-associated hyperexcitability.
- [x] **198** — Rank top 5 orphan-drug–eligible candidates for rare epileptic encephalopathies.
- [x] **199** — Identify disease-modifying vs symptomatic rescue candidates in Dup15q syndrome.

## NEUROPSYCHIATRY & CIRCUIT DISORDERS (25/25 complete)

- [x] **200** — Find clinically de-risked drugs for treatment-resistant depression using EP embedding rescue.
- [x] **201** — Identify combination therapies for schizophrenia targeting E/I imbalance and synaptic plasticity.
- [x] **202** — Rank mTOR-adjacent targets for major depressive disorder.
- [x] **203** — Identify rapid-onset antidepressant–like EP signatures in Quiver's compound atlas.
- [x] **204** — Find drugs rescuing chronic stress–induced EP phenotypes.
- [x] **205** — Identify novel mechanisms for bipolar disorder supported by gene + EP convergence.
- [x] **206** — Rank anti-psychotics by network normalization strength.
- [x] **207** — Identify E/I balancing drugs without sedation signatures.
- [x] **208** — For PTSD, identify compounds correcting hyperactive stress circuitry signatures.
- [x] **209** — Identify drugs correcting glutamatergic overdrive in schizophrenia models.
- [x] **210** — Rank novel NMDA-modulating scaffolds by rescue potential and safety.
- [x] **211** — Identify compounds reversing sleep disruption EP phenotypes.
- [x] **212** — For OCD, identify corticostriatal circuit modulators with clinical precedent.
- [x] **213** — Identify GABAergic drugs minimizing tolerance development risk.
- [x] **214** — Rank polypharmacy combinations predicted to outperform SSRI monotherapy.
- [x] **215** — Identify small molecules targeting synaptic vesicle cycling in psychiatric disease clusters.
- [x] **216** — Find Phase I–safe drugs antipodal to psychosis-related CRISPR signatures.
- [x] **217** — Identify anti-inflammatory agents correcting neuroimmune psychiatric signatures.
- [x] **218** — Rank cognitive-enhancing mechanisms supported by EP data.
- [x] **219** — Identify clinically safe drugs improving cortical oscillatory stability.
- [x] **220** — For autism spectrum disorder, identify convergent pathway nodes across genetic models.
- [x] **221** — Identify drugs correcting intrinsic excitability without suppressing plasticity.
- [x] **222** — Rank lithium-adjacent mechanisms by EP rescue performance.
- [x] **223** — Identify BBB-penetrant kinase inhibitors modulating psychiatric EP clusters.
- [x] **224** — Find drugs rescuing long-term adaptation deficits in depressive neuron models.

## NEURODEGENERATION (20/20 complete)

- [x] **225** — Find clinically de-risked drugs for early Alzheimer's disease using multi-modal rescue ranking.
- [x] **226** — Identify small molecules correcting tauopathy EP signatures.
- [x] **227** — Rank drugs reversing synaptic collapse in Parkinson's disease models.
- [x] **228** — Identify mTOR-independent autophagy enhancers for neurodegeneration.
- [x] **229** — For ALS, rank compounds stabilizing motor neuron firing.
- [x] **230** — Identify combination strategies for Huntington's disease.
- [x] **231** — Rank mitochondrial stabilizers by EP rescue strength.
- [x] **232** — Identify drugs correcting network desynchronization in dementia.
- [x] **233** — For FTD (MAPT mutation), identify antipodal drug signatures.
- [x] **234** — Identify compounds restoring adaptation metrics in aged neuron models.
- [x] **235** — Rank small molecules by predicted disease-modifying potential vs symptomatic.
- [x] **236** — Identify drugs correcting calcium dysregulation in neurodegeneration clusters.
- [x] **237** — Rank inflammation-modulating drugs by rescue in mixed neuron-glia models.
- [x] **238** — Identify drugs reducing pathological bursting in dopaminergic neurons.
- [x] **239** — For APOE4-associated dysfunction, identify network-normalizing compounds.
- [x] **240** — Rank top 5 FDA-approved drugs for repurposing in early AD.
- [x] **241** — Identify BBB-penetrant autophagy enhancers with human safety data.
- [x] **242** — For synucleinopathy, identify drugs reversing synaptic vesicle deficits.
- [x] **243** — Rank disease-modifying vs symptomatic candidates in Parkinson's.
- [x] **244** — Identify polypharmacology strategies correcting multi-pathway dysfunction.

## PAIN & ION CHANNEL DISORDERS (15/15 complete)

- [x] **245** — Identify small molecules targeting Nav1.7/Nav1.8 with minimal cardiovascular risk.
- [x] **246** — Rank ASO vs small molecule approaches for chronic pain.
- [x] **247** — Identify repurposing candidates for small fiber neuropathy.
- [x] **248** — Rank Phase II–safe sodium channel modulators by EP rescue.
- [x] **249** — Identify BBB-penetrant pain drugs with minimal sedation signature.
- [x] **250** — Find drugs antipodal to CRISPR Nav1.7 GOF phenotype.
- [x] **251** — Identify non-opioid analgesics supported by EP + genetics convergence.
- [x] **252** — Rank kinase inhibitors modulating nociceptive neuron firing.
- [x] **253** — Identify drugs correcting dorsal root ganglion hyperexcitability.
- [x] **254** — Rank compounds with analgesic potential and minimal tolerance liability.
- [x] **255** — Identify small molecules mimicking protective SCN9A LOF phenotype.
- [x] **256** — Rank pain drugs by safety margin in human neuron EP data.
- [x] **257** — Identify dual-mechanism pain combinations minimizing CNS depression.
- [x] **258** — Identify ion channel modulators predicted to reduce chronic neuropathic pain.
- [x] **259** — Rank clinically de-risked compounds for diabetic neuropathy.

## PLATFORM-LEVEL / MULTI-DISEASE STRATEGIC PROMPTS (15/15 complete)

- [x] **260** — Identify cross-disease convergent targets across epilepsy, ASD, and schizophrenia.
- [x] **261** — Rank top 10 CNS programs by Phase 2 probability uplift using Quiver validation.
- [x] **262** — Identify combination strategies maximizing rescue across 3 neurodevelopmental disorders.
- [x] **263** — Rank CRISPR suppressor hits by druggability and BBB feasibility.
- [x] **264** — Identify small molecules with multi-disease applicability based on embedding similarity.
- [x] **265** — Rank top 5 ASO programs ready for IND based on rescue + safety scoring.
- [x] **266** — Identify drug repurposing candidates with pediatric tolerability.
- [x] **267** — Rank novel scaffolds for CNS targeting using Quiver + chemoinformatics.
- [x] **268** — Identify drugs correcting both EP and morphology phenotypes.
- [x] **269** — Rank top 10 white-space CNS targets with low competitive density.
- [x] **270** — Identify combination therapies maximizing rescue with minimal toxicity signatures.
- [x] **271** — Rank candidates by composite rescue + clinical de-risking score.
- [x] **272** — Identify next experiments required to confirm top 3 ranked drugs.
- [x] **273** — For a $25M budget, prioritize 3 CNS programs based on rescue + feasibility.
- [x] **274** — Deliver a final prioritized list of clinically de-risked CNS programs across 5 diseases with mechanistic rationale and experimental plan.

## ASO SEQUENCE-LEVEL GENERATION PROMPTS (25/25 complete)

- [x] **275** — Design 5 gapmer ASO sequences targeting TSC2 mRNA that achieve 50–70% knockdown in human cortical neurons, maximize rescue of the TSC2 KO EP phenotype, and minimize predicted innate immune activation.
- [x] **276** — Generate allele-specific ASO sequences selectively suppressing the SCN8A R1872Q gain-of-function mutation without affecting wild-type transcript.
- [x] **277** — Design partial knockdown ASOs for MECP2 duplication syndrome targeting transcript regions that produce ~40% reduction while preserving physiological expression.
- [x] **278** — Generate splice-modulating ASOs that reduce inclusion of pathogenic exon variants in SCN2A while maintaining functional channel expression.
- [x] **279** — For SYNGAP1 haploinsufficiency, design ASOs targeting repressor elements to increase expression via antisense-mediated translational upregulation.
- [x] **280** — Design CNS-optimized ASO sequences targeting mTOR that reduce pathway hyperactivation but avoid full pathway suppression toxicity.
- [x] **281** — Generate 10 ASO sequences targeting Nav1.7 (SCN9A) optimized for intrathecal delivery, predicted BBB penetration, and minimal cardiotoxicity.
- [x] **282** — Design antisense oligonucleotides targeting GRIN2B gain-of-function variants using SNP-discriminating chemistry.
- [x] **283** — Generate ASOs targeting PTEN for controlled partial suppression, avoiding oncogenic liability predicted from transcriptomic models.
- [x] **284** — Design exon-skipping ASOs for a TSC1 truncating mutation to restore reading frame and evaluate predicted EP rescue.
- [x] **285** — Generate ASO candidates targeting SHANK3 transcripts that correct hyperexcitability signatures in excitatory neurons.
- [x] **286** — Design multi-target ASOs capable of co-modulating two convergent pathway genes implicated in ASD cluster embeddings.
- [x] **287** — Generate ASO sequences targeting DEPDC5 that reduce mTORC1 hyperactivation while preserving autophagy.
- [x] **288** — Design allele-specific ASOs targeting CACNA1A missense mutation without suppressing total calcium channel expression.
- [x] **289** — Generate antisense candidates targeting FOXG1 overexpression while minimizing developmental neurotoxicity signatures.
- [x] **290** — Design chemically modified ASOs (2'MOE, LNA mixmer, PMO variants) targeting TSC2 and rank by predicted CNS stability and toxicity.
- [x] **291** — Generate ASO sequences targeting SCN1A regulatory elements to enhance expression in inhibitory neurons.
- [x] **292** — Design intron-targeting ASOs that modulate alternative splicing in CDKL5 to restore functional protein production.
- [x] **293** — Generate 5 ASOs targeting KCNQ2 gain-of-function variants predicted to normalize firing rate without inducing hypoexcitability.
- [x] **294** — Design ASOs targeting inflammatory mediator IL-1β transcripts implicated in neuroinflammation EP signatures.
- [x] **295** — Generate allele-selective ASOs targeting mutant HTT transcript (Huntington's disease) while preserving wild-type allele.
- [x] **296** — Design ASOs targeting MAPT (tau) that reduce pathogenic isoform expression but preserve total tau needed for microtubule stability.
- [x] **297** — Generate antisense sequences targeting UBE3A antisense transcript (UBE3A-ATS) to reactivate paternal allele in Angelman syndrome.
- [x] **298** — Design combinatorial ASO strategies targeting both SCN2A and downstream excitability modulators predicted to outperform monotherapy.
- [x] **299** — For a given disease cluster (epilepsy, ASD, or TSC), generate a ranked list of 10 ASO sequences including: Exact nucleotide sequences (5'→3'), Predicted knockdown %, Off-target risk score, Immunogenicity risk, CNS stability prediction, EP rescue probability score, Recommended next validation experiments.
