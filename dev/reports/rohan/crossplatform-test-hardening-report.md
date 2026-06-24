# Task H — Cross-platform test hardening — report

**Branch:** `rohan/crossplatform-test-hardening`
**Built-By:** rohan
**Tier:** Standard (test-only portability fixes; facts/behavior unchanged)

## Goal
Fix three pre-existing cross-platform test failures Hayes flagged (resolved HELP entry).
These are portability fixes only — no engine facts or behavior change.

## Changes

### 1. `moat/tests/test_client.py` — clone-dir name hardcoded
`test_default_db_path_ends_with_repo_relative_path` asserted the default moat DB path
ended with the literal `sapphire-capability-map/RohanOnly/moat/moat.sqlite`. A clone in
any other directory name (e.g. `sapphire-overnight/...`) failed.

**Fix:** derive the repo-root dir name at runtime. The test file sits at
`<repo>/sapphire-orchestrator/moat/tests/`, so `Path(__file__).resolve().parents[3]` is the
repo root — the same root `moat/client.py` resolves via `parents[2]` for `_REPO_ROOT`. The
expected suffix is now `f"{repo_root.name}/RohanOnly/moat/moat.sqlite"`. Passes regardless of
clone dir name.

### 2. `tests/test_scenarios.py` — `UnicodeDecodeError` on cp1252 (Windows)
`Path.read_text()` uses the locale default encoding; on a cp1252 Windows locale, reading the
UTF-8 scenario/manifest JSON raised `UnicodeDecodeError`.

**Fix:** added `encoding="utf-8"` to all five `read_text()` calls in the module.

### 3. `trace_view.py` — `UnicodeEncodeError` writing `✓` to cp1252 stdout
`main()` did `print(render(...))`; the rendered trace contains `✓` (U+2713), which a cp1252
stdout cannot encode → crash on Windows.

**Fix:** routed the write through a new `_safe_print()` that writes to `sys.stdout` and, on
`UnicodeEncodeError`, round-trips the text through the stream's own encoding with
`errors="replace"`. The CLI never crashes on a legacy locale. Stdlib-only; no behavior change
on a UTF-8 stdout.

**Regression test added:** `test_main_survives_cp1252_stdout` swaps `sys.stdout` for a
`TextIOWrapper(BytesIO, encoding="cp1252")` (which genuinely cannot represent `✓`) and asserts
`main([eid])` returns 0. Verified non-vacuous — `render(eid)` for the fixture trace does
contain `✓`, so the naive `print` path raises without the fix.

## Gates

- **Gate 1 — full suite green:** `bash dev/run-tests.sh` → **343 tests, GREEN**
  (contracts 23 · harness 68 · emet 18 · memory 14 · selfimprove 20 · moat 68 · tests 132).
  Baseline was 342; +1 is the new cp1252 regression test.
- **Gate 3 — provenance/secrets:** no secrets, no binaries, no provenance changes (test-only +
  one stdlib stdout guard).
- **Gate 4 — stdlib runtime:** `_safe_print` uses only `sys`; no third-party imports added.

## Files changed
- `sapphire-orchestrator/moat/tests/test_client.py`
- `sapphire-orchestrator/tests/test_scenarios.py`
- `sapphire-orchestrator/trace_view.py`
- `sapphire-orchestrator/tests/test_trace_view.py`
