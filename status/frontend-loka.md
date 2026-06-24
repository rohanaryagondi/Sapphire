# Status — Front End / LOKA

*The user-facing layer + the contract it plugs into. Updated 2026-06-24 (**LOKA source received + analyzed**).*
Background: `docs/LOKA.md`. Readiness plan: `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md`.
**Integration plan + wire contract + open questions:** `docs/integrations/loka/` (INTEGRATION_PLAN · CONTRACT · OPEN-QUESTIONS).

## The framing (2026-06 sprint)
**LOKA = the front-end + conversation scaffold.** Quiver tools = the predictive capability (plug into the
seam pattern). **Sapphire = the agentic reasoning layer** (`live_engine.run_live` — the two-bucket firm).
End-to-end: **LOKA → `run_live` → Bucket-1 (EMET·moat·seams·corpora) → Bucket-2 roundtable → synthesis → LOKA.**

## State today
- ✅ **The front door now serves the live harnessed firm** (K1, PR #24, 2026-06-24). `serve.py`'s `/api/run`
  defaults to `live_engine.run_live` (`via=engine-live`) — a real harnessed run, NOT canned. The canned
  scenarios + headless-claude are kept as explicit labeled fallbacks (`?mode=canned`/`claude`). `site/` Console
  is still the old surface and is likely **superseded by LOKA** — don't invest in it.
- ✅ **Frozen, validated contract:** `sapphire-orchestrator/contracts/run_live_schema.{md,py}` documents +
  validates the `run_live` output shape. **This dict is the integration point LOKA plugs into.**
- ✅ **LOKA source received + analyzed** (2026-06-24): `q-state-biosciences/drug-discovery-agent` (HEAD `8685382`,
  2026-02-12) — a **Chainlit** app, Claude via **AWS Bedrock**, single agent + 13-tool registry. Cloned read-only
  to `../drug-discovery-agent` (sibling of this repo, **never modified**). Full map + plan in `docs/integrations/loka/`.
- **Direction chosen (Rohan, 2026-06-24): LOKA as a thin UI over Sapphire** — for complex/CNS queries LOKA routes
  to `run_live` and renders the dossier + roundtable + synthesis first-class; it keeps its fast tools for simple lookups.

## Open items
1. ✅ **DONE (K1):** `run_live` service boundary + real `/api/run` — **the bridge LOKA calls already exists.**
2. ✅ **DONE (K2):** corpus-first→search-the-gap runtime retrieval (PR #26).
3. **Resolve 3 open questions** (`docs/integrations/loka/OPEN-QUESTIONS.md`): **Q1 data boundary — escalated to a
   human** (LOKA queries internal perturbation data directly); Q2 bridge shape (ours, lean drop-in `BaseTool`);
   Q3 inference path (ours, lean Sapphire self-contained).
4. **Build the Sapphire-side `integrations/loka/` adapter** (drop-in `BaseTool` + conformance test) after Q1–Q3 — a
   future dev-harness task, **not started** (this session was plan/contract docs only).

## The unknowns are now answered (were "capture when the code arrives")
Call shape = HTTP via `/api/run` (no in-process import); streaming = batch (show a spinner); session = LOKA
DynamoDB/S3 + surface our `engagement_id`; rendering = Chainlit `cl.Dataframe`/`cl.Text`/`cl.Step` (mapping in
`docs/integrations/loka/CONTRACT.md §3`); Quiver tools surface as `BaseTool` registry entries. Auth on the bridge
is a Phase-2 deploy detail. Full detail: `docs/integrations/loka/OPEN-QUESTIONS.md §Q4`.

## Watch-outs
- **Don't wire the old `site/` Console** as if it's the destination — LOKA supersedes it.
- Keep the **product-vs-build** line clean and the **data boundary** intact across the LOKA seam (public
  identifiers only leave to external evidence; internal data may reach the reasoning LLM, not external sources).
