# Plan — End-to-end readiness for LOKA (the front end)

*Strategic readiness map. LOKA code + more Quiver-tool access arrive 2026-06-24; Hayes & Gavin work their
parts the same day. Goal: by the time LOKA lands, the **backend is already end-to-end-capable on its own**, so
LOKA integration is shallow wiring — not foundation-laying. Background: `docs/LOKA.md`, `status/frontend-loka.md`.*

## The end-to-end target
```
LOKA (front end / conversation scaffold)
        │  query in · structured run out
        ▼
live_engine.run_live(query)            ← the live harnessed firm (THE entry boundary)
        ▼
Bucket 1 — facts (harness-dispatched, guard-enforced, provenance-stamped)
   EMET (live) · moat (real) · Q-Models · aso-tox · quant-fact seams (gnomad/gtex/interpro/gprofiler)
   · the 13 semantic agents — each CORPUS-FIRST → SEARCH-THE-GAP
        ▼
Bucket 2 — persona roundtable (independent verdicts → moderated rebuttal; the spread is the product)
        ▼
synthesis (recommendation + confidence + proposed experiment) · full trace
        │
        ▼  back to LOKA for rendering
```
**Division of labor (sprint framing):** LOKA = front end + scaffold · Quiver tools = predictive capability
(seam pattern) · **Sapphire = the agentic reasoning layer.**

## Where we actually are (honest)
- ✅ `run_live` runs the full firm offline (mock backends + real moat); harness guards/trace/provenance work.
- ✅ Real fact sources: EMET (live), moat (real), Q-Models (real), aso-tox (real), 4 quant-fact seams merged.
- ✅ FDA-memory dual-source corpus + the locked corpus METHOD + `validate-corpus.sh` gate; 12 corpora delegated.
- ❌ **The live firm is not behind any front door.** `serve.py`'s `_run_live` is the headless-Claude/canned
  path, not `live_engine.run_live`. The Console (`site/`) plays canned scenarios.
- ❌ **Corpora are inert at run time** — no agent reads its corpus yet (corpus-first retrieval unimplemented).
- ❌ LOKA's actual call shape is unknown until tomorrow.

## The two LOKA-INDEPENDENT critical-path builds (do before / parallel to LOKA)
These don't need LOKA and are the difference between "demoable canned" and "a real live system." Each is a
feature run through the dev lifecycle (brief → implement → review → Gate-5 verify → PR).

### Task K1 — `run_live` as a clean service boundary (the keystone)
- Define and freeze the **contract**: `run_live(query: str, *, sequences=None, ...) -> result dict` with a
  documented, stable output schema (plan · discover{dossier,flags,agents} · consult{round1,round2} ·
  synthesize · engagement_id · trace ref · provenance). This dict IS the API LOKA consumes.
- Expose it behind a thin transport so any front end can call it: replace `serve.py`'s canned `_run_live` with
  the harnessed `live_engine.run_live` behind the existing `/api/run?q=` (keep a canned fallback for `$0`
  offline demos, clearly labeled). Result: a real end-to-end path exists **even before LOKA**, and LOKA
  inherits the same boundary.
- Stays stdlib-only at the engine; the live LLM/EMET calls are already behind the harness/seams.
- DoD: `GET /api/run?q="is TSC2 a viable CNS target?"` returns a real harnessed run (live or honest-degraded),
  not a canned scenario; the result schema is documented in one place LOKA can read.

### Task K2 — corpus runtime retrieval (corpus-first → search-the-gap)
- In the Bucket-1 dispatch, before an agent makes a live web/EMET call, **query its corpus**
  (`sapphire-orchestrator/corpus/<agent>/index.jsonl` + notes) for the stable ~70%; only search live for the
  gap. Stdlib-only reader (json/grep over claim-cards by lens fields + entities).
- Provenance: corpus-sourced facts carry their card's `source`/`tier`/url (+ a `corpus` provenance marker);
  the live-search path is unchanged. Veto rule intact (a veto still needs its T1 primary).
- DoD: a query whose answer is in the FDA-memory corpus is answered FROM the corpus in `run_live` (traced as
  corpus-sourced), with a live call made only for the uncovered part. Wire it generically so every agent that
  has a `corpus/<id>/` dir uses it; agents without a corpus are unchanged.

> Sequencing note: K1 and K2 are independent and can land in either order; K2 makes the corpora (the big
> delegated effort) actually pay off, K1 makes the whole firm reachable. Recommend **K1 first** (reachability),
> then K2 (grounding) — but both before we call anything "end-to-end."

## What waits for LOKA (capture, don't build blind)
When the LOKA code lands: read it, **vendor/integrate per `vendor/` convention** (preserve original; a
`VENDORED.md`; precedent `vendor/design-form-agent/`), and resolve the unknowns in `status/frontend-loka.md`
(call shape, auth, streaming, session model, dossier/spread rendering, how Quiver tools surface in its UI).
Then write the LOKA↔`run_live` adapter against the K1 contract. **Do not pre-build a LOKA adapter tonight.**

## More Quiver tools (arriving tomorrow) — already have the pattern
New tools plug in as **stdlib seams** exactly like `aso_tox_seam.py` / the quant-fact seams: a thin
`sapphire-orchestrator/tools/<tool>_seam.py` (engine stays stdlib; heavy deps in a subprocess/delegate), a
harness `agents.json` entry with a complete `output_schema`, an allowed provenance label, wired into
`_BUCKET1_AGENTS` + `python_fns`. No harness change needed to absorb them — assign each as a `<tool>-seam` task.

## Harness changes made in THIS prep (so tomorrow is clean)
- **No GitHub Pro — permanent.** Removed `dev/enable-branch-protection.sh` and scrubbed all "pending Pro /
  staged for Pro / for the day we go paid" language. Hook-based + CODEOWNERS + `audit-history.sh` is the
  **complete, permanent** enforcement model (`dev/CONVENTIONS.md` §1). Don't reintroduce branch-protection talk.
- Added `status/frontend-loka.md` (front-end track) and reconciled `status/OVERALL.md` to current reality.

## Decisions for Rohan (tomorrow, or now)
1. **Build K1 + K2 pre-LOKA?** (Recommended: yes — they're LOKA-independent and on the critical path. Lead-driven.)
2. **Who builds them** — lead (you/me) vs a contributor? (Recommend lead: bedrock/engine, not corpus-shaped.)
3. **LOKA integration:** vendor the code into `vendor/loka/` and adapt, or keep LOKA as a separate repo calling
   `run_live` as a service? (Decide when we see the code; `vendor/` is the default per convention.)

## Out of scope here
Building the LOKA adapter (needs the code); the contributors' corpora/experiment-design work (separately tasked).
