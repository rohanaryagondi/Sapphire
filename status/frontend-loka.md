# Status — Front End / LOKA

*The user-facing layer + the contract it plugs into. Updated 2026-06-23 (LOKA code arriving 2026-06-24).*
Background: `docs/LOKA.md`. Readiness plan: `docs/superpowers/plans/2026-06-24-loka-end-to-end-readiness.md`.

## The framing (2026-06 sprint)
**LOKA = the front-end + conversation scaffold.** Quiver tools = the predictive capability (plug into the
seam pattern). **Sapphire = the agentic reasoning layer** (`live_engine.run_live` — the two-bucket firm).
End-to-end: **LOKA → `run_live` → Bucket-1 (EMET·moat·seams·corpora) → Bucket-2 roundtable → synthesis → LOKA.**

## State today
- **Interim front face:** `site/` Console + `sapphire-orchestrator/serve.py`. ⚠️ `serve.py`'s `_run_live` is the
  **headless-Claude/canned-scenario path, NOT `live_engine.run_live`** — the live harnessed firm is not yet the
  brain behind any front door. `site/` is likely **superseded by LOKA**; don't invest in the old Console.
- **The real engine entry:** `sapphire-orchestrator/live_engine.py` → `run_live(query, ...)` returns the
  structured run (plan · dossier · roundtable · synthesis · provenance · trace). Verified offline; **not yet
  exposed as a stable service boundary** a front end calls.
- **LOKA code:** not yet in the repo. When it lands it'll be vendored/integrated per the `vendor/` convention
  (`dev/CONVENTIONS.md` §4; precedent `vendor/design-form-agent/`).

## Open items (the keystone path — LOKA-independent, do before/while LOKA lands)
1. **`run_live` as a clean service boundary** — a documented `run_live(query) -> result` contract + a thin
   transport (HTTP/CLI) LOKA calls. This is the single integration point; nail it and LOKA wiring is shallow.
2. **Corpus runtime retrieval** — corpus-first→search-the-gap in the Bucket-1 dispatch, so agents read their
   corpora live. Corpora are inert without it.
3. **Replace serve.py's canned `_run_live`** with the harnessed `run_live` (behind the same `/api/run`
   contract) so there's a real end-to-end path even before LOKA — and LOKA inherits it.

## Resolved-by-LOKA unknowns (capture when the code arrives — do NOT build blind)
- LOKA's call shape (HTTP? in-process? what request/response schema?), auth, streaming vs batch, session model,
  how it renders the dossier/roundtable/spread, and how Quiver tools are surfaced in its UI.

## Watch-outs
- **Don't wire the old `site/` Console** as if it's the destination — LOKA supersedes it.
- Keep the **product-vs-build** line clean and the **data boundary** intact across the LOKA seam (public
  identifiers only leave to external evidence; internal data may reach the reasoning LLM, not external sources).
