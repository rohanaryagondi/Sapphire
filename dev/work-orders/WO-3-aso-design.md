# WO-3 — ASO Design seam (first design-class tool)

**For:** Rohan Claude (worker) · **Branch:** `rohan/aso-design` cut from `main` · **Plan:** [`docs/plan/02_ASO_DESIGN.md`](../../docs/plan/02_ASO_DESIGN.md) (esp. §7) + [`01_TOOL_SEAM_PATTERN.md`](../../docs/plan/01_TOOL_SEAM_PATTERN.md)
**Lifecycle:** `/sapphire-build`. AWS work uses `/sapphire-aws`. **Blocked? →** `dev/HELP.md`.
**Depends on:** WO-2 Phase A (the live firm + `class` field). **Decisions:** bundled-EC2 (D3), artifact registry (D4), explicit-ask only (D5).
**Source pipeline:** the Quiver template (steps 00→07) — readme + scripts in `~/Downloads/basic_design_template.zip` (00 identify → 02 R gapmer tiling → 03 OligoWalk/Docker thermo → 04 bowtie2 off-target on EC2 → 05 GBR tox = the existing `aso-tox` → 06/07 R annotate+filter → ~20 candidates).

## Goal
A `aws-async` design seam: **gene symbol → ~20 ranked candidate ASOs** (tox + off-target + ΔG annotated),
whose per-candidate facts re-enter Bucket 1 (the design loop). It composes the existing `aso-tox` (step 05).

## Steps
1. **Phase 1 — the image.** Build one tagged `Sapphire` AMI/container with the whole pipeline: R + the `.Rmd`
   scripts, OligoWalk (RNAstructure biocontainer), bowtie2 + samtools + the transcriptome indices, the NCBI
   `datasets` CLI, the GBR `.pkl`, and a single `run_aso_design.sh <GENE>` entrypoint that runs 00→07 and
   writes `top_candidates.csv` + `full_annotation.csv`. Pin everything. (Built once; the heavy part.)
2. **Phase 2 — the seam** `sapphire-orchestrator/tools/aso_design_seam.py` (kind `aws-async`). Reuse the
   Q-Models launcher verbatim: account-gate → launch tagged box (create-only + ledger) → stage the gene
   symbol (public ID only) → run the entrypoint → retrieve `top_candidates.csv` → **teardown by ledgered id**
   → ledger cost. Dry-run default; live behind every safety guard.
3. **Phase 3 — output + loop.** Write the asset bundle to **`RohanOnly/assets/aso-design/<run_ref>/`** (D4);
   the dossier carries a reference + the shortlist + **per-candidate facts** (tox/off-target/ΔG) that re-enter
   Bucket 1. Use the design-asset schema in `contracts/` (add it if absent).
4. **Phase 4 — activation.** Control activates `aso-design` only when `class` includes `design` AND the ask is
   an explicit ASO-design request for a gene (D5). Register in `harness/agents.json` (`class:"design"`,
   `provenance:"aso-design"`).
5. **Phase 5 — guardrails + honesty.** Per-engagement cost cap + cost ledger + idle/hard-cap watchdogs; if
   AWS/creds/refs unavailable → abstain with reason (never fabricate). Capture ONE real gene run as a scenario
   for the $0 canned path.

## DoD
One real end-to-end run for a gene (e.g. SCN9A) → ~20 cited candidates with tox/off-target/ΔG; EC2 teardown
verified + ledgered; assets in the registry; the shortlist + per-candidate facts appear in a `run_live`
dossier; honest-abstain tested; captured scenario added.

## Gates
Suite green · independent review · provenance + no secrets (only public IDs + sequences leave) · stdlib-engine
boundary (heavy deps only in the image/subprocess) · **Gate 5: the real AWS run + verified teardown** (the
proof, like the Q-Models smoke test).

## Risks
~3 hr / real-$ per run → the cost cap + explicit-ask gate are mandatory. OligoWalk headless in-image. Reference
data drives EC2 storage (50–100 GB). AMI needs maintenance.
