---
name: emet-prompting
description: How to prompt EMET (BenchSci) for maximum breadth and balanced for-vs-against evidence — not just literature. Use whenever you write an EMET query (the orchestrator's emet-live task, the Chrome worker, or a manual run). Companion to emet-runner (the Playwright driver) + emet_capabilities.md (the tool surface).
---

# emet-prompting — getting EMET's full breadth + balanced evidence

EMET (BenchSci BEKG) is **not a literature search.** It is an agentic biomedical knowledge engine:
**9 workflows · 22 capabilities · ~70 data sources** (genetics, variants, expression, perturbation/CRISPR,
pathways, structure, ML/ESM-2, clinical, cheminformatics). A prompt that asks only for "papers on X" leaves
~90% of that on the table. Two things make an EMET prompt good: **breadth** (pull every relevant evidence
modality) and **balance** (evidence *for* AND evidence *against* — the risks that actually sink a target).

## The core frame: evidence FOR vs evidence AGAINST
A prediction is only as good as the counter-evidence you went looking for. *"When making predictions you have
to weigh evidence in favor vs evidence opposed — maybe the target also activates inflammation, maybe it does a
billion things in the cell so knocking it down breaks everything, maybe it's toxic, maybe it's not even
expressed."* For any target/hypothesis, EXPLICITLY ask EMET for **both sides**:

**FOR — does it support the hypothesis?**
- Genetic association — GWAS Catalog, ClinVar, OpenTargets, Genebass, Pan-UK Biobank.
- Causal / mechanistic — pathway position, perturbation-rescue, directionality of effect.
- Right place — expression in the relevant tissue / cell type (CNS, neurons, the disease cell).

**AGAINST — what would make it a bad target? (ask for each BY NAME — these are easy to miss)**
- **Pleiotropy / multifunctionality** — "does it do a billion things?" → GO-term breadth, # of pathways
  (Reactome / STRING / SIGNOR), hub-ness. A hub gene's knockdown has broad collateral effects.
- **Inflammation / immune liability** — is the target tied to activating inflammation or immune signaling?
  (pathway + literature)
- **Toxicity** — on-target / target-based tox, safety flags, post-market signals (OpenFDA/FAERS) for known
  modulators, PGx. (Safety & Toxicity capability; Drug Safety / Safety Assessment workflows.)
- **Essentiality / dependency** — is knockdown lethal or broadly fitness-affecting? DepMap, CRISPR screens,
  common-essential lists. A pan-essential gene is not a viable knockdown target.
- **Expression gap** — is it even expressed in the relevant CNS tissue / cell type? GTEx, Protein Atlas,
  single-cell (CellxGene / Human Cell Atlas). Not expressed → the mechanism can't operate.
- **Constraint** — gnomAD pLI / LoF-intolerance: an LoF-intolerant gene is risky to knock down.

Tell EMET to **weigh both sides and flag contradictions** — never accept a one-sided "supports the target."

## How to prompt (the recipe)
1. **Thinking = Thorough** — triggers the agentic Research Plan (loads Skills, queries DBs in parallel).
   Use it for any substantive evidence question (Balanced/Quick are for quick lookups).
2. **Name the workflow** that fits the question:
   - Target Validation — genetic + druggability + expression + safety for a target.
   - Safety Assessment / Drug Safety — deep tox / pharmacovigilance.
   - Pathway Analysis — network, enrichment, **pleiotropy / hub-ness**.
   - Quantitative Evidence — TPM, mutation burden, constraint, dependency, survival (effect sizes).
   - Target Modulation — perturbation data + drug-response profiles.
   - Database Q&A — one specific cross-validated fact.
3. **Demand breadth explicitly** — *"Don't limit to literature. Pull genetic, expression, perturbation/
   dependency (DepMap/CRISPR), pathway, structural, and clinical evidence and reconcile across them."*
4. **Demand both sides** — *"Give evidence in favor AND evidence against / risks: pleiotropy, inflammation,
   toxicity, essentiality, expression, constraint. Flag contradictions."*
5. **Stringency** — *"use high-stringency thresholds"* for a go / no-go call.
6. **Quantitative when relevant** — ask for TPM, pLI, dependency scores, effect sizes, p-values.
7. **Cite or drop** — every claim carries a PMID / DOI / DB record; abstain rather than invent.
8. **Public identifiers ONLY** — gene symbols, published SMILES, disease terms, trial IDs. NEVER Quiver
   internal scores, candidate IDs (`QS…`), or EP/CRISPR/functional traces. (Several EMET capabilities accept
   proprietary inputs — never feed them our data; the harness `data_boundary` guard enforces this.)

## Templates
**Target / rescue validation (balanced, full breadth):**
> Run the Target Validation workflow for **<GENE>** in **<disease>**, thinking=Thorough, high-stringency.
> Does <GENE> <hypothesis — e.g. "rescue the TSC2-KO / mTORC1-hyperactivation phenotype when knocked down">?
> Use your FULL toolset, not just literature: genetic association (GWAS/ClinVar/OpenTargets), expression in
> CNS/neurons (GTEx/Protein Atlas/single-cell), perturbation & dependency (DepMap/CRISPR screens/Perturbation
> Catalogue), pathway position & pleiotropy (Reactome/STRING/SIGNOR + GO-term breadth), structure
> (PDB/AlphaFold), and clinical/safety (ClinicalTrials.gov/FAERS). Give evidence FOR **and** evidence AGAINST
> — explicitly check pleiotropy, inflammation/immune liability, toxicity, essentiality (is knockdown lethal?),
> expression gaps, and gnomAD constraint. Flag every contradiction. Cite each claim (PMID/DOI/DB record).

**Safety / liability deep-dive:**
> Run the Safety Assessment workflow for **<GENE>**, thinking=Thorough. Surface on-target toxicity, tissue
> expression breadth (off-tissue risk), essentiality/dependency, immune/inflammatory associations, PGx, and
> post-market signals (FAERS) for known modulators. Cite each.

## Breadth checklist (before sending)
- Did the prompt invite **≥3 modalities beyond papers** (genetics / expression / perturbation / pathway /
  structure / clinical)?
- Did it ask for **AGAINST-evidence** (pleiotropy, inflammation, toxicity, essentiality, expression, constraint)?
- Thorough + a named workflow + stringency set?
- **Public IDs only**? Cite-or-drop? If any answer is "no," fix the prompt before sending.

## See also
- `.claude/skills/emet-runner/SKILL.md` — drives EMET via Playwright (the mechanics of one run).
- `.claude/skills/emet-chrome-worker/SKILL.md` — the persistent Chrome worker (the live file queue).
- `sapphire-cascade/emet_capabilities.md` — the full tool surface; `emet_protocol.md` — the operating protocol.
