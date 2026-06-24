# LOKA ↔ Sapphire — Open Questions (decisions needed before building)

*Resolve these before Phase 2. **Q1 is escalated to a human (Rohan/Quiver)** per the 2026-06-24 direction call.
Q2/Q3 are ours to decide. Plan: [`INTEGRATION_PLAN.md`](INTEGRATION_PLAN.md).*

---

## Q1 — Data boundary across the LOKA↔Sapphire seam ⛔ **HUMAN DECISION**

**The finding.** Sapphire's hard rule: *Quiver internal data (EP/CRISPR signatures + scores) never leaves to
external evidence (EMET / web / Q-Models); only public identifiers do.* In code, the firm guards this and degrades
to mock rather than leak.

**LOKA already crosses near that line.** Its `search_perturbation_matches` / `search_global_ranking` tools query
**Quiver internal HTS electrophysiology signatures** directly (RDS Postgres `perturbation_similarity_top200`,
`src/tools/perturbation_search.py`) and feed the results **into the Bedrock LLM context**. So:
- The boundary today is enforced at **LOKA's infrastructure perimeter** (it's Quiver's own AWS + Quiver's own
  Bedrock), **not in code** the way Sapphire enforces it.
- LOKA's `browse_web` / `search_web` reach the *public* internet in the same agent loop that has just seen internal
  perturbation data in its context window. Within one Bedrock session, internal facts and an external-fetch tool
  coexist — the model is trusted not to put internal data into a web query, but nothing mechanically prevents it.

**The decision you need to make (pick one, or amend):**
1. **Sapphire owns the moat; LOKA stays public-first.** Internal moat facts reach the reasoning layer *only*
   through Sapphire (provenance-stamped); LOKA's perturbation tools are treated as a separate, acknowledged
   Quiver-internal surface that we do not route through the external-evidence path.
2. **LOKA's internal-data access is sanctioned** (Quiver AWS + Quiver Bedrock = within the trust perimeter);
   document that the boundary is perimeter-enforced there, and ensure no external-fetch tool can receive
   internal data in the same turn (a LOKA-side guard).
3. **Other / amend** — e.g. require a code-level boundary guard in LOKA mirroring Sapphire's before coupling.

**Why it can't be auto-decided:** it's a governance/compliance call about Quiver's own data on Quiver's own infra,
not a code-quality choice. **Building waits on your answer.**

## Q2 — Bridge shape (ours)

How does LOKA reach `/api/run`?
- **(a) Drop-in `BaseTool`** (`SapphireAnalysisTool`) that POSTs to `/api/run` — lowest friction, reversible,
  works with LOKA's loop unchanged. **Recommended for v1.**
- **(b) In-loop router** in `Agent.process_message` that bypasses the Bedrock loop for complex queries — truer to
  "thin UI over Sapphire," bigger change.

We author the artifact as a **drop-in in Sapphire** (`integrations/loka/`, Phase 2) regardless; (a) vs (b) only
changes how LOKA wires it. Leaning **(a) → (b)**.

## Q3 — Inference path when `run_live` runs behind LOKA (ours)

LOKA's own agent uses **AWS Bedrock**. Sapphire's live harness was designed around **Claude Code on the user's
subscription**. When LOKA calls `/api/run`, *which model executes the firm's reasoning?*
- **(i) Keep Sapphire self-contained** — `serve.py`/`run_live` runs on its own host with its own inference; LOKA
  just consumes the JSON. Cleanest separation; LOKA's Bedrock and Sapphire's inference stay independent. **Likely.**
- **(ii) Sapphire dispatches via Bedrock too** — unify on Bedrock so the whole stack uses one inference path
  (needs a harness Bedrock dispatch kind). More work; only if ops wants a single model plane.

This is an ops/architecture choice; default to **(i)** unless there's a reason to unify.

## Q4 — Resolved-by-inspection (were open in `status/frontend-loka.md`)

Now answered from the source, recorded so we don't re-derive:
- **Call shape:** HTTP (Chainlit app); our `/api/run` is the seam — no in-process import needed. ✅
- **Streaming vs batch:** `run_live` is **batch** (no token stream) → LOKA shows a step/spinner. ✅
- **Session model:** LOKA persists threads/messages in DynamoDB + files in S3; Sapphire keeps its own append-only
  trace keyed by `engagement_id`. Surface `engagement_id` in LOKA for cross-reference. ✅
- **How LOKA renders results:** Chainlit elements (`cl.Dataframe`/`cl.Text`/`cl.Image`/`cl.Step`) via
  `_create_*_table` helpers — mapping in [`CONTRACT.md §3`](CONTRACT.md). ✅
- **How Quiver tools surface in LOKA:** as `BaseTool` registry entries (`src/tools/registry.py`). Our seams
  (aso-tox, quant-fact) could later be exposed LOKA-side the same way (convergence, Phase 4). ✅
- **Auth:** LOKA uses Chainlit OAuth at the UI; the `/api/run` bridge auth (network policy / token) is a Phase-2
  deployment detail. ⏳

## Still open / external

- **DisGeNET API key, Bedrock model access, AWS resources** are LOKA-side ops, not our concern.
- **LOKA has no test suite** — our conformance test on the contract is the only automated guard on the seam from
  our side; the joint end-to-end smoke (Phase 3) is manual until LOKA adds tests.
