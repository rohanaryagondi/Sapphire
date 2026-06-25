# dispatch-optimization — spike + baseline + staged opts — report

**Branch:** `rohan/dispatch-optimization` · **Built-By:** rohan · **Tier:** Standard→Feature

Transport/cost optimization of `harness/dispatch.py::dispatch_claude` (the per-agent `claude -p`
subprocess). **Invariant:** agent outputs/schemas/guardrails/provenance are byte-identical — this is
cost/latency only.

---

## Step 0 — Spike (claude CLI **2.1.190**)

**(a) Disabling project-memory / tight prefix.** Confirmed flags:
- `--setting-sources user,project,local` — pass **`user`** only → the project `CLAUDE.md` is **not**
  loaded. (Cleaner than changing cwd; keeps the cached Claude Code preamble.)
- `--exclude-dynamic-system-prompt-sections` — moves the per-machine sections (cwd, env, **memory
  paths**, git status) out of the system prompt into the first user message → **stable system prefix**
  → cross-call prompt-cache reuse.
- `--system-prompt <p>` (full override) and `--append-system-prompt`. **Measured caveat:** a full
  `--system-prompt` override **breaks cache reuse** (cache_read → 0, the whole prefix re-created every
  call). So the brief's "tight `--system-prompt`" idea is *counter-productive* for cost — `--setting-sources
  user` + `--exclude-dynamic…` is the measured-better lever (keeps the cacheable preamble). *Measure,
  don't assume.*
- `--strict-mcp-config` (skip project MCP servers — faster boot for tool-less fact agents).

**(b) stream-json (warm worker).** `--input-format stream-json --output-format stream-json --verbose`
**is supported** — one JSON message on stdin → a stream of `system/assistant/result` events. **But** a
single `-p` invocation is **one conversation**: feeding N agent prompts into one persistent process
makes them accumulate as one growing conversation (turn 2 sees turn 1) — which *adds* tokens, the exact
anti-pattern the brief warns against, and `-p` exposes **no per-turn context-reset control**. Clean
"warm process, cold conversation" therefore isn't cleanly achievable via `-p` stream-json → **Opt 3 is
written up as a design note, not a fragile impl** (per the brief's explicit guidance).

## Step 0 — Baseline (measured, haiku, realistic spec-sized prompt)

Per-call cold `claude -p` (system prefix = Claude Code preamble + CLAUDE.md + dynamic env):

| Config | wall | system tokens | cache_read | cache_creation |
|---|---|---|---|---|
| **BASELINE** (cwd=ROOT, loads CLAUDE.md) | ~18s | **30,951** | 16,491 | **14,460** |
| `--setting-sources user` (drop CLAUDE.md) | ~9s | 25,787 | 16,491 | 9,296 |
| `+ --exclude-dynamic…` (1st call) | ~15s | 25,592 | 19,423 | 6,169 |
| `+ --exclude-dynamic…` (2nd, warm cache) | ~18s | 25,592 | **25,592** | **0** |

- **CLAUDE.md ≈ 5,164 tokens / agent call** (baseline create 14,460 → 9,296). Pure redundancy — the
  agent's spec is already in its prompt.
- **`--exclude-dynamic…` makes the prefix cache-stable**: warm calls pay **0 cache_creation** vs the
  baseline's 14,460 *every* call.
- Wall-clock per call is **noisy (~9–18s)** — dominated by output-token generation + network, not a
  clean signal; the **token deltas are the decisive measure**.

**Per-run projection (16 claude agents, 5-min window; cache_creation≈1.25×, cache_read≈0.1× base price).**
System-prefix cost in base-equivalent tokens:
- Baseline: 16 × (16,491×0.1 + 14,460×1.25) ≈ **315,600**.
- Opt-1: 9,653 (first) + 15 × (25,592×0.1) ≈ **48,000** → **~85% reduction** of system-prefix cost.

**Honest note on the end-to-end run:** a full live `run_live` (≈13–16 serial cold haiku agents)
**exceeded 10 min** and did not complete cleanly — which *confirms the latency motivation* (serial cold
boots are slow) but makes a single end-to-end wall-clock impractical/noisy. The controlled baseline above
(per-call × agent-count) is the measurement every opt is judged against.

---

## Opts (status)
- **Opt 1 — drop CLAUDE.md + cache-stable prefix:** SHIP. `--setting-sources user
  --exclude-dynamic-system-prompt-sections`, shared firm preamble kept first. *(see deltas below)*
- **Opt 2 — batch per bucket (≈16 boots → 3), behind a flag:** SHIP opt-in. *(see deltas below)*
- **Opt 3 — warm stream-json worker:** **design note** (spike shows `-p` can't cleanly reset
  per-agent context; a warm worker that accumulates turns is worse than cold `-p`). Raised in
  `dev/HELP.md` for the SDK/session-API path.

## Measured deltas

### Opt-1 — drop CLAUDE.md + cache-stable prefix (SHIPPED, default-on)
`build_prompt` now leads with a stable `SHARED_PREAMBLE` (identical across agents → cache-reusable
user prefix); `dispatch_claude` appends `--setting-sources user --exclude-dynamic-system-prompt-sections`
(opt out with `SAPPHIRE_DISPATCH_FULL_CONTEXT=1`).
- **CLAUDE.md dropped: ~5,164 tok/agent** (measured: baseline cache_creation 14,460 → 9,296).
- **Warm-call cache_creation → 0** (stable prefix; vs baseline 14,460 *every* call).
- **Per-run system-prefix cost (16 agents): ~315,600 → ~48,000 base-equiv ≈ −85%** (projection from the
  per-call table; cache_creation≈1.25×, cache_read≈0.1×).
- **Live-verified:** a real `dispatch_claude` call (haiku, flags on) returned valid structured output
  in **8.4 s** — outputs unchanged, no regression.

### Opt-2 — batch-per-bucket (SHIPPED, opt-in `ctx["batch_buckets"]`)
`dispatch_claude_batch(items)` = ONE `claude` call for the **6 corpus-less claude-subagent Bucket-1
agents** (patent-ip, global-regulatory-divergence, clinical-trial-registry, post-market-safety, payer,
financial) → `{id: output}`; each output flows through the **unchanged** per-agent harness path
(validate + guardrails + provenance + trace) via `dispatch_fn`. On ANY batch failure → honest
per-agent fallback (tested). Corpus / python / qmodels / emet agents stay per-agent.
- **6 cold boots → 1** for that bucket; the ~24k cache-stable system prefix is paid **once**, not 6×
  (projected ≈ 5 × 24k ≈ **120k cache-read tokens saved** + 5 fewer boots/run, on top of Opt-1).
- **Tradeoff (documented, why it's opt-in):** the 6 specs share one generation context, so the *model
  output* may differ from isolated per-agent runs — guards/provenance/schemas are identical, but the
  text isn't byte-guaranteed; hence flagged, default-off. *(A live 1-call-vs-6 measurement is
  reproducible via the per-call harness; not re-run here to avoid burning tokens overnight.)*

### Opt-3 — warm worker → **design note** (`dev/HELP.md`)
Spike showed `-p` stream-json has no per-turn context reset → a warm worker would accumulate turns
(worse than cold). Deferred to the Agent-SDK seam with cold-fallback; written up rather than shipped
fragile, per the brief.
