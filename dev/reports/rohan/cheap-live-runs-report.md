# cheap-live-runs — real EMET + real moat without burning default-model tokens — report

**Branch:** `rohan/cheap-live-runs` · **Built-By:** rohan · **Tier:** Standard (2 independent work-items)

## Goal
A live run that uses **real moat + real EMET (the user's logged-in session) + real seams/corpora**, but
with LLM reasoning on **haiku** so it doesn't burn default-model tokens.

## W1 — wire EMET into the live ctx
- `live_engine._wire_emet_handler(ctx)` `setdefault`s a real `emet_handler`
  (`emet.handler.make_emet_handler()`) — **lazy import** so the stdlib engine import graph stays clean
  (verified: `import live_engine` pulls **no** third-party module and does **not** load `emet.handler`).
  `run_live(ctx=None)` now **registers** EMET → `emet-runner` is no longer silently absent. A
  caller-supplied handler (tests) is **not** overridden.
- **Session reuse — verified, not assumed, not faked.** The live runner (`emet/handler.py::_default_runner`)
  drives EMET by shelling out to a **separate `claude -p` subprocess** with its own Playwright MCP
  browser. Inspection of `~/.claude.json` shows the Playwright MCP is the default (no `--isolated` /
  no `--user-data-dir`) → a persistent profile, so a BenchSci login *can* persist to disk. **But** the
  subprocess does **not** inherit THIS interactive session's live, logged-in browser/tabs and contends
  on the Chrome profile lock, so reliable reuse is **not cleanly guaranteed** from the pure-Python
  `run_live` path. Per the brief I did **not** fake it: a login screen → `{"login_required": true}` →
  the handler `escalate`s → the agent **abstains honestly** (no fabricated facts). The session-sharing
  design question is raised in **`dev/HELP.md`** (options: EMET-MCP / shared persistent profile /
  in-session orchestration).
- **Tests:** `_wire_emet_handler({})` registers a callable handler; an injected handler is not
  overridden; a mock handler **fires** and lands an `emet-live` fact in the dossier; `ctx=None`'s
  registered handler is actually **invoked** and `emet-runner` reports `ok` (not abstained) — all
  offline, no live browser.

## W2 — cheap-live controls
- **(a) Model pass-through:** `harness/dispatch.py::dispatch_claude` adds `["--model", CLAUDE_MODEL]`
  when the env is set (additive; mirrors `serve.py`). Unset → CLI default (existing behavior). Tested
  with a fake runner that **captures argv** (present when set, absent when unset).
- **(b) "Live (cheap · haiku)" profile:** `frontend/` gains a 3rd Chainlit profile = real backends +
  **haiku** for every claude agent (Bucket-1 facts + Bucket-2 personas), pinned via `CLAUDE_MODEL`
  through `bridge.run(..., model=)`. The bridge **sets and restores** `CLAUDE_MODEL` around the run
  (scoped; tested set-during + restore-after). I chose **haiku-for-everything** over mock-personas as
  the cleanest honest option (the brief's explicit "OR" choice): real facts + real-but-cheap personas,
  nothing mocked or relabeled, **zero engine/harness change beyond W2(a)**. Mock-personas-only would
  need a per-agent runner seam — noted as a possible follow-up. Existing **Demo/Live profiles
  unchanged**.
- **EMET honors the lever too:** `emet/handler.py::_default_runner` threads `["--model", …]` (same
  `CLAUDE_MODEL`/`SAPPHIRE_MODEL` precedence) into the EMET `claude -p` subprocess, so the cheap
  profile's "every claude agent on haiku" is accurate and EMET's own claude cost is capped, not left
  on the default model (Head Claude Gate-2 finding). Tested by capturing the subprocess argv.

## Gate evidence
- **Gate 1 — full suite:** `bash dev/run-tests.sh` → **490 GREEN** (harness 71 · emet 21 · tests 206 ·
  frontend 31 · …). +12 new tests. (One transient slow-suite RED, under concurrent load, re-ran green.)
- **Gate 3 — provenance/secrets:** no secrets/binaries; data boundary intact (EMET = `emet-live` →
  external plane, public identifiers only; the skill rejects internal IDs). No new provenance labels.
- **Gate 4 — stdlib runtime:** importing `live_engine` pulls **no** third-party and does not import
  `emet.handler` (lazy). `dispatch.py` change uses only stdlib `os`.
- **Gate 5 — functional:** the app boots; the profile selector shows **3 profiles** incl
  "Live (cheap · haiku)" (honestly labeled — real backends + haiku); the **Demo** profile still renders
  the full transparency view (no regression from the 3-profile routing). The live/cheap paths
  (claude CLI + logged-in EMET) are token-burning + env-dependent; their wiring is proven by the
  offline unit tests (argv `--model`, env set/restore, handler registration+invocation).

## Constraints honored
Engine stays stdlib-only (lazy EMET import); additive-only to the `run_live` contract; `vendor/`
untouched; Demo/Live profiles unbroken; honesty over a fragile fake-live path (honest-abstain + HELP).
