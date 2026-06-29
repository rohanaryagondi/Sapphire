# 02 — ASO Design (the worked example of a design-class tool)

> Source: Quiver's `basic_design_template` pipeline (steps 00–07). This doc maps that pipeline onto the
> [seam pattern](01_TOOL_SEAM_PATTERN.md) and flags the open questions it forces. Status: 🔵 PLANNED.
> The acute-tox step is already 🟢 BUILT as `aso-tox` — ASO Design *composes* it.

## 1. What it is
Given a **target gene symbol**, ASO Design produces a ranked set of **gapmer antisense oligonucleotide
candidates** (default 20-mers), each annotated with thermodynamics, human/cyno off-target risk, and
predicted CNS toxicity, then filtered to a shortlist (the top ~20 spread across the transcript). It is the
firm's first true **design-class** tool: it *makes an asset*, it doesn't just gather evidence.

It is also the heaviest tool we've integrated: **multi-stage, multi-environment, and hours-long** (the
off-target step alone is ~3 hrs on EC2 for ~11k gapmers). It must be an `aws-async` seam, never inline.

## 2. The pipeline (stages → environment → what each emits)

| # | Stage | Tool / lang | Environment | Runtime | Emits |
|---|---|---|---|---|---|
| 01 | Identify + download sequences | NCBI `datasets` CLI | CLI/network | mins | `target_transcript.fasta` (MANE Select) + human/cyno RefSeq isoforms |
| 02 | Initial annotation (gapmer tiling) | R (`.Rmd`) | R | mins | `initial_annotation.csv`, `aso_candidate.fa`, `aso_candidate.tsv` |
| 03 | Thermodynamics | **OligoWalk** (RNAstructure 6.1) | **Docker** | mins | `default_DNA_20mers_noheader` (ΔG, DNA chemistry, struct-free) |
| 04 | Human off-target | **bowtie2** + samtools + py | **EC2** (50–100 GB) | **~3 hrs** | `hsv2_allspliced_summary`, `hsv2_allunspliced_summary` (min edit dist, max aln length, # disqualifying alns per ASO) |
| 05 | Tox prediction | **GBR model** (the `aso-tox` seam 🟢) | python+sklearn | secs | `target_tox_predictions.csv` (Hagedorn + Zhang-GBR scores) |
| 06 | Full annotation (merge) | R (`.Rmd`) | R | mins | `full_annotation.csv` (thermo + off-target + tox) |
| 07 | Filter + select | R (`.Rmd`) | R | secs | `annotation_filtered.csv`, `top_candidates.csv` (~20 ASOs) |

Reference data the pipeline needs: MANE GTF/GFF (~8–9 MB each), human + cyno RefSeq, bowtie2 transcriptome
indices (spliced + unspliced — the large ones drive the EC2 storage + time).

## 3. Mapping onto the seam contract

- **(a) Registry entry** (`agents.json`): `id: "aso-design"`, `kind: "aws-async"`, `class: "design"`,
  `provenance: "aso-design"`, `activates_when:` the engagement asks to design ASOs for a gene (or synthesis
  concludes a gene target is worth pursuing), `schema:` the design-asset bundle.
- **(b) Data boundary:** inputs are a **gene symbol** + public transcript **sequences** — all public, all
  fine to send to AWS. No Quiver internal scores cross. ✅ clean.
- **(c) Execution tier:** `aws-async`. Reuse the **Q-Models launcher** pattern (tagged `Sapphire` EC2,
  create-only + ledger, teardown-by-ledgered-id, idle/hard-cap watchdogs). The orchestration challenge is
  that this is **multi-stage across environments** (CLI → R → Docker → EC2 → R), not a single eval — see §4.
- **(d) Output envelope (design bundle):**
  ```
  { asset_type: "aso-gapmer", target: "<GENE>", run_ref: "<ledgered job id>",
    candidates: [ { id, sequence, position, dG, offtarget:{min_edit, max_aln, n_disqual},
                    tox:{hagedorn, gbr, label} } … ],   // from top_candidates.csv
    provenance: "aso-design", captured_at, notes }
  ```
  Plus **per-candidate facts** that re-enter Bucket 1 (each candidate's tox + off-target become dossier
  facts the partners can weigh).
- **(e) Honest degradation:** if AWS/creds/Docker/refs are unavailable → abstain with the reason; never emit
  fabricated candidates. A captured scenario (one real run for one gene) lets the canned path demo it $0.

## 4. The orchestration problem (this tool's hard part)
Unlike `aso-tox` (one subprocess) or a Q-Models GPU eval (one `*_eval.py`), ASO Design is a **DAG across
environments**. Two viable shapes — pick one in [`03 §D3`](03_OPEN_DECISIONS.md):
- **(i) One bundled EC2 job** — bake R + OligoWalk(Docker-in-Docker or native RNAstructure) + bowtie2 +
  refs into one AMI/image; the seam launches it, runs 01→07 end-to-end on the box, retrieves
  `top_candidates.csv`, tears down. Simplest seam (one launch/retrieve), heaviest image.
- **(ii) Staged seam** — the seam runs the light stages locally (01 download, 02/06/07 R, 05 tox) and only
  the heavy off-target (04) on EC2. More moving parts, less compute, but the seam has to sequence stages.
Given the seam contract favors "one launch → one envelope," **(i) is the recommended v1** (treat the whole
pipeline as one ledgered AWS job), with (ii) as an optimization later.

## 5. The design loop in action (why this matters for the firm)
```
  "design ASOs for SCN9A"  ─▶  Engagement Lead (class=design)
        ▶ ASO Design (aws-async)  ─▶  20 candidate gapmers + annotations
              ▶ each candidate ─▶ Bucket 1 facts (aso-tox 🟢, off-target, thermo)
                    ▶ Bucket 2 partners weigh the shortlist (tox vs potency vs off-target spread)
                          ▶ Synthesis: recommended candidate(s) + (⚪) Experiment Design proposes the assay
```
This is the firm doing real medicinal-chemistry-adjacent work, not just diligence. It also composes cleanly:
`aso-tox` is step 05 — already built — so ASO Design's tox annotation is the *same* model the firm already
trusts. No duplicate truth.

## 6. Open questions (resolve in `03`)
1. **Bundled vs staged execution** (§4) — D3.
2. **Where do candidates live?** Asset store / artifact registry vs inline in the dossier (they can be large).
3. **Cost guardrails** — a ~3 hr EC2 run per gene is real spend; needs the cost ledger + a per-engagement cap.
4. **Trigger policy** — does design auto-fire when a target validates, or only on an explicit design ask?
   (Auto-firing could spend AWS on every diligence query — probably gate it behind an explicit class.)
5. **Chemistry scope** — v1 = DNA gapmer 20-mers (as templated). Other chemistries/lengths later.
6. **OligoWalk in the cloud** — RNAstructure is a biocontainer; confirm it runs headless in the chosen tier.

## 7. Build plan v1 (step 3) 🔵
Decisions baked in: **bundled-EC2** (D3 ✅) · **artifact registry** for assets (D4 ✅) · **explicit design
ask only** (D5 ✅).

**Phase 1 — the image.** Build one tagged `Sapphire` AMI/container that holds the whole pipeline: R + the
`.Rmd` scripts (02/06/07), OligoWalk (RNAstructure biocontainer), bowtie2 + samtools + the spliced/unspliced
transcriptome indices, the NCBI `datasets` CLI, the GBR `aso_tox_gbr_model.pkl`, and a single
`run_aso_design.sh GENE` entrypoint that runs 00→07 end-to-end and writes `top_candidates.csv` +
`full_annotation.csv`. Pin everything; this is the heavy part but it's built once.

**Phase 2 — the seam** (`sapphire-orchestrator/tools/aso_design_seam.py`, kind `aws-async`). Reuse the
**Q-Models launcher** verbatim: account-gate → launch the tagged box (create-only + ledger) → stage the
gene symbol (public ID only) → run `run_aso_design.sh` → retrieve `top_candidates.csv` →
**teardown by ledgered id** → ledger the cost. Dry-run by default; live behind every existing safety guard.

**Phase 3 — output + the loop.** Write the asset bundle to **`RohanOnly/assets/aso-design/<run_ref>/`**
(registry, D4); the dossier carries a *reference* + the shortlist + **per-candidate facts** (each candidate's
tox + off-target + ΔG) that **re-enter Bucket 1** — `aso-tox` is already step 05, so its tox annotation is
the same model the firm trusts. Schema: the design-asset bundle from [`01 §2(d)`](01_TOOL_SEAM_PATTERN.md).

**Phase 4 — activation.** Control activates `aso-design` only when the engagement class includes `design`
AND the ask is an explicit ASO-design request for a gene (D5). Never auto-fires on diligence.

**Phase 5 — guardrails + honesty.** Per-engagement **cost cap** + the cost ledger + idle/hard-cap watchdogs.
If AWS/creds/refs unavailable → **abstain with reason**, never fabricate candidates. Capture ONE real gene
run as a scenario so the canned path demos it $0.

**DoD:** one real end-to-end run for a gene (e.g. SCN9A) produces ~20 cited candidates with tox/off-target/ΔG;
EC2 teardown verified + ledgered; assets in the registry; the shortlist + per-candidate facts appear in a
`run_live` dossier; honest-abstain path tested; captured scenario added.
**Gates:** suite green · independent review · provenance + no secrets (only public IDs leave) · **Gate 5: the
real AWS run + verified teardown** (this is the proof, like the Q-Models smoke test).
**Risks:** ~3 hr / real-$ per run (mitigate: cost cap + explicit-ask gate); OligoWalk headless in-image;
reference-data size drives EC2 storage; AMI maintenance over time.
