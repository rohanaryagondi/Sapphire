# Loka — what it is, what's in the shared folder, and how Sapphire leverages it

Findings from `~/Downloads/Loka - Shared Folder.zip`, extracted to
`Career/Quiver/Sapphire/Loka - Shared Folder/` (meeting **recordings** excluded on extract, per request —
they were the 7 GB bulk; the small **meeting notes** PDFs were kept). Captured 2026-06-21.

## TL;DR
- **Loka's application source code is NOT in this folder.** The folder is a shared *engagement* folder
  (deliverable PDFs, meeting notes, use-case images, one data parquet, a `.env`, and an `llm_benchmark.zip`
  that is just 4 PNG charts). The actual app lives in a **private GitHub repo**
  `q-state-biosciences/drug-discovery-agent` — we must request access to "build on it."
- **The single most valuable in-hand asset is real Quiver moat data:**
  `Data/CNS_DFP_distance_20251215.parquet` — **38.4M rows** of perturbation↔perturbation EP-signature
  distances (cosine + euclidean, with similar/opposite directionality). This is the **real internal moat**
  we've been treating as MOCK. Verified queryable + biologically sane (nearest neighbor of `TSC2` is
  `TSC1`, cos 0.084 — the TSC/mTOR complex).

## What Loka built (the "GenAI Accelerator")
A Quiver-branded **Drug Discovery Agent**: a conversational chatbot that reasons over Quiver's proprietary
perturbation data + external biological APIs. 3-phase engagement (RAPID Assessment → PoC → proposed MVP);
PoC delivered (a working agent), **not** production/MVP. Status at the Roadmap Checkpoint: data-integration
phase, ~week 7/14; handover Feb 2–6 2026.

## Architecture & stack (from the deliverable PDFs + `.env`)
```
User → Cognito (OAuth) → Route53 → ALB → ECS/Fargate (Chainlit app)
   Chainlit app →  Amazon Bedrock (Claude Sonnet 4.5 "Pro" / Haiku 4.5 "Fast")
                →  RDS PostgreSQL  (the 38M-row perturbation-similarity "Bio DB" + materialized views)
                →  DynamoDB        (sessions / conversation history)
                →  S3              (docs, molecular files, persisted scratchpads)
                →  Secrets Manager (keys, DB creds)
   CI/CD: GitHub Actions → ECR → ECS (Fargate)
```
External APIs the agent calls at runtime: **UniProt, KEGG, DisGeNET, STRING, DrugBank/ClinicalTrials.gov/
PubMed/FDA (via web search + headless browser)**.

**Agent design:** a *single-agent* Bedrock loop (no LangChain) with **13 tools** in 4 groups —
(A) **Perturbation Search** over Quiver's similarity DB (gene/drug × gene/drug, similar vs **opposite** via
a `match_effect` directionality column), (B) biological context (UniProt/KEGG/DisGeNET/STRING),
(C) research/validation (web + browser), (D) a `manage_dataframe` **scratchpad** persisted across turns.
≤10 tool calls/request; 150K-token sliding-window context; chain-of-thought shown then stripped. A
**multi-agent** coordinator→specialists design is *proposed* for the MVP (not built).

## The data — `CNS_DFP_distance` (DFP = Drug/gene Functional Perturbation)
Quiver's optical-electrophysiology platform stimulates patient-derived neurons and measures 500+ EP
features per perturbation; vectors are PCA-reduced and **all pairwise distances precomputed**. Schema (12
cols): `query_/ref_perturbation{,Name,Type,Dose,Direction}`, `cosine_distance`, `euclidean_distance`.
~18k gene perturbations + ~3.5k compounds across 25+ brain cell types. Loka served it from RDS with
materialized views (top-200 per query × effect × metric) for sub-second lookups. **We can use the parquet
directly** (pyarrow/DuckDB) — no Postgres required.

## Use cases (the 2 screenshots)
1. **Drug→Gene signature matching** — "which drugs *mimic* TSC2 KO?" (same EP signature) → UniProt+KEGG
   context → mechanism + hypothesis type.
2. **Mechanistic rescue** — "which drugs *rescue* the TSC2 KO phenotype?" (**opposite** EP direction) →
   disease context (DisGeNET) → intervention points → clinical feasibility (safety/BBB/approval). Rapamycin
   surfaces as expected (a correctness check).
The four workflows: gene-gene, gene-drug, drug-gene, drug-drug — each similar (mimic) or opposite (rescue).

## How Sapphire leverages this
**Immediately, in-hand (no Loka code needed):**
1. **Retire the MOCK moat → real moat.** ✅ **WIRED (real)** — see `sapphire-orchestrator/moat/`
   (`MoatClient` + `moat_facts`, provenance `moat-real`) + `_build/build_moat_db.py` (parquet → SQLite).
   The dossier now carries real CNS_DFP perturbation-similarity evidence (similar genes + rescue compounds).
   The Phase-5 self-improvement `moat_blindspot` loop has a real substrate to update.
   **Semantics (verified live):** `query_perturbationDirection` is Original (half) / Antipodal (half);
   `ref` is always Original. **similar (mimic)** = nearest cosine among **Original**-query rows;
   **rescue (opposite)** = nearest cosine among **Antipodal**-query rows; top-K is kept **per ref_type**
   (genes + compounds separately) so compound rescues aren't crowded out by genes. Sanity: `TSC2` nearest
   = `TSC1` (the TSC complex). **Caveat:** raw EP-antipodal-distance does NOT reproduce Loka's flagship
   "rapamycin rescues TSC2" result — Sirolimus/Everolimus are not in TSC2's top-50 antipodal compounds
   (top rescues are e.g. Isorhamnetin, an mTOR/autophagy modulator). Loka layers extra scoring on the raw
   distance (their 40% rescue / 30% mechanistic / 30% safety weights + pathway/clinical reasoning, likely
   dose-aware). Reproducing their exact ranking is gated on getting their repo + 7-stage workflow doc (the
   asks below). Our moat is the **correct, real EP-distance substrate**; Loka's demo scoring sits on top.
2. **Adopt Loka's reasoning designs** — the 4 perturbation workflows + the 2 use-case flowcharts map onto
   our agents; the multi-model Pro/Haiku split, the scratchpad pattern, and their LLM-as-judge eval harness
   are reusable patterns.
3. **Tool overlap is already covered** — Sapphire's EMET (BenchSci) is a superset of Loka's UniProt/KEGG/
   DisGeNET/STRING/PubMed tools; Q-Models covers the compute. So Sapphire's orchestrator + harness + EMET +
   Console is a strict superset of Loka's single-agent loop — we reuse Loka's **data + designs**, not its UI.

**Must request from Quiver/Loka (to "build on the code"):**
- The **`q-state-biosciences/drug-discovery-agent`** repo (agent loop, 13 tool defs, system prompt,
  `manage_dataframe`, Chainlit UI).
- The **Quiver 7-stage target-ID workflow doc** (stage I/O, scoring weights: e.g. 40% phenotypic rescue /
  30% mechanistic / 30% safety) referenced in the RAPID report.
- A **DisGeNET API key**, and Quiver's **MoA model** (`.pkl`/`.joblib`) referenced in the proposal.
- Optional: AWS/IaC access (ECS/RDS) — not needed if we run the parquet locally + our own stack.

## ⚠️ Security note
`Loka - Shared Folder/.env` contains **live secrets** (Postgres `DB_PASSWORD`, `CHAINLIT_AUTH_SECRET`,
`OAUTH_COGNITO_CLIENT_SECRET`, `DISGENET_API_KEY`, S3/DynamoDB names, a dev AWS endpoint). It is **outside
the git repo** and must **never be committed**. Recommend rotating these credentials (a plaintext `.env`
with a DB password is sitting in OneDrive) and moving it to a secret manager. Values are NOT reproduced here.

## Folder manifest (recordings removed)
Deliverable PDFs (RAPID Assessment, Implementation Proposal ×2, Roadmap Checkpoint, Kick-off `.pptx`,
Nov-3 meeting notes, availability calendar) · `Meeting notes/` (16 Gemini PDFs) · `Use Case examples/`
(2 PNGs) · `Data/CNS_DFP_distance_20251215.parquet` (365 MB) · `llm_benchmark.zip` (4 chart PNGs) · `.env`.
