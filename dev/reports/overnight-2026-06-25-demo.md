# Overnight shift — REAL TSC2 demo — morning report (2026-06-25)

**Outcome: SUCCESS. The TSC2 demo is complete — it runs live AND replays instantly.** All four planned
tracks shipped, every PR gated (independent review + Gate-5 verify; the keystone also live-acceptance-tested
by Head Claude). Auditor: 0 PRs held at end; every finding fixed before merge.

## Demo state (honest)
- **Runs live:** YES. `live_engine.run_live` convenes the firm; the live-EMET keystone is proven — Head Claude
  independently drove a fresh TSC2 Target-Validation query in an authenticated BenchSci session, got real PMIDs
  (e.g. 33307091), and confirmed they land as `emet-live` external-plane facts via `run_live` (status ok, not
  abstain, no fabrication).
- **Replays instantly:** YES. `scenarios/tsc2_live_run.json` is a captured REAL run (wall 1050s; real moat
  internal-plane facts + 8 live EMET PMIDs + 5-persona spread + DIVERGENCE + synthesis), replayed by the front
  end **$0/offline** (verified with the network blocked). Internal-only tagged; honest demo doc `frontend/DEMO_TSC2.md`.
- **Cost:** all-haiku live path + a "Live (cheap · haiku)" front-end profile; captured replay is $0.

## Tracks (all merged)
- **A — live-EMET in-session keystone** (#57): real PMIDs via the session bridge; honest-abstain when no session.
- **B — dispatch optimization** (#56): cache-stable prefix + drop redundant CLAUDE.md (Opt-1) + batched-per-bucket
  (Opt-2, flagged, union --allowedTools). Opt-3 warm worker parked → Claude Agent SDK (HELP-resolved).
- **D — TSC2 captured scenario** (#61): the demo artifact; real + reproducible + honest.
- **E — robyn_scs firm seam** (#62): callable fire-when-relevant Bucket-1 tool; honest KNOWN_UNKNOWN on empty plate.

## What's mocked / abstaining (no overclaiming)
- In the captured demo: EMET PMIDs are REAL (captured from a live session). Two personas (Third Rock GP,
  Adversarial Red-Team) **abstained on the harness guardrail** — shown honestly as abstentions, not deliberate holds.
- robyn-scs fires only with real imaging data → honest-empty for the TSC2 query (no SCS imaging in scope).
- Internal moat data in the captured scenario is REAL (approved, internal-only tagged — do not ship externally as-is).

## Backlog / honest gaps (for Rohan)
1. **Provenance set gap (pre-existing):** `qmodels`, `fda-primary`, `semantic-web` are emitted by the engine but
   missing from `contracts/provenance.py` PROVENANCE → `is_valid_provenance()` returns False for them. Small fix,
   not introduced overnight. **Suggested single next step.**
2. Corpora: 3/13 semantic corpora live (Gavin); the rest remain (Hayes 6 / Gavin 3).
3. Durable live-EMET = EMET-MCP (current in-session capture is the working interim).
4. Front-end Console UI still renders the old canned data file in places; the new `frontend/` is the surface.

## Needs Rohan
Nothing blocking. The demo is ready to show (lead with the captured scenario; one live query to prove it's real).
