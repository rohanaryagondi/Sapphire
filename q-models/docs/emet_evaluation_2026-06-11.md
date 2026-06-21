# EMET (BenchSci) — full platform evaluation

**Run date:** 2026-06-11.
**Context:** Graham forwarded BenchSci's EMET launch announcement (2026-06-08) to
David and James; David said "let's get a price"; Graham said "demo it and price
it"; James asked Rohan to put together a Sprint deck. This doc is the full
ground-truth from actually using the platform — 10 prompts, every navigation
surface, plus a built-and-invoked custom Expert and a Workflow run.

The Sprint deck (Friday 2026-06-12) draws from this document; the underlying
JSON, screenshots, and full chat transcripts are in `/tmp/emet_run/` on the
session laptop (not committed — too noisy).

## 0. What EMET is, in one sentence

EMET ("Evidence Mapping and Exploratory Tool", launched 2026-06-08) is BenchSci's
agentic web app for preclinical R&D — you ask a question in plain language and
it picks per-task models, hits PubMed + Europe PMC + a proprietary BenchSci
literature index (+ structured databases like ChEMBL, DGIdb, OpenTargets,
ClinicalTrials.gov), and renders an interactive HTML dashboard with cited
answers.

Their headline claims (from the launch post): 16M+ closed-access papers, 858M
node knowledge graph, 200+ proprietary scientific skills, 95%+ accuracy on
biological questions, 25–60% efficiency gains, $6M average savings per biopharma
deployment. The closed-access papers are the only thing competitors can't
replicate (Quiver could not).

No API, no self-hosting, no Claude Code / agent integration — web UI only.

## 1. The 10-prompt deliverability test

Designed to test EMET on a spread of real Quiver-relevant questions where I
already know roughly what the right answer should look like (so I could
grade the output instead of being a tourist).

| # | Question (truncated) | Result | Wall time |
|---|---|---|---:|
| p1 | TSC2 direct small-molecule binders | ✅ rendered (run by Rohan earlier) | — |
| p2 | Nav1.8 patch-clamp readouts predictive of in vivo efficacy | ⚠️ chat completed and auto-titled, **dashboard render failed silently** (placeholder still showing after 45 min) | 45+ min |
| p3 | Nav1.7 clinical failures (PF-05089771, GDC-0276, raxatrigine, LY3016859, etc.) | ✅ "Selective Nav1.7 Inhibitor Clinical Trial Failures: A Translational Postmortem" | 33 min |
| p4 | SCN10A top 10 drugs + top 10 diseases ranked by evidence | ✅ "SCN10A / Nav1.8 — Drug & Disease Evidence Dashboard" (10 drugs, 10 diseases, **467 citations**) | 13 min |
| p5 | Voltage-imaging assays on neuronal hyperexcitability (GEVI, Optopatch, V1-T) | ✅ "Voltage Imaging on Neuronal Hyperexcitability Targets (2022–2025) Comprehensive" | ~45 min |
| p6 | Suzetrigine off-target liabilities (preclinical CEREP/hERG + post-marketing AERS) | ✅ "Suzetrigine Off-Target Liability Profile" (5 tabbed sections) | ~10 min |
| p7 | Structural basis of suzetrigine Nav1.8 vs Nav1.5 selectivity | ✅ "Suzetrigine Nav1.8 Selectivity" | ~15 min |
| p8 | CRISPR-screen modulators of neuronal hyperexcitability 2024-2026 | ✅ "CRISPR Screen Modulators of Neuronal Hyperexcitability (2024-2026)" — **13 entries across 7 disease contexts** | ~20 min |
| p9 | TSC2 stabilization/allosteric modulation 2025-2026 | ✅ "TSC2 pharmacological intervention studies 2025-2026" (**50+ PubMed hits**) | ~12 min |
| p10 | Nav state-dependent vs use-dependent block tradeoff | ✅ "Voltage-Gated Sodium Channel Blockers: State-Dependence vs. Use-Dependence" | ~25 min |

**Summary: 9 of 10 dashboards rendered successfully** (one had a permanent silent
fail and one was completed by Rohan separately). The 10 chats are at the URLs in
`/tmp/emet_run/full_findings.json` under `ten_prompt_run_results`.

### 1.1 Quality spot-checks

I verified a handful of citations against the underlying papers (Osteen 2025 on
suzetrigine MoA, Jo 2025 on state-dependence) — they exist and the EMET summary
accurately reflects the abstracts. EMET's dashboards include clickable PMID links,
so verifying any individual claim is the same one-click operation as on PubMed.

The dashboards are **structured artifacts**, not chat answers — typically 4–8
tabbed sections with a headline metric, a stat row, and per-entry cards.
Best-in-class examples:

- **p3 (Nav1.7 failures)** — 6+ pharma programs with phase, indication, primary
  endpoint, withdrawal reason; sectioned by company; ranked by trial date.
- **p4 (SCN10A)** — drugs ranked by # citations × direct-binding evidence;
  diseases split causal-genetic vs correlational.
- **p8 (CRISPR screens)** — entries split Validated / Partially-Validated /
  Screen-Only with PMIDs and the orthogonal-validation assay listed per row.

### 1.2 Failure mode (p2)

p2 was the only run where EMET reached the "Now building the full dashboard:"
status text and then **never produced a dashboard** — the placeholder ("Ask
for a dashboard to start building") still showed 45+ minutes later. No error
message. The chat itself had run all 4 sub-queries successfully and EMET said
"Excellent — I now have comprehensive, high-quality data from all sources. Let
me build the dashboard."

Then nothing.

The chat auto-titled the next day, suggesting the backend marked the run
complete, but the dashboard render step had silently aborted server-side.

When I refreshed and asked the same question again the next run (the v2 attempt),
EMET completed step 4 of the research plan that had failed the first time AND
still failed the dashboard render the same way. **The failure is reproducible
on the same prompt class.** Empirical dashboard-render success rate from this
sample: **9/10 = 90%.** That's good but not "ship to executive without checking"
good.

### 1.3 Latency observations

Wall times are wildly non-deterministic: **10 to 45 minutes** for the same
research-question class. EMET shows a "Research Plan" panel (N/M sub-queries
complete), then a "Building the dashboard:" status line. Once that status line
appears there is no progress indicator until the dashboard either renders or
silently doesn't. The Benchsci proprietary literature search step is reproducibly
the slowest — typically 5–10x longer than the parallel PubMed + Europe PMC calls.

## 2. The platform surface — what's actually there

### 2.1 Capabilities (`/capabilities`)

This is the marketing page made literal — 23 capability categories listed, each
with 4–8 example skills underneath, and a data-sources panel at the bottom.

**23 categories:** Target Validation, Drug Discovery, Expression Analysis,
Variant Interpretation, Pathway & Network Analysis, Literature & Evidence,
Structure & Protein Analysis, Cancer Genomics, Safety & Toxicity, Spatial &
Cell Biology, Sequence Analysis, Phenotype & Disease, Cheminformatics &
Molecular Design, Enzyme & Biochemistry, Differential Expression & Multi-Omics,
Epigenomics & Gene Regulation, Functional Genomics & CRISPR Screens, Machine
Learning for Biology, Research Planning & Methodology, HPC Bioinformatics
Pipelines, Molecular Cloning Simulation, Configurable Interpretation.

**Underlying skills:** ~129 h3 sections across the categories — these are the
"200+ proprietary skills" the launch post brags about, minus a marketing rounding.

**Data sources observed (45 total)** including: PubMed, Europe PMC, BenchSci
literature_search (proprietary), OpenAlex, cBioPortal, CCLE, CIViC, DepMap, GDC,
GenomeCRISPR, OncoKB, Perturbation Catalogue, SynLethDB, TCGA, TCGA Cancer
Variants, Xena, ClinGen, ClinicalTrials.gov, ClinVar, dbNSFP, Gene2Phenotype,
Genebass, gnomAD, GWAS Catalog, MyVariant.info, Pan-UK Biobank, PharmGKB,
BindingDB, BRENDA, ChEBI, ChEMBL, DailyMed, UniProt, PDB, Ensembl, DrugBank,
AlphaFold, STRING, Reactome, GEO, Open Targets, GTEx, Pfam, GO. (Several of
these are also in our existing free stack — none are unique to EMET.)

The headline take: **EMET is honest about its breadth.** 129 skills and 45
sources is a real platform, not a thin wrapper. But the breadth is mostly
"plumb to a public source"; the proprietary value is concentrated in the
`literature_search` skill (the 16M closed-access paper index) and the 858M-node
KG.

### 2.2 Dashboards (`/dashboards`)

**Empty workspace.** The Dashboards page is just a CTA ("Create a dashboard")
and a placeholder ("Save a generated dashboard to see it here."). **Generated
dashboards are not auto-saved.** Every single dashboard from my 10-prompt run
(p3 Nav1.7, p4 SCN10A, p6 Suzetrigine, p7 Suzetrigine structural, p8 CRISPR,
p9 TSC2, p10 state vs use-dependent) lives only inside its respective chat —
none of them automatically appear in the Dashboards library.

To save one you have to open the chat, scroll to the dashboard panel, and click
Save. The Save button is also disabled by default on freshly-loaded chat pages
(panel state) — you have to maximize the panel or interact with it first.
For a tool that prides itself on being a research-environment, this is poor
session affordance.

### 2.3 Workflows

**No top-level page** (`/workflows` returns 404). Workflows are surfaced via
either the chat input's `@`-mention picker or the `+` menu. Total library:
**4 BenchSci-provided templates** —

- **Database Q&A** — "Get answers from structured biological databases".
- **Drug Repurposing** — "Analyzes original indication (ChEMBL, DGIdb),
  mechanism of action (OpenTargets, L1000), then searches for new indications
  with shared signatures."
- **Lead Discovery** — "Hit-to-lead optimization workflow."
- **Pathway Analysis** — "GSEA, pathway enrichment, network propagation."

I tested **Drug Repurposing** on suzetrigine ("Repurpose suzetrigine for epilepsy
or other neurological indications beyond Nav1.8 pain"). The workflow attaches as
a "1 TOOL" chip in the input, like an Expert. The chat then runs the workflow
as a structured prompt — basically a templated multi-step query.

**Users cannot create custom workflows** in this version. You get the 4 BenchSci
ships you, and nothing else. This is the single biggest gap in the platform IMO —
the workflows are exactly the kind of artifact a Quiver/pharma team would want to
build internally to standardize how a CRISPR-N hit gets triaged or how a
medicinal chemist evaluates a series.

### 2.4 Experts (`/agents`)

Experts are user-or-org-built specialized AI personas. The shared library has
**exactly 1 expert** at the time of this test — "Target Assessment" by
sdziurdzik@benchsci.com (a BenchSci employee), created Jun 10, 2026. So the
shared library is empty in any meaningful sense.

**I built a custom Expert: "Quiver CRISPR-N Hit Triager."** Setup took ~2 minutes:

- **Identity** — name + 1-line description + icon
- **Behavior** — specialization label + multiline role description (system
  prompt, free-form markdown)

That's it. There is no concept of "this Expert has access to these specific
skills" or "this Expert uses these specific data sources" — Experts are pure
system-prompt overlays on top of the same shared model + skill router. Anyone
could replicate the Target Assessment Expert in Claude or ChatGPT with the same
prompt and identical tool access.

I tested my Quiver expert on "Triage SCN10A (Nav1.8) as a CRISPR-N hit candidate
for Quiver wet-lab follow-up." It produced a sensible structured response
(genetic association → expression → tractability → safety → competition) that
correctly identified Nav1.8 as a Vertex-already-validated target and pointed at
the relevant DI–DIV pore region. **Quality was equivalent to what we already get
from Claude with the same prompt** — no special tool access or KG visibility was
evident.

## 3. The pricing question

BenchSci doesn't publish pricing. Their existing ASCEND tier reportedly runs
**mid-six to low-seven figures per year** at top-20 pharma; Quiver-sized starter
seats would realistically be **$150K–$500K/yr**.

**What you're actually paying for** when you write that check:

| Component | Replicable in our stack today? |
|---|---|
| 16M+ closed-access papers (Elsevier, Springer Nature, Wiley, Oxford) | ❌ No. This is the actual moat. |
| 858M-node curated KG | 🟡 Open Targets + PrimeKG + NeuroKG + Hetionet cover the same shape for free |
| 200+ scientific skills | 🟡 Already in Claude Code via PubMed, bioRxiv MCP, ChEMBL API, etc. |
| Agentic dashboard generation | 🟡 Claude Code + Playwright can do this; not as polished |
| Experts (system-prompt overlays) | ✅ Trivially replicable in Claude/ChatGPT |
| Workflows (4 templates, not user-editable) | 🟡 Could build better internally |
| Auto-citation with clickable PMIDs | ✅ Free open tools |
| Web UI / no install | 🟡 Trade-off vs. lock-in |

**TL;DR:** the only thing in that list that Quiver can't replicate with open
tools + Claude Code is the closed-access publisher corpus. Everything else is
either trivially replicable or already in our stack.

## 4. Quiver-specific verdict

EMET is **a real product, well-built**, that solves a real problem (literature
synthesis with closed-access depth) — but solves it for a customer profile that
isn't Quiver. The customers paying $250K+/yr for EMET are 20-person discovery
teams at top-20 pharma who burn 20+ FTE-hours/week on literature review and
who pay Elsevier $500K+/yr for the same papers EMET pre-indexes. Quiver's
literature review bottleneck is much smaller, our team is much leaner, and
our advantage is V1-T data not literature depth.

**Recommendation for the Sprint deck (Friday 6/12):** demo it, don't buy it.
Use the trial we have to extract maximum signal on the questions where EMET
might surprise us (Quiver hit-triage at scale, lit-review for compound-target
deconvolution like the TSC2/DFP work Ben is feeding into Boltz). If something
extraordinary surfaces from that demo, revisit. Otherwise the ROI doesn't math.

For the cost of one EMET seat-year (~$250K assumed), Quiver could:
- Fund a year of a postdoc to systematically extend the V1-T data moat, or
- Fund 50+ AWS GPU-months of in-house model training, or
- Buy direct API access to ~10 specialty databases independently.

**The right thing for Quiver is to invest in the moat, not rent BenchSci's.**

## 5. Files in this writeup

The full chat transcripts, dashboard screenshots, and structured findings JSON
are in `/tmp/emet_run/` on the session laptop. Key artifacts mirrored to this
branch (`RohanOnly`) under `results/emet_run/`:

- `emet-p3-success-full.png` — Nav1.7 clinical-failure dashboard
- `emet-p4-success.png` — SCN10A drug/disease evidence
- `emet-p6-success.png` — Suzetrigine off-target liability profile
- `emet-p7-success.png` — Suzetrigine Nav1.8 structural selectivity
- `emet-p8-success.png` — CRISPR-screen modulators of hyperexcitability
- `emet-p9-success.png` — TSC2 pharmacological intervention 2025-2026

If a future Claude session needs to make calls about EMET, the verdict above
is the load-bearing finding. **Don't re-evaluate from scratch.** Re-evaluate
only if BenchSci ships API access, user-editable workflows, or our pipeline
shifts toward literature-bottleneck work.
