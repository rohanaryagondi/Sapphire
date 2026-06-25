# Overnight shift — get a REAL, reproducible TSC2 demo working

*Created 2026-06-25. Decisions (Rohan): **in-session EMET reuse · full scope incl. robyn_scs tool · TSC2/
tuberous-sclerosis demo · all-haiku**. Deadline: **morning report by 08:30 AM 2026-06-25**.*

## Goal (definition of done by morning)
A user can run the **TSC2 / tuberous-sclerosis** query through the front-end **Live profile** and get a real
end-to-end firm run: real moat (internal plane) + **live EMET PMIDs** (external plane, using the logged-in
session) + quant seams + Q-Models + corpora → persona roundtable → synthesis, rendered transparently — and the
exact run is **captured as a deterministic scenario** so the demo is instant + reproducible ($0 replay) with the
live path proven once. Everything honestly labeled; nothing faked.

## Roles
- **Workers build; Head Claude audits.** Head Claude (separate session) is the pure approver: gates/merges every
  PR, keeps `status/` + `dev/LEDGER.md` current, files the morning report. Workers do NOT merge their own PRs.
- **Rohan Claude** = the keystone builder (Tracks B→A→D→E, in that priority order).
- **Hayes + Gavin** = corpora breadth (Track C), autonomous via their watchers.

## Non-negotiables (every track)
- **Honesty over a demo that overclaims.** If a real backend can't fire, the agent **abstains** — never fabricate
  a fact/PMID/persona. Render shows `mock`/abstain/provenance verbatim (already the case).
- **Data boundary intact:** internal (moat) data never crosses to an external-fetch agent; EMET = external plane,
  public identifiers only. The two-plane render must stay correct.
- **Engine stays stdlib-only** (lazy-import heavy deps); **don't touch `vendor/`**; run_live contract additive-only.
- **All-haiku** for live agents during build/rehearsal (`CLAUDE_MODEL`/the cheap profile). Captured scenario replays $0.
- **Gates 1–5** before every PR (Feature-tier → also Gate 6). Offline tests must stay green + not require live calls in CI.

## Tracks

### Track B — finish `dispatch-optimization` (Rohan Claude, FIRST; already in flight)
Per `docs/superpowers/plans/2026-06-24-dispatch-optimization.md`: spike+baseline → Opt1 (sub-agents stop loading
CLAUDE.md, cache-friendly) → Opt2 (batch-per-bucket, flagged) → Opt3 (warm stream-json worker, per-agent context
reset, cold fallback). Ship what's solid; write up Opt3 as a HELP/design note if stream-json isn't clean. DoD: a
full live (haiku) run is materially cheaper/faster than baseline, with measured before/after; agent outputs/contracts
byte-identical.

### Track A — KEYSTONE: `live-emet-session-reuse` (in-session orchestration) (Rohan Claude)
Make the EMET agent use the **already-authenticated** browser session by running the EMET step **inside the
orchestrator's own Claude tool-session** (the `/sapphire`-skill pattern with the shared Playwright MCP) instead of a
detached `claude -p` subprocess. So `run_live`'s `emet-runner` returns **live cited PMIDs** when a session exists.
- Keep the existing **honest-abstain** path intact for when no session is available (login_required → abstain, no
  fabrication). The in-session path is additive behind the `emet_handler` seam; the subprocess path remains as fallback.
- Engine stays stdlib (the in-session runner lives behind the handler seam; lazy). Offline tests use the injected
  mock handler (no live browser in CI). Add a test that the in-session handler is selected when available and that
  abstain still fires when not.
- DoD: with a logged-in EMET session, a live run lands ≥1 real `emet-live` PMID fact in the external plane; without
  one, it abstains honestly. Document the one-time login step.
- **Risk/halt:** this is the hardest task. If in-session reuse hits an architectural wall, fall back to the
  shared-`--user-data-dir` profile route (document it + flag the credential-at-rest note to Rohan in HELP) rather
  than waking Rohan — ship *a* working live-EMET path, honestly labeled.

### Track D — capture the TSC2 demo scenario (Rohan Claude, after B+A)
Run the **TSC2 / tuberous-sclerosis** query through the real firm (haiku, EMET live) once, and **capture it as a
deterministic scenario** (`scenarios/` + `_build/capture_scenario.py` machinery) so the front end can replay it
instantly at $0. The scenario must reflect the REAL run (real moat facts, real EMET PMIDs, real seam/corpus facts,
the persona spread, the synthesis, ideally a surfaced internal-vs-literature **DIVERGENCE**). DoD: the captured
scenario loads in the front end and renders the full transparent firm; a short `docs/` note describes the demo
script (what to type, what to point at — the two planes, the divergence, the spread).

### Track E — robyn_scs as a callable Bucket-1 firm tool (Rohan Claude, last / if time)
Wire the **already-vendored + endpoint-wired** robyn_scs (`tools/robyn_scs/`) into the firm as a Bucket-1 tool seam
(`sapphire-orchestrator/tools/…_seam.py` pattern), so the orchestrator *can* call it (e.g., when a query implicates
electrophysiology connectivity). Heavy deps stay in the tool (stdlib engine). Honest: only fires when relevant;
abstains/skips otherwise. DoD: the firm can invoke a robyn_scs endpoint behind the seam, traced + provenance-stamped,
without running the full pipeline in CI. (Independent of the TSC2 capture — may not fire for TSC2.)

### Track C — corpora breadth (Hayes 6 / Gavin 3 remaining, autonomous)
Keep shipping dual-source Bucket-1 corpora per the locked METHOD (one PR each). Deeper dossier = richer demo. No
change to their flow; Head Claude gates each.

## Sequencing (Rohan Claude)
**B (finish) → A (keystone) → D (capture) → E (robyn seam).** One PR per track; STOP after each for Head Claude to
gate. If blocked, write `dev/HELP.md` and keep working on the next unblocked track.

## Auditor model (Head Claude)
- React to PRs (event monitors) + a 30-min backup cron sweep; gate in isolated worktrees (never the main tree —
  Rohan Claude builds there); auto-merge all-green, else request changes + leave open; answer HELP on main.
- **Wake Rohan only at a genuine halt-point:** a data-boundary/credential decision, a stuck keystone with no honest
  fallback, or a gate that can't pass. Routine progress waits for the morning report.
- **Morning report by 08:30** → `dev/reports/overnight-2026-06-25-demo.md`: what shipped, the demo state (can we run
  it live? is the scenario captured?), what's mocked/abstaining + why, the single next step, anything that needs Rohan.

## Wind-down
All PRs gated (none left dangling), status/ledger current, the captured scenario verified to replay, monitors/crons
reconciled, morning report filed.
