# MAMMAL Exploration Plan

Phased plan to answer: **is MAMMAL useful for Quiver's work, and in what role?**

Each phase has explicit exit criteria. Failing a phase means stopping and writing up findings — don't push forward without evidence.

---

## Phase 0 — Instantiation (Day 1)

**Goal**: prove we can use the model before asking what it's good for.

**Tasks**:
- Coordinate with Matt + Margalise — find out what already exists, don't duplicate work
- Pull MAMMAL weights from HuggingFace (`ibm/biomed.omics.bl.sm.ma-ted-458m`)
- Get inference running locally (M3 Pro MPS) or via Margalise's interface
- Sanity check: encode a known compound (e.g., aspirin SMILES `CC(=O)OC1=CC=CC=C1C(=O)O`) → get back an embedding → verify it's a real-valued vector of expected dimension

**Exit criteria**: model loads, runs inference, returns embeddings without error.

**Output**: a working notebook in `notebooks/` titled something like `00_instantiation.ipynb` that anyone on the team can re-run.

---

## Phase 1 — Calibration on grounded ground truth (Day 2–3) [PRIORITY]

**Goal**: confirm MAMMAL works on real biology we know the answers to. This is the most important phase. The senior voice in the room will ask "is this real or hype" — the answer must be empirical, not paper benchmarks.

**Tasks**:

1. **Jernabix → Nav1.8** binding prediction (called out by name in the meeting):
   - Look up Jernabix SMILES (also known as JZP-110? — verify with team; if unclear, ask Matt/David)
   - Look up Nav1.8 protein sequence (UniProt: Q9Y5Y9, gene SCN10A)
   - Feed both into MAMMAL's drug-target interaction head
   - Compare predicted binding affinity to known experimental KD/IC50

2. **5–10 more known drug-target pairs** from Quiver's prior work (consult Matt/David for which pairs we have ground truth on):
   - Compute predicted affinity for each
   - Compute Spearman / Pearson correlation between predicted and experimental affinity

3. **Negative controls**:
   - 5–10 unrelated drug-protein pairs (randomly sample SMILES × sequences from non-target combinations)
   - Confirm low predicted affinity

4. **Comparative benchmark**:
   - Pick one specialized DTI model (DeepPurpose, MolTrans, or similar — Matt to advise)
   - Run on the same pairs
   - Compare correlation / ranking metrics

**Exit criteria** (see `success_criteria.md` for full pass/fail grid):
- **Pass**: predicted affinities correlate with known affinities on the small ground-truth set; Jernabix → Nav1.8 specifically scores higher than random pairs
- **Fail**: no correlation, or known active pairs score lower than random pairs → stop, write up, do not proceed to Phase 2

**Output**: `results/phase1_calibration.md` with the ground-truth set, predictions, comparison to specialist, and a clear pass/fail call.

---

## Phase 2 — Real Quiver use cases (Week 1–2)

**Goal**: test MAMMAL on the actual workflows the meeting proposed. Only proceed if Phase 1 passes.

Three named tests, ranked by ease and information value:

### 2a. Hit-list expansion (easiest, most direct value)

- Take a real Quiver top-50 from a screen (Matt to provide the compound list)
- Use MAMMAL's SMILES similarity (compound embeddings, nearest neighbors) to expand the set to 100–500 candidates
- Filter by predicted BBB penetration (MAMMAL has this as a task head)
- Filter by predicted clinical toxicity (MAMMAL ClinTox head)
- Return top 10–20 survivors
- Compare against what a Quiver team member would have ranked manually

### 2b. TSC top 20 nominated genes (high stakes, real program)

- Get the TSC top-20 gene list (Matt / TSC program lead)
- For each gene → get its protein sequence
- Run MAMMAL drug-target interaction across a reasonable candidate small-molecule library (FDA-approved + DrugBank + Quiver's DFP library)
- Rank candidates by predicted binding
- Check whether known TSC drugs (rapamycin, everolimus, MTOR-pathway adjacent) appear in the top 100 / top 10

### 2c. CRISPR-N 1400 genes systematic interrogation (hardest, biggest payoff)

- For the subset of CRISPR-N genes that look like disease targets (Mahdi/team to flag)
- Run MAMMAL to nominate either small-molecule inhibitors or ASO candidates
- Cross-reference with KG-derived druggability priors (Caitlin's graph) if available

**Exit criteria** (see `success_criteria.md`):
- **Pass**: at least 2c gives interesting overlap with prior knowledge; expanded hit lists are usable (not all filtered out as toxic)
- **Fail**: results are noise / known biology missing → stop, write up findings

**Output**: `results/phase2_use_cases.md` per test, with concrete examples and judgment calls.

---

## Phase 3 — Comparative benchmarking (Week 2)

**Goal**: test the "specialized may beat generalist" concern. Decide what MAMMAL is genuinely better at than alternatives.

**Tasks**:

1. **MAMMAL vs Proton** (Zitnik lab, CNS-specific): run both on the TSC use case from Phase 2b. Which produces a more useful ranking?
2. **MAMMAL vs specialized DTI model** on the Phase 1 calibration set (already partially done in Phase 1).
3. **MAMMAL alone vs MAMMAL + KG hybrid**: take Caitlin's KG, use MAMMAL embeddings to enrich a query, see if the hybrid finds things neither alone would.

**Exit criteria**:
- **Pass**: MAMMAL is at least competitive with specialists on cross-modal tasks; clear win condition emerges (either MAMMAL is the right tool, or it's not, with evidence)
- **Fail**: specialists dominate on every test → MAMMAL is downstream enrichment only, not core infrastructure

**Output**: `results/phase3_comparative.md` with head-to-head numbers.

---

## Phase 4 — Sapphire integration prototype (only if Phases 1–3 succeed)

**Goal**: prototype the "MAMMAL as latent space layer of Sapphire" architecture.

**Tasks**:
- Get a slice of Caitlin's Neo4j KG (some manageable subgraph, e.g., 100 genes + 100 drugs + their edges)
- Compute MAMMAL embeddings for every gene (via protein sequence) and drug (via SMILES) in the subgraph
- Write embeddings as node properties on the Neo4j nodes
- Build the simplest hybrid query: "Find drugs in pathway X whose embedding is closest to drug Y"
- Demo it — does it work? Does it return sensible results?

**Exit criteria**:
- **Pass**: hybrid query returns results that make sense manually
- **Strong pass**: query surfaces something neither pure-KG nor pure-MAMMAL alone would find
- **Fail**: integration breaks or results are noise

**Output**: working prototype + writeup. This is the proof of concept that would make MAMMAL part of the Sapphire architecture.

---

## What NOT to do

- **Don't feed traces into MAMMAL.** No trace modality. Trace is V1-T's job.
- **Don't fine-tune day 1.** Off-the-shelf first. Fine-tuning is a Phase 5 question after we know if it's worth it.
- **Don't replace specialized models without head-to-head benchmarking.**
- **Don't over-promise on Angelini before Phase 1 is done.** Angelini scoping meeting happens next week with James, Caitlin, Mahdi — don't precommit deliverables before we have calibration data.
- **Don't push past a failing phase.** If Phase 1 fails, stop. Write up. Don't waste time on Phase 2 with a broken foundation.

---

## Reporting

- Update Notion project page (https://www.notion.so/36ee87e515f181289939ee64294ab5e8) at the end of each phase
- 6/4 weekly check-in: report Phase 1 calibration results
- 6/11 weekly check-in: report Phase 2 use case results
