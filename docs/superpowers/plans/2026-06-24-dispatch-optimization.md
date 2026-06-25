# Task brief — dispatch optimization (warm Claude, no redundant context re-reads)

*Owner: **rohan** (built by Rohan Claude; Head Claude reviews/gates/merges). Tier: **Standard→Feature** (spike →
staged opts). Created 2026-06-24. **Sequence: do `cheap-live-runs` FIRST and let it merge** — both edit
`harness/dispatch.py` (cheap-live adds the `--model` pass-through); start this from the updated `main` to avoid conflicts.*

## Why
A live `run_live` fans out ~16 agents (Bucket-1 facts + Bucket-2 personas + synthesis), and **each is a fresh
`claude -p` subprocess** (`harness/dispatch.py::dispatch_claude`, `subprocess.run(cmd, cwd=ROOT)`). Two costs:
1. **~16 cold CLI boots** per run (latency).
2. Because `cwd=ROOT`, **every sub-agent auto-loads CLAUDE.md (project memory) + the tool/system preamble** —
   redundant context the agent doesn't need (its spec is already in the prompt). Anthropic's 5-min prompt cache
   amortizes the *shared identical prefix* across calls, but cache misses (>5-min gaps, prefix drift) and the
   unnecessary CLAUDE.md load still re-pay tokens.
Goal: keep agents **warm** and stop re-reading context they don't need — **on the subscription, no API key** —
without changing any agent's output, contract, guardrails, or provenance.

## Hard invariants (do NOT regress)
- Every optimization lives **behind the existing `dispatch_claude` seam**; the `runner=` injection + all offline
  tests (which never call live claude) must keep working unchanged.
- Agent **outputs, schemas, guardrails, provenance** are byte-for-byte unaffected — this is a transport/cost change only.
- Engine stays **stdlib-only**. Don't touch `vendor/`. Don't break `cheap-live-runs` (`CLAUDE_MODEL`→`--model`).
- **Honesty:** no fabrication; if a warm path errors, fall back to the current cold `claude -p` rather than guessing.

## Step 0 — Spike + baseline (do this first, report before building)
- Confirm the exact CLI capabilities in THIS `claude` version: (a) how to **disable project-memory load /
  set a tight system prompt** for a sub-agent call (so it stops dragging in CLAUDE.md); (b) whether
  `--input-format stream-json --output-format stream-json` (persistent stdin) is supported for a long-lived process.
- **Measure the current baseline:** instrument one real (or haiku) `run_live` and record per-run **wall-clock** +
  **token usage** (the `claude` JSON envelope returns `modelUsage`/usage — sum it). This is the number every opt is
  measured against. Put it in the report; don't optimize blind.

## Opt 1 — stop sub-agents re-loading CLAUDE.md (small, safe, first)
- Run `dispatch_claude` from a **minimal cwd without a CLAUDE.md** (or the flag that disables project memory) and
  pass a **tight `--system-prompt`** so each agent carries only its spec + inputs, not the whole repo memory.
- Keep the **shared firm preamble identical and FIRST** in the prompt so the 5-min prompt cache hits across agents.
- Verify outputs unchanged (same fixtures/schemas). Report token delta vs baseline.

## Opt 2 — batch per bucket (medium)
- Replace N-subprocess-per-bucket with **one `claude` call per bucket**: one for all Bucket-1 claude-fact agents,
  one for the persona panel — each returning a **schema-enforced array**, with per-item provenance/guards still
  applied after parsing. ~16 boots → ~3. Keep the per-agent guardrail + provenance stamping in the harness.
- This must be **opt-in / behind a flag** so the per-agent path stays available (and tests can pick either).

## Opt 3 — warm worker (the "warm start", bigger; staged last)
- Keep **one (or a small pool of) long-lived `claude` process(es)** in stream-json mode, booted once per run and
  reused across agents. **Critical:** reset context per agent (fresh logical turn / clear) so the conversation does
  NOT accumulate prior agents' turns (warm *process*, cold *conversation*) — otherwise you ADD tokens. Manage the
  process lifecycle (spawn, health-check, teardown, timeout) and **fall back to cold `claude -p` on any failure**.
- Behind `dispatch_claude`; `runner=` injection still overrides for tests. Report wall-clock + token delta.

## Definition of done
- Step-0 spike + baseline reported (flags confirmed, current token/latency numbers).
- Opt 1 shipped (sub-agents no longer load CLAUDE.md; cache-friendly prefix); Opt 2 behind a flag; Opt 3 staged
  with cold-fallback. Each with a measured before/after in the report.
- Suite green; offline tests untouched in behavior; agent outputs/contracts/guards/provenance identical; engine stdlib.
- Gates 1–5 (Feature → also Gate 6 whole-branch if it grows large). Hand to Head Claude; don't self-merge.

## Notes
- Don't over-engineer Opt 3 if the spike shows stream-json isn't cleanly supported — Opt 1 + 2 capture most of the
  win; in that case ship 1+2 and write up 3 as a HELP/design note rather than a fragile implementation.
- Measure, don't assume. "SOTA on shit is still shit" — a warm worker that bloats context is worse than cold `-p`.
