# Status — Front End / LOKA

*The user-facing layer + the contract it plugs into. Updated 2026-06-23 (LOKA code arriving 2026-06-24).*
Background: `docs/LOKA.md`. Readiness plan: `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md`.

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
- **LOKA code:** not yet in the repo. When it lands it'll be vendored/integrated per the `vendor/` convention
  (`dev/CONVENTIONS.md` §4; precedent `vendor/design-form-agent/`), with the adapter written against the K1 contract.

## Open items
1. ✅ **DONE (K1):** `run_live` service boundary + real `/api/run`.
2. **Corpus runtime retrieval (K2, in progress)** — corpus-first→search-the-gap in the Bucket-1 dispatch, so
   agents read their corpora live. Corpora are inert without it.
3. **LOKA adapter** — once the LOKA code lands, wire LOKA ↔ the K1 `run_live` contract (resolve the unknowns below first).

## Resolved-by-LOKA unknowns (capture when the code arrives — do NOT build blind)
- LOKA's call shape (HTTP? in-process? what request/response schema?), auth, streaming vs batch, session model,
  how it renders the dossier/roundtable/spread, and how Quiver tools are surfaced in its UI.

## Watch-outs
- **Don't wire the old `site/` Console** as if it's the destination — LOKA supersedes it.
- Keep the **product-vs-build** line clean and the **data boundary** intact across the LOKA seam (public
  identifiers only leave to external evidence; internal data may reach the reasoning LLM, not external sources).
